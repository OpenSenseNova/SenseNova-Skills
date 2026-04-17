"""Async Text-to-Image (no-enhance) client using the U1 API (REST + polling).

Usage:
    from generation.text_to_image import TextToImageClient
    client = TextToImageClient(api_key="sk-xxx", base_url="https://...")
    result = await client.generate(prompt="a cute cat")
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from u1_api.paths import (
    generation_file_download_url,
    generation_file_presigned_url,
    generation_file_upload_url,
    text_to_image_create_url,
    text_to_image_status_url,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


DEFAULT_MODEL_SIZE = "2k"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_TIMEOUT = 300.0
API_KEY_ENV = "U1_API_KEY"
BASE_URL_ENV = "U1_BASE_URL"
OUTPUT_DIR = Path("/tmp/openclaw-u1-image")


def build_headers(api_key: str) -> dict[str, str]:
    """Build HTTP headers for API authentication.

    Args:
        api_key (str):
            The API key for authentication.

    Returns:
        dict[str, str]:
            Headers dictionary with Authorization set to the api_key.
    """
    return {"Authorization": api_key}


def ensure_output_path(path: Path) -> Path:
    """Ensure the parent directory of the given path exists.

    Args:
        path (Path):
            The file path whose parent directory should be created.

    Returns:
        Path:
            The original path unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def is_absolute_url(value: str) -> bool:
    """Check if the given value is an absolute URL.

    Args:
        value (str):
            The string to check.

    Returns:
        bool:
            True if value contains both a scheme (e.g., "http") and
            a network location (netloc), False otherwise.
    """
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def extract_task_input(task: dict) -> dict:
    """Extract the input parameters from a task dictionary.

    Args:
        task (dict):
            The task dictionary, typically from an API response.

    Returns:
        dict:
            The input parameters if available, otherwise a subset of
            fields (prompt, negative_prompt, image_size, aspect_ratio,
            seed, unet_name) from the task.
    """
    task_input = task.get("input")
    if isinstance(task_input, dict):
        return task_input
    return {
        key: task.get(key)
        for key in (
            "prompt",
            "negative_prompt",
            "image_size",
            "aspect_ratio",
            "seed",
            "unet_name",
        )
        if key in task
    }


def extract_task_image(task: dict) -> dict | None:
    """Extract the image result from a completed task.

    Args:
        task (dict):
            The task dictionary from an API response.

    Returns:
        dict | None:
            The image dictionary containing a URL if present,
            otherwise None.
    """
    image = task.get("image")
    if isinstance(image, dict) and image.get("url"):
        return image
    return None


async def download_image(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    image_ref: str,
    output_path: Path,
) -> Path:
    """Download an image from a URL or image reference.

    Args:
        client (httpx.AsyncClient):
            The HTTP client for making requests.
        base_url (str):
            The API base URL.
        headers (dict[str, str]):
            HTTP headers including authentication.
        image_ref (str):
            The image reference (URL or cached file key) to download.
        output_path (Path):
            The local file path where the image will be saved.

    Returns:
        Path:
            The path to the downloaded image file.
    """
    if is_absolute_url(image_ref):
        response = await client.get(image_ref, headers=headers)
    else:
        download_url = generation_file_download_url(base_url, image_ref)
        response = await client.get(download_url, headers=headers)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return output_path


async def upload_local_image(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    image_path: Path,
) -> str:
    """Upload a local image file to the generation service.

    Args:
        client (httpx.AsyncClient):
            The HTTP client for making requests.
        base_url (str):
            The API base URL.
        headers (dict[str, str]):
            HTTP headers including authentication.
        image_path (Path):
            Path to the local image file to upload.

    Returns:
        str:
            The OSS path returned by the server after successful upload.

    Raises:
        ValueError:
            If the server response is not a non-empty string.
    """
    with open(image_path, "rb") as image_file:
        response = await client.post(
            generation_file_upload_url(base_url),
            headers=headers,
            files={"upload_file": (image_path.name, image_file)},
        )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, str) or not body:
        raise ValueError(f"unexpected upload response: {body}")
    return body


