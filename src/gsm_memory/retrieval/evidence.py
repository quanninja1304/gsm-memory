"""Normalized evidence and deterministic, gold-blind selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_kind: str
    source_locator: str
    content: str
    entity_refs: tuple[str, ...] = ()
    time_scope: str | None = None
    scope_id: str | None = None
    role_candidates: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    retrieval_stage: str = "unknown"
    rank: int = 0
    score: float = 0.0
    eligibility: str = "eligible"
    conflict_status: str = "none"
    coverage_status: str = "unknown"
    token_cost: int = 0


def select_evidence(items: list[EvidenceItem], *, token_budget: int, per_source_cap: int = 3) -> list[EvidenceItem]:
    """Select deterministically without reading gold roles or expected answers."""
    ordered = sorted(items, key=lambda x: (x.eligibility != "eligible", -x.score, x.rank, x.evidence_id))
    selected: list[EvidenceItem] = []
    source_counts: dict[str, int] = {}
    spent = 0
    for item in ordered:
        if item.eligibility != "eligible" or source_counts.get(item.source_kind, 0) >= per_source_cap:
            continue
        if spent + item.token_cost > token_budget:
            continue
        selected.append(item)
        spent += item.token_cost
        source_counts[item.source_kind] = source_counts.get(item.source_kind, 0) + 1
    return selected


def interval_eligible(*, valid_from: datetime, valid_to: datetime | None,
                      known_from: datetime, known_to: datetime | None,
                      at: datetime, as_of: datetime) -> bool:
    """Half-open valid/known eligibility for state assertions."""
    return (valid_from <= at and (valid_to is None or at < valid_to)
            and known_from <= as_of and (known_to is None or as_of < known_to))


def point_eligible(*, event_time: datetime, window_start: datetime,
                   window_end: datetime, known_from: datetime,
                   known_to: datetime | None, as_of: datetime) -> bool:
    """Point events use window membership and are never encoded as [t,t)."""
    return (window_start <= event_time < window_end and known_from <= as_of
            and (known_to is None or as_of < known_to))
