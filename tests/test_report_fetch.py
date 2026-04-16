from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

from switchbase_teamview.report_fetch import fetch_generated_reports


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb


def test_fetch_generated_reports_writes_server_get_files(tmp_path: Path, monkeypatch) -> None:
    seen_urls: list[str] = []

    def fake_urlopen(url: str, timeout: int = 20):
        del timeout
        seen_urls.append(url)
        if url.endswith(".png?token=weird-token"):
            return _FakeResponse(b"\x89PNG\r\n\x1a\nfake")
        return _FakeResponse(b'{"ranking_type":"daily","items":[]}')

    monkeypatch.setattr("switchbase_teamview.report_fetch.urlopen", fake_urlopen)

    output_dir = tmp_path / "outputs" / "server-get"
    result = fetch_generated_reports(
        base_url="http://example.test/api/generated-reports",
        token="weird-token",
        output_dir=output_dir,
    )

    assert result.saved_paths == [
        output_dir / "daily.json",
        output_dir / "daily-poster.png",
        output_dir / "weekly.json",
        output_dir / "weekly-poster.png",
        output_dir / "monthly.json",
        output_dir / "monthly-poster.png",
    ]
    assert result.failures == []
    assert (output_dir / "daily.json").read_text(encoding="utf-8") == '{"ranking_type":"daily","items":[]}'
    assert (output_dir / "monthly-poster.png").read_bytes().startswith(b"\x89PNG")
    assert seen_urls[0] == "http://example.test/api/generated-reports/daily.json?token=weird-token"


def test_fetch_generated_reports_continues_after_missing_file(tmp_path: Path, monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: int = 20):
        del timeout
        if "weekly.json" in url:
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=BytesIO(b"missing"))
        if url.endswith(".png?token=weird-token"):
            return _FakeResponse(b"\x89PNG\r\n\x1a\nfake")
        return _FakeResponse(b'{"ranking_type":"daily","items":[]}')

    monkeypatch.setattr("switchbase_teamview.report_fetch.urlopen", fake_urlopen)

    output_dir = tmp_path / "outputs" / "server-get"
    result = fetch_generated_reports(
        base_url="http://example.test/api/generated-reports",
        token="weird-token",
        output_dir=output_dir,
    )

    assert output_dir.joinpath("daily.json").exists()
    assert output_dir.joinpath("monthly.json").exists()
    assert not output_dir.joinpath("weekly.json").exists()
    assert [path.name for path in result.saved_paths] == [
        "daily.json",
        "daily-poster.png",
        "weekly-poster.png",
        "monthly.json",
        "monthly-poster.png",
    ]
    assert result.failures == [("weekly.json", "HTTP Error 404: Not Found")]
