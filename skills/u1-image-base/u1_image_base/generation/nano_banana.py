from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from typing_extensions import override

from u1_image_base.configs import global_configs, is_valid_base_url
from u1_image_base.utils.error_utils import U1HttpErrorBase

from .core import ensure_output_path
from .core.client_base import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    T2IBaseClient,
)

DEFAULT_MODEL_SIZE: Literal["1K", "2K", "4K"] = "2K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
OUTPUT_DIR = Path("/tmp/openclaw-u1-image")


class NanoBananaText2ImageClient(T2IBaseClient):
    """Async client for U1 text-to-image-no-enhance API."""

    # requires `{model}` placeholder for format string
    DEFAULT_API_PATH = "/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        model: str | None = None,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
        ssl_verify: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the NanoBananaText2ImageClient.

        Args:
            api_key (str):
                API key for authentication.
            base_url (str | None, optional):
                API base URL. If None, reads from U1_IMAGE_GEN_BASE_URL env var.
            model (str | None, optional):
                Model name. If None, reads from U1_IMAGE_GEN_MODEL env var.
            max_connections (int, optional):
                Maximum number of connections. Defaults to 100.
            timeout (float, optional):
                Total timeout in seconds for HTTP requests.
                Defaults to DEFAULT_HTTP_REQUEST_TIMEOUT.
            ssl_verify (bool, optional):
                If True, enable TLS verification. Defaults to True.
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_connections=max_connections,
            timeout=timeout,
            ssl_verify=ssl_verify,
            **kwargs,
        )

    @override
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        model: str | None = None,
        image_size: Literal["1K", "2K", "4K"] = DEFAULT_MODEL_SIZE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        output_path: Path | None = None,
        **kwargs: Any,
    ) -> dict:
        """Generate an image from text prompt.

        Args:
            prompt (str):
                Text prompt for image generation.
            negative_prompt (str, optional):
                Negative prompt. Defaults to "".
            model (str | None, optional):
                Model name override. Defaults to None.
            image_size (str, optional):
                Image size preset ("1K", "2K", "4K"). Defaults to DEFAULT_MODEL_SIZE.
            aspect_ratio (str, optional):
                Aspect ratio (e.g. "16:9", "1:1"). Defaults to DEFAULT_ASPECT_RATIO.
            output_path (Path | None, optional):
                Output path for the generated image. Defaults to None.
            **kwargs:
                Additional arguments (ignored, for compatibility with U1Text2ImageClient).

        Returns:
            dict:
                Dictionary with keys: status, output (path), message.
        """
        model = model or self.model
        # Normalize image_size to uppercase for NanoBanana API
        image_size = image_size.upper()  # type: ignore[assignment]
        payload = self.build_payload(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
        )
        headers = self.headers
        api_url = self.get_api_url(model)

        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"t2i_{timestamp}.png"
        output_path = ensure_output_path(output_path)

        client = await self._get_client()

        try:
            create_response = await client.post(
                api_url,
                json=payload,
                headers=headers,
            )
            data = self.parse_response(create_response)
        except U1HttpErrorBase as exc:
            details = exc.detail or ""
            field_name = None
            if exc.code == 404:
                field_name = "U1_IMAGE_GEN_BASE_URL"
            elif exc.code == 401:
                field_name = "U1_API_KEY"
            if field_name is not None:
                field_hint = global_configs.get_annotated_field(field_name)
                if field_hint is not None:
                    env_names = list(field_hint.env_names) if field_hint.env_names else []
                    if env_names:
                        if len(env_names) == 1:
                            details += (
                                f"\nIs the environment variable `{env_names[0]}` set correctly?"
                            )
                        else:
                            env_names_str = ", ".join([f"`{n}`" for n in env_names])
                            details += f"\nIs any of the following environment variable(s) set correctly: {env_names_str}?"
            return {
                "status": "failed",
                "error": f"HTTP {exc.code}: {exc.message}",
                "message": details,
            }
        try:
            images = data["images"]
            if not images:
                return {
                    "status": "failed",
                    "error": "No image generated from the model",
                }
            image, mime_type = images[-1]
            image_bytes = base64.b64decode(image)
            suffix = mime_type_to_suffix(mime_type)
            saved_path = output_path.with_suffix(suffix)
            saved_path.write_bytes(image_bytes)
            return {
                "status": "ok",
                "output": str(saved_path),
                "message": "Image generated successfully",
            }
        except httpx.HTTPStatusError as exc:
            return {
                "status": "failed",
                "error": f"HTTP {exc.response.status_code}",
                "message": f"http error: {exc.response.status_code} {exc.response.text}",
            }
        except (httpx.HTTPError, OSError, ValueError) as exc:
            return {
                "status": "failed",
                "error": type(exc).__name__,
                "message": f"request error: {exc}",
            }

    @property
    @override
    def api_key(self) -> str:
        api_key = self._api_key or global_configs.U1_API_KEY
        if not api_key:
            raise ValueError(
                "API key is missing: {}".format(global_configs.get_env_var_help("U1_API_KEY"))
            )
        return api_key

    @property
    @override
    def base_url(self) -> str:
        base_url = self._base_url or global_configs.U1_IMAGE_GEN_BASE_URL
        if not base_url:
            raise ValueError(
                "Base URL is missing: {}".format(
                    global_configs.get_env_var_help("U1_IMAGE_GEN_BASE_URL")
                )
            )
        if not is_valid_base_url(base_url):
            raise ValueError(
                f"Base URL is not a valid base URL: {base_url}. "
                f"Try setting environment variable(s): {global_configs.get_env_var_help('U1_IMAGE_GEN_BASE_URL')}"
            )
        return base_url

    @override
    def get_api_url(self, model: str | None = None) -> str:
        model = model or self.model
        path = self.DEFAULT_API_PATH.format(model=model).lstrip("/")
        api_url = f"{self.base_url.rstrip('/')}/{path}"
        return api_url

    @override
    def build_payload(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        image_size: Literal["1K", "2K", "4K"] = DEFAULT_MODEL_SIZE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        max_output_tokens: int = 8192,
        **kwargs: Any,
    ) -> dict:
        parts: list[dict] = [{"text": prompt}]
        if (image_b64 := kwargs.get("image_b64")) and (
            image_mime_type := kwargs.get("image_mime_type")
        ):
            if image_mime_type not in ["image/jpeg", "image/png"]:
                msg = (
                    f"Unsupported image MIME type: {image_mime_type}. "
                    "Supported types: image/jpeg, image/png"
                )
                raise ValueError(msg)
            parts.append({"inline_data": {"mime_type": image_mime_type, "data": image_b64}})
        return {
            "contents": [{"role": "USER", "parts": parts}],
            "generationConfig": {
                "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": image_size},
                "maxOutputTokens": max_output_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            ],
        }

    @property
    @override
    def headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    @override
    def parse_response(self, response: httpx.Response) -> dict:
        raw_data = super().parse_response(response)

        images: list[tuple[str, str]] = []
        finish_reasons: list[str] = []
        candidates: list[dict] = raw_data.get("candidates") or []
        for c in candidates:
            content: dict[str, Any] = c.get("content") or {}
            parts: list[dict[str, Any]] = content.get("parts") or []
            if f_reason := content.get("finishReason"):
                finish_reasons.append(f_reason)
            for p in parts:
                inline_data: dict[str, Any] = p.get("inlineData", {})
                if inline_data:
                    mime_type: str = inline_data.get("mimeType")  # pyright: ignore[reportAssignmentType]
                    data: str = inline_data.get("data")  # pyright: ignore[reportAssignmentType]
                    images.append((data, mime_type))
        return {
            "images": images,
            "finish_reasons": finish_reasons,
        }


def mime_type_to_suffix(mime_type: str) -> str:
    """Convert MIME type to file suffix.

    Args:
        mime_type: MIME type.

    Returns:
        str: File suffix.
    """
    if mime_type == "image/jpeg":
        return ".jpg"
    elif mime_type == "image/png":
        return ".png"
    elif mime_type == "image/webp":
        return ".webp"
    else:
        return ".png"
