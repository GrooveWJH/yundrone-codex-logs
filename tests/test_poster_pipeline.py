from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scripts.poster import cli, export, loaders
from scripts.poster.models import DataPolicy, PosterRequest, RankingSnapshot


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


def test_build_snapshot_applies_default_policy() -> None:
    snapshot = loaders.build_snapshot(
        raw_payload=_payload(),
        policy=DataPolicy(),
        period="daily",
        source="memory",
    )

    assert snapshot.scope == "filtered"
    assert [item.email for item in snapshot.items] == ["alice@yundrone.cn"]
    assert snapshot.items[0].rank == 1


def test_load_snapshot_from_json_matches_in_memory_builder(tmp_path: Path) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")

    from_file = loaders.load_snapshot_from_json(
        input_file,
        period="daily",
        policy=DataPolicy(include_all_members=True),
    )
    from_memory = loaders.load_snapshot_from_memory(
        _payload(),
        period="daily",
        policy=DataPolicy(include_all_members=True),
        source="memory",
    )

    assert from_file == from_memory.model_copy(update={"source": str(input_file)})


def test_load_snapshot_from_api_uses_fetched_payload(monkeypatch) -> None:
    monkeypatch.setattr(loaders, "fetch_ranking_payload", lambda base_url, token, period: _payload())

    snapshot = loaders.load_snapshot_from_api(
        "http://example.test/api/public-rankings",
        "weird-token",
        "daily",
        DataPolicy(),
    )

    assert isinstance(snapshot, RankingSnapshot)
    assert snapshot.period == "daily"
    assert [item.email for item in snapshot.items] == ["alice@yundrone.cn"]


def test_load_snapshots_from_json_dir_supports_all_periods(tmp_path: Path) -> None:
    for period in ("daily", "weekly", "monthly"):
        path = tmp_path / f"{period}.json"
        path.write_text(json.dumps({**_payload(), "ranking_type": period}), encoding="utf-8")

    snapshots = loaders.load_snapshots_from_json_dir(tmp_path, ["daily", "weekly", "monthly"], policy=DataPolicy())

    assert [snapshot.period for snapshot in snapshots] == ["daily", "weekly", "monthly"]


def test_export_save_png_writes_file(tmp_path: Path) -> None:
    snapshot = loaders.load_snapshot_from_memory(_payload(), period="daily", policy=DataPolicy(), source="memory")
    request = PosterRequest(snapshots=[snapshot])
    figure = cli.build_figure(request)
    output_path = export.save_png(figure, tmp_path / "poster.png")

    assert output_path.exists()
    assert output_path.suffix == ".png"


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
    saved_payload = json.loads((json_dir / "daily.json").read_text(encoding="utf-8"))
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


def test_cli_uses_outputs_directory_when_output_not_provided(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    expected_output = tmp_path / "outputs" / "daily-poster.png"
    seen: dict[str, Path] = {}

    def fake_save_png(figure, output_path, *, dpi=250, facecolor="#f5f6fa"):
        del figure, dpi, facecolor
        seen["output_path"] = output_path
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
    assert seen["output_path"] == expected_output
    assert expected_output.exists()


def test_cli_accepts_include_all_members_flag(tmp_path: Path) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    output_file = tmp_path / "poster.png"

    cli.run(
        [
            "--input-source",
            "json",
            "--period",
            "daily",
            "--input-file",
            str(input_file),
            "--output",
            str(output_file),
            "--include-all-members",
        ]
    )

    snapshot = loaders.load_snapshot_from_json(
        input_file,
        period="daily",
        policy=DataPolicy(include_all_members=True),
    )
    assert [item.email for item in snapshot.items] == [
        "codex@yundrone.cn",
        "bob@example.com",
        "alice@yundrone.cn",
    ]


def test_cli_loads_public_token_from_repo_root_env(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / ".env").write_text("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN=env-token\n", encoding="utf-8")
    seen: dict[str, object] = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN", raising=False)

    def fake_load_snapshot_from_api(base_url, token, period, policy):
        del base_url, policy
        seen["snapshot_token"] = token
        return RankingSnapshot(
            period=period,
            generated_at=1_776_007_200,
            source="api",
            scope="filtered",
            items=[],
        )

    def fake_fetch_ranking_payload(base_url, token, period):
        del base_url, period
        seen["payload_token"] = token
        return _payload()

    monkeypatch.setattr(loaders, "load_snapshot_from_api", fake_load_snapshot_from_api)
    monkeypatch.setattr(loaders, "fetch_ranking_payload", fake_fetch_ranking_payload)
    monkeypatch.setattr(export, "save_png", lambda figure, output_path, **kwargs: output_path)

    exit_code = cli.run(["--period", "daily"])

    assert exit_code == 0
    assert seen["snapshot_token"] == "env-token"
    assert seen["payload_token"] == "env-token"


def test_typer_cli_help_exposes_core_options() -> None:
    runner = CliRunner()

    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "--input-source" in result.stdout
    assert "--period" in result.stdout
    assert "--output" in result.stdout
    assert "outputs/<period>" in result.stdout


def test_run_without_argv_preserves_process_cli(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_app(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(cli, "app", fake_app)

    assert cli.run() == 0
    assert seen["kwargs"]["prog_name"] == "python -m scripts.poster"
    assert seen["kwargs"]["standalone_mode"] is False
    assert "args" not in seen["kwargs"]
