from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from switchbase_teamview.feishu_reports import FeishuReportCache
from switchbase_teamview.typst_posters import TypstPosterOutput
from switchbase_teamview.typst_posters import TypstTrioPosterOutput

_TZ = ZoneInfo("Asia/Shanghai")


def test_feishu_report_cache_reuses_same_minute_typst_poster(tmp_path: Path) -> None:
    renderer = FakeRenderer(tmp_path)
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve(period="daily")
    second = cache.resolve(period="daily")

    assert first.poster_path == second.poster_path
    assert first.from_cache is False
    assert second.from_cache is True
    assert len(renderer.calls) == 1
    assert renderer.calls[0]["start_at"] == datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)
    assert renderer.calls[0]["end_at"] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)
    assert renderer.calls[0]["scope"] == "whitelist"
    assert first.poster_path == tmp_path / "feishu-cache" / "whitelist" / "tokens" / "daily" / "202604161223" / "daily-poster.png"
    assert first.json_path.read_text(encoding="utf-8")


def test_feishu_report_cache_expires_at_next_minute_and_purges_old_dir(tmp_path: Path) -> None:
    current = datetime(2026, 4, 16, 12, 23, 59, tzinfo=_TZ)
    renderer = FakeRenderer(tmp_path)
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: current,
    )

    first = cache.resolve(period="daily")
    current = datetime(2026, 4, 16, 12, 24, 0, tzinfo=_TZ)
    second = cache.resolve(period="daily")

    assert len(renderer.calls) == 2
    assert first.poster_path != second.poster_path
    assert not first.poster_path.exists()
    assert renderer.calls[1]["end_at"] == datetime(2026, 4, 16, 12, 24, tzinfo=_TZ)


def test_feishu_report_cache_uses_natural_weekly_and_monthly_windows(tmp_path: Path) -> None:
    renderer = FakeRenderer(tmp_path)
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    cache.resolve(period="weekly")
    cache.resolve(period="monthly")

    assert renderer.calls[0]["start_at"] == datetime(2026, 4, 13, 0, 0, tzinfo=_TZ)
    assert renderer.calls[0]["end_at"] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)
    assert renderer.calls[1]["start_at"] == datetime(2026, 4, 1, 0, 0, tzinfo=_TZ)
    assert renderer.calls[1]["end_at"] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)


def test_feishu_report_cache_rejects_non_token_metric(tmp_path: Path) -> None:
    cache = FeishuReportCache(renderer=FakeRenderer(tmp_path), cache_dir=tmp_path / "feishu-cache")

    with pytest.raises(ValueError, match="only support token"):
        cache.resolve(period="daily", metric="quota")


def test_feishu_report_cache_reuses_same_minute_typst_trio_poster(tmp_path: Path) -> None:
    renderer = FakeRenderer(tmp_path)
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve_trio()
    second = cache.resolve_trio()

    assert first.poster_path == second.poster_path
    assert first.from_cache is False
    assert second.from_cache is True
    assert len(renderer.trio_calls) == 1
    assert renderer.trio_calls[0]["end_at"] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)
    assert renderer.trio_calls[0]["scope"] == "whitelist"
    assert first.poster_path == tmp_path / "feishu-cache" / "whitelist" / "tokens" / "trio" / "202604161223" / "trio-poster.png"
    assert '"periods"' in first.json_path.read_text(encoding="utf-8")


def test_feishu_report_cache_reuses_same_minute_typst_trio_pdf(tmp_path: Path) -> None:
    renderer = FakeRenderer(tmp_path)
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve_trio_pdf()
    second = cache.resolve_trio_pdf()

    assert first.pdf_path == second.pdf_path
    assert first.from_cache is False
    assert second.from_cache is True
    assert len(renderer.trio_pdf_calls) == 1
    assert renderer.trio_pdf_calls[0]["end_at"] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)
    assert first.pdf_path == tmp_path / "feishu-cache" / "whitelist" / "tokens" / "trio-pdf" / "202604161223" / "trio-poster.pdf"
    assert '"periods"' in first.json_path.read_text(encoding="utf-8")


def test_feishu_report_cache_invalidates_same_minute_trio_when_whitelist_changes(tmp_path: Path) -> None:
    whitelist_path = tmp_path / "teamview_whitelist.json"
    whitelist_path.write_text('{"email:a@example.com":{"alias":"A","include":true}}', encoding="utf-8")
    renderer = FakeRenderer(tmp_path)
    renderer.service = SimpleNamespace(whitelist_store=SimpleNamespace(path=whitelist_path))
    cache = FeishuReportCache(
        renderer=renderer,
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve_trio()
    second = cache.resolve_trio()
    whitelist_path.write_text('{"email:a@example.com":{"alias":"A","include":false}}', encoding="utf-8")
    third = cache.resolve_trio()

    assert first.poster_path == second.poster_path == third.poster_path
    assert first.from_cache is False
    assert second.from_cache is True
    assert third.from_cache is False
    assert len(renderer.trio_calls) == 2


def test_feishu_report_cache_rejects_non_token_trio_metric(tmp_path: Path) -> None:
    cache = FeishuReportCache(renderer=FakeRenderer(tmp_path), cache_dir=tmp_path / "feishu-cache")

    with pytest.raises(ValueError, match="only support token"):
        cache.resolve_trio(metric="quota")


class FakeRenderer:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.calls: list[dict[str, object]] = []
        self.trio_calls: list[dict[str, object]] = []
        self.trio_pdf_calls: list[dict[str, object]] = []

    def render_period(self, **kwargs) -> TypstPosterOutput:
        self.calls.append(kwargs)
        output_path = kwargs["output_path"]
        assert isinstance(output_path, Path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        period = kwargs["period"]
        payload = {
            "ranking_type": period,
            "generated_at": int(kwargs["end_at"].timestamp()),
            "window_start": int(kwargs["start_at"].timestamp()),
            "window_end": int(kwargs["end_at"].timestamp()),
            "items": [],
        }
        return TypstPosterOutput(
            period=period,
            metric="tokens",
            payload=payload,
            poster_path=output_path,
            window_text="window",
        )

    def render_trio(self, **kwargs) -> TypstTrioPosterOutput:
        self.trio_calls.append(kwargs)
        output_path = kwargs["output_path"]
        assert isinstance(output_path, Path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return TypstTrioPosterOutput(
            metric="tokens",
            payloads={
                "daily": {"ranking_type": "daily", "items": []},
                "weekly": {"ranking_type": "weekly", "items": []},
                "monthly": {"ranking_type": "monthly", "items": []},
            },
            poster_path=output_path,
            window_texts={"daily": "daily window", "weekly": "weekly window", "monthly": "monthly window"},
        )

    def render_trio_pdf(self, **kwargs) -> TypstTrioPosterOutput:
        self.trio_pdf_calls.append(kwargs)
        output_path = kwargs["output_path"]
        assert isinstance(output_path, Path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"pdf")
        return TypstTrioPosterOutput(
            metric="tokens",
            payloads={
                "daily": {"ranking_type": "daily", "items": []},
                "weekly": {"ranking_type": "weekly", "items": []},
                "monthly": {"ranking_type": "monthly", "items": []},
            },
            poster_path=output_path,
            window_texts={"daily": "daily window", "weekly": "weekly window", "monthly": "monthly window"},
        )
