"""AI layer.

Boundary rule: ``build_ai_payload`` is the only route from analytics into this
package, and it emits aggregates only. Providers implement the ``AIProvider``
protocol; the concrete choice is a config value, never a code dependency.
"""

from app.services.ai.factory import get_provider, provider_status
from app.services.ai.grok import GrokProvider
from app.services.ai.mock import MockProvider
from app.services.ai.payload import build_ai_payload
from app.services.ai.provider import AIProvider, AIResponse
from app.services.ai.service import AIService

__all__ = [
    "AIProvider",
    "AIResponse",
    "AIService",
    "GrokProvider",
    "MockProvider",
    "build_ai_payload",
    "get_provider",
    "provider_status",
]
