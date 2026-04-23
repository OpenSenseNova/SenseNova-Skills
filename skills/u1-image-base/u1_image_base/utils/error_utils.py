from __future__ import annotations

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
        return f"{self.message}: {self.detail}"


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


class U1HttpResponseParseError(U1HttpErrorBase):
    MESSAGE = "Failed to parse HTTP response"


class U1HttpTimeoutError(U1HttpErrorBase):
    MESSAGE = "Timeout Error"


class U1HttpNetworkError(U1HttpErrorBase):
    MESSAGE = "Network Error"


class U1HttpUnknownError(U1HttpErrorBase):
    MESSAGE = "Unknown Error"
