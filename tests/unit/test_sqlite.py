from __future__ import annotations

from pathlib import Path

from vibe_check.sqlite import sqlite_path_from_conn_string


def test_sqlite_path_from_conn_string_memory() -> None:
    assert sqlite_path_from_conn_string(":memory:") == Path(":memory:")


def test_sqlite_path_from_conn_string_relative_plain() -> None:
    assert sqlite_path_from_conn_string("data/checkpoints/test.db") == Path(
        "data/checkpoints/test.db"
    )


def test_sqlite_path_from_conn_string_relative_sqlalchemy() -> None:
    assert sqlite_path_from_conn_string("sqlite:///data/checkpoints/test.db") == Path(
        "data/checkpoints/test.db"
    )


def test_sqlite_path_from_conn_string_absolute_sqlalchemy() -> None:
    assert sqlite_path_from_conn_string("sqlite:////tmp/test.db") == Path("/tmp/test.db")
