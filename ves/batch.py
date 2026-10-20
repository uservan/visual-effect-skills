"""Run a batch of episodes (one model; tasks x conditions x seeds) with N episodes in parallel, resumably:

    python -m ves.batch --config motivation/configs/<batch>.yaml [--dry-run]

Run directories: <runs_root>/<model>/<condition>/<task_id>/s<seed>_a<attempt>/.  On every start, a run directory
without result.json is marked "interrupted" (it was killed); a (task, condition, seed) with a completed attempt is
skipped.  Interrupted attempts are retried without limit (preemption is not the run's fault); environment or
harness errors at most `max_attempts` times.  SIGTERM is forwarded to the running episodes, then exit 143.
Exit 0 when every planned run has a completed attempt, 6 when some gave up after errors (needs review).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

from .recorder import dump_json
from .tasks import load_tasks

PROJECT = Path(__file__).resolve().parent.parent
TERMINATED = False


def _on_sigterm(signum, frame):
    global TERMINATED
    TERMINATED = True


def harness_info() -> dict:
    h = hashlib.sha256()
    for p in sorted((PROJECT / "ves").rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(str(p.relative_to(PROJECT)).encode())
            h.update(p.read_bytes())
    git = lambda *a: subprocess.run(["git", "-C", str(PROJECT), *a], capture_output=True, text=True).stdout.strip()
    return {"ves_sha256": h.hexdigest(), "repo_commit": git("rev-parse", "HEAD"),
            "repo_dirty": bool(git("status", "--porcelain"))}


def _abs(p: str | None) -> str | None:
    return None if p is None else str((PROJECT / p).resolve())


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("app", "tasks"):
        if isinstance(cfg.get(key), str):  # a separate YAML file
            cfg[key] = yaml.safe_load((PROJECT / cfg[key]).read_text(encoding="utf-8"))
    urls = os.environ.get("VES_BASE_URLS")
    if urls:
        cfg["model"]["base_urls"] = urls.split(",")
    return cfg


def read_status(run_dir: Path) -> str:
    r = run_dir / "result.json"
    if r.exists():
        try:
            return json.loads(r.read_text(encoding="utf-8")).get("status", "error")
        except json.JSONDecodeError:
            return "error"
    dump_json(r, {"status": "interrupted", "error": "no result.json at batch restart (killed while running)",
                  "run_id": run_dir.name, "marked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    return "interrupted"


def plan(cfg: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (todo, done, gave_up); todo items carry the next attempt number."""
    runs_root = Path(_abs(cfg["runs_root"]))
    tasks = load_tasks(cfg["tasks"], PROJECT)
    todo, done, gave_up = [], [], []
    for task in tasks:  # task-major order: the conditions of one task finish close together
        for cond in cfg["conditions"]:
            for seed in cfg.get("seeds", [0]):
                d = runs_root / cfg["model"]["name"] / cond / task["task_id"]
                attempts = sorted(d.glob(f"s{seed}_a*"), key=lambda p: int(p.name.split("_a")[-1]))
                statuses = [read_status(p) for p in attempts]
                item = {"task": task, "condition": cond, "seed": seed, "dir": d,
                        "attempt": (int(attempts[-1].name.split("_a")[-1]) + 1) if attempts else 1,
                        "failures": sum(s in ("error", "env_error") for s in statuses)}
                if "completed" in statuses:
                    done.append(item)
                elif item["failures"] >= int(cfg.get("max_attempts", 3)):
                    gave_up.append(item)
                else:
                    todo.append(item)
    return todo, done, gave_up


def env_spec_for(env_cfg: dict, task: dict) -> dict:
    """The batch config's env section for one task, with its paths made absolute."""
    spec = {**env_cfg, "env_dir": task["env_dir"], "task": task["task"]}
    for key in ("ga_root", "image", "template_root", "work_root"):
        if spec.get(key):
            spec[key] = _abs(spec[key])
    return spec


