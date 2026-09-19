import asyncio
from pathlib import Path

from gsm_memory.adapters.graphiti import construct_mode_a


def test_mode_a_round_trip_search_and_repeat_write():
    snapshot = Path("data/gsm-dev-core-0.2.2/public/snapshots/296f03c2-6abf-57b3-8a17-249486d98fe8")
    report = asyncio.run(construct_mode_a(snapshot))
    assert report["records"] == 359
    assert report["capability_matrix"]["replace_records"] == 2
    assert report["capability_matrix"]["retract_records"] == 1
    assert report["capability_matrix"]["point_assertions"] > 1
    assert report["repeat_write_idempotent"] is True
    assert report["indexed_search_executed"] is True
    assert report["indexed_search_result_ids"]
