from __future__ import annotations

import csv
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

Period = Literal["daily", "weekly", "monthly"]
PeriodArg = Literal["daily", "weekly", "monthly", "all"]
Metric = Literal["tokens", "quota", "intensity"]
MetricArg = Literal["tokens", "quota", "intensity", "all"]
PERIODS: tuple[Period, ...] = ("daily", "weekly", "monthly")
METRICS: tuple[Metric, ...] = ("tokens", "quota", "intensity")
CSV_HEADER = ("rank", "name", "value")
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


class RankingService(Protocol):
    def build_natural_ranking(self, *, scope: str, ranking_type: str, limit: int) -> dict[str, Any]: ...


def export_csv_files(*, period: PeriodArg, metric: MetricArg, output_dir: Path, service: RankingService) -> list[Path]:
    periods = PERIODS if period == "all" else (period,)
    payloads = {period_name: _ranking_payload(period_name=period_name, service=service) for period_name in periods}
    return write_metric_files(periods=periods, metric=metric, output_dir=output_dir, payloads=payloads)


def write_metric_files(
    *,
    periods: tuple[Period, ...] | list[Period],
    metric: MetricArg,
    output_dir: Path,
    payloads: dict[str, dict[str, Any]],
) -> list[Path]:
    time_texts = {
        period_name: time_text_from_payload(payload, period=period_name)
        for period_name, payload in payloads.items()
    }
    for period_name, time_text in time_texts.items():
        write_time_files(output_dir=output_dir, time_text=time_text, name=f"{period_name}.time")
    fallback_period = "monthly" if "monthly" in time_texts else str(periods[-1])
    write_time_files(output_dir=output_dir, time_text=time_texts[fallback_period])
    metrics = METRICS if metric == "all" else (metric,)
    return [
        _write_metric_csv(period_name=period_name, metric=metric_name, output_dir=output_dir, payload=payloads[period_name])
        for metric_name in metrics
        for period_name in periods
    ]


def rows_from_payload(payload: dict[str, Any], *, metric: Metric) -> list[dict[str, str]]:
    items = sorted(
        payload.get("items", []),
        key=lambda item: (-metric_value(item, metric=metric), str(item.get("email") or ""), str(item.get("username") or "")),
    )
    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            {
                "rank": str(index),
                "name": str(item.get("display_name") or "").strip(),
                "value": compact_metric_value(item, metric=metric),
            }
        )
    return rows


def csv_text(rows: list[dict[str, str]]) -> str:
    stream = io.StringIO()
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow([row[key] for key in CSV_HEADER])
    return stream.getvalue()


def write_time_files(*, output_dir: Path, time_text: str, name: str = "time") -> list[Path]:
    paths = []
    for metric in METRICS:
        path = output_dir / metric / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(time_text, encoding="utf-8")
        paths.append(path)
    return paths


def time_text_from_payload(payload: dict[str, Any], *, period: str) -> str:
    window_start = int(payload["window_start"]) if payload.get("window_start") is not None else None
    window_end = int(payload["window_end"]) if payload.get("window_end") is not None else None
    generated_at = int(payload.get("generated_at") or 0)
    if window_start is not None and window_end is not None:
        return format_window(period=period, start_timestamp=window_start, end_timestamp=window_end)
    return default_period_window_text(period=period, generated_at=generated_at)


def format_window(*, period: str, start_timestamp: int, end_timestamp: int) -> str:
    start = datetime.fromtimestamp(start_timestamp, tz=_TZ_SHANGHAI)
    end = datetime.fromtimestamp(end_timestamp, tz=_TZ_SHANGHAI)
    fmt_hm = "%H:%M"
    if period == "daily":
        return f"{start.strftime('%Y/%m/%d')} {start.strftime(fmt_hm)} – {end.strftime(fmt_hm)} CST"
    if period == "weekly":
        return f"{start.strftime('%m/%d')} {start.strftime(fmt_hm)} – {end.strftime('%m/%d')} {end.strftime(fmt_hm)} CST"
    return f"{start.strftime('%Y/%m/%d')} {start.strftime(fmt_hm)} – {end.strftime('%m/%d')} {end.strftime(fmt_hm)} CST"


def default_period_window_text(*, period: str, generated_at: int) -> str:
    end = datetime.fromtimestamp(generated_at, tz=_TZ_SHANGHAI)
    fmt_hm = "%H:%M"
    fmt_md = "%m/%d"
    if period == "daily":
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        return f"{start.strftime('%Y/%m/%d')} {start.strftime(fmt_hm)} – {end.strftime(fmt_hm)} CST"
    if period == "weekly":
        start = (end - timedelta(days=end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return f"{start.strftime(fmt_md)} {start.strftime(fmt_hm)} – {end.strftime(fmt_md)} {end.strftime(fmt_hm)} CST"
    start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return f"{start.strftime('%Y/%m')}/01 {start.strftime(fmt_hm)} – {end.strftime(fmt_md)} {end.strftime(fmt_hm)} CST"


def compact_metric_value(item: dict[str, Any], *, metric: Metric) -> str:
    if metric == "tokens":
        return compact_count(int(item.get("used_tokens") or 0))
    if metric == "quota":
        return compact_count(int(item.get("window_used_quota") or 0))
    return compact_decimal(metric_value(item, metric="intensity"))


def metric_value(item: dict[str, Any], *, metric: Metric) -> float:
    used_tokens = int(item.get("used_tokens") or 0)
    window_used_quota = int(item.get("window_used_quota") or 0)
    if metric == "tokens":
        return float(used_tokens)
    if metric == "quota":
        return float(window_used_quota)
    return float(window_used_quota / used_tokens) if used_tokens else 0.0


def compact_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def compact_decimal(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.2f}"


def _ranking_payload(*, period_name: str, service: RankingService) -> dict[str, Any]:
    return service.build_natural_ranking(scope="whitelist", ranking_type=period_name, limit=sys.maxsize)


def _write_metric_csv(*, period_name: str, metric: Metric, output_dir: Path, payload: dict[str, Any]) -> Path:
    output_path = output_dir / metric / f"{period_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(csv_text(rows_from_payload(payload, metric=metric)), encoding="utf-8")
    return output_path
