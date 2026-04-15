from __future__ import annotations

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


def axis_tick_label(value: float, _position: float) -> str:
    raw = int(value)
    if raw >= 1_000_000:
        return f"{raw / 1_000_000:.0f}M"
    if raw >= 1_000:
        return f"{raw / 1_000:.0f}K"
    return str(raw)


def build_chart_layout(items: list[RankingItem], *, config: PosterConfig) -> ChartLayout:
    del config
    values = [item.used_tokens for item in items]
    max_value = float(max(values)) if values else 0.0
    if not max_value:
        return ChartLayout(0.0, [0.0, 1.0], 1.0, 1.0, 1.0, 0.0)

    ticks, track_width, xlim = _axis_geometry(max_value)
    bar_scale, label_gap_data = _bar_params(max_value, track_width, xlim)
    return ChartLayout(max_value, ticks, track_width, xlim, bar_scale, label_gap_data)


def fig_gap_from_pt(points: float, *, figure_height_in: float) -> float:
    return points / (figure_height_in * 72.0)


def panel_header_anchor_x(track_width: float, xlim: float) -> float:
    return track_width / xlim


def nice_tick_step(target_step: float) -> int:
    magnitude = 10 ** max(len(str(int(target_step))) - 1, 0)
    normalized = target_step / magnitude
    if normalized <= 1:
        step = 1
    elif normalized <= 2:
        step = 2
    elif normalized <= 5:
        step = 5
    else:
        step = 10
    return int(step * magnitude)


def _axis_geometry(max_value: float) -> tuple[list[float], float, float]:
    step = nice_tick_step(max_value / 6.0)
    track_width = float(((int(max_value) + step - 1) // step) * step)
    ticks = [float(tick) for tick in range(0, int(track_width) + step, step)]
    xlim = track_width * 1.05
    return ticks, track_width, xlim


def _bar_params(max_value: float, track_width: float, xlim: float) -> tuple[float, float]:
    data_per_pt = xlim / PANEL_WIDTH_PT
    label_str = compact_tokens(int(max_value))
    text_data = len(label_str) * LABEL_FONT_PT * LABEL_CHAR_EM * data_per_pt
    gap_data = BAR_LABEL_GAP_PT * data_per_pt
    pad_data = GRIDLINE_PAD_PT * data_per_pt
    bar_max = track_width - text_data - gap_data - pad_data
    bar_scale = max(0.60, min(bar_max / max_value, 0.98))
    return bar_scale, gap_data
