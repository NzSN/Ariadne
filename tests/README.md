# Executable validation

## Context and follow-up

**Status.** Current test-based validation policy. Retained qualification reports,
archives and historical pass flags have been removed at the user's request.

**Why this document exists.** The [assurance contract](../docs/Ariadne/semantic-assurance.md#generated-validation-and-evidence-retention)
replaces the retained collection with executable tests and actual test inputs.

**What this document establishes.** Tests define current expectations. Models,
generators, small input fixtures and explicit golden vectors belong in source;
generated reports, raw logs and measurements are transient run products.

**Where to go next.** Read the [implementation guide](../docs/implementation.md)
for source ownership, the [model guide](../Specs/README.md) for TLA+ contracts,
and the [core replay guide](../mbt/README.md) for model-generated observations.

**What remains unresolved.** Finite generated tests are not universal proofs.
Native helpers, external real captures and model-checker runtimes are prerequisites
of their named tests. Unavailable prerequisites remain unexercised; deleted old
reports cannot supply a passing result.

## Test matrix

| Contract | Executable check | Scope |
| --- | --- | --- |
| Core recovery, definitions, slicing and optimized completion | `python3 tools/run_generated_validation.py` | 3,200 configured generated core/graph/unwind cases plus current core TLA+ replay and compiled mutants. |
| Core-only dependencies and portable behavior | `cargo test --offline --locked --no-default-features` | Standard-library core and selected portable feature tests. |
| Default integrations and reports | `cargo test --offline --locked` | Default test selection; ignored native/capture tests require their declared inputs. |
| Validator rejection cases and fixture integrity | `python3 -m unittest discover -s tools -p 'test_*.py'` | Synthetic negative controls, live controlled-capture inspection, source/layout and test-output policy. |
| Typed stateflow and supplied IR replay | `python3 mbt/stage-e/run.py` | Generated model expectations, real Rust observations and compiled engine mutants. |
| Native fixed-input algorithms | `python3 tools/check_bap_core_replay.py --output target/native-replay` and `python3 tools/check_bap_core_mutations.py --output target/native-mutations` | Requires the pinned native helper/SDK and runtime; source/tool-bound fresh observations. |
| Scalar BIL equations | `python3 tools/check_bap_admission_oracle.py --output target/scalar-oracle.json` | Fresh helper lifting against independent arithmetic/flag equations; requires the BAP helper/runtime. |
| Loop fixture arithmetic and source compatibility | `python3 tests/bap/fixtures/loop-closure/extract.py --check` | Compact source inputs, signed table targets and region edges; no archived product output. |
| Active formal models | Named `Specs/check-*.sh` commands in the model guide | Declared finite configurations and independent oracles; run on an authorized qualification host. |
| Real captures and timing | Named native tests, capture observers and `tools/measure_*.py` | Explicit live inputs and declared budgets; never inferred from generated normalized graphs. |

Root formatting, all-feature/all-target Clippy, `tools/check_rust_layout.py` and
`tools/check_doc_links.py` remain required checks. Under CPU contention the default
suite's existing guard deadlines may require `RUST_TEST_THREADS=1`; thresholds
must not be relaxed to manufacture a pass.

## Fixtures and generated products

The Windows workload archive in `input/fixtures/workloads/` contains only three
test inputs: the controlled minidump, its matching PE and the producer witness.
It contains no logs, acceptance receipts, source snapshots or nested archives.
The independent inspector executes afresh when these inputs are materialized.
Other case definitions specify hashes, queries and expected facts, not prior
successful outcomes. The externally supplied scoped real capture remains an
explicit prerequisite; no substitute input receives credit for it.

The 666-entry vector in `reports/fixtures/i5c-legacy-sha256.json` defines expected
size/digest values for exact compatibility tests. It contains no old payloads,
paths or pass flags. Codec fixtures under `investigation/fixtures/saved_sources/`
are parsed as actual test inputs. Compiler-owned generated bindings, trace corpora
and type-admission inputs remain necessary inputs to model-based replay.

Run outputs belong under ignored `target/`, `mbt/.work/` or system temporary
directories. The generated runner offers no option to publish or archive them.
Historical dated documentation links into Git history only for context. Current
tests execute without the removed collection or its LFS objects. Git history and
already cached historical LFS objects are not rewritten or pruned by this migration.
