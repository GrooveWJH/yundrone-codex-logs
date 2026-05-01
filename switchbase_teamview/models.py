"""Pydantic models for the TeamView external API."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class TeamViewModel(BaseModel):
    """Base configuration shared across TeamView protocol models."""

    model_config = ConfigDict(extra="ignore")


class UsageMember(TeamViewModel):
    newapi_user_id: int
    username: str
    display_name: str
    email: str
    role: str
    quota: int
    used_quota: int
    window_used_quota: int = 0
    request_count: int
    used_tokens: int
    user_group: str
    synced_at: int | None


class UsageData(TeamViewModel):
    total_members: int
    total_quota: int
    total_used_quota: int
    total_window_used_quota: int = 0
    total_used_tokens: int
    total_request_count: int
    members: list[UsageMember]
    queried_at: int


class UsageResponse(TeamViewModel):
    success: bool
    data: UsageData


class LogItem(TeamViewModel):
    id: int
    time: int
    username: str
    model: str
    token_name: str | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    quota: int
    quota_usd: str
    use_time_seconds: float | None = None
    is_stream: bool | int | None = None
    request_id: str | None = None


class LogsData(TeamViewModel):
    items: list[LogItem]


class LogsResponse(TeamViewModel):
    success: bool
    data: LogsData


T = TypeVar("T", bound=BaseModel)


class APIEnvelope(TeamViewModel, Generic[T]):
    success: bool
    data: T | None = None
    message: str | None = None
