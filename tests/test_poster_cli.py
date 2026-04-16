from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scripts.poster import cli, export, loaders
from scripts.poster.models import DataPolicy, RankingSnapshot


def _payload() -> dict[str, object]:
    return {
        "ranking_type": "daily",
        "generated_at": 1_776_007_200,
        "items": [
            {
                "email": "alice@yundrone.cn",
                "display_name": "Alice",
                "raw_display_name": "alice",
                "username": "alice",
                "used_tokens": 120,
                "request_count": 3,
            },
            {
                "email": "codex@yundrone.cn",
                "display_name": "Codex",
                "raw_display_name": "codex",
                "username": "codex",
                "used_tokens": 999,
                "request_count": 9,
            },
            {
                "email": "bob@example.com",
                "display_name": "Bob",
                "raw_display_name": "bob",
                "username": "bob",
                "used_tokens": 400,
                "request_count": 4,
            },
        ],
    }


def test_cli_generates_png_and_json_from_json_input(tmp_path: Path) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    output_file = tmp_path / "poster.png"
    json_dir = tmp_path / "json"

    exit_code = cli.run(
        [
            "--input-source",
            "json",
            "--period",
            "daily",
            "--input-file",
            str(input_file),
            "--output",
            str(output_file),
            "--json-dir",
            str(json_dir),
        ]
    )

    assert exit_code == 0
    assert output_file.exists()
    saved_payload = json.loads((tmp_path / "daily.json").read_text(encoding="utf-8"))
    assert saved_payload["ranking_type"] == "daily"


def test_cli_prints_runtime_debug_steps(tmp_path: Path, capsys) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    output_file = tmp_path / "poster.png"
    json_dir = tmp_path / "json"

    exit_code = cli.run(
        [
            "--input-source",
            "json",
            "--period",
            "daily",
            "--input-file",
            str(input_file),
            "--output",
            str(output_file),
            "--json-dir",
            str(json_dir),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[poster]" in captured.out
    assert "source=json" in captured.out
    assert "periods=daily" in captured.out
    assert "saved png" in captured.out


def test_cli_rejects_all_members_scope_for_api_source() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli.app,
        [
            "--period",
            "daily",
            "--token",
            "token",
            "--scope",
            "all-members",
        ],
    )

    assert result.exit_code != 0
    assert "all-members scope requires --input-source teamview, json, or memory-test-hook" in (
        result.stdout + result.stderr
    )


def test_cli_uses_outputs_directory_when_output_not_provided(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    expected_output = tmp_path / "outputs" / "daily-poster.png"
    seen: dict[str, object] = {}

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        seen["called"] = True
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr(export, "save_png", fake_save_png)
    monkeypatch.chdir(tmp_path)

    exit_code = cli.run(
        [
            "--input-source",
            "json",
            "--period",
            "daily",
            "--input-file",
            str(input_file),
        ]
    )

    assert exit_code == 0
    assert seen["called"] is True
    assert expected_output.exists()
    assert json.loads((tmp_path / "outputs" / "daily.json").read_text(encoding="utf-8"))["ranking_type"] == "daily"


def test_cli_all_writes_three_single_period_posters(tmp_path: Path, monkeypatch) -> None:
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    for period in ("daily", "weekly", "monthly"):
        (json_dir / f"{period}.json").write_text(
            json.dumps({**_payload(), "ranking_type": period}),
            encoding="utf-8",
        )

    seen_paths: list[Path] = []

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        seen_paths.append(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr(export, "save_png", fake_save_png)
    monkeypatch.chdir(tmp_path)

    exit_code = cli.run(
        [
            "--input-source",
            "json",
            "--period",
            "all",
            "--json-dir",
            str(json_dir),
        ]
    )

    assert exit_code == 0
    assert len(seen_paths) == 3
    assert (tmp_path / "outputs" / "daily-poster.png").exists()
    assert (tmp_path / "outputs" / "weekly-poster.png").exists()
    assert (tmp_path / "outputs" / "monthly-poster.png").exists()
    assert json.loads((tmp_path / "outputs" / "daily.json").read_text(encoding="utf-8"))["ranking_type"] == "daily"
    assert json.loads((tmp_path / "outputs" / "weekly.json").read_text(encoding="utf-8"))["ranking_type"] == "weekly"
    assert json.loads((tmp_path / "outputs" / "monthly.json").read_text(encoding="utf-8"))["ranking_type"] == "monthly"
