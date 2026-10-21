# Fix the nine table-jump blockers in guarded frame preparation

## Context and follow-up

**Status.** Complete within the explicit target/guard integration and target-coverage scope, 2026-10-15. The [loop follow-up](loop-aware-target-resolution.md) closes the ninth C5 incoming-coverage clause in probe `dump-20261015T051409`; all nine original tables and both frame queries pass their declared coverage/parity gates. The 2026-10-14 partial result remains historical evidence. Full frame-path enumeration, MOVAPS admission and the remaining semantic barriers are separate, unmet gates.

**2026-10-15 follow-up.** The [loop extension](loop-aware-target-resolution.md) passes L0–L6 on corrected snapshot `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee`. Initial attempt `dump-20261015T050210` failed caller publication while callee parity passed; its correction, regression and fresh qualification pass. Probe `dump-20261015T051409` accepts both complete loop receipts and both Rust/native frame results. Parent C5/C6 acceptance is closed for this stated scope, with the earlier failure retained separately.

**Why this document exists.** The [captured table inspection](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/README.md) proves that the nine dispatch tables are available, while the baseline mutually exclusive preparation extensions left their target sets empty. The [test matrix](../../../tests/README.md) defines current validation.

**What this document establishes.** Fine-grained stages, file ownership, dependencies, safety/acceptance gates and remote qualification for the [canonical composition design](../../../docs/Ariadne/guarded-target-resolution-design.md).

**Where to go next.** Read the [accepted 2026-10-15 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md), [loop-closure ledger](loop-aware-target-resolution.md) and [canonical design](../../../docs/Ariadne/guarded-target-resolution-design.md) for current outcomes and limits. The [2026-10-14 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/20261014/README.md), [existing resolver ledger](../indirect-target-resolution.md), [original guard delivery](justified-branch-pruning.md) and [request-budget delivery](native-request-budget.md) retain their original scope.

**What remains unresolved.** This plan fixes target/guard integration for the nine jumps. The other 19 recorded semantic stops and any newly discovered barriers remain explicit. Their resolution, regional coverage and successful full-dump path enumeration are separate gates; no alignment or positive-path guarantee is made here.

