from __future__ import annotations

import httpx

import switchbase_teamview.client as client_module


USAGE_RESPONSE = {
    "success": True,
    "data": {
        "total_members": 2,
        "total_quota": 3000,
        "total_used_quota": 1200,
        "total_used_tokens": 20,
        "total_request_count": 2,
        "members": [
            {
                "newapi_user_id": 101,
                "username": "alice",
                "display_name": "Alice",
                "email": "alice@example.com",
                "role": "admin",
                "quota": 1000,
                "used_quota": 500,
                "request_count": 2,
                "used_tokens": 20,
                "user_group": "default",
                "synced_at": 1776168000,
            },
            {
                "newapi_user_id": 102,
                "username": "bob",
                "display_name": "Bob",
                "email": "bob@example.com",
                "role": "member",
                "quota": 2000,
                "used_quota": 700,
                "request_count": 0,
                "used_tokens": 0,
                "user_group": "default",
                "synced_at": 1776168000,
            },
        ],
        "queried_at": 1775976210,
    },
}

LOGS_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {
                "id": 25807,
                "time": 1775904951,
                "username": "groove",
                "model": "gpt-5.3-codex",
                "token_name": None,
                "prompt_tokens": 100000,
                "completion_tokens": 57829,
                "total_tokens": 157829,
                "quota": 123,
                "quota_usd": "0.028492",
                "use_time_seconds": 1.25,
                "is_stream": True,
                "request_id": "req_123",
            }
        ]
    },
}


def test_usage_query_uses_header_auth_and_parses_members() -> None:
    TeamViewClient = getattr(client_module, "TeamViewClient", None)
    assert TeamViewClient is not None

    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["url"] = str(request.url)
        seen_request["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=USAGE_RESPONSE)

    client = TeamViewClient(
        api_key="stv_test_key",
        base_url="https://team.switchbase.vip",
        transport=httpx.MockTransport(handler),
    )

    response = client.get_usage(username="alice", start_timestamp=1712800000, end_timestamp=1712809999)

    assert response.success is True
    assert response.data.total_members == 2
    assert response.data.members[0].username == "alice"
    assert seen_request["api_key"] == "stv_test_key"
    assert seen_request["url"] == (
        "https://team.switchbase.vip/api/external/usage"
        "?username=alice&start_timestamp=1712800000&end_timestamp=1712809999"
    )


def test_logs_query_passes_filters_and_parses_items() -> None:
    TeamViewClient = getattr(client_module, "TeamViewClient", None)
    assert TeamViewClient is not None

    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["url"] = str(request.url)
        return httpx.Response(200, json=LOGS_RESPONSE)

    client = TeamViewClient(
        api_key="stv_test_key",
        base_url="https://team.switchbase.vip",
        transport=httpx.MockTransport(handler),
    )

    response = client.get_logs(
        username="groove",
        model_name="gpt-5.3-codex",
        start_timestamp=1712800000,
        end_timestamp=1712809999,
        page=1,
        size=10,
        log_type=2,
    )

    assert response.data.items[0].model == "gpt-5.3-codex"
    assert response.data.items[0].quota_usd == "0.028492"
    assert seen_request["url"] == (
        "https://team.switchbase.vip/api/external/logs"
        "?username=groove&model_name=gpt-5.3-codex&start_timestamp=1712800000"
        "&end_timestamp=1712809999&p=1&size=10&type=2"
    )


def test_api_error_response_raises_domain_exception() -> None:
    TeamViewClient = getattr(client_module, "TeamViewClient", None)
    TeamViewAPIError = getattr(client_module, "TeamViewAPIError", None)
    assert TeamViewClient is not None
    assert TeamViewAPIError is not None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "message": "bad key"})

    client = TeamViewClient(
        api_key="stv_test_key",
        base_url="https://team.switchbase.vip",
        transport=httpx.MockTransport(handler),
    )

    try:
        client.get_usage()
    except Exception as exc:  # pragma: no cover - assertion path
        assert isinstance(exc, TeamViewAPIError)
        assert "bad key" in str(exc)
    else:  # pragma: no cover - assertion path
        raise AssertionError("expected TeamViewAPIError")
