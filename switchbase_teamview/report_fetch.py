"""Fetch generated report artifacts from the deployed server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from switchbase_teamview.env import load_project_env

DEFAULT_BASE_URL = "http://103.231.13.190:47593/api/generated-reports"
REPORT_FILES = [
    "daily.json",
    "daily-poster.png",
    "weekly.json",
    "weekly-poster.png",
    "monthly.json",
    "monthly-poster.png",
]


@dataclass(frozen=True)
class FetchResult:
    saved_paths: list[Path]
    failures: list[tuple[str, str]]


def fetch_generated_reports(
    *,
    base_url: str,
    token: str,
    output_dir: Path,
) -> FetchResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    failures: list[tuple[str, str]] = []
    query = urlencode({"token": token})
    for filename in REPORT_FILES:
        url = f"{base_url.rstrip('/')}/{filename}?{query}"
        print(f"[report-fetch] GET {url}", flush=True)
        try:
            with urlopen(url, timeout=20) as response:
                target = output_dir / filename
                target.write_bytes(response.read())
                saved_paths.append(target)
                print(f"[report-fetch] saved {target}", flush=True)
        except (HTTPError, URLError, OSError) as exc:
            failures.append((filename, str(exc)))
            print(f"[report-fetch] failed {filename}: {exc}", flush=True)
    return FetchResult(saved_paths=saved_paths, failures=failures)


def main() -> None:
    load_project_env()
    token = os.getenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN", "")
    if not token:
        raise SystemExit("Missing SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN")
    output_dir = Path.cwd() / "outputs" / "server-get"
    print(f"[report-fetch] output_dir={output_dir}", flush=True)
    print(f"[report-fetch] base_url={DEFAULT_BASE_URL}", flush=True)
    result = fetch_generated_reports(base_url=DEFAULT_BASE_URL, token=token, output_dir=output_dir)
    if result.failures:
        summary = ", ".join(f"{name} ({error})" for name, error in result.failures)
        raise SystemExit(f"Fetch completed with missing files: {summary}")
