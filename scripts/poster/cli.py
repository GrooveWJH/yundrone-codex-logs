from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import find_dotenv
from scripts.poster import export, loaders
from scripts.poster.models import DataPolicy, Period, PosterRequest, RankingScope
from scripts.poster.render import build_figure
from switchbase_teamview.reporting import ReportGenerator
from switchbase_teamview.dashboard import DashboardService
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
        typer.Option(help="Poster input source: api, teamview, json, or memory-test-hook."),
    ] = "api",
    period: Annotated[
        str,
        typer.Option(help="Ranking period to render: daily, weekly, monthly, or all."),
    ] = ...,
    output: Annotated[
        str | None,
        typer.Option(
            help="PNG output path. For --period all, treated as a target directory.",
            show_default="outputs/<period>-poster.png",
        ),
    ] = None,
    base_url: Annotated[str, typer.Option(help="Ranking API base URL.")] = DEFAULT_BASE_URL,
    token: Annotated[
        str | None,
        typer.Option(help="Public ranking token. Defaults to SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN."),
    ] = None,
    json_dir: Annotated[str, typer.Option(help="Directory to read JSON payloads from or save outputs into.")] = "./outputs",
    input_file: Annotated[str | None, typer.Option(help="Input JSON file for json or memory-test-hook mode.")] = None,
    scope: Annotated[
        str,
        typer.Option(help="Ranking scope: filtered or all-members."),
    ] = "filtered",
    top_n: Annotated[int, typer.Option(help="Maximum number of ranked members to render.")] = 5,
    allowed_domain: Annotated[list[str], typer.Option(help="Allowed email domain. Repeat to allow multiple.")] = [],
    exclude_email: Annotated[list[str], typer.Option(help="Excluded email. Repeat to exclude multiple.")] = [],
) -> int:
    source = _validate_choice(input_source, {"api", "teamview", "json", "memory-test-hook"}, "--input-source")
    chosen_period = _validate_choice(period, {"daily", "weekly", "monthly", "all"}, "--period")
    chosen_scope = _validate_choice(scope, {"filtered", "all-members"}, "--scope")
    policy = _policy_from_values(chosen_scope, top_n, allowed_domain, exclude_email)
    periods = ["daily", "weekly", "monthly"] if chosen_period == "all" else [chosen_period]
    token = token or os.getenv("SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN")
    output_paths = _output_paths(output, chosen_period, periods)
    output_dir = _output_dir(output)
    _debug(
        "start "
        f"source={source} "
        f"scope={chosen_scope} "
        f"periods={','.join(periods)} "
        f"outputs={','.join(str(path) for path in output_paths)} "
        f"json_dir={Path(json_dir).resolve()} "
        f"output_dir={output_dir.resolve()}"
    )
    if chosen_scope == "all-members" and source == "api":
        typer.echo(
            "Error: all-members scope requires --input-source teamview, json, or memory-test-hook",
            err=True,
        )
        raise typer.Exit(2)
    payloads = [
        _load_payload(period_name, source, chosen_scope, top_n, base_url, token, json_dir, input_file)
        for period_name in periods
    ]
    generator = ReportGenerator(output_dir=output_dir, policy=policy)
    _debug(f"render payloads={len(payloads)}")
    for period_name, payload, output_path in zip(periods, payloads, output_paths, strict=True):
        result = generator.write_payload(period=period_name, payload=payload, poster_path=output_path)
        _debug(f"saved payload period={period_name} path={result.json_path}")
        _debug(f"saved png path={output_path}")
    return 0


def _load_payload(
    period: Period,
    input_source: str,
    scope: RankingScope,
    top_n: int,
    base_url: str,
    token: str | None,
    json_dir: str,
    input_file: str | None,
):
    source = input_source
    _debug(f"load payload period={period} source={source}")
    if source == "api":
        if not token:
            raise typer.BadParameter("Missing SWITCHBASE_TEAMVIEW_PUBLIC_TOKEN or --token")
        return loaders.fetch_ranking_payload(base_url, token, period)
    if source == "teamview":
        return _dashboard_service().build_natural_ranking(scope=scope, ranking_type=period, limit=top_n)
    return loaders.load_payload_from_json(_input_path(period, json_dir, input_file))


def _input_path(period: Period, json_dir: str, input_file: str | None) -> Path:
    if input_file:
        return Path(input_file)
    return Path(json_dir) / f"{period}.json"


def _policy_from_values(
    scope: RankingScope,
    top_n: int,
    allowed_domain: list[str],
    exclude_email: list[str],
) -> DataPolicy:
    return DataPolicy(
        scope=scope,
        allowed_email_domains=allowed_domain or ["yundrone.cn"],
        excluded_emails=exclude_email or ["codex@yundrone.cn"],
        top_n=top_n,
    )


def _output_paths(output: str | None, chosen_period: str, periods: list[Period]) -> list[Path]:
    if chosen_period != "all":
        return [_single_output_path(output, periods[0])]
    base_dir = _output_dir(output)
    return [base_dir / f"{period}-poster.png" for period in periods]


def _single_output_path(output: str | None, period: Period) -> Path:
    if output:
        return Path(output)
    return Path.cwd() / "outputs" / f"{period}-poster.png"


def _output_dir(output: str | None) -> Path:
    if not output:
        return Path.cwd() / "outputs"
    output_path = Path(output)
    if output_path.suffix:
        return output_path.parent
    return output_path


def _validate_choice(value: str, allowed: set[str], option_name: str) -> str:
    if value not in allowed:
        raise typer.BadParameter(
            f"Invalid value for {option_name}: {value}. Expected one of: {', '.join(sorted(allowed))}"
        )
    return value


def _debug(message: str) -> None:
    typer.echo(f"[poster] {message}")


def _dashboard_service() -> DashboardService:
    return DashboardService.from_env()
