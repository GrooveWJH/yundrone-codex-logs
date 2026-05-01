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

    def send_usage_help_by_chat_id(self, *, chat_id: str) -> None:
        self._send_message(chat_id=chat_id, msg_type="interactive", content=self._usage_help_content())

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

    @staticmethod
    def _usage_help_content() -> str:
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "Codex 用量报告使用方法"}},
            "elements": [
                {"tag": "markdown", "content": "**点击按钮或 @ 机器人发送表格里的完整命令都可以生成报告。仅 @ 或发送空格，会返回本帮助。**"},
                {
                    "tag": "table",
                    "columns": [
                        {"name": "type", "display_name": "系列", "data_type": "text"},
                        {"name": "daily", "display_name": "日", "data_type": "text"},
                        {"name": "weekly", "display_name": "周", "data_type": "text"},
                        {"name": "monthly", "display_name": "月", "data_type": "text"},
                        {"name": "overview", "display_name": "总览", "data_type": "text"},
                    ],
                    "rows": [
                        {"type": "Token", "daily": "日报", "weekly": "周报", "monthly": "月报", "overview": "总览"},
                        {"type": "Quota", "daily": "quota日报", "weekly": "quota周报", "monthly": "quota月报", "overview": "quota"},
                        {
                            "type": "Intensity",
                            "daily": "成本强度日报",
                            "weekly": "成本强度周报",
                            "monthly": "成本强度月报",
                            "overview": "成本强度",
                        },
                    ],
                },
                {"tag": "action", "actions": _command_buttons("Token", ["日", "周", "月", "总"])},
                {"tag": "action", "actions": _command_buttons("Quota", ["日", "周", "月", "总"])},
                {"tag": "action", "actions": _command_buttons("Intensity", ["日", "周", "月", "总"])},
            ],
        }
        return json.dumps(card, ensure_ascii=False)


def _command_buttons(series: str, labels: list[str]) -> list[dict[str, object]]:
    series_button = {
        "tag": "button",
        "text": {"tag": "plain_text", "content": series},
        "type": "primary",
        "value": {"command": _button_command(series, "总")},
    }
    period_buttons = [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": label},
            "type": "default",
            "value": {"command": _button_command(series, label)},
        }
        for label in labels
    ]
    return [series_button, *period_buttons]


def _button_command(series: str, label: str) -> str:
    prefixes = {"Token": "", "Quota": "quota_", "Intensity": "intensity_"}
    suffixes = {"日": "daily", "周": "weekly", "月": "monthly", "总": "overview"}
    return f"{prefixes[series]}{suffixes[label]}"
