from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if sys.path[:1] != [root_str]:
        sys.path.insert(0, root_str)
    return root
