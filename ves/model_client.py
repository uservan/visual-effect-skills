"""OpenAI-compatible chat client for locally served models (vLLM), with retries and token accounting.

The reasoning text of thinking models is never stored (protocol: no private chain-of-thought is recorded); only
its length is kept for cost accounting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import openai


class ContextOverflow(RuntimeError):
    """The request no longer fits the model's context window."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, as returned


@dataclass
class ModelReply:
    content: str
    tool_calls: list[ToolCall]
    finish_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    reasoning_chars: int
    latency_s: float
    attempts: int
    request_id: str | None = None
    extra: dict = field(default_factory=dict)


class ModelClient:
    def __init__(self, base_urls: list[str], model: str, sampling: dict | None = None, extra_body: dict | None = None,
                 timeout_s: float = 900.0, max_retries: int = 6):
        self.model = model
        self.sampling = dict(sampling or {})
        self.extra_body = dict(extra_body or {})
        self.max_retries = max_retries
        self.clients = [openai.OpenAI(base_url=u, api_key="EMPTY", timeout=timeout_s, max_retries=0) for u in base_urls]

    def chat(self, messages: list[dict], tools: list[dict], route: int = 0) -> ModelReply:
        client = self.clients[route % len(self.clients)]
        delay, last_error = 5.0, None
        for attempt in range(1, self.max_retries + 1):
            t0 = time.time()
            try:
                resp = client.chat.completions.create(
                    model=self.model, messages=messages, tools=tools, tool_choice="auto",
                    extra_body=self.extra_body or None, **self.sampling)
            except openai.BadRequestError as e:
                msg = str(e)
                if "context length" in msg or "maximum context" in msg or "too long" in msg:
                    raise ContextOverflow(msg) from e
                raise
            except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError,
                    openai.RateLimitError) as e:
                last_error = e
                time.sleep(delay)
                delay = min(delay * 2, 120.0)
                continue
            choice = resp.choices[0]
            msg = choice.message
            calls = [ToolCall(id=tc.id or f"call_{attempt}_{i}", name=tc.function.name, arguments=tc.function.arguments or "")
                     for i, tc in enumerate(msg.tool_calls or [])]
            reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
            usage = resp.usage
            return ModelReply(
                content=msg.content or "", tool_calls=calls, finish_reason=choice.finish_reason,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                reasoning_chars=len(reasoning), latency_s=round(time.time() - t0, 3), attempts=attempt,
                request_id=getattr(resp, "id", None))
        raise RuntimeError(f"model server unreachable after {self.max_retries} attempts: {last_error}")
