"""Run one episode (model x condition x task x seed) in its own process:

    python -m ves.run_episode --spec <episode.json>

Writes config.json, task.json, trace.jsonl, model_responses.jsonl, screenshots/, effects/, final_state/,
final_state.json and result.json into spec["run_dir"].  result.json is written last; a run directory without it
was interrupted (the batch runner marks it so on its next start).  Exit code: 0 when the episode reached the
verifier, 3 on an environment failure, 4 on any other error, 143 on SIGTERM.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

from .actions import CoordSpace
from .agent import Agent, AgentConfig, Budget
from .envs import EnvError, make_env
from .knowledge import build_knowledge
from .model_client import ModelClient
from .recorder import RunRecorder, dump_json

EXIT_CODES = {"completed": 0, "env_error": 3, "error": 4, "interrupted": 143}


class Interrupted(BaseException):
    """Raised from the SIGTERM handler so that blocking calls unwind."""


def _on_sigterm(signum, frame):
    raise Interrupted()


def _close_with_timeout(env, seconds: float) -> str | None:
    err: list[str] = []

    def work():
        try:
            env.close()
        except Exception as e:  # the run is over either way; keep the reason
            err.append(f"{type(e).__name__}: {e}")
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(seconds)
    return "close timed out" if t.is_alive() else (err[0] if err else None)


def run(spec: dict) -> int:
    t0 = time.time()
    run_dir = Path(spec["run_dir"])
    rec = RunRecorder(run_dir)
    m, task, b = spec["model"], spec["task"], spec["budget"]
    max_steps = min(int(task.get("max_steps") or b["max_steps_cap"]), int(b["max_steps_cap"]))
    config = {**spec, "max_steps": max_steps, "host": socket.gethostname(), "pbs_job": os.environ.get("PBS_JOBID"),
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    rec.write_json("task.json", task)
    rec.write_json("config.json", config)
    status, stop_reason, verdict, agent_out, env_meta, error, env, close_err = "error", None, None, {}, {}, None, None, None
    stop = threading.Event()
    try:
        knowledge = build_knowledge(spec["condition"], spec["app"])
        config["knowledge"] = knowledge.provenance
        rec.write_json("config.json", config)
        env = make_env(spec["env"])
        rec.diff_ignore = list(env.diff_ignore_boxes())
        w, h = env.native_size
        coord = CoordSpace(m.get("coord", "norm1000"), *m.get("model_screen", (1280, 720)), w, h)
        client = ModelClient(m["base_urls"], m["served_name"], m.get("sampling"), m.get("extra_body"))
        budget = Budget(max_steps=max_steps, max_turns=int(b.get("max_turns_factor", 3) * max_steps + 20),
                        timeout_s=float(b.get("timeout_s", 3600)),
                        max_consecutive_errors=int(b.get("max_consecutive_errors", 5)))
        env_meta = env.reset(int(spec["seed"]))
        rec.event({"type": "env_ready", **env_meta})
        agent = Agent(env, client, knowledge, rec,
                      AgentConfig(coord, int(spec.get("agent", {}).get("keep_screenshots", 6))),
                      budget, route=int(spec.get("route", 0)), stop_event=stop)
        agent_out = agent.run(task["instruction"])
        stop_reason = agent_out["stop_reason"]
        rec.save_screenshot(env.screenshot(), "final.png")
        verdict = env.finalize(run_dir / "final_state")
        rec.event({"type": "verifier", **{k: v for k, v in verdict.items() if k != "raw"}})
        status = "env_error" if stop_reason == "env_error" else "completed"
    except Interrupted:
        stop.set()
        status, error = "interrupted", "SIGTERM (preemption or walltime)"
    except EnvError as e:
        status, error = "env_error", str(e)
        rec.event({"type": "error", "kind": "env", "detail": str(e)})
    except Exception as e:
        status, error = "error", f"{type(e).__name__}: {e}"
        rec.event({"type": "error", "kind": "harness", "detail": traceback.format_exc()[-4000:]})
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)  # let the result be written
        if env is not None:
            close_err = _close_with_timeout(env, 15 if status == "interrupted" else 180)
            ep = getattr(env, "episode_dir", None)
            if ep and Path(ep).exists():
                try:
                    shutil.move(str(ep), str(run_dir / "env_episode"))
                except Exception:
                    pass
        rec.close()

    if verdict is not None:
        dump_json(run_dir / "final_state.json", {
            "final_screenshot": "screenshots/final.png", "copied": verdict.get("copied"),
            "copy_errors": verdict.get("copy_errors"), "verifier_raw": verdict.get("raw")})
    s = agent_out
    result = {
        "task_id": task["task_id"], "benchmark": task.get("benchmark"), "model_id": m["name"],
        "checkpoint": m.get("checkpoint"), "condition": spec["condition"],
        "software_version": env_meta.get("software"), "seed": spec["seed"], "run_id": spec["run_id"],
        "status": status, "stop_reason": stop_reason, "error": error,
        "success": bool(verdict["passed"]) if verdict else None, "score": (verdict or {}).get("score"),
        "verifier": ({"program": verdict.get("verifier"), "passed": verdict.get("passed"),
                      "score": verdict.get("score"), "feedback": verdict.get("feedback")} if verdict else None),
        "failure_tags": [], "first_error_step": None,
        "actions": s.get("gui_steps", 0), "max_steps": max_steps, "model_turns": s.get("model_turns", 0),
        "observations": s.get("observations", 0), "skill_calls": s.get("skill_calls", 0),
        "invalid_actions": s.get("invalid_actions", 0),
        "tokens": {"prompt": s.get("prompt_tokens", 0), "completion": s.get("completion_tokens", 0),
                   "max_prompt": s.get("max_prompt_tokens", 0), "reasoning_chars": s.get("reasoning_chars", 0)},
        "context": {"screenshots_sent": s.get("screenshots_sent", 0),
                    "knowledge_images_sent": s.get("knowledge_images_sent", 0)},
        "runtime": {"total_s": round(time.time() - t0, 1), "reset_s": env_meta.get("reset_s"),
                    "agent_s": s.get("agent_s"), "model_latency_s": s.get("model_latency_s"),
                    "verify_s": (verdict or {}).get("verify_s")},
        "evidence_paths": {"trace": "trace.jsonl", "model_responses": "model_responses.jsonl",
                           "screenshots": "screenshots/", "effects": "effects/",
                           "final_screenshot": "screenshots/final.png", "final_state": "final_state/",
                           "env_episode": "env_episode/" if (run_dir / "env_episode").exists() else None},
        "close_error": close_err, "host": config["host"], "pbs_job": config["pbs_job"],
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    dump_json(run_dir / "result.json", result)
    return EXIT_CODES.get(status, 4)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, type=Path)
    a = ap.parse_args(argv)
    signal.signal(signal.SIGTERM, _on_sigterm)
    return run(json.loads(a.spec.read_text(encoding="utf-8")))


if __name__ == "__main__":
    sys.exit(main())
