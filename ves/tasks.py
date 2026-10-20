"""Task entries from benchmark task folders (CUA-World / gym-anything layout: <env_dir>/tasks/<id>/task.json)."""
from __future__ import annotations

import json
from pathlib import Path


def cua_world_task(env_dir: Path, task: str) -> dict:
    """The instruction is the task's own `description`, exactly what VisualSkill's runner gives Claude."""
    env_dir = Path(env_dir)
    tj = env_dir / "tasks" / task / "task.json"
    data = json.loads(tj.read_text(encoding="utf-8"))
    return {
        "task_id": f"cuaworld.{env_dir.name}.{task}",
        "benchmark": "cua_world",
        "env_dir": str(env_dir),
        "task": task,
        "instruction": data.get("description", ""),
        "max_steps": (data.get("init") or {}).get("max_steps"),
        "verifier": ((data.get("success") or {}).get("spec") or {}).get("program"),
        "task_json": data,
    }


def load_tasks(cfg: dict, project: Path) -> list[dict]:
    """cfg: {"benchmark": "cua_world", "env_dir": <relative to project>, "ids": [...]}."""
    if cfg.get("benchmark", "cua_world") != "cua_world":
        raise ValueError(f"unsupported benchmark {cfg.get('benchmark')!r}")
    env_dir = (project / cfg["env_dir"]).resolve()
    return [cua_world_task(env_dir, t) for t in cfg["ids"]]
