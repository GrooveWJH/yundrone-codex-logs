from __future__ import annotations

import json
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateImageRequest
from lark_oapi.api.im.v1 import CreateImageRequestBody
from lark_oapi.api.im.v1 import CreateMessageRequest
from lark_oapi.api.im.v1 import CreateMessageRequestBody
from lark_oapi.api.im.v1 import CreateMessageReactionRequest
from lark_oapi.api.im.v1 import CreateMessageReactionRequestBody
from lark_oapi.api.im.v1 import DeleteMessageReactionRequest
from lark_oapi.api.im.v1 import Emoji

from switchbase_teamview.exceptions import TeamViewError


class FeishuClient:
    def __init__(self, *, app_id: str, app_secret: str, log_level: lark.LogLevel = lark.LogLevel.INFO) -> None:
        self._client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(log_level)
            .build()
        )

    def send_image_by_chat_id(self, *, chat_id: str, image_path: Path) -> None:
        image_key = self._upload_message_image(image_path)
        self._send_message(
            chat_id=chat_id,
            msg_type="image",
            content=json.dumps({"image_key": image_key}, ensure_ascii=False),
        )

    def send_text_by_chat_id(self, *, chat_id: str, text: str) -> None:
        self._send_message(
            chat_id=chat_id,
            msg_type="text",
            content=json.dumps({"text": text}, ensure_ascii=False),
        )

    def send_post_with_image_by_chat_id(
        self,
        *,
        chat_id: str,
        title: str,
        lines: list[str],
        image_path: Path,
    ) -> None:
        image_key = self._upload_message_image(image_path)
        self._send_message(
            chat_id=chat_id,
            msg_type="post",
            content=self._post_content(title=title, lines=lines, image_key=image_key),
        )

    def add_message_reaction(self, *, message_id: str, emoji_type: str) -> str:
        request = (
            CreateMessageReactionRequest.builder()
            .message_id(message_id)
            .request_body(
                CreateMessageReactionRequestBody.builder()
                .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message_reaction.create(request)
        if not response.success() or response.data is None or not response.data.reaction_id:
            raise TeamViewError(f"Feishu message reaction add failed: code={response.code}, msg={response.msg}")
        return response.data.reaction_id

    def delete_message_reaction(self, *, message_id: str, reaction_id: str) -> None:
        request = (
            DeleteMessageReactionRequest.builder()
            .message_id(message_id)
            .reaction_id(reaction_id)
            .build()
        )
        response = self._client.im.v1.message_reaction.delete(request)
        if not response.success():
            raise TeamViewError(f"Feishu message reaction delete failed: code={response.code}, msg={response.msg}")

    def _upload_message_image(self, image_path: Path) -> str:
        with image_path.open("rb") as image_file:
            request = CreateImageRequest.builder().request_body(
                CreateImageRequestBody.builder().image_type("message").image(image_file).build()
            ).build()
            response = self._client.im.v1.image.create(request)
        if not response.success() or response.data is None or not response.data.image_key:
            raise TeamViewError(f"Feishu image upload failed: code={response.code}, msg={response.msg}")
        return response.data.image_key

    def _send_message(self, *, chat_id: str, msg_type: str, content: str) -> None:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.create(request)
        if not response.success():
            raise TeamViewError(f"Feishu message send failed: code={response.code}, msg={response.msg}")

    @staticmethod
    def _post_content(*, title: str, lines: list[str], image_key: str) -> str:
        content: list[list[dict[str, str]]] = [[{"tag": "text", "text": line}] for line in lines if line.strip()]
        content.append([{"tag": "img", "image_key": image_key}])
        return json.dumps({"zh_cn": {"title": title, "content": content}}, ensure_ascii=False)
