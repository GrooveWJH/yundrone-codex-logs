"""Scheduling helpers for periodic report generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo


Period = Literal["daily", "weekly", "monthly"]
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class ScheduledJob:
    period: Period
    start_at: datetime
    end_at: datetime


def startup_jobs(now: datetime) -> list[ScheduledJob]:
    current = _as_shanghai(now)
    if _is_boundary(current):
        return jobs_for_boundary(current)
    latest_boundary = _floor_half_hour(current)
    if latest_boundary == _day_start(current):
        return []
    return [ScheduledJob(period="daily", start_at=_day_start(current), end_at=latest_boundary)]


def next_boundary_after(now: datetime) -> datetime:
    current = _as_shanghai(now)
    if _is_boundary(current):
        return current + timedelta(minutes=30)
    return _floor_half_hour(current) + timedelta(minutes=30)


def jobs_for_boundary(boundary: datetime) -> list[ScheduledJob]:
    current = _as_shanghai(boundary)
    if not _is_boundary(current):
        raise ValueError(f"boundary must be aligned to a half-hour mark: {current.isoformat()}")
    if current.hour == 0 and current.minute == 0:
        return [
            ScheduledJob(period="weekly", start_at=_week_start(current), end_at=current),
            ScheduledJob(period="monthly", start_at=_month_start(current), end_at=current),
        ]
    return [ScheduledJob(period="daily", start_at=_day_start(current), end_at=current)]


def _as_shanghai(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=_TZ_SHANGHAI)
    return value.astimezone(_TZ_SHANGHAI)


def _floor_half_hour(value: datetime) -> datetime:
    minute = 30 if value.minute >= 30 else 0
    return value.replace(minute=minute, second=0, microsecond=0)


def _is_boundary(value: datetime) -> bool:
    return value.minute in {0, 30} and value.second == 0 and value.microsecond == 0


def _day_start(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start(value: datetime) -> datetime:
    return _day_start(value) - timedelta(days=value.weekday())


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
