"""Scheduling helpers for combined daily 09:30 Feishu broadcasts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
_REPORT_HOUR = 9
_REPORT_MINUTE = 30


@dataclass(frozen=True)
class ReportWindow:
    period: str
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class CombinedReportJob:
    due_at: datetime
    slot_id: str
    daily: ReportWindow
    weekly: ReportWindow
    monthly: ReportWindow
    weekly_is_previous_period: bool
    monthly_is_previous_period: bool


def jobs_due(now: datetime) -> list[CombinedReportJob]:
    current = _as_shanghai(now)
    if not _is_due_minute(current):
        return []
    due_at = _due_at_for_day(current)
    return [CombinedReportJob(
        due_at=due_at,
        slot_id=f"combined:{due_at.strftime('%Y%m%d%H%M')}",
        daily=_daily_window(current),
        weekly=_weekly_window(current, due_at),
        monthly=_monthly_window(current, due_at),
        weekly_is_previous_period=current.weekday() == 0,
        monthly_is_previous_period=current.day == 1,
    )]


def next_run_after(now: datetime) -> datetime:
    current = _as_shanghai(now)
    today_due = _due_at_for_day(current)
    if current < today_due:
        return today_due
    return today_due + timedelta(days=1)


def _daily_window(current: datetime) -> ReportWindow:
    today_start = _day_start(current)
    return ReportWindow(period="daily", start_at=today_start - timedelta(days=1), end_at=today_start)


def _weekly_window(current: datetime, due_at: datetime) -> ReportWindow:
    week_start = _day_start(current) - timedelta(days=current.weekday())
    if current.weekday() == 0:
        return ReportWindow(period="weekly", start_at=week_start - timedelta(days=7), end_at=week_start)
    return ReportWindow(period="weekly", start_at=week_start, end_at=due_at)


def _monthly_window(current: datetime, due_at: datetime) -> ReportWindow:
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if current.day == 1:
        previous_day = month_start - timedelta(days=1)
        previous_month_start = previous_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return ReportWindow(period="monthly", start_at=previous_month_start, end_at=month_start)
    return ReportWindow(period="monthly", start_at=month_start, end_at=due_at)


def _as_shanghai(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=_TZ_SHANGHAI)
    return value.astimezone(_TZ_SHANGHAI)


def _due_at_for_day(value: datetime) -> datetime:
    return value.replace(hour=_REPORT_HOUR, minute=_REPORT_MINUTE, second=0, microsecond=0)


def _day_start(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_due_minute(value: datetime) -> bool:
    return value.hour == _REPORT_HOUR and value.minute == _REPORT_MINUTE
