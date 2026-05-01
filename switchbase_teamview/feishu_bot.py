from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from switchbase_teamview.feishu_commands import COMMAND_TARGETS
from switchbase_teamview.feishu_commands import FAILURE_LABELS
from switchbase_teamview.feishu_commands import USAGE_TEXT
from switchbase_teamview.feishu_commands import Command
from switchbase_teamview.feishu_commands import is_report_command
from switchbase_teamview.feishu_commands import parse_command
from switchbase_teamview.feishu_reports import FeishuReportCache

_DEDUP_TTL_SECONDS = 600.0
_REACTION_IN_PROGRESS = "Alarm"
_REACTION_SUCCESS = "DONE"
_REACTION_INVALID = "THINKING"
_REACTION_FAILURE = "SWEAT"
_RATE_LIMIT_SECONDS = 5.0
_RATE_LIMIT_TEXT = "失败，两次请求至少间隔5s"


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
        self._last_report_request_at: dict[str, tuple[float, str]] = {}
        self._rate_limit_lock = threading.Lock()
        self.run_card_actions_async = True

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
        if command in {"invalid", "help"}:
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_INVALID, command=command)
            return self._reply_usage(message_id=message_id, chat_id=message.chat_id, command=command)
        if not self._reserve_report_slot(message.chat_id, message_id):
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_FAILURE, command=command)
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome="rate-limited")
            return self._reply_text(
                message_id=message_id,
                chat_id=message.chat_id,
                command=command,
                text=_RATE_LIMIT_TEXT,
            )
        alarm_reaction_id = self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_IN_PROGRESS, command=command)
        try:
            metric, period = COMMAND_TARGETS[command]
            report = self.report_cache.resolve_overview(metric=metric) if period is None else self.report_cache.resolve(period=period, metric=metric)
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
                text=f"{FAILURE_LABELS[command]}生成失败，请稍后再试。",
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

    def _reply_usage(self, *, message_id: str, chat_id: str, command: Command) -> bool:
        try:
            sender = getattr(self.feishu_client, "send_usage_help_by_chat_id", None)
            if callable(sender):
                sender(chat_id=chat_id)
            else:
                self.feishu_client.send_text_by_chat_id(chat_id=chat_id, text=USAGE_TEXT)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=chat_id, command=command, outcome="failed-send-text", error=exc)
            return True
        self._finish_message(message_id, success=True)
        self._log(message_id=message_id, chat_id=chat_id, command=command, outcome="sent-help")
        return True

    def handle_card_action_trigger(self, event: P2CardActionTrigger) -> P2CardActionTriggerResponse:
        command = _card_action_command(event)
        chat_id = _card_action_chat_id(event)
        action_id = _card_action_id(event)
        if not chat_id or not is_report_command(command):
            return _card_toast("warning", "无法识别按钮命令，请 @ 机器人发送 help。")
        if not self._reserve_report_slot(chat_id, action_id):
            self._log(message_id="card-action", chat_id=chat_id, command=command, outcome="rate-limited")
            return _card_toast("warning", _RATE_LIMIT_TEXT)
        if self.run_card_actions_async:
            threading.Thread(target=self._send_card_report, args=(chat_id, command), daemon=True).start()
        else:
            self._send_card_report(chat_id, command)
        return _card_toast("info", f"收到，正在生成 {FAILURE_LABELS[command]}。")

    def _send_card_report(self, chat_id: str, command: Command) -> None:
        try:
            metric, period = COMMAND_TARGETS[command]
            report = self.report_cache.resolve_overview(metric=metric) if period is None else self.report_cache.resolve(period=period, metric=metric)
            self.feishu_client.send_image_by_chat_id(chat_id=chat_id, image_path=report.poster_path)
        except Exception as exc:
            self._log(message_id="card-action", chat_id=chat_id, command=command, outcome="failed-card-action", error=exc)
            return
        source = "cache-hit" if getattr(report, "from_cache", False) else "generated"
        self._log(message_id="card-action", chat_id=chat_id, command=command, outcome=f"card-{source}")

    def _reserve_report_slot(self, chat_id: str, request_id: str) -> bool:
        now = self.time_provider()
        with self._rate_limit_lock:
            last = self._last_report_request_at.get(chat_id)
            if last is not None and request_id and request_id == last[1]:
                return True
            if last is not None and now - last[0] < _RATE_LIMIT_SECONDS:
                return False
            self._last_report_request_at[chat_id] = (now, request_id)
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


def _card_action_command(event: P2CardActionTrigger) -> Command:
    value = getattr(getattr(getattr(event, "event", None), "action", None), "value", None)
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, str):
            return command if is_report_command(command) else "invalid"
    return "invalid"


def _card_action_chat_id(event: P2CardActionTrigger) -> str:
    context = getattr(getattr(event, "event", None), "context", None)
    chat_id = getattr(context, "open_chat_id", None)
    return chat_id if isinstance(chat_id, str) else ""


def _card_action_id(event: P2CardActionTrigger) -> str:
    context = getattr(getattr(event, "event", None), "context", None)
    message_id = getattr(context, "open_message_id", None)
    return message_id if isinstance(message_id, str) else ""


def _card_toast(toast_type: str, content: str) -> P2CardActionTriggerResponse:
    return P2CardActionTriggerResponse({"toast": {"type": toast_type, "content": content}})
