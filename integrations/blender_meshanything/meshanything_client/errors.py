from __future__ import annotations


class MeshAnythingAPIError(RuntimeError):
    """Raised when the Space API returns an error or an unexpected response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        detail: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.detail = detail
