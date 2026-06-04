from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from switchbase_teamview.feishu_commands import TOKEN_USAGE_CARD_COMMAND


def test_card_action_button_sends_trio_report_to_original_chat(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "trio-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            assert metric == "tokens"
            return SimpleNamespace(poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), report_cache=FakeCache())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_private"))

    assert response.toast.type == "info"
    assert response.toast.content == "正在生成图片"
    assert sent == [("oc_private", poster)]


def test_card_action_button_rejects_old_daily_button_command(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            raise AssertionError(metric)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), report_cache=FakeCache())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command="daily", chat_id="oc_private"))

    assert response.toast.type == "warning"
    assert "无法识别" in response.toast.content
    assert sent == []


def test_card_action_button_rejects_unknown_command() -> None:
    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

    service = FeishuBotService(feishu_client=FakeFeishuClient())
    service.run_card_actions_async = False

    response = service.handle_card_action_trigger(_card_event(command="unknown", chat_id="oc_private"))

    assert response.toast.type == "warning"
    assert "无法识别" in response.toast.content


def test_card_action_button_blocks_parallel_generation(tmp_path: Path) -> None:
    release = threading.Event()
    started = threading.Event()
    poster = tmp_path / "trio-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            assert image_path == poster

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            started.set()
            release.wait(timeout=5)
            return SimpleNamespace(poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), report_cache=FakeCache())
    service.run_card_actions_async = True

    first = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_first"))
    assert started.wait(timeout=5) is True
    second = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_second"))
    release.set()

    assert first.toast.type == "info"
    assert first.toast.content == "正在生成图片"
    assert second.toast.type == "warning"
    assert second.toast.content == "正在制作中，请勿重复请求"


def test_card_action_button_cools_down_after_success(tmp_path: Path) -> None:
    current = 100.0
    sent: list[tuple[str, Path]] = []
    poster = tmp_path / "trio-poster.png"
    poster.write_bytes(b"png")

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

    class FakeCache:
        def resolve_trio(self, *, metric: str):
            return SimpleNamespace(poster_path=poster, from_cache=False)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        report_cache=FakeCache(),
        time_provider=lambda: current,
    )
    service.run_card_actions_async = False

    first = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_first"))
    current = 104.1
    second = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_second"))
    current = 110.0
    third = service.handle_card_action_trigger(_card_event(command=TOKEN_USAGE_CARD_COMMAND, chat_id="oc_third"))

    assert first.toast.type == "info"
    assert second.toast.type == "warning"
    assert second.toast.content == "请等待 6 秒冷却后再操作"
    assert third.toast.type == "info"
    assert sent == [("oc_first", poster), ("oc_third", poster)]


def _card_event(*, command: str, chat_id: str, message_id: str = "om_card"):
    return SimpleNamespace(
        event=SimpleNamespace(
            action=SimpleNamespace(value={"command": command}),
            context=SimpleNamespace(open_chat_id=chat_id, open_message_id=message_id),
        )
    )
