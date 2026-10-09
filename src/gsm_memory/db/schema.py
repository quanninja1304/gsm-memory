"""Database schema and table initialization for GSM Local SQLite."""

from __future__ import annotations

import sqlite3
from typing import Sequence

DDL_STATEMENTS: Sequence[str] = [
    # 1. BẢNG TÀI XẾ (DRIVERS)
    """
    CREATE TABLE IF NOT EXISTS drivers (
        driver_id TEXT PRIMARY KEY,
        driver_code TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        depot_name TEXT,
        region TEXT,
        service_type TEXT,
        program TEXT,
        status TEXT DEFAULT 'active',
        vehicle_model TEXT,
        license_plate TEXT,
        rating_avg REAL DEFAULT 5.0,
        acceptance_rate REAL DEFAULT 1.0,
        cancellation_rate_30d REAL DEFAULT 0.0,
        completed_trips_count INTEGER DEFAULT 0,
        cancelled_trips_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_drivers_code ON drivers(driver_code);",
    "CREATE INDEX IF NOT EXISTS idx_drivers_name ON drivers(full_name);",
    "CREATE INDEX IF NOT EXISTS idx_drivers_depot ON drivers(depot_name);",

    # 2. BẢNG SNAPSHOTS THỜI GIAN (SNAPSHOTS)
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        known_as_of TEXT NOT NULL,
        scope TEXT,
        aliases TEXT, -- JSON array
        is_baseline INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_snapshots_known ON snapshots(known_as_of);",

    # 3. BẢNG CHUYẾN ĐI (TRIPS)
    """
    CREATE TABLE IF NOT EXISTS trips (
        trip_id TEXT PRIMARY KEY,
        driver_id TEXT NOT NULL REFERENCES drivers(driver_id) ON DELETE CASCADE,
        snapshot_id TEXT REFERENCES snapshots(snapshot_id),
        start_time TEXT NOT NULL,
        end_time TEXT,
        pickup_address TEXT NOT NULL,
        dropoff_address TEXT NOT NULL,
        region TEXT,
        service_type TEXT,
        distance_km REAL DEFAULT 0.0,
        fare_amount INTEGER DEFAULT 0,
        outcome TEXT NOT NULL, -- 'completed', 'cancelled'
        reason_code TEXT DEFAULT 'unspecified',
        cancel_party TEXT DEFAULT 'none', -- 'driver', 'passenger', 'system', 'none'
        passenger_rating INTEGER,
        passenger_feedback TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_trips_driver_id ON trips(driver_id);",
    "CREATE INDEX IF NOT EXISTS idx_trips_snapshot ON trips(snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_trips_outcome ON trips(outcome);",
    "CREATE INDEX IF NOT EXISTS idx_trips_start_time ON trips(start_time);",
    "CREATE INDEX IF NOT EXISTS idx_trips_region ON trips(region);",

    # 4. BẢNG PHIÊN HỘI THOẠI (CHAT SESSIONS)
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        driver_id TEXT REFERENCES drivers(driver_id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_driver ON chat_sessions(driver_id);",

    # 5. BẢNG TIN NHẮN CHAT (CHAT MESSAGES)
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        message_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
        role TEXT NOT NULL, -- 'user', 'assistant', 'system'
        content TEXT NOT NULL,
        status TEXT DEFAULT 'ANSWERED',
        query_plan TEXT, -- JSON
        citations TEXT, -- JSON
        subgraph TEXT, -- JSON
        latency_ms REAL DEFAULT 0.0,
        created_at TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at ASC);",

    # 6. BẢNG BỘ NHỚ NGỮ CẢNH (CONTEXT MEMORY)
    """
    CREATE TABLE IF NOT EXISTS context_memory (
        memory_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
        driver_id TEXT REFERENCES drivers(driver_id) ON DELETE SET NULL,
        memory_key TEXT NOT NULL,
        memory_value TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT 'conversation', -- 'user_explicit', 'ai_inferred', 'system'
        updated_at TEXT NOT NULL,
        UNIQUE(session_id, memory_key)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_memory_session ON context_memory(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_memory_driver ON context_memory(driver_id);",
]


def init_schema(conn: sqlite3.Connection) -> None:
    """Execute all schema DDL statements within the given SQLite connection and migrate columns."""
    with conn:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)

        # Migration: Ensure snapshot_id exists in trips table
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(trips)").fetchall()]
            if "snapshot_id" not in cols:
                conn.execute("ALTER TABLE trips ADD COLUMN snapshot_id TEXT REFERENCES snapshots(snapshot_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_snapshot ON trips(snapshot_id);")
        except Exception as e:
            print(f"[Schema Migration Warning] {e}")

        # Migration: Ensure status exists in chat_messages table and backfill clarification status
        try:
            msg_cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
            if "status" not in msg_cols:
                conn.execute("ALTER TABLE chat_messages ADD COLUMN status TEXT DEFAULT 'ANSWERED';")

            # Backfill existing clarification messages if missing_fields present
            import json
            cursor = conn.execute(
                "SELECT message_id, query_plan FROM chat_messages WHERE role = 'assistant' AND (status IS NULL OR status = 'ANSWERED');"
            )
            rows = cursor.fetchall()
            for r in rows:
                if r[1]:
                    try:
                        qp = json.loads(r[1])
                        if qp.get("missing_fields") or qp.get("clarification_reasons"):
                            conn.execute("UPDATE chat_messages SET status = 'NEEDS_CLARIFICATION' WHERE message_id = ?", (r[0],))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Schema Migration Warning] {e}")

