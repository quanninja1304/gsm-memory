"""Data models for GSM Local Database."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class DriverRecord(BaseModel):
    driver_id: str
    driver_code: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    depot_name: str | None = None
    region: str | None = None
    service_type: str | None = None
    program: str | None = None
    status: str = "active"
    vehicle_model: str | None = None
    license_plate: str | None = None
    rating_avg: float = 5.0
    acceptance_rate: float = 1.0
    cancellation_rate_30d: float = 0.0
    completed_trips_count: int = 0
    cancelled_trips_count: int = 0
    created_at: str
    updated_at: str


class SnapshotRecord(BaseModel):
    snapshot_id: str
    label: str
    known_as_of: str
    scope: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_baseline: bool = False
    created_at: str


class TripRecord(BaseModel):
    trip_id: str
    driver_id: str
    snapshot_id: str | None = None
    start_time: str
    end_time: str | None = None
    pickup_address: str
    dropoff_address: str
    region: str | None = None
    service_type: str | None = None
    distance_km: float = 0.0
    fare_amount: int = 0
    outcome: Literal["completed", "cancelled"] = "completed"
    reason_code: str = "unspecified"
    cancel_party: str = "none"
    passenger_rating: int | None = None
    passenger_feedback: str | None = None
    notes: str | None = None
    created_at: str


class ChatSessionRecord(BaseModel):
    session_id: str
    title: str
    driver_id: str | None = None
    created_at: str
    updated_at: str
    is_active: bool = True
    messages_count: int = 0
    last_message_preview: str | None = None


class ChatMessageRecord(BaseModel):
    message_id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    status: str | None = "ANSWERED"
    query_plan: dict[str, Any] | None = None
    citations: list[dict[str, Any]] | None = None
    subgraph: dict[str, Any] | None = None
    latency_ms: float = 0.0
    created_at: str


class ContextMemoryItem(BaseModel):
    memory_id: str
    session_id: str
    driver_id: str | None = None
    memory_key: str
    memory_value: str
    confidence: float = 1.0
    source: str = "conversation"
    updated_at: str


class DatabaseStats(BaseModel):
    drivers_count: int
    trips_count: int
    snapshots_count: int = 0
    completed_trips_count: int
    cancelled_trips_count: int
    chat_sessions_count: int
    chat_messages_count: int
    context_memories_count: int
    db_size_bytes: int
    db_file_path: str

