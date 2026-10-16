# Loop-aware resolver: design and implementation plan

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

**Proposed, 2026-10-15. No runtime implementation or new dump result is claimed.**

Extend the existing resolver with a private inductive loop-closure module. The first target is the two nine-instruction local dispatch regions in dump03958, with checked initialization, every entrance/backedge, fresh selector loads and independently replayed coverage. The full cyclic components contain many calls and clobbers and are outside this first proof scope.

This is a generated reading view. Canonical contracts remain in the [composition design](../../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up); execution stages remain in the [L0–L6 plan](../plans/completed/loop-aware-target-resolution.md).

## Proposed design


The following loop-aware design is proposed on 2026-10-15. Its [L0–L6 implementation plan](../plans/completed/loop-aware-target-resolution.md) covers the stable-base follow-up to C5. This section is the canonical contract; the plan owns task sequencing, and future raw qualification belongs under `evidence/Ariadne/loop-aware-target-resolution/`. The ninth C5 clause remains open until fresh implementation and dump evidence establish it. Designing this extension does not change the 2026-10-14 result.

### Decision and first support scope

Extend the existing target resolver with a private loop-closure module. Keep one discovery coordinator, one candidate epoch and the existing pointer/table evaluation. A loop closure is an additional coverage-proof strategy, not another competing target resolver. No resolver registry, general SMT solver, new runtime dependency or new CLI switch is required for this first scope.

Support bounded, source-checked local dispatch regions with a captured relative-32 table. Prove a constant table-base bank across every region entrance and internal edge, permit changing object pointers and fresh selector loads, and prove a finite unsigned selector domain at each indexed table load. Rooted target-only v1 remains unchanged in this stage; the new proof is used by local combined preparation. General nested-loop synthesis, arbitrary heap traversal, memory alias proofs, regional MOVAPS admission and successful frame-path enumeration remain separate work.

The analysis must terminate within its budgets. It need not prove that the program's loop terminates: an inductive invariant covers arbitrary finite traversals even when an infinite runtime traversal is possible.

### Dump-specific feasibility inspection

A read-only inspection on 2026-10-15 used the final caller [captured/candidate report](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/minidump-rust.json.gz) and [target receipts](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/target-report.json). This is structural evidence, not a new closure proof or dump execution.

| Property | Original dispatch | Newly exposed dispatch |
| --- | --- | --- |
| Dispatch VA | `0x00007ff77440da09` | `0x00007ff77440dadd` |
| Captured table base | `0x00007ff77ba909a8` | `0x00007ff77ba909d0` |
| Base initialization | LEA at `0x00007ff77440d9e2`, bytes `488d15bf2f6807` | LEA at `0x00007ff77440dab6`, bytes `488d15132f6807` |
| Represented region entrance | `0x00007ff77440d9e9 → 0x00007ff77440d9f7` | `0x00007ff77440dabd → 0x00007ff77440dacb` |
| Pointer-changing backedge | Table index 3 → `0x00007ff77440d9eb`, `mov rcx,[rcx]` | Table index 3 → `0x00007ff77440dabf`, `mov rcx,[rcx]` |
| Selector / compare / unsigned branch | `0x00007ff77440d9f7` / `0x00007ff77440d9fc` / `0x00007ff77440da00` | `0x00007ff77440dacb` / `0x00007ff77440dad0` / `0x00007ff77440dad4` |
| Proposed local region | 9 instructions, 10 internal edges, 1 entrance, 4 exits | 9 instructions, 10 internal edges, 1 entrance, 4 exits |
| Local base clobbers / calls / memory writes | 0 / 0 / 0 | 0 / 0 / 0 |
| Maximal candidate SCC | 4,694 nodes; 37 entrances; 631 sites may-define RDX; 246 calls | 411 nodes; 1 entrance; 53 sites may-define RDX; 18 calls |

The maximal SCC is unsuitable for the proposed constant-base invariant. The small phase region is the relevant proof domain: every represented entrance passes a base-reset LEA followed by an unconditional jump. Region construction must discover this shape from controls, transfers and definition boundaries; the addresses above are acceptance fixtures, never production dispatch conditions. The checker must independently enumerate every actual entrance and exit, so a producer cannot hide a clobber by shrinking its claimed region.

The caller candidate epoch is 610 and `composition.candidate_sha256` is `50b54d681fe01f9488da4cf2c90948afe52cb2ab13dad2e960bad55648122a3f`. The original dump SHA-256 remains `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`. Do not substitute the guard graph digest for this candidate-request identity. Exact region members, edges, original BIL, bytes, contributors and initialization chains must become source-bound L0 fixtures before implementation.

