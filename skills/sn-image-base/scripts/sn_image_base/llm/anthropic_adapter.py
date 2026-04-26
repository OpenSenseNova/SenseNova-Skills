"""Anthropic Messages API adapter for LLM (async only, text-only).

Supports Anthropic's /v1/messages endpoint. Does NOT support image inputs.

Usage:
    from llm.anthropic_adapter import AnthropicMessagesAdapter

    adapter = AnthropicMessagesAdapter(
        endpoint_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-xxx",
        model="claude-sonnet-4-6",
    )
    result = await adapter.text_completion(
        user_prompt="Optimize this text: Hello world",
        system_prompt="You are a helpful assistant.",
    )
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..utils.error_utils import U1HttpResponseParseError
from ..utils.httpx_client import httpx_response_raise_for_status_code
from .llm_adapter import LlmAdapter

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 150.0
DEFAULT_MAX_TOKENS = 4096


class AnthropicMessagesAdapter(LlmAdapter):
    """Anthropic Messages API adapter.

    Features:

    * Text-only completion via :meth:`text_completion`.
    * Shared or internally-created :class:`httpx.AsyncClient` for connection
      pooling.
    * Model name can be overridden per-call or at initialization.

    This adapter is intentionally generic. No preset base_url, model, or system prompt.
    All required parameters must be provided by the caller.
    """

    def __init__(
        self,
        endpoint_url: str,
        api_key: str,
        model: str,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the Anthropic Messages adapter.

        Args:
            endpoint_url: Full ``/v1/messages`` endpoint URL
                (e.g. ``https://api.anthropic.com/v1/messages``).
            api_key: Bearer token for the ``Authorization`` header.
            model: Default model name sent in the request payload.
            max_tokens: Maximum tokens to generate. Defaults to 4096.
            timeout: Request timeout in seconds. Defaults to 150.
            async_client (httpx.AsyncClient | None, optional):
                Shared HTTP client supplied by the caller. When
                provided the adapter reuses it and will *not* close it in
                :meth:`aclose`. Defaults to None.
        """
        self._url = endpoint_url
        self._api_key = api_key
        self._default_model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._external_client = async_client
        self._client: httpx.AsyncClient | None = async_client
        logger.info(
            "AnthropicMessagesAdapter: endpoint=%s model=%s max_tokens=%s",
            self._url,
            self._default_model,
            self._max_tokens,
        )

    def _get_client(self) -> httpx.AsyncClient:
        """Return the async HTTP client, creating it lazily if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def _build_payload(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str | None,
    ) -> dict[str, Any]:
        """Assemble the full JSON request payload for Anthropic Messages API.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System instruction (may be empty).
            model: Model name to use (overrides default if provided).

        Returns:
            dict[str, Any]: JSON-serialisable request body.
        """
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }
        return payload

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        """Extract the assistant message text from Anthropic Messages response.

        Handles responses with or without content blocks, and extracts text
        from content blocks when available.

        Args:
            data: Parsed JSON response body.

        Returns:
            str: Assistant text content.

        Raises:
            RuntimeError: If the response contains no extractable content.
        """
        # Try to extract from content blocks first
        content = data.get("content", [])
        if content:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")

        # Fallback: if there's a thinking field, return it as indicator
        thinking = data.get("thinking")
        if thinking:
            return f"[Think] {thinking}"

        # Last resort: return string representation of data
        raise RuntimeError("Anthropic Messages response has no extractable content.")

    async def text_completion(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        """Call the ``/v1/messages`` endpoint with text-only content.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System-level instruction. Defaults to ''.
            model: Model name to use. Defaults to the model set at init.

        Returns:
            str: Assistant message text extracted from the API response.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
            RuntimeError: If the response contains no content.
        """
        payload = self._build_payload(user_prompt, system_prompt, model)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
        }
        resp = await self._get_client().post(self._url, json=payload, headers=headers)
        httpx_response_raise_for_status_code(resp)
        try:
            data = resp.json()
        except ValueError as exc:
            raise U1HttpResponseParseError(
                detail=f"Failed to parse HTTP response. {resp.request.url}. Response content: {resp.content}",
                code=resp.status_code,
            ) from exc
        return self._parse_response(data)

    async def aclose(self) -> None:
        """Close the internal async HTTP client if we own it.

        Has no effect when the client was injected from outside.
        """
        if self._external_client is None and self._client is not None:
            await self._client.aclose()
            self._client = None
