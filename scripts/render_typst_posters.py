from __future__ import annotations

import subprocess
import shutil
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import click
import typer
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.typst_metrics import METRICS, PERIODS, export_csv_files
from switchbase_teamview.typst_posters import DEFAULT_FONT_PATH
from switchbase_teamview.typst_posters import DEFAULT_TYPST_TRIO
from switchbase_teamview.typst_posters import TypstCompileError
from switchbase_teamview.typst_posters import TypstMissingError
from switchbase_teamview.typst_posters import typst_command
from switchbase_teamview.typst_posters import typst_csv_dir
from switchbase_teamview.typst_posters import typst_trio_command

PeriodArg = Literal["daily", "weekly", "monthly", "trio", "all"]
MetricArg = Literal["tokens", "quota", "intensity", "all"]
DEFAULT_CSV_DIR = Path("outputs/metrics")
DEFAULT_OUTPUT_DIR = Path("outputs/typst-posters")
DEFAULT_TYPST_MAIN = Path("typst/main.typ")
DEFAULT_PPI = 200
app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    help="导出 TeamView Typst 排名图 PNG。",
)


class PeriodChoice(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    trio = "trio"
    all = "all"


class MetricChoice(StrEnum):
    tokens = "tokens"
    quota = "quota"
    intensity = "intensity"
    all = "all"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        return app(args=args, prog_name="render_typst_posters.py", standalone_mode=False) or 0
    except TypstMissingError as exc:
        typer.echo(str(exc), err=True)
        return 1
    except TypstCompileError as exc:
        typer.echo(f"Typst 编译失败：{exc}", err=True)
        return 1
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


@app.command(help="刷新 Typst CSV 并编译输出 PNG 排名图。")
def render(
    metric: Annotated[
        MetricChoice,
        typer.Option(
            "--metric",
            "-m",
            help="指标类型：tokens、quota、intensity 或 all。",
            rich_help_panel="基础选项",
        ),
    ] = MetricChoice.all,
    period: Annotated[
        PeriodChoice,
        typer.Option(
            "--period",
            "-p",
            help="统计周期：daily、weekly、monthly、trio 或 all。",
            rich_help_panel="基础选项",
        ),
    ] = PeriodChoice.all,
    csv_dir: Annotated[
        Path,
        typer.Option(
            "--csv-dir",
            help="Typst CSV 输出目录。",
            rich_help_panel="输出选项",
        ),
    ] = DEFAULT_CSV_DIR,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="PNG 输出目录。",
            rich_help_panel="输出选项",
        ),
    ] = DEFAULT_OUTPUT_DIR,
    typst_main: Annotated[
        Path,
        typer.Option(
            "--typst-main",
            help="Typst 正式入口文件。",
            rich_help_panel="Typst 选项",
        ),
    ] = DEFAULT_TYPST_MAIN,
    typst_trio: Annotated[
        Path,
        typer.Option(
            "--typst-trio",
            help="Typst 三合一入口文件。",
            rich_help_panel="Typst 选项",
        ),
    ] = DEFAULT_TYPST_TRIO,
    font_path: Annotated[
        Path,
        typer.Option(
            "--font-path",
            help="额外 Typst 字体目录。",
            rich_help_panel="Typst 选项",
        ),
    ] = DEFAULT_FONT_PATH,
    ppi: Annotated[
        int,
        typer.Option(
            "--ppi",
            help="Typst PNG 输出 PPI。",
            rich_help_panel="Typst 选项",
        ),
    ] = DEFAULT_PPI,
) -> None:
    paths = render_typst_posters(
        metric=metric.value,
        period=period.value,
        csv_dir=csv_dir,
        output_dir=output_dir,
        typst_main=typst_main,
        typst_trio=typst_trio,
        font_path=font_path,
        ppi=ppi,
        service=DashboardService.from_env(),
    )
    for path in paths:
        _debug(f"saved png path={path}")


