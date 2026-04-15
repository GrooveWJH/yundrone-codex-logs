from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from matplotlib.ticker import FuncFormatter

from scripts.poster import fonts, layout
from scripts.poster.models import Period, PosterConfig, PosterRequest, RankingItem, RankingSnapshot

FIG_BG = "#f5f6fa"
TEXT_PRIMARY = "#1a1a2e"
TEXT_SECONDARY = "#6c757d"
AXIS_TEXT = "#000000"
TRACK_COLOR = "#e9ecef"
GRID_COLOR = "#dee2e6"
DIVIDER_COLOR = "#4a4f57"
BAR_FILL_COLOR = "#2f343b"
BAR_PREMIUM_HIGHLIGHT_COLOR = "#565c64"
RANK_COLORS = ["#f5a623", "#9b9b9b", "#b87333", "#adb5bd", "#adb5bd"]
PERIOD_TITLES: dict[Period, str] = {"daily": "日统计", "weekly": "周统计", "monthly": "月统计"}
MAIN_TITLE = "Codex token"
REPORT_LABEL = "用量播报"
HEADER_ROW_AXES_Y = 1.03
PERIOD_BADGE_Y_OFFSET = 0.01
_TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


def build_figure(request: PosterRequest) -> Figure:
    config = request.config
    plt.rcParams["font.sans-serif"] = fonts.FONT_FALLBACKS
    plt.rcParams["axes.unicode_minus"] = False
    font_paths = fonts.resolve_noto_font_paths(
        font_dir=config.font_dir,
        cache_dir=config.font_cache_dir,
        font_url=config.font_url,
    )
    font_set = _font_set(config, font_paths)
    fig_width = 6.8 * len(request.snapshots) + 0.8
    fig, axes = plt.subplots(1, len(request.snapshots), figsize=(fig_width, config.figure_height_in))
    axes_list = [axes] if len(request.snapshots) == 1 else list(axes)
    fig.patch.set_facecolor(FIG_BG)

    for axis, snapshot in zip(axes_list, request.snapshots):
        _draw_rank_panel(axis, snapshot, config, font_set)

    left_margin = 0.065 if len(request.snapshots) > 1 else 0.1
    plt.subplots_adjust(
        left=left_margin,
        right=0.98,
        top=config.subplot_top,
        bottom=config.subplot_bottom,
        wspace=0.24,
    )
    left_x, right_x = _center_axes_on_plot_edges(axes_list, request.snapshots, config)
    outer_margin = min(left_x, 1.0 - right_x)
    title_row_y = 1.0 - outer_margin

    title_text = fig.text(
        left_x,
        title_row_y,
        config.main_title,
        color=TEXT_PRIMARY,
        fontproperties=font_set["header_title"],
        ha="left",
        va="top",
    )
    period_text = fig.text(
        right_x,
        title_row_y - config.period_badge_y_offset,
        header_period_label([snapshot.period for snapshot in request.snapshots]),
        color=TEXT_PRIMARY,
        fontproperties=font_set["period_title"],
        ha="right",
        va="top",
    )

    _align_bottom_margin(fig, axes_list, target_margin=outer_margin)
    left_x, right_x = _center_axes_on_plot_edges(axes_list, request.snapshots, config)
    outer_margin = min(left_x, 1.0 - right_x)
    title_row_y = 1.0 - outer_margin
    title_text.set_position((left_x, title_row_y))
    period_text.set_position((right_x, title_row_y - config.period_badge_y_offset))
    divider_y = _header_divider_layout_for_axis(
        axes_list[0],
        config=config,
    )["divider_y"]
    fig.lines.append(
        plt.Line2D(
            [left_x, right_x],
            [divider_y, divider_y],
            transform=fig.transFigure,
            color=DIVIDER_COLOR,
            linewidth=1.2,
        )
    )
    return fig


