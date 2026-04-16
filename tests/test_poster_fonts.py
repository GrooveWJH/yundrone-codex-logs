from __future__ import annotations

from pathlib import Path

from scripts.poster import fonts
from scripts.poster.models import PosterRequest, RankingItem, RankingSnapshot
from scripts.poster.render import build_figure
from switchbase_teamview import report_daemon


def test_build_figure_uses_explicit_font_file_for_cjk_labels() -> None:
    snapshot = RankingSnapshot(
        period="daily",
        generated_at=1_776_007_200,
        source="memory",
        scope="filtered",
        items=[RankingItem(display_name="杨庆彬", username="alice", used_tokens=120, request_count=3, rank=1)],
    )

    figure = build_figure(PosterRequest(snapshots=[snapshot]))
    text_files = {text.get_text(): text.get_fontproperties().get_file() for text in figure.texts}
    text_files.update({text.get_text(): text.get_fontproperties().get_file() for axis in figure.axes for text in axis.texts})

    assert Path(text_files["Codex token"]).name == "NotoSansSC-Bold.otf"
    assert Path(text_files["日统计"]).name == "NotoSansSC-Bold.otf"
    assert Path(text_files["用量播报"]).name == "NotoSansSC-Bold.otf"
    assert Path(text_files["杨庆彬"]).name == "NotoSansSC-Medium.otf"
    subtitle = next(text for text in text_files if text.endswith("CST"))
    assert Path(text_files[subtitle]).name == "NotoSansSC-Light.otf"


def test_report_daemon_primes_poster_fonts_before_running(monkeypatch) -> None:
    called: list[bool] = []

    monkeypatch.setattr(report_daemon, "_prime_poster_fonts", lambda: called.append(True))

    daemon = report_daemon.ReportDaemon(sleep_fn=lambda _: None)

    assert called == [True]
    assert daemon is not None


def test_font_properties_preserve_explicit_font_file_without_weight_lookup() -> None:
    font_paths = fonts.resolve_noto_font_paths()

    properties = fonts.font_properties(path=font_paths["bold"], size=18, weight="bold")

    assert Path(properties.get_file()).name == "NotoSansSC-Bold.otf"
