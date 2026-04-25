"""Async Image Edit client using the U1 API (REST + polling).

Usage:
    from image_edit.image_edit import ImageEditClient
    client = ImageEditClient(api_key="sk-xxx", base_url="https://...")
    result = await client.edit(image="input.png", prompt="remove watermark")
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

from u1_image_base.configs import global_configs
from u1_image_base.generation.core import (
    download_image,
    ensure_output_path,
    resolve_image_ref,
)
from u1_image_base.u1_api.paths import (
    image_edit_create_url,
    image_edit_status_url,
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


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


def extract_task_input(task: dict) -> dict:
    """Extract the input parameters from a task dictionary.

    Args:
        task (dict):
            The task dictionary, typically from an API response.

    Returns:
        dict:
            The input parameters if available, otherwise a subset of
            fields (image, prompt, seed) from the task.
    """
    task_input = task.get("input")
    if isinstance(task_input, dict):
        return task_input
    return {key: task.get(key) for key in ("image", "prompt", "seed") if key in task}


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


class ImageEditClient:
    """Async client for U1 image-edit API."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        timeout: float = DEFAULT_TIMEOUT,
        insecure: bool = False,
    ) -> None:
        """Initialize the ImageEditClient.

        Args:
            api_key (str):
                API key for authentication.
            base_url (str | None, optional):
                API base URL. If None, reads from U1_BASE_URL env var.
            poll_interval (float, optional):
                Polling interval in seconds for task status checks.
                Defaults to DEFAULT_POLL_INTERVAL.
            timeout (float, optional):
                Total timeout in seconds for the edit call.
                Defaults to DEFAULT_TIMEOUT.
            insecure (bool, optional):
                If True, disable TLS verification. Defaults to False.
        """
        self.api_key = api_key
        self.base_url = (base_url or global_configs.VLM_BASE_URL).rstrip("/")
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

    async def edit(
        self,
        image: str,
        prompt: str,
        seed: int | None = None,
        output_path: Path | None = None,
    ) -> dict:
        """Edit an image based on the prompt.

        Args:
            image (str):
                Local image path, remote URL, or cached file key.
            prompt (str):
                Edit instruction prompt.
            seed (int | None, optional):
                Random seed for reproducibility. Defaults to None.
            output_path (Path | None, optional):
                Output path for the edited image. Defaults to None.

        Returns:
            dict:
                Dictionary with keys: status, output (path), task_id, message.
        """
        if not self.api_key:
            return {"status": "failed", "error": f"{API_KEY_ENV} is required"}

        headers = build_headers(self.api_key)
        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            import time

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = OUTPUT_DIR / f"edit_{timestamp}.png"
        output_path = ensure_output_path(output_path)

        client = await self._get_client()

        try:
            image_ref = await resolve_image_ref(client, self.base_url, headers, image)

            payload: dict = {
                "image": image_ref,
                "prompt": prompt,
            }
            if seed is not None:
                payload["seed"] = seed

            create_response = await client.post(
                image_edit_create_url(self.base_url),
                json=payload,
                headers=headers,
            )
            create_response.raise_for_status()
            task = create_response.json()
            task_id = task["id"]

            deadline = asyncio.get_event_loop().time() + self.timeout
            while True:
                status_response = await client.get(
                    image_edit_status_url(self.base_url, task_id),
                    headers=headers,
                )
                status_response.raise_for_status()
                task = status_response.json()
                state = task["state"]
                # progress = task.get("progress", 0.0)

                if state == "completed":
                    image_result = extract_task_image(task)
                    if not image_result:
                        return {
                            "status": "failed",
                            "error": f"task completed but no image found: {task}",
                            "task_id": task_id,
                        }
                    saved_path = await download_image(
                        client=client,
                        base_url=self.base_url,
                        headers=headers,
                        image_ref=image_result["url"],
                        output_path=output_path,
                    )
                    return {
                        "status": "ok",
                        "output": str(saved_path),
                        "task_id": task_id,
                        "message": "Image edited successfully",
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
    image: str,
    prompt: str,
    api_key: str,
    base_url: str | None = None,
    seed: int | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    timeout: float = DEFAULT_TIMEOUT,
    insecure: bool = False,
    output_format: str = "text",
    save_path: Path | None = None,
) -> int:
    """Async entry point for image-edit.

    Args:
        image (str):
            Local image path, remote URL, or cached file key.
        prompt (str):
            Edit instruction prompt.
        api_key (str):
            API key for authentication.
        base_url (str | None, optional):
            API base URL. If None, reads from U1_BASE_URL env var.
        seed (int | None, optional):
            Random seed. Defaults to None.
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
    client = ImageEditClient(
        api_key=api_key,
        base_url=base_url,
        poll_interval=poll_interval,
        timeout=timeout,
        insecure=insecure,
    )
    try:
        result = await client.edit(
            image=image,
            prompt=prompt,
            seed=seed,
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

    parser = argparse.ArgumentParser(description="Async image-edit client.")
    parser.add_argument(
        "--image",
        required=True,
        help="Local image path, remote URL, or cached file key",
    )
    parser.add_argument("--prompt", required=True, help="Edit instruction prompt")
    parser.add_argument("--api-key", default=global_configs.VLM_API_KEY, help="API key")
    parser.add_argument("--base-url", default=global_configs.VLM_BASE_URL, help="API base URL")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
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
