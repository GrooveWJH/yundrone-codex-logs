from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from scripts import export_typst_metric_csv as exporter

_TZ = ZoneInfo("Asia/Shanghai")


def _ts(year: int, month: int, day: int, hour: int, minute: int) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=_TZ).timestamp())


def _payload() -> dict[str, object]:
    return {
        "ranking_type": "monthly",
        "generated_at": _ts(2026, 4, 28, 13, 0),
        "window_start": _ts(2026, 4, 1, 0, 0),
        "window_end": _ts(2026, 4, 28, 13, 0),
        "items": [
            {
                "display_name": "Alice Team",
                "email": "alice@example.com",
                "username": "alice",
                "used_tokens": 45_000_000,
                "window_used_quota": 90_000_000,
            },
            {
                "display_name": "Bob Team",
                "email": "bob@example.com",
                "username": "bob",
                "used_tokens": 999_000,
                "window_used_quota": 1_498_500,
            },
            {
                "display_name": "Zero Team",
                "email": "zero@example.com",
                "username": "zero",
                "used_tokens": 0,
                "window_used_quota": 99_999,
            },
        ]
    }


def test_csv_text_uses_fixed_header_order_and_quotes_all_cells() -> None:
    text = exporter.csv_text(exporter.rows_from_payload(_payload(), metric="tokens"))

    assert text.splitlines()[0] == '"rank","name","value"'
    assert text.splitlines()[1] == '"1","Alice Team","45.00M"'
    assert csv.reader(text.splitlines()).__next__() == list(exporter.CSV_HEADER)


def test_rows_format_tokens_quota_and_intensity_as_single_metric_value() -> None:
    assert exporter.rows_from_payload(_payload(), metric="tokens") == [
        {"rank": "1", "name": "Alice Team", "value": "45.00M"},
        {"rank": "2", "name": "Bob Team", "value": "999.0K"},
        {"rank": "3", "name": "Zero Team", "value": "0"},
    ]
    assert exporter.rows_from_payload(_payload(), metric="quota") == [
        {"rank": "1", "name": "Alice Team", "value": "90.00M"},
        {"rank": "2", "name": "Bob Team", "value": "1.50M"},
        {"rank": "3", "name": "Zero Team", "value": "100.0K"},
    ]
    assert exporter.rows_from_payload(_payload(), metric="intensity") == [
        {"rank": "1", "name": "Alice Team", "value": "2.00"},
        {"rank": "2", "name": "Bob Team", "value": "1.50"},
        {"rank": "3", "name": "Zero Team", "value": "0.00"},
    ]


def test_metric_rows_sort_by_selected_metric() -> None:
    payload = {
        "items": [
            {"display_name": "High Token", "used_tokens": 1000, "window_used_quota": 1000},
            {"display_name": "High Intensity", "used_tokens": 100, "window_used_quota": 900},
        ]
    }

    assert [row["name"] for row in exporter.rows_from_payload(payload, metric="tokens")] == ["High Token", "High Intensity"]
    assert [row["name"] for row in exporter.rows_from_payload(payload, metric="quota")] == ["High Token", "High Intensity"]
    assert [row["name"] for row in exporter.rows_from_payload(payload, metric="intensity")] == ["High Intensity", "High Token"]


def test_compact_decimal_uses_same_large_number_style_for_intensity() -> None:
    assert exporter.compact_decimal(1_234_567.89) == "1.23M"
    assert exporter.compact_decimal(12_345.67) == "12.3K"
    assert exporter.compact_decimal(12.345) == "12.35"