def episode_spec(cfg: dict, item: dict, route: int, harness: dict) -> dict:
    run_id = f"s{item['seed']}_a{item['attempt']}"
    task = item["task"]
    app = {k: _abs(v) for k, v in cfg["app"].items() if k.endswith(("_skill", "_oracle"))}
    env = env_spec_for(cfg["env"], task)
    return {"run_dir": str(item["dir"] / run_id), "run_id": run_id, "seed": item["seed"],
            "condition": item["condition"], "model": cfg["model"], "app": app, "task": task, "env": env,
            "budget": cfg["budget"], "agent": cfg.get("agent", {}), "route": route, "harness": harness,
            "batch": cfg["name"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    a = ap.parse_args(argv)
    cfg = load_config(a.config if a.config.is_absolute() else PROJECT / a.config)
    todo, done, gave_up = plan(cfg)
    print(f"[batch {cfg['name']}] {len(done)} done, {len(todo)} to run, {len(gave_up)} gave up", flush=True)
    if a.dry_run:
        for it in todo:
            print(f"  {it['task']['task_id']} {it['condition']} seed {it['seed']} attempt {it['attempt']}")
        return 0
    signal.signal(signal.SIGTERM, _on_sigterm)
    harness = harness_info()
    parallel = int(cfg.get("parallel", 1))
    running: dict[int, tuple[subprocess.Popen, dict]] = {}  # route slot -> (process, item)
    queue = list(todo)
    max_attempts = int(cfg.get("max_attempts", 3))
    while (queue or running) and not TERMINATED:
        for slot in range(parallel):
            if slot in running or not queue or TERMINATED:
                continue
            item = queue.pop(0)
            spec = episode_spec(cfg, item, slot, harness)
            run_dir = Path(spec["run_dir"])
            run_dir.mkdir(parents=True, exist_ok=True)
            spec_path = run_dir / "episode_spec.json"
            dump_json(spec_path, spec)
            log = open(run_dir / "episode.log", "ab")
            p = subprocess.Popen([sys.executable, "-m", "ves.run_episode", "--spec", str(spec_path)], cwd=PROJECT,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            log.close()
            running[slot] = (p, item)
            print(f"[batch] slot {slot}: {item['task']['task_id']} {item['condition']} {spec['run_id']} pid {p.pid}",
                  flush=True)
            time.sleep(float(cfg.get("stagger_s", 5)))  # stagger VM boots
        time.sleep(2)
        for slot, (p, item) in list(running.items()):
            rc = p.poll()
            if rc is None:
                continue
            del running[slot]
            run_dir = item["dir"] / f"s{item['seed']}_a{item['attempt']}"
            if not (run_dir / "result.json").exists() and rc != 143:  # crashed without a result: an error, not a kill
                dump_json(run_dir / "result.json", {"status": "error", "error": f"episode process exited {rc} "
                                                    "without result.json; see episode.log", "run_id": run_dir.name})
            status = read_status(run_dir)
            print(f"[batch] slot {slot} finished: {item['task']['task_id']} {item['condition']} exit {rc} {status}",
                  flush=True)
            if status == "completed":
                done.append(item)
            elif status == "interrupted" and not TERMINATED:
                queue.insert(0, {**item, "attempt": item["attempt"] + 1})
            elif status in ("error", "env_error"):
                failures = item["failures"] + 1
                if failures < max_attempts:
                    queue.append({**item, "attempt": item["attempt"] + 1, "failures": failures})
                else:
                    gave_up.append({**item, "failures": failures})
    if TERMINATED:
        print("[batch] SIGTERM: stopping the running episodes", flush=True)
        for p, _ in running.values():
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.time() + 20
        while time.time() < deadline and any(p.poll() is None for p, _ in running.values()):
            time.sleep(0.5)
        return 143
    print(f"[batch {cfg['name']}] finished: {len(done)} completed, {len(gave_up)} gave up", flush=True)
    return 0 if not gave_up else 6


if __name__ == "__main__":
    sys.exit(main())
