from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from matplotlib.figure import Figure

from switchbase_teamview.reporting import ReportGenerator


def _payload(period: str = "daily", generated_at: int = 1_776_007_200) -> dict[str, object]:
    return {
        "ranking_type": period,
        "generated_at": generated_at,
        "items": [
            {
                "email": "alice@yundrone.cn",
                "display_name": "Alice",
                "raw_display_name": "alice",
                "username": "alice",
                "used_tokens": 120,
                "request_count": 3,
            }
        ],
    }


def test_report_generator_writes_json_and_poster_into_outputs(tmp_path: Path, monkeypatch) -> None:
    payload = _payload()
    seen: dict[str, object] = {}

    class FakeService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int):
            seen["scope"] = scope
            seen["ranking_type"] = ranking_type
            seen["start_timestamp"] = start_timestamp
            seen["end_timestamp"] = end_timestamp
            seen["limit"] = limit
            return payload

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr("scripts.poster.export.save_png", fake_save_png)

    generator = ReportGenerator(service=FakeService(), output_dir=tmp_path / "outputs")
    start_at = datetime(2026, 4, 15, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    end_at = datetime(2026, 4, 15, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = generator.generate_and_write(period="daily", start_at=start_at, end_at=end_at)

    assert result.json_path == tmp_path / "outputs" / "daily.json"
    assert result.poster_path == tmp_path / "outputs" / "daily-poster.png"
    assert json.loads(result.json_path.read_text(encoding="utf-8"))["ranking_type"] == "daily"
    assert result.poster_path.read_bytes() == b"png"
    assert seen == {
        "scope": "filtered",
        "ranking_type": "daily",
        "start_timestamp": int(start_at.timestamp()),
        "end_timestamp": int(end_at.timestamp()),
        "limit": 10,
    }


def test_report_generator_keeps_previous_outputs_when_poster_write_fails(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    json_path = output_dir / "daily.json"
    poster_path = output_dir / "daily-poster.png"
    json_path.write_text(json.dumps({"ranking_type": "daily", "items": ["old"]}), encoding="utf-8")
    poster_path.write_bytes(b"old-png")

    class FakeService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int):
            del scope, ranking_type, start_timestamp, end_timestamp, limit
            return _payload()

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, output_path, dpi, facecolor
        raise RuntimeError("png failed")

    monkeypatch.setattr("scripts.poster.export.save_png", fake_save_png)

    generator = ReportGenerator(service=FakeService(), output_dir=output_dir)
    start_at = datetime(2026, 4, 15, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    end_at = datetime(2026, 4, 15, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    try:
        generator.generate_and_write(period="daily", start_at=start_at, end_at=end_at)
    except RuntimeError as exc:
        assert str(exc) == "png failed"
    else:  # pragma: no cover - defensive path
        raise AssertionError("expected generate_and_write to raise")

    assert json.loads(json_path.read_text(encoding="utf-8")) == {"ranking_type": "daily", "items": ["old"]}
    assert poster_path.read_bytes() == b"old-png"


def test_report_generator_uses_filtered_scope_by_default(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int):
            seen["scope"] = scope
            seen["ranking_type"] = ranking_type
            seen["limit"] = limit
            del start_timestamp, end_timestamp
            return _payload(period=ranking_type)

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr("scripts.poster.export.save_png", fake_save_png)

    generator = ReportGenerator(service=FakeService(), output_dir=tmp_path / "outputs")
    start_at = datetime(2026, 4, 15, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    end_at = datetime(2026, 4, 15, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    generator.generate_and_write(period="daily", start_at=start_at, end_at=end_at)

    assert seen == {"scope": "filtered", "ranking_type": "daily", "limit": 10}


def test_report_generator_supports_custom_poster_path(tmp_path: Path, monkeypatch) -> None:
    class FakeService:
        def build_ranking(self, *, scope: str, ranking_type: str, start_timestamp: int, end_timestamp: int, limit: int):
            del scope, ranking_type, start_timestamp, end_timestamp, limit
            return _payload()

    def fake_save_png(figure: Figure, output_path: Path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr("scripts.poster.export.save_png", fake_save_png)

    generator = ReportGenerator(service=FakeService(), output_dir=tmp_path / "outputs")
    custom_poster = tmp_path / "outputs" / "feishu-cache" / "all-members" / "daily" / "202604161223" / "daily-poster.png"

    result = generator.generate_and_write(
        period="daily",
        start_at=datetime(2026, 4, 16, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        end_at=datetime(2026, 4, 16, 12, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        poster_path=custom_poster,
    )

    assert result.poster_path == custom_poster
    assert result.json_path == custom_poster.parent / "daily.json"
    assert result.poster_path.read_bytes() == b"png"
