"""Shared exceptions for u1-image-base."""

from __future__ import annotations


class U1BaseError(Exception):
    """Base exception for u1-image-base."""

    DEFAULT_MESSAGE = "An error occurred in the u1-image-base skill."

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = self.DEFAULT_MESSAGE
        super().__init__(message)


class MissingApiKeyError(U1BaseError):
    """Raised when API key is not provided via CLI argument or U1_API_KEY environment variable."""

    DEFAULT_MESSAGE = (
        "API key is required but was not provided. "
        "Set the U1_API_KEY environment variable or pass --api-key explicitly."
    )
