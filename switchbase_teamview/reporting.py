"""Generate ranking JSON and poster outputs for explicit windows."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from scripts.poster import export, loaders
from scripts.poster.models import DataPolicy, Period, PosterRequest, RankingScope
from scripts.poster.render import build_figure
from switchbase_teamview.dashboard import DashboardService


@dataclass(frozen=True)
class ReportOutput:
    period: Period
    json_path: Path
    poster_path: Path


class ReportGenerator:
    def __init__(
        self,
        *,
        service: DashboardService | None = None,
        output_dir: Path | None = None,
        policy: DataPolicy | None = None,
        scope: RankingScope = "filtered",
        limit: int = 10,
    ) -> None:
        self.service = service or DashboardService.from_env()
        self.output_dir = output_dir or (Path.cwd() / "outputs")
        self.policy = policy or DataPolicy(scope=scope)
        self.scope = scope
        self.limit = limit

    def generate_and_write(
        self,
        *,
        period: Period,
        start_at: datetime,
        end_at: datetime,
        poster_path: Path | None = None,
    ) -> ReportOutput:
        payload = self.service.build_ranking(
            scope=self.scope,
            ranking_type=period,
            start_timestamp=int(start_at.timestamp()),
            end_timestamp=int(end_at.timestamp()),
            limit=self.limit,
        )
        return self.write_payload(period=period, payload=payload, poster_path=poster_path)

    def write_payload(
        self,
        *,
        period: Period,
        payload: dict[str, object],
        poster_path: Path | None = None,
    ) -> ReportOutput:
        poster_path = poster_path or (self.output_dir / f"{period}-poster.png")
        json_path = poster_path.parent / f"{period}.json"
        snapshot = loaders.load_snapshot_from_memory(payload, period=period, policy=self.policy, source=str(json_path))
        figure = build_figure(PosterRequest(snapshots=[snapshot]))
        self._write_atomic_outputs(payload=payload, figure=figure, json_path=json_path, poster_path=poster_path)
        return ReportOutput(period=period, json_path=json_path, poster_path=poster_path)

    def _write_atomic_outputs(
        self,
        *,
        payload: dict[str, object],
        figure,
        json_path: Path,
        poster_path: Path,
    ) -> None:
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
    def _tmp_path(path: Path) -> Path:
        suffix = "".join(path.suffixes) or ".tmp"
        stem = path.name[: -len(suffix)] if path.suffixes else path.name
        return path.with_name(f".{stem}.{uuid4().hex}.tmp{suffix}")
