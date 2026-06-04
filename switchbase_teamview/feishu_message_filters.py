from __future__ import annotations

_AT_ALL_NAMES = {"所有人", "全体成员", "全员", "全体", "everyone", "all"}


def is_at_all_message(message) -> bool:
    mentions = getattr(message, "mentions", None) or []
    for mention in mentions:
        mention_id = getattr(mention, "id", None)
        if _is_all_identifier(getattr(mention_id, "user_id", None)):
            return True
        if _is_all_identifier(getattr(mention_id, "open_id", None)):
            return True
        if _is_all_identifier(getattr(mention_id, "union_id", None)):
            return True
        if _is_at_all_name(getattr(mention, "name", "")):
            return True
    return _content_contains_at_all(getattr(message, "content", "") or "")


def has_explicit_mentions(message) -> bool:
    mentions = getattr(message, "mentions", None) or []
    if mentions:
        return True
    return _content_contains_at_tag(getattr(message, "content", "") or "")


def is_group_chat(message) -> bool:
    return (getattr(message, "chat_type", "") or "").strip().lower() in {"group", "topic"}


def has_bot_mention(message, *, bot_names: tuple[str, ...]) -> bool:
    expected_names = {_normalize_mention_name(name) for name in bot_names if name.strip()}
    mentions = getattr(message, "mentions", None) or []
    for mention in mentions:
        mention_name = _normalize_mention_name(getattr(mention, "name", ""))
        if mention_name in expected_names:
            return True
    content = getattr(message, "content", "") or ""
    return any(f"@{name}" in content for name in bot_names if name.strip())


def _is_all_identifier(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() == "all"


def _is_at_all_name(value: object) -> bool:
    return _normalize_mention_name(value) in {_normalize_mention_name(name) for name in _AT_ALL_NAMES}


def _normalize_mention_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(value.strip().lower().split())


def _content_contains_at_all(content: str) -> bool:
    patterns = (
        'user_id="all"',
        "user_id='all'",
        "user_id=all",
        'user_id=\\"all\\"',
        'open_id="all"',
        "open_id='all'",
        'open_id=\\"all\\"',
        'union_id="all"',
        "union_id='all'",
        'union_id=\\"all\\"',
        "@所有人",
        "@全体成员",
    )
    return any(pattern in content for pattern in patterns)


def _content_contains_at_tag(content: str) -> bool:
    return "<at " in content or "&lt;at " in content
