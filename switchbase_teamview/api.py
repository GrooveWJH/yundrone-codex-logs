"""API-only HTTP service for public TeamView rankings."""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError

JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]
PNG_HEADERS = [("Content-Type", "image/png")]
ALLOWED_REPORT_FILES = {
    "daily.json": ("json", "daily.json"),
    "weekly.json": ("json", "weekly.json"),
    "monthly.json": ("json", "monthly.json"),
    "daily-poster.png": ("png", "daily-poster.png"),
    "weekly-poster.png": ("png", "weekly-poster.png"),
    "monthly-poster.png": ("png", "monthly-poster.png"),
}


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def create_app(
    *,
    service: Any | None = None,
    public_token: str | None = None,
    output_dir: Path | None = None,
) -> Callable:
    load_project_env()
    dashboard_service = service or DashboardService.from_env()
    expected_token = public_token if public_token is not None else os.getenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN", "")
    report_output_dir = output_dir or Path(os.getenv("SWITCHBASE_TEAMVIEW_OUTPUT_DIR", "outputs"))

    def app(environ: dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if method != "GET":
            return _json_response(start_response, 404, {"detail": "Not Found"})
        if path.startswith("/api/public-rankings/"):
            provided_token = _query_token(environ)
            if not expected_token or not hmac.compare_digest(provided_token, expected_token):
                return _json_response(start_response, 403, {"detail": "Forbidden"})
            ranking_type = path.removeprefix("/api/public-rankings/").strip("/")
            try:
                payload = dashboard_service.get_public_ranking(ranking_type=ranking_type)
            except TeamViewError as exc:
                return _json_response(start_response, 400, {"detail": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive path
                return _json_response(start_response, 502, {"detail": str(exc)})
            return _json_response(start_response, 200, payload)
        if path.startswith("/api/generated-reports/"):
            provided_token = _query_token(environ)
            if not expected_token or not hmac.compare_digest(provided_token, expected_token):
                return _json_response(start_response, 403, {"detail": "Forbidden"})
            filename = path.removeprefix("/api/generated-reports/").strip("/")
            return _report_file_response(start_response, report_output_dir, filename)
        return _json_response(start_response, 404, {"detail": "Not Found"})

    return app


def main() -> None:
    load_project_env()
    host = os.getenv("SWITCHBASE_TEAMVIEW_API_HOST", "127.0.0.1")
    port = int(os.getenv("SWITCHBASE_TEAMVIEW_API_PORT", "8000"))
    app = create_app()
    with make_server(host, port, app, server_class=ThreadingWSGIServer, handler_class=WSGIRequestHandler) as server:
        print(f"[teamview-api] listening on http://{host}:{port}", flush=True)
        server.serve_forever()


def _json_response(start_response: Callable, status_code: int, payload: dict[str, Any]) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [*JSON_HEADERS, ("Content-Length", str(len(body)))]
    start_response(f"{status_code} {_reason_phrase(status_code)}", headers)
    return [body]


def _report_file_response(start_response: Callable, output_dir: Path, filename: str) -> list[bytes]:
    allowed = ALLOWED_REPORT_FILES.get(filename)
    if allowed is None:
        return _json_response(start_response, 404, {"detail": "Not Found"})
    kind, safe_name = allowed
    path = output_dir / safe_name
    if not path.exists() or not path.is_file():
        return _json_response(start_response, 404, {"detail": "Not Found"})
    body = path.read_bytes()
    headers = [*(JSON_HEADERS if kind == "json" else PNG_HEADERS), ("Content-Length", str(len(body)))]
    start_response("200 OK", headers)
    return [body]


def _query_token(environ: dict[str, Any]) -> str:
    params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    return params.get("token", [""])[0]


def _reason_phrase(status_code: int) -> str:
    return {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        502: "Bad Gateway",
    }.get(status_code, "OK")


__all__ = ["create_app", "main"]
