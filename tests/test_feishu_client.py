from __future__ import annotations

import json
from pathlib import Path

from switchbase_teamview.feishu_client import FeishuClient


def test_send_post_with_image_builds_single_post_message(tmp_path: Path) -> None:
    seen: dict[str, object] = {}
    image_path = tmp_path / "poster.png"
    image_path.write_bytes(b"png")

    class FakeFeishuClient(FeishuClient):
        def __init__(self) -> None:
            pass

        def _upload_message_image(self, value: Path) -> str:
            seen["upload_path"] = value
            return "img_v3_key"

        def _send_message(self, *, chat_id: str, msg_type: str, content: str) -> None:
            seen["chat_id"] = chat_id
            seen["msg_type"] = msg_type
            seen["content"] = json.loads(content)

    client = FakeFeishuClient()
    client.send_post_with_image_by_chat_id(
        chat_id="oc_private",
        title="Codex 用量播报",
        lines=["以下为今日总览", "日报：昨天完整 24h"],
        image_path=image_path,
    )

    assert seen["upload_path"] == image_path
    assert seen["chat_id"] == "oc_private"
    assert seen["msg_type"] == "post"
    assert seen["content"] == {
        "zh_cn": {
            "title": "Codex 用量播报",
            "content": [
                [{"tag": "text", "text": "以下为今日总览"}],
                [{"tag": "text", "text": "日报：昨天完整 24h"}],
                [{"tag": "img", "image_key": "img_v3_key"}],
            ],
        }
    }


def test_add_and_delete_message_reaction_build_requests() -> None:
    seen: dict[str, object] = {}

    class FakeReactionAPI:
        def create(self, request):
            seen["create_message_id"] = request.message_id
            seen["create_emoji"] = request.request_body.reaction_type.emoji_type
            return type(
                "Response",
                (),
                {"success": lambda self: True, "code": 0, "msg": "ok", "data": type("Data", (), {"reaction_id": "reaction_123"})()},
            )()

        def delete(self, request):
            seen["delete_message_id"] = request.message_id
            seen["delete_reaction_id"] = request.reaction_id
            return type("Response", (), {"success": lambda self: True, "code": 0, "msg": "ok"})()

    class FakeClient(FeishuClient):
        def __init__(self) -> None:
            self._client = type("SDK", (), {"im": type("IM", (), {"v1": type("V1", (), {"message_reaction": FakeReactionAPI()})()})()})()

    client = FakeClient()

    reaction_id = client.add_message_reaction(message_id="om_test", emoji_type="Alarm")
    client.delete_message_reaction(message_id="om_test", reaction_id="reaction_123")

    assert reaction_id == "reaction_123"
    assert seen == {
        "create_message_id": "om_test",
        "create_emoji": "Alarm",
        "delete_message_id": "om_test",
        "delete_reaction_id": "reaction_123",
    }
