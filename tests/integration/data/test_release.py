import json
from pathlib import Path

import pytest

from gsm_memory.data.build import build_release
from gsm_memory.data.validation import validate_release


def test_small_release_build_contract(tmp_path):
    repo=Path(__file__).parents[3]
    out=tmp_path/"candidate"
    counts=build_release(repo,out,repo/"configs/datasets/gsm-dev-core-0.2.1.json")
    assert counts["real_sources"]==224 and counts["terminal_trips"]==80 and counts["semantic_cases"]==42
    report=validate_release(out,repo)
    assert report["summary"]["fail"]==0
    assert (out/"public/runtime_queries/test.jsonl").stat().st_size==0


def test_build_rejects_superseded_dataset_identity(tmp_path):
    repo=Path(__file__).parents[3]
    with pytest.raises(ValueError, match="dataset config identity mismatch"):
        build_release(repo,tmp_path/"candidate",repo/"configs/datasets/gsm-dev-core-0.2.json")
    assert not (tmp_path/"candidate").exists()
