"""U1 REST API path segments (relative to API base URL, no host)."""

from __future__ import annotations

from urllib.parse import quote

GENERATION_TEXT_TO_IMAGE = "/v1/generation/text-to-image"
GENERATION_FILES_PREFIX = "/v1/generation/files"


def join_base(base_url: str, path: str) -> str:
    """Join a base URL with a path segment.

    Args:
        base_url (str):
            The API base URL (e.g., "https://api.example.com").
        path (str):
            The path segment to append.

    Returns:
        str:
            The joined URL with the base stripped of trailing slashes and
            the path prepended with a leading slash if missing.
    """
    base = base_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base}/{path}"


def text_to_image_create_url(base_url: str) -> str:
    """Build the URL for submitting a text-to-image generation task.

    Args:
        base_url (str):
            The API base URL.

    Returns:
        str:
            The full URL for the text-to-image creation endpoint.
    """
    return join_base(base_url, GENERATION_TEXT_TO_IMAGE)


def text_to_image_status_url(base_url: str, task_id: str) -> str:
    """Build the URL for checking the status of a text-to-image task.

    Args:
        base_url (str):
            The API base URL.
        task_id (str):
            The unique identifier of the generation task.

    Returns:
        str:
            The full URL for the text-to-image status endpoint.
    """
    return join_base(base_url, f"{GENERATION_TEXT_TO_IMAGE}/{task_id}")


def generation_file_download_url(base_url: str, image_ref: str) -> str:
    """Build the URL for downloading a generated file.

    Args:
        base_url (str):
            The API base URL.
        image_ref (str):
            The file reference (key) for the generated image.

    Returns:
        str:
            The full URL for the file download endpoint, with the image
            key URL-encoded.
    """
    image_key = image_ref.lstrip("/")
    return f"{join_base(base_url, GENERATION_FILES_PREFIX)}/{quote(image_key, safe='/')}"


def generation_file_upload_url(base_url: str) -> str:
    """Build the URL for uploading generation files.

    Args:
        base_url (str):
            The API base URL.

    Returns:
        str:
            The full URL for the file upload endpoint.
    """
    return join_base(base_url, GENERATION_FILES_PREFIX)


def generation_file_presigned_url(base_url: str) -> str:
    """Build the URL for generating a presigned URL for file upload/download.

    Args:
        base_url (str):
            The API base URL.

    Returns:
        str:
            The full URL for the presigned URL generation endpoint.
    """
    return join_base(base_url, f"{GENERATION_FILES_PREFIX}/generate-presigned-url")
