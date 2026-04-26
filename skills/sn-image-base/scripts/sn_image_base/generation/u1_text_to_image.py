"""Async Text-to-Image (no-enhance) client using the U1 API (REST + polling).

Usage:
    from sn_image_base.generation import U1Text2ImageClient
    client = U1Text2ImageClient(api_key="sk-xxx", base_url="https://...")
    result = await client.generate(prompt="a cute cat")
"""

from __future__ import annotations

import asyncio
import json
import sys
import typing
from pathlib import Path

import httpx
from typing_extensions import Any, Literal, override

from sn_image_base.configs import global_configs, is_valid_base_url
from sn_image_base.u1_api.paths import (
    text_to_image_create_url,
    text_to_image_status_url,
)

from .core import download_image, ensure_output_path, extract_task_image
from .core.client_base import (
    DEFAULT_HTTP_REQUEST_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    T2IBaseClient,
)

DEFAULT_MODEL_SIZE = "2k"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
OUTPUT_DIR = Path("/tmp/openclaw-sn-image")


class U1Text2ImageClient(T2IBaseClient):
    """Async client for U1 text-to-image-no-enhance API."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        model: str | None = None,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
        ssl_verify: bool = True,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        **kwargs: typing.Any,
    ) -> None:
        """Initialize the U1Text2ImageClient.

        Args:
            api_key (str):
                API key for authentication.
            base_url (str | None, optional):
                API base URL. If None, reads from SN_IMAGE_GEN_BASE_URL env var.
            poll_interval (float, optional):
                Polling interval in seconds for task status checks.
                Defaults to DEFAULT_POLL_INTERVAL.
            timeout (float, optional):
                Total timeout in seconds for the generate call.
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
        self.poll_interval = poll_interval

    @override
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        model: str | None = None,
        image_size: Literal["1k", "2k", "4k"] = DEFAULT_MODEL_SIZE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        seed: int | None = None,
        unet_name: str | None = None,
        output_path: Path | None = None,
    ) -> dict:
        """Generate an image from text prompt.

        Args:
            prompt (str):
                Text prompt for image generation.
            negative_prompt (str, optional):
                Negative prompt. Defaults to "".
            image_size (str, optional):
                Image size preset ("1k" or "2k"). Defaults to DEFAULT_MODEL_SIZE.
            aspect_ratio (str, optional):
                Aspect ratio (e.g. "16:9", "1:1"). Defaults to DEFAULT_ASPECT_RATIO.
            seed (int | None, optional):
                Random seed for reproducibility. Defaults to None.
            unet_name (str | None, optional):
                Optional UNet model name. Defaults to None.
            output_path (Path | None, optional):
                Output path for the generated image. Defaults to None.

        Returns:
            dict:
                Dictionary with keys: status, output (path), task_id, message.
        """
        payload: dict = self.build_payload(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
            seed=seed,
            unet_name=unet_name,
        )
        headers = self.headers
        api_url = self.get_api_url()

        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            import time

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"t2i_{timestamp}.png"
        output_path = ensure_output_path(output_path)

        client = await self._get_client()

        try:
            create_response = await client.post(api_url, json=payload, headers=headers)
            task = self.parse_response(create_response)
            task_id = task["id"]

            deadline = asyncio.get_running_loop().time() + self._timeout
            while True:
                status_response = await client.get(
                    text_to_image_status_url(self.base_url, task_id),
                    headers=headers,
                )
                status_response.raise_for_status()
                task = status_response.json()
                state = task["state"]
                # progress = task.get("progress", 0.0)

                if state == "completed":
                    image = extract_task_image(task)
                    if not image:
                        return {
                            "status": "failed",
                            "error": f"task completed but no image found: {task}",
                            "task_id": task_id,
                        }
                    saved_path = await download_image(
                        client=client,
                        base_url=self.base_url,
                        headers=headers,
                        image_ref=image["url"],
                        output_path=output_path,
                    )
                    return {
                        "status": "ok",
                        "output": str(saved_path),
                        "task_id": task_id,
                        "message": "Image generated successfully",
                    }

                if state in {"failed", "canceled", "interrupted"}:
                    error_msg = task.get("error_message") or "unknown error"
                    return {
                        "status": "failed",
                        "error": f"Task {state}: {error_msg}",
                        "task_id": task_id,
                    }

                if asyncio.get_running_loop().time() >= deadline:
                    return {
                        "status": "failed",
                        "error": "Timeout",
                        "task_id": task_id,
                    }

                await asyncio.sleep(self.poll_interval)

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
        api_key = self._api_key or global_configs.SN_API_KEY
        if not api_key:
            raise ValueError(
                "API key is missing: {}".format(global_configs.get_env_var_help("SN_API_KEY"))
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
    def get_api_url(self) -> str:
        return text_to_image_create_url(self.base_url)

    @override
    def build_payload(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        image_size: str = DEFAULT_MODEL_SIZE,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> dict:
        payload: dict = {
            "prompt": prompt,
            "image_size": image_size,
            "aspect_ratio": aspect_ratio,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed := kwargs.get("seed"):
            payload["seed"] = seed
        if unet_name := kwargs.get("unet_name"):
            payload["unet_name"] = unet_name
        return payload

    @property
    @override
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }


async def main_async(
    prompt: str,
    api_key: str,
    base_url: str | None = None,
    negative_prompt: str = "",
    image_size: Literal["1k", "2k", "4k"] = DEFAULT_MODEL_SIZE,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    seed: int | None = None,
    unet_name: str | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    timeout: float = DEFAULT_HTTP_REQUEST_TIMEOUT,
    insecure: bool = False,
    output_format: str = "text",
    save_path: Path | None = None,
) -> int:
    """Async entry point for text-to-image generation.

    Args:
        prompt (str):
            Text prompt for image generation.
        api_key (str):
            API key for authentication.
        base_url (str | None, optional):
            API base URL. If None, reads from SN_BASE_URL env var.
        negative_prompt (str, optional):
            Negative prompt. Defaults to "".
        image_size (str, optional):
            Image size preset ("1k" or "2k"). Defaults to DEFAULT_MODEL_SIZE.
        aspect_ratio (str, optional):
            Aspect ratio (e.g. "16:9", "1:1"). Defaults to DEFAULT_ASPECT_RATIO.
        seed (int | None, optional):
            Random seed. Defaults to None.
        unet_name (str | None, optional):
            UNet model name. Defaults to None.
        poll_interval (float, optional):
            Polling interval in seconds. Defaults to DEFAULT_POLL_INTERVAL.
        timeout (float, optional):
            Timeout in seconds. Defaults to DEFAULT_HTTP_REQUEST_TIMEOUT.
        insecure (bool, optional):
            If True, disable TLS verification. Defaults to False.
        output_format (str, optional):
            Output format ("text" or "json"). Defaults to "text".
        save_path (Path | None, optional):
            Output image path. Defaults to None.

    Returns:
        int:
            Exit code: 0 for success, 1 for failure.
    """
    client = U1Text2ImageClient(
        api_key=api_key,
        base_url=base_url,
        model=global_configs.SN_IMAGE_GEN_MODEL,
        poll_interval=poll_interval,
        timeout=timeout,
        ssl_verify=not insecure,
    )
    try:
        result = await client.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
            seed=seed,
            unet_name=unet_name,
            output_path=save_path,
        )

        if output_format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            if result["status"] == "ok":
                if result.get("message"):
                    print(result["message"])
                print(result["output"])
            else:
                print(result.get("message") or result["error"], file=sys.stderr)

        return 0 if result["status"] == "ok" else 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    import argparse

    parser = argparse.ArgumentParser(
        description="Async text-to-image (no-enhance) generation client."
    )
    parser.add_argument("--prompt", required=True, help="Text prompt for image generation")
    parser.add_argument("--negative-prompt", default="", help="Negative prompt")
    parser.add_argument(
        "--image-size",
        default=DEFAULT_MODEL_SIZE,
        choices=["1k", "2k"],
        help="Image size preset",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        choices=[
            "2:3",
            "3:2",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
            "1:1",
            "16:9",
            "9:16",
            "21:9",
            "9:21",
        ],
        help="Aspect ratio",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--unet-name", default=None, help="UNet model name (optional)")
    parser.add_argument("--api-key", default=global_configs.SN_API_KEY, help="API key")
    parser.add_argument(
        "--base-url", default=global_configs.SN_IMAGE_GEN_BASE_URL, help="API base URL"
    )
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_HTTP_REQUEST_TIMEOUT)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    parser.add_argument(
        "-o",
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--save-path", type=Path, default=None, help="Output image path")

    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(**vars(args))))
