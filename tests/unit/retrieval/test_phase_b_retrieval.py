from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from gsm_memory.retrieval import BM25Index, ChunkConfig, EvidenceItem, construct_chunks, interval_eligible, point_eligible, select_evidence


RELEASE = Path("data/gsm-dev-core-0.2.2")


def test_chunk_ids_and_inventory_are_deterministic():
    a, links_a, inventory_a = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    b, links_b, inventory_b = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    assert a == b
    assert links_a == links_b
    assert inventory_a == inventory_b
    assert inventory_a["document_count"] == 9
    assert inventory_a["definition_count"] == 12


def test_chunk_identity_includes_coordinates_and_configuration():
    chunks, _, _ = construct_chunks(RELEASE, "debug_core")
    first = chunks[0]
    assert replace(first, normalized_start=first.normalized_start + 1) != first
    alternate, _, _ = construct_chunks(RELEASE, "debug_core", ChunkConfig(max_tokens=120, overlap=20))
    assert {c.chunk_id for c in chunks} != {c.chunk_id for c in alternate}


def test_projection_links_resolve_and_bm25_is_stable():
    chunks, links, _ = construct_chunks(RELEASE, "debug_core")
    ids = {c.chunk_id for c in chunks}
    assert links and all(link.runtime_id in ids for link in links)
    index = BM25Index(chunks)
    assert index.search("doanh số tối thiểu", top_k=5) == index.search("doanh số tối thiểu", top_k=5)


def test_selector_budget_and_per_source_cap_are_gold_blind():
    items = [EvidenceItem(str(i), kind, f"x:{i}", "evidence", score=10-i, rank=i, token_cost=10)
             for i, kind in enumerate(["document", "document", "document", "kg", "kg"])]
    selected = select_evidence(items, token_budget=30, per_source_cap=2)
    assert sum(item.token_cost for item in selected) <= 30
    assert sum(item.source_kind == "document" for item in selected) <= 2
    assert {item.source_kind for item in selected} == {"document", "kg"}


def test_temporal_eligibility_uses_half_open_intervals_and_point_windows():
    dt = lambda day: datetime(2026, 9, day, tzinfo=timezone.utc)
    assert interval_eligible(valid_from=dt(1), valid_to=dt(3), known_from=dt(1), known_to=None, at=dt(2), as_of=dt(2))
    assert not interval_eligible(valid_from=dt(1), valid_to=dt(3), known_from=dt(1), known_to=None, at=dt(3), as_of=dt(3))
    assert point_eligible(event_time=dt(2), window_start=dt(1), window_end=dt(3), known_from=dt(2), known_to=None, as_of=dt(2))
    assert not point_eligible(event_time=dt(3), window_start=dt(1), window_end=dt(3), known_from=dt(2), known_to=None, as_of=dt(3))
