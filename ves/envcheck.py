"""Environment check without a model: reset one benchmark task, screenshot, one harmless action, verifier, close.

    python -m ves.envcheck --config motivation/configs/batches/smoke_holo4.yaml --task brightness_contrast \
        --out logs/envcheck/brightness_contrast

Writes initial.png, after_move.png, final_state/ and report.json (timings, software versions, verifier result).
The verifier is expected to fail (nothing was edited); the check is that every stage runs.
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

from .batch import PROJECT, _abs, env_spec_for, load_config
from .envs import make_env
from .tasks import cua_world_task


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--task", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args(argv)
    cfg = load_config(a.config if a.config.is_absolute() else PROJECT / a.config)
    out = (a.out if a.out.is_absolute() else PROJECT / a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    task = cua_world_task(Path(_abs(cfg["tasks"]["env_dir"])), a.task)
    spec = env_spec_for(cfg["env"], task)
    report = {"task": task["task_id"], "instruction": task["instruction"], "stages": {}}
    env = make_env(spec)
    t = time.time()
    try:
        report["meta"] = env.reset(0)
        report["stages"]["reset_s"] = round(time.time() - t, 1)
        (out / "initial.png").write_bytes(env.screenshot())
        w, h = env.native_size
        t = time.time()
        (out / "after_move.png").write_bytes(env.execute({"kind": "move", "x": w // 2, "y": h // 2}))
        report["stages"]["action_s"] = round(time.time() - t, 1)
        t = time.time()
        verdict = env.finalize(out / "final_state")
        report["stages"]["finalize_s"] = round(time.time() - t, 1)
        report["verdict"] = {k: v for k, v in verdict.items() if k != "raw"}
        report["ok"] = True
    except Exception as e:
        report["ok"] = False
        report["error"] = f"{type(e).__name__}: {e}"
        report["traceback"] = traceback.format_exc()[-6000:]
    finally:
        t = time.time()
        try:
            env.close()
        except Exception as e:
            report["close_error"] = f"{type(e).__name__}: {e}"
        report["stages"]["close_s"] = round(time.time() - t, 1)
        (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "traceback"}, indent=1, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
