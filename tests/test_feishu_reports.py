from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from switchbase_teamview.feishu_reports import FeishuReportCache


_TZ = ZoneInfo("Asia/Shanghai")


def test_feishu_report_cache_reuses_same_minute_request(tmp_path: Path) -> None:
    calls: list[tuple[str, datetime, datetime, Path]] = []

    class FakeGenerator:
        def generate_and_write(self, *, period: str, start_at: datetime, end_at: datetime, poster_path: Path):
            calls.append((period, start_at, end_at, poster_path))
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            poster_path.write_bytes(b"png")
            json_path = poster_path.with_name(f"{period}.json")
            json_path.write_text("{}", encoding="utf-8")
            return type("Result", (), {"period": period, "json_path": json_path, "poster_path": poster_path})()

    cache = FeishuReportCache(
        report_generator=FakeGenerator(),
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve(period="daily")
    second = cache.resolve(period="daily")

    assert first.poster_path == second.poster_path
    assert len(calls) == 1
    assert calls[0][0] == "daily"
    assert calls[0][1] == datetime(2026, 4, 16, 0, 0, tzinfo=_TZ)
    assert calls[0][2] == datetime(2026, 4, 16, 12, 23, tzinfo=_TZ)


def test_feishu_report_cache_expires_at_next_minute(tmp_path: Path) -> None:
    current = datetime(2026, 4, 16, 12, 23, 59, tzinfo=_TZ)
    calls: list[tuple[str, datetime, datetime, Path]] = []

    class FakeGenerator:
        def generate_and_write(self, *, period: str, start_at: datetime, end_at: datetime, poster_path: Path):
            calls.append((period, start_at, end_at, poster_path))
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            poster_path.write_bytes(end_at.strftime("%H:%M").encode("utf-8"))
            json_path = poster_path.with_name(f"{period}.json")
            json_path.write_text("{}", encoding="utf-8")
            return type("Result", (), {"period": period, "json_path": json_path, "poster_path": poster_path})()

    cache = FeishuReportCache(
        report_generator=FakeGenerator(),
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: current,
    )

    first = cache.resolve(period="daily")
    current = datetime(2026, 4, 16, 12, 24, 0, tzinfo=_TZ)
    second = cache.resolve(period="daily")

    assert len(calls) == 2
    assert first.poster_path != second.poster_path
    assert not first.poster_path.exists()
    assert calls[1][2] == datetime(2026, 4, 16, 12, 24, tzinfo=_TZ)


def test_feishu_report_cache_uses_natural_weekly_and_monthly_windows(tmp_path: Path) -> None:
    calls: list[tuple[str, datetime, datetime, Path]] = []

    class FakeGenerator:
        def generate_and_write(self, *, period: str, start_at: datetime, end_at: datetime, poster_path: Path):
            calls.append((period, start_at, end_at, poster_path))
            poster_path.parent.mkdir(parents=True, exist_ok=True)
            poster_path.write_bytes(b"png")
            json_path = poster_path.with_name(f"{period}.json")
            json_path.write_text("{}", encoding="utf-8")
            return type("Result", (), {"period": period, "json_path": json_path, "poster_path": poster_path})()

    cache = FeishuReportCache(
        report_generator=FakeGenerator(),
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    cache.resolve(period="weekly")
    cache.resolve(period="monthly")

    assert calls[0][:3] == (
        "weekly",
        datetime(2026, 4, 13, 0, 0, tzinfo=_TZ),
        datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
    )
    assert calls[1][:3] == (
        "monthly",
        datetime(2026, 4, 1, 0, 0, tzinfo=_TZ),
        datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
    )


def test_feishu_report_cache_defaults_to_all_members_scope(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeGenerator:
        def __init__(self, *, output_dir: Path, scope: str, limit: int, policy):
            seen["output_dir"] = output_dir
            seen["scope"] = scope
            seen["limit"] = limit
            seen["policy_scope"] = policy.scope
            seen["policy_top_n"] = policy.top_n

    monkeypatch.setattr("switchbase_teamview.feishu_reports.ReportGenerator", FakeGenerator)

    cache = FeishuReportCache(cache_dir=tmp_path / "feishu-cache")

    assert cache.scope == "all-members"
    assert seen == {
        "output_dir": tmp_path / "feishu-cache",
        "scope": "all-members",
        "limit": 7,
        "policy_scope": "all-members",
        "policy_top_n": 7,
    }
