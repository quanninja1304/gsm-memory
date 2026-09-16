# AGENTS.md

This file contains repository-level instructions for coding agents working in `memory/`.

Read this file before modifying code.

These instructions are persistent repository guidance. A task-specific hand-off prompt may further narrow the work, but it must not silently redefine frozen business/data semantics.

---

## 1. Project

**Project:** Scalable Retrieval for Memory-Augmented AI Agents
**Current dataset:** `gsm-dev-core-0.2`
**Current phase:** deterministic dataset generation and **Data Freeze Gate (DFG)**.

The project evaluates:

* document/policy retrieval;
* temporal KG retrieval;
* hybrid evidence retrieval;
* entity/time correctness;
* evidence selection;
* downstream agent reasoning.

The primary research object is **retrieval and evidence construction**, not a new generic memory framework.

Graphiti is the temporal KG reference baseline, but Graphiti belongs to the later **Benchmark Readiness Gate (BRG)**.

The current dataset build must be independently valid before Graphiti, embeddings, rerankers, or an LLM reader are introduced.

---

## 2. Read Before Coding

Before changing code:

1. Read this `AGENTS.md`.
2. Read `README.md` and relevant local README files.
3. Inspect the actual repository tree and Git state.
4. Inspect dependency manifests/locks and the active Python environment.
5. Read the normative documents below.
6. Search existing code/tests before creating new modules.
7. Preserve unrelated user changes.

Prefer:

```bash
rg --files
rg "<symbol-or-term>"
```

over guessing paths or APIs.

A directory mentioned in documentation is not evidence that its implementation already exists.

---

## 3. Source of Truth

The repository contains several design documents with different roles.

### Normative documents

#### `docs/02_synthetic_schema_and_data_design.md`

Normative for:

* business/data schema;
* predicates and types;
* identity;
* valid/known time;
* immutable ledger semantics;
* source precedence;
* correction/retraction;
* reported measures;
* derived metrics;
* task bindings;
* formulas;
* proof semantics;
* EX01–EX25;
* schema invariants.

Current business schema:

```text
schema_version = 1.1
```

Do not change these semantics merely because implementation is difficult.

#### `docs/05_dataset_release_spec.md`

Normative for the current release implementation:

```text
release_spec_version = 0.2.0
dataset_version      = gsm-dev-core-0.2
seed                 = 42
```

It defines:

* release composition;
* exact world recipe;
* ledger branches;
* scenario/case catalog;
* corpus profiles;
* output files;
* packaging;
* validation;
* DFG.

### Supporting contracts

#### `docs/01_problem_and_evaluation.md`

Normative for:

* RuntimeQuery;
* evidence interfaces;
* L1–L4 evaluation;
* incomplete relevance judgments;
* context/evidence scoring;
* failure attribution.

#### `docs/04_benchmark_to_dataset_mapping.md`

Methodology/design rationale.

It may guide benchmark mechanics but must not open new schema/domain scope.

#### `docs/03_dataset_and_graphiti_baseline_plan.md`

Historical/planning guidance.

Useful for repo grounding, logging, and C0 organization where still compatible.

Legacy pre-audit proposals do **not** override 02 or 05.

---

## 4. Conflict Handling

Do not silently reconcile conflicting specifications.

Use this rule:

* `02` owns **business/schema semantics**.
* `05` owns **release composition and implementation contract**.
* `01` owns **evaluation/request semantics**.
* `04` provides methodology.
* `03` is non-normative planning where superseded.

If `02` and `05` appear semantically incompatible:

1. identify the exact sections;
2. stop the affected stage;
3. report the conflict;
4. continue unrelated work if safe.

Do not change:

* thresholds;
* windows;
* formulas;
* expected answers;
* source precedence;
* temporal semantics;
* task scope

just to make tests or a baseline pass.

---

## 5. Current Scope

The current implementation target is:

```text
DATA_G0
→ DATA_G1
→ DATA_G2
→ DATA_G3
→ DATA_G4
→ DATA_G5
→ DATA_G6
→ Data Freeze Gate
```

The task is not complete after scaffolding, G0, or a successful import.

Current work ends at a real DFG result.

After DFG, separate work may implement:

```text
document baseline
Graphiti adapters
retrieval
agent reader
runtime experiments
Benchmark Readiness Gate
```

