"""Shared exceptions for sn-image-base."""

from __future__ import annotations


class U1BaseError(Exception):
    """Base exception for sn-image-base."""

    DEFAULT_MESSAGE = "An error occurred in the sn-image-base skill."

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = self.DEFAULT_MESSAGE
        super().__init__(message)


class BadConfigurationError(U1BaseError):
    """Raised when the configuration is invalid."""

    DEFAULT_MESSAGE = "The configuration is invalid."


class MissingApiKeyError(BadConfigurationError):
    """Raised when API key is not provided via CLI argument or environment variable."""

    DEFAULT_MESSAGE = (
        "API key is required but was not provided. "
        "Set the SN_API_KEY environment variable or pass --api-key explicitly."
    )


class InvalidBaseUrlError(BadConfigurationError):
    """Raised when base URL is not provided via CLI argument or environment variable."""

    DEFAULT_MESSAGE = (
        "Base URL is required but was not provided. "
        "Set the SN_IMAGE_GEN_BASE_URL environment variable or pass --base-url explicitly."
    )
