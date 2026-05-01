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
    assert parse_command("1") == "daily"
    assert parse_command("quota日报") == "quota_daily"
    assert parse_command("quota 周报") == "quota_weekly"
    assert parse_command("quota") == "quota_overview"
    assert parse_command("2") == "quota_daily"
    assert parse_command("成本强度日报") == "intensity_daily"
    assert parse_command("成本强度 月报") == "intensity_monthly"
    assert parse_command("成本强度") == "intensity_overview"
    assert parse_command("3") == "intensity_daily"
    assert parse_command("help") == "help"
    assert parse_command("帮助") == "help"
    assert parse_command("@Codex用量报告") == "help"
    assert parse_command("   ") == "help"
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
        def resolve(self, *, period: str, metric: str = "tokens"):
            assert period == "daily"
            assert metric == "tokens"
            return SimpleNamespace(period=period, poster_path=poster)

        def resolve_overview(self, *, metric: str = "tokens"):
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
        def resolve(self, *, period: str, metric: str = "tokens"):
            assert period == "weekly"
            assert metric == "tokens"
            raise FileNotFoundError(period)

        def resolve_overview(self, *, metric: str = "tokens"):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="周报")) is True
    assert sent_text == [("oc_test_chat", "周报生成失败，请稍后再试。")]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "SWEAT"),
    ]


def test_handle_message_event_sends_rich_usage_for_invalid_and_help(tmp_path: Path) -> None:
    sent_help: list[str] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_usage_help_by_chat_id(self, *, chat_id: str) -> None:
            sent_help.append(chat_id)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_invalid"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            raise AssertionError((message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            raise AssertionError(period)

        def resolve_overview(self, *, metric: str = "tokens"):
            raise AssertionError("unexpected overview")

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    for text, message_id in [("随便聊聊", "om_invalid"), ("日报月报周报", "om_ambiguous"), ("帮助", "om_help")]:
        assert service.handle_message_event(message_event(text=text, message_id=message_id)) is True

    assert sent_help == ["oc_test_chat", "oc_test_chat", "oc_test_chat"]
    assert reactions == [
        ("add", "om_invalid", "THINKING"),
        ("add", "om_ambiguous", "THINKING"),
        ("add", "om_help", "THINKING"),
    ]


def test_handle_message_event_sends_help_when_message_is_only_mention(tmp_path: Path) -> None:
    sent_help: list[str] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_usage_help_by_chat_id(self, *, chat_id: str) -> None:
            sent_help.append(chat_id)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_invalid"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            raise AssertionError((message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            raise AssertionError(period)

        def resolve_overview(self, *, metric: str = "tokens"):
            assert metric == "tokens"
            return SimpleNamespace(kind="overview", poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告")) is True
    assert sent_help == ["oc_test_chat"]
    assert reactions == [("add", "om_test_message", "THINKING")]


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
        def resolve(self, *, period: str, metric: str = "tokens"):
            raise AssertionError(period)

        def resolve_overview(self, *, metric: str = "tokens"):
            assert metric == "tokens"
            return SimpleNamespace(kind="overview", poster_path=poster, from_cache=True)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="总览")) is True
    assert sent == [("oc_test_chat", poster)]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "DONE"),
    ]


def test_handle_message_event_routes_quota_and_intensity_commands(tmp_path: Path) -> None:
    current = 100.0
    sent: list[tuple[str, Path]] = []
    calls: list[tuple[str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            return None

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            calls.append((period, metric))
            poster = tmp_path / f"{period}-{metric}.png"
            poster.write_bytes(b"png")
            return SimpleNamespace(period=period, poster_path=poster, from_cache=False)

        def resolve_overview(self, *, metric: str = "tokens"):
            calls.append(("overview", metric))
            poster = tmp_path / f"overview-{metric}.png"
            poster.write_bytes(b"png")
            return SimpleNamespace(period="overview", poster_path=poster, from_cache=False)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )

    assert service.handle_message_event(message_event(text="quota日报", message_id="om_quota_daily")) is True
    current = 105.0
    assert service.handle_message_event(message_event(text="成本强度", message_id="om_intensity")) is True

    assert calls == [("daily", "quota"), ("overview", "intensity")]
    assert len(sent) == 2
