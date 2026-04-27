"""OpenAI-compatible chat/completions adapter for text and vision."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from sn_image_base.configs import is_valid_base_url
from sn_image_base.exceptions import InvalidBaseUrlError, MissingApiKeyError
from sn_image_base.utils.error_utils import (
    U1HttpBadResponseError,
    U1HttpNotFoundError,
    U1HttpResponseParseError,
    error_type_to_error_class,
    finish_reason_to_error_class,
    sanitize_base64_in_data,
)
from sn_image_base.utils.httpx_client import httpx_response_raise_for_status_code
from sn_image_base.vlm.utils import image_to_data_url
from sn_image_base.vlm.vlm_adapter import VlmAdapter

from .llm_adapter import LlmAdapter

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 600.0
DEFAULT_MAX_COMPLETION_TOKENS = 8192


class OpenAIChatAdapter(LlmAdapter, VlmAdapter):
    """OpenAI-compatible ``/chat/completions`` adapter for text and vision."""

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
        self._url = endpoint_url
        self._api_key = api_key
        self._default_model = model
        self._timeout = timeout
        self._reasoning_effort = reasoning_effort or None
        self._external_client = async_client
        self._client: httpx.AsyncClient | None = async_client
        logger.info(
            "OpenAIChatAdapter: endpoint=%s model=%s reasoning_effort=%s",
            self._url,
            self._default_model,
            self._reasoning_effort,
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
        }

    @staticmethod
    def _build_vision_content(
        user_prompt: str,
        images: list[str | bytes],
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": image_to_data_url(img)}} for img in images
        )
        return content

    def _build_payload(
        self,
        user_prompt: str,
        system_prompt: str,
        model: str,
        *,
        images: list[str | bytes] | None = None,
        max_completion_tokens: int | None = DEFAULT_MAX_COMPLETION_TOKENS,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content: str | list[dict[str, Any]]
        if images:
            user_content = self._build_vision_content(user_prompt, images)
        else:
            user_content = user_prompt
        messages.append({"role": "user", "content": user_content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if max_completion_tokens:
            payload["max_completion_tokens"] = max_completion_tokens
        return payload

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> str:
        if "error" in data and (error := data["error"]):
            error_message = error.get("message")
            error_type = error.get("type")
            error_code = error.get("code")
            error_class, explanation = error_type_to_error_class(error_type)
            raise error_class(
                explanation,
                detail=f"chat/completions response has error. Error: {error_message}",
                code=error_code,
            )

        choices = data.get("choices") or []
        if not choices:
            sanitized_data = sanitize_base64_in_data(data)
            dumped = json.dumps(sanitized_data, ensure_ascii=False)
            raise U1HttpBadResponseError(
                detail=f"chat/completions response has no choices. Response: {dumped}",
            )

        contents: list[str] = []
        finish_reason: str | None = None
        for choice in choices:
            msg = choice.get("message", {})
            finish_reason = choice.get("finish_reason") or finish_reason
            content_val = msg.get("content")
            if isinstance(content_val, str):
                contents.append(content_val)
            elif isinstance(content_val, list):
                parts: list[str] = []
                for block in content_val:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            parts.append(text)
                contents.append("".join(parts))

        final_content = "".join(contents)
        if final_content:
            return final_content

        sanitized_data = sanitize_base64_in_data(data)
        dumped = json.dumps(sanitized_data, ensure_ascii=False)
        detail_msg = ""
        if finish_reason:
            detail_msg += f"\n^ Finish reason: {finish_reason}"
        detail_msg += f"\n^ Response: {dumped}"
        if finish_reason == "stop":
            raise U1HttpBadResponseError(
                "chat/completions response with empty content.",
                detail=detail_msg,
            )
        if finish_reason:
            error_class, explanation = finish_reason_to_error_class(finish_reason)
            raise error_class(explanation, detail=detail_msg)
        raise U1HttpBadResponseError(
            "chat/completions response has no content. No finish reason provided.",
            detail=detail_msg,
        )

    async def _post_payload(self, payload: dict[str, Any], model: str) -> str:
        resp = await self._get_client().post(self._url, json=payload, headers=self._headers)
        try:
            httpx_response_raise_for_status_code(resp)
            data = resp.json()
        except U1HttpNotFoundError as exc:
            raise U1HttpNotFoundError(
                detail=f"{exc.detail} model={model!r}",
                code=resp.status_code,
            ) from exc
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
        resolved_model = model or self._default_model
        payload = self._build_payload(user_prompt, system_prompt, resolved_model)
        return await self._post_payload(payload, resolved_model)

    async def vision_completion(
        self,
        user_prompt: str,
        images: list[str | bytes],
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        resolved_model = model or self._default_model
        payload = self._build_payload(
            user_prompt,
            system_prompt,
            resolved_model,
            images=images,
        )
        return await self._post_payload(payload, resolved_model)

    async def aclose(self) -> None:
        if self._external_client is None and self._client is not None:
            await self._client.aclose()
            self._client = None


if __name__ == "__main__":
    import argparse
    import asyncio

    from sn_image_base.configs import global_configs

    parser = argparse.ArgumentParser(description="Async OpenAI-compatible chat adapter.")
    parser.add_argument("--prompt", default=None, help="Prompt to use for the model")
    parser.add_argument("--system-prompt", default=None, help="System prompt to use")
    parser.add_argument("--image", default=os.environ.get("IMAGE_PATH"), help="Optional image path")
    args = parser.parse_args()

    async def main() -> None:
        prompt = args.prompt or "Write a poem about the topic: 'Hello world'"
        base_url = global_configs.SN_CHAT_BASE_URL
        if not base_url:
            raise InvalidBaseUrlError(
                f"No base URL provided for chat runtime. {global_configs.get_env_var_help('SN_CHAT_BASE_URL')}"
            )
        if not is_valid_base_url(base_url):
            raise InvalidBaseUrlError(
                f"Invalid base URL for chat runtime: {base_url}. {global_configs.get_env_var_help('SN_CHAT_BASE_URL')}"
            )
        endpoint_url = f"{base_url.rstrip('/')}/chat/completions"
        api_key = global_configs.SN_CHAT_API_KEY
        if not api_key:
            raise MissingApiKeyError(
                f"No API key provided for chat runtime. {global_configs.get_env_var_help('SN_CHAT_API_KEY')}"
            )
        model = global_configs.SN_TEXT_MODEL

        adapter = OpenAIChatAdapter(
            endpoint_url=endpoint_url,
            api_key=api_key,
            model=model,
        )
        try:
            if args.image:
                result = await adapter.vision_completion(
                    user_prompt=prompt,
                    images=[args.image],
                    system_prompt=args.system_prompt or "",
                )
            else:
                result = await adapter.text_completion(
                    user_prompt=prompt,
                    system_prompt=args.system_prompt or "",
                )
            print(result)
        finally:
            await adapter.aclose()

    asyncio.run(main())
