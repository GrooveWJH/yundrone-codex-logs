from __future__ import annotations

import io
import json
from pathlib import Path
from collections.abc import Callable
from typing import Any
from wsgiref.util import setup_testing_defaults

import switchbase_teamview.api as api_module


def _request(app, path: str, query: str = "") -> tuple[int, dict[str, str], bytes]:
    environ: dict[str, Any] = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = path
    environ["QUERY_STRING"] = query
    environ["REQUEST_METHOD"] = "GET"
    environ["SERVER_NAME"] = "localhost"
    environ["SERVER_PORT"] = "8000"
    environ["wsgi.input"] = io.BytesIO(b"")
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app(environ, start_response))
    status_code = int(str(captured["status"]).split()[0])
    headers = {name: value for name, value in captured["headers"]}
    return status_code, headers, body


def test_public_api_exposes_only_public_ranking_endpoints() -> None:
    create_app = getattr(api_module, "create_app", None)
    assert create_app is not None

    class FakeService:
        def get_public_ranking(self, ranking_type: str):
            return {
                "ranking_type": ranking_type,
                "items": [{"email": "alice@yundrone.cn", "display_name": "Alice Ops", "used_tokens": 120}],
            }

    app = create_app(service=FakeService(), public_token="weird-token")

    forbidden = _request(app, "/api/public-rankings/daily", "token=bad-token")
    allowed = _request(app, "/api/public-rankings/monthly", "token=weird-token")
    missing_page = _request(app, "/")
    missing_dashboard = _request(app, "/api/dashboard")
    missing_rankings = _request(app, "/api/rankings")
    missing_aliases = _request(app, "/api/aliases")

    assert forbidden[0] == 403
    assert allowed[0] == 200
    assert json.loads(allowed[2])["ranking_type"] == "monthly"
    assert json.loads(allowed[2])["items"][0]["used_tokens"] == 120
    assert missing_page[0] == 404
    assert missing_dashboard[0] == 404
    assert missing_rankings[0] == 404
    assert missing_aliases[0] == 404


def test_public_api_rejects_unsupported_ranking_type_with_existing_error_shape() -> None:
    create_app = getattr(api_module, "create_app", None)
    assert create_app is not None

    class FakeService:
        def get_public_ranking(self, ranking_type: str):
            raise api_module.TeamViewError(f"Unsupported ranking_type: {ranking_type}")

    app = create_app(service=FakeService(), public_token="weird-token")
    status_code, headers, body = _request(app, "/api/public-rankings/yearly", "token=weird-token")

    assert status_code == 400
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(body) == {"detail": "Unsupported ranking_type: yearly"}


def test_public_api_serves_generated_report_json_and_png_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "daily.json").write_text(json.dumps({"ranking_type": "daily", "items": []}), encoding="utf-8")
    (output_dir / "daily-poster.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    app = api_module.create_app(service=object(), public_token="weird-token", output_dir=output_dir)

    json_response = _request(app, "/api/generated-reports/daily.json", "token=weird-token")
    png_response = _request(app, "/api/generated-reports/daily-poster.png", "token=weird-token")

    assert json_response[0] == 200
    assert json_response[1]["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(json_response[2]) == {"ranking_type": "daily", "items": []}
    assert png_response[0] == 200
    assert png_response[1]["Content-Type"] == "image/png"
    assert png_response[2].startswith(b"\x89PNG")


def test_public_api_generated_report_routes_require_token_and_return_404_when_missing(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "weekly.json").write_text(json.dumps({"ranking_type": "weekly", "items": []}), encoding="utf-8")

    app = api_module.create_app(service=object(), public_token="weird-token", output_dir=output_dir)

    forbidden = _request(app, "/api/generated-reports/weekly.json", "token=bad-token")
    missing = _request(app, "/api/generated-reports/monthly.json", "token=weird-token")

    assert forbidden[0] == 403
    assert missing[0] == 404
    assert json.loads(missing[2]) == {"detail": "Not Found"}
