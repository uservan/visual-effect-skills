"""Writes one run directory in the layout required by docs/motivation-experiments.md:

    <run_dir>/config.json task.json trace.jsonl model_responses.jsonl result.json final_state.json
              screenshots/initial.png step_000_before.png step_000_after.png ... final.png
              effects/edit_000_before.png edit_000_after.png edit_000_diff.png ...
              final_state/   (files copied out of the environment after the episode)

trace.jsonl and model_responses.jsonl are appended and flushed event by event, so an interrupted run stays
inspectable.  Raw traces are never rewritten afterwards; annotations live in separate files.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .images import effect_images


def dump_json(path: Path, obj) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class RunRecorder:
    def __init__(self, run_dir: Path, diff_ignore: list | tuple = ()):
        self.dir = Path(run_dir)
        for sub in ("screenshots", "effects", "final_state"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.diff_ignore = [tuple(b) for b in diff_ignore]
        self._trace = open(self.dir / "trace.jsonl", "a", encoding="utf-8")
        self._responses = open(self.dir / "model_responses.jsonl", "a", encoding="utf-8")

    def rel(self, p: Path) -> str:
        return str(Path(p).relative_to(self.dir))

    def write_json(self, name: str, obj) -> None:
        dump_json(self.dir / name, obj)

    def save_screenshot(self, png: bytes, name: str) -> str:
        p = self.dir / "screenshots" / name
        p.write_bytes(png)
        return self.rel(p)

    def alias_screenshot(self, existing_rel: str, name: str) -> str:
        """The 'before' image of a step is the capture the model last saw; store it under the step's own name
        as a hard link (same bytes, no extra space)."""
        src, dst = self.dir / existing_rel, self.dir / "screenshots" / name
        if dst.exists():
            dst.unlink()
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
        return self.rel(dst)

    def effect(self, step: int, before_rel: str, after_rel: str) -> dict:
        info = effect_images(self.dir / before_rel, self.dir / after_rel, self.dir / "effects" / f"edit_{step:03d}",
                             ignore=self.diff_ignore)
        if "paths" in info:
            info["paths"] = {k: self.rel(v) for k, v in info["paths"].items()}
        return info

    def event(self, obj: dict) -> None:
        obj = {"t": round(time.time(), 3), **obj}
        self._trace.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        self._trace.flush()

    def model_response(self, obj: dict) -> None:
        obj = {"t": round(time.time(), 3), **obj}
        self._responses.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        self._responses.flush()

    def close(self) -> None:
        for f in (self._trace, self._responses):
            try:
                f.close()
            except Exception:
                pass
