from __future__ import annotations

import re
from typing import Literal

from scripts.poster.models import ReportMetric

Command = Literal[
    "daily",
    "weekly",
    "monthly",
    "overview",
    "quota_daily",
    "quota_weekly",
    "quota_monthly",
    "quota_overview",
    "intensity_daily",
    "intensity_weekly",
    "intensity_monthly",
    "intensity_overview",
    "help",
    "invalid",
]
Period = Literal["daily", "weekly", "monthly"]
USAGE_TEXT = "可发送：日报 / 周报 / 月报 / 总览 / quota日报 / quota / 成本强度日报 / 成本强度；仅 @ 机器人会返回帮助。"

COMMAND_ALIASES: dict[str, Command] = {
    "日报": "daily",
    "日榜": "daily",
    "daily": "daily",
    "1": "daily",
    "周报": "weekly",
    "周榜": "weekly",
    "weekly": "weekly",
    "月报": "monthly",
    "月榜": "monthly",
    "monthly": "monthly",
    "总览": "overview",
    "overview": "overview",
    "quota日报": "quota_daily",
    "quota 日报": "quota_daily",
    "quota日榜": "quota_daily",
    "2": "quota_daily",
    "quota周报": "quota_weekly",
    "quota 周报": "quota_weekly",
    "quota周榜": "quota_weekly",
    "quota月报": "quota_monthly",
    "quota 月报": "quota_monthly",
    "quota月榜": "quota_monthly",
    "quota": "quota_overview",
    "成本强度日报": "intensity_daily",
    "成本强度 日报": "intensity_daily",
    "3": "intensity_daily",
    "成本强度周报": "intensity_weekly",
    "成本强度 周报": "intensity_weekly",
    "成本强度月报": "intensity_monthly",
    "成本强度 月报": "intensity_monthly",
    "成本强度": "intensity_overview",
    "help": "help",
    "帮助": "help",
    "使用方法": "help",
    "?": "help",
}

FAILURE_LABELS: dict[Command, str] = {
    "daily": "日报",
    "weekly": "周报",
    "monthly": "月报",
    "overview": "总览",
    "quota_daily": "quota日报",
    "quota_weekly": "quota周报",
    "quota_monthly": "quota月报",
    "quota_overview": "quota总览",
    "intensity_daily": "成本强度日报",
    "intensity_weekly": "成本强度周报",
    "intensity_monthly": "成本强度月报",
    "intensity_overview": "成本强度总览",
    "help": "帮助",
    "invalid": "命令",
}

COMMAND_TARGETS: dict[Command, tuple[ReportMetric, Period | None]] = {
    "daily": ("tokens", "daily"),
    "weekly": ("tokens", "weekly"),
    "monthly": ("tokens", "monthly"),
    "overview": ("tokens", None),
    "quota_daily": ("quota", "daily"),
    "quota_weekly": ("quota", "weekly"),
    "quota_monthly": ("quota", "monthly"),
    "quota_overview": ("quota", None),
    "intensity_daily": ("intensity", "daily"),
    "intensity_weekly": ("intensity", "weekly"),
    "intensity_monthly": ("intensity", "monthly"),
    "intensity_overview": ("intensity", None),
}


def parse_command(text: str) -> Command:
    normalized = re.sub(r"@\S+", " ", text)
    normalized = " ".join(normalized.split()).strip().lower()
    if not normalized:
        return "help"
    return COMMAND_ALIASES.get(normalized, "invalid")


def is_report_command(command: Command) -> bool:
    return command in COMMAND_TARGETS
