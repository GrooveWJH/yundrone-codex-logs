from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from switchbase_teamview.feishu_bot import FeishuBotService
from tests.feishu_test_utils import message_event


def _poster(tmp_path: Path, name: str = "daily-poster.png") -> Path:
    poster = tmp_path / "outputs" / "feishu-cache" / name
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"png")
    return poster


def test_retries_same_message_id_after_image_send_failure(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = _poster(tmp_path, "monthly-poster.png")
    resolves: list[str] = []
    attempts = {"count": 0}

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("send image failed")
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)
            return SimpleNamespace(period=period, poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())
    event = message_event(text="月报", message_id="om_retry_after_send_failure")

    assert service.handle_message_event(event) is True
    assert service.handle_message_event(event) is True
    assert resolves == ["monthly", "monthly"]
    assert sent == [("oc_test_chat", poster)]


def test_retries_same_message_id_after_generate_failure(tmp_path: Path) -> None:
    sent: list[tuple[str, Path]] = []
    poster = _poster(tmp_path, "weekly-poster.png")
    resolves: list[str] = []
    attempts = {"count": 0}

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            sent.append((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            sent.append((chat_id, Path(text)))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("generate failed")
            return SimpleNamespace(period=period, poster_path=poster, from_cache=False)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())
    event = message_event(text="周报", message_id="om_retry_after_generate_failure")

    assert service.handle_message_event(event) is True
    assert service.handle_message_event(event) is True
    assert resolves == ["weekly", "weekly"]
    assert sent[-1] == ("oc_test_chat", poster)


def test_fallback_text_failure_does_not_mark_success(tmp_path: Path) -> None:
    attempts = {"count": 0}

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            attempts["count"] += 1
            raise RuntimeError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            raise FileNotFoundError(period)

    service = FeishuBotService(feishu_client=FakeFeishuClient(), output_dir=tmp_path / "outputs", report_cache=FakeCache())
    event = message_event(text="周报", message_id="om_fallback_failure")

    assert service.handle_message_event(event) is True
    assert service.handle_message_event(event) is True
    assert attempts["count"] == 2


def test_short_circuits_when_message_is_inflight(tmp_path: Path) -> None:
    resolves: list[str] = []

    class FakeFeishuClient:
        def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
            raise AssertionError((chat_id, image_path))

        def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
            raise AssertionError((chat_id, text))

    class FakeCache:
        def resolve(self, *, period: str):
            resolves.append(period)

    service = FeishuBotService(
        feishu_client=FakeFeishuClient(),
        output_dir=tmp_path / "outputs",
        report_cache=FakeCache(),
        time_provider=lambda: 100.0,
    )
    service._inflight_message_ids["om_inflight"] = 999.0

    assert service.handle_message_event(message_event(text="日报", message_id="om_inflight")) is True
    assert resolves == []
