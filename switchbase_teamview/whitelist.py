from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from switchbase_teamview.exceptions import TeamViewError
from switchbase_teamview.models import UsageMember


@dataclass(frozen=True)
class WhitelistEntry:
    """A user selection rule for reportable TeamView members."""

    alias: str = ""
    include: bool = True


@dataclass
class WhitelistStore:
    """Load explicit report membership rules."""

    path: Path

    def load(self) -> dict[str, WhitelistEntry]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TeamViewError(f"Whitelist file is invalid JSON: {self.path}") from exc
        if not isinstance(raw, dict):
            raise TeamViewError(f"Whitelist file must contain an object: {self.path}")
        entries: dict[str, WhitelistEntry] = {}
        for raw_key, raw_value in raw.items():
            key = str(raw_key).strip()
            if not key:
                continue
            if isinstance(raw_value, str):
                entries[key] = WhitelistEntry(alias=raw_value.strip(), include=True)
                continue
            if not isinstance(raw_value, dict):
                raise TeamViewError(f"Whitelist entry must be a string or object: {key}")
            entries[key] = WhitelistEntry(
                alias=str(raw_value.get("alias") or "").strip(),
                include=bool(raw_value.get("include", True)),
            )
        return entries


def match_whitelist_entry(member: UsageMember, whitelist: dict[str, WhitelistEntry]) -> WhitelistEntry | None:
    keys = (
        f"id:{member.newapi_user_id}",
        f"username:{member.username.strip().lower()}",
        f"email:{member.email.strip().lower()}",
    )
    for key in keys:
        if key in whitelist:
            return whitelist[key]
    return None
