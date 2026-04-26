from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from sn_image_base.u1_api.paths import (
    generation_file_presigned_url,
    generation_file_upload_url,
)


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
            Absolute URL to download directly, or OSS key (fetches presigned URL
            then downloads; no fallback to direct files API).
        output_path (Path):
            The local file path where the image will be saved.

    Returns:
        Path:
            The path to the downloaded image file.
    """
    if is_absolute_url(image_ref):
        response = await client.get(image_ref, headers=headers)
    else:
        # Presigned OSS GET must not use the same AsyncClient default headers as API
        # calls (e.g. Content-Type: application/json), or the OSS signature will not match.
        presigned_url = await generate_presigned_url(client, base_url, headers, image_ref)
        async with httpx.AsyncClient(
            timeout=client.timeout,
            trust_env=True,
        ) as fetch_client:
            response = await fetch_client.get(presigned_url)
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
