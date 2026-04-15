"""FastAPI application for the TeamView dashboard."""

from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


class AliasUpdate(BaseModel):
    email: str = Field(min_length=1)
    alias: str = ""


def create_app(*, service: Any | None = None, public_token: str | None = None) -> FastAPI:
    load_project_env()
    app = FastAPI(title="TeamView Usage Board")
    app.state.dashboard_service = service or DashboardService.from_env()
    app.state.public_token = public_token if public_token is not None else os.getenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN", "")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "title": "TeamView Usage Board",
                "preset_options": [
                    ("today", "今天"),
                    ("last_7_days", "近7天"),
                    ("last_30_days", "近30天"),
                    ("this_month", "本月"),
                    ("last_month", "上月"),
                ],
            },
        )

    @app.get("/api/dashboard")
    def dashboard(
        preset: str = Query(default="today"),
        start_timestamp: int | None = Query(default=None),
        end_timestamp: int | None = Query(default=None),
    ) -> dict[str, Any]:
        return _call_service(
            app.state.dashboard_service.get_dashboard,
            preset=preset,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )

    @app.get("/api/rankings")
    def rankings() -> dict[str, Any]:
        return _call_service(app.state.dashboard_service.get_rankings)

    @app.get("/api/public-rankings/{ranking_type}")
    def public_ranking(ranking_type: str, token: str = Query(default="")) -> dict[str, Any]:
        expected = app.state.public_token
        if not expected or not hmac.compare_digest(token, expected):
            raise HTTPException(status_code=403, detail="Forbidden")
        return _call_service(app.state.dashboard_service.get_public_ranking, ranking_type=ranking_type)

    @app.post("/api/aliases")
    def aliases(payload: AliasUpdate) -> dict[str, str]:
        return _call_service(
            app.state.dashboard_service.set_alias,
            email=payload.email,
            alias=payload.alias,
        )

    return app


def _call_service(func, **kwargs):
    try:
        return func(**kwargs)
    except TeamViewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def main() -> None:
    load_project_env()
    host = os.getenv("SWITCHBASE_TEAMVIEW_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("SWITCHBASE_TEAMVIEW_WEB_PORT", "8000"))
    uvicorn.run("switchbase_teamview.web:create_app", factory=True, host=host, port=port, reload=False)


__all__ = ["create_app", "main"]
