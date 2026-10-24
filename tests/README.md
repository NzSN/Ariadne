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
reports cannot supply a passing result. The [plain REP/accounting contract](../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting)
defines a finite v12 three-form dependency scope; full AMD64 legality and
concrete-form coverage remain open.

## Test matrix

| Contract | Executable check | Scope |
| --- | --- | --- |
| Core recovery, definitions, slicing and optimized completion | `python3 tools/run_generated_validation.py` | 3,200 configured generated core/graph/unwind cases plus current core TLA+ replay and compiled mutants. |
| Core-only dependencies and portable behavior | `cargo test --offline --locked --no-default-features` | Standard-library core and selected portable feature tests. |
| Default integrations and reports | `cargo test --offline --locked` | Default test selection; ignored native/capture tests require their declared inputs. |
| Validator rejection cases and fixture integrity | `python3 -m unittest discover -s tools -p 'test_*.py'` | Synthetic negative controls, live controlled-capture inspection, source/layout and test-output policy. |
| Typed stateflow and supplied IR replay | `python3 mbt/stage-e/run.py` | Generated model expectations, real Rust observations and compiled engine mutants. |
| Native fixed-input algorithms | `python3 tools/check_bap_core_replay.py --output target/native-replay` and `python3 tools/check_bap_core_mutations.py --output target/native-mutations` | Requires the pinned native helper/SDK and runtime; source/tool-bound fresh observations. |
| Finite memory-MOV8 native consumption | Run `python3 tools/check_amd64_mov8_memory_native.py --output target/memory-mov8-native-current` through the pinned read-only dependency wrapper | Seven exact named tests: 2,880 address-64 encodings across both targets, weak memory/byte origins, all 2,880 address-32 refusals across both targets, and the existing four register/native regressions. Synthetic minidumps and trusted reader-normalized effects; full AMD64 and real execution remain outside this gate. |
| Scalar BIL equations | `python3 tools/check_bap_admission_oracle.py --output target/scalar-oracle.json` | Fresh helper lifting against independent arithmetic/flag equations; requires the BAP helper/runtime. |
| AMD64 family survey and explicit flag producer | `python3 tools/probe_amd64_semantics.py --native --output target/new-semantics-survey`; `python3 -m unittest discover -s tests/bap -p 'test_*.py'` | Finite actual-byte inventory and strict accounting. The source-built flag extension has a separate build/opt-in contract; unknown rows do not count as full coverage. |
| Pinned instruction inventory | `python3 tools/amd64_inventory.py generate --output target/new-inventory`; `python3 tools/amd64_inventory.py check target/new-inventory/inventory.json` | Requires fetched pinned XED inputs. Complete extraction of its symbolic templates; AMD legality reconciliation remains separate. |
| AMD64 full-coverage obligations | `python3 tools/amd64_coverage.py --xed target/new-inventory/inventory.json --output target/new-accounting --require-full`; `python3 -m unittest discover -s tools -p 'test_amd64_coverage.py'` | Deterministic symbolic-form, manual-gap and exact-byte worklists. Add accepted `--manual` products and a current-source `--survey` explicitly. Pinned manual rows/gaps remain visible when products are omitted. Missing inputs, opaque/unexercised cases and absent authoritative bindings keep full support false; strict mode exits nonzero. |
| Historical AMD manual-gap recovery | Follow the [C2 source reconstruction contract](../docs/Ariadne/amd64-coverage-design.md#102-geometry-and-source-region-execution-c2); `python3 -m unittest discover -s tests/bap -p 'test_amd64_manual_geometry*.py'`; `python3 -m unittest discover -s tests/bap -p test_amd64_manual_inventory.py` | Fresh three-volume `extract`/`check` reconstructs every immutable old gap from pinned source products; five-volume `regions`/`check-regions` accounts for the wider source scope. Actual word-box fixtures exercise grouped cells, wrapped encodings, source conflicts and non-encoding material. A transcription disposition does not parse its semantic constraints or establish legal-form completeness. |
| Publisher source-entry migration review | Follow the [P1 review contract](../docs/Ariadne/amd64-coverage-design.md#1016-publisher-migration-entry-review); `PYTHONPATH=tools python3 -m unittest test_amd64_corpus_entry_review test_amd64_corpus_migration` | Fresh seven-PDF reconstruction and independent output replay map 110 entry records while preserving all 115 unresolved obligations. Prior-family links, complete raw section text/geometry and additional scope do not establish semantic equivalence or corpus adoption. |
| Selected conversion source constraints | Follow the [conversion review contract](../docs/Ariadne/amd64-coverage-design.md#1017-conversion-family-source-constraints); `PYTHONPATH=tools python3 -m unittest test_amd64_conversion_constraints` | Four base/X variants, 22 source claims, exact physical anchors and four retained conflict/scope boundaries. Query kernels check lane/memory shapes and 1,024 immediate/MXCSR selector cases; no numeric IEEE conversion, encoding legality or production admission. |
| Remaining paired-family source constraints | Follow the [paired-family contract](../docs/Ariadne/amd64-coverage-design.md#1018-remaining-paired-family-source-constraints); `PYTHONPATH=tools python3 -m unittest test_amd64_paired_constraints` | 24 selected clauses and 328 anchors across both exact Vol4 revisions for GF2 inverse affine, MOVD and scalar negative multiply-add. Seven conflict/unreviewed-scope boundaries and all 115 migration obligations remain; preceding conversion and seven-PDF reconstruction are required. No whole-section equivalence, numeric semantics or runtime admission. |
| P1 source adoption and migration dispositions | Follow the [P1 completion contract](../docs/Ariadne/amd64-coverage-design.md#1020-p1-source-selection-and-structural-migration-completed); `PYTHONPATH=tools python3 -m unittest test_amd64_source_adoption test_amd64_migration_dispositions` | Fresh exact publisher/source reconstruction, seven adjudications, 33 table decisions and all 368 Vol5 pages. Current P1 dispositions cover all 115 original IDs while retaining P2/P3 follow-ups. Strict adoption exits 0 only after the owning replay; the old whole-required-source placeholder is removed. |
| Extended cross-volume source rules | Follow the [P2 execution contract](../docs/Ariadne/amd64-coverage-design.md#1019-section-5-execution-and-current-exit-gates); `PYTHONPATH=tools python3 -m unittest test_amd64_extended_constraints` | Nine clauses/53 exact anchors, 1,792 signed byte/access-size cases and 458,752 signed-16 displacement choices. One derived source-rule disposition retains nine earlier reference scopes and all 516 original unparsed cells. No tuple decoder, instruction legality or production admission. |
| Final frame-path publication cap | Follow the [runtime repair](../docs/Ariadne/investigation-design.md#frame-path-final-output-budget-repair); `cargo test --offline --locked --features property-tests --lib frame_paths:: -- --test-threads=1` | Exact complete serialized-size enforcement across early/ordinary returns, a default boundary regression and retained shrunk property case. Native/capture and broad release qualification remain separate. |
| AMD source obligations and publisher adjudications | Follow the [resumed source-review contract](../docs/Ariadne/amd64-coverage-design.md#1010-resumed-source-review-and-validation); `PYTHONPATH=tools python3 -m unittest test_amd64_source_obligations test_amd64_source_authority` | Maintained source excerpts exercise stable identities, table ownership and bounded corrections. Optional authority integration freshly replays publisher PDFs; serialized passing reports cannot adjudicate a conflict. Full ledger extraction/check also requires the exact pinned extraction runtime and complete source products. |
| Finite MOV8 domain and bindings | `PYTHONPATH=tools python3 -m unittest test_amd64_source_constraints test_amd64_domains test_amd64_reconciliation test_amd64_domain_bindings`; follow the [resumed binding boundary](../docs/Ariadne/amd64-coverage-design.md#1010-resumed-source-review-and-validation) | The 640-point register-byte pilot exercises typed constraints, partial XED reconciliation and strict producer framing. Fresh source/BAP/LLVM/numeric/Rust observations are separate prerequisites; stale bindings and mismatched native tools remain rejected. A partial relation never increments complete candidate bindings. |
| Publisher-corpus migration and architectural constraints | `PYTHONPATH=tools python3 -m unittest test_amd64_corpus_migration test_amd64_source_constraints test_amd64_source_obligations`; follow the [stopped continuation](../docs/Ariadne/amd64-coverage-design.md#1013-constraint-and-mov8-continuation-stopped-for-publication) | Fresh seven-PDF comparison, preserved historical IDs, 24 typed clauses and explicit unresolved references/cells. Candidate comparison never grants corpus adoption or complete parsing. |
| Dependent memory-MOV8 domains | `PYTHONPATH=tools python3 -m unittest test_amd64_memory_domains test_amd64_memory_bindings test_amd64_reconciliation`; `python3 tools/amd64_domain_bindings.py --help` | The binding CLI dispatches schema v5 to the memory checker: 5,760 selected ModRM/SIB/displacement points, with address-64 support and address-32 refusal separate. Actual source/BAP/LLVM/Rust campaigns are required. The [mapping continuation](../docs/Ariadne/amd64-coverage-design.md#1014-per-form-source-rule-mapping-resumed) completes the five-rule adjustment and affected refresh. |
| Register-MOV8 native consumer | Run `python3 tools/check_amd64_mov8_native.py --output target/new-mov8-native` through the verified `tools/with_mirrorrust_snapshot.py run` wrapper; `PYTHONPATH=tools python3 -m unittest test_amd64_mov8_native` | Requires qualified BAP/LLVM/native-core artifacts. Four exact named release tests check 1,280 instruction-target instances, independent origins, structural refusals and address-32 stop barriers. Fresh execution is required; memory forms and independent native ISA/re-decoding are separate. |
| Advanced source producer | Build and run the [advanced integration commands](../docs/Ariadne/bap-analysis-core-design.md#pinned-form-inventory-and-advanced-producer); `python3 tools/check_bap_bit_count_oracle.py --output target/new-bit-count/report.json` | Explicit v10/v11 selection; actual BAP sequences, native/reference equality, saved-proof controls and independent numeric equations. |
| Plain repeated-string dependencies | Follow the [v12 setup and commands](../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting); `cargo test --offline --locked --lib repeated_string`; `python3 tools/check_bap_repeated_string_oracle.py --output target/new-rep-oracle/report.json` | Exact F3 A4/AA/A6 projection and loop-aware consumers; ignored native tests require pinned advanced producer/current native helper. Nine proof transports/direct entry points refuse the exact v12 token from overall semantic identity or site projection, including empty/all-null sites. Native capture trusts validated reader-supplied normalized effects bound to byte/profile/query evidence; it does not independently replay raw REP BIL. Numeric equations do not qualify hardware partial faults or general REP. |
| Memory REP successors | Follow the [v13/v14 recipe and source-bundle contract](../docs/Ariadne/amd64-coverage-design.md#104-default-address-memory-rep-execution-r1); `cargo test --offline --locked --lib lods_source`; `python3 tools/check_bap_repeated_string_oracle.py --recipes tests/bap/fixtures/repeated-string/memory-recipes-v2.json --output target/new-memory-rep/report.json`; `python3 -m unittest discover -s tests/bap -p 'test_lods_source.py'` | v13 selects 24 original nonempty default-address forms; v14 adds four actual BAP source LODS lifts under its own lock. Ignored materialization/native matrices exercise 192/224 tuple instances; LODS source tests require its selected pinned bundle. Proof transports remain refused for v12/v13/v14; numeric normal completion does not qualify partial faults or address overrides. |
| AMD address-size REP and bindings | Follow the [v15 contract](../docs/Ariadne/amd64-coverage-design.md#107-amd-address-size-rep-implementation-r2) and [56-point registry](../docs/Ariadne/amd64-coverage-design.md#108-expanded-source-to-consumer-bindings-c3c4); `cargo test --offline --locked --lib rep_address_source`; `python3 -m unittest discover -s tests/bap -p 'test_rep_address_*.py'`; `python3 -m unittest discover -s tools -p 'test_amd64_legal_forms.py'` | Explicit AMD zero-count premise; 56 canonical tuples with a 32-case replacement producer. Ignored local/native v15 matrices each cover 448 instances; new native helper/refusal gates are required separately. Source-cell/producer/Rust bindings prove only this finite domain, not the full 10,569 symbolic domains. Optional hardware C probes retain their CPU-specific scope. |
| Conventional Windows unwind operations | `cargo test --offline --locked --test input_frame_paths`; `python3 tools/check_amd64_unwind_windows.py --cases target/new-unwind-inputs --output target/new-unwind-reference` | Independent synthetic metadata/stack controls and fresh Windows RtlVirtualUnwind comparisons. Export inputs using the ignored test documented in the investigation design. Windows v3/APX remains separate. |
| Loop fixture arithmetic and source compatibility | `python3 tests/bap/fixtures/loop-closure/extract.py --check` | Compact source inputs, signed table targets and region edges; no archived product output. |
| Active formal models | Named `Specs/check-*.sh` commands in the model guide | Declared finite configurations and independent oracles; run on an authorized qualification host. |
| Real captures and timing | Named native tests, capture observers and `tools/measure_*.py` | Explicit live inputs and declared budgets; never inferred from generated normalized graphs. |

Root formatting, all-feature/all-target Clippy, `tools/check_rust_layout.py` and
`tools/check_doc_links.py` remain required checks. Under CPU contention the default
suite's existing guard deadlines may require `RUST_TEST_THREADS=1`; thresholds
must not be relaxed to manufacture a pass.

The [2026-10-23 plain REP stage](../.agents/plans/amd64-operation-coverage.md#resume-plain-rep-and-coverage-accounting)
records completed finite projection/consumer, final-helper integration and proof
refusal checks. Its four Rust mutants use unchanged Rust SUT/observers from
before final native policy hardening; the final native policy has separate
compiled/dispatch controls and current-helper integration checks. These finite
results do not close general REP or full AMD64 coverage.

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
