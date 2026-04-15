from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

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


def resolve_noto_font_paths(
    *,
    font_dir: Path | None = None,
    cache_dir: Path | None = None,
    font_url: str | None = None,
) -> dict[str, Path | None]:
    resolved: dict[str, Path | None] = {}
    variants = {
        "regular": "NotoSansSC-Regular.otf",
        "bold": "NotoSansSC-Bold.otf",
        "light": "NotoSansSC-Light.otf",
        "medium": "NotoSansSC-Medium.otf",
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
        return FontProperties(fname=str(path), size=size, weight=weight)
    return FontProperties(family=FONT_FALLBACKS, size=size, weight=weight)