def test_export_all_periods_refreshes_requested_metric_and_all_time_files(tmp_path: Path) -> None:
    service = FakeService()

    paths = exporter.export_csv_files(period="all", metric="quota", output_dir=tmp_path, service=service)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "quota/daily.csv",
        "quota/weekly.csv",
        "quota/monthly.csv",
    ]
    assert [call[1] for call in service.calls] == ["daily", "weekly", "monthly"]
    assert all(call[0] == "whitelist" for call in service.calls)
    assert all(call[2] > 1_000_000 for call in service.calls)
    assert (tmp_path / "quota" / "monthly.csv").read_text(encoding="utf-8").splitlines()[2] == '"2","Bob Team","1.50M"'
    assert not (tmp_path / "tokens" / "monthly.csv").exists()
    assert not (tmp_path / "intensity" / "monthly.csv").exists()
    assert (tmp_path / "tokens" / "time").read_text(encoding="utf-8") == "2026/04/01 00:00 – 04/28 13:00 CST"
    assert (tmp_path / "quota" / "time").read_text(encoding="utf-8") == "2026/04/01 00:00 – 04/28 13:00 CST"
    assert (tmp_path / "intensity" / "time").read_text(encoding="utf-8") == "2026/04/01 00:00 – 04/28 13:00 CST"
    assert (tmp_path / "tokens" / "daily.time").read_text(encoding="utf-8") == "2026/04/01 00:00 – 13:00 CST"
    assert (tmp_path / "tokens" / "weekly.time").read_text(encoding="utf-8") == "04/01 00:00 – 04/28 13:00 CST"
    assert (tmp_path / "tokens" / "monthly.time").read_text(encoding="utf-8") == "2026/04/01 00:00 – 04/28 13:00 CST"


def test_all_metric_period_combinations_have_distinct_output_paths(tmp_path: Path) -> None:
    paths = exporter.export_csv_files(period="all", metric="all", output_dir=tmp_path, service=FakeService())

    assert len(paths) == 9
    assert len({path.as_posix() for path in paths}) == 9


def test_export_single_period_writes_only_requested_metric_file(tmp_path: Path) -> None:
    paths = exporter.export_csv_files(period="monthly", metric="intensity", output_dir=tmp_path, service=FakeService())

    assert paths == [tmp_path / "intensity" / "monthly.csv"]
    assert paths[0].read_text(encoding="utf-8").splitlines()[1] == '"1","Alice Team","2.00"'
    assert (tmp_path / "tokens" / "time").exists()
    assert (tmp_path / "quota" / "time").exists()
    assert (tmp_path / "intensity" / "time").exists()
    assert (tmp_path / "tokens" / "monthly.time").exists()
    assert not (tmp_path / "tokens" / "daily.time").exists()


def test_export_single_period_with_all_metric_writes_three_metric_files(tmp_path: Path) -> None:
    paths = exporter.export_csv_files(period="daily", metric="all", output_dir=tmp_path, service=FakeService())

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "tokens/daily.csv",
        "quota/daily.csv",
        "intensity/daily.csv",
    ]
    assert (tmp_path / "tokens" / "daily.csv").read_text(encoding="utf-8").splitlines()[1] == '"1","Alice Team","45.00M"'
    assert (tmp_path / "quota" / "daily.csv").read_text(encoding="utf-8").splitlines()[1] == '"1","Alice Team","90.00M"'
    assert (tmp_path / "intensity" / "daily.csv").read_text(encoding="utf-8").splitlines()[1] == '"1","Alice Team","2.00"'


def test_time_text_from_payload_reuses_poster_window_format() -> None:
    assert exporter.time_text_from_payload(_payload(), period="monthly") == "2026/04/01 00:00 – 04/28 13:00 CST"


def test_typer_help_is_rich_chinese_and_exposes_metric_choices() -> None:
    result = CliRunner().invoke(exporter.app, ["--help"])

    assert result.exit_code == 0
    assert "按周期和指标导出白名单 CSV" in result.stdout
    assert "基础选项" in result.stdout
    assert "输出选项" in result.stdout
    assert "--period" in result.stdout
    assert "--metric" in result.stdout
    assert "daily" in result.stdout
    assert "quota" in result.stdout
    assert "intensity" in result.stdout


def test_main_prints_usage_without_traceback_for_invalid_choice(capsys) -> None:
    exit_code = exporter.main(["-p", "nonsense", "-m", "tokens"])

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "参数错误" in captured.err
    assert "Usage:" in captured.out
    assert "daily" in captured.out
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_main_prints_usage_without_traceback_for_unknown_option(capsys) -> None:
    exit_code = exporter.main(["--bad-option"])

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "参数错误" in captured.err
    assert "Usage:" in captured.out
    assert "--period" in captured.out
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def build_natural_ranking(self, *, scope: str, ranking_type: str, limit: int) -> dict[str, object]:
        self.calls.append((scope, ranking_type, limit))
        return _payload()
