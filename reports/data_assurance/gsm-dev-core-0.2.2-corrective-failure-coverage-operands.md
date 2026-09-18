# gsm-dev-core-0.2.2 — coverage generation operand audit

## Status

`BLOCKED` before schema implementation or candidate materialization.

The new `coverage_artifact` contract is approved, and the intended high-level
subjects/domains are known. The current canonical generator inputs are still
insufficient to instantiate that contract without prohibited inference.

## Generator evidence

At `src/gsm_memory/data/build.py:223`, the generator creates coverage artifacts
from exactly three `(private label, member list)` pairs. At line 224 it writes
only artifact identity/type, members, count, `complete=true`, and a hash of the
member list. The configuration contains no structured coverage recipes.

For the 10-member artifact, D_B can be recovered by resolving all member trip
rows, but no declared valid window, boundary convention, source-set identity,
selector version, inclusion/exclusion criteria, completeness cutoff, or
correction/retraction policy exists.

For both empty artifacts, even subject and covered domain are absent from the
canonical operands. Supplying them requires interpreting the private labels
`coverage_dh` and `incident_db`, or consulting affected cases/support atoms.
Both derivations are explicitly forbidden.

Member event minimum/maximum times cannot be substituted for a declared
coverage window: that would describe observed members rather than the universe
within which absence/completeness is claimed.

## Per-artifact result

| Artifact | Members | Result |
| --- | ---: | --- |
| `28afa3ef-0535-5323-8a83-e99345c7022a` | 10 | Subject recoverable; window/source-set/completeness operands missing |
| `097e9c93-eabb-5dcd-b271-a5b2afa9e734` | 0 | Subject, domain, window, and source-set operands missing |
| `75b8a22c-6d1c-526f-b817-f0f0de55a818` | 0 | Subject, domain, window, and source-set operands missing |

This triggers stop conditions 1, 2, 3, and 9. The approved prose cannot be
silently converted into generator facts where the task requires values to come
from canonical structured generation operands.

## Required input

Continuation requires an explicitly approved, case-independent structured
coverage recipe for every artifact. It must pin exact subject, canonical domain,
valid window and boundary convention, public selector, source-set identity and
version, allowed sources, inclusion/exclusion criteria, completeness cutoff,
correction/retraction behavior, world/scope, and publication binding.

No `0.2.2` config, candidate, frozen release, or PASS certificate was created.
`gsm-dev-core-0.2.1` remains unchanged.
