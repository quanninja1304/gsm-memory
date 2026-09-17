import pytest

from gsm_memory.data.ledger import LedgerError, payload_hash, reduce_prefix, select_fact, validate_ledger


def record(rid, sid, at, seq, operation, assertions, targets=()):
    r={"record_id":rid,"source_id":sid,"scope_id":"scope","known_at":at,"commit_seq":seq,"operation":operation,"target_assertion_ids":list(targets),"assertions":assertions,"raw_payload":{}}
    r["payload_hash"]=payload_hash(r);return r


def assertion(aid,value):
    return {"assertion_id":aid,"logical_fact_id":"fact","subject_id":"d","predicate":"REPORTED_MEASURE","object":{"type":"integer","value":value},"qualifiers":{},"valid":{"kind":"point","at":"2026-01-01T00:00:00.000000Z"},"event_time":None,"source_refs":[]}


S={"a":{"authority_rank":10,"allowed_predicates":["REPORTED_MEASURE"],"can_correct_source_ids":["a"]},"b":{"authority_rank":10,"allowed_predicates":["REPORTED_MEASURE"],"can_correct_source_ids":["b"]}}


def test_replace_and_historical_prefix():
    rows=[record("r1","a","2026-01-01T00:00:00.000000Z",1,"assert",[assertion("a1",200)]),record("r2","a","2026-01-02T00:00:00.000000Z",2,"replace",[assertion("a2",240)],["a1"])]
    assert select_fact(reduce_prefix(rows,S,"2026-01-01T12:00:00.000000Z"),"fact",S)["value"]["value"]==200
    assert select_fact(reduce_prefix(rows,S,"2026-01-02T00:00:00.000000Z"),"fact",S)["value"]["value"]==240


def test_equal_rank_conflict_and_unauthorized_revision():
    rows=[record("r1","a","2026-01-01T00:00:00.000000Z",1,"assert",[assertion("a1",200)]),record("r2","b","2026-01-02T00:00:00.000000Z",2,"assert",[assertion("a2",240)])]
    assert select_fact(reduce_prefix(rows,S,"2026-01-03T00:00:00.000000Z"),"fact",S)["status"]=="unresolved_conflict"
    bad=rows+[record("r3","b","2026-01-03T00:00:00.000000Z",3,"retract",[],["a1"])]
    with pytest.raises(LedgerError): validate_ledger(bad,S)
