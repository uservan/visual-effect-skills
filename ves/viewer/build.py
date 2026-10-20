"""Build the static trajectory viewer from recorded runs (never re-runs a model):

    python -m ves.viewer.build [--runs motivation/runs] [--out motivation/viewer]
                               [--annotations motivation/analysis/failure_annotations.csv]

Writes <out>/index.html, app.js, style.css, data/index.js and data/runs/<key>.js.  Images are referenced by
relative paths into the run directories (nothing is embedded), so the viewer opens straight from disk
(file://) as long as <out> and <runs> keep their relative position.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
CONFIG_KEYS = ("batch", "seed", "run_id", "max_steps", "budget", "agent", "harness", "host", "pbs_job", "started_at",
               "knowledge")


def read_jsonl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"type": "unreadable_line"})
    return out


def load_annotations(path: Path | None) -> dict:
    """failure_annotations.csv: model,condition,task_id,run_id,first_error_step,failure_tags,evidence_paths,notes,annotator
    (failure_tags separated by ';')."""
    out = {}
    if path and path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out[(row.get("model", ""), row.get("condition", ""), row.get("task_id", ""), row.get("run_id", ""))] = row
    return out


def _js(var: str, key: str | None, obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")
    if key is None:
        return f"window.{var} = {payload};\n"
    return f"window.{var} = window.{var} || {{}};\nwindow.{var}[{json.dumps(key)}] = {payload};\n"


def build(runs_root: Path, out_dir: Path, annotations: Path | None) -> int:
    (out_dir / "data" / "runs").mkdir(parents=True, exist_ok=True)
    for f in STATIC.iterdir():
        shutil.copy2(f, out_dir / f.name)
    ann = load_annotations(annotations)
    index = []
    for i, rj in enumerate(sorted(runs_root.glob("*/*/*/*/result.json"))):
        run_dir = rj.parent
        model, cond, task_id, run_id = run_dir.parts[-4:]
        try:
            res = json.loads(rj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            res = {"status": "unreadable"}
        cfg_path = run_dir / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        task = cfg.get("task", {})
        a = ann.get((model, cond, task_id, run_id), {})
        key = f"r{i:05d}"
        rel = os.path.relpath(run_dir, out_dir).replace(os.sep, "/")
        first_error = a.get("first_error_step")
        index.append({
            "key": key, "model": model, "condition": cond, "task_id": task_id, "run_id": run_id, "path": rel,
            "status": res.get("status"), "success": res.get("success"), "score": res.get("score"),
            "stop_reason": res.get("stop_reason"), "actions": res.get("actions"), "max_steps": res.get("max_steps"),
            "model_turns": res.get("model_turns"), "skill_calls": res.get("skill_calls"),
            "invalid_actions": res.get("invalid_actions"), "tokens": res.get("tokens"),
            "runtime_s": (res.get("runtime") or {}).get("total_s"),
            "feedback": (res.get("verifier") or {}).get("feedback"), "instruction": task.get("instruction"),
            "first_error_step": int(first_error) if str(first_error or "").strip().isdigit() else None,
            "failure_tags": [t for t in (a.get("failure_tags") or "").split(";") if t.strip()],
            "finished_at": res.get("finished_at"),
        })
        run = {"key": key, "path": rel, "result": res, "annotation": a,
               "config": {k: cfg.get(k) for k in CONFIG_KEYS if k in cfg},
               "model": {k: (cfg.get("model") or {}).get(k) for k in ("name", "checkpoint", "sampling", "extra_body",
                                                                       "coord", "model_screen")},
               "task": {k: task.get(k) for k in ("task_id", "benchmark", "instruction", "max_steps", "verifier")},
               "trace": read_jsonl(run_dir / "trace.jsonl"),
               "responses": read_jsonl(run_dir / "model_responses.jsonl")}
        (out_dir / "data" / "runs" / f"{key}.js").write_text(_js("VES_RUNS", key, run), encoding="utf-8")
    (out_dir / "data" / "index.js").write_text(_js("VES_INDEX", None, index), encoding="utf-8")
    return len(index)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=Path, default=PROJECT / "motivation" / "runs")
    ap.add_argument("--out", type=Path, default=PROJECT / "motivation" / "viewer")
    ap.add_argument("--annotations", type=Path, default=PROJECT / "motivation" / "analysis" / "failure_annotations.csv")
    a = ap.parse_args(argv)
    n = build(a.runs.resolve(), a.out.resolve(), a.annotations)
    print(f"viewer: {n} run(s) -> {a.out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
