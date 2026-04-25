"""OpenAI-compatible chat/completions LLM adapter (async only, text-only).

Supports any backend that follows the standard ``POST /chat/completions``
request/response schema. Does NOT support image inputs.

Usage:
    from llm.chat_completions_adapter import ChatCompletionsLlmAdapter

    adapter = ChatCompletionsLlmAdapter(
        endpoint_url="https://api.openai.com/v1/chat/completions",
        api_key="sk-xxx",
        model="gpt-4o",
    )
    result = await adapter.text_completion(
        user_prompt="Optimize this text: Hello world",
        system_prompt="You are a text optimization assistant.",
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

DEFAULT_REQUEST_TIMEOUT = 1500.0


class ChatCompletionsLlmAdapter(LlmAdapter):
    """LLM adapter for any OpenAI-compatible ``/chat/completions`` endpoint.

    Features:

    * Text-only completion via :meth:`text_completion`.
    * Optional ``reasoning_effort`` request field (Cloudsway extension).
    * Shared or internally-created :class:`httpx.AsyncClient` for connection
      pooling.
    * Model name can be overridden per-call or at initialization.

    This adapter is intentionally generic. No预设 base_url, model, or system prompt.
    All required parameters must be provided by the caller.
    """

    def __init__(
        self,
        endpoint_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        async_client: httpx.AsyncClient | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        """Initialize the chat/completions LLM adapter.

        Args:
            endpoint_url: Full ``/chat/completions`` endpoint URL
                (e.g. ``https://api.openai.com/v1/chat/completions``).
            api_key: Bearer token for the ``Authorization`` header.
            model: Default model name sent in the request payload.
            timeout: Request timeout in seconds. Defaults to 1500.
            async_client (httpx.AsyncClient | None, optional):
                Shared HTTP client supplied by the caller. When
                provided the adapter reuses it and will *not* close it in
                :meth:`aclose`. Defaults to None.
            reasoning_effort (str | None, optional):
                Optional ``reasoning_effort`` field appended
                to the JSON body (e.g. ``'high'``). Pass ``None`` or ``''``
                to omit the field. Defaults to None.
        """
        self._url = endpoint_url
        self._api_key = api_key
        self._default_model = model
        self._timeout = timeout
        self._reasoning_effort = reasoning_effort or None
        self._external_client = async_client
        self._client: httpx.AsyncClient | None = async_client
        logger.info(
            "ChatCompletionsLlmAdapter: endpoint=%s model=%s reasoning_effort=%s",
            self._url,
            self._default_model,
            self._reasoning_effort,
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
        """Assemble the full JSON request payload for a text-only call.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System instruction (may be empty).
            model: Model name to use (overrides default if provided).

        Returns:
            dict[str, Any]: JSON-serialisable request body.
        """
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": messages,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        """Extract the assistant message text from a chat/completions response.

        Handles both plain-string and list-of-content-blocks message formats.

        Args:
            data: Parsed JSON response body.

        Returns:
            str: Concatenated assistant text.

        Raises:
            RuntimeError: If the response contains no ``choices``.
        """
        choice = (data.get("choices") or [None])[0]
        if not choice:
            raise RuntimeError("chat/completions response has no choices.")
        msg = choice.get("message", {})
        content_val = msg.get("content")
        if isinstance(content_val, str):
            return content_val
        if isinstance(content_val, list):
            parts: list[str] = []
            for block in content_val:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return str(content_val or "")

    async def text_completion(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        """Call the ``/chat/completions`` endpoint with text-only content.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System-level instruction. Defaults to ''.
            model: Model name to use. Defaults to the model set at init.

        Returns:
            str: Assistant message text extracted from the API response.

        Raises:
            httpx.HTTPStatusError: On non-2xx HTTP responses.
            RuntimeError: If the response contains no ``choices``.
        """
        payload = self._build_payload(user_prompt, system_prompt, model)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
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
