from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from switchbase_teamview.exceptions import TeamViewError

RankingScope = Literal["filtered", "all-members"]


def validate_ranking_scope(scope: RankingScope) -> None:
    if scope not in {"filtered", "all-members"}:
        raise TeamViewError(f"Unsupported ranking scope: {scope}")


def apply_ranking_scope(items: list[dict[str, object]], scope: RankingScope) -> list[dict[str, object]]:
    if scope == "all-members":
        return items
    return [item for item in items if is_filtered_ranking_member(str(item.get("email") or ""))]


def is_filtered_ranking_member(email: str) -> bool:
    normalized = email.strip().lower()
    return normalized.endswith("@yundrone.cn") and normalized != "codex@yundrone.cn"


def resolve_ranking_window(*, ranking_type: str, now: datetime) -> dict[str, int | str]:
    if ranking_type == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif ranking_type == "weekly":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_start - timedelta(days=now.weekday())
    elif ranking_type == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise TeamViewError(f"Unsupported ranking_type: {ranking_type}")

    return {
        "ranking_type": ranking_type,
        "start_timestamp": int(start.timestamp()),
        "end_timestamp": int(now.timestamp()),
    }
