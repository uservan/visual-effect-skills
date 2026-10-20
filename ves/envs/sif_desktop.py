"""CUA-World tasks in a rootless Singularity desktop (ABCI jobs have no root, no Docker and no usable /dev/kvm).

One container instance per episode from the image built by ves/envs/container/gimp.def: Xvfb on display :1 (the
display number the task scripts hard-code) and the fluxbox window manager.  The benchmark's own files are used
unchanged: env.json mounts (/workspace/scripts, /workspace/config, /workspace/tasks), the post_start hook, the task's
pre_task / post_task hooks (run exactly as gym-anything runs them: `bash -lc <hook> > /home/ga/<stage>.log 2>&1`) and
the task's verifier through gym-anything's VerifierRunner.  Differences from gym-anything's Docker environment:
no GNOME / systemd; hooks run as an unprivileged user with the image's sudo / su / apt-get / chown shims; the
env's pre_start hook (apt-get install of GIMP) is replaced by the image, which has those packages; GIMP's
profile and font caches are warmed once per environment (template home); GIMP image windows open maximized.
Actions are injected with the same pyautogui calls as gym-anything's QEMU runner.

Spec keys: image, env_dir, task, ga_root (absolute paths), work_root (per-episode directories; default
$PBS_LOCALDIR/ves-episodes), template_root (default <repo>/vm/homes), settle_s (wait after an action; default 4.0 =
gym-anything's 2 s step wait + VisualSkill's 2 s screenshot pause), post_task_settle_s (default 15, as
gym-anything), stable_timeout_s (wait for a still screen before the first observation), copy_out, keep_work.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .base import DesktopEnv, EnvError

PROJECT = Path(__file__).resolve().parents[2]
# HOME cannot be overridden with --env in Singularity; the home directory is set with --home at instance start and
# exported again at the start of every shell command
EXEC_ENV = ("DISPLAY=:1", "USER=ga", "LOGNAME=ga", "XDG_RUNTIME_DIR=/tmp/runtime-ga")
SHELL_PREFIX = "export HOME=/home/ga USER=ga LOGNAME=ga DISPLAY=:1 XDG_RUNTIME_DIR=/tmp/runtime-ga; cd /home/ga 2>/dev/null; "
FLUXBOX_INIT = "session.screen0.toolbar.visible: false\nsession.screen0.workspaces: 1\n"
FLUXBOX_APPS = "[app] (role=gimp-image-window)\n  [Maximized] {yes}\n[end]\n"


def _key_map() -> dict:
    from gym_anything.runtime.runners.qemu_apptainer import QemuApptainerRunner
    return dict(QemuApptainerRunner._KEY_NAME_MAP)


def pyautogui_script(a: dict, key_map: dict) -> str:
    """The pyautogui calls gym-anything's QEMU runner makes for the same action (inject_action)."""
    k = a["kind"]
    if k == "click":
        cmd = f"pyautogui.click({int(a['x'])}, {int(a['y'])}, button={a['button']!r})"
    elif k == "double_click":
        cmd = f"pyautogui.doubleClick({int(a['x'])}, {int(a['y'])})"
    elif k == "move":
        cmd = f"pyautogui.moveTo({int(a['x'])}, {int(a['y'])})"
    elif k == "drag":
        cmd = (f"pyautogui.moveTo({int(a['x1'])}, {int(a['y1'])}); "
               f"pyautogui.drag({int(a['x2'] - a['x1'])}, {int(a['y2'] - a['y1'])}, duration=0.5, button='left')")
    elif k == "scroll":  # ours and pyautogui's: positive = up
        cmd = f"pyautogui.moveTo({int(a['x'])}, {int(a['y'])}); pyautogui.scroll({int(a['clicks'])})"
    elif k == "type":
        cmd = f"pyautogui.write({a['text']!r}, interval=0.03)"
    elif k == "key":
        keys = ", ".join(repr(key_map.get(x.lower(), x.lower())) for x in a["keys"])
        cmd = f"pyautogui.hotkey({keys})"
    else:
        raise ValueError(f"unknown action kind {k!r}")
    return "import pyautogui; pyautogui.FAILSAFE = False; pyautogui.PAUSE = 0.02; " + cmd


