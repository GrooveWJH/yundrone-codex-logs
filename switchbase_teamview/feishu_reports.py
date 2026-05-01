from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from scripts.poster import export, loaders
from scripts.poster.models import DataPolicy, PosterConfig, PosterRequest, RankingScope, ReportMetric
from scripts.poster.render import build_figure
from switchbase_teamview.reporting import ReportGenerator, ReportOutput


Period = str
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
_FEISHU_TOP_N = 10
_SOURCE_LIMIT = 10_000
_OVERVIEW_PERIODS = ("daily", "weekly", "monthly")
_METRIC_TITLES: dict[ReportMetric, str] = {
    "tokens": "Codex token",
    "quota": "Codex quota",
    "intensity": "Codex intensity",
}


@dataclass(frozen=True)
class FeishuCachedReport:
    period: str
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
        self.policy = DataPolicy(scope=scope, top_n=_FEISHU_TOP_N)
        self.report_generator = report_generator or ReportGenerator(
            output_dir=self.cache_dir,
            scope=scope,
            limit=_FEISHU_TOP_N,
            policy=self.policy,
        )
        self.now_provider = now_provider or (lambda: datetime.now(_TZ_SHANGHAI))

    def resolve(self, *, period: str, metric: ReportMetric = "tokens") -> FeishuCachedReport:
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self._minute_dir(metric=metric, period=period, end_at=end_at)
        self._purge_stale_period_cache(metric=metric, period=period, keep_dir=minute_dir)
        poster_path = minute_dir / f"{period}-poster.png"
        json_path = minute_dir / f"{period}.json"
        if poster_path.exists() and json_path.exists():
            return FeishuCachedReport(period=period, end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=True)

        if metric == "tokens":
            output = self.report_generator.generate_and_write(
                period=period,
                start_at=self._period_start(period=period, end_at=end_at),
                end_at=end_at,
                poster_path=poster_path,
            )
            return self._cached_report(period=period, end_at=end_at, output=output)
        payload = self._payload_for_period(period=period, end_at=end_at)
        self._write_metric_report(period=period, metric=metric, payload=payload, json_path=json_path, poster_path=poster_path)
        return FeishuCachedReport(period=period, end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=False)

    def resolve_overview(self, *, metric: ReportMetric = "tokens") -> FeishuCachedReport:
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self._minute_dir(metric=metric, period="overview", end_at=end_at)
        self._purge_stale_period_cache(metric=metric, period="overview", keep_dir=minute_dir)
        poster_path = minute_dir / "overview-poster.png"
        json_path = minute_dir / "overview.json"
        if poster_path.exists() and json_path.exists():
            return FeishuCachedReport(period="overview", end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=True)

        policy = self._policy_for_metric(metric)
        payloads = {
            period: self._ranked_payload(
                period=period,
                metric=metric,
                payload=self._payload_for_period(period=period, end_at=end_at),
                source=f"feishu-overview:{metric}:{period}",
            )
            for period in _OVERVIEW_PERIODS
        }
        snapshots = [
            loaders.load_snapshot_from_memory(payloads[period], period=period, policy=policy, source=f"feishu-overview:{metric}:{period}")
            for period in _OVERVIEW_PERIODS
        ]
        figure = build_figure(PosterRequest(snapshots=snapshots, config=self._poster_config(metric)))
        overview_payload = {"generated_at": int(end_at.timestamp()), "scope": self.scope, "items": payloads}
        self._write_atomic(payload=overview_payload, json_path=json_path, poster_path=poster_path, figure=figure)
        return FeishuCachedReport(period="overview", end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=False)

    def _payload_for_period(self, *, period: str, end_at: datetime) -> dict[str, object]:
        start_at = self._period_start(period=period, end_at=end_at)
        return self.report_generator.service.build_ranking(
            scope=self.scope,
            ranking_type=period,
            start_timestamp=int(start_at.timestamp()),
            end_timestamp=int(end_at.timestamp()),
            limit=_SOURCE_LIMIT,
        )

    def _write_metric_report(self, *, period: str, metric: ReportMetric, payload: dict[str, object], json_path: Path, poster_path: Path) -> None:
        payload = self._ranked_payload(period=period, metric=metric, payload=payload, source=str(json_path))
        snapshot = loaders.load_snapshot_from_memory(payload, period=period, policy=self._policy_for_metric(metric), source=str(json_path))
        figure = build_figure(PosterRequest(snapshots=[snapshot], config=self._poster_config(metric)))
        self._write_atomic(payload=payload, json_path=json_path, poster_path=poster_path, figure=figure)

    def _ranked_payload(self, *, period: str, metric: ReportMetric, payload: dict[str, object], source: str) -> dict[str, object]:
        snapshot = loaders.load_snapshot_from_memory(payload, period=period, policy=self._policy_for_metric(metric), source=source)
        return {
            "ranking_type": period,
            "generated_at": payload.get("generated_at"),
            "scope": self.scope,
            "items": [item.model_dump() for item in snapshot.items],
        }

    def _purge_stale_period_cache(self, *, metric: ReportMetric, period: str, keep_dir: Path) -> None:
        period_dir = self.cache_dir / self.scope / metric / period
        if not period_dir.exists():
            return
        for child in period_dir.iterdir():
            if child != keep_dir:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

    def _policy_for_metric(self, metric: ReportMetric) -> DataPolicy:
        return DataPolicy(scope=self.scope, top_n=_FEISHU_TOP_N, metric=metric)

    @staticmethod
    def _poster_config(metric: ReportMetric) -> PosterConfig:
        return PosterConfig(main_title=_METRIC_TITLES[metric], value_format=metric)

    def _minute_dir(self, *, metric: ReportMetric, period: str, end_at: datetime) -> Path:
        return self.cache_dir / self.scope / metric / period / end_at.strftime("%Y%m%d%H%M")

    def _write_atomic(self, *, payload: dict[str, object], json_path: Path, poster_path: Path, figure) -> None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_tmp = self._tmp_path(json_path)
        poster_tmp = self._tmp_path(poster_path)
        try:
            json_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            export.save_png(figure, poster_tmp)
            os.replace(json_tmp, json_path)
            os.replace(poster_tmp, poster_path)
        finally:
            for path in (json_tmp, poster_tmp):
                if path.exists():
                    path.unlink()

    @staticmethod
    def _cached_report(*, period: str, end_at: datetime, output: ReportOutput) -> FeishuCachedReport:
        return FeishuCachedReport(period=period, end_at=end_at, json_path=output.json_path, poster_path=output.poster_path, from_cache=False)

    @staticmethod
    def _tmp_path(path: Path) -> Path:
        suffix = "".join(path.suffixes) or ".tmp"
        stem = path.name[: -len(suffix)] if path.suffixes else path.name
        return path.with_name(f".{stem}.{uuid4().hex}.tmp{suffix}")

    @staticmethod
    def _minute_boundary(value: datetime) -> datetime:
        current = value if value.tzinfo is not None else value.replace(tzinfo=_TZ_SHANGHAI)
        return current.astimezone(_TZ_SHANGHAI).replace(second=0, microsecond=0)

    @staticmethod
    def _period_start(*, period: str, end_at: datetime) -> datetime:
        if period == "daily":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=end_at.weekday())
        return end_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
