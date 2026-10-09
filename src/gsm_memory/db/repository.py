"""Repository pattern implementation for local SQLite storage."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gsm_memory.db.connection import create_connection, get_db_path, get_db_session
from gsm_memory.db.models import (
    ChatMessageRecord,
    ChatSessionRecord,
    ContextMemoryItem,
    DatabaseStats,
    DriverRecord,
    SnapshotRecord,
    TripRecord,
)
from gsm_memory.db.schema import init_schema


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalDatabaseRepository:
    """Provides high-level repository access to the SQLite database."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.init_db()

    def init_db(self) -> None:
        """Ensure schema exists."""
        with get_db_session(self.db_path) as conn:
            init_schema(conn)

    # =========================================================================
    # CHAT SESSIONS
    # =========================================================================

    def create_session(
        self,
        title: str | None = None,
        driver_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        s_id = session_id or str(uuid.uuid4())
        now = _now_iso()
        s_title = title or "Cuộc trò chuyện mới"
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, title, driver_id, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (s_id, s_title, driver_id, now, now),
            )
        return s_id

    def list_sessions(self, limit: int = 50) -> list[ChatSessionRecord]:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    s.session_id,
                    s.title,
                    s.driver_id,
                    s.created_at,
                    s.updated_at,
                    s.is_active,
                    COUNT(m.message_id) AS messages_count,
                    (SELECT content FROM chat_messages WHERE session_id = s.session_id ORDER BY created_at DESC LIMIT 1) AS last_message_preview
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                ChatSessionRecord(
                    session_id=r["session_id"],
                    title=r["title"],
                    driver_id=r["driver_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_active=bool(r["is_active"]),
                    messages_count=r["messages_count"],
                    last_message_preview=r["last_message_preview"],
                )
                for r in rows
            ]

    def get_session(self, session_id: str) -> ChatSessionRecord | None:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    s.session_id,
                    s.title,
                    s.driver_id,
                    s.created_at,
                    s.updated_at,
                    s.is_active,
                    COUNT(m.message_id) AS messages_count,
                    (SELECT content FROM chat_messages WHERE session_id = s.session_id ORDER BY created_at DESC LIMIT 1) AS last_message_preview
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                WHERE s.session_id = ?
                GROUP BY s.session_id
                """,
                (session_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return ChatSessionRecord(
                session_id=r["session_id"],
                title=r["title"],
                driver_id=r["driver_id"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                is_active=bool(r["is_active"]),
                messages_count=r["messages_count"],
                last_message_preview=r["last_message_preview"],
            )

    def update_session_title(self, session_id: str, title: str) -> None:
        now = _now_iso()
        with get_db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (title, now, session_id),
            )

    def set_session_driver(self, session_id: str, driver_id: str | None) -> None:
        valid_driver_id: str | None = None
        if driver_id:
            real_driver = self.get_driver(driver_id)
            if real_driver:
                valid_driver_id = real_driver.driver_id
        now = _now_iso()
        with get_db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE chat_sessions SET driver_id = ?, updated_at = ? WHERE session_id = ?",
                (valid_driver_id, now, session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        with get_db_session(self.db_path) as conn:
            cur = conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
            return cur.rowcount > 0

    # =========================================================================
    # CHAT MESSAGES
    # =========================================================================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        status: str = "ANSWERED",
        query_plan: dict[str, Any] | None = None,
        citations: list[dict[str, Any]] | None = None,
        subgraph: dict[str, Any] | None = None,
        latency_ms: float = 0.0,
        message_id: str | None = None,
        created_at: str | None = None,
    ) -> str:
        m_id = message_id or str(uuid.uuid4())
        now = created_at or _now_iso()
        qp_json = json.dumps(query_plan, ensure_ascii=False) if query_plan else None
        cit_json = json.dumps(citations, ensure_ascii=False) if citations else None
        sg_json = json.dumps(subgraph, ensure_ascii=False) if subgraph else None

        with get_db_session(self.db_path) as conn:
            # Insert message
            conn.execute(
                """
                INSERT INTO chat_messages (message_id, session_id, role, content, status, query_plan, citations, subgraph, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (m_id, session_id, role, content, status, qp_json, cit_json, sg_json, latency_ms, now),
            )
            # Update session's updated_at
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return m_id

    def get_messages(self, session_id: str, limit: int = 100) -> list[ChatMessageRecord]:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT message_id, session_id, role, content, status, query_plan, citations, subgraph, latency_ms, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            messages: list[ChatMessageRecord] = []
            for r in rows:
                qp = json.loads(r["query_plan"]) if r["query_plan"] else None
                cit = json.loads(r["citations"]) if r["citations"] else None
                sg = json.loads(r["subgraph"]) if r["subgraph"] else None
                msg_status = r["status"] if ("status" in r.keys() and r["status"]) else "ANSWERED"
                messages.append(
                    ChatMessageRecord(
                        message_id=r["message_id"],
                        session_id=r["session_id"],
                        role=r["role"],
                        content=r["content"],
                        status=msg_status,
                        query_plan=qp,
                        citations=cit,
                        subgraph=sg,
                        latency_ms=r["latency_ms"] or 0.0,
                        created_at=r["created_at"],
                    )
                )
            return messages

    # =========================================================================
    # CONTEXT MEMORY
    # =========================================================================

    def get_context(self, session_id: str) -> dict[str, str]:
        """Return dict of memory_key -> memory_value for active session."""
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT memory_key, memory_value FROM context_memory WHERE session_id = ?",
                (session_id,),
            )
            rows = cursor.fetchall()
            return {r["memory_key"]: r["memory_value"] for r in rows}

    def get_context_items(self, session_id: str) -> list[ContextMemoryItem]:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT memory_id, session_id, driver_id, memory_key, memory_value, confidence, source, updated_at
                FROM context_memory
                WHERE session_id = ?
                ORDER BY updated_at DESC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                ContextMemoryItem(
                    memory_id=r["memory_id"],
                    session_id=r["session_id"],
                    driver_id=r["driver_id"],
                    memory_key=r["memory_key"],
                    memory_value=r["memory_value"],
                    confidence=r["confidence"],
                    source=r["source"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def set_context_key(
        self,
        session_id: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source: str = "conversation",
        driver_id: str | None = None,
    ) -> None:
        valid_driver_id: str | None = None
        if driver_id:
            real_driver = self.get_driver(driver_id)
            if real_driver:
                valid_driver_id = real_driver.driver_id

        m_id = str(uuid.uuid4())
        now = _now_iso()
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO context_memory (memory_id, session_id, driver_id, memory_key, memory_value, confidence, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, memory_key) DO UPDATE SET
                    memory_value = excluded.memory_value,
                    driver_id = COALESCE(excluded.driver_id, context_memory.driver_id),
                    confidence = excluded.confidence,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (m_id, session_id, valid_driver_id, key, value, confidence, source, now),
            )

    def delete_context_key(self, session_id: str, key: str) -> None:
        with get_db_session(self.db_path) as conn:
            conn.execute(
                "DELETE FROM context_memory WHERE session_id = ? AND memory_key = ?",
                (session_id, key),
            )

    def clear_session_context(self, session_id: str) -> None:
        with get_db_session(self.db_path) as conn:
            conn.execute("DELETE FROM context_memory WHERE session_id = ?", (session_id,))

    def merge_slots_and_plan(
        self,
        session_id: str,
        slots: dict[str, Any] | Any,
        plan: dict[str, Any] | Any,
    ) -> None:
        """Extract conversational context entities from slots & plan and persist in memory."""
        try:
            # Convert slots/plan to dict if objects
            s_dict = slots if isinstance(slots, dict) else getattr(slots, "__dict__", {})
            p_dict = plan if isinstance(plan, dict) else getattr(plan, "__dict__", {})

            driver_id = p_dict.get("driver_id") or s_dict.get("driver_id")
            driver_mention = p_dict.get("driver_mention") or s_dict.get("driver_mention")
            time_scope = p_dict.get("time_scope") or s_dict.get("time_mention")
            snapshot_id = p_dict.get("snapshot_id") or s_dict.get("snapshot_id")
            policy_scope = p_dict.get("policy_scope") or (
                ", ".join(s_dict.get("policy_mentions", [])) if s_dict.get("policy_mentions") else None
            )
            intent = p_dict.get("intent") or s_dict.get("intent")
            missing_fields = p_dict.get("missing_fields") or s_dict.get("missing_slots")

            # Validate and normalize driver_id to real UUID
            valid_driver_id: str | None = None
            if driver_id:
                real_driver = self.get_driver(driver_id)
                if real_driver:
                    valid_driver_id = real_driver.driver_id

            # 1. Driver info
            if valid_driver_id:
                self.set_context_key(session_id, "driver_id", valid_driver_id, confidence=1.0, driver_id=valid_driver_id)
                self.set_session_driver(session_id, valid_driver_id)
            if driver_mention:
                self.set_context_key(session_id, "driver_mention", str(driver_mention), confidence=0.95, driver_id=valid_driver_id)

            # 2. Time scope
            if time_scope and str(time_scope).lower() not in ("none", "chưa có", ""):
                self.set_context_key(session_id, "time_scope", str(time_scope), confidence=0.9)

            # 3. Snapshot ID
            if snapshot_id:
                self.set_context_key(session_id, "snapshot_id", str(snapshot_id), confidence=1.0)

            # 4. Policy scope & topics
            if policy_scope:
                self.set_context_key(session_id, "policy_scope", str(policy_scope), confidence=0.9)

            policy_topics = p_dict.get("policy_topics") or s_dict.get("policy_topics")
            if policy_topics:
                if isinstance(policy_topics, list):
                    topics_str = ", ".join(str(t) for t in policy_topics if t)
                else:
                    topics_str = str(policy_topics)
                if topics_str.strip():
                    self.set_context_key(session_id, "policy_topics", topics_str.strip(), confidence=0.9)

            # 5. Last intent
            if intent:
                self.set_context_key(session_id, "last_intent", str(intent), confidence=0.85)

            # 6. Pending clarification
            if missing_fields:
                missing_str = ", ".join(missing_fields)
                self.set_context_key(session_id, "pending_clarification", missing_str, confidence=1.0)
            else:
                self.delete_context_key(session_id, "pending_clarification")
        except Exception as e:
            print(f"[DB Warning] merge_slots_and_plan failed: {e}")

    # =========================================================================
    # DRIVERS
    # =========================================================================

    def upsert_driver(self, d: DriverRecord) -> None:
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO drivers (
                    driver_id, driver_code, full_name, phone, email, depot_name, region,
                    service_type, program, status, vehicle_model, license_plate, rating_avg,
                    acceptance_rate, cancellation_rate_30d, completed_trips_count,
                    cancelled_trips_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(driver_id) DO UPDATE SET
                    driver_code = excluded.driver_code,
                    full_name = excluded.full_name,
                    phone = COALESCE(excluded.phone, drivers.phone),
                    email = COALESCE(excluded.email, drivers.email),
                    depot_name = COALESCE(excluded.depot_name, drivers.depot_name),
                    region = COALESCE(excluded.region, drivers.region),
                    service_type = COALESCE(excluded.service_type, drivers.service_type),
                    program = COALESCE(excluded.program, drivers.program),
                    status = excluded.status,
                    vehicle_model = COALESCE(excluded.vehicle_model, drivers.vehicle_model),
                    license_plate = COALESCE(excluded.license_plate, drivers.license_plate),
                    rating_avg = excluded.rating_avg,
                    acceptance_rate = excluded.acceptance_rate,
                    cancellation_rate_30d = excluded.cancellation_rate_30d,
                    completed_trips_count = excluded.completed_trips_count,
                    cancelled_trips_count = excluded.cancelled_trips_count,
                    updated_at = excluded.updated_at
                """,
                (
                    d.driver_id,
                    d.driver_code,
                    d.full_name,
                    d.phone,
                    d.email,
                    d.depot_name,
                    d.region,
                    d.service_type,
                    d.program,
                    d.status,
                    d.vehicle_model,
                    d.license_plate,
                    d.rating_avg,
                    d.acceptance_rate,
                    d.cancellation_rate_30d,
                    d.completed_trips_count,
                    d.cancelled_trips_count,
                    d.created_at,
                    d.updated_at,
                ),
            )

    def get_drivers(self, search: str | None = None) -> list[DriverRecord]:
        with get_db_session(self.db_path) as conn:
            if search:
                term = f"%{search}%"
                cursor = conn.execute(
                    """
                    SELECT * FROM drivers
                    WHERE driver_code LIKE ? OR full_name LIKE ? OR depot_name LIKE ?
                    ORDER BY driver_code ASC
                    """,
                    (term, term, term),
                )
            else:
                cursor = conn.execute("SELECT * FROM drivers ORDER BY driver_code ASC")
            rows = cursor.fetchall()
            return [DriverRecord(**dict(r)) for r in rows]

    def search_drivers_by_name(self, name: str) -> list[DriverRecord]:
        """Dynamically search drivers by name (supports accented, unaccented, word-level and ordered phrase matching)."""
        if not name or not name.strip():
            return []
        import unicodedata

        def _strip_accents(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s)
            return "".join([c for c in nfkd if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D").lower()

        clean_query = _strip_accents(name.strip())
        q_words = clean_query.split()
        if not q_words:
            return []

        all_drivers = self.get_drivers()
        matched: list[DriverRecord] = []
        for d in all_drivers:
            clean_fn = _strip_accents(d.full_name)
            d_words = clean_fn.split()

            if len(q_words) == 1:
                # Single word token: must be an exact word match in driver's name
                if q_words[0] in d_words:
                    matched.append(d)
            else:
                # Multi-word phrase:
                # 1. Contiguous word sublist match (e.g. "Thu Hà" in "Bùi Thu Hà")
                matched_contiguous = False
                for i in range(len(d_words) - len(q_words) + 1):
                    if d_words[i : i + len(q_words)] == q_words:
                        matched_contiguous = True
                        break
                if matched_contiguous:
                    matched.append(d)
                else:
                    # 2. Ordered word subset match (e.g. "Bùi Hà" in "Bùi Thu Hà")
                    it = iter(d_words)
                    if all(w in it for w in q_words):
                        matched.append(d)
        return matched

    def get_driver_by_code(self, code: str) -> DriverRecord | None:
        """Find driver by code, dynamically supporting formats like DRV-001 or D1."""
        if not code or not code.strip():
            return None
        c_clean = code.strip().upper()
        import re

        if re.match(r"^D\d+$", c_clean):
            num = int(c_clean[1:])
            c_clean = f"DRV-{num:03d}"
        return self.get_driver(c_clean)

    def get_driver(self, identifier: str) -> DriverRecord | None:
        """Find driver by UUID or driver_code."""
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM drivers WHERE driver_id = ? OR UPPER(driver_code) = UPPER(?)",
                (identifier, identifier),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return DriverRecord(**dict(r))

    def update_driver_metrics(self, driver_id: str) -> None:
        """Recompute trips count and cancel rate from trips table."""
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN outcome = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN outcome = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                    AVG(CASE WHEN passenger_rating IS NOT NULL THEN passenger_rating ELSE NULL END) AS avg_rating
                FROM trips
                WHERE driver_id = ?
                """,
                (driver_id,),
            )
            stat = cursor.fetchone()
            if not stat or stat["total"] == 0:
                return

            total = stat["total"]
            cancelled = stat["cancelled"] or 0
            completed = stat["completed"] or 0
            rate = round(cancelled / total, 4) if total > 0 else 0.0
            avg_rating = round(stat["avg_rating"], 2) if stat["avg_rating"] is not None else 5.0
            now = _now_iso()

            conn.execute(
                """
                UPDATE drivers SET
                    completed_trips_count = ?,
                    cancelled_trips_count = ?,
                    cancellation_rate_30d = ?,
                    rating_avg = ?,
                    updated_at = ?
                WHERE driver_id = ?
                """,
                (completed, cancelled, rate, avg_rating, now, driver_id),
            )

    # =========================================================================
    # SNAPSHOTS
    # =========================================================================

    def upsert_snapshot(self, s: SnapshotRecord) -> None:
        aliases_json = json.dumps(s.aliases, ensure_ascii=False)
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO snapshots (snapshot_id, label, known_as_of, scope, aliases, is_baseline, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    label = excluded.label,
                    known_as_of = excluded.known_as_of,
                    scope = excluded.scope,
                    aliases = excluded.aliases,
                    is_baseline = excluded.is_baseline
                """,
                (s.snapshot_id, s.label, s.known_as_of, s.scope, aliases_json, 1 if s.is_baseline else 0, s.created_at),
            )

    def list_snapshots(self) -> list[SnapshotRecord]:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM snapshots ORDER BY known_as_of DESC")
            rows = cursor.fetchall()
            snapshots: list[SnapshotRecord] = []
            for r in rows:
                al = json.loads(r["aliases"]) if r["aliases"] else []
                snapshots.append(
                    SnapshotRecord(
                        snapshot_id=r["snapshot_id"],
                        label=r["label"],
                        known_as_of=r["known_as_of"],
                        scope=r["scope"],
                        aliases=al,
                        is_baseline=bool(r["is_baseline"]),
                        created_at=r["created_at"],
                    )
                )
            return snapshots

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord | None:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
            r = cursor.fetchone()
            if not r:
                return None
            al = json.loads(r["aliases"]) if r["aliases"] else []
            return SnapshotRecord(
                snapshot_id=r["snapshot_id"],
                label=r["label"],
                known_as_of=r["known_as_of"],
                scope=r["scope"],
                aliases=al,
                is_baseline=bool(r["is_baseline"]),
                created_at=r["created_at"],
            )

    def find_snapshot_by_alias_or_time(
        self,
        time_query: str | None = None,
        time_resolved: str | None = None,
    ) -> SnapshotRecord | None:
        """Find snapshot dynamically using AI standardized ISO time or branch alias.
        Zero-hardcode approach:
        1. If AI resolved time is available (e.g. '2026-09-16', '2026-09', '2027-09'),
           match directly against database snapshots' known_as_of timestamp.
        2. If time_query specifies a direct UUID or exact branch code (e.g. 'L_CONFLICT'), match that.
        """
        import re

        snapshots = self.list_snapshots()
        if not snapshots:
            return None

        # 1. Exact UUID match if provided
        for target in (time_query, time_resolved):
            if target and target.strip():
                t_lower = target.strip().lower()
                for s in snapshots:
                    if s.snapshot_id.lower() == t_lower:
                        return s

        # 2. Match via standardized ISO format from AI Understanding (time_resolved)
        # e.g., '2026-09-16' matches known_as_of '2026-09-16T12:00:00.000000Z'
        # e.g., '2026-09' matches baseline '2026-09-17T12:00:00.000000Z'
        # e.g., '2027-09' matches nothing in database -> returns None
        target_iso = None
        for candidate in (time_resolved, time_query):
            if candidate and candidate.strip():
                c = candidate.strip()
                if re.match(r"^\d{4}(-\d{2})?(-\d{2})?", c):
                    target_iso = c
                    break

        if target_iso:
            candidates: list[SnapshotRecord] = []
            for s in snapshots:
                # known_as_of is ISO format: YYYY-MM-DDTHH:MM:SS
                if s.known_as_of.startswith(target_iso):
                    candidates.append(s)

            if candidates:
                # Prefer baseline snapshot if multiple match (e.g. at month level YYYY-MM)
                for c in candidates:
                    if c.is_baseline:
                        return c
                return candidates[0]
            # Target ISO specified (e.g. 2027-09 or 2025) but not present in database
            return None

        # 3. Match explicit branch names or benchmark aliases
        if time_query and time_query.strip():
            q = time_query.strip().lower()
            for s in snapshots:
                for alias in s.aliases:
                    if alias.lower() == q:
                        return s
            for s in snapshots:
                if q in s.label.lower():
                    return s

        return None

    # =========================================================================
    # TRIPS
    # =========================================================================

    def upsert_trip(self, t: TripRecord) -> None:
        with get_db_session(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trips (
                    trip_id, driver_id, snapshot_id, start_time, end_time, pickup_address, dropoff_address,
                    region, service_type, distance_km, fare_amount, outcome, reason_code,
                    cancel_party, passenger_rating, passenger_feedback, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trip_id) DO UPDATE SET
                    driver_id = excluded.driver_id,
                    snapshot_id = COALESCE(excluded.snapshot_id, trips.snapshot_id),
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    pickup_address = excluded.pickup_address,
                    dropoff_address = excluded.dropoff_address,
                    region = excluded.region,
                    service_type = excluded.service_type,
                    distance_km = excluded.distance_km,
                    fare_amount = excluded.fare_amount,
                    outcome = excluded.outcome,
                    reason_code = excluded.reason_code,
                    cancel_party = excluded.cancel_party,
                    passenger_rating = excluded.passenger_rating,
                    passenger_feedback = excluded.passenger_feedback,
                    notes = excluded.notes
                """,
                (
                    t.trip_id,
                    t.driver_id,
                    t.snapshot_id,
                    t.start_time,
                    t.end_time,
                    t.pickup_address,
                    t.dropoff_address,
                    t.region,
                    t.service_type,
                    t.distance_km,
                    t.fare_amount,
                    t.outcome,
                    t.reason_code,
                    t.cancel_party,
                    t.passenger_rating,
                    t.passenger_feedback,
                    t.notes,
                    t.created_at,
                ),
            )

    def count_driver_trips(
        self,
        driver_id: str,
        snapshot_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        """Count trips for driver filtered by snapshot or time interval."""
        with get_db_session(self.db_path) as conn:
            clauses = ["driver_id = ?"]
            params: list[Any] = [driver_id]
            if snapshot_id:
                clauses.append("(snapshot_id = ? OR snapshot_id IS NULL)")
                params.append(snapshot_id)
            if start_time:
                clauses.append("start_time >= ?")
                params.append(start_time)
            if end_time:
                clauses.append("start_time <= ?")
                params.append(end_time)
            q = f"SELECT COUNT(*) FROM trips WHERE {' AND '.join(clauses)}"
            return conn.execute(q, params).fetchone()[0]

    def get_trips(
        self,
        driver_id: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TripRecord]:
        with get_db_session(self.db_path) as conn:
            clauses: list[str] = []
            params: list[Any] = []
            if driver_id:
                clauses.append("driver_id = ?")
                params.append(driver_id)
            if outcome:
                clauses.append("outcome = ?")
                params.append(outcome)

            where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            params.extend([limit, offset])

            query = f"""
                SELECT * FROM trips
                {where_str}
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [TripRecord(**dict(r)) for r in rows]

    def get_trip(self, trip_id: str) -> TripRecord | None:
        with get_db_session(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM trips WHERE trip_id = ?", (trip_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return TripRecord(**dict(r))

    # =========================================================================
    # STATS
    # =========================================================================

    def get_stats(self) -> DatabaseStats:
        with get_db_session(self.db_path) as conn:
            drivers_count = conn.execute("SELECT COUNT(*) FROM drivers").fetchone()[0]
            trips_count = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
            snapshots_count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            completed_trips_count = conn.execute("SELECT COUNT(*) FROM trips WHERE outcome = 'completed'").fetchone()[0]
            cancelled_trips_count = conn.execute("SELECT COUNT(*) FROM trips WHERE outcome = 'cancelled'").fetchone()[0]
            chat_sessions_count = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
            chat_messages_count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
            context_memories_count = conn.execute("SELECT COUNT(*) FROM context_memory").fetchone()[0]

            size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return DatabaseStats(
                drivers_count=drivers_count,
                trips_count=trips_count,
                snapshots_count=snapshots_count,
                completed_trips_count=completed_trips_count,
                cancelled_trips_count=cancelled_trips_count,
                chat_sessions_count=chat_sessions_count,
                chat_messages_count=chat_messages_count,
                context_memories_count=context_memories_count,
                db_size_bytes=size,
                db_file_path=str(self.db_path),
            )
