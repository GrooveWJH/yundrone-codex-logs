from __future__ import annotations

from scripts.poster.models import DataPolicy, RankingItem


def apply_policy(items: list[RankingItem], policy: DataPolicy) -> list[RankingItem]:
    filtered = [item for item in items if _item_allowed(item, policy)]
    ordered = sorted(filtered, key=_sort_tuple)
    limited = ordered[: policy.top_n]
    return [item.model_copy(update={"rank": index}) for index, item in enumerate(limited, start=1)]


def snapshot_scope(policy: DataPolicy) -> str:
    return policy.scope


def _item_allowed(item: RankingItem, policy: DataPolicy) -> bool:
    if policy.scope == "all-members":
        return True

    email = item.email.strip().lower()
    if not email:
        return False
    if email in {value.strip().lower() for value in policy.excluded_emails}:
        return False
    domains = [value.strip().lower() for value in policy.allowed_email_domains if value.strip()]
    return bool(domains) and any(email.endswith(f"@{domain}") for domain in domains)


def _sort_tuple(item: RankingItem) -> tuple[int, str, str]:
    return (-item.used_tokens, item.email, item.username)
