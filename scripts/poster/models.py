from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Period = Literal["daily", "weekly", "monthly"]
InputSource = Literal["api", "json", "memory-test-hook"]
SortKey = Literal["used_tokens_desc"]
DisplayNameStrategy = Literal["display_name_first"]


class PosterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RankingItem(PosterModel):
    email: str = ""
    display_name: str = ""
    raw_display_name: str = ""
    username: str = ""
    used_tokens: int = 0
    request_count: int = 0
    rank: int = 0


class RankingSnapshot(PosterModel):
    period: Period
    generated_at: int
    source: str
    scope: str
    items: list[RankingItem]


class DataPolicy(PosterModel):
    include_all_members: bool = False
    allowed_email_domains: list[str] = Field(default_factory=lambda: ["yundrone.cn"])
    excluded_emails: list[str] = Field(default_factory=lambda: ["codex@yundrone.cn"])
    top_n: int = 5
    sort_key: SortKey = "used_tokens_desc"
    display_name_strategy: DisplayNameStrategy = "display_name_first"


class PosterConfig(PosterModel):
    main_title: str = "Codex token"
    report_label: str = "用量播报"
    figure_height_in: float = 7.4
    subplot_bottom: float = 0.10
    subplot_top: float = 0.79
    period_badge_y_offset: float = 0.01
    header_row_axes_y: float = 1.03
    header_divider_clearance_pt: float = 10.0
    header_title_font_size: float = 14.0
    period_badge_font_size: float = 28.0
    subtitle_font_size: float = 12.0
    rank_font_size: float = 11.0
    name_font_size: float = 13.0
    value_font_size: float = 11.0
    font_dir: Path | None = None
    font_cache_dir: Path | None = None
    font_url: str | None = None


class PosterRequest(PosterModel):
    snapshots: list[RankingSnapshot]
    config: PosterConfig = Field(default_factory=PosterConfig)