### Private module and invocation

Use a private Rust module under `src/bap/target_resolution/` for region discovery, finite invariant proposal and loop-receipt validation, with small named interfaces. Keep ordinary path substitution, existing target recognition and discovery ownership in their current modules. The native checker independently implements the same receipt contract from original source evidence.

```text
try_loop_closure(bound_query, candidate_graph, original_transfers,
                 dispatch_site, retained_table_evidence, shared_budget)
  -> NotApplicable
   | Candidate { coverage_receipt, table_witnesses }
   | Partial { reason }
```

Attempt this strategy for eligible local cyclic table contexts before finalizing `cyclic-incoming-state`. Preserve existing bounded-frontier, infeasible and stable-simple-cycle paths. A failed proposal leaves the original conservative result; a successful proposal is still candidate evidence until independent validation accepts it. No instruction address, expected target list or concrete crash-time register may select or initialize the strategy.

For the first version, a loop receipt proves **whole-dispatch incoming coverage** and attaches at that dispatch's root coverage obligation. It does not claim to close an arbitrary accumulated reverse-prefix context. Existing path receipts remain individually replayed target/infeasibility evidence. This avoids equating different reverse contexts or weakening the current repeated-path checks.

### Inductive proof obligations

Let `R` be a proposed finite local region, `G` the bound candidate graph and `I[n]` an assertion about the relevant scalar state immediately before region instruction `n`.

```text
Entrance:     every represented edge u outside R → v inside R
              has source-replayed initialization establishing I[v].

Preservation: original normal-path BIL at n, together with its edge predicate,
              maps every state admitted by I[n] into I[successor]
              for every internal edge.

Dispatch:     the assertion at the table-load point bounds its selector;
              captured reads and modular signed-offset arithmetic derive
              every possible target at the dispatch.

Coverage:     all region entrances, internal edges, exits, relevant roots,
              and all derived table successors are represented and checked.
```

An entrance proof may begin at a source-checked assignment that resets the base for arbitrary prior scalar values. Replay the complete short corridor from that assignment to the entrance. Any edge entering after the reset, any root inside the region or any alternate initialization needs its own proof; it cannot be silently ignored. First-scope unsupported entrances return partial.

Use a small width-aware private abstract domain: `Top`, constant, finite unsigned interval and finite word set. This is a resolver-proof implementation, separate from the supplied abstract-stateflow API. Proposal may iterate assertions within budgets; replay checks asserted inclusions directly and does not rerun or trust the producer's convergence decisions.

For each region, the intended point-specific assertions are:

1. RDX equals the captured base at all relevant points.
2. Each unknown selector-byte load produces a fresh arbitrary value in `0..255`; MOVZX preserves that unsigned interpretation.
3. The source-replayed CMP/JA chain establishes `selector ≤ 9` on the edge to the indexed load. Preserve compare/flag definition identity; wrong polarity, signed comparisons or intervening flag/selector writes cannot establish this bound.
4. The signed table load changes R8 from selector to offset, and ADD changes it to a member of the derived target set. The `0..9` assertion applies before the table load, not to R8 at the jump.

Fresh means an independent abstract value per transition. Even the range-check loop may be overapproximated with fresh loads; the new proof never needs two iterations' selector values to agree. Existing stronger stable-load contradiction proofs remain valid under their own unchanged premises.

The first scope rejects original stores, hidden pending-store BIL, opaque calls, unknown memory writes, unsupported relevant effects and unproved base clobbers inside the region or its initialization corridors. Changing RCX and ordinary pointer loads are permitted when the required invariant remains established. Unrelated scalar values may become `Top`. This rule introduces no normal-effect admission, LLVM effect fallback, concrete heap reads or historical memory premise.

### Avoiding circular target and region proofs

The current incomplete target set or `Instruction.complete` flag cannot establish a loop's successor coverage. First reconstruct the table form and finite selector domain from original transfers/assertions; validate every required captured slot and derive the full successor set. Compare it with the prospective candidate graph, queue every new destination, and recompute region boundaries and assertions after graph expansion. Only then admit the coverage certificate on the stable candidate epoch.

A missing destination may remain an explicit recovery endpoint; it cannot be erased from the target set. Unsupported control inside a claimed proof region prevents closure. A new graph entrance, changed source transfer, target-completeness change or changed boundary invalidates the affected receipt. One coordinator owns target union, proof invalidation and guard re-evaluation; no independent loop cache may outlive its bound epoch/scope.

In particular, the first accepted proposal can change `Instruction.complete` without adding a destination. That changes the candidate fingerprint and advances the epoch. Recompute and independently replay the summary on the resulting candidate graph before sealing; copying a receipt and replacing its epoch field is not revalidation.