Do not begin those unless explicitly requested.

---

## 6. Hard Scope Boundaries

Do **not** add new business domains or predicates outside the frozen contract.

In particular, do not add:

* offer lifecycle;
* online sessions;
* raw revenue accounting;
* raw rating events;
* payroll;
* attendance;
* detailed cohorts;
* GPS simulation;
* fraud simulation;
* persona/preferences;
* policy eligibility verdict edges;
* generic financial DSL;
* generic policy override engine.

The only new operational predicates approved by Schema v1.1 are:

```text
REPORTED_MEASURE
DRIVER_PROGRAM
```

Existing legacy predicates and `cancel_rate_30d` remain available as defined in 02.

A deferred row remains deferred unless a new compatibility audit/version explicitly opens it.

---

## 7. Fixed Release Invariants

The current pilot must contain exactly:

```text
1 world W0
8 drivers
80 distinct terminal trips

25 scenario roots
32 ScenarioManifest variants
8 ledger timelines:
  L0
  + 7 alternate branches

42 semantic cases
42 direct query renderings

dev  = 42
test = 0
```

Do not count:

* duplicate observations;
* source copies;
* revisions;
* auxiliary conformance fixtures

as additional terminal trips.

The 42 queries are development/conformance fixtures, not 42 statistically independent samples.

Do not claim general model superiority or production accuracy from this catalogue.

---

## 8. Corpus Contract

The real GSM corpus contains:

```text
224 canonical individual articles
```

The aggregate duplicate file is excluded as an independent retrieval document.

Two corpus profiles are required.

### `debug_core@1`

Contains the six audited real snapshots:

* P154
* P151
* P05
* P23
* P172
* P26

Purpose:

* fast debugging;
* conformance;
* loader development;
* local tests.

### `retrieval_full@1`

Contains all:

```text
224 canonical real articles
```

This is the **default retrieval baseline corpus** once runtime retrieval is implemented.

Within the 224 documents:

```text
audited sources       = 6
primary-gold sources  = 4
retrieval-only        = remaining documents
```

Primary reviewed gold currently comes only from reviewed TEXT spans in:

* P154
* P151
* P05
* P23

P172 and P26 are audited distractors.

The remaining documents do not receive executable bindings or primary gold automatically.

---

## 9. Incomplete Relevance Judgments

Never assume:

```text
unreviewed = irrelevant
```

Use the distinction:

```text
reviewed positive
reviewed negative / graded judgment
unjudged
```

For semantic evaluation, the primary question is whether confirmed support/proof was retrieved.

If ranking metrics such as Precision or nDCG are later computed:

* state the judgment convention;
* report judgment coverage;
* do not silently map all unjudged documents to relevance `0`.

A document containing similar information does not automatically satisfy a task that explicitly requests another pinned source/edition.

---

## 10. Source Integrity

Pinned source assets are immutable inputs.

Important source locations include:

```text
external/policy_green_sm_corpus/
data/raw/archives/policy_green_sm_source.zip
```

Treat source checkout/archive as read-only unless explicitly instructed otherwise.

Expected archive SHA-256:

```text
cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9
```

Verify actual bytes.

Do not:

* crawl the website again;
* replace a pinned source with a newer page at the same URL;
* deduplicate by title;
* rewrite source wording;
* silently approve OCR;
* infer source identity from filename alone.

Normalization is limited to the contract, including:

```text
CRLF → LF
UTF-8
Unicode code-point offsets
[start, end)
1-based line numbers
```

Unknown evidence remains unknown.

---

## 11. Real Policy Time Semantics

Do not confuse:

```text
posted_date
captured_at
ARTIFACT_PUBLICATION availability
normative effective time
```

They are distinct concepts.

The benchmark availability assigned to real snapshots is not evidence that a policy was normatively effective at that instant.

Do not fabricate:

* real policy supersession;
* real historical website publication sequence;
* normative effective intervals

without source evidence.

Real T01–T07 tasks operate on the supplied edition/snapshot under the contract in 02/05.

Synthetic controls may have generated `POLICY_PUBLICATION` histories because those histories are part of the synthetic oracle.

---

## 12. Offline Requirement

`DATA_G0–DATA_G6` and DFG must run with:

```text
OPENAI_API_KEY unset
GEMINI_API_KEY unset
ANTHROPIC_API_KEY unset
other provider credentials unset
```

