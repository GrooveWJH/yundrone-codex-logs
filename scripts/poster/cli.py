from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import find_dotenv
from scripts.poster import export, loaders
from scripts.poster.models import DataPolicy, Period, PosterRequest
from scripts.poster.render import build_figure
from switchbase_teamview.env import load_project_env

DEFAULT_BASE_URL = "http://103.231.13.190:47593/api/public-rankings"
app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def run(argv: list[str] | None = None) -> int:
    env_path = find_dotenv(filename=".env", usecwd=True)
    load_project_env()
    if env_path:
        _debug(f"loaded env path={env_path}")
    else:
        _debug("loaded env path=not-found")
    if argv is None:
        return app(prog_name="python -m scripts.poster", standalone_mode=False) or 0
    return app(args=argv, prog_name="python -m scripts.poster", standalone_mode=False) or 0


@app.command()
def main(
    input_source: Annotated[
        str,
        typer.Option(help="Poster input source: api, json, or memory-test-hook."),
    ] = "api",
    period: Annotated[
        str,
        typer.Option(help="Ranking period to render: daily, weekly, monthly, or all."),
    ] = ...,
    output: Annotated[
        str | None,
        typer.Option(
            help="PNG output path. Defaults to outputs/<period>-poster.png.",
            show_default="outputs/<period>-poster.png",
        ),
    ] = None,
    base_url: Annotated[str, typer.Option(help="Ranking API base URL.")] = DEFAULT_BASE_URL,
    token: Annotated[
        str | None,
        typer.Option(help="Public ranking token. Defaults to SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN."),
    ] = None,
    json_dir: Annotated[str, typer.Option(help="Directory to save fetched or reused JSON payloads.")] = "./tmp",
    input_file: Annotated[str | None, typer.Option(help="Input JSON file for json or memory-test-hook mode.")] = None,
    include_all_members: Annotated[bool, typer.Option(help="Disable default member filtering.")] = False,
    top_n: Annotated[int, typer.Option(help="Maximum number of ranked members to render.")] = 5,
    allowed_domain: Annotated[list[str], typer.Option(help="Allowed email domain. Repeat to allow multiple.")] = [],
    exclude_email: Annotated[list[str], typer.Option(help="Excluded email. Repeat to exclude multiple.")] = [],
) -> int:
    source = _validate_choice(input_source, {"api", "json", "memory-test-hook"}, "--input-source")
    chosen_period = _validate_choice(period, {"daily", "weekly", "monthly", "all"}, "--period")
    policy = _policy_from_values(include_all_members, top_n, allowed_domain, exclude_email)
    periods = ["daily", "weekly", "monthly"] if chosen_period == "all" else [chosen_period]
    token = token or os.getenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN")
    output_path = _output_path(output, chosen_period)
    _debug(
        "start "
        f"source={source} "
        f"periods={','.join(periods)} "
        f"output={output_path} "
        f"json_dir={Path(json_dir).resolve()}"
    )
    snapshots = [
        _load_snapshot(period_name, source, base_url, token, json_dir, input_file, policy)
        for period_name in periods
    ]
    _save_payloads(source, base_url, token, json_dir, input_file, periods)
    _debug(f"render snapshots={len(snapshots)}")
    figure = build_figure(PosterRequest(snapshots=snapshots))
    export.save_png(figure, output_path)
    _debug(f"saved png path={output_path}")
    return 0


def _load_snapshot(
    period: Period,
    input_source: str,
    base_url: str,
    token: str | None,
    json_dir: str,
    input_file: str | None,
    policy: DataPolicy,
):
    source = input_source
    _debug(f"load snapshot period={period} source={source}")
    if source == "api":
        if not token:
            raise typer.BadParameter("Missing SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN or --token")
        return loaders.load_snapshot_from_api(base_url, token, period, policy)
    if source == "json":
        return loaders.load_snapshot_from_json(_input_path(period, json_dir, input_file), period=period, policy=policy)
    payload = loaders.load_payload_from_json(_input_path(period, json_dir, input_file))
    return loaders.load_snapshot_from_memory(payload, period=period, policy=policy, source="memory-test-hook")


def _save_payloads(
    input_source: str,
    base_url: str,
    token: str | None,
    json_dir: str,
    input_file: str | None,
    periods: list[Period],
) -> None:
    output_dir = Path(json_dir)
    for period in periods:
        if input_source == "api":
            if not token:
                raise typer.BadParameter("Missing SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN or --token")
            payload = loaders.fetch_ranking_payload(base_url, token, period)
        else:
            payload = loaders.load_payload_from_json(_input_path(period, json_dir, input_file))
        payload_path = output_dir / f"{period}.json"
        loaders.save_payload(payload_path, payload)
        _debug(f"saved payload period={period} path={payload_path}")


def _input_path(period: Period, json_dir: str, input_file: str | None) -> Path:
    if input_file:
        return Path(input_file)
    return Path(json_dir) / f"{period}.json"


def _policy_from_values(
    include_all_members: bool,
    top_n: int,
    allowed_domain: list[str],
    exclude_email: list[str],
) -> DataPolicy:
    return DataPolicy(
        include_all_members=include_all_members,
        allowed_email_domains=allowed_domain or ["yundrone.cn"],
        excluded_emails=exclude_email or ["codex@yundrone.cn"],
        top_n=top_n,
    )


def _output_path(output: str | None, period: str) -> Path:
    if output:
        return Path(output)
    return Path.cwd() / "outputs" / f"{period}-poster.png"


def _validate_choice(value: str, allowed: set[str], option_name: str) -> str:
    if value not in allowed:
        raise typer.BadParameter(
            f"Invalid value for {option_name}: {value}. Expected one of: {', '.join(sorted(allowed))}"
        )
    return value


def _debug(message: str) -> None:
    typer.echo(f"[poster] {message}")
