from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from tests.feishu_test_utils import message_event


def test_handle_message_event_reuses_same_minute_cached_report(tmp_path: Path) -> None:
    current = 100.0
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "trio-202604161223-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

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
        def resolve_trio(self, *, metric: str):
            resolves.append(metric)
            return SimpleNamespace(poster_path=poster)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )

    assert service.handle_message_event(message_event(text="报告", chat_type="p2p", message_id="om_first")) is True
    current = 110.0
    assert service.handle_message_event(message_event(text="@Codex用量报告 报告", message_id="om_second")) is True
    assert resolves == ["tokens", "tokens"]
    assert sent == [("oc_test_chat", poster), ("oc_test_chat", poster)]


def test_handle_message_event_deduplicates_repeated_message_id(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "outputs" / "feishu-cache" / "trio-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

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
        def resolve_trio(self, *, metric: str):
            resolves.append(metric)
            return SimpleNamespace(poster_path=poster, from_cache=True)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())
    event = message_event(text="@Codex用量报告 报告", message_id="om_duplicate")

    assert service.handle_message_event(event) is True
    assert service.handle_message_event(event) is True
    assert resolves == ["tokens"]
    assert sent == [("oc_test_chat", poster)]


def test_handle_message_event_allows_same_message_id_after_dedup_ttl(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    current = 100.0
    poster = tmp_path / "outputs" / "feishu-cache" / "trio-poster.png"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    resolves: list[str] = []

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
        def resolve_trio(self, *, metric: str):
            resolves.append(metric)
            return SimpleNamespace(poster_path=poster, from_cache=False)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )
    event = message_event(text="报告", chat_type="p2p", message_id="om_expiring")

    assert service.handle_message_event(event) is True
    current = 1000.0
    assert service.handle_message_event(event) is True
    assert resolves == ["tokens", "tokens"]
    assert sent == [("oc_test_chat", poster), ("oc_test_chat", poster)]
