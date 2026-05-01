from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from tests.feishu_test_utils import message_event


def test_handle_message_event_rate_limits_reports_per_chat(tmp_path: Path) -> None:
    current = 100.0
    sent: list[tuple[str, Path]] = []
    sent_text: list[tuple[str, str]] = []
    calls: list[str] = []
    reactions: list[tuple[str, str, str]] = []
    poster = tmp_path / "daily.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent_text.append((chat_id, text))

        def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
            reactions.append(("add", message_id, emoji_type))
            return "reaction_alarm"

        def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
            reactions.append(("delete", message_id, reaction_id))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            calls.append(period)
            return SimpleNamespace(period=period, poster_path=poster, from_cache=False)

        def resolve_overview(self, *, metric: str = "tokens"):
            raise AssertionError(metric)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )

    assert service.handle_message_event(message_event(text="日报", message_id="om_first")) is True
    current = 104.9
    assert service.handle_message_event(message_event(text="周报", message_id="om_second")) is True
    current = 105.0
    assert service.handle_message_event(message_event(text="日报", message_id="om_third")) is True

    assert calls == ["daily", "daily"]
    assert sent == [("oc_test_chat", poster), ("oc_test_chat", poster)]
    assert sent_text == [("oc_test_chat", "失败，两次请求至少间隔5s")]
    assert ("add", "om_second", "SWEAT") in reactions
