"""Grok (xAI) provider.

Talks to the OpenAI-compatible chat-completions endpoint at ``api.x.ai``.
Requires ``GROK_API_KEY``; without it the factory selects ``MockProvider``
instead, so the application is fully usable before any account exists.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AIProviderError
from app.core.logging import get_logger
from app.schemas.ai import AIPayload
from app.services.ai.prompts import loader
from app.services.ai.provider import AIResponse

logger = get_logger(__name__)

#: Transient statuses worth one retry.
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 2

#: Models sometimes wrap JSON in a fence despite being told not to.
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class GrokProvider:
    """:class:`~app.services.ai.provider.AIProvider` implementation for xAI Grok."""

    name = "grok"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.grok_api_key
        self.base_url = (base_url or settings.grok_base_url).rstrip("/")
        self.model = model or settings.grok_model
        self.timeout = timeout if timeout is not None else settings.grok_timeout_seconds
        self._client = client
        self._owns_client = client is None

    @property
    def is_mock(self) -> bool:
        return False

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # -- transport ----------------------------------------------------------
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _chat(self, user_prompt: str, *, json_mode: bool) -> tuple[str, dict[str, Any]]:
        if not self.configured:
            raise AIProviderError(
                "GROK_API_KEY is not set. See SETUP_REQUIRED.md.",
                code="ai_provider_unconfigured",
            )

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": loader.system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            # Low but non-zero: narrative should read naturally while staying
            # anchored to the supplied figures.
            "temperature": 0.3,
            "max_tokens": settings.grok_max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await client.post("/chat/completions", json=body)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("grok_timeout", extra={"attempt": attempt})
                continue
            except httpx.HTTPError as exc:
                raise AIProviderError(f"Could not reach the AI provider: {exc}") from exc

            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                logger.warning(
                    "grok_retryable_status",
                    extra={"status": response.status_code, "attempt": attempt},
                )
                continue

            if response.status_code == 401:
                raise AIProviderError(
                    "The AI provider rejected the API key.", code="ai_provider_unauthorized"
                )
            if response.status_code == 429:
                raise AIProviderError(
                    "The AI provider rate limit was exceeded. Try again shortly.",
                    code="ai_provider_rate_limited",
                )
            if response.status_code >= 400:
                raise AIProviderError(
                    f"The AI provider returned HTTP {response.status_code}."
                )

            return self._extract(response)

        raise AIProviderError(
            f"The AI provider did not respond after {_MAX_ATTEMPTS} attempts."
        ) from last_error

    @staticmethod
    def _extract(response: httpx.Response) -> tuple[str, dict[str, Any]]:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("The AI provider returned an unreadable response.") from exc

        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("The AI provider returned empty content.")
        return content.strip(), data.get("usage") or {}

    # -- generation ---------------------------------------------------------
    async def _generate(
        self, prompt_name: str, payload: AIPayload, *, json_mode: bool = False
    ) -> AIResponse:
        started = time.perf_counter()
        content, usage = await self._chat(
            loader.render(prompt_name, payload), json_mode=json_mode
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        structured: dict[str, Any] | None = None
        if json_mode:
            structured = _parse_json(content)
            if structured is None:
                raise AIProviderError(
                    "The AI provider returned malformed JSON for a structured section."
                )

        return AIResponse(
            content=content,
            structured=structured,
            provider=self.name,
            model=self.model,
            prompt_version=loader.PROMPT_VERSION,
            is_fallback=False,
            tokens_prompt=usage.get("prompt_tokens"),
            tokens_completion=usage.get("completion_tokens"),
            latency_ms=latency_ms,
        )

    async def generate_summary(self, payload: AIPayload) -> AIResponse:
        return await self._generate(loader.EXECUTIVE_SUMMARY, payload)

    async def generate_root_cause(self, payload: AIPayload) -> AIResponse:
        return await self._generate(loader.ROOT_CAUSE, payload, json_mode=True)

    async def generate_recommendations(self, payload: AIPayload) -> AIResponse:
        return await self._generate(loader.RECOMMENDATIONS, payload, json_mode=True)

    async def generate_risks(self, payload: AIPayload) -> AIResponse:
        return await self._generate(loader.RISKS, payload)


def _parse_json(content: str) -> dict[str, Any] | None:
    """Parse a JSON section, tolerating a stray markdown fence."""
    text = content.strip()
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else {"items": parsed}


__all__ = ["GrokProvider"]
