# Replace retained evidence with executable tests

## Context and follow-up

**Status.** T0–T5 complete within the migration scope below. This user instruction supersedes the preceding
G0–G4 retention design and repository guidance requiring old artifacts to remain.

**Why this document exists.** The [assurance design](../../docs/Ariadne/semantic-assurance.md#generated-validation-and-evidence-retention)
owns the selected test-only validation policy.

**What this document establishes.** Remove the retained evidence collection,
replace active dependencies with tests and actual test inputs, and keep generated
outputs under ignored target directories. Do not relocate archives as fixtures.

**Where to go next.** Read the [test index](../../tests/README.md) for executable
coverage and the [core MBT contract](../../mbt/README.md) for generated replay.

**What remains unresolved.** Real captures, native helpers and model runtimes
remain explicit prerequisites of their tests; deleting prior reports does not
establish fresh native, performance or release acceptance. Git history is not rewritten.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Stages

| Stage | Exit | Status |
| --- | --- | --- |
| T0 | Classify all consumers of retained records and choose executable replacements | Passed |
| T1 | Minimal exercised test inputs, explicit expected vectors and live validators | Passed |
| T2 | Remove archive production/publication and old-record-only gate reuse | Passed |
| T3 | Update maintained documentation, instructions and navigation | Passed |
| T4 | Remove all retained evidence and its LFS policy; add tests preventing regeneration | Passed |
| T5 | Fresh affected/root tests, MBT/PBT, link/layout checks and final dependency audit | Passed |

## Scope

Keep product-level captured-evidence semantics and schemas unchanged. Keep source
models, independent oracles, mutation controls, generated replay corpora, minimal
codec inputs and crash fixtures. Results, timing samples, raw logs, copied source
trees, historical acceptance flags and qualification archives are disposable run
products under target/. Retained passing flags are not test expectations.
Historical documentation may link to the exact Git revision for dated context;
current coverage is determined by executable tests and their stated prerequisites.

## Completed migration and validation

- Removed the whole working-tree collection: 5,229 files / approximately
  3,646.58 decimal MB. No qualification archive was renamed as a fixture.
- Essential inputs and explicit expected vectors total about 0.5 decimal MB.
  The Windows archive contains only three actual test inputs; the 666-case
  vector contains only expected sizes/digests. Independent live checks replace
  historical passing flags. Old runtime export and report-only MBT baselines
  are removed. All run products stay outside maintained source.
- Fresh PBT passes 3,200 configured cases. Core replay passes twelve traces /
  168 observations / five genuine compiled mutants; stateflow/IR replay passes
  64 traces / 326 observations / fifteen genuine compiled mutants. Source and
  tool identities stay unchanged through the selected run.
- The real scalar lifter passes 104 independent arithmetic/flag comparisons.
  All 247 Python controls, the composition/caller/loop oracles, default/core-only
  Rust tests, reports-only tests, format and all-feature/all-target Clippy pass.
  Layout, navigation, diff checks and core dependency activation checks pass.
- A feature-matrix check exposed private helpers compiled in configurations
  without their owners. Their gates now match input/BAP ownership, preserving
  input-library imports and the no-input MBT build. Intermediate failed runs
  remain transient diagnostics and never become passing records.
- Full native-core/capture, timing and release qualification remain unexercised:
  the installed analysis helper is source-stale and the required sealed
  dependency view is inactive. The fresh scalar check is a distinct narrow tier.
- Git history and already cached historical LFS objects were not rewritten or
  pruned. Dated documentation links to their exact historical Git revision;
  current coverage is defined by the [test matrix](../../tests/README.md).
