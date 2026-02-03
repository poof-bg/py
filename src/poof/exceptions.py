"""Custom exceptions for the Poof SDK."""

from __future__ import annotations


class PoofError(Exception):
    """Base exception for all Poof API errors.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code.
        details: Additional details or troubleshooting steps.
        request_id: Unique request ID for support.
        status_code: HTTP status code.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: str | None = None,
        request_id: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details
        self.request_id = request_id
        self.status_code = status_code
        super().__init__(message)

    def __repr__(self) -> str:
        parts = [f"PoofError({self.message!r}"]
        if self.code:
            parts.append(f", code={self.code!r}")
        if self.status_code:
            parts.append(f", status_code={self.status_code}")
        if self.request_id:
            parts.append(f", request_id={self.request_id!r}")
        parts.append(")")
        return "".join(parts)


class AuthError(PoofError):
    """Raised when authentication fails (401).

    This typically means the API key is invalid, missing, or revoked.
    """

    pass


class PaymentRequiredError(PoofError):
    """Raised when the account has insufficient credits (402).

    Upgrade your plan or wait for the next billing cycle.
    """

    pass


class PermissionDeniedError(PoofError):
    """Raised when access is forbidden (403).

    The account may be suspended or the API key lacks permissions.
    """

    pass


class RateLimitError(PoofError):
    """Raised when rate limit is exceeded (429).

    Implement exponential backoff and retry.
    """

    pass


class ValidationError(PoofError):
    """Raised when request validation fails (400).

    Check the parameters and image format.
    """

    pass


class ServerError(PoofError):
    """Raised when a server-side error occurs (5xx).

    Please try again later.
    """

    pass
