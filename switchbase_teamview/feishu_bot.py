from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Literal

from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from switchbase_teamview.feishu_reports import FeishuReportCache

Command = Literal["daily", "weekly", "monthly", "overview", "invalid"]
Period = Literal["daily", "weekly", "monthly"]
_DEDUP_TTL_SECONDS = 600.0
_USAGE_TEXT = "可发送：日报 / 周报 / 月报 / 总览；仅 @ 机器人也会返回总览。"
_REACTION_IN_PROGRESS = "Alarm"
_REACTION_SUCCESS = "DONE"
_REACTION_INVALID = "THINKING"
_REACTION_FAILURE = "SWEAT"
_COMMAND_ALIASES: dict[str, Command] = {
    "日报": "daily",
    "日榜": "daily",
    "daily": "daily",
    "周报": "weekly",
    "周榜": "weekly",
    "weekly": "weekly",
    "月报": "monthly",
    "月榜": "monthly",
    "monthly": "monthly",
    "总览": "overview",
    "overview": "overview",
}
_FAILURE_LABELS: dict[Command, str] = {
    "daily": "日报",
    "weekly": "周报",
    "monthly": "月报",
    "overview": "总览",
    "invalid": "命令",
}


def parse_command(text: str) -> Command:
    normalized = _normalize_command_text(text)
    if not normalized:
        return "overview"
    return _COMMAND_ALIASES.get(normalized, "invalid")


class FeishuBotService:
    def __init__(
        self,
        *,
        feishu_client,
        output_dir: Path | None = None,
        report_cache: FeishuReportCache | None = None,
        time_provider=None,
    ) -> None:
        self.feishu_client = feishu_client
        self.output_dir = output_dir or (Path.cwd() / "outputs")
        self.report_cache = report_cache or FeishuReportCache(cache_dir=self.output_dir / "feishu-cache")
        self.time_provider = time_provider or time.monotonic
        self._inflight_message_ids: dict[str, float] = {}
        self._succeeded_message_ids: dict[str, float] = {}

    def handle_message_event(self, event: P2ImMessageReceiveV1) -> bool:
        message = getattr(getattr(event, "event", None), "message", None)
        if message is None or message.message_type != "text" or not message.chat_id:
            return False
        message_id = (message.message_id or "").strip()
        command = parse_command(_message_text(message.content or ""))
        deduped = self._begin_message(message_id)
        if deduped:
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome=deduped)
            return True
        alarm_reaction_id: str | None = None
        if command == "invalid":
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_INVALID, command=command)
            return self._reply_text(message_id=message_id, chat_id=message.chat_id, command=command, text=_USAGE_TEXT)
        alarm_reaction_id = self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_IN_PROGRESS, command=command)
        try:
            report = self.report_cache.resolve_overview() if command == "overview" else self.report_cache.resolve(period=command)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome="failed-generate", error=exc)
            self._transition_reaction(
                message_id=message_id,
                alarm_reaction_id=alarm_reaction_id,
                final_emoji=_REACTION_FAILURE,
                command=command,
            )
            return self._reply_text(
                message_id=message_id,
                chat_id=message.chat_id,
                command=command,
                text=f"{_FAILURE_LABELS[command]}生成失败，请稍后再试。",
                mark_success=False,
            )
        try:
            self.feishu_client.send_image_by_chat_id(chat_id=message.chat_id, image_path=report.poster_path)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome="failed-send-image", error=exc)
            self._transition_reaction(
                message_id=message_id,
                alarm_reaction_id=alarm_reaction_id,
                final_emoji=_REACTION_FAILURE,
                command=command,
            )
            return True
        self._finish_message(message_id, success=True)
        self._transition_reaction(
            message_id=message_id,
            alarm_reaction_id=alarm_reaction_id,
            final_emoji=_REACTION_SUCCESS,
            command=command,
        )
        source = "cache-hit" if getattr(report, "from_cache", False) else "generated"
        self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome=source)
        return True

    def _reply_text(self, *, message_id: str, chat_id: str, command: Command, text: str, mark_success: bool = True) -> bool:
        try:
            self.feishu_client.send_text_by_chat_id(chat_id=chat_id, text=text)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=chat_id, command=command, outcome="failed-send-text", error=exc)
            return True
        self._finish_message(message_id, success=mark_success)
        self._log(
            message_id=message_id,
            chat_id=chat_id,
            command=command,
            outcome="sent-text" if mark_success else "sent-text-retryable",
        )
        return True

    def _safe_add_reaction(self, *, message_id: str, emoji_type: str, command: Command) -> str | None:
        if not message_id:
            return None
        try:
            return self.feishu_client.add_message_reaction(message_id=message_id, emoji_type=emoji_type)
        except Exception as exc:
            self._log(message_id=message_id, chat_id="", command=command, outcome="failed-add-reaction", error=exc)
            return None

    def _safe_delete_reaction(self, *, message_id: str, reaction_id: str | None, command: Command) -> None:
        if not message_id or not reaction_id:
            return
        try:
            self.feishu_client.delete_message_reaction(message_id=message_id, reaction_id=reaction_id)
        except Exception as exc:
            self._log(message_id=message_id, chat_id="", command=command, outcome="failed-delete-reaction", error=exc)

    def _transition_reaction(self, *, message_id: str, alarm_reaction_id: str | None, final_emoji: str, command: Command) -> None:
        self._safe_delete_reaction(message_id=message_id, reaction_id=alarm_reaction_id, command=command)
        self._safe_add_reaction(message_id=message_id, emoji_type=final_emoji, command=command)

    def _begin_message(self, message_id: str) -> str | None:
        if not message_id:
            return None
        now = self.time_provider()
        self._prune_message_state(now)
        if message_id in self._inflight_message_ids:
            return "duplicate-inflight"
        if message_id in self._succeeded_message_ids:
            return "deduped-succeeded"
        self._inflight_message_ids[message_id] = now + _DEDUP_TTL_SECONDS
        return None

    def _finish_message(self, message_id: str, *, success: bool) -> None:
        if not message_id:
            return
        self._inflight_message_ids.pop(message_id, None)
        if success:
            self._succeeded_message_ids[message_id] = self.time_provider() + _DEDUP_TTL_SECONDS

    def _prune_message_state(self, now: float) -> None:
        self._inflight_message_ids = {
            message_id: expires_at for message_id, expires_at in self._inflight_message_ids.items() if expires_at > now
        }
        self._succeeded_message_ids = {
            message_id: expires_at for message_id, expires_at in self._succeeded_message_ids.items() if expires_at > now
        }

    @staticmethod
    def _log(*, message_id: str, chat_id: str, command: Command, outcome: str, error: Exception | None = None) -> None:
        suffix = f" error={type(error).__name__}: {error}" if error else ""
        print(f"[feishu-bot] message_id={message_id} chat_id={chat_id} command={command} outcome={outcome}{suffix}", flush=True)


def _normalize_command_text(text: str) -> str:
    normalized = re.sub(r"@\S+", " ", text)
    normalized = " ".join(normalized.split()).strip().lower()
    return normalized


def _message_text(raw_content: str) -> str:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return raw_content
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            return text
    return raw_content
