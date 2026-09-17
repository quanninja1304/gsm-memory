from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .primitives import canonical_bytes, sha256_bytes


class LedgerError(ValueError):
    pass


@dataclass(frozen=True)
class AcceptedAssertion:
    payload: dict[str, Any]
    record_id: str
    source_id: str
    known_from: str
    known_to: str | None


def payload_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k not in {"payload_hash", "commit_seq", "text"}}
    return sha256_bytes(canonical_bytes(body))


def validate_ledger(records: Iterable[dict[str, Any]], sources: dict[str, dict[str, Any]]) -> None:
    active: dict[str, dict[str, Any]] = {}
    seen_records: set[str] = set()
    last_key: tuple[str, int] | None = None
    for record in sorted(records, key=lambda r: (r["known_at"], r["commit_seq"])):
        if record["record_id"] in seen_records:
            raise LedgerError("duplicate record_id")
        seen_records.add(record["record_id"])
        key = (record["known_at"], record["commit_seq"])
        if last_key is not None and key <= last_key:
            raise LedgerError("replay order is not strict")
        last_key = key
        if payload_hash(record) != record["payload_hash"]:
            raise LedgerError(f"payload hash mismatch: {record['record_id']}")
        op, targets, assertions = record["operation"], record["target_assertion_ids"], record["assertions"]
        if op == "assert" and targets:
            raise LedgerError("assert cannot target")
        if op == "retract" and assertions:
            raise LedgerError("retract cannot assert")
        if op in {"replace", "retract"} and not targets:
            raise LedgerError("revision requires targets")
        source = sources[record["source_id"]]
        for target in targets:
            if target not in active:
                raise LedgerError(f"target is not active: {target}")
            old = active[target]
            if old["known_at"] >= record["known_at"]:
                raise LedgerError("target must be known strictly earlier")
            if old["source_id"] not in source["can_correct_source_ids"]:
                raise LedgerError("unauthorized correction")
            del active[target]
        for assertion in assertions:
            if assertion["assertion_id"] in active:
                raise LedgerError("duplicate active assertion")
            if assertion["predicate"] not in source["allowed_predicates"]:
                raise LedgerError("source predicate not authorized")
            active[assertion["assertion_id"]] = {**assertion, "source_id": record["source_id"], "known_at": record["known_at"]}


def reduce_prefix(
    records: Iterable[dict[str, Any]], sources: dict[str, dict[str, Any]], known_as_of: str
) -> list[AcceptedAssertion]:
    prefix = sorted((r for r in records if r["known_at"] <= known_as_of), key=lambda r: (r["known_at"], r["commit_seq"]))
    validate_ledger(prefix, sources)
    active: dict[str, AcceptedAssertion] = {}
    for record in prefix:
        for target in record["target_assertion_ids"]:
            old = active.pop(target)
            active[target] = AcceptedAssertion(old.payload, old.record_id, old.source_id, old.known_from, record["known_at"])
        for assertion in record["assertions"]:
            active[assertion["assertion_id"]] = AcceptedAssertion(assertion, record["record_id"], record["source_id"], record["known_at"], None)
    return sorted(active.values(), key=lambda x: x.payload["assertion_id"])


def select_fact(view: Iterable[AcceptedAssertion], logical_fact_id: str, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = [item for item in view if item.known_to is None and item.payload["logical_fact_id"] == logical_fact_id]
    if not candidates:
        return {"status": "missing", "values": []}
    best = min(sources[item.source_id]["authority_rank"] for item in candidates)
    top = [item for item in candidates if sources[item.source_id]["authority_rank"] == best]
    values = {canonical_bytes(item.payload["object"]) for item in top}
    if len(values) > 1:
        return {"status": "unresolved_conflict", "values": [item.payload["object"] for item in top]}
    return {"status": "accepted", "value": top[0].payload["object"], "assertion_ids": [item.payload["assertion_id"] for item in top]}