### Receipt and coverage representation

The new local report retains existing path witnesses and adds a tagged coverage alternative for each row:

```text
CoverageEvidence =
    ExistingPrefixTree { path_receipt_refs }
  | InductiveDispatch { loop_closure_receipt }
```

`ExistingPrefixTree` preserves the existing exact incoming-prefix rules. `InductiveDispatch` independently covers every incoming state at one site through the entrance and preservation obligations above; it is not an `infeasible` receipt or an arbitrary-register local frontier. Retained path witnesses are individually validated even when the row uses inductive coverage. Target arithmetic from path/table evidence remains checked independently from the coverage choice. No reason is removed merely because a new strategy returned nonempty targets.

A strict `LoopClosureReceipt` carries its rule version, dispatch site, ordered region VAs, complete typed boundary/internal edge inventories, initialization corridors, point assertions and guard-definition references, captured table/domain/entry references, and original transfer/byte identities. It binds the snapshot, query/activation/premises, semantic/model ruleset, candidate epoch and graph digest. It contains no trusted “proof succeeded” Boolean. Rust and native reconstruct the graph/effects, check all inclusions and table arithmetic, and derive acceptance themselves.

Replay preserves the old prohibition on general cycles in ordinary path receipts. The new induction rule is the sole additional way to establish cyclic dispatch coverage. If any remaining required context or read is unresolved, the row stays partial with its known candidates and explicit reasons.

### Version and compatibility decision

The following names are planned wire identities; they are not current capabilities:

| Surface | Current exercised identity | Loop-capable producer identity |
| --- | --- | --- |
| Local target report / profile | `ariadne.indirect-target-resolution/v2` / `captured-local-indirect-targets/v1` | `ariadne.indirect-target-resolution/v3` / `captured-local-indirect-targets/v2` |
| Combined native input | `captured-guarded-targets/v1` | `captured-guarded-targets/v2` |
| Composition report | `ariadne.guarded-target-resolution/v1` | `ariadne.guarded-target-resolution/v2` |
| Combined minidump / explanation / frame-path reports | v4 / v3 / v3 | v5 / v4 / v4 |

New combined queries use the new identities consistently, including queries where the loop strategy declines. Keep rooted v1, target-only and guard-only behavior and legacy saved-report decoding explicitly supported. Old helpers reject the new combined profile before analysis; never silently strip a loop proof or fall back to weaker admission. New readers dispatch by version and preserve exact old/new semantics. Model/engine hashes and profile commitments include the new closure checker; receipt binding must not hash its own enclosing report into itself.

Legacy compatibility includes **semantic replay of the retained reports**, not parsing alone. The current composition validator hashes both its live Rust source and live TLA+ model. Editing those files changes the expected identities, so version dispatch must also select a frozen legacy validation contract. Before runtime edits, preserve the exact old sources as hash-verified fixture assets and retain a dedicated v1 checker/replay path. Its admitted model/checker pair is `e142a6fd22d78044c444c26211b7c659a56fedb5f9e555aa20e3aa1be23e8b10` / `c36c8876810e35ed10b7e366e650d7854958b0ad7b07d33084039d39b68e9580`. Native build metadata must advertise version-indexed supported proof identities separately from the current helper's own build identity. Keep retained receipt identities unchanged; a legacy identity must not authorize the new loop fields or weaker replay. Test an actual retained 2026-10-14 combined minidump and frame report after the new implementation is built, together with profile/hash downgrade and proof-stripping negatives.

Keep the current API and CLI opt-ins and the existing target-limit JSON fields. Charge graph scans, assertion transfer/inclusion checks, domain operations and validation work to finite counters derived from `max_steps`, `max_values`, `max_entries`, `max_read_bytes`, `max_evidence_bytes`, `max_rounds` and `max_elapsed_ms`. Loop computation has no uncapped nested work or changed global defaults. Rooted and disabled modes gain no new semantics. Limits still allow explicit zero-work outcomes. L0 freezes exact accounting units for producer and checker separately.

### Qualification and acceptance boundary

The [L0–L6 plan](../plans/completed/loop-aware-target-resolution.md) requires an authoritative loop-closure model and independent oracle before runtime changes, then Rust production/replay, native replay, integration/codec checks, source-isolated mutation/replay and the original dump retry. All Cargo, native, model and replay work runs in remote `windows-dev` WSL. Local checks for this design change are documentation/navigation and whitespace only.

