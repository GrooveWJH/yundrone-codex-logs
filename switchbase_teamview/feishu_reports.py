from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from scripts.poster.models import DataPolicy
from scripts.poster.models import RankingScope
from switchbase_teamview.reporting import ReportGenerator, ReportOutput


Period = Literal["daily", "weekly", "monthly"]
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
_FEISHU_TOP_N = 7


@dataclass(frozen=True)
class FeishuCachedReport:
    period: Period
    end_at: datetime
    json_path: Path
    poster_path: Path
    from_cache: bool


class FeishuReportCache:
    def __init__(
        self,
        *,
        report_generator: ReportGenerator | None = None,
        cache_dir: Path | None = None,
        now_provider=None,
        scope: RankingScope = "all-members",
    ) -> None:
        self.cache_dir = cache_dir or (Path.cwd() / "outputs" / "feishu-cache")
        self.scope = scope
        self.report_generator = report_generator or ReportGenerator(
            output_dir=self.cache_dir,
            scope=scope,
            limit=_FEISHU_TOP_N,
            policy=DataPolicy(scope=scope, top_n=_FEISHU_TOP_N),
        )
        self.now_provider = now_provider or (lambda: datetime.now(_TZ_SHANGHAI))

    def resolve(self, *, period: Period) -> FeishuCachedReport:
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self.cache_dir / self.scope / period / end_at.strftime("%Y%m%d%H%M")
        self._purge_stale_period_cache(period=period, keep_dir=minute_dir)
        poster_path = minute_dir / f"{period}-poster.png"
        json_path = minute_dir / f"{period}.json"
        if poster_path.exists() and json_path.exists():
            return FeishuCachedReport(
                period=period,
                end_at=end_at,
                json_path=json_path,
                poster_path=poster_path,
                from_cache=True,
            )

        output = self.report_generator.generate_and_write(
            period=period,
            start_at=self._period_start(period=period, end_at=end_at),
            end_at=end_at,
            poster_path=poster_path,
        )
        return self._cached_report(period=period, end_at=end_at, output=output)

    def _purge_stale_period_cache(self, *, period: Period, keep_dir: Path) -> None:
        period_dir = self.cache_dir / self.scope / period
        if not period_dir.exists():
            return
        for child in period_dir.iterdir():
            if child != keep_dir:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

    @staticmethod
    def _cached_report(*, period: Period, end_at: datetime, output: ReportOutput) -> FeishuCachedReport:
        return FeishuCachedReport(
            period=period,
            end_at=end_at,
            json_path=output.json_path,
            poster_path=output.poster_path,
            from_cache=False,
        )

    @staticmethod
    def _minute_boundary(value: datetime) -> datetime:
        current = value if value.tzinfo is not None else value.replace(tzinfo=_TZ_SHANGHAI)
        return current.astimezone(_TZ_SHANGHAI).replace(second=0, microsecond=0)

    @staticmethod
    def _period_start(*, period: Period, end_at: datetime) -> datetime:
        if period == "daily":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=end_at.weekday())
        return end_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
