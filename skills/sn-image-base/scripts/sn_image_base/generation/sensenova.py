from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx
from PIL import Image
from typing_extensions import override

from sn_image_base.configs import global_configs, is_valid_base_url
from sn_image_base.exceptions import InvalidBaseUrlError, MissingApiKeyError
from sn_image_base.generation.core import ensure_output_path
from sn_image_base.generation.core.client_base import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    T2IBaseClient,
)
from sn_image_base.utils.error_utils import U1HttpErrorBase

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_RESOLUTION: Literal["1K", "2K", "4K"] = "2K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
OUTPUT_DIR = Path("/tmp/openclaw-sn-image")


IMAGE_GEN_ENDPOINT = "/images/generations"


class SensenovaText2ImageClient(T2IBaseClient):
    """Async client for Sensenova text-to-image API."""

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
        """Initialize the SensenovaText2ImageClient.

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
        api_key = api_key or global_configs.SN_IMAGE_GEN_API_KEY
        if not api_key:
            raise MissingApiKeyError(
                "API key is missing: {}".format(
                    global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY")
                )
            )
        base_url = base_url or global_configs.SN_IMAGE_GEN_BASE_URL
        if not base_url:
            raise InvalidBaseUrlError(
                "Base URL is missing: {}".format(
                    global_configs.get_env_var_help("SN_IMAGE_GEN_BASE_URL")
                )
            )
        if not is_valid_base_url(base_url):
            raise InvalidBaseUrlError(
                f"Base URL is not a valid base URL: {base_url}. "
                f"Try setting environment variable(s): {global_configs.get_env_var_help('SN_IMAGE_GEN_BASE_URL')}"
            )
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
        image_size: Literal["1K", "2K", "4K"] = DEFAULT_RESOLUTION,
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
                Image size preset ("1K", "2K", "4K"). Defaults to DEFAULT_RESOLUTION.
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
        # Normalize image_size to uppercase for NanoBanana API
        image_size = image_size.upper()  # type: ignore[assignment]
        output_format = "png"
        size = self._resolve_size(image_size, aspect_ratio)
        payload = self.build_payload(
            prompt=prompt,
            model=model,
            size=size,
            aspect_ratio=aspect_ratio,
            output_format=output_format,
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
            # elif exc.code == 400:
            #     warnings.warn(f"Bad request: {exc.message}; body: {payload}", stacklevel=2)
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
            images_urls: list[str] = data["images_urls"]
            if not images_urls:
                return {
                    "status": "failed",
                    "error": "No image generated from the model",
                }
            url = images_urls[-1]
            suffix = f".{output_format}"
            save_path = output_path.with_suffix(suffix)
            saved_path = await download_image(url, save_path)
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
    def get_api_url(self, _model: str | None = None) -> str:
        base_url = self.base_url.rstrip("/")
        path = IMAGE_GEN_ENDPOINT.lstrip("/")
        api_url = f"{base_url}/{path}"
        return api_url

    @override
    def build_payload(
        self,
        prompt: str,
        model: str,
        *,
        size: str | None = None,
        modalities: Sequence[str] = ("text", "image"),
        output_format: Literal["png"] = "png",
        response_format: Literal["url"] = "url",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the payload for the SenseNova image-generation endpoint.

        Args:
            prompt (str): The prompt to generate an image for.
            model (str): The model to use for generation.
            size (str | None): Pixel size string (for example, "1920x1920").
            modalities (Sequence[str]): Reserved for compatibility; currently not sent.
            output_format (Literal["png"]): The output format of the image. Defaults to "png".
            response_format (Literal["url"]): The response format of the image. Defaults to "url".
            **kwargs (Any, optional): Additional parameters to pass to the API.

        Example:
        {
            "model": "sensenova-u1-fast",
            "prompt": "A cat wearing a hat",
            "size": "1024x1024",
            "response_format": "url",
            "output_format": "png",
        }
        """
        payload = {
            "model": model,
            "prompt": prompt,
            # "modalities": modalities,
            "size": size,
            # "n": 1,
            "response_format": response_format,
            "output_format": output_format,
            **kwargs,
        }
        return payload

    @property
    @override
    def headers(self) -> dict[str, str]:
        if not self.api_key:
            raise MissingApiKeyError(
                "API key is missing: {}".format(
                    global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY")
                )
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def _resolve_size(
        cls,
        resolution: Literal["1K", "2K"] | str | None = None,
        aspect_ratio: ASPECT_RATIO_LITERALS | str | None = None,
    ) -> str | None:
        """Convert (resolution, aspect_ratio) to a pixel size string.

        If aspect_ratio is None, returns the resolution as-is (e.g. "1K").
        """
        if not resolution and not aspect_ratio:
            return None
        resolution = resolution or "2K"
        aspect_ratio = aspect_ratio or "1:1"
        if resolution == "1K":
            buckets = BUCKETS_1K
        elif resolution == "2K":
            buckets = BUCKETS_2K
        else:
            raise ValueError(f"Unsupported resolution: {resolution!r}. Must be '1K' or '2K'.")
        try:
            ws, _, hs = aspect_ratio.strip().partition(":")
            width = int(ws)
            height = int(hs)
            ratio = width / height
        except Exception as e:
            raise ValueError(f"Invalid aspect ratio: {aspect_ratio!r}") from e
        if ratio > 16 / 9:
            raise ValueError(f"Aspect ratio {aspect_ratio!r} is too wide. Maximum is 16:9")
        if ratio < 9 / 21:
            raise ValueError(f"Aspect ratio {aspect_ratio!r} is too high. Maximum is 9:21")
        w, h = _find_nearest_aspect_ratio(ratio, buckets)
        return f"{w}x{h}"

    @override
    def parse_response(self, response: httpx.Response) -> dict:
        """Parse the response from the SenseNova image-generation endpoint.

        Example response data:

        ```json
        {
            "data": [{
                "url": "https://cdn.sensenova.dev/gen/..."
            }]
        }
        ```

        Args:
            response: The HTTP response from the SenseNova image-generation endpoint.

        Returns:
            dict: Parsed data with key ``images_urls``.
        """
        raw_data = super().parse_response(response)

        images_urls: list[str] = []
        for item in raw_data.get("data", []):
            url = item.get("url")
            if url:
                images_urls.append(url)
        return {"images_urls": images_urls}


async def download_image(
    url: str,
    save_path: Path,
    timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
) -> Path:
    """Download an image from a URL.

    Args:
        url: The URL of the image to download.
        timeout: The timeout for the request.

    Returns:
        Path: The path to the downloaded image file.
    """
    save_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    bytes_written = 0
    expected_length: int | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=save_path.parent,
            prefix=f".{save_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        expected_length = int(content_length)
                    async for chunk in response.aiter_bytes():
                        bytes_written += len(chunk)
                        temp_file.write(chunk)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        if expected_length is not None and bytes_written != expected_length:
            raise OSError(
                f"Downloaded image is incomplete: got {bytes_written} bytes, "
                f"expected {expected_length} bytes"
            )

        assert temp_path is not None
        _validate_image_file(temp_path)
        temp_path.replace(save_path)
        return save_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _validate_image_file(image_path: Path) -> None:
    """Verify that the downloaded image can be decoded completely."""
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        image.load()


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


ASPECT_RATIO_LITERALS = Literal[
    "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "1:1", "16:9", "9:16", "9:21"
]
BUCKETS_1K: dict[ASPECT_RATIO_LITERALS, tuple[int, int]] = {
    "2:3": (1088, 1632),
    "3:2": (1632, 1088),
    "3:4": (1152, 1536),
    "4:3": (1536, 1152),
    "4:5": (1184, 1472),
    "5:4": (1472, 1184),
    "1:1": (1344, 1344),
    "16:9": (1792, 992),
    "9:16": (992, 1792),
    "9:21": (864, 2048),
}
BUCKETS_2K: dict[ASPECT_RATIO_LITERALS, tuple[int, int]] = {
    "2:3": (1664, 2496),
    "3:2": (2496, 1664),
    "3:4": (1760, 2368),
    "4:3": (2368, 1760),
    "4:5": (1824, 2272),
    "5:4": (2272, 1824),
    "1:1": (2048, 2048),
    "16:9": (2752, 1536),
    "9:16": (1536, 2752),
    "9:21": (1344, 3136),
}


def _find_nearest_aspect_ratio(
    ratio: float,
    buckets: dict[ASPECT_RATIO_LITERALS, tuple[int, int]],
) -> tuple[int, int]:
    wh_pairs = sorted(
        buckets.values(),
        key=lambda wh: abs(wh[0] / wh[1] - ratio),
    )
    return wh_pairs[0]


if __name__ == "__main__":
    import asyncio

    async def main_async():
        client = SensenovaText2ImageClient(
            api_key=global_configs.SN_IMAGE_GEN_API_KEY,
            base_url=global_configs.SN_IMAGE_GEN_BASE_URL,
        )

        result = await client.generate(
            prompt="A cat wearing a hat",
            image_size="1K",
            aspect_ratio="16:9",
        )
        print(result)

    asyncio.run(main_async())
