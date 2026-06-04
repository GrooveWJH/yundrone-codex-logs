from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import render_typst_posters as renderer


def test_default_render_exports_all_csv_and_compiles_nine_pngs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    csv_dir = Path("metrics")
    output_dir = Path("typst-posters")
    service, export_calls, run_calls = _patch_render_dependencies(monkeypatch)
    for metric in renderer.METRICS:
        for period in renderer.PERIODS:
            time_path = csv_dir / metric / f"{period}.time"
            time_path.parent.mkdir(parents=True, exist_ok=True)
            time_path.write_text(f"{metric} {period} window", encoding="utf-8")

    paths = renderer.render_typst_posters(
        metric="all",
        period="all",
        csv_dir=csv_dir,
        output_dir=output_dir,
        typst_main=Path("typst/main.typ"),
        ppi=200,
    )

    expected_targets = [
        ("tokens", "daily"),
        ("tokens", "weekly"),
        ("tokens", "monthly"),
        ("quota", "daily"),
        ("quota", "weekly"),
        ("quota", "monthly"),
        ("intensity", "daily"),
        ("intensity", "weekly"),
        ("intensity", "monthly"),
    ]
    expected_paths = [output_dir / metric / f"{period}.png" for metric, period in expected_targets]
    assert paths == expected_paths
    assert export_calls == [
        {
            "period": "all",
            "metric": "all",
            "output_dir": csv_dir,
            "service": service,
        }
    ]
    assert len(run_calls) == 9
    for (cmd, check), output_path, (metric, period) in zip(run_calls, expected_paths, expected_targets, strict=True):
        assert check is True
        _assert_typst_command(
            cmd,
            output_path=output_path,
            metric=metric,
            period=period,
            ppi=200,
            window=f"{metric} {period} window",
        )


def test_single_metric_period_renders_one_default_output_path(tmp_path: Path, monkeypatch) -> None:
    _, _, run_calls = _patch_render_dependencies(monkeypatch)
    monkeypatch.chdir(tmp_path)
    time_path = tmp_path / "metrics" / "quota" / "daily.time"
    time_path.parent.mkdir(parents=True, exist_ok=True)
    time_path.write_text("daily quota window", encoding="utf-8")

    paths = renderer.render_typst_posters(
        metric="quota",
        period="daily",
        csv_dir=tmp_path / "metrics",
        typst_main=Path("typst/main.typ"),
        ppi=144,
        service=object(),
    )

    assert paths == [Path("outputs/typst-posters") / "quota" / "daily.png"]
    assert len(run_calls) == 1
    _assert_typst_command(
        run_calls[0][0],
        output_path=paths[0],
        metric="quota",
        period="daily",
        ppi=144,
        window="daily quota window",
    )


def test_window_text_falls_back_to_metric_time_file(tmp_path: Path) -> None:
    time_path = tmp_path / "metrics" / "tokens" / "time"
    time_path.parent.mkdir(parents=True, exist_ok=True)
    time_path.write_text("monthly fallback", encoding="utf-8")

    assert renderer._window_text(csv_dir=tmp_path / "metrics", metric="tokens", period="monthly") == "monthly fallback"


def test_trio_period_renders_one_three_period_png(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    csv_dir = Path("metrics")
    output_dir = Path("posters")
    service, export_calls, run_calls = _patch_render_dependencies(monkeypatch)

    paths = renderer.render_typst_posters(
        metric="tokens",
        period="trio",
        csv_dir=csv_dir,
        output_dir=output_dir,
        typst_trio=Path("typst/trio.typ"),
        ppi=180,
    )

    assert paths == [output_dir / "tokens" / "trio.png"]
    assert export_calls == [
        {
            "period": "all",
            "metric": "tokens",
            "output_dir": csv_dir,
            "service": service,
        }
    ]
    assert run_calls == [(
        [
            "typst",
            "compile",
            "typst/trio.typ",
            str(output_dir / "tokens" / "trio.png"),
            "--root",
            ".",
            "--font-path",
            "assets/NotoSansSC",
            "--ppi",
            "180",
            "--input",
            "metric=tokens",
            "--input",
            "csv-dir=../../metrics",
        ],
        True,
    )]


def test_trio_period_with_all_metrics_renders_three_pngs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _, _, run_calls = _patch_render_dependencies(monkeypatch)

    paths = renderer.render_typst_posters(
        metric="all",
        period="trio",
        csv_dir=Path("metrics"),
        output_dir=Path("posters"),
        typst_trio=Path("typst/trio.typ"),
        ppi=120,
    )

    assert paths == [
        Path("posters") / "tokens" / "trio.png",
        Path("posters") / "quota" / "trio.png",
        Path("posters") / "intensity" / "trio.png",
    ]
    assert [cmd[11] for cmd, _ in run_calls] == ["metric=tokens", "metric=quota", "metric=intensity"]


def test_main_reports_readable_error_when_typst_is_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    service = object()
    monkeypatch.setattr(renderer.DashboardService, "from_env", staticmethod(lambda: service))
    monkeypatch.setattr(renderer.shutil, "which", lambda name: None)

    exit_code = renderer.main(
        [
            "--metric",
            "quota",
            "--period",
            "daily",
            "--csv-dir",
            str(tmp_path / "metrics"),
            "--output-dir",
            str(tmp_path / "posters"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "找不到 typst 命令" in captured.err
    assert "Traceback" not in captured.err


def test_main_returns_nonzero_when_typst_compile_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    service = object()
    monkeypatch.setattr(renderer.DashboardService, "from_env", staticmethod(lambda: service))
    monkeypatch.setattr(renderer.shutil, "which", lambda name: "typst")
    monkeypatch.setattr(renderer, "export_csv_files", lambda **kwargs: [])

    def fake_run(cmd: list[str], *, check: bool) -> subprocess.CompletedProcess:
        del check
        raise subprocess.CalledProcessError(7, cmd)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    exit_code = renderer.main(
        [
            "--metric",
            "quota",
            "--period",
            "daily",
            "--csv-dir",
            "metrics",
            "--output-dir",
            "posters",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "Typst 编译失败" in captured.err
    assert "Traceback" not in captured.err


def _patch_render_dependencies(monkeypatch):
    service = object()
    export_calls: list[dict[str, object]] = []
    run_calls: list[tuple[list[str], bool]] = []
    monkeypatch.setattr(renderer.DashboardService, "from_env", staticmethod(lambda: service))
    monkeypatch.setattr(renderer.shutil, "which", lambda name: "typst")

    def fake_export_csv_files(**kwargs):
        export_calls.append(kwargs)
        return []

    def fake_run(cmd: list[str], *, check: bool) -> subprocess.CompletedProcess:
        run_calls.append((cmd, check))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(renderer, "export_csv_files", fake_export_csv_files)
    monkeypatch.setattr(renderer.subprocess, "run", fake_run)
    return service, export_calls, run_calls


def _assert_typst_command(
    cmd: list[str],
    *,
    output_path: Path,
    metric: str,
    period: str,
    ppi: int,
    window: str,
) -> None:
    assert cmd[:4] == ["typst", "compile", "typst/main.typ", str(output_path)]
    assert cmd[4:12] == [
        "--root",
        ".",
        "--font-path",
        "assets/NotoSansSC",
        "--ppi",
        str(ppi),
        "--input",
        f"metric={metric}",
    ]
    assert cmd[12:15] == [
        "--input",
        f"period={period}",
        "--input",
    ]
    assert cmd[15].startswith("csv-dir=")
    assert cmd[16:] == ["--input", f"window={window}"]
