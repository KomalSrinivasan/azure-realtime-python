"""Custom error types for Azure OpenAI Realtime API."""


class RealtimeError(Exception):
    """Base error for all realtime API errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class AuthenticationError(RealtimeError):
    """Authentication failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "AUTHENTICATION_ERROR")


class ConnectionError(RealtimeError):
    """Connection failed or was lost."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONNECTION_ERROR")


class NegotiationError(RealtimeError):
    """SDP negotiation failed."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message, "NEGOTIATION_ERROR")
        self.status = status
