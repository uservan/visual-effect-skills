"""The agent loop: one model, one task, one knowledge condition, fully recorded.

Message layout (identical across conditions except the knowledge blocks):
  system: prompts.system_prompt (+ skill tools and VisualSkill's nudge when a skill is installed)
  user:   [skill index] [oracle notes] "Task: ..." "Current screenshot:" <image>
  then per model turn: assistant (tool calls) -> one tool message per call -> user message with any loaded skill
  topic content -> user message with the screenshot after the last action.
Only GUI actions count toward the step budget; screenshot / list_topics / load_topic do not (as in VisualSkill,
where the step budget is the environment's).  Only the newest `keep_screenshots` screenshots stay in the context
as images; skill figures and oracle figures stay.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from . import prompts
from .actions import (GUI_TOOLS, OBSERVE_TOOLS, SKILL_TOOLS, ActionError, CoordSpace, describe_action, parse_arguments,
                      to_backend_action, tool_schemas)
from .envs.base import DesktopEnv, EnvError
from .images import data_url, downscale_png, file_data_url
from .knowledge import Knowledge
from .model_client import ContextOverflow, ModelClient
from .recorder import RunRecorder


@dataclass
class Budget:
    max_steps: int                 # GUI actions
    max_turns: int                 # model calls
    timeout_s: float               # wall clock of the agent phase
    max_consecutive_errors: int = 5


@dataclass
class AgentConfig:
    coord: CoordSpace
    keep_screenshots: int = 6


def _looks_like_tool_call(text: str) -> bool:
    t = text or ""
    return any(m in t for m in ("<tool_call>", "<function=", '"name": "click"', "</tool_call>"))


class Agent:
    def __init__(self, env: DesktopEnv, client: ModelClient, knowledge: Knowledge, rec: RunRecorder,
                 cfg: AgentConfig, budget: Budget, route: int = 0, stop_event: threading.Event | None = None):
        self.env, self.client, self.k, self.rec, self.cfg, self.budget = env, client, knowledge, rec, cfg, budget
        self.route = route
        self.stop_event = stop_event or threading.Event()
        self.messages: list[dict] = []
        self._shot_parts: list[tuple[int, int]] = []  # (message index, part index) of screenshot images
        self.stats = {"model_turns": 0, "gui_steps": 0, "observations": 0, "skill_calls": 0, "invalid_actions": 0,
                      "prompt_tokens": 0, "completion_tokens": 0, "max_prompt_tokens": 0, "reasoning_chars": 0,
                      "screenshots_sent": 0, "knowledge_images_sent": 0, "model_latency_s": 0.0}

    # ---- message helpers -------------------------------------------------------------------------------
    def _model_png(self, native_png: bytes) -> bytes:
        return downscale_png(native_png, (self.cfg.coord.model_w, self.cfg.coord.model_h))

    def _add_user(self, parts: list[dict]) -> None:
        self.messages.append({"role": "user", "content": parts})

    def _screenshot_parts(self, label: str, native_png: bytes) -> list[dict]:
        self.stats["screenshots_sent"] += 1
        return [{"type": "text", "text": label},
                {"type": "image_url", "image_url": {"url": data_url(self._model_png(native_png))}}]

    def _push_screenshot_message(self, label: str, native_png: bytes) -> None:
        self._add_user(self._screenshot_parts(label, native_png))
        self._shot_parts.append((len(self.messages) - 1, 1))
        self._prune_screenshots()

    def _prune_screenshots(self) -> None:
        keep = max(1, self.cfg.keep_screenshots)
        while len(self._shot_parts) > keep:
            mi, pi = self._shot_parts.pop(0)
            self.messages[mi]["content"][pi] = {"type": "text", "text": prompts.OMITTED_SCREENSHOT}

    def _knowledge_parts(self, parts: list[dict]) -> list[dict]:
        out = []
        for p in parts:
            if p["type"] == "text":
                out.append({"type": "text", "text": p["text"]})
            else:
                out.append({"type": "image_url", "image_url": {"url": file_data_url(p["path"])}})
                self.stats["knowledge_images_sent"] += 1
        return out

    # ---- episode ---------------------------------------------------------------------------------------
    def run(self, instruction: str) -> dict:
        coord = self.cfg.coord
        with_skill = self.k.skill is not None
        system = prompts.system_prompt(coord.model_w, coord.model_h, coord.describe(), with_skill)
        tools = tool_schemas(coord, with_skill)
        self.rec.write_json("prompt_context.json", {"system": system, "tools": tools})
        self.messages = [{"role": "system", "content": system}]

        first: list[dict] = []
        if with_skill:
            first.append({"type": "text", "text": prompts.SKILL_BLOCK_HEADER.format(name=self.k.skill.name)
                          + self.k.skill.index_text()})
        if self.k.oracle is not None:
            first.append({"type": "text", "text": prompts.ORACLE_BLOCK_HEADER})
            first += self._knowledge_parts(self.k.oracle.parts())
        first.append({"type": "text", "text": prompts.TASK_LINE.format(instruction=instruction)})
        current = self.env.screenshot()
        current_rel = self.rec.save_screenshot(current, "initial.png")
        first += self._screenshot_parts(prompts.FIRST_SCREENSHOT, current)
        self._add_user(first)
        self._shot_parts.append((1, len(first) - 1))
        self.rec.event({"type": "init", "instruction": instruction, "screenshot": current_rel,
                        "first_message_text": [p["text"] for p in first if p["type"] == "text"]})

        t_start, consecutive_errors, stop_reason, n_obs = time.time(), 0, None, 0
        while stop_reason is None:
            if self.stop_event.is_set():
                stop_reason = "interrupted"
                break
            if self.stats["model_turns"] >= self.budget.max_turns:
                stop_reason = "max_turns"
                break
            if time.time() - t_start > self.budget.timeout_s:
                stop_reason = "timeout"
                break
            turn = self.stats["model_turns"]
            try:
                reply = self.client.chat(self.messages, tools, route=self.route)
            except ContextOverflow as e:
                self.rec.event({"type": "error", "turn": turn, "kind": "context_overflow", "detail": str(e)[:2000]})
                stop_reason = "context_overflow"
                break
            self.stats["model_turns"] += 1
            for key in ("prompt_tokens", "completion_tokens", "reasoning_chars"):
                self.stats[key] += getattr(reply, key)
            self.stats["max_prompt_tokens"] = max(self.stats["max_prompt_tokens"], reply.prompt_tokens)
            self.stats["model_latency_s"] = round(self.stats["model_latency_s"] + reply.latency_s, 3)
            self.rec.model_response({
                "turn": turn, "content": reply.content, "finish_reason": reply.finish_reason,
                "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in reply.tool_calls],
                "usage": {"prompt_tokens": reply.prompt_tokens, "completion_tokens": reply.completion_tokens},
                "reasoning_chars": reply.reasoning_chars, "latency_s": reply.latency_s, "attempts": reply.attempts,
                "request_id": reply.request_id})
            assistant = {"role": "assistant", "content": reply.content or ""}
            if reply.tool_calls:
                assistant["tool_calls"] = [{"id": c.id, "type": "function",
                                            "function": {"name": c.name, "arguments": c.arguments or "{}"}}
                                           for c in reply.tool_calls]
            self.messages.append(assistant)

            if not reply.tool_calls:
                if _looks_like_tool_call(reply.content):
                    consecutive_errors += 1
                    self.stats["invalid_actions"] += 1
                    self.rec.event({"type": "invalid_action", "turn": turn, "error": "unparsed tool call",
                                    "content": reply.content[:2000]})
                    self._add_user([{"type": "text", "text": prompts.MALFORMED_TOOL_CALL}])
                    if consecutive_errors >= self.budget.max_consecutive_errors:
                        stop_reason = "invalid_actions"
                    continue
                stop_reason = "agent_done"
                self.rec.event({"type": "agent_done", "turn": turn, "message": reply.content[:4000]})
                break

            pending_knowledge: list[list[dict]] = []
            new_screen = False
            for call in reply.tool_calls:
                result_text = None
                if stop_reason is not None:
                    result_text = prompts.BUDGET_EXHAUSTED
                elif call.name in GUI_TOOLS and self.stats["gui_steps"] >= self.budget.max_steps:
                    stop_reason = "max_steps"
                    result_text = prompts.BUDGET_EXHAUSTED
                else:
                    try:
                        args = parse_arguments(call.arguments)
                        if call.name in GUI_TOOLS:
                            action = to_backend_action(call.name, args, coord)
                            step = self.stats["gui_steps"]
                            before_rel = self.rec.alias_screenshot(current_rel, f"step_{step:03d}_before.png")
                            t0 = time.time()
                            after = self.env.execute(action)
                            t1 = time.time()
                            after_rel = self.rec.save_screenshot(after, f"step_{step:03d}_after.png")
                            effect = self.rec.effect(step, before_rel, after_rel)
                            self.rec.event({"type": "step", "step": step, "turn": turn, "tool_call_id": call.id,
                                            "tool": call.name, "arguments": args, "action": action,
                                            "action_text": describe_action(action), "t_start": round(t0, 3),
                                            "t_end": round(t1, 3), "before": before_rel, "after": after_rel,
                                            "effect": effect})
                            self.stats["gui_steps"] += 1
                            current, current_rel, new_screen = after, after_rel, True
                            result_text = "Action executed."
                        elif call.name in OBSERVE_TOOLS:
                            current = self.env.screenshot()
                            current_rel = self.rec.save_screenshot(current, f"observe_{n_obs:03d}.png")
                            self.rec.event({"type": "observe", "turn": turn, "tool_call_id": call.id,
                                            "screenshot": current_rel})
                            n_obs += 1
                            self.stats["observations"] += 1
                            new_screen = True
                            result_text = "Screenshot taken."
                        elif call.name in SKILL_TOOLS and self.k.skill is not None:
                            self.stats["skill_calls"] += 1
                            if call.name == "list_topics":
                                result_text = "\n".join(self.k.skill.topics())
                                self.rec.event({"type": "skill", "turn": turn, "tool": "list_topics"})
                            else:
                                topic = args.get("topic")
                                if not isinstance(topic, str) or not topic.strip():
                                    raise ActionError("load_topic needs a topic path string")
                                parts = self.k.skill.load_topic(topic)
                                n_img = sum(p["type"] == "image" for p in parts)
                                self.rec.event({"type": "skill", "turn": turn, "tool": "load_topic", "topic": topic,
                                                "ok": not parts[0].get("text", "").startswith("ERROR"),
                                                "images": n_img,
                                                "figures": [str(p["path"].name) for p in parts if p["type"] == "image"]})
                                if parts[0].get("text", "").startswith("ERROR"):
                                    result_text = parts[0]["text"]
                                else:
                                    pending_knowledge.append(self._knowledge_parts(parts))
                                    result_text = prompts.TOPIC_LOADED.format(topic=topic)
                        else:
                            raise ActionError(f"unknown tool {call.name!r}")
                        consecutive_errors = 0
                    except ActionError as e:
                        consecutive_errors += 1
                        self.stats["invalid_actions"] += 1
                        result_text = f"Error: {e}"
                        self.rec.event({"type": "invalid_action", "turn": turn, "tool_call_id": call.id,
                                        "tool": call.name, "arguments": call.arguments, "error": str(e)})
                    except EnvError as e:
                        self.rec.event({"type": "error", "turn": turn, "kind": "env", "detail": str(e)})
                        stop_reason = "env_error"
                        result_text = f"Error: environment failure ({e})"
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text})
            for parts in pending_knowledge:
                self._add_user(parts)
            if new_screen:
                self._push_screenshot_message(prompts.AFTER_ACTION, current)
            if stop_reason is None and self.stats["gui_steps"] >= self.budget.max_steps:
                stop_reason = "max_steps"
            if stop_reason is None and consecutive_errors >= self.budget.max_consecutive_errors:
                stop_reason = "invalid_actions"

        self.rec.event({"type": "stop", "reason": stop_reason, "stats": dict(self.stats)})
        return {"stop_reason": stop_reason, "agent_s": round(time.time() - t_start, 1), "last_screenshot": current_rel,
                **self.stats}