def render_typst_posters(
    *,
    metric: MetricArg,
    period: PeriodArg,
    csv_dir: Path = DEFAULT_CSV_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    typst_main: Path = DEFAULT_TYPST_MAIN,
    typst_trio: Path = DEFAULT_TYPST_TRIO,
    font_path: Path = DEFAULT_FONT_PATH,
    ppi: int = DEFAULT_PPI,
    service=None,
) -> list[Path]:
    if ppi <= 0:
        raise typer.BadParameter("--ppi must be a positive integer")
    typst_bin = _typst_binary()
    service = service or DashboardService.from_env()
    csv_period: Literal["daily", "weekly", "monthly", "all"] = "all" if period == "trio" else period
    _debug(f"export csv metric={metric} period={csv_period} csv_dir={csv_dir}")
    export_csv_files(period=csv_period, metric=metric, output_dir=csv_dir, service=service)

    if period == "trio":
        return _render_trio_targets(
            typst_bin=typst_bin,
            metric=metric,
            csv_dir=csv_dir,
            output_dir=output_dir,
            typst_trio=typst_trio,
            font_path=font_path,
            ppi=ppi,
        )

    output_paths: list[Path] = []
    for metric_name, period_name in _render_targets(metric=metric, period=period):
        output_path = output_dir / metric_name / f"{period_name}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = _typst_command(
            typst_bin=typst_bin,
            typst_main=typst_main,
            output_path=output_path,
            font_path=font_path,
            metric=metric_name,
            period=period_name,
            csv_dir=csv_dir,
            window=_window_text(csv_dir=csv_dir, metric=metric_name, period=period_name),
            ppi=ppi,
        )
        _debug(f"compile metric={metric_name} period={period_name} output={output_path}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise TypstCompileError(
                f"exit={exc.returncode} cmd={' '.join(map(str, exc.cmd))}"
            ) from exc
        output_paths.append(output_path)
    return output_paths


def _render_trio_targets(
    *,
    typst_bin: str,
    metric: MetricArg,
    csv_dir: Path,
    output_dir: Path,
    typst_trio: Path,
    font_path: Path,
    ppi: int,
) -> list[Path]:
    metrics = METRICS if metric == "all" else (metric,)
    output_paths: list[Path] = []
    for metric_name in metrics:
        output_path = output_dir / metric_name / "trio.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = _typst_trio_command(
            typst_bin=typst_bin,
            typst_trio=typst_trio,
            output_path=output_path,
            font_path=font_path,
            metric=metric_name,
            csv_dir=csv_dir,
            ppi=ppi,
        )
        _debug(f"compile metric={metric_name} period=trio output={output_path}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise TypstCompileError(
                f"exit={exc.returncode} cmd={' '.join(map(str, exc.cmd))}"
            ) from exc
        output_paths.append(output_path)
    return output_paths


def _render_targets(*, metric: MetricArg, period: PeriodArg) -> list[tuple[str, str]]:
    metrics = METRICS if metric == "all" else (metric,)
    periods = PERIODS if period == "all" else (period,)
    return [(metric_name, period_name) for metric_name in metrics for period_name in periods]


def _typst_command(
    *,
    typst_bin: str,
    typst_main: Path,
    output_path: Path,
    font_path: Path,
    metric: str,
    period: str,
    csv_dir: Path,
    window: str | None,
    ppi: int,
) -> list[str]:
    return typst_command(
        typst_bin=typst_bin,
        typst_main=typst_main,
        output_path=output_path,
        font_path=font_path,
        metric=metric,
        period=period,
        csv_dir=typst_csv_dir(csv_dir, typst_main=typst_main),
        window=window,
        ppi=ppi,
    )


def _typst_trio_command(
    *,
    typst_bin: str,
    typst_trio: Path,
    output_path: Path,
    font_path: Path,
    metric: str,
    csv_dir: Path,
    ppi: int,
) -> list[str]:
    return typst_trio_command(
        typst_bin=typst_bin,
        typst_trio=typst_trio,
        output_path=output_path,
        font_path=font_path,
        metric=metric,
        csv_dir=typst_csv_dir(csv_dir, typst_main=typst_trio),
        ppi=ppi,
    )


def _typst_binary() -> str:
    typst_bin = shutil.which("typst")
    if not typst_bin:
        raise TypstMissingError("找不到 typst 命令。请安装 Typst，或确认 typst 已在 PATH 中。")
    return typst_bin


def _window_text(*, csv_dir: Path, metric: str, period: str) -> str | None:
    period_path = csv_dir / metric / f"{period}.time"
    if period_path.exists():
        return period_path.read_text(encoding="utf-8").strip()
    fallback_path = csv_dir / metric / "time"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8").strip()
    return None


def _debug(message: str) -> None:
    typer.echo(f"[typst-posters] {message}")


if __name__ == "__main__":
    raise SystemExit(main())
