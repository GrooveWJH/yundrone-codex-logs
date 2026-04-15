from __future__ import annotations

from fastapi.testclient import TestClient

import switchbase_teamview.web as web_module


def test_web_app_serves_dashboard_page_and_api_routes() -> None:
    create_app = getattr(web_module, "create_app", None)
    assert create_app is not None

    class FakeService:
        def get_dashboard(self, *, preset=None, start_timestamp=None, end_timestamp=None):
            return {
                "meta": {"preset": preset or "today", "start_timestamp": 1, "end_timestamp": 2},
                "summary": {"total_members": 1, "total_used_tokens": 120, "total_request_count": 4},
                "members": [
                    {
                        "email": "alice@example.com",
                        "display_name": "Alice Ops",
                        "username": "alice",
                        "role": "admin",
                        "user_group": "vip",
                        "request_count": 4,
                        "used_tokens": 120,
                        "used_quota": 120,
                    }
                ],
            }

        def get_rankings(self):
            return {
                "daily": [{"email": "alice@example.com", "display_name": "Alice Ops", "used_tokens": 120}],
                "weekly": [],
                "monthly": [],
            }

        def set_alias(self, *, email: str, alias: str):
            return {"email": email, "alias": alias}

    app = create_app(service=FakeService())
    client = TestClient(app)

    page = client.get("/")
    dashboard = client.get("/api/dashboard", params={"preset": "today"})
    rankings = client.get("/api/rankings")

    assert page.status_code == 200
    assert "TeamView Usage Board" in page.text
    assert dashboard.status_code == 200
    assert dashboard.json()["members"][0]["display_name"] == "Alice Ops"
    assert rankings.status_code == 200
    assert rankings.json()["daily"][0]["used_tokens"] == 120


def test_web_app_updates_alias_by_email() -> None:
    create_app = getattr(web_module, "create_app", None)
    assert create_app is not None

    class FakeService:
        def get_dashboard(self, *, preset=None, start_timestamp=None, end_timestamp=None):
            return {"meta": {}, "summary": {}, "members": []}

        def get_rankings(self):
            return {"daily": [], "weekly": [], "monthly": []}

        def set_alias(self, *, email: str, alias: str):
            return {"email": email, "alias": alias}

    app = create_app(service=FakeService())
    client = TestClient(app)

    response = client.post("/api/aliases", json={"email": "alice@example.com", "alias": "Alice Ops"})

    assert response.status_code == 200
    assert response.json() == {"email": "alice@example.com", "alias": "Alice Ops"}


def test_web_app_exposes_public_ranking_endpoints_with_token() -> None:
    create_app = getattr(web_module, "create_app", None)
    assert create_app is not None

    class FakeService:
        def get_dashboard(self, *, preset=None, start_timestamp=None, end_timestamp=None):
            return {"meta": {}, "summary": {}, "members": []}

        def get_rankings(self):
            return {"daily": [], "weekly": [], "monthly": []}

        def get_public_ranking(self, ranking_type: str):
            return {
                "ranking_type": ranking_type,
                "items": [{"email": "alice@example.com", "display_name": "Alice Ops", "used_tokens": 120}],
            }

        def set_alias(self, *, email: str, alias: str):
            return {"email": email, "alias": alias}

    app = create_app(service=FakeService(), public_token="weird-token")
    client = TestClient(app)

    forbidden = client.get("/api/public-rankings/daily", params={"token": "bad-token"})
    allowed = client.get("/api/public-rankings/monthly", params={"token": "weird-token"})

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["ranking_type"] == "monthly"
    assert allowed.json()["items"][0]["used_tokens"] == 120
