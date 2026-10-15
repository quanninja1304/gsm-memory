"""SQLite Database Connection and Initialization for GSM Memory."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Default path for the local SQLite database
ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "gsm_local.db"


def get_db_path() -> Path:
    """Return the absolute Path to the SQLite database file."""
    env_path = os.getenv("GSM_LOCAL_DB_PATH")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = ROOT_DIR / p
        return p
    return DEFAULT_DB_PATH


def create_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create and configure a new SQLite connection."""
    if db_path is None:
        path = get_db_path()
    else:
        path = Path(db_path)
        if not path.is_absolute():
            path = ROOT_DIR / path

    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(path),
        timeout=10.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    # Performance and integrity pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    return conn


@contextmanager
def get_db_session(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database transactions."""
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
