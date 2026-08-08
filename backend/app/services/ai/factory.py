"""Provider selection.

``AI_PROVIDER=auto`` (the default) picks Grok when a key is present and the
offline mock otherwise, which is what makes the whole product runnable with no
external account. Adding a new backend means adding one branch here and one
class — nothing in the service layer changes.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.ai import AIStatusOut
from app.services.ai.grok import GrokProvider
from app.services.ai.mock import MockProvider
from app.services.ai.provider import AIProvider

logger = get_logger(__name__)


def get_provider() -> AIProvider:
    """Return the configured provider instance."""
    choice = settings.ai_provider

    if choice == "mock":
        return MockProvider()

    if choice == "grok":
        provider = GrokProvider()
        if not provider.configured:
            # Fail loudly in the logs but still return Grok: the operator
            # explicitly asked for it, and the service layer will degrade to a
            # labelled fallback rather than 500.
            logger.warning("grok_selected_without_key")
        return provider

    # auto
    if settings.grok_api_key:
        return GrokProvider()
    logger.info("ai_provider_mock_selected", extra={"reason": "no GROK_API_KEY configured"})
    return MockProvider()


def provider_status() -> AIStatusOut:
    """Describes the active provider for the UI's AI status badge."""
    provider = get_provider()
    is_mock = provider.is_mock

    if is_mock:
        message = (
            "Running InsightIQ's built-in offline analyst. Narrative is generated from "
            "your computed metrics using templates, not a language model. Set GROK_API_KEY "
            "to enable AI-written narrative."
        )
    else:
        message = f"Connected to {provider.name} using model {provider.model}."

    return AIStatusOut(
        provider=provider.name,
        model=provider.model,
        configured=not is_mock,
        is_mock=is_mock,
        message=message,
    )


__all__ = ["get_provider", "provider_status"]
