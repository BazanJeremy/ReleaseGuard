"""LLM client layer for System 2 narration (ADR-001 System 1/System 2 split).

Same pattern as FlakySense ADR-004: the gate never depends on this module
being functional. System 2 narrates CONDITIONAL GO verdicts only, and any
failure degrades to the deterministic System 1 rationale. Activation is
gated on ``ANTHROPIC_API_KEY`` plus the optional ``llm`` dependency group
(``pip install -e .[llm]``).
"""

from __future__ import annotations

import os
from typing import Protocol

DEFAULT_MODEL = "claude-opus-4-8"


class LLMClient(Protocol):
    """Minimal completion surface the System 2 narrator depends on."""

    def complete(self, system: str, user: str) -> str:
        """Return the model's text response for a system + user prompt pair."""
        ...


class AnthropicClient:
    """Reference ``LLMClient`` backed by the Anthropic Messages API."""

    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 16000) -> None:
        import anthropic  # deferred import: optional dependency

        self._client = anthropic.Anthropic()
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("LLM declined the request (stop_reason=refusal)")
        text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        if not text:
            raise RuntimeError("LLM returned an empty text response")
        return text


def client_from_env() -> LLMClient | None:
    """Build the default client when the environment enables System 2.

    Returns ``None`` when ``ANTHROPIC_API_KEY`` is unset or the ``anthropic``
    SDK is not installed — the gate then runs purely on System 1.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return AnthropicClient()
    except ImportError:
        return None
