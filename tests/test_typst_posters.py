from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from switchbase_teamview import typst_posters
from switchbase_teamview.typst_posters import TypstCompileError
from switchbase_teamview.typst_posters import TypstPosterRenderer
from switchbase_teamview.typst_posters import typst_command
from switchbase_teamview.typst_posters import typst_csv_dir
from switchbase_teamview.typst_posters import typst_trio_command

_TZ = ZoneInfo("Asia/Shanghai")


def test_typst_command_includes_csv_dir_and_window() -> None:
    cmd = typst_command(
        typst_bin="typst",
        typst_main=Path("typst/main.typ"),
        output_path=Path("out.png"),
        font_path=Path("assets/NotoSansSC"),
        metric="tokens",
        period="daily",
        csv_dir=Path("../../outputs/metrics"),
        window="2026/04/16 00:00 – 12:23 CST",
        ppi=200,
    )

    assert cmd == [
        "typst",
        "compile",
        "typst/main.typ",
        "out.png",
        "--root",
        ".",
        "--font-path",
        "assets/NotoSansSC",
        "--ppi",
        "200",
        "--input",
        "metric=tokens",
        "--input",
        "period=daily",
        "--input",
        "csv-dir=../../outputs/metrics",
        "--input",
        "window=2026/04/16 00:00 – 12:23 CST",
    ]


def test_typst_csv_dir_is_relative_to_typst_lib() -> None:
    assert typst_csv_dir(Path("outputs/metrics")) == Path("../../outputs/metrics")


def test_typst_csv_dir_rejects_absolute_paths_outside_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="csv_dir must be under Typst root"):
        typst_csv_dir(tmp_path / "metrics")


def test_typst_trio_command_includes_csv_dir() -> None:
    cmd = typst_trio_command(
        typst_bin="typst",
        typst_trio=Path("typst/trio.typ"),
        output_path=Path("trio.png"),
        font_path=Path("assets/NotoSansSC"),
        metric="tokens",
        csv_dir=Path("../../outputs/metrics"),
        ppi=200,
    )

    assert cmd == [
        "typst",
        "compile",
        "typst/trio.typ",
        "trio.png",
        "--root",
        ".",
        "--font-path",
        "assets/NotoSansSC",
        "--ppi",
        "200",
        "--input",
        "metric=tokens",
        "--input",
        "csv-dir=../../outputs/metrics",
    ]


def test_renderer_writes_three_csvs_and_compiles_trio_pdf(tmp_path: Path, monkeypatch) -> None:
    run_calls: list[tuple[list[str], bool]] = []
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: list[str], *, check: bool):
        run_calls.append((cmd, check))
        Path(cmd[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[3]).write_bytes(b"pdf")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(typst_posters.subprocess, "run", fake_run)
    fake_service = FakeService()
    renderer = TypstPosterRenderer(service=fake_service, typst_bin="typst")
    output_path = tmp_path / "trio.pdf"

    result = renderer.render_trio_pdf(
        end_at=datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
        output_path=output_path,
        csv_dir=Path("metrics"),
        scope="whitelist",
    )

    assert result.poster_path == output_path
    assert output_path.read_bytes() == b"pdf"
    assert (tmp_path / "metrics" / "tokens" / "daily.csv").exists()
    assert run_calls[0][0][3] == str(output_path)


def test_renderer_writes_csv_and_compiles_png(tmp_path: Path, monkeypatch) -> None:
    run_calls: list[tuple[list[str], bool]] = []
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: list[str], *, check: bool):
        run_calls.append((cmd, check))
        Path(cmd[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[3]).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(typst_posters.subprocess, "run", fake_run)
    fake_service = FakeService()
    renderer = TypstPosterRenderer(service=fake_service, typst_bin="typst")
    output_path = tmp_path / "daily.png"

    result = renderer.render_period(
        period="daily",
        start_at=datetime(2026, 4, 16, 0, 0, tzinfo=_TZ),
        end_at=datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
        output_path=output_path,
        csv_dir=Path("metrics"),
    )

    assert result.poster_path == output_path
    assert (tmp_path / "metrics" / "tokens" / "daily.csv").exists()
    assert (tmp_path / "metrics" / "tokens" / "daily.time").read_text(encoding="utf-8") == "2026/04/16 00:00 – 12:23 CST"
    assert run_calls[0][1] is True
    assert "--input" in run_calls[0][0]
    assert run_calls[0][0][6:8] == ["--font-path", "assets/NotoSansSC"]
    assert any(part.startswith("csv-dir=") for part in run_calls[0][0])


def test_renderer_writes_three_csvs_and_compiles_trio_png(tmp_path: Path, monkeypatch) -> None:
    run_calls: list[tuple[list[str], bool]] = []
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: list[str], *, check: bool):
        run_calls.append((cmd, check))
        Path(cmd[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[3]).write_bytes(b"png")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(typst_posters.subprocess, "run", fake_run)
    fake_service = FakeService()
    renderer = TypstPosterRenderer(service=fake_service, typst_bin="typst")
    output_path = tmp_path / "trio.png"

    result = renderer.render_trio(
        end_at=datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
        output_path=output_path,
        csv_dir=Path("metrics"),
        scope="whitelist",
    )

    assert result.poster_path == output_path
    assert [payload["ranking_type"] for payload in result.payloads.values()] == ["daily", "weekly", "monthly"]
    assert (tmp_path / "metrics" / "tokens" / "daily.csv").exists()
    assert (tmp_path / "metrics" / "tokens" / "weekly.csv").exists()
    assert (tmp_path / "metrics" / "tokens" / "monthly.csv").exists()
    assert run_calls == [(
        [
            "typst",
            "compile",
            "typst/trio.typ",
            str(output_path),
            "--root",
            ".",
            "--font-path",
            "assets/NotoSansSC",
            "--ppi",
            "200",
            "--input",
            "metric=tokens",
            "--input",
            "csv-dir=../../metrics",
        ],
        True,
    )]
    assert [call["ranking_type"] for call in fake_service.calls] == ["daily", "weekly", "monthly"]


def test_renderer_raises_readable_compile_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(cmd: list[str], *, check: bool):
        del check
        raise subprocess.CalledProcessError(9, cmd)

    monkeypatch.setattr(typst_posters.subprocess, "run", fake_run)
    renderer = TypstPosterRenderer(service=FakeService(), typst_bin="typst")

    with pytest.raises(TypstCompileError, match="exit=9"):
        renderer.render_period(
            period="daily",
            start_at=datetime(2026, 4, 16, 0, 0, tzinfo=_TZ),
            end_at=datetime(2026, 4, 16, 12, 23, tzinfo=_TZ),
            output_path=tmp_path / "daily.png",
            csv_dir=Path("metrics"),
        )


class FakeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def build_ranking(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "scope": kwargs["scope"],
            "ranking_type": kwargs["ranking_type"],
            "generated_at": kwargs["end_timestamp"],
            "items": [
                {
                    "email": "alice@example.com",
                    "display_name": "Alice",
                    "used_tokens": 12_345_678,
                    "window_used_quota": 24_000_000,
                }
            ],
        }
