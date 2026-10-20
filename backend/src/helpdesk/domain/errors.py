class HelpdeskError(Exception):
    """Base exception for all helpdesk domain and application errors."""

    def __init__(
        self, message: str = "An internal error occurred", detail: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or message


class NotFoundError(HelpdeskError):
    """Raised when a requested resource is not found (404)."""


class ConflictError(HelpdeskError):
    """Raised when an update conflicts with the current version (409)."""


class ValidationError(HelpdeskError):
    """Raised when data validation fails (422)."""


class ConfigurationError(HelpdeskError):
    """Raised when application configuration is invalid."""


class ProviderError(HelpdeskError):
    """Raised when an external provider (LLM, Embedding, etc.) fails."""
