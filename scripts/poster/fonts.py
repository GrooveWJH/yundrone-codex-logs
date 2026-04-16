from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, fontManager

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FONT_DIR = ROOT / "assets" / "NotoSansSC"
DEFAULT_FONT_CACHE_DIR = ROOT / "tmp" / "font-cache"
DEFAULT_FONT_URL = (
    "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/"
    "SimplifiedChinese/NotoSansCJKsc-Regular.otf"
)
FONT_FALLBACKS = [
    "Noto Sans SC",
    "SF Pro Display",
    "PingFang SC",
    "Hiragino Sans GB",
    "Arial Unicode MS",
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
]
_PRIMED_FONT_KEYS: set[tuple[str, ...]] = set()


def resolve_noto_font_paths(
    *,
    font_dir: Path | None = None,
    cache_dir: Path | None = None,
    font_url: str | None = None,
) -> dict[str, Path | None]:
    resolved: dict[str, Path | None] = {}
    variants = {
        "thin": "NotoSansSC-Thin.otf",
        "regular": "NotoSansSC-Regular.otf",
        "demilight": "NotoSansSC-DemiLight.otf",
        "bold": "NotoSansSC-Bold.otf",
        "light": "NotoSansSC-Light.otf",
        "medium": "NotoSansSC-Medium.otf",
        "black": "NotoSansSC-Black.otf",
    }
    font_dir = font_dir or DEFAULT_FONT_DIR
    cache_dir = cache_dir or DEFAULT_FONT_CACHE_DIR
    font_url = font_url if font_url is not None else DEFAULT_FONT_URL

    for key, filename in variants.items():
        local_path = font_dir / filename
        if local_path.exists():
            resolved[key] = local_path
            continue
        if key == "regular" and font_url:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached_path = cache_dir / filename
            if not cached_path.exists():
                urlretrieve(font_url, cached_path)
            resolved[key] = cached_path
            continue
        resolved[key] = None
    return resolved


def font_properties(*, path: Path | None, size: float, weight: str | int | None = None) -> FontProperties:
    if path is not None:
        fontManager.addfont(str(path))
        return FontProperties(fname=str(path), size=size)
    return FontProperties(family=FONT_FALLBACKS, size=size, weight=weight)


def register_font_paths(font_paths: dict[str, Path | None]) -> None:
    for path in font_paths.values():
        if path is not None:
            fontManager.addfont(str(path))


def prime_font_cache(
    *,
    font_dir: Path | None = None,
    cache_dir: Path | None = None,
    font_url: str | None = None,
) -> dict[str, Path | None]:
    font_paths = resolve_noto_font_paths(font_dir=font_dir, cache_dir=cache_dir, font_url=font_url)
    register_font_paths(font_paths)
    cache_key = tuple(str(path) for path in font_paths.values() if path is not None)
    if cache_key in _PRIMED_FONT_KEYS:
        return font_paths
    figure = Figure(figsize=(1, 1))
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.text(0.1, 0.7, "用量播报日统计", fontproperties=font_properties(path=font_paths.get("bold"), size=14))
    axis.text(0.1, 0.4, "杨庆彬", fontproperties=font_properties(path=font_paths.get("medium"), size=12))
    axis.text(0.1, 0.1, "2026/04/16 00:00", fontproperties=font_properties(path=font_paths.get("light"), size=10))
    figure.canvas.draw()
    figure.clear()
    _PRIMED_FONT_KEYS.add(cache_key)
    return font_paths
