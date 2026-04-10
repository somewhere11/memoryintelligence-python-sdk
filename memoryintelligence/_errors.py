"""Memory Intelligence SDK - Error types.

Complete error hierarchy for programmatic exception handling.
Every error has a `code` string attribute that matches the API error envelope.
"""

from dataclasses import dataclass, field


class MIError(Exception):
    """Base. All SDK errors inherit from this."""
    code: str = "mi_error"

    def __init__(self, message: str = "Memory Intelligence error"):
        super().__init__(message)


class ConfigurationError(MIError):
    """Invalid SDK configuration (wrong key format, live key + localhost, etc.)"""
    code = "configuration_error"

    def __init__(self, message: str = "Invalid configuration"):
        super().__init__(message)


class LicenseError(MIError):
    """License invalid, expired beyond grace period, or revoked."""
    code = "license_error"
    days_expired: int = 0  # 0 if not expired, N if in warning period
    renew_url: str = "https://memoryintelligence.io/billing"

    def __init__(
        self,
        message: str = "License error",
        days_expired: int = 0,
        renew_url: str = "https://memoryintelligence.io/billing",
    ):
        super().__init__(message)
        self.days_expired = days_expired
        self.renew_url = renew_url


class AuthenticationError(MIError):
    """API key rejected by server."""
    code = "authentication_error"

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class RateLimitError(MIError):
    """Rate limit exceeded."""
    code = "rate_limit"
    retry_after: int = 60  # seconds, from Retry-After header

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
    ):
        super().__init__(message)
        self.retry_after = retry_after


class ScopeViolationError(MIError):
    """Cross-scope access attempt or missing scope_id."""
    code = "scope_violation"

    def __init__(self, message: str = "Scope violation"):
        super().__init__(message)


class PIIViolationError(MIError):
    """Content rejected due to PII policy."""
    code = "pii_violation"
    detected_types: list = field(default_factory=list)

    def __init__(
        self,
        message: str = "PII violation detected",
        detected_types: list | None = None,
    ):
        super().__init__(message)
        self.detected_types = detected_types or []


class GovernanceError(MIError):
    """Operation violates governance policy."""
    code = "governance_error"

    def __init__(self, message: str = "Governance policy violation"):
        super().__init__(message)


class ConflictError(MIError):
    """Resource conflict (e.g., duplicate UMO)."""
    code = "conflict"

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message)


class PaymentRequiredError(MIError):
    """Payment required - license upgrade needed."""
    code = "payment_required"

    def __init__(self, message: str = "License upgrade required"):
        super().__init__(message)


class EncryptionError(MIError):
    """Encryption/decryption failure."""
    code = "encryption_error"

    def __init__(self, message: str = "Encryption error"):
        super().__init__(message)


class PermissionError(MIError):
    """Permission denied."""
    code = "permission_error"

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class ProvenanceError(MIError):
    """Provenance verification failed."""
    code = "provenance_error"

    def __init__(self, message: str = "Provenance verification failed"):
        super().__init__(message)


class ValidationError(MIError):
    """Request payload failed server-side validation."""
    code = "validation_error"
    field: str = ""  # which field failed

    def __init__(
        self,
        message: str = "Validation error",
        field: str = "",
    ):
        super().__init__(message)
        self.field = field


class PaymentRequiredError(MIError):
    """Payment required - license upgrade needed."""
    code = "payment_required"

    def __init__(self, message: str = "License upgrade required"):
        super().__init__(message)


class PermissionError(MIError):
    """Permission denied for this operation."""
    code = "permission_error"

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message)


class NotFoundError(MIError):
    """Resource not found."""
    code = "not_found"

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ConflictError(MIError):
    """Resource conflict (e.g., duplicate UMO)."""
    code = "conflict"

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message)


class ServerError(MIError):
    """Unrecoverable server-side error."""
    code = "server_error"
    request_id: str = ""  # from X-MI-Request-ID response header

    def __init__(
        self,
        message: str = "Server error",
        request_id: str = "",
    ):
        super().__init__(message)
        self.request_id = request_id


class ConnectionError(MIError):
    """Could not reach the API."""
    code = "connection_error"

    def __init__(self, message: str = "Could not connect to API"):
        super().__init__(message)


class TimeoutError(MIError):
    """Request timed out."""
    code = "timeout"

    def __init__(self, message: str = "Request timed out"):
        super().__init__(message)


# HTTP status code to exception mapping
# Used by _http.py to raise appropriate exceptions
HTTP_STATUS_EXCEPTIONS: dict[int, type[MIError]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: PaymentRequiredError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
    451: PIIViolationError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
    504: ServerError,
}


def get_exception_for_status(status_code: int) -> type[MIError]:
    """Get the appropriate exception class for an HTTP status code."""
    return HTTP_STATUS_EXCEPTIONS.get(status_code, ServerError)
