from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService


def test_card_action_button_sends_report_to_original_chat(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "daily-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            assert period == "daily"
            assert metric == "tokens"
            return SimpleNamespace(poster_path=poster, from_cache=False)

        def resolve_overview(self, *, metric: str = "tokens"):
            raise AssertionError(metric)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), report_cache=FakeCache())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command="daily", chat_id="oc_private"))

    assert response.toast.type == "info"
    assert "日报" in response.toast.content
    assert sent == [("oc_private", poster)]


def test_card_action_button_can_send_overview(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "overview-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            raise AssertionError(period)

        def resolve_overview(self, *, metric: str = "tokens"):
            assert metric == "quota"
            return SimpleNamespace(poster_path=poster, from_cache=True)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), report_cache=FakeCache())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command="quota_overview", chat_id="oc_private"))

    assert response.toast.type == "info"
    assert sent == [("oc_private", poster)]


def test_card_action_button_rejects_unknown_command() -> None:
    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

    service = FeishuBotService(feishu_client=FakeFeishuClient())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command="unknown", chat_id="oc_private"))

    assert response.toast.type == "warning"
    assert "无法识别" in response.toast.content


def test_card_action_button_rate_limits_same_chat(tmp_path: Path) -> None:
    current = 100.0
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "daily-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve(self, *, period: str, metric: str = "tokens"):
            return SimpleNamespace(poster_path=poster, from_cache=False)

        def resolve_overview(self, *, metric: str = "tokens"):
            raise AssertionError(metric)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )
    service.run_card_actions_async = False

    first = service.handle_card_action_trigger(_card_event(command="daily", chat_id="oc_private", message_id="om_first"))
    current = 104.9
    second = service.handle_card_action_trigger(_card_event(command="weekly", chat_id="oc_private", message_id="om_second"))

    assert first.toast.type == "info"
    assert second.toast.type == "warning"
    assert second.toast.content == "失败，两次请求至少间隔5s"
    assert sent == [("oc_private", poster)]


def _card_event(*, command: str, chat_id: str, message_id: str = "om_card"):
    return SimpleNamespace(
        event=SimpleNamespace(
            action=SimpleNamespace(value={"command": command}),
            context=SimpleNamespace(open_chat_id=chat_id, open_message_id=message_id),
        )
    )