The dataset build must not require network access.

If a pinned input is missing:

```text
FAIL explicitly
```

Do not download or regenerate a replacement.

Dataset generation must not call:

* LLM APIs;
* embedding APIs;
* hosted rerankers;
* Graphiti LLM extraction;
* websites.

A build that fails solely because an API key is absent is an implementation bug.

---

## 13. Graphiti Boundary

The dataset package must not import or initialize Graphiti as part of G0–G6.

Data/evaluation modules must not have package-level side effects that initialize:

* Graphiti;
* Neo4j;
* Gemini;
* OpenAI;
* embedding clients;
* network services.

Allowed during DFG:

```text
canonical structured data
deterministic narratives
Mode A input manifests
Mode B input manifests
```

Not allowed during DFG:

```text
Graphiti UUIDs
graph nodes created by Graphiti
graph edges created by Graphiti
episodes created by Graphiti
embeddings
chunk IDs from an actual index
ProjectionLink outputs
ingestion receipts
retrieval latency
agent answers
```

Those are BRG/run artifacts.

---

## 14. Recommended Repository Areas

Inspect the repository before creating anything.

Expected areas include:

```text
src/gsm_memory/data/
src/gsm_memory/evaluation/
configs/datasets/
scripts/data/
tests/unit/
tests/conformance/
tests/integration/
artifacts/data_builds/
reports/data_freeze/
```

Prefer adding functionality inside existing package conventions.

Do not create a new generic framework simply because a clean-room architecture would look nicer.

Suggested modules are only suggestions, for example:

```text
contracts.py
ids.py
time.py
serialization.py
corpus.py
world.py
ledger.py
reducer.py
cases.py
snapshots.py
render.py
validation.py
cli.py
```

Create a module only when it has real responsibility.

Avoid empty scaffolding.

---

## 15. Dependency Direction

Keep dependencies approximately one-way:

```text
types / serialization / IDs / time
            ↓
        corpus + world
            ↓
          ledger
            ↓
          reducer
            ↓
    scenarios + gold/proofs
            ↓
      snapshots/packages
            ↓
          queries
            ↓
        validation
            ↓
         packaging
```

The gold evaluator may read private bindings/oracle information during offline generation.

Runtime/public code must not import private gold.

Avoid circular imports between:

* reducer;
* evaluator;
* generator;
* validator.

Shared semantic helpers must be small and independently tested.

---

## 16. Identity

Persistent semantic identity must be deterministic.

Use UUIDv5 and stable private keys exactly as specified in 05.

Do not use:

```python
hash(...)
id(obj)
list position
filesystem iteration order
mtime
wall-clock time
Graphiti UUID
```

for canonical persistent identity.

Imported snapshot IDs remain the IDs defined by the pinned source catalog.

If the same immutable SourceRecord appears in multiple branches:

```text
same ID
same payload
same hash
same commit_seq
```

If its content changes, it is a new record/version.

---

## 17. Time

Use timezone-aware datetime values.

Keep distinct:

```text
event_time
valid time
known / transaction time
ingestion time
```

Logical benchmark time must not be derived from execution wall clock.

Important rules:

* intervals are `[from, to)`;
* `unknown` is not infinity;
* point is not an empty interval;
* future-effective facts may already be known;
* future-known facts must not leak into historical prefixes;
* `known_to` must be derived from the visible prefix, not copied from future information.

Use:

```text
Asia/Ho_Chi_Minh
```

where BC01 requires the benchmark business calendar.

Canonical storage timestamps use UTC.

---

## 18. Exact Arithmetic

Do not use binary floating point for normative threshold/formula logic.

Use exact integer/rational arithmetic for:

```text
RM_ACCEPTANCE
RM_RATING
cancel_rate_30d
T02 charge formula
threshold comparisons
```

Examples:

```text
AR < 1/2
rating > 97/20
```

must preserve strict boundaries exactly.

Do not use rounded display values as truth.

---

## 19. Immutable Ledger

The ledger is append-only.

Support:

```text
assert
replace
retract
```

Corrections/retractions target canonical assertion IDs.

Never implement:

```text
latest timestamp wins
```

as the generic conflict rule.

Resolution depends on:

* exact fact key;
* scope;
* valid time;
* known cutoff;
* source authority;
* correction permissions;
* conflict rules.

