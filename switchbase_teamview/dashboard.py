"""Dashboard service and whitelist persistence for the TeamView board."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from switchbase_teamview.client import TeamViewClient
from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError
from switchbase_teamview.models import UsageMember, UsageResponse
from switchbase_teamview.rankings import RankingScope, apply_ranking_scope, resolve_ranking_window, validate_ranking_scope
from switchbase_teamview.whitelist import WhitelistEntry, WhitelistStore, match_whitelist_entry

DEFAULT_TIMEZONE = "Asia/Shanghai"
RANKING_TIMEZONE = "Asia/Shanghai"
DEFAULT_WHITELIST_FILE = "teamview_whitelist.json"

class DashboardService:
    """Aggregate TeamView usage into dashboard-friendly payloads."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] | None = None,
        whitelist_store: WhitelistStore | None = None,
        timezone: str = DEFAULT_TIMEZONE,
        now_provider: Callable[[], datetime] | None = None,
        ranking_ttl_seconds: int = 60,
    ) -> None:
        self.timezone = ZoneInfo(timezone)
        self.ranking_timezone = ZoneInfo(RANKING_TIMEZONE)
        self.now_provider = now_provider or (lambda: datetime.now(self.timezone))
        self.client_factory = client_factory or self._default_client_factory
        self.whitelist_store = whitelist_store or WhitelistStore(Path(DEFAULT_WHITELIST_FILE))
        self.ranking_ttl_seconds = ranking_ttl_seconds
        self._ranking_cache: tuple[float, dict[str, Any]] | None = None

    @classmethod
    def from_env(cls) -> "DashboardService":
        load_project_env()
        whitelist_file = Path(os.getenv("SWITCHBASE_TEAMVIEW_WHITELIST_FILE", DEFAULT_WHITELIST_FILE))
        timezone = os.getenv("SWITCHBASE_TEAMVIEW_TIMEZONE", DEFAULT_TIMEZONE)
        ttl = int(os.getenv("SWITCHBASE_TEAMVIEW_RANKING_TTL", "60"))
        return cls(
            whitelist_store=WhitelistStore(whitelist_file),
            timezone=timezone,
            ranking_ttl_seconds=ttl,
        )

    def get_dashboard(
        self,
        *,
        preset: str | None = "today",
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
    ) -> dict[str, Any]:
        window = self._resolve_window(
            preset=preset,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        usage = self._fetch_usage(start_timestamp=window["start_timestamp"], end_timestamp=window["end_timestamp"])
        members = self._transform_members(usage.data.members)
        return {
            "meta": window,
            "summary": {
                "total_members": usage.data.total_members,
                "total_quota": usage.data.total_quota,
                "total_used_quota": usage.data.total_used_quota,
                "total_window_used_quota": usage.data.total_window_used_quota,
                "total_used_tokens": usage.data.total_used_tokens,
                "total_request_count": usage.data.total_request_count,
                "queried_at": usage.data.queried_at,
            },
            "members": members,
        }

    def get_rankings(self) -> dict[str, list[dict[str, Any]]]:
        now = time.time()
        if self._ranking_cache and self._ranking_cache[0] > now:
            return self._ranking_cache[1]

        payload = {
            "daily": self._ranking_for_window("daily"),
            "weekly": self._ranking_for_window("weekly"),
            "monthly": self._ranking_for_window("monthly"),
        }
        self._ranking_cache = (now + self.ranking_ttl_seconds, payload)
        return payload

    def get_public_ranking(self, ranking_type: str) -> dict[str, Any]:
        return self.build_natural_ranking(scope="filtered", ranking_type=ranking_type, limit=10)

    def build_natural_ranking(
        self,
        *,
        scope: RankingScope,
        ranking_type: str,
        limit: int,
    ) -> dict[str, Any]:
        window = self._resolve_ranking_window(ranking_type)
        return self.build_ranking(
            scope=scope,
            ranking_type=ranking_type,
            start_timestamp=int(window["start_timestamp"]),
            end_timestamp=int(window["end_timestamp"]),
            limit=limit,
        )

    def build_ranking(
        self,
        *,
        scope: RankingScope,
        ranking_type: str,
        start_timestamp: int,
        end_timestamp: int,
        limit: int,
    ) -> dict[str, Any]:
        validate_ranking_scope(scope)
        if ranking_type not in {"daily", "weekly", "monthly"}:
            raise TeamViewError(f"Unsupported ranking_type: {ranking_type}")
        if start_timestamp > end_timestamp:
            raise TeamViewError("start_timestamp must be less than or equal to end_timestamp")
        if start_timestamp == end_timestamp:
            return {"scope": scope, "ranking_type": ranking_type, "items": [], "generated_at": end_timestamp}
        usage = self._fetch_usage(start_timestamp=start_timestamp, end_timestamp=end_timestamp)
        ranked = self._transform_members(usage.data.members)
        scoped_items = apply_ranking_scope(ranked, scope)
        return {
            "scope": scope,
            "ranking_type": ranking_type,
            "items": scoped_items[:limit],
            "generated_at": end_timestamp,
        }

    def get_windowed_ranking(
        self,
        *,
        ranking_type: str,
        start_timestamp: int,
        end_timestamp: int,
        scope: RankingScope = "filtered",
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.build_ranking(
            scope=scope,
            ranking_type=ranking_type,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit,
        )

    def _default_client_factory(self) -> TeamViewClient:
        api_key = os.getenv("SWITCHBASE_TEAMVIEW_API_KEY")
        if not api_key:
            raise TeamViewError("Missing API key. Set SWITCHBASE_TEAMVIEW_API_KEY.")
        base_url = os.getenv("SWITCHBASE_TEAMVIEW_BASE_URL", "https://team.switchbase.vip")
        return TeamViewClient(api_key=api_key, base_url=base_url)

    def _fetch_usage(self, *, start_timestamp: int, end_timestamp: int) -> UsageResponse:
        client = self.client_factory()
        try:
            return client.get_usage(start_timestamp=start_timestamp, end_timestamp=end_timestamp)
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _ranking_for_window(self, ranking_type: str) -> list[dict[str, Any]]:
        window = self._resolve_ranking_window(ranking_type)
        return self.build_ranking(
            scope="filtered",
            ranking_type=ranking_type,
            start_timestamp=int(window["start_timestamp"]),
            end_timestamp=int(window["end_timestamp"]),
            limit=10,
        )["items"]

    def _transform_members(self, members: list[UsageMember]) -> list[dict[str, Any]]:
        whitelist = self.whitelist_store.load()
        ranked = [
            self._member_payload(member, whitelist=whitelist)
            for member in members
        ]
        ranked.sort(key=lambda item: (-item["used_tokens"], item["email"], item["username"]))
        return ranked

    @staticmethod
    def _member_payload(
        member: UsageMember,
        *,
        whitelist: dict[str, WhitelistEntry],
    ) -> dict[str, Any]:
        whitelist_entry = match_whitelist_entry(member, whitelist)
        alias = whitelist_entry.alias if whitelist_entry else ""
        return {
            "email": member.email,
            "display_name": alias or member.display_name.strip() or member.username.strip() or member.email.strip(),
            "alias": alias,
            "username": member.username,
            "raw_display_name": member.display_name,
            "role": member.role,
            "user_group": member.user_group,
            "request_count": member.request_count,
            "used_tokens": member.used_tokens,
            "used_quota": member.used_quota,
            "window_used_quota": member.window_used_quota,
            "quota": member.quota,
            "newapi_user_id": member.newapi_user_id,
            "synced_at": member.synced_at,
            "whitelisted": bool(whitelist_entry and whitelist_entry.include),
        }

    def _resolve_ranking_window(self, ranking_type: str) -> dict[str, int | str]:
        return resolve_ranking_window(ranking_type=ranking_type, now=self.now_provider().astimezone(self.ranking_timezone))

    def _resolve_window(
        self,
        *,
        preset: str | None = None,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
    ) -> dict[str, Any]:
        now = self.now_provider().astimezone(self.timezone)
        if start_timestamp is not None or end_timestamp is not None:
            if start_timestamp is None or end_timestamp is None:
                raise TeamViewError("Custom range requires both start_timestamp and end_timestamp")
            if start_timestamp >= end_timestamp:
                raise TeamViewError("start_timestamp must be less than end_timestamp")
            return {
                "preset": "custom",
                "label": "自定义",
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
            }

        chosen = preset or "today"
        if chosen == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            label = "今天"
        elif chosen == "last_7_days":
            start = now - timedelta(days=7)
            label = "近7天"
        elif chosen == "last_30_days":
            start = now - timedelta(days=30)
            label = "近30天"
        elif chosen == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            label = "本月"
        elif chosen == "last_month":
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = current_month_start
            last_month_start = (current_month_start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return {"preset": chosen, "label": "上月", "start_timestamp": int(last_month_start.timestamp()), "end_timestamp": int(last_month_end.timestamp())}
        else:
            raise TeamViewError(f"Unsupported preset: {chosen}")

        return {
            "preset": chosen,
            "label": label,
            "start_timestamp": int(start.timestamp()),
            "end_timestamp": int(now.timestamp()),
        }
