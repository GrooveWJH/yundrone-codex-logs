"""HTTP client for the TeamView external API."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from switchbase_teamview.exceptions import (
    TeamViewAPIError,
    TeamViewHTTPError,
    TeamViewProtocolError,
)
from switchbase_teamview.models import APIEnvelope, LogsData, LogsResponse, UsageData, UsageResponse


class TeamViewClient:
    """Synchronous client for TeamView management endpoints."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://team.switchbase.vip",
        timeout: float = 10.0,
        auth_in_query: bool = False,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.auth_in_query = auth_in_query
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={} if auth_in_query else {"x-api-key": api_key},
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def __enter__(self) -> "TeamViewClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def get_usage(
        self,
        *,
        username: str | None = None,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
    ) -> UsageResponse:
        params = self._build_params(
            username=username,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        payload = self._request("GET", "/api/external/usage", params=params)
        return self._parse_response(payload, UsageData, UsageResponse)

    def get_logs(
        self,
        *,
        username: str | None = None,
        model_name: str | None = None,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
        page: int | None = None,
        size: int | None = None,
        log_type: int | None = None,
    ) -> LogsResponse:
        params = self._build_params(
            username=username,
            model_name=model_name,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            p=page,
            size=size,
            type=log_type,
        )
        payload = self._request("GET", "/api/external/logs", params=params)
        return self._parse_response(payload, LogsData, LogsResponse)

    def _request(self, method: str, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        effective_params = dict(params)
        if self.auth_in_query:
            effective_params["api_key"] = self.api_key

        try:
            response = self._client.request(method, path, params=effective_params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = exc.response.text.strip() or exc.response.reason_phrase
            raise TeamViewHTTPError(exc.response.status_code, message) from exc
        except httpx.HTTPError as exc:
            raise TeamViewHTTPError(-1, str(exc)) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TeamViewProtocolError("Response body is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise TeamViewProtocolError("Response body must be a JSON object")
        return payload

    @staticmethod
    def _build_params(**kwargs: Any) -> dict[str, Any]:
        return {key: value for key, value in kwargs.items() if value is not None}

    @staticmethod
    def _parse_response(
        payload: dict[str, Any],
        data_model: type[UsageData] | type[LogsData],
        response_model: type[UsageResponse] | type[LogsResponse],
    ) -> UsageResponse | LogsResponse:
        try:
            envelope = APIEnvelope[data_model].model_validate(payload)  # type: ignore[name-defined]
        except ValidationError as exc:
            raise TeamViewProtocolError(f"Response schema mismatch: {exc}") from exc

        if not envelope.success:
            raise TeamViewAPIError(envelope.message or "TeamView API reported failure")
        if envelope.data is None:
            raise TeamViewProtocolError("Response is missing data")
        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise TeamViewProtocolError(f"Response schema mismatch: {exc}") from exc


__all__ = [
    "TeamViewAPIError",
    "TeamViewClient",
    "TeamViewHTTPError",
    "TeamViewProtocolError",
]