Equal highest-authority contradictory claims remain:

```text
unresolved_conflict
```

unless the contract supplies a valid correction relation.

---

## 20. Branches

The current release contains:

```text
L0
L_NO_OPDAY
L_WRONG_DRIVER
L_CONFLICT
L_RETRACT
L_WRONG_WINDOW
L_NO_BRIDGE
L_NO_COVERAGE
```

Branches are separate timelines.

Never ingest or concatenate them into one timeline.

Branch mutations operate on record sets.

Shared records must remain byte/logically identical.

Masking must remove dependent artifacts/support that would leak the masked fact.

Do not use the private world to repair observable missing evidence.

---

## 21. Reported vs Derived Quantities

Keep these concepts separate.

### Reported measure

A source claims an already-computed value.

Examples:

```text
RM_REVENUE
RM_ACCEPTANCE
RM_RATING
RM_OPDAY
```

A reported measure does **not** imply that the dataset knows how GSM internally computed it.

Do not fabricate raw-event lineage.

### Derived metric

The benchmark computes the metric from the complete raw population under an explicit definition.

Current mandatory example:

```text
cancel_rate_30d
```

Exact aggregates require appropriate coverage/source-set evidence.

Do not use a reported value to replace a proof that requires raw derivation.

Do not require raw events when the task explicitly authorizes a reported measure.

---

## 22. Observable Truth vs Private World Truth

Keep two notions separate.

### Private world

Used to construct coherent synthetic data and test the generator.

### Observable gold

What an agent can validly conclude from the public evidence visible at a given prefix.

The evaluator must score according to observable evidence.

If private truth says `X` but visible evidence is missing:

```text
insufficient_evidence
```

may be the correct gold.

If visible equal-rank sources disagree:

```text
unresolved_conflict
```

may be the correct gold even when the private world knows which source is true.

Never let hidden oracle truth resolve a public conflict.

---

## 23. Gold Construction

Gold must be determined before retrieval/system outputs.

Gold may depend on:

* reviewed source clauses;
* approved task bindings;
* public definitions/conventions;
* visible ledger prefix;
* deterministic formulas;
* source authority;
* coverage.

Gold must not depend on:

* Graphiti;
* BM25;
* dense retrieval;
* reranker output;
* LLM judgment;
* baseline answer;
* proposed-system answer.

Never change gold because a baseline fails.

---

## 24. Support Atoms and Proofs

Semantic gold is based on:

```text
SupportAtom
EvidenceProof
GoldSupportLink
```

not physical retrieval-unit identity.

A proof must be:

* sound;
* sufficient;
* entity-correct;
* time-correct;
* source-correct;
* minimal according to task semantics.

Alternative sufficient proofs may exist.

Short-circuit logic is allowed when semantically valid.

Negative cases must not receive `Complete=1` from an empty proof.

Track explicitly:

```text
missing roles
conflict groups
candidate identities
available evidence
```

when appropriate.

Never use:

```text
Graphiti UUID
chunk ID
vector-store ID
```

as the semantic atom identity.

---

## 25. Query Rules

The canonical release has:

```text
42 direct Vietnamese query renderings
```

Do not add:

* paraphrases;
* implicit variants;
* composed queries;
* new discovery questions

to the 42-case canonical pilot unless the spec version changes.

T01–T07 continue to pin the intended edition/snapshot.

Do not remove the snapshot reference merely to make retrieval harder.

Document-discovery evaluation is a later diagnostic subset.

Public RuntimeQuery must not expose:

* C001–C042 aliases;
* task IDs;
* fault labels;
* expected status;
* proof hints;
* private AST;
* hidden operand values.

---

## 26. Scenario Sidecars

`ScenarioManifest` is private evaluation metadata.

It is not a business entity or business predicate.

Closed models must reject unknown keys when required by the spec.

Respect:

* required vs nullable distinction;
* mutation discriminators;
* parent DAG;
* ownership;
* FK constraints;
* split grouping;
* snapshot routing.

Do not weaken validators just to ingest malformed generated output.

---

## 27. Public / Private Boundary

Private directories must never be mounted into runtime retrieval.

Examples of private content:

```text
private/oracle/
private/eval/
task bindings
gold answers
proofs
mutation/fault metadata
private source-role labels
```

Examples of public content:

