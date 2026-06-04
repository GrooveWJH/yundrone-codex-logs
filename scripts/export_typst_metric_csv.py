from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import click
import typer
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.typst_metrics import (
    CSV_HEADER,
    METRICS,
    PERIODS,
    MetricArg,
    PeriodArg,
    compact_decimal,
    csv_text,
    export_csv_files,
    rows_from_payload,
    time_text_from_payload,
)

DEFAULT_OUTPUT_DIR = Path("outputs/metrics")
app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    help="导出 Typst 可直接读取的 TeamView 白名单指标 CSV。",
)


class PeriodChoice(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    all = "all"


class MetricChoice(StrEnum):
    tokens = "tokens"
    quota = "quota"
    intensity = "intensity"
    all = "all"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        return app(args=args, prog_name="export_typst_metric_csv.py", standalone_mode=False) or 0
    except click.UsageError as exc:
        typer.echo("参数错误：无法识别或不支持该参数。", err=True)
        typer.echo(f"详情：{exc.format_message()}", err=True)
        typer.echo("请参考下方 usage 页面：", err=True)
        if exc.ctx:
            typer.echo(exc.ctx.get_help())
        else:
            typer.echo("请使用 --help 查看可用参数。", err=True)
        return 2
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)


@app.command(help="按周期和指标导出白名单 CSV。")
def export(
    period: Annotated[
        PeriodChoice,
        typer.Option(
            "--period",
            "-p",
            help="统计周期：daily=今日，weekly=本周，monthly=本月，all=三种周期。",
            rich_help_panel="基础选项",
        ),
    ] = PeriodChoice.monthly,
    metric: Annotated[
        MetricChoice,
        typer.Option(
            "--metric",
            "-m",
            help="指标类型：tokens=Token 值，quota=Quota 用量，intensity=用量强度，all=全部指标。",
            rich_help_panel="基础选项",
        ),
    ] = MetricChoice.tokens,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="CSV 输出目录。脚本会按 metric 分层写入，例如 tokens/monthly.csv。",
            rich_help_panel="输出选项",
        ),
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    paths = export_csv_files(
        period=period.value,
        metric=metric.value,
        output_dir=output_dir,
        service=DashboardService.from_env(),
    )
    for path in paths:
        typer.echo(f"已导出：{path}")


__all__ = [
    "CSV_HEADER",
    "METRICS",
    "PERIODS",
    "MetricArg",
    "PeriodArg",
    "compact_decimal",
    "csv_text",
    "export_csv_files",
    "rows_from_payload",
    "time_text_from_payload",
    "app",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
