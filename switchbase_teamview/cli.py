"""CLI entrypoints for the TeamView client."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Sequence

from switchbase_teamview.client import TeamViewClient
from switchbase_teamview.env import load_project_env
from switchbase_teamview.exceptions import TeamViewError

ENV_API_KEY = "SWITCHBASE_TEAMVIEW_API_KEY"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="teamview-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("usage", "validate"):
        command = subparsers.add_parser(name)
        _add_common_options(command)
        command.add_argument("--username")
        command.add_argument("--start-timestamp", type=int)
        command.add_argument("--end-timestamp", type=int)
        command.add_argument("--json", action="store_true")

    logs = subparsers.add_parser("logs")
    _add_common_options(logs)
    logs.add_argument("--username")
    logs.add_argument("--model-name")
    logs.add_argument("--start-timestamp", type=int)
    logs.add_argument("--end-timestamp", type=int)
    logs.add_argument("-p", "--page", type=int, default=0)
    logs.add_argument("--size", type=int, default=20)
    logs.add_argument("--type", dest="log_type", type=int, default=2)
    logs.add_argument("--json", action="store_true")

    return parser


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key")
    parser.add_argument("--base-url", default="https://team.switchbase.vip")
    parser.add_argument("--auth-in-query", action="store_true")


def _resolve_api_key(api_key: str | None) -> str:
    load_project_env()
    if api_key:
        return api_key
    env_api_key = os.getenv(ENV_API_KEY)
    if env_api_key:
        return env_api_key
    raise TeamViewError(f"Missing API key. Set {ENV_API_KEY} or pass --api-key.")


def _dump_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_validate(response: Any) -> None:
    members = response.data.members
    if not members:
        print("接口可用，但当前组织无成员数据")
        return

    member = members[0]
    print(
        "validate ok "
        f"username={member.username} "
        f"display_name={member.display_name} "
        f"request_count={member.request_count} "
        f"used_tokens={member.used_tokens} "
        f"used_quota={member.used_quota}"
    )


def run(argv: Sequence[str] | None = None) -> int:
    load_project_env()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        api_key = _resolve_api_key(args.api_key)
        client = TeamViewClient(
            api_key=api_key,
            base_url=args.base_url,
            auth_in_query=args.auth_in_query,
        )
        try:
            if args.command == "usage":
                response = client.get_usage(
                    username=args.username,
                    start_timestamp=args.start_timestamp,
                    end_timestamp=args.end_timestamp,
                )
                if args.json:
                    _dump_json(response.model_dump(mode="json"))
                else:
                    print(
                        "usage "
                        f"members={response.data.total_members} "
                        f"requests={response.data.total_request_count} "
                        f"used_tokens={response.data.total_used_tokens}"
                    )
                return 0

            if args.command == "logs":
                response = client.get_logs(
                    username=args.username,
                    model_name=args.model_name,
                    start_timestamp=args.start_timestamp,
                    end_timestamp=args.end_timestamp,
                    page=args.page,
                    size=args.size,
                    log_type=args.log_type,
                )
                if args.json:
                    _dump_json(response.model_dump(mode="json"))
                else:
                    print(f"logs items={len(response.data.items)}")
                return 0

            response = client.get_usage(
                username=args.username,
                start_timestamp=args.start_timestamp,
                end_timestamp=args.end_timestamp,
            )
            if args.json:
                _dump_json(response.model_dump(mode="json"))
            else:
                _print_validate(response)
            return 0
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
    except TeamViewError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
