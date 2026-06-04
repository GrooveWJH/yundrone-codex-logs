from __future__ import annotations

import json
import math
import threading
import time
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTrigger
from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from switchbase_teamview.feishu_commands import FAILURE_LABELS
from switchbase_teamview.feishu_commands import TOKEN_USAGE_CARD_COMMAND
from switchbase_teamview.feishu_commands import USAGE_TEXT
from switchbase_teamview.feishu_commands import Command
from switchbase_teamview.feishu_commands import parse_command
from switchbase_teamview.feishu_message_filters import has_bot_mention
from switchbase_teamview.feishu_message_filters import is_at_all_message
from switchbase_teamview.feishu_message_filters import is_group_chat
from switchbase_teamview.feishu_message_filters import has_explicit_mentions
from switchbase_teamview.feishu_reports import FeishuReportCache

_DEDUP_TTL_SECONDS = 600.0
_REACTION_IN_PROGRESS = "Alarm"
_REACTION_SUCCESS = "DONE"
_REACTION_INVALID = "THINKING"
_REACTION_FAILURE = "SWEAT"
_MAINTENANCE_TEXT = "播报服务正在迁移升级中，请等待通知。"
_CARD_GENERATION_COOLDOWN_SECONDS = 10.0
_CARD_GENERATION_START_TEXT = "正在生成图片"
_CARD_GENERATION_BUSY_TEXT = "正在制作中，请勿重复请求"
_DEFAULT_BOT_NAMES = ("Codex用量报告",)
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


