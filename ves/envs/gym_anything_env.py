"""CUA-World (gym-anything) backend: the benchmark's own environment specs, task setup hooks and verifiers.

The runner is chosen by gym-anything from GYM_ANYTHING_RUNNER (on ABCI: "qemu", QEMU inside Apptainer).  The agent
loop owns the step budget, so gym-anything's own max_steps/timeout termination is switched off after reset.

Spec keys: env_dir (absolute), task (task id), ga_root (gym-anything checkout; env.json mount paths are relative
to it), use_cache, settle_s (extra wait after each action, VisualSkill's controller waits 2 s), copy_out (paths
inside the desktop copied out after the episode), ignore_boxes (screen regions excluded from difference images).
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .base import DesktopEnv, EnvError


def to_ga_actions(a: dict) -> list[dict]:
    """Backend-neutral action -> gym-anything action list (same mapping as VisualSkill's bridge.py)."""
    k = a["kind"]
    if k == "click":
        return [{"mouse": {f"{a['button']}_click": [a["x"], a["y"]]}}]
    if k == "double_click":
        return [{"mouse": {"double_click": [a["x"], a["y"]]}}]
    if k == "move":
        return [{"mouse": {"move": [a["x"], a["y"]]}}]
    if k == "drag":
        return [{"mouse": {"left_click_drag": [[a["x1"], a["y1"]], [a["x2"], a["y2"]]]}}]
    if k == "scroll":  # ours: positive = up; gym-anything: positive = down
        return [{"mouse": {"move": [a["x"], a["y"]]}}, {"mouse": {"scroll": -int(a["clicks"])}}]
    if k == "type":
        return [{"keyboard": {"text": a["text"]}}]
    if k == "key":
        return [{"keyboard": {"keys": list(a["keys"])}}]
    raise ValueError(f"unknown action kind {k!r}")


class GymAnythingDesktop(DesktopEnv):
    def __init__(self, spec: dict):
        self.spec = spec
        self._env = None
        self.episode_dir: Path | None = None
        w, h = spec.get("native_size", (1920, 1080))
        self.native_size = (int(w), int(h))

    @property
    def runner(self):
        return self._env._runner

    def reset(self, seed: int) -> dict:
        if self.spec.get("runner"):
            os.environ["GYM_ANYTHING_RUNNER"] = self.spec["runner"]
        os.environ.update({k: str(v) for k, v in (self.spec.get("env_vars") or {}).items()})
        # env.json mount and recording paths are relative to the gym-anything root; one episode runs per process
        os.chdir(self.spec["ga_root"])
        from gym_anything.api import from_config
        t0 = time.time()
        try:
            self._env = from_config(self.spec["env_dir"], self.spec["task"])
            self._env.reset(seed=seed, use_cache=bool(self.spec.get("use_cache", False)))
        except Exception as e:
            raise EnvError(f"environment reset failed: {type(e).__name__}: {e}") from e
        self._env.set_episode_limits(max_steps=None, timeout_sec=None)
        self.episode_dir = Path(self._env.episode_dir) if self._env.episode_dir else None
        return {"backend": "gym_anything", "runner": getattr(self._env, "runner_name", None),
                "env_id": self._env.env_spec.id, "task_spec_id": self._env.task_spec.id if self._env.task_spec else None,
                "episode_dir": str(self.episode_dir) if self.episode_dir else None,
                "reset_s": round(time.time() - t0, 1), "software": self._versions()}

    def _versions(self) -> dict:
        out = {}
        cap = getattr(self.runner, "exec_capture", None)
        for name, cmd in self.spec.get("version_cmds", {"gimp": "gimp --version", "os": "lsb_release -ds"}).items():
            try:
                out[name] = (cap(cmd) or "").strip()[:200] if cap else None
            except Exception as e:
                out[name] = f"unavailable ({type(e).__name__})"
        return out

    def screenshot(self) -> bytes:
        fd, name = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        path = Path(name)
        try:
            if not self.runner.capture_screenshot(path) or not path.exists() or path.stat().st_size == 0:
                raise EnvError("screenshot capture failed")
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)

    def execute(self, action: dict) -> bytes:
        try:
            self._env.step(to_ga_actions(action))
        except Exception as e:
            raise EnvError(f"action failed: {type(e).__name__}: {e}") from e
        time.sleep(float(self.spec.get("settle_s", 2.0)))
        return self.screenshot()

    def finalize(self, outputs_dir: Path) -> dict:
        t0 = time.time()
        try:
            summary = self._env._complete_episode()  # post-task hook (e.g. automated export), settle, verifier
        except Exception as e:
            raise EnvError(f"post-task hook or verifier failed: {type(e).__name__}: {e}") from e
        copied, errors = [], []
        for src in self.spec.get("copy_out", ["/home/ga/Desktop"]):
            try:
                dst = Path(outputs_dir) / src.strip("/").replace("/", "__")
                self.runner.copy_from(src, str(dst))
                copied.append({"src": src, "dst": str(dst)})
            except Exception as e:
                errors.append({"src": src, "error": f"{type(e).__name__}: {e}"})
        ver = (summary or {}).get("verifier") or {}
        passed = bool(ver.get("passed"))
        try:
            score = float(ver.get("score", 100.0 if passed else 0.0))
        except (TypeError, ValueError):
            score = 100.0 if passed else 0.0
        spec = self._env.task_spec
        program = getattr(getattr(getattr(spec, "success", None), "spec", None), "program", None) if spec else None
        return {"passed": passed, "score": round(score / 100.0 if score > 1.0 else score, 4),
                "feedback": str(ver.get("feedback", "")), "verifier": program, "raw": summary,
                "copied": copied, "copy_errors": errors, "verify_s": round(time.time() - t0, 1)}

    def close(self) -> None:
        if self._env is not None:
            try:
                self._env.close()
            finally:
                self._env = None

    def diff_ignore_boxes(self):
        return [tuple(b) for b in self.spec.get("ignore_boxes", [(0, 0, self.native_size[0], 34)])]
