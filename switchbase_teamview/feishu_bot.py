from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from switchbase_teamview.feishu_reports import FeishuReportCache

Period = Literal["daily", "weekly", "monthly"]
_DEDUP_TTL_SECONDS = 600.0

_PERIOD_KEYWORDS: list[tuple[Period, tuple[str, ...]]] = [
    ("daily", ("日报", "日榜", "daily")),
    ("weekly", ("周报", "周榜", "weekly")),
    ("monthly", ("月报", "月榜", "monthly")),
]

_PERIOD_LABELS: dict[Period, str] = {"daily": "日报", "weekly": "周报", "monthly": "月报"}


def parse_period_command(text: str) -> Period | None:
    normalized = text.strip().lower()
    for period, keywords in _PERIOD_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return period
    return None


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
        period = parse_period_command(_message_text(message.content or ""))
        if period is None:
            return False
        deduped = self._begin_message(message_id)
        if deduped:
            self._log(message_id=message_id, chat_id=message.chat_id, period=period, outcome=deduped)
            return True
        try:
            report = self.report_cache.resolve(period=period)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(message_id=message_id, chat_id=message.chat_id, period=period, outcome="failed-generate", error=exc)
            try:
                self.feishu_client.send_text_by_chat_id(
                    chat_id=message.chat_id,
                    text=f"{_PERIOD_LABELS[period]}生成失败，请稍后再试。",
                )
            except Exception as text_exc:
                self._log(
                    message_id=message_id,
                    chat_id=message.chat_id,
                    period=period,
                    outcome="failed-send-text",
                    error=text_exc,
                )
            return True
        try:
            self.feishu_client.send_image_by_chat_id(chat_id=message.chat_id, image_path=report.poster_path)
        except Exception as exc:
            self._finish_message(message_id, success=False)
            self._log(
                message_id=message_id,
                chat_id=message.chat_id,
                period=period,
                outcome="failed-send-image",
                error=exc,
            )
            return True
        self._finish_message(message_id, success=True)
        source = "cache-hit" if getattr(report, "from_cache", False) else "generated"
        self._log(message_id=message_id, chat_id=message.chat_id, period=period, outcome=source)
        return True

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
    def _log(*, message_id: str, chat_id: str, period: Period, outcome: str, error: Exception | None = None) -> None:
        suffix = f" error={type(error).__name__}: {error}" if error else ""
        print(
            f"[feishu-bot] message_id={message_id} chat_id={chat_id} period={period} outcome={outcome}{suffix}",
            flush=True,
        )


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
