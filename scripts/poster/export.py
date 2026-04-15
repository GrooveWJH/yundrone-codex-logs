from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def save_png(figure: Figure, output_path: Path, *, dpi: int = 250, facecolor: str = "#f5f6fa") -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=dpi, facecolor=facecolor)
    plt.close(figure)
    return output_path
