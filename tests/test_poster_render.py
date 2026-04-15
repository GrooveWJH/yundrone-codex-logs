from __future__ import annotations

import inspect
import math
from datetime import datetime
from pathlib import Path

from PIL import Image

from scripts.poster import fonts, layout, render
from scripts.poster.models import PosterConfig, PosterRequest, RankingItem, RankingSnapshot


def _snapshot(period: str = "daily") -> RankingSnapshot:
    return RankingSnapshot(
        period=period,
        generated_at=int(datetime(2026, 4, 15, 22, 4).timestamp()),
        source="test",
        scope="filtered",
        items=[
            RankingItem(
                email="alpha@yundrone.cn",
                display_name="Alpha",
                raw_display_name="Alpha",
                username="alpha",
                used_tokens=30_770_000,
                request_count=10,
                rank=1,
            ),
            RankingItem(
                email="bravo@yundrone.cn",
                display_name="Bravo",
                raw_display_name="Bravo",
                username="bravo",
                used_tokens=17_420_000,
                request_count=8,
                rank=2,
            ),
            RankingItem(
                email="charlie@yundrone.cn",
                display_name="Charlie",
                raw_display_name="Charlie",
                username="charlie",
                used_tokens=7_020_000,
                request_count=4,
                rank=3,
            ),
            RankingItem(
                email="delta@yundrone.cn",
                display_name="Delta",
                raw_display_name="Delta",
                username="delta",
                used_tokens=1_370_000,
                request_count=2,
                rank=4,
            ),
            RankingItem(
                email="echo@yundrone.cn",
                display_name="Echo",
                raw_display_name="Echo",
                username="echo",
                used_tokens=869_100,
                request_count=1,
                rank=5,
            ),
        ],
    )


def _request(periods: list[str]) -> PosterRequest:
    return PosterRequest(
        snapshots=[_snapshot(period) for period in periods],
        config=PosterConfig(),
    )


def test_layout_scales_bars_so_top_label_stays_inside_last_gridline() -> None:
    snapshot = RankingSnapshot(
        period="monthly",
        generated_at=0,
        source="test",
        scope="filtered",
        items=[
            RankingItem(
                email="top@yundrone.cn",
                display_name="Top User",
                raw_display_name="Top User",
                username="top",
                used_tokens=135_259_738,
                request_count=1,
                rank=1,
            ),
            RankingItem(
                email="second@yundrone.cn",
                display_name="Second User",
                raw_display_name="Second User",
                username="second",
                used_tokens=34_845_207,
                request_count=1,
                rank=2,
            ),
        ],
    )

    chart_layout = layout.build_chart_layout(snapshot.items, config=PosterConfig())
    top_value = snapshot.items[0].used_tokens
    scaled_bar_end = top_value * chart_layout.bar_scale
    label_text = layout.compact_tokens(top_value)
    data_per_pt = chart_layout.xlim / layout.PANEL_WIDTH_PT
    text_data = len(label_text) * layout.LABEL_FONT_PT * layout.LABEL_CHAR_EM * data_per_pt
    label_right_edge = scaled_bar_end + chart_layout.label_gap_data + text_data
    right_padding = layout.GRIDLINE_PAD_PT * data_per_pt

    assert chart_layout.bar_scale < 1.0
    assert math.isclose(chart_layout.track_width, chart_layout.ticks[-1])
    assert label_right_edge <= chart_layout.track_width - right_padding + 1e-6


def test_render_build_figure_does_not_save_png() -> None:
    source = inspect.getsource(render.build_figure)

    assert "savefig" not in source


def test_fonts_prefers_local_noto_sans_sc_fonts(tmp_path: Path) -> None:
    font_dir = tmp_path / "NotoSansSC"
    font_dir.mkdir()
    regular = font_dir / "NotoSansSC-Regular.otf"
    bold = font_dir / "NotoSansSC-Bold.otf"
    light = font_dir / "NotoSansSC-Light.otf"
    medium = font_dir / "NotoSansSC-Medium.otf"
    for path in (regular, bold, light, medium):
        path.write_bytes(b"dummy-font")

    paths = fonts.resolve_noto_font_paths(font_dir=font_dir, cache_dir=tmp_path / "cache", font_url=None)

    assert paths["regular"] == regular
    assert paths["bold"] == bold
    assert paths["light"] == light
    assert paths["medium"] == medium


