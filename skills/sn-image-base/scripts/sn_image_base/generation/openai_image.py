from __future__ import annotations

import base64
import math
import re
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from typing_extensions import override

from sn_image_base.configs import global_configs, is_valid_base_url
from sn_image_base.exceptions import BadConfigurationError
from sn_image_base.utils.error_utils import U1HttpErrorBase

from .core import ensure_output_path
from .core.client_base import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    T2IBaseClient,
)

DEFAULT_RESOLUTION: Literal["1K", "2K"] = "2K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
OUTPUT_DIR = Path("/tmp/openclaw-sn-image")

B64_PARSE_PATTERN = re.compile(r"^data:([a-zA-Z0-9/]+?);base64,([+-/_A-Za-z0-9]+=*)$")


class OpenAIImageGenerationClient(T2IBaseClient):
    """Async client for OpenAI Image Generation API."""

    DEFAULT_API_PATH = "/images/generations"

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
        """Initialize the OpenAIImageGenerationClient.

        Args:
            api_key (str):
                API key for authentication.
            base_url (str | None, optional):
                API base URL. If None, reads from SN_IMAGE_GEN_BASE_URL env var.
            model (str | None, optional):
                Model name. If None, reads from SN_IMAGE_GEN_MODEL env var.
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
        *,
        model: str | None = None,
        image_size: Literal["1K", "2K", "1k", "2k"] | None = None,
        aspect_ratio: str | None = DEFAULT_ASPECT_RATIO,
        output_path: Path | None = None,
        **kwargs: Any,
    ) -> dict:
        """Generate an image from text prompt.

        Args:
            prompt (str):
                Text prompt for image generation.
            model (str | None, optional):
                Model name override. Defaults to None.
            image_size (str, optional):
                Image size preset ("1K", "2K"). Defaults to DEFAULT_RESOLUTION.
            aspect_ratio (str, optional):
                Aspect ratio (e.g. "16:9", "1:1"). Defaults to DEFAULT_ASPECT_RATIO.
            output_path (Path | None, optional):
                Output path for the generated image. Defaults to None.
            **kwargs:
                Additional arguments reserved for backend compatibility.

        Returns:
            dict:
                Dictionary with keys: status, output (path), message.
        """
        model = model or self.model or global_configs.SN_IMAGE_GEN_MODEL
        if not model:
            raise BadConfigurationError(
                f"Model is not set. {global_configs.get_env_var_help('SN_IMAGE_GEN_MODEL')}"
            )
        image_size = image_size or DEFAULT_RESOLUTION
        if aspect_ratio is None:
            size = None
        else:
            rw, _, rh = aspect_ratio.partition(":")
            try:
                aspect_ratio_val: float = float(int(rw) / int(rh))
            except (ValueError, ZeroDivisionError) as e:
                raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from e
            size = self._resolve_size(
                resolution=image_size,
                aspect_ratio_val=aspect_ratio_val,
            )
        payload = self.build_payload(
            prompt=prompt,
            model=model,
            size=size,
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
                field_name = "SN_IMAGE_GEN_BASE_URL"
            elif exc.code == 401:
                field_name = "SN_IMAGE_GEN_API_KEY"
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
            image_bytes, mime_type = images[-1]
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
        api_key = self._api_key or global_configs.SN_IMAGE_GEN_API_KEY
        if not api_key:
            raise ValueError(
                "API key is missing: {}".format(
                    global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY")
                )
            )
        return api_key

    @property
    @override
    def base_url(self) -> str:
        base_url = self._base_url or global_configs.SN_IMAGE_GEN_BASE_URL
        if not base_url:
            raise ValueError(
                "Base URL is missing: {}".format(
                    global_configs.get_env_var_help("SN_IMAGE_GEN_BASE_URL")
                )
            )
        if not is_valid_base_url(base_url):
            raise ValueError(
                f"Base URL is not a valid base URL: {base_url}. "
                f"Try setting environment variable(s): {global_configs.get_env_var_help('SN_IMAGE_GEN_BASE_URL')}"
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
        model: str,
        *,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """
        Example:
        {
            "model": "dall-e-3",
            "prompt": "一只戴着墨镜的猫在赛博朋克城市的街道上喝咖啡, 赛璐璐画风",
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
        }
        """
        size = size or "auto"
        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "response_format": "b64_json",
            **kwargs,
        }
        return payload

    @property
    @override
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @override
    def parse_response(self, response: httpx.Response) -> dict:
        """
        Example:
        {
            "data": [{
                "b64_json": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABOYA3Q..."
            }],
            "created": 1776789055
            "usage": {
                "input_tokens":773,
                "output_tokens":765,
                "total_tokens":1538,
                "input_tokens_details": {
                    "text_tokens":8,
                    "image_tokens":765
                }
            }
        }
        """
        raw_data = super().parse_response(response)

        images: list[tuple[bytes, str]] = []
        data_items: list[dict] = raw_data.get("data") or []
        for item in data_items:
            encoded: str = item.get("b64_json") or ""
            if not encoded:
                continue

            if encoded.startswith("data:"):
                match = B64_PARSE_PATTERN.match(encoded)
                if match:
                    mime_type = match.group(1)
                    b64_data = match.group(2)
                else:
                    raise ValueError(
                        f"Invalid base64 data in response: {encoded[:100]}... (truncated)"
                    )
            else:
                mime_type = "image/png"  # fallback to png
                b64_data = encoded
            try:
                decoded = base64.b64decode(b64_data)
            except Exception as e:
                raise ValueError(
                    f"Failed to decode base64 data in response: {e}. b64_json: {encoded[:100]}... (truncated)"
                ) from e
            images.append((decoded, mime_type))
        return {
            "images": images,
        }

    @classmethod
    def _resolve_size(
        cls,
        resolution: str,
        aspect_ratio_val: float | None,
    ) -> str:
        """Convert (resolution, aspect_ratio) to a pixel size string."""
        resolution = resolution.upper()
        if resolution == "1K":
            max_pixel = 1024**2
        elif resolution == "2K":
            max_pixel = 2048**2
        else:
            raise ValueError(f"Unsupported resolution: {resolution}")
        aspect_ratio_val = aspect_ratio_val or 1
        if aspect_ratio_val < 1 / 3 or aspect_ratio_val > 3:
            raise ValueError(f"Aspect ratio value must be between [1/3, 3], got {aspect_ratio_val}")

        width: int = round(math.sqrt(max_pixel * aspect_ratio_val))
        height: int = round(math.sqrt(max_pixel / aspect_ratio_val))
        return f"{width}x{height}"


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
