"""OpenAI-compatible chat/completions VLM adapter (async only).

Supports any backend that follows the standard ``POST /chat/completions``
request/response schema with vision support (image_url content blocks).

Usage:

    ```python
    from vlm.chat_completions_adapter import ChatCompletionsVlmAdapter

    adapter = ChatCompletionsVlmAdapter(
        endpoint_url="https://api.openai.com/v1/chat/completions",
        api_key="sk-xxx",
        model="gpt-4o",
    )
    result = await adapter.vision_completion(
        user_prompt="Describe this image",
        images=["path/to/image.png"],
        system_prompt="You are a helpful assistant.",
    )
    ```

    ```bash
    export SN_LM_API_KEY=sk-xxxxxx
    export IMAGE_PATH=/path/to/image.png
    python -m sn_image_base.vlm.chat_completions_adapter
    ```
"""

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

from .utils import image_to_data_url
from .vlm_adapter import VlmAdapter

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 600.0
DEFAULT_MAX_COMPLETION_TOKENS = 8192


class ChatCompletionsVlmAdapter(VlmAdapter):
    """VLM adapter for any OpenAI-compatible ``/chat/completions`` endpoint.

    Features:

    * Multimodal ``image_url`` vision content (images encoded as data URLs).
    * Optional ``reasoning_effort`` request field (Cloudsway extension).
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
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        async_client: httpx.AsyncClient | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        """Initialize the chat/completions VLM adapter.

        Args:
            endpoint_url: Full ``/chat/completions`` endpoint URL
                (e.g. ``https://api.openai.com/v1/chat/completions``).
            api_key: Bearer token for the ``Authorization`` header.
            model: Default model name sent in the request payload.
            timeout: Request timeout in seconds. Defaults to 600.
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
            "ChatCompletionsVlmAdapter: endpoint=%s model=%s reasoning_effort=%s",
            self._url,
            self._default_model,
            self._reasoning_effort,
        )

    def _get_client(self) -> httpx.AsyncClient:
        """Return the async HTTP client, creating it lazily if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @staticmethod
    def _build_user_content(
        user_prompt: str,
        images: list[str | bytes],
    ) -> list[dict[str, Any]]:
        """Build the ``user`` turn content list with text + image_url blocks.

        Args:
            user_prompt: The text instruction.
            images: Images encoded as data URLs.

        Returns:
            list[dict[str, Any]]: OpenAI-style multimodal content blocks.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": image_to_data_url(img)}} for img in images
        )
        return content

    def _build_payload(
        self,
        user_prompt: str,
        images: list[str | bytes],
        system_prompt: str,
        model: str,
        *,
        max_completion_tokens: int | None = DEFAULT_MAX_COMPLETION_TOKENS,
    ) -> dict[str, Any]:
        """Assemble the full JSON request payload for a vision call.

        Args:
            user_prompt: User-facing text instruction.
            images: Images for the user turn.
            system_prompt: System instruction (may be empty).
            model: Resolved model name to use in the request payload.
            max_completion_tokens: Maximum number of tokens to generate. Defaults to None.

        Returns:
            dict[str, Any]: JSON-serialisable request body.
        """
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": self._build_user_content(user_prompt, images),
            },
        ]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
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
        """Extract the assistant message text from a chat/completions response.

        Handles both plain-string and list-of-content-blocks message formats.

        Example data structure:

        .. code-block:: json

        [
          {
            "index": 0,
            "message": {
              "role": "assistant",
              "reasoning": "Here's a thinking process ..."
            },
            "finish_reason": "length"
          },
          {
            "prompt_tokens": 21,
            "completion_tokens": 1024,
            "total_tokens": 1045,
            "prompt_tokens_details": {
              "cached_tokens": 0,
              "audio_tokens": 0
            }
          }
        ]

        Args:
            data: Parsed JSON response body.

        Returns:
            str: Concatenated assistant text.

        Raises:
            RuntimeError: If the response contains no ``choices``.
        """
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
        reasoning: list[str] = []
        contents: list[str] = []
        finish_reason: str | None = None
        for c in choices:
            msg = c.get("message", {})
            f_reason = c.get("finish_reason")
            reasoning_val = msg.get("reasoning")
            content_val = msg.get("content")
            if reasoning_val:
                reasoning.append(reasoning_val)
            if f_reason:
                finish_reason = f_reason
            if isinstance(content_val, str):
                contents.append(content_val)
            if isinstance(content_val, list):
                parts: list[str] = []
                for block in content_val:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            parts.append(text)
                contents.append("".join(parts))
        final_content = "".join(contents)
        if not final_content:
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
                raise error_class(
                    explanation,
                    detail=detail_msg,
                )
            raise U1HttpBadResponseError(
                "chat/completions response has no content. No finish reason provided.",
                detail=detail_msg,
            )
        return final_content

    async def vision_completion(
        self,
        user_prompt: str,
        images: list[str | bytes],
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        """Call the ``/chat/completions`` endpoint with vision content.

        Args:
            user_prompt: User-facing text instruction.
            images: Images to include in the user turn.
            system_prompt: System-level instruction. Defaults to ''.
            model: Model name to use. Defaults to the model set at init.

        Returns:
            str: Assistant message text extracted from the API response.

        Raises:
            U1HttpNotFoundError: On 404 responses, with model context appended.
            U1HttpResponseParseError: If the HTTP response body is not valid JSON.
            U1HttpBaseError: On other HTTP errors.
            RuntimeError: If the response contains no ``choices``.
        """
        model = model or self._default_model
        payload = self._build_payload(user_prompt, images, system_prompt, model)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._get_client().post(self._url, json=payload, headers=headers)
        try:
            httpx_response_raise_for_status_code(resp)
            data = resp.json()
        except U1HttpNotFoundError as e:
            # re-raise with more context
            raise U1HttpNotFoundError(
                detail=f"{e.detail} model={model!r}",
                code=resp.status_code,
            ) from e
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


if __name__ == "__main__":
    import asyncio

    from sn_image_base.configs import global_configs

    async def main():
        base_url = global_configs.VLM_BASE_URL
        if not base_url:
            raise InvalidBaseUrlError(
                f"No base URL provided for VLM. {global_configs.get_env_var_help('VLM_BASE_URL')}"
            )
        if not is_valid_base_url(base_url):
            raise InvalidBaseUrlError(
                f"Invalid base URL for VLM: {base_url}. {global_configs.get_env_var_help('VLM_BASE_URL')}"
            )
        base_url = base_url.rstrip("/")
        endpoint = "/chat/completions"
        endpoint_url = f"{base_url}{endpoint}"
        api_key = global_configs.VLM_API_KEY
        if not api_key:
            raise MissingApiKeyError(
                f"No API key provided for VLM. {global_configs.get_env_var_help('VLM_API_KEY')}"
            )
        model = global_configs.VLM_MODEL

        image_path = os.environ.get("IMAGE_PATH")
        if not image_path or not os.path.exists(image_path):
            raise ValueError(
                "Please set an valid `IMAGE_PATH` environment variable for running this script."
            )

        adapter = ChatCompletionsVlmAdapter(
            endpoint_url=endpoint_url,
            api_key=api_key,
            model=model,
        )
        result = await adapter.vision_completion(
            user_prompt="Describe this image",
            images=[image_path],
            system_prompt="You are a helpful assistant.",
        )
        print(result)

    asyncio.run(main())