def test_render_period_subtitle_has_no_period_prefix() -> None:
    snapshot = _snapshot()

    assert "今日" not in render.period_subtitle(snapshot)
    assert "本周" not in render.period_subtitle(_snapshot("weekly"))
    assert "本月" not in render.period_subtitle(_snapshot("monthly"))


def test_render_constants_keep_current_visual_language() -> None:
    assert render.AXIS_TEXT == "#000000"
    assert render.BAR_FILL_COLOR == "#2f343b"
    assert render.BAR_PREMIUM_HIGHLIGHT_COLOR == "#565c64"
    assert render.DIVIDER_COLOR == "#4a4f57"
    assert render.MAIN_TITLE == "Codex token"
    assert render.REPORT_LABEL == "用量播报"
    assert render.header_period_label(["daily", "weekly", "monthly"]) == "日统计 / 周统计 / 月统计"
    assert 0.0 < render.PERIOD_BADGE_Y_OFFSET < 0.05
    assert 1.0 <= render.HEADER_ROW_AXES_Y <= 1.07


def test_render_premium_bar_keeps_layering_without_gradient() -> None:
    source = inspect.getsource(render.draw_right_rounded_bar)

    assert "premium" in source
    assert "imshow" not in source
    assert "np.zeros" not in source


def test_render_balances_outer_plot_whitespace_for_daily(tmp_path: Path) -> None:
    output = tmp_path / "daily.png"
    figure = render.build_figure(_request(["daily"]))
    figure.savefig(output, dpi=250, facecolor=render.FIG_BG)

    image = Image.open(output).convert("RGB")
    left_edge, right_edge = _grid_edge_columns(image)
    left_margin = left_edge
    right_margin = image.width - 1 - right_edge

    assert abs(left_margin - right_margin) <= 2


def test_render_matches_top_and_bottom_margins_to_plot_edges(tmp_path: Path) -> None:
    output = tmp_path / "daily_uniform_margins.png"
    figure = render.build_figure(_request(["daily"]))
    figure.savefig(output, dpi=250, facecolor=render.FIG_BG)

    image = Image.open(output).convert("RGB")
    left_edge, right_edge = _grid_edge_columns(image)
    plot_margin = (left_edge + (image.width - 1 - right_edge)) / 2.0
    top_margin, bottom_margin = _vertical_content_margins(image)

    assert abs(top_margin - plot_margin) <= 12
    assert abs(bottom_margin - plot_margin) <= 8


def _grid_edge_columns(image: Image.Image) -> tuple[int, int]:
    target = tuple(int(render.GRID_COLOR[i : i + 2], 16) for i in (1, 3, 5))
    y_start = int(image.height * 0.22)
    y_end = int(image.height * 0.92)
    threshold = max(40, int((y_end - y_start) * 0.45))
    matches: list[int] = []

    for x in range(image.width):
        count = 0
        for y in range(y_start, y_end):
            pixel = image.getpixel((x, y))
            if all(abs(channel - expected) <= 10 for channel, expected in zip(pixel, target)):
                count += 1
        if count >= threshold:
            matches.append(x)

    assert matches, "expected to find vertical grid lines in the rendered daily poster"
    return matches[0], matches[-1]


def _vertical_content_margins(image: Image.Image) -> tuple[int, int]:
    bg = image.getpixel((0, 0))
    top = None
    bottom = None

    for y in range(image.height):
        if any(image.getpixel((x, y)) != bg for x in range(image.width)):
            top = y
            break

    for y in range(image.height - 1, -1, -1):
        if any(image.getpixel((x, y)) != bg for x in range(image.width)):
            bottom = y
            break

    assert top is not None and bottom is not None, "expected visible rendered content"
    return top, image.height - 1 - bottom