```text
operational records
published source registry
public document corpus
public definitions
snapshot packages
runtime query templates
Mode A/B source input packages
```

A public package must not reveal a future source merely through:

* catalog entry;
* filename;
* header;
* alias;
* known_to;
* artifact;
* cache;
* summary.

---

## 28. Corpus Profiles and Runtime Identity

Corpus profile identity must be versioned and hashable.

Do not use a bare flag such as:

```text
full_corpus=true
```

as sufficient experiment identity.

A corpus profile should identify at least:

```text
profile ID
profile version
member document IDs
member count
gold-bearing member IDs
retrieval-only member IDs
manifest/content hash
```

Future runtime index/cache identity must include corpus profile/hash.

Changing corpus membership after freeze requires a new version/release according to versioning rules.

---

## 29. Snapshot Isolation

Runtime snapshot packages are allowlists.

Runtime code may only access the package selected for the query.

The archive/root operational directory is not an unrestricted runtime data source.

Snapshot visibility applies to:

* ledger prefix;
* names;
* source registry;
* documents;
* definitions;
* coverage;
* source-set members;
* artifacts.

A loader must not bypass isolation by reading the full archive directly.

---

## 30. Mode A / Mode B Dataset Inputs

During DFG, create only source-level input packages.

### Mode A

Points to deterministic structured public data.

### Mode B

Points to deterministic textual observations representing the same public information.

Mode A and Mode B must preserve parity in:

* source identity;
* facts;
* valid time;
* known time;
* revision targets;
* provenance.

Mode B narratives must not add facts that are absent from the structured source.

Mode B narratives must not omit gold-critical facts.

Actual graph construction is BRG work.

---

## 31. Pipeline Stages

### DATA_G0 — Sources/contracts

Required:

* verify pinned source archive;
* inventory 224 canonical real articles;
* exclude aggregate duplicate;
* verify audited hashes/locators;
* build corpus profile plans;
* prepare definitions and source metadata.

### DATA_G1 — World

Build:

* entities;
* name histories;
* facts;
* 80 terminal trips;
* reports;
* incidents;
* synthetic policy controls.

Private world and observation plan remain separate.

### DATA_G2 — Publication ledger

Build:

* L0;
* seven alternate branches;
* immutable records;
* corrections/retractions;
* source registry;
* coverage;
* artifact publication.

Then validate ledger semantics.

### DATA_G3 — Cases and gold

Build:

* 25 roots;
* 32 variants;
* 42 semantic cases;
* expected statuses/values;
* support atoms;
* proofs;
* source links.

Use deterministic evaluator logic.

Do not hard-code the production oracle as:

```python
if case_id == "...":
    return expected_answer
```

Expected tables from the spec belong in independent tests.

### DATA_G4 — Packages

Materialize:

* private release files;
* public ledgers;
* narratives;
* documents;
* definitions;
* snapshots;
* Mode A/B input manifests.

Do not create system projection IDs.

### DATA_G5 — Queries

Render exactly:

```text
42 dev queries
0 test queries
```

`test.jsonl` must remain intentionally empty for this release.

### DATA_G6 — Validation/package closure

Execute all required:

```text
V01–V10
SM01–SM08
EX01–EX25
AUX groups
counterfactual checks
public/private leakage checks
corpus-profile checks
reproducibility prerequisites
```

Required failures are failures, not warnings.

---

## 32. Tests Are Part of Implementation

Do not postpone tests until G6.

Add tests as each semantic component is implemented.

At minimum include tests for:

* UUID generation;
* canonical serialization;
* hashes;
* rationals;
* timestamp normalization;
* interval boundaries;
* valid/known separation;
* source precedence;
* correction authorization;
* replacement;
* retraction;
* conflicts;
* coverage;
* metric denominator zero;
* reported undefined vs missing;
* branch closures;
* scenario DAG/FKs;
* proof sufficiency/minimality;
* public/private isolation;
* corpus profiles;
* deterministic query rendering.

Port EX01–EX25 exactly as conformance fixtures with their original semantics.

Do not rewrite them into the 42 release cases merely for convenience.

---

## 33. Auxiliary Conformance

Required auxiliary areas include:

```text
AUX_IDENTITY
AUX_TIME
AUX_EVENT
AUX_INCIDENT
AUX_REVISION
AUX_POLICY
AUX_ARTIFACT
AUX_CONTEXT
AUX_ACCESS
```

