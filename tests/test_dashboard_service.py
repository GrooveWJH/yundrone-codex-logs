from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from switchbase_teamview.models import UsageResponse
import switchbase_teamview.dashboard as dashboard_module


def _usage_response(members: list[dict[str, object]]) -> UsageResponse:
    total_used_tokens = sum(int(member["used_tokens"]) for member in members)
    total_request_count = sum(int(member["request_count"]) for member in members)
    total_quota = sum(int(member["quota"]) for member in members)
    total_used_quota = sum(int(member["used_quota"]) for member in members)
    return UsageResponse.model_validate(
        {
            "success": True,
            "data": {
                "total_members": len(members),
                "total_quota": total_quota,
                "total_used_quota": total_used_quota,
                "total_used_tokens": total_used_tokens,
                "total_request_count": total_request_count,
                "members": members,
                "queried_at": 1776246798,
            },
        }
    )


def test_dashboard_service_applies_alias_and_last_7_days_window(tmp_path: Path) -> None:
    DashboardService = getattr(dashboard_module, "DashboardService", None)
    AliasStore = getattr(dashboard_module, "AliasStore", None)
    assert DashboardService is not None
    assert AliasStore is not None

    alias_file = tmp_path / "aliases.json"
    alias_file.write_text(json.dumps({"alice@example.com": "Alice Ops"}), encoding="utf-8")
    fixed_now = datetime(2026, 4, 15, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    seen_calls: list[tuple[int | None, int | None]] = []

    members = [
        {
            "newapi_user_id": 1,
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "role": "admin",
            "quota": 1000,
            "used_quota": 700,
            "request_count": 11,
            "used_tokens": 320,
            "user_group": "vip",
            "synced_at": 1776244478,
        },
        {
            "newapi_user_id": 2,
            "username": "bob",
            "display_name": "",
            "email": "bob@example.com",
            "role": "member",
            "quota": 800,
            "used_quota": 200,
            "request_count": 3,
            "used_tokens": 90,
            "user_group": "default",
            "synced_at": 1776244478,
        },
    ]

    class FakeClient:
        def get_usage(
            self,
            *,
            username: str | None = None,
            start_timestamp: int | None = None,
            end_timestamp: int | None = None,
        ) -> UsageResponse:
            seen_calls.append((start_timestamp, end_timestamp))
            return _usage_response(members)

    service = DashboardService(
        client_factory=lambda: FakeClient(),
        alias_store=AliasStore(alias_file),
        now_provider=lambda: fixed_now,
        ranking_ttl_seconds=60,
    )

    payload = service.get_dashboard(preset="last_7_days")
    expected_start = int((fixed_now - dashboard_module.timedelta(days=7)).timestamp())
    expected_end = int(fixed_now.timestamp())

    assert payload["meta"]["preset"] == "last_7_days"
    assert payload["members"][0]["display_name"] == "Alice Ops"
    assert payload["members"][1]["display_name"] == "bob"
    assert payload["summary"]["total_used_tokens"] == 410
    assert seen_calls == [(expected_start, expected_end)]


def test_dashboard_service_builds_rankings_with_fixed_windows_and_sorting(tmp_path: Path) -> None:
    DashboardService = getattr(dashboard_module, "DashboardService", None)
    AliasStore = getattr(dashboard_module, "AliasStore", None)
    assert DashboardService is not None
    assert AliasStore is not None

    fixed_now = datetime(2026, 4, 15, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    windows_seen: list[int] = []

    def usage_for_days(days: int) -> UsageResponse:
        if days == 1:
            members = [
                {
                    "newapi_user_id": 1,
                    "username": "alice",
                    "display_name": "Alice",
                    "email": "alice@example.com",
                    "role": "admin",
                    "quota": 1000,
                    "used_quota": 700,
                    "request_count": 5,
                    "used_tokens": 80,
                    "user_group": "vip",
                    "synced_at": 1776244478,
                },
                {
                    "newapi_user_id": 2,
                    "username": "bob",
                    "display_name": "Bob",
                    "email": "bob@example.com",
                    "role": "member",
                    "quota": 1000,
                    "used_quota": 500,
                    "request_count": 7,
                    "used_tokens": 110,
                    "user_group": "default",
                    "synced_at": 1776244478,
                },
            ]
        elif days == 7:
            members = [
                {
                    "newapi_user_id": 1,
                    "username": "alice",
                    "display_name": "Alice",
                    "email": "alice@example.com",
                    "role": "admin",
                    "quota": 1000,
                    "used_quota": 700,
                    "request_count": 20,
                    "used_tokens": 230,
                    "user_group": "vip",
                    "synced_at": 1776244478,
                },
                {
                    "newapi_user_id": 2,
                    "username": "bob",
                    "display_name": "Bob",
                    "email": "bob@example.com",
                    "role": "member",
                    "quota": 1000,
                    "used_quota": 500,
                    "request_count": 22,
                    "used_tokens": 420,
                    "user_group": "default",
                    "synced_at": 1776244478,
                },
            ]
        else:
            members = [
                {
                    "newapi_user_id": 1,
                    "username": "alice",
                    "display_name": "Alice",
                    "email": "alice@example.com",
                    "role": "admin",
                    "quota": 1000,
                    "used_quota": 700,
                    "request_count": 60,
                    "used_tokens": 900,
                    "user_group": "vip",
                    "synced_at": 1776244478,
                },
                {
                    "newapi_user_id": 2,
                    "username": "bob",
                    "display_name": "Bob",
                    "email": "bob@example.com",
                    "role": "member",
                    "quota": 1000,
                    "used_quota": 500,
                    "request_count": 50,
                    "used_tokens": 620,
                    "user_group": "default",
                    "synced_at": 1776244478,
                },
            ]
        return _usage_response(members)

    class FakeClient:
        def get_usage(
            self,
            *,
            username: str | None = None,
            start_timestamp: int | None = None,
            end_timestamp: int | None = None,
        ) -> UsageResponse:
            assert start_timestamp is not None
            assert end_timestamp is not None
            days = max(1, round((end_timestamp - start_timestamp) / 86400))
            windows_seen.append(days)
            return usage_for_days(days)

    service = DashboardService(
        client_factory=lambda: FakeClient(),
        alias_store=AliasStore(tmp_path / "aliases.json"),
        now_provider=lambda: fixed_now,
        ranking_ttl_seconds=60,
    )

    payload = service.get_rankings()

    assert windows_seen == [1, 7, 30]
    assert payload["daily"][0]["email"] == "bob@example.com"
    assert payload["weekly"][0]["email"] == "bob@example.com"
    assert payload["monthly"][0]["email"] == "alice@example.com"
    assert payload["monthly"][0]["used_tokens"] == 900


def test_dashboard_service_returns_single_public_ranking_bucket(tmp_path: Path) -> None:
    DashboardService = getattr(dashboard_module, "DashboardService", None)
    AliasStore = getattr(dashboard_module, "AliasStore", None)
    assert DashboardService is not None
    assert AliasStore is not None

    fixed_now = datetime(2026, 4, 15, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    class FakeClient:
        def get_usage(
            self,
            *,
            username: str | None = None,
            start_timestamp: int | None = None,
            end_timestamp: int | None = None,
        ) -> UsageResponse:
            return _usage_response(
                [
                    {
                        "newapi_user_id": 1,
                        "username": "alice",
                        "display_name": "Alice",
                        "email": "alice@example.com",
                        "role": "admin",
                        "quota": 1000,
                        "used_quota": 700,
                        "request_count": 20,
                        "used_tokens": 230,
                        "user_group": "vip",
                        "synced_at": 1776244478,
                    }
                ]
            )

    service = DashboardService(
        client_factory=lambda: FakeClient(),
        alias_store=AliasStore(tmp_path / "aliases.json"),
        now_provider=lambda: fixed_now,
        ranking_ttl_seconds=60,
    )

    payload = service.get_public_ranking("weekly")

    assert payload["ranking_type"] == "weekly"
    assert payload["items"][0]["email"] == "alice@example.com"
    assert payload["items"][0]["used_tokens"] == 230


def test_dashboard_service_from_env_loads_dotenv(monkeypatch, tmp_path: Path) -> None:
    DashboardService = getattr(dashboard_module, "DashboardService", None)
    assert DashboardService is not None

    seen: dict[str, object] = {}
    alias_file = tmp_path / "aliases.json"
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "SWITCHBASE_TEAMVIEW_API_KEY=stv_from_dotenv",
                f"SWITCHBASE_TEAMVIEW_ALIAS_FILE={alias_file}",
                "SWITCHBASE_TEAMVIEW_TIMEZONE=Asia/Shanghai",
                "SWITCHBASE_TEAMVIEW_RANKING_TTL=90",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_API_KEY", raising=False)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_ALIAS_FILE", raising=False)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_TIMEZONE", raising=False)
    monkeypatch.delenv("SWITCHBASE_TEAMVIEW_RANKING_TTL", raising=False)

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            seen["api_key"] = kwargs["api_key"]
            seen["base_url"] = kwargs["base_url"]

    monkeypatch.setattr(dashboard_module, "TeamViewClient", FakeClient)

    service = DashboardService.from_env()
    client = service.client_factory()

    assert seen["api_key"] == "stv_from_dotenv"
    assert service.alias_store.path == alias_file
    assert service.ranking_ttl_seconds == 90
    assert str(service.timezone) == "Asia/Shanghai"
    assert client is not None
