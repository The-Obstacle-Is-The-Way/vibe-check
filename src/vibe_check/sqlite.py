"""SQLite helpers for checkpointing and ledgers."""

from __future__ import annotations

from pathlib import Path


def sqlite_path_from_conn_string(conn_string: str) -> Path:
    """Normalize a SQLite connection string into a filesystem path.

    Supports:
    - `:memory:`
    - `relative/or/absolute/path.db`
    - SQLAlchemy-style:
      - `sqlite:///relative/path.db`
      - `sqlite:////absolute/path.db`
    """
    raw = conn_string.strip()
    if raw == ":memory:":
        return Path(raw)

    if raw.startswith("sqlite:////"):
        return Path("/" + raw.removeprefix("sqlite:////"))

    if raw.startswith("sqlite:///"):
        return Path(raw.removeprefix("sqlite:///"))

    return Path(raw)