The original-dump gate requires both DA09 and DADD to retain their four witnessed targets and become complete through independently accepted induction receipts, with all other original table candidates preserved and native/Rust full-state parity. Inventory every remaining coverage barrier and path outcome. Closing these two sites does not qualify the maximal SCCs, eliminate other semantic stops, prove MOVAPS alignment or guarantee an active call anchor or available frame paths.

**Dated design validation, 2026-10-15:** source and retained graph inspection plus semantic/qualification review support the proposed small-region scope. Runtime, model and dump acceptance remain unexecuted. The 2026-10-14 artifacts retain their original identities and result; future implementation qualification requires new source/tool-bound records.


---

## Implementation plan — L0–L6

## Context and follow-up

**Status.** Designed 2026-10-15; implementation and qualification have not started. L0–L6 below extend the existing resolver with checked local-region induction. No loop capability is accepted by this document.

**Why this document exists.** The [canonical composition design](../../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up) owns this extension's contracts. The [C0–C6 parent plan](../plans/completed/guarded-target-resolution.md) retains the ninth incoming-coverage clause after successful candidate recovery.

**What this document establishes.** The support boundary, reviewable implementation stages, file ownership, dependencies and remote acceptance gates for closing the DA09/DADD cyclic dispatch certificates.

**Where to go next.** Read the canonical design's loop section first, then L0 for exact proof/codec/budget decisions and L6 for the required dump outcome. The [retained qualification](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md) supplies the baseline; the [formal-model guide](../../Specs/README.md) defines model authority.

**What remains unresolved.** Every L stage remains pending. The callee's other indirect jumps and work residuals, caller semantic barriers, MOVAPS admission, call-anchor recovery and full frame paths remain separate gates. Larger SCCs and general loop synthesis are outside this first scope.

## Objective and design decision

Extend the current resolver with a private loop-closure proof module. Reuse `relative32` evaluation and one materialization coordinator. For a small local dispatch region, prove a stable table base, permit changing RCX and fresh selector loads, and establish the selector domain before each indexed table load. Produce a whole-dispatch induction receipt checked independently by Rust and native admission.

This is a design-and-plan delivery only. It authorizes no claim that a code change or new dump result exists. Implementation should execute the gates below without replacing unknown controls, adding roots or importing crash-time values into earlier states.

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

These are fixture expectations, never address-specific production rules. The canonical design records the table bases, original bytes and complete obligation structure. L0 must independently reproduce these facts from the sealed baseline and retain them as test fixtures. Structural feasibility is not a completed induction proof; rejected reverse contexts were not fully recorded by the old implementation.

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

The private module returns `NotApplicable`, `Candidate{receipt,table_witnesses}` or `Partial{reason}`. A candidate cannot set `complete=true` until the shared validator accepts all required obligations on the final epoch. New target discoveries invalidate region/boundary proofs and restart checked closure. One context's first successful witness cannot erase other incoming alternatives.

## Stages, ownership and dependencies

Owners describe independent responsibilities for execution, not changes made by this plan. Workers are not alone in the checkout: preserve unrelated changes, edit only assigned files and coordinate shared interfaces before implementation. L0 freezes the interface and receipt contract before L2/L3 proceed in parallel. Review gates are evidence gates, not additional user-confirmation steps.

