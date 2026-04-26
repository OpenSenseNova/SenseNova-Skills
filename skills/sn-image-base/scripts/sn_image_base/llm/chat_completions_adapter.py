"""OpenAI-compatible chat/completions LLM adapter (async only, text-only).

Supports any backend that follows the standard ``POST /chat/completions``
request/response schema. Does NOT support image inputs.

Usage:

    ```python
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
    ```

    ```bash
    export SN_LM_API_KEY=sk-xxxxxx
    python -m sn_image_base.llm.chat_completions_adapter
    ```
"""

from __future__ import annotations

import json
import logging
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

from .llm_adapter import LlmAdapter

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 600.0
DEFAULT_MAX_COMPLETION_TOKENS = 8192


class ChatCompletionsLlmAdapter(LlmAdapter):
    """LLM adapter for any OpenAI-compatible ``/chat/completions`` endpoint.

    Features:

    * Text-only completion via :meth:`text_completion`.
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
        """Initialize the chat/completions LLM adapter.

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
        model: str,
        *,
        max_completion_tokens: int | None = DEFAULT_MAX_COMPLETION_TOKENS,
    ) -> dict[str, Any]:
        """Assemble the full JSON request payload for a text-only call.

        Args:
            user_prompt: User-facing text instruction.
            system_prompt: System instruction (may be empty).
            model: Resolved model name to use in the request payload.
            max_completion_tokens: Maximum number of tokens to generate. Defaults to None.

        Returns:
            dict[str, Any]: JSON-serialisable request body.
        """
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
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
            U1HttpNotFoundError: On 404 responses, with model context appended.
            U1HttpResponseParseError: If the HTTP response body is not valid JSON.
            U1HttpBaseError: On other HTTP errors.
            RuntimeError: If the response contains no ``choices``.
        """
        model = model or self._default_model
        payload = self._build_payload(user_prompt, system_prompt, model)
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
    import argparse
    import asyncio

    from sn_image_base.configs import global_configs

    parser = argparse.ArgumentParser(description="Async LLM adapter.")
    parser.add_argument("--prompt", default=None, help="Prompt to use for the LLM")
    parser.add_argument("--system-prompt", default=None, help="System prompt to use for the LLM")
    args = parser.parse_args()
    prompt = args.prompt
    system_prompt = args.system_prompt

    async def main(
        prompt: str | None = None,
        system_prompt: str | None = None,
    ):
        prompt = prompt or "Write a poem about the topic: 'Hello world'"
        base_url = global_configs.LLM_BASE_URL
        if not base_url:
            raise InvalidBaseUrlError(
                f"No base URL provided for LLM. {global_configs.get_env_var_help('LLM_BASE_URL')}"
            )
        if not is_valid_base_url(base_url):
            raise InvalidBaseUrlError(
                f"Invalid base URL for LLM: {base_url}. {global_configs.get_env_var_help('LLM_BASE_URL')}"
            )
        base_url = base_url.rstrip("/")
        endpoint = "/chat/completions"
        endpoint_url = f"{base_url}{endpoint}"
        api_key = global_configs.LLM_API_KEY
        if not api_key:
            raise MissingApiKeyError(
                f"No API key provided for LLM. {global_configs.get_env_var_help('LLM_API_KEY')}"
            )
        model = global_configs.LLM_MODEL

        adapter = ChatCompletionsLlmAdapter(
            endpoint_url=endpoint_url,
            api_key=api_key,
            model=model,
        )
        print(f"Using prompt: {prompt!r} on {endpoint_url!r}")
        result = await adapter.text_completion(
            user_prompt=prompt,
            system_prompt=system_prompt or "",
        )
        print(result)

    asyncio.run(main(prompt, system_prompt))
