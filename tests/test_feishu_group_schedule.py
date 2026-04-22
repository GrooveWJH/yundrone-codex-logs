from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from switchbase_teamview.feishu_group_schedule import jobs_due, next_run_after


_TZ = ZoneInfo("Asia/Shanghai")


def test_jobs_due_before_0930_is_empty() -> None:
    assert jobs_due(datetime(2026, 4, 22, 9, 29, 59, tzinfo=_TZ)) == []


def test_jobs_due_after_0930_minute_is_empty() -> None:
    assert jobs_due(datetime(2026, 4, 22, 9, 31, 0, tzinfo=_TZ)) == []


def test_jobs_due_at_0930_emits_single_combined_job_for_normal_day() -> None:
    jobs = jobs_due(datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ))

    assert len(jobs) == 1
    job = jobs[0]
    assert job.slot_id == "combined:202604220930"
    assert job.daily.start_at == datetime(2026, 4, 21, 0, 0, 0, tzinfo=_TZ)
    assert job.daily.end_at == datetime(2026, 4, 22, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.start_at == datetime(2026, 4, 20, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.end_at == datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ)
    assert job.monthly.start_at == datetime(2026, 4, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.monthly.end_at == datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ)
    assert job.weekly_is_previous_period is False
    assert job.monthly_is_previous_period is False


def test_jobs_due_on_monday_uses_previous_full_week() -> None:
    jobs = jobs_due(datetime(2026, 4, 27, 9, 30, 0, tzinfo=_TZ))

    assert len(jobs) == 1
    job = jobs[0]
    assert job.weekly.start_at == datetime(2026, 4, 20, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.end_at == datetime(2026, 4, 27, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly_is_previous_period is True
    assert job.monthly_is_previous_period is False


def test_jobs_due_on_month_start_uses_previous_full_month() -> None:
    jobs = jobs_due(datetime(2026, 5, 1, 9, 30, 0, tzinfo=_TZ))

    assert len(jobs) == 1
    job = jobs[0]
    assert job.monthly.start_at == datetime(2026, 4, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.monthly.end_at == datetime(2026, 5, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.start_at == datetime(2026, 4, 27, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.end_at == datetime(2026, 5, 1, 9, 30, 0, tzinfo=_TZ)
    assert job.weekly_is_previous_period is False
    assert job.monthly_is_previous_period is True


def test_jobs_due_on_monday_month_start_uses_previous_week_and_month() -> None:
    jobs = jobs_due(datetime(2026, 6, 1, 9, 30, 0, tzinfo=_TZ))

    assert len(jobs) == 1
    job = jobs[0]
    assert job.weekly.start_at == datetime(2026, 5, 25, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly.end_at == datetime(2026, 6, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.monthly.start_at == datetime(2026, 5, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.monthly.end_at == datetime(2026, 6, 1, 0, 0, 0, tzinfo=_TZ)
    assert job.weekly_is_previous_period is True
    assert job.monthly_is_previous_period is True


def test_next_run_after_targets_next_0930_boundary() -> None:
    assert next_run_after(datetime(2026, 4, 22, 8, 0, 0, tzinfo=_TZ)) == datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ)
    assert next_run_after(datetime(2026, 4, 22, 9, 30, 0, tzinfo=_TZ)) == datetime(2026, 4, 23, 9, 30, 0, tzinfo=_TZ)
    assert next_run_after(datetime(2026, 4, 22, 11, 0, 0, tzinfo=_TZ)) == datetime(2026, 4, 23, 9, 30, 0, tzinfo=_TZ)
