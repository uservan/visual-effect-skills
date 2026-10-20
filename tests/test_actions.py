import pytest

from ves.actions import ActionError, CoordSpace, describe_action, parse_arguments, to_backend_action, tool_schemas

NORM = CoordSpace("norm1000", 1280, 720, 1920, 1080)
PIX = CoordSpace("pixels", 1280, 720, 1920, 1080)


def test_norm1000_corners_and_center():
    assert NORM.to_native(0, 0) == (0, 0)
    assert NORM.to_native(500, 500) == (960, 540)
    assert NORM.to_native(1000, 1000) == (1919, 1079)


def test_pixels_matches_visualskill_scaling():
    # VisualSkill: int(x * 1920 / 1280), int(y * 1080 / 720)
    for x, y in [(0, 0), (640, 360), (100, 700), (1279, 719)]:
        assert PIX.to_native(x, y) == (min(round(x * 1.5), 1919), min(round(y * 1.5), 1079))


def test_out_of_range_is_an_error():
    with pytest.raises(ActionError):
        NORM.to_native(1001, 5)
    with pytest.raises(ActionError):
        PIX.to_native(-1, 5)
    with pytest.raises(ActionError):
        NORM.to_native("left", 5)


def test_string_numbers_are_accepted():
    assert NORM.to_native("250", "750") == (480, 810)


def test_tool_translation():
    assert to_backend_action("click", {"x": 500, "y": 500}, NORM) == {"kind": "click", "x": 960, "y": 540, "button": "left"}
    assert to_backend_action("click", {"x": 500, "y": 500, "button": "right"}, NORM)["button"] == "right"
    assert to_backend_action("drag_to", {"start_x": 0, "start_y": 0, "end_x": 1000, "end_y": 500}, NORM) == \
        {"kind": "drag", "x1": 0, "y1": 0, "x2": 1919, "y2": 540}
    assert to_backend_action("scroll", {"x": 10, "y": 10, "clicks": "-3"}, NORM)["clicks"] == -3
    assert to_backend_action("type_text", {"text": "hello"}, NORM) == {"kind": "type", "text": "hello"}
    assert to_backend_action("hotkey", {"keys": ["ctrl", "shift", "e"]}, NORM)["keys"] == ["ctrl", "shift", "e"]
    assert to_backend_action("hotkey", {"keys": '["ctrl", "s"]'}, NORM)["keys"] == ["ctrl", "s"]
    assert to_backend_action("hotkey", {"keys": "ctrl+s"}, NORM)["keys"] == ["ctrl", "s"]
    assert to_backend_action("key_press", {"key": "Return"}, NORM)["keys"] == ["Return"]
    assert to_backend_action("key_press", {"key": "ctrl+z"}, NORM)["keys"] == ["ctrl", "z"]
    assert to_backend_action("key_press", {"key": "+"}, NORM)["keys"] == ["plus"]
    assert to_backend_action("key_press", {"key": "5"}, NORM)["keys"] == ["5"]


@pytest.mark.parametrize("name,args", [
    ("click", {"x": 5}), ("click", {"x": 5, "y": 5, "button": "side"}), ("scroll", {"x": 1, "y": 1, "clicks": 0}),
    ("type_text", {"text": ""}), ("hotkey", {"keys": []}), ("teleport", {}),
])
def test_invalid_calls(name, args):
    with pytest.raises(ActionError):
        to_backend_action(name, args, NORM)


def test_parse_arguments():
    assert parse_arguments('{"x": 1}') == {"x": 1}
    assert parse_arguments("") == {}
    assert parse_arguments({"a": 1}) == {"a": 1}
    with pytest.raises(ActionError):
        parse_arguments("{not json")
    with pytest.raises(ActionError):
        parse_arguments("[1, 2]")


def test_schemas_and_descriptions():
    names = [t["function"]["name"] for t in tool_schemas(NORM, with_skill=False)]
    assert names == ["screenshot", "click", "double_click", "move_to", "drag_to", "scroll", "type_text", "key_press", "hotkey"]
    names = [t["function"]["name"] for t in tool_schemas(NORM, with_skill=True)]
    assert names[-2:] == ["list_topics", "load_topic"]
    assert describe_action({"kind": "scroll", "x": 1, "y": 2, "clicks": -2}) == "scroll down 2 at (1, 2)"
