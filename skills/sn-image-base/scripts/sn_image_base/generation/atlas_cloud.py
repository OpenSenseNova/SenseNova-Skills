from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

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

DEFAULT_MODEL_SIZE: Literal["2K", "4K"] = "2K"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
OUTPUT_DIR = Path("/tmp/openclaw-sn-image")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TERMINAL_FAILURE_STATES = frozenset({"failed", "timeout", "canceled", "cancelled"})
ATLAS_2K_SIZES = {
    "2:3": "1664*2496",
    "3:2": "2496*1664",
    "3:4": "1728*2304",
    "4:3": "2304*1728",
    "4:5": "1792*2240",
    "5:4": "2240*1792",
    "1:1": "1920*1920",
    "16:9": "2560*1440",
    "9:16": "1440*2560",
    "21:9": "3024*1296",
    "9:21": "1296*3024",
}


class AtlasCloudText2ImageClient(T2IBaseClient):
    """Async client for Atlas Cloud task-based image generation."""

    SUBMIT_PATH = "/model/generateImage"
    RESULT_PATH = "/model/result"

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
        image_size: Literal["2K", "4K", "2k", "4k"] = DEFAULT_MODEL_SIZE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        output_path: Path | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        **kwargs: Any,
    ) -> dict:
        resolved_model = model or self.model or global_configs.SN_IMAGE_GEN_MODEL
        if not resolved_model:
            raise BadConfigurationError(
                f"Model is not set. {global_configs.get_env_var_help('SN_IMAGE_GEN_MODEL')}"
            )
        if poll_interval < 0:
            raise ValueError("poll_interval must be greater than or equal to zero")

        size = self._resolve_size(image_size.upper(), aspect_ratio)
        payload = self.build_payload(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=resolved_model,
            size=size,
        )
        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / f"t2i_{time.strftime('%Y%m%d_%H%M%S')}.png"
        saved_path = ensure_output_path(output_path).with_suffix(".png")

        client = await self._get_client()
        try:
            submit_response = await client.post(self.get_api_url(), json=payload)
            submitted = self.parse_response(submit_response)
            if error := self._response_error(submitted):
                return self._failure("AtlasApiError", error)
            prediction_id = self._unwrap(submitted).get("id")
            if not prediction_id:
                return self._failure(
                    "InvalidResponse", "Atlas Cloud submission did not return a prediction id"
                )

            image_url = await self._poll_result(
                client,
                str(prediction_id),
                poll_interval=poll_interval,
            )
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._ssl_verify,
            ) as download_client:
                download_response = await download_client.get(image_url)
                download_response.raise_for_status()
                image_bytes = download_response.content
            if not image_bytes.startswith(PNG_SIGNATURE):
                return self._failure("InvalidImage", "Atlas Cloud output is not a PNG image")

            saved_path.write_bytes(image_bytes)
            return {
                "status": "ok",
                "output": str(saved_path),
                "task_id": str(prediction_id),
                "message": "Image generated successfully",
            }
        except U1HttpErrorBase as exc:
            details = f"\n{exc.detail}" if exc.detail else ""
            return self._failure(
                type(exc).__name__, f"HTTP {exc.code}: {exc.message}{details}"
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            return self._failure(type(exc).__name__, str(exc))

    async def _poll_result(
        self,
        client: httpx.AsyncClient,
        prediction_id: str,
        *,
        poll_interval: float,
    ) -> str:
        deadline = asyncio.get_running_loop().time() + self._timeout
        result_url = (
            f"{self.base_url.rstrip('/')}{self.RESULT_PATH}/"
            f"{quote(prediction_id, safe='')}"
        )
        while asyncio.get_running_loop().time() < deadline:
            response = await client.get(result_url)
            payload = self.parse_response(response)
            if error := self._response_error(payload):
                raise ValueError(error)
            data = self._unwrap(payload)
            status = str(data.get("status") or "").lower()
            if status in {"completed", "succeeded"}:
                output = data.get("outputs", data.get("output"))
                if isinstance(output, list):
                    image_url = next((item for item in output if isinstance(item, str)), None)
                else:
                    image_url = output if isinstance(output, str) else None
                if not image_url:
                    raise ValueError("Atlas Cloud completed task did not return an output URL")
                return image_url
            if status in TERMINAL_FAILURE_STATES:
                raise ValueError(
                    f"Atlas Cloud prediction {prediction_id} ended with status {status}"
                )
            await asyncio.sleep(poll_interval)
        raise ValueError(f"Atlas Cloud prediction {prediction_id} timed out")

    @property
    @override
    def api_key(self) -> str:
        api_key = self._api_key or global_configs.SN_IMAGE_GEN_API_KEY
        if not api_key:
            raise ValueError(
                "API key is missing: "
                + global_configs.get_env_var_help("SN_IMAGE_GEN_API_KEY")
            )
        return api_key

    @property
    @override
    def base_url(self) -> str:
        base_url = self._base_url or global_configs.SN_IMAGE_GEN_BASE_URL
        if not base_url:
            raise ValueError(
                "Base URL is missing: "
                + global_configs.get_env_var_help("SN_IMAGE_GEN_BASE_URL")
            )
        if not is_valid_base_url(base_url):
            raise ValueError(f"Base URL is not valid: {base_url}")
        return base_url

    @override
    def get_api_url(self, model: str | None = None) -> str:
        return f"{self.base_url.rstrip('/')}{self.SUBMIT_PATH}"

    @override
    def build_payload(
        self,
        prompt: str,
        model: str,
        *,
        negative_prompt: str = "",
        size: str,
        **kwargs: Any,
    ) -> dict:
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "output_format": "png",
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    @property
    @override
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_size(resolution: str, aspect_ratio: str) -> str:
        if resolution not in {"2K", "4K"}:
            raise ValueError(f"Unsupported image size: {resolution}")
        if resolution == "2K":
            try:
                return ATLAS_2K_SIZES[aspect_ratio]
            except KeyError as exc:
                raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc
        width_text, separator, height_text = aspect_ratio.partition(":")
        if not separator:
            raise ValueError(f"Invalid aspect ratio: {aspect_ratio}")
        try:
            width_ratio = int(width_text)
            height_ratio = int(height_text)
            if width_ratio <= 0 or height_ratio <= 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"Invalid aspect ratio: {aspect_ratio}") from exc

        long_edge = 4096
        if width_ratio >= height_ratio:
            width = long_edge
            height = round(long_edge * height_ratio / width_ratio / 8) * 8
        else:
            height = long_edge
            width = round(long_edge * width_ratio / height_ratio / 8) * 8
        return f"{width}*{height}"

    @staticmethod
    def _unwrap(payload: dict) -> dict:
        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    @staticmethod
    def _response_error(payload: dict) -> str | None:
        if error := payload.get("error"):
            if isinstance(error, dict):
                return str(error.get("message") or error)
            return str(error)
        code = payload.get("code")
        if code is not None and code not in {0, 200}:
            return str(payload.get("message") or f"Atlas Cloud API returned code {code}")
        return None

    @staticmethod
    def _failure(error_type: str, error: str) -> dict:
        return {"status": "failed", "error_type": error_type, "error": error}
