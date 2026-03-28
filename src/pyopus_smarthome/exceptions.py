class OpusError(Exception):
    """Base exception for OPUS client."""


class OpusConnectionError(OpusError):
    """Cannot connect to gateway."""


class OpusAuthError(OpusError):
    """Authentication failed."""


class OpusApiError(OpusError):
    """API returned an error response."""

    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")
