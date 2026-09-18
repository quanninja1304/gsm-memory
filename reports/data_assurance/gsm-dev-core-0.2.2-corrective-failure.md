# gsm-dev-core-0.2.2 corrective attempt — blocked

## Summary

The corrective attempt stopped during the required public-provenance preflight.
No `0.2.2` config, candidate, frozen release, certificate, or PASS report was
created.

The approved catalog/artifact locator decision resolves the earlier provenance
problem for three `fleet_registry`, one `candidate_identity`, and three
`metric_definition` atoms. It does not resolve a newly identified defect:
three `synthetic_rule` atoms have no public source containing the rule semantics
at their selected snapshots.

## Blocking evidence

The affected atoms belong to semantic cases:

* `783302e6-d636-525f-a38f-f55f698deafb`;
* `2f0b9271-f893-52a6-916f-a1d94d9a94ac`;
* `660eaed8-1ede-5727-a0c5-c85d1cef17c6`.

The public `S_BRIDGE:v1` normalized revision is
`147ffa90-1e68-5b12-b8ac-d125cb01bc6b`, with SHA-256
`53134f9a893a5f9050d027baba313f649ceaff6a36932c531867336356c945d4`.
Its 76-character placeholder text contains neither the `fleet_region` premise
nor the incident exception. The actual rule appears only in
`private/oracle/policy_rules.jsonl`.

Additionally, all inspected required snapshot `documents.jsonl` files contain
zero synthetic-control document revisions. A ledger `POLICY_PUBLICATION`
assertion proves that a version was issued, but does not prove its rule content.
Consequently, a locator to that assertion would be source-valid for publication
state but unsound for the `synthetic_rule` evidence role.

This triggers stop conditions 1 and 10: a required source is not public in the
required snapshot, and additional support atoms lack genuine public provenance.

## Integrity and decision boundary

`gsm-dev-core-0.2.1` remains unchanged and its read-only verifier still passes
635/635 entries. No fake `ENTITY_NAME`, definition-publication, or synthetic-rule
ledger assertions were added.

Continuing requires a separate semantic/publication decision. One valid route
would be to approve deterministic rendering of the existing synthetic rule AST
into public synthetic clauses and include those revisions in the appropriate
snapshot allowlists. That changes public evidence visibility and therefore was
not inferred from the catalog/artifact-locator approval alone.

Until such a decision is approved, DFG03/DFG04 and A1_G3/A1_G4/A1_G5 are
blocked, and `gsm-dev-core-0.2.2` must not be frozen.
