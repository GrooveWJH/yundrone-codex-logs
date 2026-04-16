from __future__ import annotations

import json
from pathlib import Path

from scripts.poster import export, loaders
from scripts.poster.render import build_figure
from scripts.poster.models import DataPolicy, PosterRequest, RankingSnapshot


def _payload() -> dict[str, object]:
    return {
        "ranking_type": "daily",
        "generated_at": 1_776_007_200,
        "items": [
            {
                "email": "alice@yundrone.cn",
                "display_name": "Alice",
                "raw_display_name": "alice",
                "username": "alice",
                "used_tokens": 120,
                "request_count": 3,
            },
            {
                "email": "codex@yundrone.cn",
                "display_name": "Codex",
                "raw_display_name": "codex",
                "username": "codex",
                "used_tokens": 999,
                "request_count": 9,
            },
            {
                "email": "bob@example.com",
                "display_name": "Bob",
                "raw_display_name": "bob",
                "username": "bob",
                "used_tokens": 400,
                "request_count": 4,
            },
        ],
    }


def test_build_snapshot_applies_default_policy() -> None:
    snapshot = loaders.build_snapshot(
        raw_payload=_payload(),
        policy=DataPolicy(),
        period="daily",
        source="memory",
    )

    assert snapshot.scope == "filtered"
    assert [item.email for item in snapshot.items] == ["alice@yundrone.cn"]
    assert snapshot.items[0].rank == 1


def test_load_snapshot_from_json_matches_in_memory_builder(tmp_path: Path) -> None:
    input_file = tmp_path / "daily.json"
    input_file.write_text(json.dumps(_payload()), encoding="utf-8")

    from_file = loaders.load_snapshot_from_json(
        input_file,
        period="daily",
        policy=DataPolicy(scope="all-members"),
    )
    from_memory = loaders.load_snapshot_from_memory(
        _payload(),
        period="daily",
        policy=DataPolicy(scope="all-members"),
        source="memory",
    )

    assert from_file == from_memory.model_copy(update={"source": str(input_file)})


def test_load_snapshot_from_api_uses_fetched_payload(monkeypatch) -> None:
    monkeypatch.setattr(loaders, "fetch_ranking_payload", lambda base_url, token, period: _payload())

    snapshot = loaders.load_snapshot_from_api(
        "http://example.test/api/public-rankings",
        "weird-token",
        "daily",
        DataPolicy(),
    )

    assert isinstance(snapshot, RankingSnapshot)
    assert snapshot.period == "daily"
    assert [item.email for item in snapshot.items] == ["alice@yundrone.cn"]


def test_load_snapshots_from_json_dir_supports_all_periods(tmp_path: Path) -> None:
    for period in ("daily", "weekly", "monthly"):
        path = tmp_path / f"{period}.json"
        path.write_text(json.dumps({**_payload(), "ranking_type": period}), encoding="utf-8")

    snapshots = loaders.load_snapshots_from_json_dir(tmp_path, ["daily", "weekly", "monthly"], policy=DataPolicy())

    assert [snapshot.period for snapshot in snapshots] == ["daily", "weekly", "monthly"]


def test_export_save_png_writes_file(tmp_path: Path) -> None:
    snapshot = loaders.load_snapshot_from_memory(_payload(), period="daily", policy=DataPolicy(), source="memory")
    request = PosterRequest(snapshots=[snapshot])
    figure = build_figure(request)
    output_path = export.save_png(figure, tmp_path / "poster.png")

    assert output_path.exists()
    assert output_path.suffix == ".png"


def test_build_figure_supports_more_than_five_ranked_members() -> None:
    payload = {
        "ranking_type": "weekly",
        "generated_at": 1_776_007_200,
        "items": [
            {
                "email": f"user{i}@example.com",
                "display_name": f"User {i}",
                "raw_display_name": f"user{i}",
                "username": f"user{i}",
                "used_tokens": 1_000 - i,
                "request_count": i,
            }
            for i in range(1, 8)
        ],
    }

    snapshot = loaders.load_snapshot_from_memory(
        payload,
        period="weekly",
        policy=DataPolicy(scope="all-members", top_n=7),
        source="memory",
    )

    figure = build_figure(PosterRequest(snapshots=[snapshot]))

    assert len(snapshot.items) == 7
    assert figure is not None
