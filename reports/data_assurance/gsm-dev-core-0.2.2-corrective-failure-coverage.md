# gsm-dev-core-0.2.2 — coverage provenance blocker

## Status

`BLOCKED` during the complete public-provenance preflight. No `0.2.2` config,
candidate, frozen release, or certificate was created.

The approved synthetic-policy decision is implementable without case-specific
selection: select every synthetic rule with a matching synthetic-control catalog
identity and matching `POLICY_PUBLICATION`. This selects `S_BRIDGE:v1`,
`S_VERSION:v1`, and `S_VERSION:v2` source-wide.

## Newly identified blocker

The public coverage artifacts do not declare what population they cover. Their
rows contain only artifact identity/type, member IDs/count, a `complete` flag,
and a content hash. They omit subject, predicate/domain, valid window,
source-set universe, completeness boundary, and scope.

Three relevant artifacts are:

| Private recipe label | Artifact ID | Members | Content hash |
| --- | --- | ---: | --- |
| `coverage_db` | `28afa3ef-0535-5323-8a83-e99345c7022a` | 10 | `63acbd25c879b5a2d621e411d5cf3462d5d91d19e0816d8c12127087142b3b17` |
| `coverage_dh` | `097e9c93-eabb-5dcd-b271-a5b2afa9e734` | 0 | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `incident_db` | `75b8a22c-6d1c-526f-b817-f0f0de55a818` | 0 | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

The two empty artifacts are byte-logically indistinguishable except for their
artifact IDs. Nothing public states that one proves a D_H terminal population
and the other proves incident-register completeness for D_B.

This affects five support atoms across four semantic cases:

* `5e2d543e-5d1e-5fe8-abb2-46ca14e44519` — complete trip coverage;
* `e6127e6b-24f3-51ed-8502-b66c4e8065df` — absence of incident evidence;
* `b50703ea-0763-5253-8ad7-28a17a15c831` — absence of incident evidence;
* `70bf20f5-6a0b-5a99-8f51-c1cebe184b90` — empty terminal population;
* `f9741e6c-594c-5c25-9129-2e876d2d3e50` — completeness of that empty population.

Using `coverage_db`, `coverage_dh`, or `incident_db` names to supply these
semantics would infer public truth from private recipe aliases. Using the
affected cases would be circular. An `ARTIFACT_PUBLICATION` record proves only
that an artifact was published, not what universe its `complete=true` covers.

## Required decision

Continuation requires an explicit coverage-artifact contract and source-grounded
values for subject, covered predicate/domain, valid window, source-set identity,
completeness boundary, and scope. That decision must establish whether these
fields are missing packaging metadata for already intended claims or whether
adding them changes the observable semantics.

Until then, proof soundness, independent reconstruction, DFG03/DFG04, and
A1_G3/A1_G5 cannot pass. No PASS certificate may be issued.
