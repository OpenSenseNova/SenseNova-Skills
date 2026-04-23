"""U1 REST API path segments (relative to API base URL, no host)."""

from __future__ import annotations

from urllib.parse import quote, urljoin, urlparse

GENERATION_TEXT_TO_IMAGE = "/v1/generation/text-to-image"
IMAGE_EDIT = "/v1/generation/image-edit"
GENERATION_FILES_PREFIX = "/v1/generation/files"
PROMPTS_EXPAND = "/v1/generation/prompts/expand"


def join_base(base_url: str, path: str) -> str:
    """Join a base URL with a path segment.
    The path of base_url is ignored.

    Example:
        join_base("https://api.example.com", "/v1/generation/text-to-image")
        -> "https://api.example.com/v1/generation/text-to-image"

        join_base("https://api.example.com/v1", "/v2/generation/text-to-image")
        -> "https://api.example.com/v2/generation/text-to-image"  # `"/v1"` is ignored

    Args:
        base_url (str):
            The API base URL (e.g., "https://api.example.com").
        path (str):
            The path segment to append.

    Returns:
        str:
            The joined URL, with the path of base_url ignored.
    """
    parsed = urlparse(base_url)
    return urljoin(parsed.geturl(), path)


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


def image_edit_create_url(base_url: str) -> str:
    """Build the URL for submitting an image edit task.

    Args:
        base_url (str):
            The API base URL.

    Returns:
        str:
            The full URL for the image edit creation endpoint.
    """
    return join_base(base_url, IMAGE_EDIT)


def image_edit_status_url(base_url: str, task_id: str) -> str:
    """Build the URL for checking the status of an image edit task.

    Args:
        base_url (str):
            The API base URL.
        task_id (str):
            The unique identifier of the image edit task.

    Returns:
        str:
            The full URL for the image edit status endpoint.
    """
    return join_base(base_url, f"{IMAGE_EDIT}/{task_id}")


def prompts_expand_url(base_url: str) -> str:
    """Build the URL for the prompts expand endpoint.

    Args:
        base_url (str):
            The API base URL.

    Returns:
        str:
            The full URL for the prompts expand endpoint.
    """
    return join_base(base_url, PROMPTS_EXPAND)


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
