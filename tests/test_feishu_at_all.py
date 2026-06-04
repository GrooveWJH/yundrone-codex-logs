from __future__ import annotations

import os
from pathlib import Path

from switchbase_teamview.feishu_bot import FeishuBotService
from tests.feishu_test_utils import message_event


def test_handle_message_event_ignores_at_all_by_user_id(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(
        message_event(
            text="@所有人 报告",
            mentions=[{"name": "所有人", "id": {"user_id": "all"}}],
        )
    )

    assert handled is True
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_handle_message_event_ignores_at_all_by_open_id(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(
        message_event(
            text="@所有人 报告",
            mentions=[{"name": "所有人", "id": {"open_id": "all"}}],
        )
    )

    assert handled is True
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_handle_message_event_ignores_at_all_by_name_only(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(
        message_event(text="@所有人 报告", mentions=[{"name": "所有人", "id": {"open_id": "ou_any"}}])
    )

    assert handled is True
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_handle_message_event_ignores_at_all_by_full_member_name(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(
        message_event(text="@全体成员 报告", mentions=[{"name": "全体成员", "id": {"open_id": "ou_any"}}])
    )

    assert handled is True
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_handle_message_event_ignores_at_all_by_content_fallback(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(
        message_event(
            text="ignored",
            raw_content='{"text":"<at user_id=\\"all\\">所有人</at> 报告"}',
        )
    )

    assert handled is True
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_handle_message_event_ignores_group_report_without_bot_mention(tmp_path: Path) -> None:
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled = service.handle_message_event(message_event(text="报告", chat_type="group", message_id="om_plain_group"))

    assert handled is False
    assert seen == {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def test_maintenance_mode_replies_only_when_explicitly_mentioned(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FEISHU_BOT_MAINTENANCE_MODE", "1")
    monkeypatch.setenv("FEISHU_BOT_MAINTENANCE_TEXT", "播报服务正在迁移升级中，请等待通知。")
    seen = _capture()
    service = FeishuBotService(feishu_client=_client(seen), output_dir=tmp_path / "outputs", report_cache=_cache())

    handled_plain = service.handle_message_event(message_event(text="报告", chat_type="group", message_id="om_plain"))
    handled_at_all = service.handle_message_event(
        message_event(
            text="@所有人 报告",
            message_id="om_at_all",
            mentions=[{"name": "所有人", "id": {"user_id": "all"}}],
        )
    )
    handled_at_bot = service.handle_message_event(
        message_event(
            text="@Codex用量报告 报告",
            message_id="om_at_bot",
            mentions=[{"name": "Codex用量报告", "id": {"open_id": "ou_bot"}}],
        )
    )

    assert handled_plain is False
    assert handled_at_all is True
    assert handled_at_bot is True
    assert seen["text"] == [("oc_test_chat", "播报服务正在迁移升级中，请等待通知。")]
    assert seen["image"] == []
    assert seen["help"] == []
    assert seen["resolve"] == []
    monkeypatch.delenv("FEISHU_BOT_MAINTENANCE_MODE", raising=False)
    monkeypatch.delenv("FEISHU_BOT_MAINTENANCE_TEXT", raising=False)


def _capture() -> dict[str, list[object]]:
    return {"image": [], "text": [], "help": [], "reaction": [], "resolve": []}


def _client(seen: dict[str, list[object]]):
    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            seen["image"].append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            seen["text"].append((chat_id, text))

        def send_usage_help_by_chat_id(self, *, chat_id: str) -> None:
            seen["help"].append(chat_id)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            seen["reaction"].append((message_id, emoji_type))
            return "reaction_any"

    return FakeFeishuClient()


def _cache():
    class FakeCache:
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

    return FakeCache()