def period_subtitle(snapshot: RankingSnapshot) -> str:
    end = datetime.fromtimestamp(snapshot.generated_at, tz=_TZ_SHANGHAI)
    fmt_hm = "%H:%M"
    fmt_md = "%m/%d"
    if snapshot.period == "daily":
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        return f"{start.strftime('%Y/%m/%d')} {start.strftime(fmt_hm)} – {end.strftime(fmt_hm)} CST"
    if snapshot.period == "weekly":
        start = (end - timedelta(days=end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return f"{start.strftime(fmt_md)} {start.strftime(fmt_hm)} – {end.strftime(fmt_md)} {end.strftime(fmt_hm)} CST"
    start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return f"{start.strftime('%Y/%m')}/01 {start.strftime(fmt_hm)} – {end.strftime(fmt_md)} {end.strftime(fmt_hm)} CST"


def header_period_label(periods: list[Period]) -> str:
    return " / ".join(PERIOD_TITLES[period] for period in periods)


def draw_right_rounded_bar(
    axis: Axes,
    *,
    y_center: float,
    width: float,
    height: float,
    color: str,
    premium: bool = False,
) -> None:
    if width <= 0:
        return
    radius = min(height / 2.0, width / 2.0)
    rect_width = max(width - radius, 0.0)
    axis.add_patch(
        Rectangle((0.0, y_center - height / 2.0), rect_width, height, facecolor=color, edgecolor="none", zorder=3)
    )
    if premium and rect_width > 0:
        axis.add_patch(
            Rectangle(
                (0.0, y_center - height / 2.0),
                rect_width,
                height * 0.30,
                facecolor=BAR_PREMIUM_HIGHLIGHT_COLOR,
                edgecolor="none",
                zorder=4,
            )
        )
    axis.add_patch(Circle((rect_width, y_center), radius=radius, facecolor=color, edgecolor="none", zorder=3))


def draw_track(axis: Axes, *, y_center: float, width: float, height: float) -> None:
    radius = height / 2.0
    rect_width = max(width - radius, 0.0)
    axis.add_patch(
        Rectangle((0.0, y_center - height / 2.0), rect_width, height, facecolor=TRACK_COLOR, edgecolor="none", zorder=1)
    )
    axis.add_patch(Circle((rect_width, y_center), radius=radius, facecolor=TRACK_COLOR, edgecolor="none", zorder=1))


def _draw_rank_panel(axis: Axes, snapshot: RankingSnapshot, config: PosterConfig, font_set: dict[str, object]) -> None:
    axis.set_facecolor(FIG_BG)
    chart_layout = layout.build_chart_layout(snapshot.items, config=config)
    header_right_x = layout.panel_header_anchor_x(chart_layout.track_width, chart_layout.xlim)
    axis.text(0.0, config.header_row_axes_y, config.report_label, ha="left", va="bottom", transform=axis.transAxes, color=TEXT_PRIMARY, clip_on=False, fontproperties=font_set["period_title"])
    axis.text(header_right_x, config.header_row_axes_y, period_subtitle(snapshot), ha="right", va="bottom", transform=axis.transAxes, color=TEXT_SECONDARY, clip_on=False, fontproperties=font_set["subtitle"])

    if not snapshot.items:
        axis.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=axis.transAxes, color=TEXT_SECONDARY, fontproperties=font_set["name"])
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
        return

    bar_height = 0.46
    y_positions = list(range(len(snapshot.items)))
    for index, (y_pos, item) in enumerate(zip(y_positions, snapshot.items)):
        draw_track(axis, y_center=y_pos, width=chart_layout.track_width, height=bar_height)
        draw_right_rounded_bar(
            axis,
            y_center=y_pos,
            width=item.used_tokens * chart_layout.bar_scale,
            height=bar_height,
            color=BAR_FILL_COLOR,
            premium=index < 3,
        )
    axis.set_ylim(-1.05, len(snapshot.items) - 0.3)
    axis.set_xlim(0, chart_layout.xlim)
    axis.invert_yaxis()
    axis.set_yticks([])
    axis.set_xticks(chart_layout.ticks)
    axis.xaxis.set_major_formatter(FuncFormatter(layout.axis_tick_label))
    axis.tick_params(axis="x", colors=AXIS_TEXT, labelsize=10, length=0, pad=8)
    axis.xaxis.grid(True, color=GRID_COLOR, linestyle="-", linewidth=0.8)
    axis.set_axisbelow(True)
    for spine in axis.spines.values():
        spine.set_visible(False)
    _draw_labels(axis, snapshot.items, chart_layout)


def _draw_labels(axis: Axes, items: list[RankingItem], chart_layout: layout.ChartLayout) -> None:
    for index, (y_pos, item) in enumerate(zip(range(len(items)), items), start=1):
        label_y = y_pos - 0.46
        axis.text(-chart_layout.max_value * 0.005, label_y, f"#{index}", ha="right", va="center", color=RANK_COLORS[index - 1], fontsize=11, fontweight="light")
        axis.text(chart_layout.max_value * 0.012, label_y, item.display_name, ha="left", va="center", color=TEXT_PRIMARY, fontsize=13)
        axis.text(item.used_tokens * chart_layout.bar_scale + chart_layout.label_gap_data, y_pos, layout.compact_tokens(item.used_tokens), ha="left", va="center", color=TEXT_SECONDARY, fontsize=11)


def _font_set(config: PosterConfig, font_paths: dict[str, object]) -> dict[str, object]:
    return {
        "header_title": fonts.font_properties(path=font_paths.get("medium") or font_paths.get("bold"), size=config.header_title_font_size, weight="light"),
        "period_title": fonts.font_properties(path=font_paths.get("bold"), size=config.period_badge_font_size, weight="bold"),
        "subtitle": fonts.font_properties(path=font_paths.get("light"), size=config.subtitle_font_size, weight="light"),
        "name": fonts.font_properties(path=font_paths.get("regular"), size=config.name_font_size, weight="regular"),
    }


def _header_divider_layout_for_axis(axis: Axes, *, config: PosterConfig) -> dict[str, float]:
    row_fig_y = _figure_y_from_axes(axis, config.header_row_axes_y)
    divider_y = row_fig_y - layout.fig_gap_from_pt(config.header_divider_clearance_pt, figure_height_in=config.figure_height_in)
    return {"row_y": row_fig_y, "divider_y": divider_y}


def _figure_y_from_axes(axis: Axes, axes_y: float) -> float:
    _, y0, _, height = axis.get_position().bounds
    return y0 + height * axes_y


def _figure_x_from_axes(axis: Axes, axes_x: float) -> float:
    x0, _, width, _ = axis.get_position().bounds
    return x0 + width * axes_x


def _center_axes_on_plot_edges(axes: list[Axes], snapshots: list[RankingSnapshot], config: PosterConfig) -> tuple[float, float]:
    left_x = _figure_x_from_axes(axes[0], 0.0)
    last_layout = layout.build_chart_layout(snapshots[-1].items, config=config)
    right_x = _figure_x_from_axes(axes[-1], layout.panel_header_anchor_x(last_layout.track_width, last_layout.xlim))
    delta = (1.0 - right_x - left_x) / 2.0
    for axis in axes:
        x0, y0, width, height = axis.get_position().bounds
        axis.set_position([x0 + delta, y0, width, height])
    left_x = _figure_x_from_axes(axes[0], 0.0)
    right_x = _figure_x_from_axes(axes[-1], layout.panel_header_anchor_x(last_layout.track_width, last_layout.xlim))
    return left_x, right_x


def _align_bottom_margin(fig: Figure, axes: list[Axes], *, target_margin: float) -> None:
    fig.canvas.draw()
    bottoms: list[float] = []
    for axis in axes:
        for label in axis.get_xticklabels():
            if label.get_text():
                bbox = label.get_window_extent(renderer=fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
                bottoms.append(bbox.y0)
    delta = target_margin - (min(bottoms) if bottoms else 0.0)
    for axis in axes:
        x0, y0, width, height = axis.get_position().bounds
        axis.set_position([x0, y0 + delta, width, height])
