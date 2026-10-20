"""GUI tools offered to the model and their translation into backend actions.

The tool set mirrors VisualSkill's cua-world-controller (screenshot, click, double_click, move_to, drag_to, scroll,
type_text, key_press, hotkey), so that every knowledge condition is compared under one action space.  The model
gives positions in its own coordinate space; they are converted to native screen pixels here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

GUI_TOOLS = ("click", "double_click", "move_to", "drag_to", "scroll", "type_text", "key_press", "hotkey")
OBSERVE_TOOLS = ("screenshot",)
SKILL_TOOLS = ("list_topics", "load_topic")


class ActionError(ValueError):
    """A tool call that cannot be executed; the message is returned to the model."""


@dataclass(frozen=True)
class CoordSpace:
    """How the model expresses screen positions.

    norm1000: integers in [0, 1000] relative to the screenshot (the Qwen3-VL / Qwen3.5 / Holo4 convention).
    pixels:   pixel positions in the downscaled screenshot the model sees (the VisualSkill / Claude convention).
    """

    kind: str
    model_w: int
    model_h: int
    native_w: int
    native_h: int

    def to_native(self, x, y) -> tuple[int, int]:
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            raise ActionError(f"coordinates must be numbers, got x={x!r}, y={y!r}")
        if self.kind == "norm1000":
            limit_x = limit_y = 1000.0
        elif self.kind == "pixels":
            limit_x, limit_y = float(self.model_w), float(self.model_h)
        else:
            raise ValueError(f"unknown coordinate space {self.kind!r}")
        if not (0 <= x <= limit_x and 0 <= y <= limit_y):
            raise ActionError(f"coordinates ({x:g}, {y:g}) are outside the screen (0..{limit_x:g}, 0..{limit_y:g})")
        nx = min(int(round(x / limit_x * self.native_w)), self.native_w - 1)
        ny = min(int(round(y / limit_y * self.native_h)), self.native_h - 1)
        return nx, ny

    def describe(self) -> str:
        if self.kind == "norm1000":
            return ("Positions are integers from 0 to 1000 relative to the screenshot: x=0 is the left edge and "
                    "x=1000 the right edge, y=0 the top edge and y=1000 the bottom edge.")
        return f"Positions are pixels in the {self.model_w}x{self.model_h} screenshot; (0, 0) is the top-left corner."


def _xy(prefix: str = "") -> dict:
    return {
        f"{prefix}x": {"type": "integer", "description": f"{prefix or ''}X position (horizontal)."},
        f"{prefix}y": {"type": "integer", "description": f"{prefix or ''}Y position (vertical)."},
    }


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required}}}


def tool_schemas(coord: CoordSpace, with_skill: bool) -> list[dict]:
    """OpenAI-style function definitions.  Every action returns a fresh screenshot."""
    c = " " + coord.describe()
    tools = [
        _fn("screenshot", "Take a screenshot of the desktop.", {}, []),
        _fn("click", "Click the mouse at (x, y)." + c,
            {**_xy(), "button": {"type": "string", "enum": ["left", "right", "middle"],
                                 "description": "Mouse button, default left."}}, ["x", "y"]),
        _fn("double_click", "Double-click at (x, y)." + c, _xy(), ["x", "y"]),
        _fn("move_to", "Move the mouse cursor to (x, y) without clicking." + c, _xy(), ["x", "y"]),
        _fn("drag_to", "Press the left button at (start_x, start_y), drag to (end_x, end_y) and release." + c,
            {**_xy("start_"), **_xy("end_")}, ["start_x", "start_y", "end_x", "end_y"]),
        _fn("scroll", "Scroll the mouse wheel at (x, y)." + c,
            {**_xy(), "clicks": {"type": "integer", "description": "Scroll clicks: positive = up, negative = down."}},
            ["x", "y", "clicks"]),
        _fn("type_text", "Type text with the keyboard.", {"text": {"type": "string"}}, ["text"]),
        _fn("key_press", "Press a single key, e.g. 'Return', 'Tab', 'Escape', 'BackSpace', 'Delete', 'Up', "
            "'Down', 'Left', 'Right', 'Home', 'End', 'Page_Up', 'Page_Down', 'F1'-'F12', 'space'.",
            {"key": {"type": "string"}}, ["key"]),
        _fn("hotkey", "Press keys together, e.g. [\"ctrl\", \"c\"], [\"ctrl\", \"shift\", \"e\"], [\"alt\", \"F4\"].",
            {"keys": {"type": "array", "items": {"type": "string"}}}, ["keys"]),
    ]
    if with_skill:
        tools += [
            _fn("list_topics", "List every topic path of the installed software skill.", {}, []),
            _fn("load_topic", "Load one topic guide of the installed software skill (its text and, if the skill has "
                "them, its figures). Use the topic path from the skill index, e.g. 'layers/layer-modes'.",
                {"topic": {"type": "string"}}, ["topic"]),
        ]
    return tools


def parse_arguments(raw) -> dict:
    """Tool-call arguments arrive as a JSON string (OpenAI format); tolerate a dict or an empty string."""
    if isinstance(raw, dict):
        return raw
    if raw is None or str(raw).strip() == "":
        return {}
    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ActionError(f"arguments are not valid JSON ({e.msg}): {str(raw)[:200]}")
    if not isinstance(args, dict):
        raise ActionError(f"arguments must be a JSON object, got {type(args).__name__}")
    return args


def _need(args: dict, *names: str):
    missing = [n for n in names if n not in args]
    if missing:
        raise ActionError(f"missing argument(s): {', '.join(missing)}")
    return [args[n] for n in names]


def _keys(value) -> list[str]:
    """Accept ["ctrl", "s"], '["ctrl", "s"]', "ctrl+s" or "Return"."""
    if isinstance(value, str):
        s = value.strip()
        parsed = None
        if s.startswith("["):
            try:
                parsed = json.loads(s)
            except json.JSONDecodeError:
                parsed = None
        if isinstance(parsed, list):
            value = parsed
        elif s == "+":
            value = ["plus"]
        else:
            value = s.split("+") if "+" in s else [s]
    if not isinstance(value, list) or not value or not all(isinstance(k, str) and k.strip() for k in value):
        raise ActionError(f"keys must be a non-empty list of key names, got {value!r}")
    return [k.strip() for k in value]


def to_backend_action(name: str, args: dict, coord: CoordSpace) -> dict:
    """Translate one GUI tool call into the backend-neutral action dict used by ves.envs."""
    if name == "click":
        x, y = coord.to_native(*_need(args, "x", "y"))
        button = args.get("button") or "left"
        if button not in ("left", "right", "middle"):
            raise ActionError(f"button must be left, right or middle, got {button!r}")
        return {"kind": "click", "x": x, "y": y, "button": button}
    if name == "double_click":
        x, y = coord.to_native(*_need(args, "x", "y"))
        return {"kind": "double_click", "x": x, "y": y}
    if name == "move_to":
        x, y = coord.to_native(*_need(args, "x", "y"))
        return {"kind": "move", "x": x, "y": y}
    if name == "drag_to":
        sx, sy = coord.to_native(*_need(args, "start_x", "start_y"))
        ex, ey = coord.to_native(*_need(args, "end_x", "end_y"))
        return {"kind": "drag", "x1": sx, "y1": sy, "x2": ex, "y2": ey}
    if name == "scroll":
        x, y = coord.to_native(*_need(args, "x", "y"))
        (clicks,) = _need(args, "clicks")
        try:
            clicks = int(float(clicks))
        except (TypeError, ValueError):
            raise ActionError(f"clicks must be an integer, got {clicks!r}")
        if clicks == 0:
            raise ActionError("clicks must not be 0")
        return {"kind": "scroll", "x": x, "y": y, "clicks": clicks}
    if name == "type_text":
        (text,) = _need(args, "text")
        if not isinstance(text, str) or text == "":
            raise ActionError("text must be a non-empty string")
        return {"kind": "type", "text": text}
    if name == "key_press":
        (key,) = _need(args, "key")
        return {"kind": "key", "keys": _keys(key)}  # "ctrl+s" becomes a combination, as in VisualSkill's bridge
    if name == "hotkey":
        (keys,) = _need(args, "keys")
        return {"kind": "key", "keys": _keys(keys)}
    raise ActionError(f"unknown tool {name!r}")


def describe_action(action: dict) -> str:
    """One-line human-readable form for traces and the viewer."""
    k = action["kind"]
    if k == "click":
        return f"{action['button']} click at ({action['x']}, {action['y']})"
    if k == "double_click":
        return f"double click at ({action['x']}, {action['y']})"
    if k == "move":
        return f"move to ({action['x']}, {action['y']})"
    if k == "drag":
        return f"drag ({action['x1']}, {action['y1']}) -> ({action['x2']}, {action['y2']})"
    if k == "scroll":
        return f"scroll {'up' if action['clicks'] > 0 else 'down'} {abs(action['clicks'])} at ({action['x']}, {action['y']})"
    if k == "type":
        return f"type {action['text']!r}"
    if k == "key":
        return "press " + "+".join(action["keys"])
    return json.dumps(action)
