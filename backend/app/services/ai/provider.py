"""The provider abstraction.

Swapping Grok for OpenAI, Gemini or a local model means writing one new class
that satisfies :class:`AIProvider` and setting a config value. No business
logic changes — services depend on this protocol, never on a concrete provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.schemas.ai import AIPayload


@dataclass(frozen=True)
class AIResponse:
    """A single narrative section returned by a provider."""

    content: str
    #: Parsed structured form when the prompt asked for JSON (recommendations,
    #: root causes). ``None`` for free-text sections.
    structured: dict[str, object] | None = None
    provider: str = "unknown"
    model: str = "unknown"
    prompt_version: str = "unknown"
    #: True when this is placeholder/degraded output rather than a live model.
    is_fallback: bool = False
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    latency_ms: int | None = None
    meta: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class AIProvider(Protocol):
    """Contract every AI backend must satisfy.

    Implementations receive an :class:`AIPayload` — aggregates only — and return
    narrative. They must never be handed raw rows, and must never be asked to
    compute a metric.
    """

    name: str
    model: str

    @property
    def is_mock(self) -> bool:
        """True when output is placeholder text rather than a live model."""
        ...

    async def generate_summary(self, payload: AIPayload) -> AIResponse:
        """Executive summary of the period."""
        ...

    async def generate_root_cause(self, payload: AIPayload) -> AIResponse:
        """Root-cause analysis of the largest metric movements."""
        ...

    async def generate_recommendations(self, payload: AIPayload) -> AIResponse:
        """Prioritised strategic recommendations."""
        ...

    async def generate_risks(self, payload: AIPayload) -> AIResponse:
        """Risks to watch over the coming periods."""
        ...

    async def aclose(self) -> None:
        """Release any transport resources."""
        ...


__all__ = ["AIProvider", "AIResponse"]
