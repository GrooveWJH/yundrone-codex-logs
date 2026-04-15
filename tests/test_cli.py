from __future__ import annotations

from pathlib import Path

import switchbase_teamview.cli as cli_module


def test_validate_command_prints_first_member_usage(monkeypatch, capsys) -> None:
    run = getattr(cli_module, "run", None)
    assert run is not None

    class FakeMember:
        username = "alice"
        display_name = "Alice"
        request_count = 2
        used_tokens = 20
        used_quota = 500

    class FakeData:
        members = [FakeMember()]

    class FakeResponse:
        success = True
        data = FakeData()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_usage(self, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setenv("SWITCHBASE_TEAMVIEW_API_KEY", "stv_test_key")
    monkeypatch.setattr(cli_module, "TeamViewClient", FakeClient)

    exit_code = run(["validate"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "alice" in output
    assert "used_tokens=20" in output


def test_validate_command_requires_api_key(monkeypatch, tmp_path: Path, capsys) -> None:
    run = getattr(cli_module, "run", None)
    assert run is not None

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_API_KEY", raising=False)

    exit_code = run(["validate"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "SWITCHBASE_TEAMVIEW_API_KEY" in captured.err


def test_validate_command_loads_api_key_from_dotenv(monkeypatch, tmp_path: Path, capsys) -> None:
    run = getattr(cli_module, "run", None)
    assert run is not None

    seen: dict[str, str] = {}
    (tmp_path / ".env").write_text("SWITCHBASE_TEAMVIEW_API_KEY=stv_from_dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_API_KEY", raising=False)

    class FakeMember:
        username = "alice"
        display_name = "Alice"
        request_count = 2
        used_tokens = 20
        used_quota = 500

    class FakeData:
        members = [FakeMember()]

    class FakeResponse:
        success = True
        data = FakeData()

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            seen["api_key"] = kwargs["api_key"]

        def get_usage(self, **kwargs) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(cli_module, "TeamViewClient", FakeClient)

    exit_code = run(["validate"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert seen["api_key"] == "stv_from_dotenv"
    assert "alice" in output
