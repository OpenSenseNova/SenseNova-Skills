from __future__ import annotations

import base64
import contextlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


class U1BaseError(Exception):
    MESSAGE = "Base error"

    def __init__(
        self,
        message: str | None = None,
        detail: str | None = None,
        code: int | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            message = self.MESSAGE
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        if self.code:
            msg = f"{self.__class__.__name__}[{self.code}]"
        else:
            msg = f"{self.__class__.__name__}"
        if self.message:
            msg += f"(message={self.message!r})"
        if self.detail:
            msg += f" <detail>{self.detail}</detail>"
        return msg


# ----------------------
# HTTP Errors
# ----------------------


class U1HttpErrorBase(U1BaseError):
    MESSAGE = "Base HTTP Error"


class U1HttpAuthError(U1HttpErrorBase):
    MESSAGE = "Authentication or Authorization Failed"


class U1HttpNotFoundError(U1HttpErrorBase):
    MESSAGE = "Resource Not Found"


class U1HttpTooManyRequestsError(U1HttpErrorBase):
    MESSAGE = "Too Many Requests"


class U1HttpServerError(U1HttpErrorBase):
    MESSAGE = "Server Error"


class U1HttpBadRequestError(U1HttpErrorBase):
    MESSAGE = "Bad Request"


class U1HttpPermissionError(U1HttpErrorBase):
    MESSAGE = "Permission Error"


class U1HttpResponseParseError(U1HttpErrorBase):
    MESSAGE = "Failed to parse HTTP response"


class U1HttpTimeoutError(U1HttpErrorBase):
    MESSAGE = "Timeout Error"


class U1HttpNetworkError(U1HttpErrorBase):
    MESSAGE = "Network Error"


class U1HttpUnknownError(U1HttpErrorBase):
    MESSAGE = "Unknown Error"


class U1HttpForbiddenContentError(U1HttpErrorBase):
    MESSAGE = "Forbidden Content Filtered"


class U1HttpTruncatedResponseError(U1HttpErrorBase):
    MESSAGE = "Truncated Response"


class U1HttpBadResponseError(U1HttpErrorBase):
    MESSAGE = "Bad Response"


def finish_reason_to_error_class(finish_reason: str) -> tuple[type[U1HttpErrorBase], str]:
    if finish_reason == "length":
        explanation = "Response was truncated due to length limit."
        return U1HttpTruncatedResponseError, explanation
    elif finish_reason == "content_filter":
        explanation = "Response was filtered due to content policy."
        return U1HttpForbiddenContentError, explanation
    elif finish_reason in ("tool_calls", "function_call"):
        explanation = "Response was halted due to tool calls or function calls."
        return U1HttpBadRequestError, explanation
    elif finish_reason == "stop":
        explanation = "Response was completed normally."
        return U1HttpBadResponseError, explanation
    return U1HttpBadRequestError, f"Unknown finish reason: {finish_reason!r}."


def error_type_to_error_class(error_type: str) -> tuple[type[U1HttpErrorBase], str]:
    if error_type == "invalid_request_error":
        explanation = "Invalid request error."
        return U1HttpBadRequestError, explanation
    elif error_type == "rate_limit_error":
        explanation = "Rate limit exceeded."
        return U1HttpTooManyRequestsError, explanation
    elif error_type == "authentication_error":
        explanation = "Authentication error."
        return U1HttpAuthError, explanation
    elif error_type == "api_error":
        explanation = "API service internal error."
        return U1HttpServerError, explanation
    elif error_type == "permission_error":
        explanation = "You are not authorized to access this resource."
        return U1HttpPermissionError, explanation
    return U1HttpBadRequestError, f"Unknown error type: {error_type!r}."


def sanitize_base64_in_data(data: Any, *, truncate_length: int = 200) -> Any:
    """Recursively replace base64-encoded strings in data structure.

    Args:
        data: Data to sanitize (dict, list, str, or other)
        truncate_length: Maximum length of base64-encoded string to truncate

    Returns:
        Sanitized data with base64 strings replaced by placeholders

    Example:
        >>> _sanitize_base64_in_data({"image": "iVBORw0KG..." * 100})
        {"image": "<base64-data: 1200 bytes>"}
    """
    # Handle binary data first (bytes, bytearray, memoryview)
    if isinstance(data, (bytes, bytearray)):
        # Try: bytes -> str
        with contextlib.suppress(Exception):
            data = data.decode("utf-8")
    if isinstance(data, (bytes, bytearray, memoryview)):
        return f'<binary-data len="{len(data)}bytes"/>'
    if isinstance(data, str):
        # Try: str -> dict | list
        with contextlib.suppress(Exception):
            data = json.loads(data)

    seen_ids: set[int] = set()  # Prevent circular references

    def __recursive_sanitize_base64_in_data(
        data: Mapping | Iterable | str | Any,
    ) -> dict | list | str | Any:
        if isinstance(data, str):
            if _is_base64_string(data) and len(data) > truncate_length:
                # Truncate base64-encoded string, replace it with placeholder
                len_str = f"{len(data):,d}bytes"
                return f'<base64-data len="{len_str}">{data[:truncate_length]}...{TRUNCATED_MARKER}...{data[-truncate_length:]}</base64-data>'
            return data
        elif isinstance(data, Mapping):
            obj_id = id(data)
            if obj_id in seen_ids:
                return "<circular-reference:mapping/>"
            seen_ids.add(obj_id)
            result = {
                key: __recursive_sanitize_base64_in_data(value) for key, value in data.items()
            }
            seen_ids.remove(obj_id)
            return result
        elif isinstance(data, Iterable):
            obj_id = id(data)
            if obj_id in seen_ids:
                return "<circular-reference:iterable/>"
            seen_ids.add(obj_id)
            result = [__recursive_sanitize_base64_in_data(item) for item in data]
            seen_ids.remove(obj_id)
            return result
        return data

    return __recursive_sanitize_base64_in_data(data)


TRUNCATED_MARKER = "<<<///TRUNCATED///>>>"
BASE64_DETECTION_MIN_LENGTH = 200  # Minimum length to consider as potential base64
BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


def _is_base64_string(value: str) -> bool:
    """Check if a string looks like base64-encoded data.

    Args:
        value: String to check

    Returns:
        True if the string appears to be base64-encoded data

    Heuristics:
        - Length >= BASE64_DETECTION_MIN_LENGTH (200 chars)
        - At least 80% of characters are valid base64 chars (A-Za-z0-9+/=)
        - No whitespace or newlines (valid base64 is continuous)
    """
    if not isinstance(value, str) or len(value) < BASE64_DETECTION_MIN_LENGTH:
        return False

    # Check if mostly base64 characters (allow some tolerance)
    if value.startswith("data:"):
        # Remove the prefix like "data:image/jpeg;base64,"
        index = value.find(";base64,")
        if index != -1:
            value = value[index + len(";base64,") :]
    valid_count = sum(1 for c in value if c in BASE64_CHARS)
    ratio = valid_count / len(value)

    if ratio >= 0.98:
        with contextlib.suppress(Exception):
            base64.b64decode(value)
            return True

    return False
