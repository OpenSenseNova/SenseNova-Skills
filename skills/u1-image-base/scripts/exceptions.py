"""Shared exceptions for u1-image-base."""


class MissingApiKeyError(Exception):
    """Raised when API key is not provided via CLI argument or U1_API_KEY environment variable."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize MissingApiKeyError with an optional custom message.

        Args:
            message: Custom error message. Defaults to None, which uses
                a standard message about U1_API_KEY and --api-key.
        """
        if message is None:
            message = (
                "API key is required but was not provided. "
                "Set the U1_API_KEY environment variable or pass --api-key explicitly."
            )
        super().__init__(message)
