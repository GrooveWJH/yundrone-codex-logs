from __future__ import annotations

import json
import os
import shutil
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from switchbase_teamview.rankings import RankingScope
from switchbase_teamview.typst_metrics import Period
from switchbase_teamview.typst_metrics import PERIODS
from switchbase_teamview.typst_posters import SOURCE_LIMIT, TypstPosterRenderer

_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class FeishuCachedReport:
    period: Period
    end_at: datetime
    json_path: Path
    poster_path: Path
    from_cache: bool


@dataclass(frozen=True)
class FeishuCachedTrioReport:
    end_at: datetime
    json_path: Path
    poster_path: Path
    from_cache: bool


@dataclass(frozen=True)
class FeishuCachedTrioPdfReport:
    end_at: datetime
    json_path: Path
    pdf_path: Path
    from_cache: bool


class FeishuReportCache:
    def __init__(
        self,
        *,
        renderer: TypstPosterRenderer | None = None,
        cache_dir: Path | None = None,
        now_provider=None,
        scope: RankingScope = "whitelist",
    ) -> None:
        self.cache_dir = cache_dir or (Path.cwd() / "outputs" / "feishu-cache")
        self.scope = scope
        self.renderer = renderer or TypstPosterRenderer()
        self.now_provider = now_provider or (lambda: datetime.now(_TZ_SHANGHAI))

    def resolve(self, *, period: Period, metric: str = "tokens") -> FeishuCachedReport:
        if metric != "tokens":
            raise ValueError("Feishu reports only support token posters.")
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self._minute_dir(period=period, end_at=end_at)
        self._purge_stale_period_cache(period=period, keep_dir=minute_dir)
        poster_path = minute_dir / f"{period}-poster.png"
        json_path = minute_dir / f"{period}.json"
        cache_inputs = self._cache_inputs()
        if poster_path.exists() and json_path.exists() and self._cache_inputs_match(json_path, cache_inputs):
            return FeishuCachedReport(period=period, end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=True)

        output = self.renderer.render_period(
            period=period,
            metric="tokens",
            start_at=self._period_start(period=period, end_at=end_at),
            end_at=end_at,
            output_path=self._tmp_path(poster_path),
            csv_dir=minute_dir / "metrics",
            scope=self.scope,
            limit=SOURCE_LIMIT,
        )
        self._write_atomic_json(payload={**output.payload, "_cache_inputs": cache_inputs}, json_path=json_path)
        os.replace(output.poster_path, poster_path)
        return FeishuCachedReport(period=period, end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=False)

    def resolve_trio(self, *, metric: str = "tokens") -> FeishuCachedTrioReport:
        if metric != "tokens":
            raise ValueError("Feishu reports only support token posters.")
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self._minute_dir(period="trio", end_at=end_at)
        self._purge_stale_period_cache(period="trio", keep_dir=minute_dir)
        poster_path = minute_dir / "trio-poster.png"
        json_path = minute_dir / "trio.json"
        cache_inputs = self._cache_inputs()
        if poster_path.exists() and json_path.exists() and self._cache_inputs_match(json_path, cache_inputs):
            return FeishuCachedTrioReport(end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=True)

        output = self.renderer.render_trio(
            metric="tokens",
            end_at=end_at,
            output_path=self._tmp_path(poster_path),
            csv_dir=minute_dir / "metrics",
            scope=self.scope,
            limit=SOURCE_LIMIT,
        )
        self._write_atomic_json(
            payload={
                "metric": output.metric,
                "generated_at": int(end_at.timestamp()),
                "window_texts": output.window_texts,
                "payloads": output.payloads,
                "periods": list(PERIODS),
                "_cache_inputs": cache_inputs,
            },
            json_path=json_path,
        )
        os.replace(output.poster_path, poster_path)
        return FeishuCachedTrioReport(end_at=end_at, json_path=json_path, poster_path=poster_path, from_cache=False)

    def resolve_trio_pdf(self, *, metric: str = "tokens") -> FeishuCachedTrioPdfReport:
        if metric != "tokens":
            raise ValueError("Feishu reports only support token posters.")
        end_at = self._minute_boundary(self.now_provider())
        minute_dir = self._minute_dir(period="trio-pdf", end_at=end_at)
        self._purge_stale_period_cache(period="trio-pdf", keep_dir=minute_dir)
        pdf_path = minute_dir / "trio-poster.pdf"
        json_path = minute_dir / "trio-pdf.json"
        cache_inputs = self._cache_inputs()
        if pdf_path.exists() and json_path.exists() and self._cache_inputs_match(json_path, cache_inputs):
            return FeishuCachedTrioPdfReport(end_at=end_at, json_path=json_path, pdf_path=pdf_path, from_cache=True)

        output = self.renderer.render_trio_pdf(
            metric="tokens",
            end_at=end_at,
            output_path=self._tmp_path(pdf_path),
            csv_dir=minute_dir / "metrics",
            scope=self.scope,
            limit=SOURCE_LIMIT,
        )
        self._write_atomic_json(
            payload={
                "metric": output.metric,
                "generated_at": int(end_at.timestamp()),
                "window_texts": output.window_texts,
                "payloads": output.payloads,
                "periods": list(PERIODS),
                "_cache_inputs": cache_inputs,
            },
            json_path=json_path,
        )
        os.replace(output.poster_path, pdf_path)
        return FeishuCachedTrioPdfReport(end_at=end_at, json_path=json_path, pdf_path=pdf_path, from_cache=False)

    def _purge_stale_period_cache(self, *, period: str, keep_dir: Path) -> None:
        period_dir = self.cache_dir / self.scope / "tokens" / period
        if not period_dir.exists():
            return
        for child in period_dir.iterdir():
            if child != keep_dir:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

    def _minute_dir(self, *, period: str, end_at: datetime) -> Path:
        return self.cache_dir / self.scope / "tokens" / period / end_at.strftime("%Y%m%d%H%M")

    def _write_atomic_json(self, *, payload: dict[str, object], json_path: Path) -> None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_tmp = self._tmp_path(json_path)
        try:
            json_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(json_tmp, json_path)
        finally:
            if json_tmp.exists():
                json_tmp.unlink()

    def _cache_inputs(self) -> dict[str, object]:
        return {"whitelist": self._whitelist_fingerprint()}

    @staticmethod
    def _cache_inputs_match(json_path: Path, expected: dict[str, object]) -> bool:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("_cache_inputs") == expected

    def _whitelist_fingerprint(self) -> dict[str, object]:
        path = self._whitelist_path()
        if path is None:
            return {"path": None}
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            return {"path": str(path), "exists": False}
        return {
            "path": str(path),
            "exists": True,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def _whitelist_path(self) -> Path | None:
        service = getattr(self.renderer, "service", None)
        store = getattr(service, "whitelist_store", None)
        path = getattr(store, "path", None)
        if isinstance(path, Path):
            return path
        if isinstance(path, str) and path.strip():
            return Path(path)
        return None

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
    def _period_start(*, period: Period, end_at: datetime) -> datetime:
        if period == "daily":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            return end_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=end_at.weekday())
        return end_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
