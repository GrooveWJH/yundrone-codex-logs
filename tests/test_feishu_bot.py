from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from switchbase_teamview.feishu_bot import parse_period_command
from tests.feishu_test_utils import message_event


def test_parse_period_command_matches_daily_weekly_monthly_keywords() -> None:
    assert parse_period_command("@Codex用量报告 日报") == "daily"
    assert parse_period_command("请发周报") == "weekly"
    assert parse_period_command("月报") == "monthly"
    assert parse_period_command("hello world") is None


def test_handle_message_event_uploads_poster_and_sends_image_reply(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:  # pragma: no cover - defensive path
            raise AssertionError(text)

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    poster = outputs / "daily-poster.png"
    poster.write_bytes(b"png")

    class FakeCache:
        def resolve(self, *, period: str):
            assert period == "daily"
            return SimpleNamespace(period=period, poster_path=poster)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=outputs, report_cache=FakeCache())

    handled = service.handle_message_event(message_event(text="@Codex用量报告 日报"))

    assert handled is True
    assert sent == [("oc_test_chat", poster)]


def test_handle_message_event_sends_fallback_text_when_poster_missing(tmp_path: Path) -> None:
    sent_text: list[tuple[str, str]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent_text.append((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            assert period == "weekly"
            raise FileNotFoundError(period)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
    )

    handled = service.handle_message_event(message_event(text="周报"))

    assert handled is True
    assert sent_text == [("oc_test_chat", "周报生成失败，请稍后再试。")]


def test_handle_message_event_ignores_unrecognized_text(tmp_path: Path) -> None:
    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, text))

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs")

    handled = service.handle_message_event(message_event(text="随便聊聊"))

    assert handled is False


def test_handle_message_event_reuses_same_minute_cached_report(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "daily-202604161223-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)
            return SimpleNamespace(period=period, poster_path=poster)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
    )

    assert service.handle_message_event(message_event(text="日报", message_id="om_first")) is True
    assert service.handle_message_event(message_event(text="@Codex用量报告 日报", message_id="om_second")) is True
    assert resolves == ["daily", "daily"]
    assert sent == [("oc_test_chat", poster), ("oc_test_chat", poster)]


def test_handle_message_event_deduplicates_repeated_message_id(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "daily-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)
            return SimpleNamespace(period=period, poster_path=poster, from_cache=True)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
    )
    event = message_event(text="@Codex用量报告 日报", message_id="om_duplicate")

    assert service.handle_message_event(event) is True
    assert service.handle_message_event(event) is True

    assert resolves == ["daily"]
    assert sent == [("oc_test_chat", poster)]


def test_handle_message_event_allows_same_message_id_after_dedup_ttl(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    current = 100.0
    poster = tmp_path / "outputs" / "feishu-cache" / "daily-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:  # pragma: no cover - defensive path
            raise AssertionError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)
            return SimpleNamespace(period=period, poster_path=poster, from_cache=False)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )
    event = message_event(text="日报", message_id="om_expiring")

    assert service.handle_message_event(event) is True
    current = 1000.0
    assert service.handle_message_event(event) is True

    assert resolves == ["daily", "daily"]
    assert sent == [("oc_test_chat", poster), ("oc_test_chat", poster)]

