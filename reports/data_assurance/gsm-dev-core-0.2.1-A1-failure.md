# gsm-dev-core-0.2.1 — A1 failure record

## Status

`A1: FAIL`

The frozen release remains byte-valid and reproducible, but it does not contain
enough source-level provenance or structured binding metadata for independent
semantic assurance. This finding does not prove that any frozen expected value
is wrong.

## Frozen evidence

| Item | Result |
| --- | --- |
| A0 frozen verifier | PASS, 635/635 |
| Missing inventory entries | 0 |
| Mismatched inventory entries | 0 |
| Unexpected inventory entries | 0 |
| Manifest SHA-256 | `61dddfd6c9f078b9b8c8288562c6196ae28a7ece390cd6d61d03041183b515b5` |
| Certificate SHA-256 | `e33158908c72d8c7cef9a96f9a5f3c0150fb5eecc187ac65c4d5f220950de67f` |
| Comparison SHA-256 | `cf1b105bd0beab4bd63cd774edf61460c49ad8ed6156ae9a734f205d5c721357` |
| Logical inventory digest | `4ed08a35393912150ffb731946965c5adc827a403835d4c9a96e9c333df16d11` |

## Verified defects

All 28 document-backed support locators have empty `clause_refs`. The affected
task distribution is T01=2, T02=11, T03=3, T04=3, T05=3, T06=2, and T07=4.
Consequently, none of the links pins a reviewed clause/span even though reviewed
spans exist for P154, P151, P05, and P23.

All 82 operational support locators contain only `public_snapshot_id`. None pins
the required world, ledger, scope, record, assertion, source identity, payload
hash, logical fact, valid/known extent, or revision lineage. They affect 34
queries.

All seven B01–B07 task bindings contain only identity/status metadata. They omit
the required source edition, clauses, conventions, answer scope, operands,
formula/evaluator, coverage, evidence roles, short circuits, and output schema.

Independent reconstruction was therefore blocked before evaluating any of the
42 cases. The existing production oracle is not accepted as the independent
reference because it relies on expected status, free-text matching, private
aliases, and case-specific constants.

## A1 gates

| Gate | Status | Reason |
| --- | --- | --- |
| A1_G1 Counterfactual/metamorphic | `not_run` | Stopped after frozen semantic-provenance defect was confirmed |
| A1_G2 AUX | `not_run` | Stopped after frozen semantic-provenance defect was confirmed |
| A1_G3 Proof/support links | `fail` | 28 document and 82 operational locators are incomplete |
| A1_G4 Snapshot/branch/isolation | `not_run` | Not used to mask the earlier required failure |
| A1_G5 Gold reconstruction | `blocked` | Structured bindings and locators are insufficient |
| A1_G6 Digests/closure | `not_run` | No successful A1 audit to close |

## Decision

A corrective `gsm-dev-core-0.2.2` release is required. It must be generated from
the source recipe, must preserve intended business semantics, and must not alter
`gsm-dev-core-0.2.1`. The corrective release may be frozen only after complete
DFG and A1 evidence passes. This report records the defect; it does not declare
the corrective release complete or ready.