async def generate_presigned_url(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    oss_path: str,
) -> str:
    """Generate a presigned URL for accessing an OSS file.

    Args:
        client (httpx.AsyncClient):
            The HTTP client for making requests.
        base_url (str):
            The API base URL.
        headers (dict[str, str]):
            HTTP headers including authentication.
        oss_path (str):
            The OSS file path for which to generate a presigned URL.

    Returns:
        str:
            The presigned URL for accessing the file.

    Raises:
        ValueError:
            If the server response is not a non-empty string.
    """
    response = await client.get(
        generation_file_presigned_url(base_url),
        headers=headers,
        params={"oss_path": oss_path},
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, str) or not body:
        raise ValueError(f"unexpected presigned url response: {body}")
    return body


async def resolve_image_ref(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    image_value: str,
) -> str:
    """Resolve an image reference to a URL.

    Args:
        client (httpx.AsyncClient):
            The HTTP client for making requests.
        base_url (str):
            The API base URL.
        headers (dict[str, str]):
            HTTP headers including authentication.
        image_value (str):
            An image reference: absolute URL, local file path, or cached key.

    Returns:
        str:
            A URL suitable for use in API requests. If image_value is an
            absolute URL, it is returned as-is. If it is a local file,
            the file is uploaded and a presigned URL is returned.
    """
    if is_absolute_url(image_value):
        return image_value
    if Path(image_value).is_file():
        uploaded_path = await upload_local_image(client, base_url, headers, Path(image_value))
        return await generate_presigned_url(client, base_url, headers, uploaded_path)
    return image_value


class TextToImageClient:
    """Async client for U1 text-to-image-no-enhance API."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT,
        insecure: bool = False,
    ) -> None:
        """Initialize the TextToImageClient.

        Args:
            api_key (str):
                API key for authentication.
            base_url (str | None, optional):
                API base URL. If None, reads from U1_BASE_URL env var.
            poll_interval (float, optional):
                Polling interval in seconds for task status checks.
                Defaults to DEFAULT_POLL_INTERVAL.
            timeout (float, optional):
                Total timeout in seconds for the generate call.
                Defaults to DEFAULT_TIMEOUT.
            insecure (bool, optional):
                If True, disable TLS verification. Defaults to False.
        """
        self.api_key = api_key
        self.base_url = (base_url or os.getenv(BASE_URL_ENV, "")).rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.insecure = insecure
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, verify=not self.insecure)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        image_size: str = DEFAULT_MODEL_SIZE,
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
        if not self.api_key:
            return {"status": "failed", "error": f"{API_KEY_ENV} is required"}

        payload: dict = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_size": image_size,
            "aspect_ratio": aspect_ratio,
        }
        if seed is not None:
            payload["seed"] = seed
        if unet_name is not None:
            payload["unet_name"] = unet_name

        headers = build_headers(self.api_key)
        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            import time

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"t2i_{timestamp}.png"
        output_path = ensure_output_path(output_path)

        client = await self._get_client()

        try:
            create_response = await client.post(
                text_to_image_create_url(self.base_url),
                json=payload,
                headers=headers,
            )
            create_response.raise_for_status()
            task = create_response.json()
            task_id = task["id"]

            deadline = asyncio.get_event_loop().time() + self.timeout
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

                if asyncio.get_event_loop().time() >= deadline:
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


async def main_async(
    prompt: str,
    api_key: str,
    base_url: str | None = None,
    negative_prompt: str = "",
    image_size: str = DEFAULT_MODEL_SIZE,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    seed: int | None = None,
    unet_name: str | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    timeout: float = DEFAULT_TIMEOUT,
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
            API base URL. If None, reads from U1_BASE_URL env var.
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
            Timeout in seconds. Defaults to DEFAULT_TIMEOUT.
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
    client = TextToImageClient(
        api_key=api_key,
        base_url=base_url,
        poll_interval=poll_interval,
        timeout=timeout,
        insecure=insecure,
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
    parser.add_argument("--api-key", default=os.getenv(API_KEY_ENV, ""), help="API key")
    parser.add_argument("--base-url", default=os.getenv(BASE_URL_ENV, ""), help="API base URL")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
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
