"""Timed Feishu reporter for the daily 09:30 combined ranking broadcast."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.poster import export, loaders
from scripts.poster.models import DataPolicy, PosterRequest
from scripts.poster.render import build_figure
from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.feishu_group_schedule import CombinedReportJob, jobs_due, next_run_after


_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
_TOP_N = 10
_TITLE = "Codex token 用量播报"


@dataclass
class BroadcastStateStore:
    path: Path

    def last_sent_slot(self) -> str | None:
        return self._load().get("combined")

    def mark_sent(self, *, slot_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"combined": slot_id}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


class FeishuGroupReporter:
    def __init__(
        self,
        *,
        feishu_client,
        chat_id: str,
        dashboard_service: DashboardService | None = None,
        output_dir: Path | None = None,
        state_store: BroadcastStateStore | None = None,
        now_provider: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.feishu_client = feishu_client
        self.chat_id = chat_id
        self.dashboard_service = dashboard_service or DashboardService.from_env()
        self.output_dir = output_dir or (Path.cwd() / "outputs")
        self.state_store = state_store or BroadcastStateStore(self.output_dir / "scheduled-feishu" / "state.json")
        self.now_provider = now_provider or (lambda: datetime.now(_TZ_SHANGHAI))
        self.sleep_fn = sleep_fn or time.sleep
        self.policy = DataPolicy(scope="all-members", top_n=_TOP_N)

    def run_forever(self) -> None:
        while True:
            self.run_pending()
            now = self.now_provider().astimezone(_TZ_SHANGHAI)
            sleep_seconds = max((next_run_after(now) - now).total_seconds(), 0.0)
            if sleep_seconds:
                self.sleep_fn(sleep_seconds)

    def run_pending(self) -> None:
        for job in jobs_due(self.now_provider().astimezone(_TZ_SHANGHAI)):
            self._run_job(job)

    def _run_job(self, job: CombinedReportJob) -> None:
        if self.state_store.last_sent_slot() == job.slot_id:
            self._log(job=job, outcome="already-sent")
            return
        try:
            poster_path = self._build_combined_poster(job)
            self.feishu_client.send_post_with_image_by_chat_id(
                chat_id=self.chat_id,
                title=_TITLE,
                lines=self._message_lines(job),
                image_path=poster_path,
            )
        except Exception as exc:  # pragma: no cover
            self._log(job=job, outcome="failed", error=exc)
            return
        self.state_store.mark_sent(slot_id=job.slot_id)
        self._log(job=job, outcome="sent")

    def _build_combined_poster(self, job: CombinedReportJob) -> Path:
        snapshots = [self._snapshot_for_window(job.daily), self._snapshot_for_window(job.weekly), self._snapshot_for_window(job.monthly)]
        figure = build_figure(PosterRequest(snapshots=snapshots))
        poster_path = self.output_dir / "scheduled-feishu" / job.due_at.strftime("%Y%m%d%H%M") / "combined-poster.png"
        return export.save_png(figure, poster_path)

    def _snapshot_for_window(self, window) -> object:
        payload = self.dashboard_service.build_ranking(
            scope="all-members",
            ranking_type=window.period,
            start_timestamp=int(window.start_at.timestamp()),
            end_timestamp=int(window.end_at.timestamp()),
            limit=_TOP_N,
        )
        return loaders.load_snapshot_from_memory(
            payload,
            period=window.period,
            policy=self.policy,
            source=f"scheduled:{window.period}:{window.start_at.isoformat()}:{window.end_at.isoformat()}",
        )

    @staticmethod
    def _message_lines(job: CombinedReportJob) -> list[str]:
        lines = [
            f"播报时间：{job.due_at.strftime('%Y-%m-%d %H:%M CST')}",
            "统计口径：昨日 / 周统计 / 月统计",
            _summary_line(job),
            "展示范围：全员榜，最多显示前 10 位。",
        ]
        return lines

    @staticmethod
    def _log(*, job: CombinedReportJob, outcome: str, error: Exception | None = None) -> None:
        suffix = f" error={type(error).__name__}: {error}" if error else ""
        print(
            f"[feishu-group-reporter] slot={job.slot_id} due_at={job.due_at.isoformat()} outcome={outcome}{suffix}",
            flush=True,
        )


def _summary_line(job: CombinedReportJob) -> str:
    if job.weekly_is_previous_period and job.monthly_is_previous_period:
        return "周统计为 <上周总览>，月统计为 <上月总览>。"
    if job.weekly_is_previous_period:
        return "周统计为 <上周总览>，月统计截止到今日 09:30。"
    if job.monthly_is_previous_period:
        return "周统计截止到今日 09:30，月统计为 <上月总览>。"
    return "周、月统计均截止到今日 09:30。"
