"""SQLite helpers for checkpointing and ledgers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


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


@asynccontextmanager
async def open_async_sqlite_saver(checkpoint_path: Path) -> AsyncIterator[Any]:
    """Open a LangGraph AsyncSqliteSaver for a given SQLite path.

    Note: LangGraph 1.0.5's AsyncSqliteSaver expects the connection to expose an
    `is_alive()` method, but `aiosqlite.Connection` does not provide it. We wrap
    the connection to satisfy that expectation.
    """
    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    class _AliveConnection:
        def __init__(self, conn: aiosqlite.Connection) -> None:
            self._conn = conn

        def is_alive(self) -> bool:
            return True

        def __getattr__(self, name: str) -> Any:
            return getattr(self._conn, name)

        def __await__(self) -> Any:
            return self._conn.__await__()

    async with aiosqlite.connect(str(checkpoint_path)) as conn:
        yield AsyncSqliteSaver(cast("Any", _AliveConnection(conn)))
