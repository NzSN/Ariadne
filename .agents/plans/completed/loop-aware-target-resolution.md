# Loop-aware extension of the existing target resolver

## Context and follow-up

**Status.** L0–L6 complete within the explicit coverage-only scope, 2026-10-15. Corrected snapshot `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee` passes validation `validation-20261015T050857`, fresh replay and original-dump probe `dump-20261015T051409`. Both cyclic dispatches have accepted complete certificates; the parent ninth C5 clause is closed. Full frame-path availability remains a separate, unmet gate.

**Why this document exists.** The [canonical composition design](../../../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up) owns this extension's contracts. This plan closes the ninth incoming-coverage clause retained by the [C0–C6 parent plan](guarded-target-resolution.md) after its initial candidate recovery.

**What this document establishes.** The support boundary, reviewable implementation stages, file ownership, dependencies and remote acceptance gates for closing the DA09/DADD cyclic dispatch certificates.

**Where to go next.** Read the [2026-10-15 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md), canonical design and dated execution ledger for the accepted scope and remaining barriers. The [2026-10-14 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/20261014/README.md) remains the unchanged baseline; the [formal component interface](../../../Specs/README.md#loop-target-closure-component-interface) separates checked premises from an unproved inter-model refinement.

**What remains unresolved.** The delivered strategy proves coverage for tables already supported by retained ordinary path/entry witnesses; it does not independently generate new table candidates. The final probe retains 30 caller and 12 callee guard barriers, unknown initial MOVAPS and a missing-or-ambiguous active call anchor. Frame paths remain unavailable. Larger SCCs, arbitrary prefix-summary reuse and general loop synthesis remain outside this scope.

Current validation follows the [executable test matrix](../../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Objective and design decision

Extend the current resolver with a private loop-closure proof module. Reuse `relative32` evaluation and one materialization coordinator. For a small local dispatch region, prove a stable table base, permit changing RCX and fresh selector loads, and establish the selector domain before each indexed table load. Produce a whole-dispatch induction receipt checked independently by Rust and native admission.

The implementation preserves unknown controls, entry roots and the distinction between captured observations and earlier states. Its first scope discharges whole-dispatch coverage using retained table evidence; unsupported proposals preserve candidates and explicit residuals. Finite validation and the separate original-dump result below qualify that scope without establishing executed history or a complete frame path.

## Baseline and concrete dump acceptance

| Baseline item | Retained value |
| --- | --- |
| Dump | `dump_03958DA4FCA844A786262A1053` |
| Dump SHA-256 | `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab` |
| Query | Thread 23668, frame pair 1 → 0, NP10 |
| Caller candidate epoch / sites | 610 / 9,590 |
| Candidate identity | `composition.candidate_sha256=50b54d681fe01f9488da4cf2c90948afe52cb2ab13dad2e960bad55648122a3f` |
| Target status | Eight original complete certificates; DA09 and DADD each have four known targets and `cyclic-incoming-state` |
| Discovery | Nine original table sets reconciled; 64 destinations, all 51 formerly missing starts attempted |
| Final result | Rust/native requests and full states match; caller MOVAPS unknown; frame listing unavailable |

The maximal SCCs contain 4,694 and 411 nodes and many base clobbers/calls. Initial support must instead discover and verify the following local regions. Instruction offsets below share the explicit semantic VA prefix `0x00007ff77440`:

```text
DA09 region: d9eb d9ee d9f1 d9f7 d9fc da00 da02 da06 da09
DADD region: dabf dac2 dac5 dacb dad0 dad4 dad6 dada dadd

Entrance / base-reset corridor:
  d9e2 LEA RDX,base → d9e9 JMP → d9f7
  dab6 LEA RDX,base → dabd JMP → dacb

Each local region: 9 nodes; 10 internal edges; 1 entrance; 4 exits.
```

These are fixture expectations, never address-specific production rules. L0 extracted their source-bound instruction/BIL/read facts under `tests/bap/fixtures/loop-closure/`, and qualified tests independently accept both local induction receipts. Probe `dump-20261015T051409` also accepts both receipts on the final full candidate graph. The canonical design records their complete obligations; rejected reverse contexts were not fully recorded by the old implementation.

## Implementation architecture

```text
Existing local resolver and coordinator
  → existing path/frontier/infeasible rules
  → private loop-region discovery and assertion proposal
  → independent loop-receipt validation
  → existing captured table evaluation / candidate union
  → discovery and epoch revalidation
  → paired native admission and reports
```

Keep ordinary path receipts unchanged. The new v3 local report uses a tagged coverage choice: existing prefix-tree coverage or a whole-dispatch inductive receipt. An inductive receipt checks every entrance and internal edge, derives all table successors without trusting current target-completeness flags, and preserves every exit. It is not a stable-load infeasibility receipt or an arbitrary-register frontier.

The private module returns `NotApplicable`, `Candidate(receipt)` or `Partial(reason)`. The delivered strategy is coverage-only: it reuses the existing resolver's path/table entry witnesses and captured reads. A missing witness or unsupported table keeps the result partial. A candidate cannot set `complete=true` until the validator accepts all required obligations on the current graph; candidate completeness changes then advance the shared epoch and require fresh validation before final sealing. New discoveries invalidate region/boundary proofs. One context's first successful witness cannot erase other incoming alternatives.

## Stages, ownership and dependencies

Owners describe independent responsibilities for execution, not changes made by this plan. Workers are not alone in the checkout: preserve unrelated changes, edit only assigned files and coordinate shared interfaces before implementation. L0 freezes the interface and receipt contract before L2/L3 proceed in parallel. Review gates are evidence gates, not additional user-confirmation steps.

| Stage / owner | Principal files and tasks | Depends on | Reviewable exit |
| --- | --- | --- | --- |
| **L0 — Contract and baseline owner** | Update canonical design; preserve this plan; extract source-bound loop fixtures into `tests/bap/fixtures/loop-closure/`; record graph policy, regions, entrances, LEA corridors, original BIL/bytes, tables and baseline hashes. Freeze new coverage tag, full wire fields, private interface, version-indexed legacy validation contract and finite work units. | Source inspection | Independent reproduction of both local regions and all entrances; frozen legacy source/model identities; explicit rejection of the maximal-SCC invariant; no production address constants or expected-target injection. |
| **L1 — Formal model and oracle owner** | Add `Specs/AriadneLoopTargetClosure.tla`, finite configs and checker; document its checked coverage-premise interface to `AriadneTargetResolution.tla` and composition authority. Add an independent finite oracle under the fixture directory. | L0 | Initialization, preservation, domain implication, every entrance/edge/exit, stale-epoch invalidation, conservative partial publication and bounded analyzer termination are modeled. Positive and deliberate counterexample configurations behave as specified. No TLA+ `INSTANCE`, refinement mapping or machine-checked inter-model coupling is claimed. |
| **L2 — Rust resolver owner** | `src/bap/target_resolution.rs`; private implementation under `src/bap/target_resolution/`; strict receipt types; `tests/bap/target_resolution_unit.rs`; `src/bin/target_resolution_validate.rs` as necessary. Add bounded region discovery, point assertions and independent replay from original BIL. | L1 contract/model cases | Both synthetic loop shapes yield accepted whole-dispatch evidence. Replay rejects bad entrances, clobbers, wrong guard provenance and tampered boundaries. Existing target/frontier/infeasible/cycle tests retain their stated behavior. |
| **L3 — Native admission owner** | `native/bap-core/capture.ml`, `composition.ml`, `main.ml`, `build.py`; relevant `src/bap/core_adapter.rs`, `core_protocol.rs`, `core_session.rs` interfaces coordinated with L2. Add independent assertion/edge/read replay, new capability/profile handling and version-indexed legacy/new ruleset/model identities. | L1 and frozen L2 wire contract | Native accepts the same valid proof cases and rejects named invalid ones. Old helpers explicitly reject the new profile. Legacy proof replay retains its frozen contract separately from the new helper build identity. JSON field order cannot change symbolic equality. Exact read contributors and original BIL remain mandatory. |
| **L4 — Integration and reports owner** | `src/input/materialize.rs`; `src/bap/composition.rs`; input frame/report/investigation codecs, `src/reports/`, CLI and consumer tests. Integrate proof invalidation, target union, completeness-only epoch changes, dedicated v1 replay, saved old/new versions and JSON/text/DOT explanations. | L2 + L3 | One coordinator and immutable query scope; new targets queued without roots; summaries rechecked after epoch changes; no proof stripping or unsupported fallback. Validate actual retained 2026-10-14 combined minidump/frame reports without rewriting their model/checker identities; old/new roundtrips preserve full requests and gaps. |
| **L5 — Qualification owner** | Loop oracle/tests, targeted mutation tooling, isolated native SDK/helper/replay outputs, model logs and a new source/tool manifest under `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/`. | L4 | Applicable root checks, model/oracle controls, native admission, saved-report controls, behavioral mutations and generated replay pass on the same source snapshot. Missing prerequisites remain unexercised rather than passed. |
| **L6 — Original-dump and delivery owner** | Byte-identical dump retry, all-nine table reconciliation, DA09/DADD proof comparison, native/Rust full-state parity, remaining-barrier report; update canonical dated validation and parent C5 status. | L5 | Both dispatches complete with the expected four-target sets and validated induction receipts; eight previously complete certificates retain valid coverage; all original candidates remain. Separate frame-path result and remaining barriers are reported honestly. |

## Dated execution ledger, 2026-10-15

Initial validation `validation-20261015T045622` passed on archive `39e902c8a34c7fd6efa4e948788d9a611f07014ceea33c5e4b4aac56c6d7d31d` (877 files), then dump attempt `dump-20261015T050210` exposed the publication defect below. The corrected archive is `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee` (877 files): validation `validation-20261015T050857` and replay `generated-replay-20261015T050942Z` pass. Subsequent documentation/evidence reconciliation does not silently refresh these runtime source bindings. Raw attempts are being sealed under `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/`; the 2026-10-14 records retain their original bytes and scope.

| Stage | Recorded result and acceptance boundary |
| --- | --- |
| L0 | Delivered: both nine-node phase fixtures, exact entrances/corridors/table reads, proof/profile decisions and frozen legacy source/model contracts. |
| L1 | Delivered: loop component typechecks and 25 finite configurations pass; the existing five target and 19 composition configurations also pass, 49 total. Independent loop oracle passes 29 concrete cases and four signed32/word64 arithmetic controls. Integration is the documented checked-premise interface, not a mechanically checked coupling of the models. |
| L2 | Delivered within the coverage-only scope: seven focused Rust loop tests pass, including both captured local regions and malformed/unproved proof controls. Existing path-cycle prohibitions remain intact. |
| L3 | Delivered: 41 native controls, including three positives, pass. Eight of eight source-isolated mutations receive behavioral credit from their passing positive and named failing negative. |
| L4 | Corrected and qualified: referenced endpoints are represented as default `Stop` placeholders before resolver proof production, including nonfollowed call destinations and unattempted slice seeds. This adds no roots and forces no discovery. Publication's graph-consistency check remains intact; no digest is relabeled. The focused endpoint-publication regression passes. Actual retained 2026-10-14 combined reports still pass frozen-contract semantic replay. |
| L5 | Corrected snapshot passes every applicable root/native/frame/report gate in `validation-20261015T050857`, including seven focused loop tests and the separate publication regression. The 49 model configurations, 41 native controls and eight behavioral mutants pass again. Fresh replay `generated-replay-20261015T050942Z` dispatches 168 + 162 observations; both wrong-digest controls reject before dispatch. Replay remains regression evidence, not full-dump acceptance. |
| L6 | Passed: corrected probe `dump-20261015T051409` meets every stated original-dump target/coverage/parity gate. Both DA09/DADD are complete with four targets and accepted induction receipts; all nine original table sets and 51 formerly missing starts reconcile. Failed attempt `dump-20261015T050210` remains separately identified, including its passing callee parity. |

All Cargo, native/model, mutation, replay and dump execution ran in remote `windows-dev` WSL. Local work was source review and lightweight static documentation checks. Earlier failed qualification attempts remain separate evidence; a later passing attempt does not erase them.

### Accepted original-dump result

Probe `dump-20261015T051409` elapsed 202,410 ms. All nine original dispatches are complete: 370 table entries reconcile to 64 distinct destinations, and all 51 formerly missing starts were attempted. Original DA09 and newly exposed DADD each retain four targets and pass independent loop-receipt admission. Native accepts both frame queries, with exact normalized-request and full-state parity against Rust.

| Result | Caller frame 1 | Callee frame 0 |
| --- | --- | --- |
| Candidate sites / epoch | 9,590 / 609 | 778 / 129 |
| Target coverage | 10 of 10 caller indirect sites complete, including both loop sites | Independent callee obligations remain explicit |
| Guard barriers | 30 | 12 |
| Completed core | 9 decoded, 9 edges, 1,269 definitions | 768 decoded, 895 edges, 1,289,259 definitions |
| Rust/native request and full state | Equal | Equal |

The caller's initial MOVAPS remains unknown. Frame listing 1 → 0 at NP10 is unavailable, returning zero paths with `missing-or-ambiguous-active-call-anchor`. This does not prove no path exists and does not fail the narrower target-closure gate. These semantic/anchor barriers remain separate work; the parent ninth C5 coverage clause is closed.

## L0 decisions to freeze before runtime edits

1. **Region rule:** bounded local phase discovery from actual table/control structure and definition boundaries; exact independent enumeration of all crossing/internal edges. Maximal SCCs may guide discovery but are not automatically proof regions.
2. **Entrance rule:** a checked base-reset assignment plus a fully covered acyclic corridor establishes the assertion for arbitrary earlier scalar state. A bypass into the corridor or an additional region entrance must be represented and proved.
3. **Assertions:** width-aware `Top`, constant, unsigned interval and finite set; same-iteration compare/flag/selector definition provenance. Unknown pointer loads and byte loads are fresh abstract values, with no inferred cross-iteration equality.
4. **Proof representation:** retain old path witnesses and add `ExistingPrefixTree | InductiveDispatch` coverage. The first loop rule covers the entire queried dispatch; arbitrary prefix summary application is deferred.
5. **Wire identity:** local target report v3/profile local-v2; combined native profile v2; composition v2; combined minidump v5, explanation v4 and frame-path v4. Preserve target-only v1, guard-only behavior and a dedicated semantic replay path for legacy combined reports. Freeze old Rust/model source bytes as hash-verified fixture assets before edits; select checker semantics and admitted proof identities by version, separately from the new helper build identity. New loop-capable producers use new identities even when a loop proof declines.
6. **Budget accounting:** use existing target-limit fields; charge every nested scan, transfer/inclusion and finite-set operation; preserve zero limits and unchanged global defaults. Define producer and validator work accounting separately, including region edges, assertion sizes and report decoding.
7. **Proof independence:** replay original source BIL, captured bytes/control and table reads. Do not accept a producer's asserted constant, region boundary, domain, successful convergence flag or existing `complete` bit as its own evidence.

## Required positive and negative controls

| Family | Positive controls | Required rejection or partial controls |
| --- | --- | --- |
| Region and entrances | Both nine-node phase regions; base clobbers elsewhere in the large SCC do not poison a valid locally reinitialized phase; multiple independently initialized entrances | Hidden entrance, corridor bypass, root inside region without proof, omitted edge/exit, incorrect region contraction |
| Induction | Stable base with changing RCX; any number of pointer-loop and range-loop traversals; selector values vary across iterations | Base clobbered on one edge, different base on one entrance, circular reliance on candidate completeness, omitted recurrence |
| Branch constraints | MOVZX byte domain and unsigned JA untaken edge prove `0..9` at the table load | Wrong polarity, signed comparison, flag clobber, selector overwritten after comparison, applying the selector bound to target-valued R8 |
| Loads and effects | Fresh byte/pointer values, captured signed32 table arithmetic, existing stable-load infeasible receipts preserved | Equating different iterations' loads; original store or hidden pending-store BIL; opaque call; unknown memory write; unsupported relevant transfer |
| Captured evidence | All ten required selector slots with exact bytes/contributors and four derived destinations | Missing/conflicting slot, bad sign extension or wrap arithmetic, wrong base/slot/width, omitted table successor |
| Identity and consumers | Same sealed scope/epoch across producer, Rust, native and saved report; actual retained v1 combined minidump/frame semantic replay; valid old/new codec cases | Altered snapshot/activation/roots/semantics/epoch, swapped source AST, stripped closure, new loop evidence submitted under a legacy profile/hash, unsupported profile downgrade, malformed/extra fields |
| Resources and termination | Finite admitted region and independent receipt checking; runtime loop need not terminate | Zero step/value/time allowance, producer and native budget exhaustion, oversized assertions/evidence, nested uncharged work |

Use an independent small finite state space to enumerate one-step transfer inclusion and generate induction counterexamples. Finite oracle cases do not establish a universal Rust theorem. Mutations must independently disable entrance checking, base preservation, branch provenance, successor coverage, selector freshness or epoch binding. Credit requires a passing original and a named behavioral negative; compile errors, timeouts and rejection by an unrelated still-active check receive no behavioral mutation credit.

## Remote validation and evidence commands

All Cargo, native helper/SDK compilation, Apalache/TLC, replay, mutations and original-dump execution run on remote `windows-dev` WSL through the established `r_windev` workflow. Source inspection and document checks may run locally. Synchronize an exact source snapshot, verify archive/source/tool hashes and use a task-private checkout. Keep replay and mutation SUT build directories isolated under their checkout's `target/`.

The following existing root commands must pass in that remote checkout after implementation:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
bash Specs/check-target-resolution.sh
bash Specs/check-guarded-target-resolution.sh
bash Specs/check-loop-target-closure.sh
python3 tests/bap/fixtures/composition/oracle.py --check
python3 tests/bap/fixtures/loop-closure/oracle.py --check
python3 tests/bap/fixtures/loop-closure/extract.py --check
```

The loop-model/oracle/fixture entry points now exist and were exercised remotely. L5 records exact invocations of the native/frame, replay and mutation tools, including affected ignored tests, strict target validation, completion codecs and legacy replay. Actual new dump receipt replay belongs to L6. Builds use task-owned native/replay/mutation directories; the replay tool's fixed `target/bap-core-replay` path aliases the isolated `target/loop-aware-replay-build` directory within the task checkout.

Future evidence must retain source and tool hashes, model files/configs, helper manifests, exact budgets, stdout/stderr, original and mutated variants, failed attempts, original dump/PDB provenance when symbols are used, all capture-read witnesses, prospective/final graph identities and native/Rust comparison results. Preserve the old 2026-10-14 artifacts byte-for-byte as historical results.

## Acceptance and stopping rules

- L0–L1 deliver a reviewed contract and finite expectation set; they do not claim implementation.
- L2–L4 cannot publish completeness from an unvalidated summary or weaken legacy path-cycle checks globally. A failed summary preserves candidates and an explicit residual.
- L5 is accepted only for its exercised source/tool/model/corpus scope. Core-only builds retain no activated external crate dependencies.
- L6 must freshly establish both `0x00007ff77440da09` and `0x00007ff77440dadd` as complete, with their four expected targets, accepted Rust/native induction evidence and all-nine reconciliation. Re-run both frame queries and compare complete normalized requests and states.
- Report remaining caller/callee barriers and NP10 availability independently. A still-unavailable listing does not fail this narrower loop-closure gate; neither does successful target closure satisfy full frame-path acceptance.
- The parent ninth C5 clause is closed by the accepted original-dump gate. Completion and archival apply to this explicit target-coverage scope; neither implies successful frame-path enumeration or general loop support.

## Validation of this plan document

The initial 2026-10-15 design delivery used source inspection and independent semantic/qualification reviews, without runtime execution. The dated ledger records initial qualification, failed caller preparation, coordinator correction, fresh qualification and the accepted second dump probe separately. This status update changes documentation only; local link/navigation and whitespace checks remain required. The [qualification record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) owns the sealed source/tool identities and exercised scope.