Current validation follows the [executable test matrix](../../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Concrete objective

Let guarded frame preparation derive checked target candidates from captured relative-32 tables, discover their destinations and recompute coverage on one final candidate graph. Reuse the existing BAP target resolver; do not implement address-specific exceptions, scan for executable-looking heap pointers or seed targets as roots.

Known independent witness: dump SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, frame pair 1:0, caller entry `0x00007ff7744033a0`. Nine `.rdata` tables contain 370 entries / 1,480 bytes, yielding 64 candidate destinations, 51 absent from the existing graph.

## Baseline seams and implemented correction

| Seam | Baseline behavior | Delivered correction; scoped qualification |
| --- | --- | --- |
| Preparation selection | `PreparationExtension` chooses target resolution or guard admission. | One explicit combined configuration retains both evidence families. |
| Pending MOVAPS | Effect-free candidate continuation supplies no ordinary target transfer. | Exact reviewed normal-continuation scalar identity, independent of alignment proof and without committing a store. |
| Original versus resolved control | Resolver changes prepared instruction targets; retained guard source control is separate. | Preserve original facts and record receipt-backed augmentation; derive effective candidate control explicitly. |
| Replay graph | Target validation uses final normalized control; unknown MOVAPS can remove a candidate continuation. | Replay on a sealed candidate graph, then validate final transformations and effects separately. |
| Closure identity | Guard epoch is constant; target coordinator detects mainly inserted targets. | Advance a shared epoch on every proof-relevant change; invalidate both receipt families. |
| Native/report admission | Existing adapters reject paired reports or compare unaugmented control with final control. | Strict versioned combined profile, candidate/final graph binding, paired validators and codecs. |
| Budgets | Resolver retained default-based ceilings; BAP aggregate query capacity was implicitly 8,192; frame binding has independent aggregate bounds. | Caller-selected finite target budgets; BAP aggregate bound follows `PrepareLimits.max_starts` through bounded child-session rotation. Shared guard epoch, frame/transport/output limits remain separate. |

## Implementation handoff

The public frame entry point is `prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(chain, index, entry, setup, guard_limits, target_limits)`. The [canonical usage section](../../../docs/Ariadne/guarded-target-resolution-design.md#api-and-cli-usage) records the required paired CLI flags, exact schemas, premises and separate limit files/request budget.

The 2026-10-14 combined delivery emits v2 local receipts (`captured-local-indirect-targets/v1`). An explicitly bounded frontier treats incoming architectural register values as arbitrary and is never a new root. Every nonterminal reverse-path prefix must cover all candidate predecessors; a bounded path alone cannot justify completeness. This permits local table proofs without following unrelated earlier paths to entry, while unsupported/unbounded alternatives and budget exhaustion remain explicit.

That delivery seals the candidate graph, original controls, target report, guard report and final request into `ariadne.guarded-target-resolution/v1`, transported under `captured-guarded-targets/v1`. Combined minidump/explanation/frame outputs are versioned separately and retain full proofs/request/source evidence. Conservative budget-stopped queries may be published only when their surviving witnesses and represented candidate domain pass replay and transformation validation; normal guard effects remain uncommitted without alignment proof. Earlier capture/discovery/evidence failures can still reject preparation.

The 2026-10-15 loop implementation uses local target report v3/profile `captured-local-indirect-targets/v2`, composition v2 and combined native profile `captured-guarded-targets/v2`; its combined minidump/explanation/frame reports are v5/v4/v4. A tagged whole-dispatch induction proof is an alternative to the unchanged prefix-tree coverage rule. Retained v1 combined reports select the frozen legacy checker/model and have passed actual semantic replay; new loop fields cannot be admitted through a legacy profile or stripped during downgrade. This coverage-only extension over retained table witnesses passes the publication regression and original-dump target-closure acceptance.

The controls include paired codec roundtrips, proof stripping, identity/premise/epoch/source tampering, an explicit unavailable endpoint and pinned-helper synthetic composition cases. Final validation `120753` passes source/model/native checks within the scope recorded in the [delivery evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/20261014/README.md). Order-independent native term comparison, twelve native infeasible controls and all 273 actual infeasible receipts pass; historical failed controls remain separately identified.

## C5 original-dump probe checkpoint

The following probe counts, source identities and gate table describe the retained **2026-10-14** result. The 2026-10-15 follow-up below records new checks without rewriting that history.

The first combined caller attempt exceeded 8,192 starts and failed the backend's hidden aggregate query cap even though `PrepareLimits.max_starts` was 16,384. The source correction selects that explicit finite aggregate bound and rotates child sessions within their unchanged 8,192-site protocol capacity. Snapshot/target/producer identities and aggregate proof maps remain fixed across children. Direct backend construction retains its existing 8,192 default; final records must include the 8,193-site boundary control.

An earlier callee preparation reached shared candidate epoch 129, exceeding guard `max_closure_rounds=64`. Final probe `121127` explicitly selected 32,768 and reached caller epoch 610 and callee epoch 129. This budget measures proof-relevant graph epochs, including changes that add no destination; it is independent of resolver pass count.

The second probe's native-finish threshold is 4,096 decoded sites, applied after Rust completes to decide whether to attempt native completion. It does not replace the native one-million-action/eight-MiB-response/paged-completion contracts. A larger finite guard transfer-evaluation allowance and 120,000-ms elapsed allowance are explicit probe settings, not changed global defaults; preserve their actual JSON controls with the result.

Final probe `121127` represented 9,590 caller sites and 778 callee sites. Every original candidate set matches the independent witness exactly (370 entries, 64 destinations), and every one of the 51 originally absent starts was attempted. Eight original dispatches are complete. Original `40da09` and new `40dadd` each retain four known destinations but remain incomplete with `cyclic-incoming-state` after an advancing-RCX loop was exposed. This meets candidate/discovery reconciliation and leaves the ninth completeness gate open.

The caller retains 32 guard-coverage barriers and its initial MOVAPS is unknown with `candidate-coverage-incomplete`. Rust and native completed both queries with `request_equal=true` and `full_state_equal=true`: caller nine decoded/nine edges/1,269 reported definitions; callee 768 decoded/895 edges/1,289,259 reported definitions. Frame listing `1:0`, `NP=10` is unavailable with zero paths and `missing-or-ambiguous-active-call-anchor`; no alignment, executed-path or positive-listing claim is made.

Native structural term comparison now ignores object field order while retaining field names, scalar values and list order. The earlier order-sensitive failure/probe `115408` remains historical; final positive probe `121127` elapsed 192,204 ms with native checker identity `cc9ff8718659af45e3d86ba0949915615f8bdb64822638597522af63dba0c0f8`. The [delivery record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/20261014/README.md) retains final parity and finite qualification; its artifact archive is sealed.

The [canonical source-review corrections](../../../docs/Ariadne/guarded-target-resolution-design.md#source-review-corrections) also record conditional-write pre-state handling, captured-read structure checks, raw source/control totality, combined transport/paged completion, saved minidump source identity and exact offline frame recovery projection. Final qualification must use the corrected sources rather than earlier snapshots.

Finite byte/word-load domains, one bounded stable-cycle unfolding and local infeasible receipts now have independent controls. Correlation is prohibited by original memory writes (including pending-store BIL), opaque calls, unknown memory or address-input writes; guard predicates are checked exactly rather than through convex bounds alone. Reported formal checks cover 19 finite models, and the independent oracle includes ten infeasible-context cases.

| Gate | Retained 2026-10-14 result |
| --- | --- |
| C0–C4 implementation | Complete: model/cases, preparation, proof/transport and consumers. |
| C5 source/model/finite cases | Passed final scoped validation `120753`, 19 finite models, oracle controls, twelve native infeasible controls and 273 actual infeasible receipts. |
| C5 original candidate/discovery reconciliation | Met for all nine sets and all 51 previously absent starts. |
| C5 complete incoming coverage | Open for original `40da09`; new `40dadd` also remains incomplete. |
| C5 final native receipt/parity | Passed: both final requests and full states equal in probe `121127`. |
| C6 full delivery scope | Ninth completeness clause remains open; keep plan active until scope is accepted or the linked L0–L6 follow-up is implemented and checked. Final scoped records are sealed. |

## Loop-closure follow-up checkpoint, 2026-10-15

The [stable-base invariant](../../../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up) is implemented within the coverage-only scope of the [L0–L6 successor plan](loop-aware-target-resolution.md). It proves both captured nine-node phase fixtures while allowing RCX and successive selector values to change. The implementation still requires existing ordinary path/table entry witnesses; it does not scan the heap, introduce roots or independently synthesize a new table candidate set.

Validation `validation-20261015T045622` passed on source archive `39e902c8a34c7fd6efa4e948788d9a611f07014ceea33c5e4b4aac56c6d7d31d` (877 files): applicable root/native/report gates, seven focused Rust loop tests, 49 finite model configurations (five target, 19 composition, 25 loop), 29 independent loop cases plus four arithmetic controls, 41 native controls including three positives, and eight of eight behaviorally credited source mutations. Fresh core/stateflow replay dispatched 168 + 162 observations; both wrong-digest controls rejected before dispatch. Actual retained combined minidump/frame reports passed semantic replay under their frozen versioned contract.

The formal integration is the [checked component-premise interface](../../../Specs/README.md#loop-target-closure-component-interface): accepted whole-dispatch coverage discharges the modeled target obligation, while all other required sites remain in the coordinator's coverage conjunction. There is no claimed TLA+ `INSTANCE`, refinement theorem or mechanically checked coupling between the component models. Finite checking, source review and executable replay remain separate evidence tiers.

Original-dump attempt `dump-20261015T050210` failed caller preparation with `loop coverage graph changed before publication`; its callee parity passed. The corrected coordinator represents every referenced endpoint as a default `Stop` before producing resolver proofs, including nonfollowed call destinations and unattempted seeds. It adds no roots or forced discovery, and retains the publication graph check. The separate endpoint-publication regression passes.

Corrected snapshot `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee` (877 files) passes validation `validation-20261015T050857`, including seven loop tests, the publication regression and the same native/model/mutation gates. Fresh replay `generated-replay-20261015T050942Z` passes 330 observations with zero dispatches in both wrong-digest controls. Both source-bound passing campaigns and the failed original attempt are retained. Heavy execution is remote WSL; local follow-up is static documentation checking.

Probe `dump-20261015T051409` passed every target-closure acceptance gate in 202,410 ms: all nine original dispatches are complete, all 370 table entries/64 destinations reconcile, and all 51 formerly missing starts were attempted. DA09 and DADD each retain four targets with independently accepted loop receipts. Native accepts both frame queries; complete normalized requests and full states equal Rust for frame 1 and frame 0.

The caller has 9,590 candidate sites at epoch 609 and all 10 indirect sites complete, with 30 remaining guard barriers; completed core remains nine decoded sites, nine edges and 1,269 definitions. The callee has 778 candidates at epoch 129, 12 guard barriers, 768 decoded sites, 895 edges and 1,289,259 definitions. Initial caller MOVAPS remains unknown. NP10 frame listing is unavailable with zero returned paths and `missing-or-ambiguous-active-call-anchor`; this does not establish that no path exists.

The ninth C5 clause and the scoped C6 delivery are complete. Their acceptance covers target/guard integration and these dispatch proofs, not removal of every semantic barrier, universal loop handling or available frame paths. The [new qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) records exact source/tool/dump identities and remaining limits.

## Staged tasks, ownership and gates

Workers must preserve unrelated changes. Each owner edits only its assigned files; cross-owner interfaces are frozen in C0 before parallel implementation.

| Task | Owner / principal files | Depends on | Reviewable exit |
| --- | --- | --- | --- |
| C0.1 freeze graph/proof contract | Coordinator/design owner: canonical design; `Specs/AriadneTargetResolution.tla`, `Specs/AriadnePredicateAdmission.tla` and relevant configs/checkers | Inspection | Original, candidate and final domains; pending-continuation rules; epoch and noncyclic digest scheme specified before runtime edits. |
| C0.2 freeze independent cases | Oracle/test owner: `tests/bap/fixtures/`, captured witness references | C0.1 | Expected sets/bounds, incoming bypass/backedge, uncertainty and stale-proof cases fixed independently of implementation. |
| C0.3 size budgets | Coordinator: existing guard/target/discovery/frame/request contracts | C0.1 | Separate budget table and declared original-dump configuration. Resolver report/path/work and 8,192-node/32,768-edge frame-binding limits assessed. Any necessary release is explicitly scoped and paired. |
| C1.1 composable preparation API | Preparation owner: `src/input/materialize.rs`, `src/input/frame_paths.rs`, `src/input/mod.rs` | C0 | Explicit combined extension/options and frame activation binding; unchanged roots/seeds and capture-only reads. |
| C1.2 pending transfer extraction | Semantic owner: `src/bap/prepare.rs`, `target_resolution.rs`, `guard_admission.rs` | C0 | Original reviewed MOVAPS supplies only justified scalar flow on its candidate normal edge. Generic exceptions/calls/unknown writes remain conservative. |
| C1.3 control/evidence layering | Preparation + semantic owners | C1.1/C1.2 | Original decoded/BIL control retained; resolver augmentation and effective candidate control distinct and witness-bound. |
| C2.1 joint worklists | Preparation owner: materialization coordinator | C1 | Resolve → queue local targets → capture/lift → repeat; known candidates survive conservative downgrades and missing-code endpoints remain represented. |
| C2.2 epoch/invalidation | Preparation + semantic owners | C2.1 | New edges and completeness/barrier/transfer changes advance the epoch and invalidate stale proofs. Roots, seeds, snapshot, activation and premise policy stay immutable; scope changes require a new intent, premise revalidation and rejection of old receipts. No self-justifying proof cycle. |
| C2.3 seal and finalize | Preparation + validator owners | C2.2 | Stable candidate graph sealed; target replay and guard checking performed there; final request validated as an authorized transformation. Unknown/refuted/budget guards keep stops. |
| C3.1 combined Rust profile | Validation owner: `src/bap/core_adapter.rs`, `core_protocol.rs`, `core_session.rs`, input validators | C2 contract | New capability/version and strict paired envelope; legacy modes preserved; incompatible helpers fail explicitly. |
| C3.2 independent native replay | Native owner: `native/bap-core/capture.ml`, `guard.ml`, `main.ml`, `build.py` | C3.1 contract | Capture/source, table arithmetic, augmented control, both proofs and final request checked independently. Missing/forged/stale/cross-query evidence rejected. |
| C4.1 frame CLI/API | Product owner: `src/bin/ariadne-minidump.rs`, frame preparation | C3 | Frame mode accepts resolver opt-in with normal-call assumption, carries exact independent budgets and declares both memory/ABI premises. |
| C4.2 codecs and consumers | Product/validation owners: `src/input/report.rs`, `investigation.rs`, investigation `model.rs`, `validate.rs`, `frame_paths.rs`, `src/reports/` | C3 | Minidump, explanation and frame-path text/JSON/DOT retain both scopes/proofs/gaps; versioned strict round-trip/tamper validation. |
| C5.1 finite model/runtime parity | Test/native owners, task-private remote WSL builds | C1–C4 | Applicable TLA typecheck/safety/termination and replay; exact Rust/native combined fixtures; target-only/guard-only/default regressions. |
| C5.2 targeted mutations | Test owner: isolated SUT/build directories under `target/` | C5.1 controls | Every credited mutant has a passing original control and a named behavioral failure; no compile-error/timeout credit. |
| C5.3 original dump retry | Qualification owner: `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/` | C5.1/C5.2 | Nine site-by-site candidate/completeness outcomes, table-oracle reconciliation, discovery accounting for 51 new starts, remaining/new barriers and native/Rust parity recorded. |
| C6 final review and delivery | Coordinator + independent reviewers | C5 | Exact source/tool/dump hashes, finite scope, unmet gates and usage reconciled in canonical docs; links/layout pass; completed plan archived after actual delivery. |

## Required negative and mutation controls

| Control | Required result |
| --- | --- |
| Wrong sign extension/base/scale or omitted table target | Independent numeric/receipt check rejects or exposes the mismatch. |
| Guard/index-range bypass, new predecessor or late backedge | Previous target completeness and guard receipt invalidated. |
| Opaque register clobber, unsupported transfer, partial/conflicting table bytes | Unknown alternatives/residuals retained; no complete certificate. |
| Readable table with missing destination code | Known target preserved as an unavailable endpoint. |
| Remove either proof or `FrozenCapturedControlData`/normal-call premise | Combined admission/codec rejects the alteration. |
| Swap activation, snapshot, roots, graph epoch or final request | Exact identity binding rejects reuse. |
| Completeness-only/barrier-only change without a new edge | Shared epoch advances; stale publication rejected. |
| Pending candidate normal path reused as final MOVAPS effects | Rejected unless a fresh alignment receipt justifies normal selection. |
| Exhausted resolver/guard/discovery/output/transport budget | Explicit partial stop or rejection under the owning contract; no false completeness. |

## Original-dump acceptance

Produce one row for each original jump: `40361f`, `403fd7`, `40417a`, `404384`, `4048c5`, `408ab0`, `409837`, `4099bf`, `40da09` under module-prefixed VAs. Compare with the preserved table witness, including signed offsets, index bounds and read contributors. Reconcile the 64 candidates: any narrowed set needs a checked index-exclusion rationale. Attempt all 51 previously absent starts unless exclusion is certified; classify every resulting gap and newly exposed dispatch.

Require `complete=true` only with validated final incoming-state coverage under the declared captured-memory premise. A table match or successful native initialization alone is insufficient. If the existing resolver lacks precision or exceeds its explicit bounds, record that as a named unmet gate and scoped follow-up; do not hand-inject the witness addresses into production to pass the test.

The acceptance goal is checked recovery/integration for these dispatches and honest remaining coverage. Preserve the other 19 original semantic stops. The current global guard policy may continue to widen residues to TOP and leave the initial MOVAPS unknown. Full core/path execution and a positive path list require their own satisfied prerequisites and recorded result.

## Execution constraints

All Cargo, native SDK/helper, model, replay and mutation builds run on **remote `windows-dev` WSL** through `r_windev`. The current computer performs only read-only source inspection and static document/layout checks. Keep campaigns in separate task-owned build directories and preserve older evidence identities.

Run affected tests and applicable root checks: format, offline/locked default tests, core-only tests and all-feature/all-target Clippy. Native/report changes additionally exercise ignored pinned-helper suites, combined capture/frame/codec cases, model/replay and targeted mutations. Verify record hashes after final source changes; historical qualification is not refreshed by linking it.

Implementation was authorized after plan review. No commit, push or deployment is included in this delivery scope. The recorded C5/C6 gates are satisfied within the explicit target-coverage scope; completed-plan archival must preserve the remaining frame-path and semantic limits.
