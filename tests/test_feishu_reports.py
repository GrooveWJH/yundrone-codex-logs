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
        "limit": 10,
        "policy_scope": "all-members",
        "policy_top_n": 10,
    }


def test_feishu_report_cache_builds_and_reuses_overview_per_minute(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, int, int, int]] = []

    class FakeService:
        def build_ranking(
            self,
            *,
            scope: str,
            ranking_type: str,
            start_timestamp: int,
            end_timestamp: int,
            limit: int,
        ) -> dict[str, object]:
            calls.append((ranking_type, start_timestamp, end_timestamp, limit))
            return {
                "scope": scope,
                "ranking_type": ranking_type,
                "generated_at": end_timestamp,
                "items": [
                    {
                        "email": "alice@example.com",
                        "display_name": "Alice",
                        "used_tokens": 123,
                        "request_count": 1,
                    }
                ],
            }

    class FakeGenerator:
        def __init__(self) -> None:
            self.service = FakeService()

    def fake_save_png(figure, output_path: Path, *, dpi: int = 250, facecolor: str = "#f5f6fa") -> Path:
        del figure, dpi, facecolor
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr("switchbase_teamview.feishu_reports.build_figure", lambda request: object())
    monkeypatch.setattr("switchbase_teamview.feishu_reports.export.save_png", fake_save_png)

    cache = FeishuReportCache(
        report_generator=FakeGenerator(),
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    first = cache.resolve_overview()
    second = cache.resolve_overview()

    assert first.poster_path == second.poster_path
    assert first.from_cache is False
    assert second.from_cache is True
    assert [call[0] for call in calls] == ["daily", "weekly", "monthly"]


def test_feishu_report_cache_uses_metric_specific_cache_and_titles(tmp_path: Path, monkeypatch) -> None:
    seen_titles: list[str] = []
    calls: list[tuple[str, int, int, int]] = []

    class FakeService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int):
            calls.append((ranking_type, start_timestamp, end_timestamp, limit))
            return {
                "scope": scope,
                "ranking_type": ranking_type,
                "generated_at": end_timestamp,
                "items": [
                    {
                        "email": "alice@example.com",
                        "display_name": "Alice",
                        "window_used_quota": 200,
                        "used_tokens": 100,
                        "request_count": 1,
                    }
                ],
            }

    class FakeGenerator:
        def __init__(self) -> None:
            self.service = FakeService()

    def fake_build_figure(request):
        seen_titles.append(request.config.main_title)
        return object()

    def fake_save_png(figure, output_path: Path, *, dpi: int = 250, facecolor: str = "#f5f6fa") -> Path:
        del figure, dpi, facecolor
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr("switchbase_teamview.feishu_reports.build_figure", fake_build_figure)
    monkeypatch.setattr("switchbase_teamview.feishu_reports.export.save_png", fake_save_png)

    cache = FeishuReportCache(
        report_generator=FakeGenerator(),
        cache_dir=tmp_path / "feishu-cache",
        now_provider=lambda: datetime(2026, 4, 16, 12, 23, 12, tzinfo=_TZ),
    )

    quota = cache.resolve(period="daily", metric="quota")
    intensity = cache.resolve_overview(metric="intensity")

    assert "/quota/" in quota.poster_path.as_posix()
    assert "/intensity/" in intensity.poster_path.as_posix()
    assert seen_titles == ["Codex quota", "Codex intensity"]
    assert [call[0] for call in calls] == ["daily", "daily", "weekly", "monthly"]
