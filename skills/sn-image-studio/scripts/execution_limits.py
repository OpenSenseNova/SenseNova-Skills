"""Coordinated time budgets, in seconds, for one image task (no automatic retries)."""

CONNECT_TIMEOUT = 30
UPLOAD_TIMEOUT = 120
IMAGE_RESPONSE_TIMEOUT = 15 * 60
IMAGE_DOWNLOAD_TIMEOUT = 120
# Leave time for upload, generation, download, decoding, and receipt publication.
IMAGE_PROCESS_TIMEOUT = 20 * 60
TASK_RECEIPT_TIMEOUT = IMAGE_PROCESS_TIMEOUT + 60
DEFAULT_AGENT_TIMEOUT = TASK_RECEIPT_TIMEOUT + 9 * 60


def error_text(exc, context):
    """Some network exceptions have an empty message; never persist a blank error."""
    return str(exc).strip() or f"{context}（{type(exc).__name__}）。"
