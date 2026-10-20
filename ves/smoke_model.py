"""Model / harness compatibility check (protocol: verify the action interface before spending compute).

    python -m ves.smoke_model --base-url http://127.0.0.1:8000/v1 --model holo4 --out logs/smoke_holo4.json

On synthetic 1280x720 screens with one labelled button at a known place, the model is asked to click the button
through the harness tools.  The check reports whether the tool calls parse, and whether the returned coordinates
fit the 0-1000 convention or the pixel convention, then runs one follow-up turn (tool result + new screenshot).
"""
from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .actions import CoordSpace, parse_arguments, tool_schemas
from .images import data_url
from .model_client import ModelClient
from .prompts import system_prompt

TARGETS = [("OK", 0.80, 0.85), ("Cancel", 0.15, 0.20), ("Apply", 0.50, 0.55), ("Export", 0.30, 0.75)]


def screen(label: str, fx: float, fy: float, size=(1280, 720)) -> bytes:
    im = Image.new("RGB", size, (236, 236, 236))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, size[0], 28], fill=(50, 50, 50))
    for i, other in enumerate(["File", "Edit", "Image", "Layer", "Colors", "Filters"]):
        d.text((12 + 70 * i, 8), other, fill=(240, 240, 240))
    cx, cy = int(fx * size[0]), int(fy * size[1])
    d.rectangle([cx - 60, cy - 22, cx + 60, cy + 22], fill=(40, 110, 220), outline=(20, 50, 120), width=2)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:
        font = ImageFont.load_default()
    d.text((cx - 30, cy - 12), label, fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--thinking", action="store_true", help="leave the chat template's thinking mode on")
    a = ap.parse_args(argv)
    coord = CoordSpace("norm1000", 1280, 720, 1920, 1080)
    extra = {} if a.thinking else {"chat_template_kwargs": {"enable_thinking": False}}
    client = ModelClient([a.base_url], a.model, {"temperature": 0.0, "max_tokens": 1024}, extra, max_retries=2)
    tools = tool_schemas(coord, with_skill=False)
    sysmsg = system_prompt(1280, 720, coord.describe(), with_skill=False)
    report = {"model": a.model, "trials": [], "time": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for label, fx, fy in TARGETS:
        png = screen(label, fx, fy)
        msgs = [{"role": "system", "content": sysmsg},
                {"role": "user", "content": [{"type": "text", "text": f"Task: Click the '{label}' button."},
                                             {"type": "text", "text": "Current screenshot:"},
                                             {"type": "image_url", "image_url": {"url": data_url(png)}}]}]
        trial = {"label": label, "target_norm1000": [round(fx * 1000), round(fy * 1000)],
                 "target_pixels": [round(fx * 1280), round(fy * 720)]}
        try:
            r = client.chat(msgs, tools)
            trial.update({"content": r.content[:500], "tool_calls": [(c.name, c.arguments) for c in r.tool_calls],
                          "latency_s": r.latency_s, "prompt_tokens": r.prompt_tokens, "reasoning_chars": r.reasoning_chars})
            clicks = [parse_arguments(c.arguments) for c in r.tool_calls if c.name in ("click", "double_click")]
            if clicks:
                x, y = float(clicks[0]["x"]), float(clicks[0]["y"])
                trial["xy"] = [x, y]
                # distance of the answer from the target, under each convention, as a fraction of the screen
                trial["err_if_norm1000"] = round(((x / 1000 - fx) ** 2 + (y / 1000 - fy) ** 2) ** 0.5, 4)
                trial["err_if_pixels"] = round(((x / 1280 - fx) ** 2 + (y / 720 - fy) ** 2) ** 0.5, 4)
                # follow-up turn: tool result + new screenshot, as in the agent loop
                msgs.append({"role": "assistant", "content": r.content or "", "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in r.tool_calls]})
                for c in r.tool_calls:
                    msgs.append({"role": "tool", "tool_call_id": c.id, "content": "Action executed."})
                msgs.append({"role": "user", "content": [{"type": "text", "text": "Screenshot after your last action:"},
                                                         {"type": "image_url", "image_url": {"url": data_url(screen("Done", 0.5, 0.5))}}]})
                r2 = client.chat(msgs, tools)
                trial["followup"] = {"content": r2.content[:300], "tool_calls": [(c.name, c.arguments) for c in r2.tool_calls]}
        except Exception as e:
            trial["error"] = f"{type(e).__name__}: {e}"
        report["trials"].append(trial)
        print(json.dumps(trial, ensure_ascii=False), flush=True)
    ok = [t for t in report["trials"] if "xy" in t]
    report["parsed_tool_calls"] = f"{len(ok)}/{len(TARGETS)}"
    if ok:
        report["mean_err_if_norm1000"] = round(sum(t["err_if_norm1000"] for t in ok) / len(ok), 4)
        report["mean_err_if_pixels"] = round(sum(t["err_if_pixels"] for t in ok) / len(ok), 4)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "trials"}), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
