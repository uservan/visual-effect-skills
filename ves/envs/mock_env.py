"""A desktop that draws the actions it receives; used to test the agent loop, recorder and viewer offline."""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .base import DesktopEnv


class MockDesktop(DesktopEnv):
    def __init__(self, spec: dict):
        self.spec = spec
        w, h = spec.get("native_size", (1920, 1080))
        self.native_size = (int(w), int(h))
        self._img = None
        self.actions: list[dict] = []

    def _png(self) -> bytes:
        buf = io.BytesIO()
        self._img.save(buf, format="PNG")
        return buf.getvalue()

    def reset(self, seed: int) -> dict:
        self._img = Image.new("RGB", self.native_size, (230, 230, 230))
        d = ImageDraw.Draw(self._img)
        d.rectangle([0, 0, self.native_size[0], 34], fill=(40, 40, 40))
        d.rectangle([600, 300, 1300, 800], fill=(90, 140, 200))
        return {"backend": "mock", "software": {"mock": "1"}, "seed": seed}

    def screenshot(self) -> bytes:
        return self._png()

    def execute(self, action: dict) -> bytes:
        self.actions.append(action)
        d = ImageDraw.Draw(self._img)
        if "x" in action:
            x, y = action["x"], action["y"]
            d.ellipse([x - 40, y - 40, x + 40, y + 40], fill=(220, 30, 30))
        if action["kind"] == "drag":
            d.line([action["x1"], action["y1"], action["x2"], action["y2"]], fill=(30, 160, 30), width=6)
        if action["kind"] in ("type", "key"):
            d.text((40, 60 + 18 * len(self.actions)), json.dumps(action), fill=(0, 0, 0))
        return self._png()

    def finalize(self, outputs_dir: Path) -> dict:
        Path(outputs_dir).mkdir(parents=True, exist_ok=True)
        (Path(outputs_dir) / "final.png").write_bytes(self._png())
        passed = len(self.actions) >= int(self.spec.get("pass_after_actions", 1))
        return {"passed": passed, "score": 1.0 if passed else 0.0,
                "feedback": f"mock verifier: {len(self.actions)} action(s)", "verifier": "mock", "raw": {}}

    def close(self) -> None:
        self._img = None