Tests must cover cases such as:

* same-name entities;
* historical aliases;
* future-effective facts;
* late events;
* same-time boundaries;
* corrected event time;
* open/resolved/reopened incidents;
* unauthorized corrections;
* equal-rank conflicts;
* missing bridge;
* stale artifacts;
* candidate-complete / selected-incomplete context;
* invalid scope/snapshot requests.

---

## 34. Independent Validation

Avoid circular correctness tests.

This is not sufficient:

```text
generator output == evaluator output
```

if both use the same faulty helper.

Maintain independent fixed expectations for:

* arithmetic;
* threshold boundaries;
* temporal boundaries;
* known-time pairs;
* conflicts;
* retractions;
* short-circuit logic;
* expected 42-case statuses.

Where practical, test the same rule through a separate small reference computation.

---

## 35. Reproducibility

Root seed:

```text
42
```

Seed derivation follows the algorithm in 05.

Do not let results depend on:

* thread count;
* filesystem order;
* dictionary insertion from uncontrolled inputs;
* wall time;
* random module global state;
* Python process hash randomization.

Assign semantic IDs before rendering.

Assign `commit_seq` globally from the planned union as specified.

Branches preserve shared sequence numbers, including gaps.

---

## 36. Logical vs Byte Hashes

Distinguish:

```text
logical hash
byte hash
```

Logical hash:

* sorted by declared primary key;
* canonical JSON;
* normalized timestamps;
* normalized rationals;
* deterministic key ordering.

Byte hash protects the materialized artifact.

Do not require Parquet byte identity across different toolchains.

Record:

* Python version;
* serializer version;
* Parquet engine/version;
* compression settings.

For the two official clean builds, use the same pinned toolchain.

---

## 37. Clean Build Requirement

Before DFG06:

1. build candidate A from empty output directory;
2. validate A;
3. build candidate B independently from empty output directory;
4. validate B;
5. compare complete logical inventories.

Do not reuse generated:

* ledger;
* cases;
* gold;
* manifests

from A in B.

Reusing immutable raw inputs and installed dependencies is allowed.

Do not compare only counts.

Compare semantic contents across the full declared inventory.

---

## 38. Data Freeze Gate

DFG has six required gates:

```text
DFG01
DFG02
DFG03
DFG04
DFG05
DFG06
```

DFG does not require:

* Graphiti;
* embeddings;
* retrieval score;
* agent accuracy;
* runtime latency.

A release filename does not prove freeze.

Allowed states before DFG06:

```text
DRAFT
VALIDATED
```

Only after all required checks have run successfully and clean-build logical equivalence is established may state become:

```text
FROZEN
```

No mandatory check may remain:

```text
FAIL
NOT_RUN
```

when declaring DFG PASS.

---

## 39. Freeze Safety

Never overwrite an existing frozen release.

If:

```text
data/gsm-dev-core-0.2/
```

already exists:

1. inspect its manifest/state/identity;
2. refuse unsafe overwrite;
3. use a staging candidate path;
4. report the conflict.

A freeze operation must verify that:

* candidate hashes;
* validation result;
* comparison evidence

still match what was approved.

Freeze must not merely replace:

```json
{"state": "VALIDATED"}
```

with:

```json
{"state": "FROZEN"}
```

without evidence checks.

---

## 40. CLI

Prefer a thin CLI around package logic.

If repository conventions do not already specify another interface, target:

```bash
python -m gsm_memory.data.cli --help

python -m gsm_memory.data.cli inventory ...
python -m gsm_memory.data.cli build ...
python -m gsm_memory.data.cli validate ...
python -m gsm_memory.data.cli compare-logical ...
python -m gsm_memory.data.cli freeze ...
```

CLI wrappers must not contain duplicate business logic.

Requirements:

* explicit config path;
* explicit output path;
* no silent append to an old candidate;
* nonzero exit code on required failure;
* validation does not mutate/fix its input;
* comparison produces machine-readable mismatch details;
* freeze verifies evidence.

---

## 41. Coding Style

Follow existing repository conventions first.

Otherwise:

* use Python type hints;
* favor small pure functions for semantics;
* keep I/O at boundaries;
* make data models explicit;
* prefer enums/literal types for closed domains;
* reject malformed input early;
* use descriptive domain names;
* avoid hidden mutable global state;
* document non-obvious temporal/provenance logic.

