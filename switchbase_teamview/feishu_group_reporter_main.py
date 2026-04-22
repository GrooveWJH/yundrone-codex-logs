from __future__ import annotations

import os
from pathlib import Path

from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError
from switchbase_teamview.feishu_client import FeishuClient
from switchbase_teamview.feishu_group_reporter import FeishuGroupReporter
from switchbase_teamview.feishu_bot_main import _log_level_from_env


def main() -> None:
    load_project_env()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    chat_id = os.getenv("FEISHU_REPORT_CHAT_ID")
    if not app_id or not app_secret:
        raise TeamViewError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")
    if not chat_id:
        raise TeamViewError("Missing FEISHU_REPORT_CHAT_ID")
    output_dir = Path(os.getenv("SWITCHBASE_TEAMVIEW_OUTPUT_DIR", "outputs"))
    log_level = _log_level_from_env(os.getenv("FEISHU_LOG_LEVEL", "INFO"))
    reporter = FeishuGroupReporter(
        feishu_client=FeishuClient(app_id=app_id, app_secret=app_secret, log_level=log_level),
        chat_id=chat_id,
        output_dir=output_dir,
    )
    print(
        f"[feishu-group-reporter] starting chat_id={chat_id} outputs={output_dir.resolve()} log_level={log_level.name}",
        flush=True,
    )
    reporter.run_forever()
