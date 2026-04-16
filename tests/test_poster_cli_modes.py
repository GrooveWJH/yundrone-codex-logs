from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scripts.poster import cli, export, loaders
from scripts.poster.models import DataPolicy


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


def test_cli_accepts_all_members_scope_for_json_input(tmp_path: Path) -> None:
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
            "--scope",
            "all-members",
        ]
    )

    snapshot = loaders.load_snapshot_from_json(
        input_file,
        period="daily",
        policy=DataPolicy(scope="all-members"),
    )
    assert [item.email for item in snapshot.items] == [
        "codex@yundrone.cn",
        "bob@example.com",
        "alice@yundrone.cn",
    ]


def test_cli_teamview_source_supports_all_members_scope(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeService:
        def build_natural_ranking(self, *, scope: str, ranking_type: str, limit: int):
            seen["scope"] = scope
            seen["ranking_type"] = ranking_type
            seen["limit"] = limit
            return {
                "scope": scope,
                "ranking_type": ranking_type,
                "generated_at": 1_776_007_200,
                "items": [
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

    monkeypatch.setattr(cli, "_dashboard_service", lambda: FakeService())

    def fake_save_png(figure, output_path, **kwargs):
        del figure, kwargs
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr(export, "save_png", fake_save_png)
    monkeypatch.chdir(tmp_path)

    exit_code = cli.run(
        [
            "--input-source",
            "teamview",
            "--period",
            "daily",
            "--scope",
            "all-members",
            "--top-n",
            "7",
        ]
    )

    saved_payload = json.loads((tmp_path / "outputs" / "daily.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert seen == {"scope": "all-members", "ranking_type": "daily", "limit": 7}
    assert saved_payload["scope"] == "all-members"
    assert [item["email"] for item in saved_payload["items"]] == [
        "codex@yundrone.cn",
        "bob@example.com",
    ]


def test_cli_loads_public_token_from_repo_root_env(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / ".env").write_text("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN=env-token\n", encoding="utf-8")
    seen: dict[str, object] = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN", raising=False)

    def fake_fetch_ranking_payload(base_url, token, period):
        del base_url, period
        seen["payload_token"] = token
        return _payload()

    monkeypatch.setattr(loaders, "fetch_ranking_payload", fake_fetch_ranking_payload)

    def fake_save_png(figure, output_path, **kwargs):
        del figure, kwargs
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        return output_path

    monkeypatch.setattr(export, "save_png", fake_save_png)

    exit_code = cli.run(["--period", "daily"])

    assert exit_code == 0
    assert seen["payload_token"] == "env-token"


def test_typer_cli_help_exposes_core_options() -> None:
    runner = CliRunner()

    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "--input-source" in result.stdout
    assert "--period" in result.stdout
    assert "--output" in result.stdout
    assert "--scope" in result.stdout
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
