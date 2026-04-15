"""Domain exceptions for the TeamView client."""

from __future__ import annotations


class TeamViewError(Exception):
    """Base error for TeamView client failures."""


class TeamViewHTTPError(TeamViewError):
    """Raised when the TeamView API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class TeamViewAPIError(TeamViewError):
    """Raised when the TeamView API responds with a domain-level failure."""


class TeamViewProtocolError(TeamViewError):
    """Raised when the TeamView API response does not match the documented schema."""
