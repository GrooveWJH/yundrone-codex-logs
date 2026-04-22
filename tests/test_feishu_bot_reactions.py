from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from switchbase_teamview.feishu_bot import parse_command
from tests.feishu_test_utils import message_event


def test_parse_command_matches_supported_keywords_and_invalid_cases() -> None:
    assert parse_command("@Codex用量报告 日报") == "daily"
    assert parse_command("周报") == "weekly"
    assert parse_command("月报") == "monthly"
    assert parse_command("总览") == "overview"
    assert parse_command("@Codex用量报告") == "overview"
    assert parse_command("   ") == "overview"
    assert parse_command("日报月报周报") == "invalid"
    assert parse_command("请发周报") == "invalid"
    assert parse_command("hello world") == "invalid"


def test_handle_message_event_uploads_poster_and_sends_image_reply(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError(text)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    poster = tmp_path / "outputs" / "daily-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")

    class FakeCache:
        def resolve(self, *, period: str):
            assert period == "daily"
            return SimpleNamespace(period=period, poster_path=poster)

        def resolve_overview(self):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告 日报")) is True
    assert sent == [("oc_test_chat", poster)]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "DONE"),
    ]


def test_handle_message_event_sends_fallback_text_when_poster_missing(tmp_path: Path) -> None:
    sent_text: list[tuple[str, str]] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent_text.append((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str):
            assert period == "weekly"
            raise FileNotFoundError(period)

        def resolve_overview(self):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="周报")) is True
    assert sent_text == [("oc_test_chat", "周报生成失败，请稍后再试。")]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "SWEAT"),
    ]


def test_handle_message_event_sends_usage_for_invalid_text(tmp_path: Path) -> None:
    sent_text: list[tuple[str, str]] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent_text.append((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_invalid"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            raise AssertionError((message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str):
            raise AssertionError(period)

        def resolve_overview(self):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="随便聊聊")) is True
    assert sent_text == [("oc_test_chat", "可发送：日报 / 周报 / 月报 / 总览；仅 @ 机器人也会返回总览。")]
    assert reactions == [("add", "om_test_message", "THINKING")]


def test_handle_message_event_sends_usage_for_ambiguous_multi_command_text(tmp_path: Path) -> None:
    sent_text: list[str] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent_text.append(text)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_invalid"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            raise AssertionError((message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str):
            raise AssertionError(period)

        def resolve_overview(self):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="日报月报周报")) is True
    assert sent_text == ["可发送：日报 / 周报 / 月报 / 总览；仅 @ 机器人也会返回总览。"]
    assert reactions == [("add", "om_test_message", "THINKING")]


def test_handle_message_event_sends_overview_when_message_is_only_mention(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    reactions: list[tuple[str, str, str]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "overview-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str):
            raise AssertionError(period)

        def resolve_overview(self):
            return SimpleNamespace(kind="overview", poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告")) is True
    assert sent == [("oc_test_chat", poster)]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "DONE"),
    ]


def test_handle_message_event_sends_overview_when_text_is_explicit_overview(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    reactions: list[tuple[str, str, str]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "overview-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str):
            raise AssertionError(period)

        def resolve_overview(self):
            return SimpleNamespace(kind="overview", poster_path=poster, from_cache=True)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="总览")) is True
    assert sent == [("oc_test_chat", poster)]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "DONE"),
    ]
