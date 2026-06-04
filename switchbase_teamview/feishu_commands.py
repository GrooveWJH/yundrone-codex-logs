from __future__ import annotations

import re
from typing import Literal

Command = Literal["report", "report_pdf", "help", "invalid"]
TOKEN_USAGE_CARD_COMMAND = "token_usage_trio"
USAGE_TEXT = "可发送：报告。其他内容会返回使用方法卡片。"

COMMAND_ALIASES: dict[str, Command] = {
    "报告": "report",
    "报告pdf": "report_pdf",
    "报告 pdf": "report_pdf",
    "help": "help",
    "帮助": "help",
    "使用方法": "help",
    "?": "help",
}

FAILURE_LABELS: dict[Command, str] = {
    "report": "报告",
    "report_pdf": "PDF报告",
    "help": "帮助",
    "invalid": "命令",
}


def parse_command(text: str) -> Command:
    normalized = re.sub(r"<at\b[^>]*>.*?</at>", " ", text)
    normalized = re.sub(r"@\S+", " ", normalized)
    normalized = " ".join(normalized.split()).strip().lower()
    if not normalized:
        return "help"
    return COMMAND_ALIASES.get(normalized, "invalid")


def is_report_command(command: Command) -> bool:
    return command == "report"
