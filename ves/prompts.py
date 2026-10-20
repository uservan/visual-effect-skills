"""Prompt text.  Adapted from VisualSkill's scripts/run-cua-world/run_task.py (SYSTEM_PROMPT and the skill nudge)
for a tool-calling open-weight model: the tools are function calls instead of MCP tools, and the end of an
episode is a reply without a tool call.  Everything except the knowledge blocks is identical across conditions.
"""
from __future__ import annotations

SYSTEM_PROMPT = """\
You are utilising an Ubuntu virtual machine to complete a task autonomously.
You see the screen as screenshots of {width}x{height} pixels.

You MUST interact with applications through their GUI only. \
Do NOT open a terminal, run shell commands, edit config files, or use any programmatic workaround.

You have the following tools to interact with the desktop:
- screenshot(): take a screenshot to see the current desktop state
- click(x, y, button): click at a screen position ("left"/"right"/"middle")
- double_click(x, y): double-click at a position
- move_to(x, y): move the mouse without clicking
- drag_to(start_x, start_y, end_x, end_y): click and drag
- scroll(x, y, clicks): scroll up (positive) or down (negative)
- type_text(text): type text
- key_press(key): press a single key (e.g. "Return", "Tab", "Escape")
- hotkey(keys): press a shortcut (e.g. ["ctrl", "c"], ["alt", "F4"])
{coord_desc}

Every action tool automatically returns a screenshot after execution.

After each action, carefully evaluate the returned screenshot to confirm you \
achieved the right outcome before moving on. If not correct, try again.

When you believe the task is complete, simply stop: reply without calling any tool.\
"""

SKILL_TOOLS_DESC = """
You also have two tools for the installed software skill:
- list_topics(): list every topic path of the skill
- load_topic(topic): load one topic guide\
"""

# VisualSkill's nudge, with "plugin / registered skills list" replaced by the inline skill index
SKILL_NUDGE = (
    "\n\nBefore acting, you have a domain skill installed (its index is given with the task). "
    "Find the topic guide(s) most relevant to this task in the index and load them with load_topic "
    "BEFORE issuing any GUI actions. The skill contains screenshots and step-by-step UI walkthroughs "
    "that will save you from guessing menu paths."
)

SKILL_BLOCK_HEADER = "Installed software skill: {name}\n\n"

ORACLE_BLOCK_HEADER = "Reference notes about the software (general, not specific to this task):\n\n"

TASK_LINE = "Task: {instruction}"
FIRST_SCREENSHOT = "Current screenshot:"
AFTER_ACTION = "Screenshot after your last action:"
OMITTED_SCREENSHOT = "[an earlier screenshot was here; omitted to save context]"
BUDGET_EXHAUSTED = "Step budget exhausted; the action was not executed and the episode is over."
TOPIC_LOADED = "Topic '{topic}' loaded; its content follows in the next message."
MALFORMED_TOOL_CALL = ("Your last reply looked like a tool call but could not be parsed. "
                       "Call a tool using the function-calling format, or reply without a tool call if the task is complete.")


def system_prompt(width: int, height: int, coord_desc: str, with_skill: bool) -> str:
    text = SYSTEM_PROMPT.format(width=width, height=height, coord_desc=coord_desc)
    if with_skill:
        text = text.replace("Every action tool automatically", SKILL_TOOLS_DESC.strip("\n") + "\n\nEvery action tool automatically", 1)
        text += SKILL_NUDGE
    return text
