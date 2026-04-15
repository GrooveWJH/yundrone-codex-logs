"""Environment loading helpers."""

from __future__ import annotations

from dotenv import find_dotenv, load_dotenv


def load_project_env() -> None:
    """Load `.env` from the current working directory tree if present."""

    dotenv_path = find_dotenv(filename=".env", usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=False)
