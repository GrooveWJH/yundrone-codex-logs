from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from scripts.poster.models import DataPolicy, Period, RankingItem, RankingSnapshot
from scripts.poster.policy import apply_policy, snapshot_scope


def fetch_ranking_payload(base_url: str, token: str, period: Period) -> dict[str, Any]:
    query = urlencode({"token": token})
    with urlopen(f"{base_url}/{period}?{query}", timeout=20) as response:
        return json.load(response)


def load_payload_from_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshot_from_api(base_url: str, token: str, period: Period, policy: DataPolicy) -> RankingSnapshot:
    payload = fetch_ranking_payload(base_url, token, period)
    return build_snapshot(raw_payload=payload, policy=policy, period=period, source=f"{base_url}/{period}")


def load_snapshot_from_json(path: Path, *, period: Period, policy: DataPolicy) -> RankingSnapshot:
    payload = load_payload_from_json(path)
    return build_snapshot(raw_payload=payload, policy=policy, period=period, source=str(path))


def load_snapshot_from_memory(
    raw_payload: dict[str, Any],
    *,
    period: Period,
    policy: DataPolicy,
    source: str = "memory",
) -> RankingSnapshot:
    return build_snapshot(raw_payload=raw_payload, policy=policy, period=period, source=source)


def load_snapshots_from_json_dir(json_dir: Path, periods: list[Period], *, policy: DataPolicy) -> list[RankingSnapshot]:
    return [load_snapshot_from_json(json_dir / f"{period}.json", period=period, policy=policy) for period in periods]


def build_snapshot(
    *,
    raw_payload: dict[str, Any],
    policy: DataPolicy,
    period: Period,
    source: str,
) -> RankingSnapshot:
    generated_at = int(raw_payload.get("generated_at") or 0)
    items = [_to_ranking_item(item, policy=policy) for item in raw_payload.get("items", [])]
    return RankingSnapshot(
        period=period,
        generated_at=generated_at,
        source=source,
        scope=snapshot_scope(policy),
        items=apply_policy(items, policy),
    )


def _to_ranking_item(raw_item: dict[str, Any], *, policy: DataPolicy) -> RankingItem:
    display_name = _display_name(raw_item, strategy=policy.display_name_strategy)
    return RankingItem(
        email=str(raw_item.get("email") or "").strip(),
        display_name=display_name,
        raw_display_name=str(raw_item.get("raw_display_name") or raw_item.get("display_name") or "").strip(),
        username=str(raw_item.get("username") or "").strip(),
        used_tokens=int(raw_item.get("used_tokens") or 0),
        request_count=int(raw_item.get("request_count") or 0),
    )


def _display_name(raw_item: dict[str, Any], *, strategy: str) -> str:
    del strategy
    for key in ("display_name", "raw_display_name", "username", "email"):
        value = str(raw_item.get(key) or "").strip()
        if value:
            return value
    return ""