Avoid premature abstraction.

Do not create a generic “memory framework” to implement one frozen dataset.

---

## 42. Error Handling

Fail explicitly on contract violations.

Examples:

* missing pinned source;
* hash mismatch;
* unknown mutation type;
* duplicate semantic ID;
* invalid FK;
* unauthorized correction;
* impossible interval;
* unknown required definition;
* branch delta mismatch;
* leaked future object;
* malformed proof;
* missing mandatory validation.

Do not silently:

* coerce;
* drop;
* fill defaults;
* choose the nearest entity;
* choose the newest source;
* convert conflict to false;
* convert missing to zero.

---

## 43. Git and Existing Work

Before editing:

```bash
git status
```

when Git is available.

Preserve:

* unrelated working-tree changes;
* nested Git checkout state;
* historical conformance outputs;
* user-created files;
* existing Graphiti tests.

Do not:

* reset;
* clean;
* reformat the whole repo;
* upgrade unrelated dependencies;
* rewrite unrelated modules

without explicit reason.

Keep changes scoped to the task.

---

## 44. Dependencies

Reuse the existing dependency manager and lockfile.

Add dependencies only when necessary.

Data/DFG implementation should require only local deterministic libraries.

Do not upgrade Graphiti or provider SDKs to solve a data-generation problem.

If a dependency is added:

* state why;
* pin it according to repo conventions;
* update lockfiles;
* verify clean install/import behavior.

---

## 45. Do Not Fabricate Evidence

Never invent:

* Git commit hashes;
* source hashes;
* generated counts;
* test results;
* validation results;
* DFG status;
* timings;
* storage size;
* Graphiti behavior;
* projection IDs;
* API responses.

Use:

```text
pending
not_run
blocked
unsupported
```

when that is the actual state.

---

## 46. Progress Updates

For long coding tasks, report progress at meaningful milestones.

Good updates:

```text
DATA_G2 complete: reducer and seven branches implemented;
temporal/retraction tests pass; moving to G3.
```

or:

```text
Blocked in G0: P151 bytes do not match pinned hash.
G1 implementation can continue independently; DFG01 cannot pass.
```

Do not spam low-level file-by-file activity.

Do not stop after every milestone to ask for confirmation unless a genuine semantic decision is required.

---

## 47. Definition of Done for Current Phase

The current phase is complete only when there is evidence for:

```text
G0 complete
G1 complete
G2 complete
G3 complete
G4 complete
G5 complete
G6 complete

clean build A
clean build B
logical comparison

DFG01–DFG06 evaluated
```

Expected release-level counts include:

```text
224 canonical real documents
6 debug_core members
4 primary-gold real sources

8 drivers
80 terminal trips

25 roots
32 variants
8 ledgers

42 dev queries
0 test queries
```

Other record/atom/file counts must come from actual generated outputs.

---

## 48. Final Handoff Report

At completion report:

1. changed modules/configs/tests/docs;
2. exact commands executed;
3. exit status for important commands;
4. actual inventory counts;
5. validation results;
6. SM01–SM08 results;
7. EX01–EX25 results;
8. AUX results;
9. clean-build comparison;
10. DFG01–DFG06 table;
11. final release state;
12. manifest/digest if frozen;
13. remaining `pending`, `blocked`, or `unsupported` items.

Do not describe BRG as complete unless it was separately implemented and evidenced.

---

## 49. Out of Scope Until BRG

Unless explicitly requested later, do not implement as part of DFG:

* BM25/dense retrieval experiments;
* reranker tuning;
* Graphiti ingestion/search;
* LLM extraction;
* agent answering;
* embeddings;
* runtime latency benchmark;
* scale comparison;
* A-MEM/KG²RAG-style improvements;
* performance claims.

After DFG, these may be implemented against the frozen dataset.

Dataset/gold must not be retroactively changed to improve their scores.

---

## 50. Guiding Principle

When uncertain, preserve:

```text
identity
time
provenance
source scope
observable evidence
gold independence
reproducibility
```

over convenience.

A smaller explicit failure is preferable to silently manufacturing certainty.

The dataset is the experimental measuring instrument.

Treat changes to its semantics, sources, gold, or visibility rules accordingly.
