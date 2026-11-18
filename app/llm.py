"""Model-agnostic LLM layer.

`LLMClient` is the only thing the pipeline knows about. LiteLLMClient talks to
any provider (Ollama, OpenAI, Anthropic, Azure, ...) through one interface, so
switching model is a config change, not a code change. Tests and CI use a fake
client, which keeps them free, fast and deterministic.
"""

import json
import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[dict]) -> LLMResult: ...


class LLMError(RuntimeError):
    """The model backend is unreachable or rejected the call (not a bad answer)."""


class LiteLLMClient:
    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    def complete(self, messages: list[dict]) -> LLMResult:
        try:
            import litellm  # imported lazily so tests don't need it

            response = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # connection refused, bad key, missing package, ...
            raise LLMError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        usage = getattr(response, "usage", None)
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:  # local models have no price
            cost = None
        return LLMResult(
            text=response.choices[0].message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            cost_usd=cost,
        )


def extract_json(text: str) -> dict:
    """Parse a JSON object out of model output (tolerates ```json fences and chatter)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)