class FeishuBotService:
    def __init__(
        self,
        *,
        feishu_client,
        output_dir: Path | None = None,
        report_cache: FeishuReportCache | None = None,
        time_provider=None,
        bot_names: tuple[str, ...] | None = None,
    ) -> None:
        self.feishu_client = feishu_client
        self.output_dir = output_dir or (Path.cwd() / "outputs")
        self.report_cache = report_cache or FeishuReportCache(cache_dir=self.output_dir / "feishu-cache")
        self.time_provider = time_provider or time.monotonic
        self._inflight_message_ids: dict[str, float] = {}
        self._succeeded_message_ids: dict[str, float] = {}
        self._card_generation_lock = threading.Lock()
        self._card_generation_inflight = False
        self._card_generation_cooldown_until = 0.0
        self.bot_names = bot_names or _bot_names_from_env(os.getenv("FEISHU_BOT_NAMES", ""))
        self.run_card_actions_async = True
        self.maintenance_mode = _env_truthy(os.getenv("FEISHU_BOT_MAINTENANCE_MODE", ""))
        self.maintenance_text = os.getenv("FEISHU_BOT_MAINTENANCE_TEXT", _MAINTENANCE_TEXT).strip() or _MAINTENANCE_TEXT

    def handle_message_event(self, event: P2ImMessageReceiveV1) -> bool:
        message = getattr(getattr(event, "event", None), "message", None)
        if message is None or message.message_type != "text" or not message.chat_id:
            return False
        message_id = (message.message_id or "").strip()
        if is_at_all_message(message):
            self._log(message_id=message_id, chat_id=message.chat_id, command="help", outcome="ignored-at-all")
            return True
        if is_group_chat(message) and not has_bot_mention(message, bot_names=self.bot_names):
            self._log(message_id=message_id, chat_id=message.chat_id, command="help", outcome="ignored-not-mentioned")
            return False
        if self.maintenance_mode:
            if not has_explicit_mentions(message):
                self._log(message_id=message_id, chat_id=message.chat_id, command="help", outcome="ignored-not-mentioned")
                return False
            return self._reply_text(
                message_id=message_id,
                chat_id=message.chat_id,
                command="help",
                text=self.maintenance_text,
            )
        command = parse_command(_message_text(message.content or ""))
        deduped = self._begin_message(message_id)
        if deduped:
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome=deduped)
            return True
        alarm_reaction_id: str | None = None
        if command in {"invalid", "help"}:
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_INVALID, command=command)
            return self._reply_usage(message_id=message_id, chat_id=message.chat_id, command=command)
        slot_status, remaining_seconds = self._reserve_card_generation_slot()
        if slot_status == "busy":
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_FAILURE, command=command)
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome="busy")
            return self._reply_text(
                message_id=message_id,
                chat_id=message.chat_id,
                command=command,
                text=_CARD_GENERATION_BUSY_TEXT,
                mark_success=False,
            )
        if slot_status == "cooldown":
            self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_FAILURE, command=command)
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome="cooldown")
            return self._reply_text(
                message_id=message_id,
                chat_id=message.chat_id,
                command=command,
                text=f"请等待 {remaining_seconds} 秒冷却后再操作",
                mark_success=False,
            )
        alarm_reaction_id = self._safe_add_reaction(message_id=message_id, emoji_type=_REACTION_IN_PROGRESS, command=command)
        success = False
        try:
            report = self._resolve_message_report(command)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._finish_card_generation(success=False)
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
            if command == "report_pdf":
                self.feishu_client.send_file_by_chat_id(
                    chat_id=message.chat_id,
                    file_path=report.pdf_path,
                    file_name=_usage_report_pdf_name(),
                )
            else:
                self.feishu_client.send_image_by_chat_id(chat_id=message.chat_id, image_path=report.poster_path)
            success = True
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._finish_card_generation(success=False)
            outcome = "failed-send-file" if command == "report_pdf" else "failed-send-image"
            self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome=outcome, error=exc)
            self._transition_reaction(
                message_id=message_id,
                alarm_reaction_id=alarm_reaction_id,
                final_emoji=_REACTION_FAILURE,
                command=command,
            )
            return True
        self._finish_message(message_id, success=True)
        self._finish_card_generation(success=success)
        self._transition_reaction(
            message_id=message_id,
            alarm_reaction_id=alarm_reaction_id,
            final_emoji=_REACTION_SUCCESS,
            command=command,
        )
        source = "cache-hit" if getattr(report, "from_cache", False) else "generated"
        self._log(message_id=message_id, chat_id=message.chat_id, command=command, outcome=source)
        return True

    def _resolve_message_report(self, command: Command):
        if command == "report_pdf":
            return self.report_cache.resolve_trio_pdf(metric="tokens")
        return self.report_cache.resolve_trio(metric="tokens")

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
        if not chat_id or command != TOKEN_USAGE_CARD_COMMAND:
            return _card_toast("warning", "无法识别按钮命令，请 @ 机器人发送 help。")
        if self.maintenance_mode:
            self._log(message_id="card-action", chat_id=chat_id, command=command, outcome="maintenance-toast")
            return _card_toast("info", self.maintenance_text)
        slot_status, remaining_seconds = self._reserve_card_generation_slot()
        if slot_status == "busy":
            self._log(message_id="card-action", chat_id=chat_id, command=command, outcome="busy-toast")
            return _card_toast("warning", _CARD_GENERATION_BUSY_TEXT)
        if slot_status == "cooldown":
            self._log(message_id="card-action", chat_id=chat_id, command=command, outcome="cooldown-toast")
            return _card_toast("warning", f"请等待 {remaining_seconds} 秒冷却后再操作")
        if self.run_card_actions_async:
            threading.Thread(target=self._send_card_trio_report, args=(chat_id,), daemon=True).start()
        else:
            self._send_card_trio_report(chat_id)
        return _card_toast("info", _CARD_GENERATION_START_TEXT)

    def _send_card_trio_report(self, chat_id: str) -> None:
        success = False
        try:
            report = self.report_cache.resolve_trio(metric="tokens")
            self.feishu_client.send_image_by_chat_id(chat_id=chat_id, image_path=report.poster_path)
            success = True
        except Exception as exc:
            self._log(
                message_id="card-action",
                chat_id=chat_id,
                command=TOKEN_USAGE_CARD_COMMAND,
                outcome="failed-card-action",
                error=exc,
            )
        finally:
            self._finish_card_generation(success=success)
        if not success:
            return
        source = "cache-hit" if getattr(report, "from_cache", False) else "generated"
        self._log(
            message_id="card-action",
            chat_id=chat_id,
            command=TOKEN_USAGE_CARD_COMMAND,
            outcome=f"card-{source}",
        )

    def _reserve_card_generation_slot(self) -> tuple[str, int]:
        now = self.time_provider()
        with self._card_generation_lock:
            if self._card_generation_inflight:
                return "busy", 0
            remaining = self._card_generation_cooldown_until - now
            if remaining > 0:
                return "cooldown", max(1, math.ceil(remaining))
            self._card_generation_inflight = True
        return "ok", 0

    def _finish_card_generation(self, *, success: bool) -> None:
        with self._card_generation_lock:
            self._card_generation_inflight = False
            if success:
                self._card_generation_cooldown_until = self.time_provider() + _CARD_GENERATION_COOLDOWN_SECONDS

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
    def _log(*, message_id: str, chat_id: str, command: str, outcome: str, error: Exception | None = None) -> None:
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


def _env_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bot_names_from_env(value: str) -> tuple[str, ...]:
    names = tuple(name.strip() for name in value.replace(";", ",").split(",") if name.strip())
    return names or _DEFAULT_BOT_NAMES


def _usage_report_pdf_name(now: datetime | None = None) -> str:
    current = now or datetime.now(_TZ_SHANGHAI)
    return f"用量报告-{current.astimezone(_TZ_SHANGHAI).strftime('%Y%m%d%H%M%S')}.pdf"


def _card_action_command(event: P2CardActionTrigger) -> str:
    value = getattr(getattr(getattr(event, "event", None), "action", None), "value", None)
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, str):
            return command
    return "invalid"


def _card_action_chat_id(event: P2CardActionTrigger) -> str:
    context = getattr(getattr(event, "event", None), "context", None)
    chat_id = getattr(context, "open_chat_id", None)
    return chat_id if isinstance(chat_id, str) else ""


def _card_toast(toast_type: str, content: str) -> P2CardActionTriggerResponse:
    return P2CardActionTriggerResponse({"toast": {"type": toast_type, "content": content}})
