from __future__ import annotations

import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_cli_script_delegates_to_package_entry(monkeypatch) -> None:
    script = ROOT / "scripts" / "run_cli.py"
    assert script.exists()

    seen: dict[str, object] = {}

    def fake_run(argv=None) -> int:
        seen["argv"] = argv
        return 0

    monkeypatch.setattr("switchbase_teamview.cli.run", fake_run)

    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover - defensive path
        raise AssertionError("expected run_cli.py to exit via SystemExit")

    assert seen["argv"] is None


def test_run_api_script_delegates_to_package_entry(monkeypatch) -> None:
    script = ROOT / "scripts" / "run_api.py"
    assert script.exists()

    seen = {"called": False}

    def fake_main() -> None:
        seen["called"] = True

    monkeypatch.setattr("switchbase_teamview.api.main", fake_main)

    runpy.run_path(str(script), run_name="__main__")

    assert seen["called"] is True


def test_run_report_daemon_script_delegates_to_package_entry(monkeypatch) -> None:
    script = ROOT / "scripts" / "run_report_daemon.py"
    assert script.exists()

    seen = {"called": False}

    def fake_main() -> None:
        seen["called"] = True

    monkeypatch.setattr("switchbase_teamview.report_daemon.main", fake_main)

    runpy.run_path(str(script), run_name="__main__")

    assert seen["called"] is True


def test_run_feishu_group_reporter_script_delegates_to_package_entry(monkeypatch) -> None:
    script = ROOT / "scripts" / "run_feishu_group_reporter.py"
    assert script.exists()

    seen = {"called": False}

    def fake_main() -> None:
        seen["called"] = True

    monkeypatch.setattr("switchbase_teamview.feishu_group_reporter_main.main", fake_main)

    runpy.run_path(str(script), run_name="__main__")

    assert seen["called"] is True


def test_run_scripts_bootstrap_repo_root_before_importing_package() -> None:
    for rel in ("run_api.py", "run_report_daemon.py", "run_feishu_bot.py", "run_feishu_group_reporter.py"):
        script_text = (ROOT / "scripts" / rel).read_text(encoding="utf-8")
        assert "from scripts._bootstrap import ensure_repo_root_on_path" in script_text
        assert "ensure_repo_root_on_path()" in script_text


def test_fetch_server_reports_script_delegates_to_package_entry(monkeypatch) -> None:
    script = ROOT / "scripts" / "fetch_server_reports.py"
    assert script.exists()

    seen = {"called": False}

    def fake_main() -> None:
        seen["called"] = True

    monkeypatch.setattr("switchbase_teamview.report_fetch.main", fake_main)

    runpy.run_path(str(script), run_name="__main__")

    assert seen["called"] is True


def test_sensitive_templates_and_gitignore_exist() -> None:
    gitignore = ROOT / ".gitignore"
    env_template = ROOT / ".env.template"
    alias_template = ROOT / "teamview_aliases.template.json"

    assert gitignore.exists()
    assert env_template.exists()
    assert alias_template.exists()

    gitignore_text = gitignore.read_text(encoding="utf-8")
    assert ".env" in gitignore_text
    assert "teamview_aliases.json" in gitignore_text
    assert ".venv/" in gitignore_text
    assert "outputs/" in gitignore_text
    assert "tmp/" in gitignore_text
    assert ".claude/settings.local.json" in gitignore_text

    env_template_text = env_template.read_text(encoding="utf-8")
    assert "SWITCHBASE_TEAMVIEW_API_KEY=stv_your_api_key_here" in env_template_text
    assert "SWITCHBASE_TEAMVIEW_ALIAS_FILE=./teamview_aliases.json" in env_template_text
    assert "SWITCHBASE_TEAMVIEW_API_HOST=127.0.0.1" in env_template_text
    assert "SWITCHBASE_TEAMVIEW_API_PORT=8000" in env_template_text
    assert "SWITCHBASE_TEAMVIEW_WEB_HOST" not in env_template_text
    assert "SWITCHBASE_TEAMVIEW_WEB_PORT" not in env_template_text
    assert "FEISHU_REPORT_CHAT_ID=oc_your_group_chat_id_here" in env_template_text

    alias_payload = json.loads(alias_template.read_text(encoding="utf-8"))
    assert isinstance(alias_payload, dict)
    assert "member@example.com" in alias_payload


def test_repo_has_check_maxline_config() -> None:
    config_path = ROOT / ".codex" / "check-maxline.json"
    assert config_path.exists()

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["max_lines"] == 300
    assert "tests/test_dashboard_service.py" in payload["exclude_files"]


def test_repo_tracks_noto_sans_sc_fonts_with_git_lfs() -> None:
    attributes_path = ROOT / ".gitattributes"
    assert attributes_path.exists()

    attributes_text = attributes_path.read_text(encoding="utf-8")
    assert "assets/NotoSansSC/*.otf filter=lfs diff=lfs merge=lfs -text" in attributes_text


def test_pyproject_registers_report_daemon_script() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'teamview-report-daemon = "switchbase_teamview.report_daemon:main"' in pyproject
    assert 'teamview-feishu-group-reporter = "switchbase_teamview.feishu_group_reporter_main:main"' in pyproject
    assert 'packages = ["switchbase_teamview", "scripts"]' in pyproject


def test_feishu_systemd_unit_uses_module_mode_entrypoint() -> None:
    unit_text = (ROOT / "deploy" / "systemd" / "yundrone-codex-feishu-bot.service").read_text(encoding="utf-8")

    assert "ExecStart=/home/groove/apps/yundrone-codex-logs/.venv/bin/python -m scripts.run_feishu_bot" in unit_text


def test_feishu_group_reporter_systemd_unit_uses_module_mode_entrypoint() -> None:
    unit_text = (
        ROOT / "deploy" / "systemd" / "yundrone-codex-feishu-group-reporter.service"
    ).read_text(encoding="utf-8")

    assert (
        "ExecStart=/home/groove/apps/yundrone-codex-logs/.venv/bin/python -m scripts.run_feishu_group_reporter"
        in unit_text
    )
