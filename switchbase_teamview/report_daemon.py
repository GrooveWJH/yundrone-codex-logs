"""Long-running daemon for periodic report generation."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.poster.fonts import prime_font_cache
from switchbase_teamview.report_schedule import Period, ScheduledJob, jobs_for_boundary, next_boundary_after, startup_jobs
from switchbase_teamview.reporting import ReportGenerator

_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


class ReportDaemon:
    def __init__(
        self,
        *,
        generator: ReportGenerator | None = None,
        now_provider: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        _prime_poster_fonts()
        self.generator = generator or ReportGenerator()
        self.now_provider = now_provider or (lambda: datetime.now(_TZ_SHANGHAI))
        self.sleep_fn = sleep_fn or time.sleep

    def run_forever(self) -> None:
        self._run_jobs(self._startup_jobs())
        while True:
            now = self.now_provider().astimezone(_TZ_SHANGHAI)
            boundary = next_boundary_after(now)
            sleep_seconds = max((boundary - now).total_seconds(), 0.0)
            if sleep_seconds:
                self.sleep_fn(sleep_seconds)
            self._run_jobs(jobs_for_boundary(boundary))

    def _run_jobs(self, jobs: list[ScheduledJob]) -> None:
        for job in jobs:
            self._run_job(job)

    def _run_job(self, job: ScheduledJob) -> None:
        try:
            result = self.generator.generate_and_write(period=job.period, start_at=job.start_at, end_at=job.end_at)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            print(
                f"[report-daemon] failed period={job.period} start={job.start_at.isoformat()} "
                f"end={job.end_at.isoformat()} error={exc}",
                flush=True,
            )
            return
        print(
            f"[report-daemon] updated period={job.period} json={result.json_path} poster={result.poster_path}",
            flush=True,
        )

    def _startup_jobs(self) -> list[ScheduledJob]:
        now = self.now_provider().astimezone(_TZ_SHANGHAI)
        jobs_by_period = {job.period: job for job in startup_jobs(now)}
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for job in jobs_for_boundary(midnight):
            if job.period in {"weekly", "monthly"} and not self._output_exists(job.period):
                jobs_by_period.setdefault(job.period, job)
        return list(jobs_by_period.values())

    def _output_exists(self, period: Period) -> bool:
        output_dir = Path(getattr(self.generator, "output_dir", Path.cwd() / "outputs"))
        return (output_dir / f"{period}.json").is_file() and (output_dir / f"{period}-poster.png").is_file()


def main() -> None:
    daemon = ReportDaemon()
    print("[report-daemon] started timezone=Asia/Shanghai", flush=True)
    daemon.run_forever()


def _prime_poster_fonts() -> None:
    prime_font_cache()