def _file_digest(path: Path) -> str:
    st = path.stat()
    return f"{path.name}:{st.st_size}:{int(st.st_mtime)}"


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    if root.exists():
        for p in sorted(q for q in root.rglob("*") if q.is_file()):
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class SifDesktop(DesktopEnv):
    def __init__(self, spec: dict):
        self.spec = spec
        self.image = Path(spec["image"])
        self.env_dir = Path(spec["env_dir"])
        self.task = spec["task"]
        self.ga_root = Path(spec["ga_root"])
        w, h = spec.get("native_size", (1920, 1080))
        self.native_size = (int(w), int(h))
        self.name: str | None = None
        self.work: Path | None = None
        self.episode_dir: Path | None = None
        self.stages: dict = {}
        self._env_spec = self._task_spec = None
        self._keys = _key_map()

    # ---- singularity -------------------------------------------------------------------------------
    def _run(self, args: list[str], timeout: float, binary: bool = False) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(args, capture_output=True, timeout=timeout, text=not binary)
        except subprocess.TimeoutExpired as e:
            raise EnvError(f"timed out after {timeout}s: {' '.join(args[:6])} ...") from e

    def _exec_args(self, name: str | None = None) -> list[str]:
        args = ["singularity", "exec", "--cleanenv"]
        for kv in EXEC_ENV:
            args += ["--env", kv]
        return args + [f"instance://{name or self.name}"]

    def sh(self, cmd: str, timeout: float = 600, name: str | None = None) -> subprocess.CompletedProcess:
        return self._run(self._exec_args(name) + ["bash", "-lc", SHELL_PREFIX + cmd], timeout)

    def _start_instance(self, name: str, home: Path, tmp: Path, mounts: list[tuple[str, str, str]]) -> None:
        """home: host directory that holds ga/ (becomes /home/ga); tmp: host directory for the container's /tmp
        (private per episode, so each container has its own X socket for display :1)."""
        args = ["singularity", "instance", "start", "--userns", "--contain", "--cleanenv", "--writable-tmpfs",
                "--home", f"{home}/ga:/home/ga", "--bind", f"{tmp}:/tmp"]
        for src, dst, mode in mounts:
            args += ["--bind", f"{src}:{dst}" + (":ro" if mode == "ro" else "")]
        for kv in EXEC_ENV:
            args += ["--env", kv]
        r = self._run(args + [str(self._staged_image()), name], timeout=180)
        if r.returncode != 0:
            raise EnvError(f"instance start failed: {r.stderr.strip()[-800:]}")

    def _staged_image(self) -> Path:
        """The image copied once per job to the node-local disk.  /groups is reachable only through the gcg51557
        group, which user-namespace processes may lose (seen with --fakeroot in job 2726350), so the container should
        not depend on it.  The template key keeps using the original file."""
        local = os.environ.get("PBS_LOCALDIR")
        if not local or not self.spec.get("stage_local", True):
            return self.image
        dst = Path(local) / "ves-image" / self.image.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst.parent / ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not dst.exists() or dst.stat().st_size != self.image.stat().st_size:
                part = dst.with_name(dst.name + ".part")
                shutil.copy2(self.image, part)
                os.replace(part, dst)
        return dst

    def _stop_instance(self, name: str) -> None:
        self._run(["singularity", "instance", "stop", name], timeout=120)

    def _start_display(self) -> None:
        w, h = self.native_size
        self.sh("mkdir -p /tmp/runtime-ga && chmod 700 /tmp/runtime-ga; "
                f"nohup Xvfb :1 -screen 0 {w}x{h}x24 -ac -nolisten tcp -nolisten local > /tmp/xvfb.log 2>&1 &", 30)
        for _ in range(30):
            if self.sh("xdpyinfo -display :1 >/dev/null 2>&1", 15).returncode == 0:
                break
            time.sleep(1)
        else:
            raise EnvError("Xvfb did not start: " + self.sh("tail -5 /tmp/xvfb.log", 15).stdout)
        self.sh("nohup fluxbox > /tmp/fluxbox.log 2>&1 &", 30)
        for _ in range(30):
            if "fluxbox" in self.sh("wmctrl -m 2>/dev/null", 15).stdout.lower():
                return
            time.sleep(1)
        raise EnvError("fluxbox did not start: " + self.sh("tail -5 /tmp/fluxbox.log", 15).stdout)

    # ---- environment template (once per environment and image) --------------------------------------
    def _template(self) -> Path:
        key = hashlib.sha256("|".join([
            _file_digest(self.image), (self.env_dir / "env.json").read_text(), _tree_digest(self.env_dir / "scripts"),
            _tree_digest(self.env_dir / "config"), FLUXBOX_INIT, FLUXBOX_APPS]).encode()).hexdigest()[:16]
        root = Path(self.spec.get("template_root") or PROJECT / "vm" / "homes")
        root.mkdir(parents=True, exist_ok=True)
        done = root / key
        with open(root / f"{key}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (done / "READY.json").exists():
                return done
            t0 = time.time()
            # built on the node-local disk (the container may not reach /groups), then copied under root by this process
            local = Path(os.environ.get("PBS_LOCALDIR") or os.environ.get("TMPDIR", "/tmp"))
            build = local / f"ves-template-{key}-{uuid.uuid4().hex[:8]}"
            (build / "home" / "ga" / ".fluxbox").mkdir(parents=True)
            (build / "tmp").mkdir()
            (build / "home" / "ga" / ".fluxbox" / "init").write_text(FLUXBOX_INIT)
            (build / "home" / "ga" / ".fluxbox" / "apps").write_text(FLUXBOX_APPS)
            name = f"ves_tpl_{uuid.uuid4().hex[:8]}"
            self._start_instance(name, build / "home", build / "tmp", [])
            try:
                # GIMP profile and plug-in / font caches, so that every episode's first GIMP start is equally fast
                r = self.sh("gimp -i -b '(gimp-quit 0)' > /tmp/gimp_warmup.log 2>&1; echo rc=$?", 900, name=name)
                version = self.sh("gimp --version", 60, name=name).stdout.strip()
                osname = self.sh(". /etc/os-release; echo $PRETTY_NAME", 60, name=name).stdout.strip()
            finally:
                self._stop_instance(name)
            meta = {"key": key, "image": str(self.image), "image_digest": _file_digest(self.image),
                    "env_dir": str(self.env_dir), "gimp": version, "os": osname, "warmup": r.stdout.strip(),
                    "seconds": round(time.time() - t0, 1), "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            staging = root / f"{key}.part-{uuid.uuid4().hex[:8]}"
            shutil.copytree(build / "home", staging / "home", symlinks=True)
            shutil.rmtree(build, ignore_errors=True)
            shutil.rmtree(done, ignore_errors=True)
            os.replace(staging, done)
            (done / "READY.json").write_text(json.dumps(meta, indent=2))
            return done

    # ---- DesktopEnv -----------------------------------------------------------------------------------
    def reset(self, seed: int) -> dict:
        from gym_anything.config.loading import _load_envspec, _load_taskspec
        t0 = time.time()
        self._env_spec = _load_envspec(self.env_dir / "env.json")  # mount sources are relative to ga_root
        self._task_spec = _load_taskspec(self.env_dir / "tasks" / self.task / "task.json")
        template = self._template()
        self.stages["template_s"] = round(time.time() - t0, 1)
        work_root = Path(self.spec.get("work_root") or Path(os.environ.get("PBS_LOCALDIR") or os.environ.get("TMPDIR", "/tmp")) / "ves-episodes")
        self.work = work_root / f"{self.task}-{uuid.uuid4().hex[:8]}"
        shutil.copytree(template / "home", self.work / "home", symlinks=True)
        (self.work / "tmp").mkdir(parents=True)
        self.episode_dir = self.work / "episode"
        self.episode_dir.mkdir()
        mounts = []
        for i, m in enumerate(self._env_spec.mounts):  # copied into the episode directory (small), see _staged_image
            src = (self.ga_root / m.source).resolve()
            if self.spec.get("stage_local", True):
                dst = self.work / "mounts" / str(i)
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                src = dst
            mounts.append((str(src), m.target, m.mode))
        self.name = f"ves_{uuid.uuid4().hex[:10]}"
        t1 = time.time()
        self._start_instance(self.name, self.work / "home", self.work / "tmp", mounts)
        self._start_display()
        self.stages["desktop_s"] = round(time.time() - t1, 1)
        hooks = self._env_spec.hooks or {}
        if hooks.get("post_start"):
            t = time.time()
            r = self.sh(f"bash -lc {hooks['post_start']} > /home/ga/env_setup_post_start.log 2>&1", 1800)
            self.stages["post_start"] = {"rc": r.returncode, "s": round(time.time() - t, 1)}
        th = self._task_spec.hooks
        if th and th.pre_task:
            t = time.time()
            r = self.sh(f"bash -lc {th.pre_task} > /home/ga/task_pre_task.log 2>&1",
                        getattr(th, "pre_task_timeout", None) or 600)
            self.stages["pre_task"] = {"rc": r.returncode, "s": round(time.time() - t, 1)}
        self.stages["stable_s"] = self._wait_stable(float(self.spec.get("stable_timeout_s", 90)))
        return {"backend": "sif", "image": str(self.image), "env_id": self._env_spec.id,
                "task_spec_id": self._task_spec.id, "template": json.loads((template / "READY.json").read_text()),
                "skipped_hooks": ["pre_start (packages are in the image)"] if hooks.get("pre_start") else [],
                "stages": dict(self.stages), "reset_s": round(time.time() - t0, 1),
                "software": self._versions(), "work_dir": str(self.work)}

    def _versions(self) -> dict:
        return {"gimp": self.sh("gimp --version", 60).stdout.strip(),
                "os": self.sh(". /etc/os-release; echo $PRETTY_NAME", 60).stdout.strip(),
                "singularity": self._run(["singularity", "--version"], 30).stdout.strip()}

    def _wait_stable(self, timeout: float) -> float:
        """Wait until two screenshots 2 s apart are identical (GIMP finished opening), at most `timeout` s."""
        t0, last = time.time(), None
        while time.time() - t0 < timeout:
            cur = hashlib.sha256(self.screenshot()).hexdigest()
            if cur == last:
                break
            last = cur
            time.sleep(2)
        return round(time.time() - t0, 1)

    def screenshot(self) -> bytes:
        r = self._run(self._exec_args() + ["import", "-window", "root", "-display", ":1", "png:-"], 60, binary=True)
        if r.returncode != 0 or not r.stdout.startswith(b"\x89PNG"):
            raise EnvError(f"screenshot failed: {r.stderr.decode(errors='replace')[-300:]}")
        return r.stdout

    def execute(self, action: dict) -> bytes:
        r = self._run(self._exec_args() + ["python3", "-c", pyautogui_script(action, self._keys)], 120)
        if r.returncode != 0:
            raise EnvError(f"action failed: {r.stderr.strip()[-500:]}")
        time.sleep(float(self.spec.get("settle_s", 4.0)))
        return self.screenshot()

    # ---- file transfer used by the verifiers (env_info["copy_from_env"]) ----------------------------
    def _host_path(self, container_path: str) -> Path | None:
        p = str(container_path)
        for prefix, host in (("/home/", self.work / "home"), ("/tmp/", self.work / "tmp")):
            if p.startswith(prefix):
                return host / p[len(prefix):]
        return None

    def copy_from(self, container_src: str, host_dst: str) -> None:
        dst = Path(host_dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src = self._host_path(container_src)
        if src is not None:
            if not src.exists():
                raise FileNotFoundError(container_src)
            if src.is_dir():
                shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return
        r = self._run(self._exec_args() + ["cat", container_src], 120, binary=True)
        if r.returncode != 0:
            raise FileNotFoundError(container_src)
        dst.write_bytes(r.stdout)

    def copy_to(self, host_src: str, container_dst: str) -> None:
        dst = self._host_path(container_dst)
        if dst is None:
            raise PermissionError(f"only /home and /tmp are writable in the container: {container_dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if Path(host_src).is_dir():
            shutil.copytree(host_src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(host_src, dst)

    def exec_capture(self, cmd: str) -> str:
        return self.sh(cmd, 600).stdout

    def finalize(self, outputs_dir: Path) -> dict:
        from gym_anything.verification.runner import VerifierRunner
        t0 = time.time()
        outputs_dir = Path(outputs_dir)
        th = self._task_spec.hooks
        if th and th.post_task:
            r = self.sh(f"bash -lc {th.post_task} > /home/ga/task_post_task.log 2>&1", 600)
            self.stages["post_task"] = {"rc": r.returncode, "s": round(time.time() - t0, 1)}
            time.sleep(float(self.spec.get("post_task_settle_s", 15)))
        try:
            (self.episode_dir / "post_verification.png").write_bytes(self.screenshot())
        except EnvError:
            pass
        try:
            ver = VerifierRunner().evaluate(runner=self, env_spec=self._env_spec, task_spec=self._task_spec,
                                            episode_dir=self.episode_dir, env_root=self.env_dir,
                                            task_root=self.env_dir / "tasks" / self.task)
        except Exception as e:
            raise EnvError(f"verifier failed: {type(e).__name__}: {e}") from e
        copied, errors = [], []
        for src in self.spec.get("copy_out", ["/home/ga/Desktop", "/home/ga/Documents"]):
            dst = outputs_dir / src.strip("/").replace("/", "__")
            try:
                self.copy_from(src, str(dst))
                copied.append({"src": src, "dst": str(dst)})
            except Exception as e:
                errors.append({"src": src, "error": f"{type(e).__name__}: {e}"})
        logs = outputs_dir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        for p in list((self.work / "home" / "ga").glob("*.log")) + list((self.work / "tmp").glob("*.log")):
            shutil.copy2(p, logs / p.name)
        if (self.episode_dir / "post_verification.png").exists():
            shutil.copy2(self.episode_dir / "post_verification.png", outputs_dir / "post_verification.png")
        passed = bool(ver.get("passed"))
        try:
            score = float(ver.get("score", 100.0 if passed else 0.0))
        except (TypeError, ValueError):
            score = 100.0 if passed else 0.0
        success_spec = getattr(self._task_spec.success, "spec", None)
        program = success_spec.get("program") if isinstance(success_spec, dict) else success_spec
        return {"passed": passed, "score": round(score / 100.0 if score > 1.0 else score, 4),
                "feedback": str(ver.get("feedback", "")), "verifier": program,
                "raw": {"verifier": ver, "stages": dict(self.stages)}, "copied": copied, "copy_errors": errors,
                "verify_s": round(time.time() - t0, 1)}

    def close(self) -> None:
        if self.name:
            try:
                self._stop_instance(self.name)
            finally:
                self.name = None
        if self.work and not self.spec.get("keep_work"):
            shutil.rmtree(self.work, ignore_errors=True)

    def diff_ignore_boxes(self):
        return [tuple(b) for b in self.spec.get("ignore_boxes", [])]
