"""Anthropic Messages API adapter for text and vision."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from sn_image_base.utils.error_utils import U1HttpResponseParseError
from sn_image_base.utils.httpx_client import httpx_response_raise_for_status_code
from sn_image_base.vlm.utils import image_to_base64
from sn_image_base.vlm.vlm_adapter import VlmAdapter

from .llm_adapter import LlmAdapter

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 150.0
DEFAULT_MAX_TOKENS = 4096


class AnthropicMessagesAdapter(LlmAdapter, VlmAdapter):
    """Anthropic Messages API adapter for text-only and vision calls."""

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
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
        }

    @staticmethod
    def _build_vision_content(
        user_prompt: str,
        images: list[str | bytes],
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for image in images:
            mime, b64 = image_to_base64(image)
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": b64,
                    },
                }
            )
        return blocks

    def _build_payload(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str | None,
        *,
        images: list[str | bytes] | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "user", "content": system_prompt})

        user_content: str | list[dict[str, Any]]
        if images:
            user_content = self._build_vision_content(user_prompt, images)
        else:
            user_content = user_prompt
        messages.append({"role": "user", "content": user_content})

        return {
            "model": model or self._default_model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        content = data.get("content", [])
        if content:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")

        thinking = data.get("thinking")
        if thinking:
            return f"[Think] {thinking}"

        raise RuntimeError("Anthropic Messages response has no extractable content.")

    async def _post_payload(self, payload: dict[str, Any]) -> str:
        resp = await self._get_client().post(self._url, json=payload, headers=self._headers)
        httpx_response_raise_for_status_code(resp)
        try:
            data = resp.json()
        except ValueError as exc:
            raise U1HttpResponseParseError(
                detail=f"Failed to parse HTTP response. {resp.request.url}. Response content: {resp.content}",
                code=resp.status_code,
            ) from exc
        return self._parse_response(data)

    async def text_completion(
        self,
        user_prompt: str,
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        payload = self._build_payload(user_prompt, system_prompt, model)
        return await self._post_payload(payload)

    async def vision_completion(
        self,
        user_prompt: str,
        images: list[str | bytes],
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        payload = self._build_payload(
            user_prompt,
            system_prompt,
            model,
            images=images,
        )
        return await self._post_payload(payload)

    async def aclose(self) -> None:
        if self._external_client is None and self._client is not None:
            await self._client.aclose()
            self._client = None
