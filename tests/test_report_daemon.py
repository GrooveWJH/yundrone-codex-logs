from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from switchbase_teamview.report_daemon import ReportDaemon


_TZ = ZoneInfo("Asia/Shanghai")


class _FakeGenerator:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.calls: list[tuple[str, datetime, datetime]] = []

    def generate_and_write(self, *, period: str, start_at: datetime, end_at: datetime):
        self.calls.append((period, start_at, end_at))
        return None


def test_report_daemon_startup_backfills_missing_weekly_and_monthly_outputs(tmp_path: Path) -> None:
    now = datetime(2026, 4, 16, 2, 21, tzinfo=_TZ)
    generator = _FakeGenerator(tmp_path / "outputs")

    daemon = ReportDaemon(generator=generator, now_provider=lambda: now, sleep_fn=lambda _: None)

    jobs = daemon._startup_jobs()

    assert [(job.period, job.start_at, job.end_at) for job in jobs] == [
        ("daily", datetime(2026, 4, 16, 0, 0, tzinfo=_TZ), datetime(2026, 4, 16, 2, 0, tzinfo=_TZ)),
        ("weekly", datetime(2026, 4, 13, 0, 0, tzinfo=_TZ), datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)),
        ("monthly", datetime(2026, 4, 1, 0, 0, tzinfo=_TZ), datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)),
    ]


def test_report_daemon_startup_does_not_duplicate_existing_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "weekly.json").write_text("{}", encoding="utf-8")
    (output_dir / "weekly-poster.png").write_bytes(b"png")
    (output_dir / "monthly.json").write_text("{}", encoding="utf-8")
    (output_dir / "monthly-poster.png").write_bytes(b"png")

    now = datetime(2026, 4, 16, 2, 21, tzinfo=_TZ)
    generator = _FakeGenerator(output_dir)
    daemon = ReportDaemon(generator=generator, now_provider=lambda: now, sleep_fn=lambda _: None)

    jobs = daemon._startup_jobs()

    assert [(job.period, job.start_at, job.end_at) for job in jobs] == [
        ("daily", datetime(2026, 4, 16, 0, 0, tzinfo=_TZ), datetime(2026, 4, 16, 2, 0, tzinfo=_TZ))
    ]
