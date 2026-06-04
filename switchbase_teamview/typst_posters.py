from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from switchbase_teamview.dashboard import DashboardService
from switchbase_teamview.rankings import RankingScope
from switchbase_teamview.typst_metrics import Metric, PERIODS, Period, format_window, write_metric_files

DEFAULT_CSV_DIR = Path("outputs/metrics")
DEFAULT_TYPST_MAIN = Path("typst/main.typ")
DEFAULT_TYPST_TRIO = Path("typst/trio.typ")
DEFAULT_FONT_PATH = Path("assets/NotoSansSC")
DEFAULT_PPI = 200
SOURCE_LIMIT = 10_000


class TypstMissingError(RuntimeError):
    pass


class TypstCompileError(RuntimeError):
    pass


@dataclass(frozen=True)
class TypstPosterOutput:
    period: Period
    metric: Metric
    payload: dict[str, object]
    poster_path: Path
    window_text: str


@dataclass(frozen=True)
class TypstTrioPosterOutput:
    metric: Metric
    payloads: dict[Period, dict[str, object]]
    poster_path: Path
    window_texts: dict[Period, str]


class TypstPosterRenderer:
    def __init__(
        self,
        *,
        service: DashboardService | None = None,
        typst_main: Path = DEFAULT_TYPST_MAIN,
        typst_trio: Path = DEFAULT_TYPST_TRIO,
        font_path: Path = DEFAULT_FONT_PATH,
        ppi: int = DEFAULT_PPI,
        typst_bin: str | None = None,
    ) -> None:
        if ppi <= 0:
            raise ValueError("ppi must be a positive integer")
        self.service = service or DashboardService.from_env()
        self.typst_main = typst_main
        self.typst_trio = typst_trio
        self.font_path = font_path
        self.ppi = ppi
        self.typst_bin = typst_bin

    def render_period(
        self,
        *,
        period: Period,
        metric: Metric = "tokens",
        start_at: datetime,
        end_at: datetime,
        output_path: Path,
        csv_dir: Path,
        scope: RankingScope = "all-members",
        limit: int = SOURCE_LIMIT,
    ) -> TypstPosterOutput:
        payload = self.service.build_ranking(
            scope=scope,
            ranking_type=period,
            start_timestamp=int(start_at.timestamp()),
            end_timestamp=int(end_at.timestamp()),
            limit=limit,
        )
        payload = {
            **payload,
            "window_start": int(start_at.timestamp()),
            "window_end": int(end_at.timestamp()),
            "generated_at": int(end_at.timestamp()),
        }
        write_metric_files(periods=[period], metric=metric, output_dir=csv_dir, payloads={period: payload})
        window_text = format_window(
            period=period,
            start_timestamp=int(start_at.timestamp()),
            end_timestamp=int(end_at.timestamp()),
        )
        self.compile_png(
            output_path=output_path,
            metric=metric,
            period=period,
            csv_dir=csv_dir,
            window=window_text,
        )
        return TypstPosterOutput(
            period=period,
            metric=metric,
            payload=payload,
            poster_path=output_path,
            window_text=window_text,
        )

    def render_trio(
        self,
        *,
        metric: Metric = "tokens",
        end_at: datetime,
        output_path: Path,
        csv_dir: Path,
        scope: RankingScope = "all-members",
        limit: int = SOURCE_LIMIT,
    ) -> TypstTrioPosterOutput:
        payloads: dict[Period, dict[str, object]] = {}
        window_texts: dict[Period, str] = {}
        for period in PERIODS:
            start_at = natural_period_start(period=period, end_at=end_at)
            payload = self.service.build_ranking(
                scope=scope,
                ranking_type=period,
                start_timestamp=int(start_at.timestamp()),
                end_timestamp=int(end_at.timestamp()),
                limit=limit,
            )
            payload = {
                **payload,
                "window_start": int(start_at.timestamp()),
                "window_end": int(end_at.timestamp()),
                "generated_at": int(end_at.timestamp()),
            }
            payloads[period] = payload
            window_texts[period] = format_window(
                period=period,
                start_timestamp=int(start_at.timestamp()),
                end_timestamp=int(end_at.timestamp()),
            )
        write_metric_files(periods=PERIODS, metric=metric, output_dir=csv_dir, payloads=payloads)
        self.compile_trio_png(output_path=output_path, metric=metric, csv_dir=csv_dir)
        return TypstTrioPosterOutput(
            metric=metric,
            payloads=payloads,
            poster_path=output_path,
            window_texts=window_texts,
        )

    def render_trio_pdf(
        self,
        *,
        metric: Metric = "tokens",
        end_at: datetime,
        output_path: Path,
        csv_dir: Path,
        scope: RankingScope = "all-members",
        limit: int = SOURCE_LIMIT,
    ) -> TypstTrioPosterOutput:
        payloads: dict[Period, dict[str, object]] = {}
        window_texts: dict[Period, str] = {}
        for period in PERIODS:
            start_at = natural_period_start(period=period, end_at=end_at)
            payload = self.service.build_ranking(
                scope=scope,
                ranking_type=period,
                start_timestamp=int(start_at.timestamp()),
                end_timestamp=int(end_at.timestamp()),
                limit=limit,
            )
            payload = {
                **payload,
                "window_start": int(start_at.timestamp()),
                "window_end": int(end_at.timestamp()),
                "generated_at": int(end_at.timestamp()),
            }
            payloads[period] = payload
            window_texts[period] = format_window(
                period=period,
                start_timestamp=int(start_at.timestamp()),
                end_timestamp=int(end_at.timestamp()),
            )
        write_metric_files(periods=PERIODS, metric=metric, output_dir=csv_dir, payloads=payloads)
        self.compile_trio_pdf(output_path=output_path, metric=metric, csv_dir=csv_dir)
        return TypstTrioPosterOutput(
            metric=metric,
            payloads=payloads,
            poster_path=output_path,
            window_texts=window_texts,
        )

    def compile_png(
        self,
        *,
        output_path: Path,
        metric: Metric,
        period: Period,
        csv_dir: Path,
        window: str | None,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = typst_command(
            typst_bin=self._typst_binary(),
            typst_main=self.typst_main,
            output_path=output_path,
            font_path=self.font_path,
            metric=metric,
            period=period,
            csv_dir=typst_csv_dir(csv_dir, typst_main=self.typst_main),
            window=window,
            ppi=self.ppi,
        )
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise TypstCompileError(
                f"Typst compile failed: exit={exc.returncode} cmd={' '.join(map(str, exc.cmd))}"
            ) from exc

    def compile_trio_png(self, *, output_path: Path, metric: Metric, csv_dir: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = typst_trio_command(
            typst_bin=self._typst_binary(),
            typst_trio=self.typst_trio,
            output_path=output_path,
            font_path=self.font_path,
            metric=metric,
            csv_dir=typst_csv_dir(csv_dir, typst_main=self.typst_trio),
            ppi=self.ppi,
        )
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise TypstCompileError(
                f"Typst compile failed: exit={exc.returncode} cmd={' '.join(map(str, exc.cmd))}"
            ) from exc

    def compile_trio_pdf(self, *, output_path: Path, metric: Metric, csv_dir: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = typst_trio_command(
            typst_bin=self._typst_binary(),
            typst_trio=self.typst_trio,
            output_path=output_path,
            font_path=self.font_path,
            metric=metric,
            csv_dir=typst_csv_dir(csv_dir, typst_main=self.typst_trio),
            ppi=self.ppi,
        )
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            raise TypstCompileError(
                f"Typst compile failed: exit={exc.returncode} cmd={' '.join(map(str, exc.cmd))}"
            ) from exc

    def _typst_binary(self) -> str:
        if self.typst_bin:
            return self.typst_bin
        typst_bin = shutil.which("typst")
        if not typst_bin:
            raise TypstMissingError("找不到 typst 命令。请安装 Typst，或确认 typst 已在 PATH 中。")
        return typst_bin


def typst_command(
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
    cmd = [
        typst_bin,
        "compile",
        str(typst_main),
        str(output_path),
        "--root",
        ".",
        "--font-path",
        str(font_path),
        "--ppi",
        str(ppi),
        "--input",
        f"metric={metric}",
        "--input",
        f"period={period}",
        "--input",
        f"csv-dir={csv_dir.as_posix()}",
    ]
    if window:
        cmd.extend(["--input", f"window={window}"])
    return cmd


def typst_trio_command(
    *,
    typst_bin: str,
    typst_trio: Path,
    output_path: Path,
    font_path: Path,
    metric: str,
    csv_dir: Path,
    ppi: int,
) -> list[str]:
    return [
        typst_bin,
        "compile",
        str(typst_trio),
        str(output_path),
        "--root",
        ".",
        "--font-path",
        str(font_path),
        "--ppi",
        str(ppi),
        "--input",
        f"metric={metric}",
        "--input",
        f"csv-dir={csv_dir.as_posix()}",
    ]


def typst_csv_dir(csv_dir: Path, *, typst_main: Path = DEFAULT_TYPST_MAIN) -> Path:
    if csv_dir.is_absolute():
        try:
            return Path("..") / Path("..") / csv_dir.relative_to(Path.cwd())
        except ValueError:
            raise ValueError(f"csv_dir must be under Typst root: {csv_dir}")
    return Path("..") / Path("..") / csv_dir


def natural_period_start(*, period: Period, end_at: datetime) -> datetime:
    if period == "daily":
        return end_at.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        return end_at.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=end_at.weekday())
    return end_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