| Stage / owner | Principal files and tasks | Depends on | Reviewable exit |
| --- | --- | --- | --- |
| **L0 — Contract and baseline owner** | Update canonical design; preserve this plan; extract source-bound loop fixtures into `tests/bap/fixtures/loop-closure/`; record graph policy, regions, entrances, LEA corridors, original BIL/bytes, tables and baseline hashes. Freeze new coverage tag, full wire fields, private interface, version-indexed legacy validation contract and finite work units. | Source inspection | Independent reproduction of both local regions and all entrances; frozen legacy source/model identities; explicit rejection of the maximal-SCC invariant; no production address constants or expected-target injection. |
| **L1 — Formal model and oracle owner** | Add planned `Specs/AriadneLoopTargetClosure.tla`, finite configs and checker; integrate its coverage case with `AriadneTargetResolution.tla` and composition authority. Add an independent finite oracle under the fixture directory. Do not encode production matcher/substitution as the oracle. | L0 | Initialization, preservation, domain implication, every entrance/edge/exit, stale-epoch invalidation, conservative partial publication and bounded analyzer termination are modeled. Positive and deliberate counterexample configurations behave as specified. |
| **L2 — Rust resolver owner** | `src/bap/target_resolution.rs`; private implementation under `src/bap/target_resolution/`; strict receipt types; `tests/bap/target_resolution_unit.rs`; `src/bin/target_resolution_validate.rs` as necessary. Add bounded region discovery, point assertions and independent replay from original BIL. | L1 contract/model cases | Both synthetic loop shapes yield accepted whole-dispatch evidence. Replay rejects bad entrances, clobbers, wrong guard provenance and tampered boundaries. Existing target/frontier/infeasible/cycle tests retain their stated behavior. |
| **L3 — Native admission owner** | `native/bap-core/capture.ml`, `composition.ml`, `main.ml`, `build.py`; relevant `src/bap/core_adapter.rs`, `core_protocol.rs`, `core_session.rs` interfaces coordinated with L2. Add independent assertion/edge/read replay, new capability/profile handling and version-indexed legacy/new ruleset/model identities. | L1 and frozen L2 wire contract | Native accepts the same valid proof cases and rejects named invalid ones. Old helpers explicitly reject the new profile. Legacy proof replay retains its frozen contract separately from the new helper build identity. JSON field order cannot change symbolic equality. Exact read contributors and original BIL remain mandatory. |
| **L4 — Integration and reports owner** | `src/input/materialize.rs`; `src/bap/composition.rs`; input frame/report/investigation codecs, `src/reports/`, CLI and consumer tests. Integrate proof invalidation, target union, completeness-only epoch changes, dedicated v1 replay, saved old/new versions and JSON/text/DOT explanations. | L2 + L3 | One coordinator and immutable query scope; new targets queued without roots; summaries rechecked after epoch changes; no proof stripping or unsupported fallback. Validate actual retained 2026-10-14 combined minidump/frame reports without rewriting their model/checker identities; old/new roundtrips preserve full requests and gaps. |
| **L5 — Qualification owner** | Loop oracle/tests, targeted mutation tooling, isolated native SDK/helper/replay outputs, model logs and a new source/tool manifest under `evidence/Ariadne/loop-aware-target-resolution/`. | L4 | Applicable root checks, model/oracle controls, native admission, saved-report controls, behavioral mutations and generated replay pass on the same source snapshot. Missing prerequisites remain unexercised rather than passed. |
| **L6 — Original-dump and delivery owner** | Byte-identical dump retry, all-nine table reconciliation, DA09/DADD proof comparison, native/Rust full-state parity, remaining-barrier report; update canonical dated validation and parent C5 status. | L5 | Both dispatches complete with the expected four-target sets and validated induction receipts; eight previously complete certificates retain valid coverage; all original candidates remain. Separate frame-path result and remaining barriers are reported honestly. |

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
python3 tests/bap/fixtures/composition/oracle.py --check
```

L1 must create and verify the new loop-model/oracle entry points. L5 records exact invocations of the existing target-resolution, native/frame, replay and mutation tools after inspecting their current options; do not present a planned script or guessed flag as an existing executable command. Include the affected ignored native tests, strict target validator, both completion codecs, actual dump receipt replay and legacy capability controls. Use dedicated outputs such as `target/loop-aware-native`, `target/loop-aware-replay-build` and `target/loop-aware-mutations-build`; adapt any tool with a fixed build path or isolate its whole SUT checkout.

Future evidence must retain source and tool hashes, model files/configs, helper manifests, exact budgets, stdout/stderr, original and mutated variants, failed attempts, original dump/PDB provenance when symbols are used, all capture-read witnesses, prospective/final graph identities and native/Rust comparison results. Preserve the old 2026-10-14 artifacts byte-for-byte as historical results.

## Acceptance and stopping rules

- L0–L1 deliver a reviewed contract and finite expectation set; they do not claim implementation.
- L2–L4 cannot publish completeness from an unvalidated summary or weaken legacy path-cycle checks globally. A failed summary preserves candidates and an explicit residual.
- L5 is accepted only for its exercised source/tool/model/corpus scope. Core-only builds retain no activated external crate dependencies.
- L6 must freshly establish both `0x00007ff77440da09` and `0x00007ff77440dadd` as complete, with their four expected targets, accepted Rust/native induction evidence and all-nine reconciliation. Re-run both frame queries and compare complete normalized requests and states.
- Report remaining caller/callee barriers and NP10 availability independently. A still-unavailable listing does not fail this narrower loop-closure gate; neither does successful target closure satisfy full frame-path acceptance.
- Update the parent ninth C5 clause only after the original-dump gate passes. Do not archive either active plan as full delivery merely because candidate recovery or finite tests pass.

## Validation of this plan document

This change is documentation only. Source inspection and independent semantic/qualification reviews informed the region, induction and version decisions. Local link/navigation and whitespace checks must pass before presenting the plan. No Cargo, native/model build, replay, mutation or dump retry is part of this planning turn.
