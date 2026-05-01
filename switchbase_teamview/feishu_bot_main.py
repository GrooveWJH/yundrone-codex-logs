from __future__ import annotations

import os
from pathlib import Path

import lark_oapi as lark

from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError
from switchbase_teamview.feishu_bot import FeishuBotService
from switchbase_teamview.feishu_client import FeishuClient


def main() -> None:
    load_project_env()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise TeamViewError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")
    output_dir = Path(os.getenv("SWITCHBASE_TEAMVIEW_OUTPUT_DIR", "outputs"))
    log_level = _log_level_from_env(os.getenv("FEISHU_LOG_LEVEL", "INFO"))
    service = FeishuBotService(
        feishu_client=FeishuClient(app_id=app_id, app_secret=app_secret, log_level=log_level),
        output_dir=output_dir,
    )
    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(service.handle_message_event)
        .register_p2_card_action_trigger(service.handle_card_action_trigger)
        .build()
    )
    print(
        f"[feishu-bot] starting long connection outputs={output_dir.resolve()} log_level={log_level.name}",
        flush=True,
    )
    lark.ws.Client(app_id, app_secret, event_handler=handler, log_level=log_level).start()


def _log_level_from_env(value: str) -> lark.LogLevel:
    levels = {
        "CRITICAL": lark.LogLevel.CRITICAL,
        "ERROR": lark.LogLevel.ERROR,
        "WARNING": lark.LogLevel.WARNING,
        "INFO": lark.LogLevel.INFO,
        "DEBUG": lark.LogLevel.DEBUG,
    }
    return levels.get(value.strip().upper(), lark.LogLevel.INFO)
