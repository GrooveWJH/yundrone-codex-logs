from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from switchbase_teamview.feishu_bot import parse_command
from tests.feishu_test_utils import message_event

def test_parse_command_matches_supported_keywords_and_invalid_cases() -> None:
    assert parse_command("@Codex用量报告 报告") == "report"
    assert parse_command("报告") == "report"
    assert parse_command("@Codex用量报告 报告pdf") == "report_pdf"
    assert parse_command("报告 pdf") == "report_pdf"
    assert parse_command("help") == "help"
    assert parse_command("帮助") == "help"
    assert parse_command("@Codex用量报告") == "help"
    assert parse_command("   ") == "help"
    assert parse_command("日报") == "invalid"
    assert parse_command("周报") == "invalid"
    assert parse_command("月报") == "invalid"
    assert parse_command("1") == "invalid"
    assert parse_command("总览") == "invalid"
    assert parse_command("quota日报") == "invalid"
    assert parse_command("quota 周报") == "invalid"
    assert parse_command("quota") == "invalid"
    assert parse_command("2") == "invalid"
    assert parse_command("成本强度日报") == "invalid"
    assert parse_command("成本强度 月报") == "invalid"
    assert parse_command("成本强度") == "invalid"
    assert parse_command("3") == "invalid"
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

    poster = tmp_path / "outputs" / "trio-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            assert metric == "tokens"
            return SimpleNamespace(poster_path=poster)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告 报告")) is True
    assert sent == [("oc_test_chat", poster)]
    assert reactions == [
        ("add", "om_test_message", "Alarm"),
        ("delete", "om_test_message", "reaction_alarm"),
        ("add", "om_test_message", "DONE"),
    ]


def test_handle_message_event_sends_hidden_pdf_report(tmp_path: Path) -> None:
    sent_files: list[tuple[str, Path, str]] = []
    reactions: list[tuple[str, str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_file_by_chat_id(self, *, chat_id: str, file_path: Path, file_name: str) -> None:
            sent_files.append((chat_id, file_path, file_name))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError(text)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    pdf_path = tmp_path / "outputs" / "trio-poster.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

        def resolve_trio_pdf(self, *, metric: str):
            assert metric == "tokens"
            return SimpleNamespace(pdf_path=pdf_path, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告 报告pdf")) is True
    assert len(sent_files) == 1
    assert sent_files[0][0] == "oc_test_chat"
    assert sent_files[0][1] == pdf_path
    assert sent_files[0][2].startswith("用量报告-")
    assert sent_files[0][2].endswith(".pdf")
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
        def resolve_trio(self, *, metric: str):
            assert metric == "tokens"
            raise FileNotFoundError(metric)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="报告", chat_type="p2p")) is True
    assert sent_text == [("oc_test_chat", "报告生成失败，请稍后再试。")]
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
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    for text, message_id in [("随便聊聊", "om_invalid"), ("日报月报周报", "om_ambiguous"), ("帮助", "om_help")]:
        assert service.handle_message_event(message_event(text=text, chat_type="p2p", message_id=message_id)) is True

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
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())

    assert service.handle_message_event(message_event(text="@Codex用量报告")) is True
    assert sent_help == ["oc_test_chat"]
    assert reactions == [("add", "om_test_message", "THINKING")]


def test_handle_message_event_treats_overview_quota_and_intensity_as_invalid(tmp_path: Path) -> None:
    sent_help: list[str] = []
    reactions: list[tuple[str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_usage_help_by_chat_id(self, *, chat_id: str) -> None:
            sent_help.append(chat_id)

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append((message_id, emoji_type))
            return "reaction_invalid"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            raise AssertionError((message_id, reaction_id))

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
    )

    for text, message_id in [("总览", "om_overview"), ("quota日报", "om_quota"), ("成本强度", "om_intensity")]:
        assert service.handle_message_event(message_event(text=text, chat_type="p2p", message_id=message_id)) is True

    assert sent_help == ["oc_test_chat", "oc_test_chat", "oc_test_chat"]
    assert reactions == [
        ("om_overview", "THINKING"),
        ("om_quota", "THINKING"),
        ("om_intensity", "THINKING"),
    ]
