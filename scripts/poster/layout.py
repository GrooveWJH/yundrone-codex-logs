from __future__ import annotations

import math
from dataclasses import dataclass

from scripts.poster.models import PosterConfig, RankingItem

PANEL_WIDTH_PT = 420.0
LABEL_FONT_PT = 11.0
LABEL_CHAR_EM = 0.58
BAR_LABEL_GAP_PT = 5.0
GRIDLINE_PAD_PT = 8.0


@dataclass(frozen=True)
class ChartLayout:
    max_value: float
    ticks: list[float]
    track_width: float
    xlim: float
    bar_scale: float
    label_gap_data: float


def compact_tokens(value: int) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def compact_value(value: float, value_format: str) -> str:
    if value_format == "intensity":
        return f"{value:.3f}"
    return compact_tokens(int(value))


def axis_tick_label(value: float, _position: float) -> str:
    raw = int(value)
    if raw >= 1_000_000:
        return f"{raw / 1_000_000:.0f}M"
    if raw >= 1_000:
        return f"{raw / 1_000:.0f}K"
    return str(raw)


def metric_axis_tick_label(value: float, value_format: str) -> str:
    if value_format == "intensity":
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return axis_tick_label(value, 0.0)


def item_value(item: RankingItem) -> float:
    return item.metric_value if item.metric_value is not None else float(item.used_tokens)


def build_chart_layout(items: list[RankingItem], *, config: PosterConfig) -> ChartLayout:
    values = [item_value(item) for item in items]
    max_value = float(max(values)) if values else 0.0
    if not max_value:
        return ChartLayout(0.0, [0.0, 1.0], 1.0, 1.0, 1.0, 0.0)

    ticks, track_width, xlim = _axis_geometry(max_value)
    bar_scale, label_gap_data = _bar_params(max_value, track_width, xlim, config.value_format)
    return ChartLayout(max_value, ticks, track_width, xlim, bar_scale, label_gap_data)


def fig_gap_from_pt(points: float, *, figure_height_in: float) -> float:
    return points / (figure_height_in * 72.0)


def panel_header_anchor_x(track_width: float, xlim: float) -> float:
    return track_width / xlim


def nice_tick_step(target_step: float) -> float:
    if target_step <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(target_step))
    normalized = target_step / magnitude
    if normalized <= 1:
        step = 1
    elif normalized <= 2:
        step = 2
    elif normalized <= 5:
        step = 5
    else:
        step = 10
    return float(step * magnitude)


def _axis_geometry(max_value: float) -> tuple[list[float], float, float]:
    step = nice_tick_step(max_value / 6.0)
    track_width = float(math.ceil(max_value / step) * step)
    count = int(round(track_width / step))
    ticks = [round(index * step, 10) for index in range(count + 1)]
    xlim = track_width * 1.05
    return ticks, track_width, xlim


def _bar_params(max_value: float, track_width: float, xlim: float, value_format: str) -> tuple[float, float]:
    data_per_pt = xlim / PANEL_WIDTH_PT
    label_str = compact_value(max_value, value_format)
    text_data = len(label_str) * LABEL_FONT_PT * LABEL_CHAR_EM * data_per_pt
    gap_data = BAR_LABEL_GAP_PT * data_per_pt
    pad_data = GRIDLINE_PAD_PT * data_per_pt
    bar_max = track_width - text_data - gap_data - pad_data
    bar_scale = max(0.60, min(bar_max / max_value, 0.98))
    return bar_scale, gap_data
