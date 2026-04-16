from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from switchbase_teamview import report_schedule


_TZ = ZoneInfo("Asia/Shanghai")


def test_startup_jobs_backfill_latest_closed_daily_half_hour() -> None:
    now = datetime(2026, 4, 15, 23, 58, tzinfo=_TZ)

    jobs = report_schedule.startup_jobs(now)

    assert len(jobs) == 1
    assert jobs[0].period == "daily"
    assert jobs[0].start_at == datetime(2026, 4, 15, 0, 0, tzinfo=_TZ)
    assert jobs[0].end_at == datetime(2026, 4, 15, 23, 30, tzinfo=_TZ)


def test_startup_jobs_skip_daily_when_latest_closed_boundary_is_midnight() -> None:
    now = datetime(2026, 4, 16, 0, 5, tzinfo=_TZ)

    assert report_schedule.startup_jobs(now) == []


def test_startup_jobs_run_scheduled_tick_when_started_exactly_on_boundary() -> None:
    now = datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)

    jobs = report_schedule.startup_jobs(now)

    assert [job.period for job in jobs] == ["weekly", "monthly"]
    assert jobs[0].start_at == datetime(2026, 4, 13, 0, 0, tzinfo=_TZ)
    assert jobs[0].end_at == now
    assert jobs[1].start_at == datetime(2026, 4, 1, 0, 0, tzinfo=_TZ)
    assert jobs[1].end_at == now


def test_jobs_for_boundary_only_runs_weekly_and_monthly_at_midnight() -> None:
    boundary = datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)

    jobs = report_schedule.jobs_for_boundary(boundary)

    assert [job.period for job in jobs] == ["weekly", "monthly"]


def test_jobs_for_boundary_runs_daily_on_half_hour_points() -> None:
    half_hour = datetime(2026, 4, 16, 0, 30, tzinfo=_TZ)
    hour = datetime(2026, 4, 16, 1, 0, tzinfo=_TZ)

    half_hour_jobs = report_schedule.jobs_for_boundary(half_hour)
    hour_jobs = report_schedule.jobs_for_boundary(hour)

    assert [(job.period, job.start_at, job.end_at) for job in half_hour_jobs] == [
        ("daily", datetime(2026, 4, 16, 0, 0, tzinfo=_TZ), half_hour)
    ]
    assert [(job.period, job.start_at, job.end_at) for job in hour_jobs] == [
        ("daily", datetime(2026, 4, 16, 0, 0, tzinfo=_TZ), hour)
    ]
