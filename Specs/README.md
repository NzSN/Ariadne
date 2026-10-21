# Ariadne formal model

## Context and follow-up

**Status.** Active analysis-model authority. Retired AMD64/x86-64 ISA specifications,
coverage inventories and their checkers were removed on 2026-10-11; the retired
model guides were removed on 2026-10-16.
The [specification synchronization ledger](../.agents/plans/specification-sync.md)
records the subsequent source audit and separate qualification limits.

**Why this document exists.** [Project overview](../README.md) motivates snapshot-scoped control flow and possible value origins.

**What this document establishes.** The analysis specifications define admissible inputs, state transitions, invariants and the meaning of partial results for recovery, stateflow and supplied IR.

**Where to go next.**

- [Explicit alignment hypotheses](AriadneAlignmentHypothesis.tla) and the
  [H0–H5 implementation plan](../.agents/plans/alignment-hypotheses.md) — additive
  conditional residue filtering, activation ownership and normal selection.
  The original guard verdict and proof remain separate. The
  [2026-10-16 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/alignment-hypotheses/20261016/README.md)
  records 25 finite model configurations and the independent 39-case oracle;
  runtime/mutation evidence remains a separate tier.

- [Predicate admission v2](AriadnePredicateAdmission.tla) and the
  [caller semantic-coverage plan](../.agents/plans/caller-semantic-coverage.md) — checked
  normal-completion terminals, exact MOVAPS load/store guards and separate
  exception-resumption limits. The predicate section below records the new
  contract, passed S5 finite runtime qualification and the separate incomplete original-caller gate.

- [Loop-target closure model](AriadneLoopTargetClosure.tla) and
  [L0–L6 extension plan](../.agents/plans/completed/loop-aware-target-resolution.md) — local-region
  entrance initialization, induction over original edges, fresh selector loads
  and the checked coverage premise consumed by target/composition admission.
  The component interface section below separates
  executable premise checks from model-to-model refinement, which is not proved.

- [Guarded target composition model](AriadneGuardedTargetResolution.tla) and
  [C0–C6 plan](../.agents/plans/completed/guarded-target-resolution.md) — immutable query scope,
  original/candidate/final graph layering, a shared epoch, paired receipt
  invalidation and proof-only final effects. The 2026-10-14 source-bound
  qualification is retained; the new loop component has its own acceptance gate.

- [Indirect-target model](AriadneTargetResolution.tla) and
  [R0–R6 ledger](../.agents/plans/indirect-target-resolution.md) — finite captured-table
  candidates, residuals, incoming-coverage invalidation and resource stops;
  five model scenarios and implementation qualification have separate records.

- [Frame question composition](AriadneFrameQuestion.tla),
  [fair question scheduling](AriadneQuestionSchedule.tla) and
  [P0–P10 program](../.agents/plans/frame-question-investigation.md) — finite
  verdict, premise, epoch, candidate-preservation and fair-termination contracts.
  Run `bash Specs/check-frame-question.sh` for two Apalache type checks and
  eighteen TLC configurations. BAP projection, capture bytes, hashes, host
  allocation and cooperative clock behavior remain concrete premises; these
  finite checks do not prove Rust/native/ISA refinement. See the
  [local qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261018/README.md) and
  [2026-10-19 remote finite acceptance](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md).

- [Frame-connection model](AriadneFrameConnections.tla) and
  [Stage 5.2 ledger](../.agents/plans/frame-connections.md) — represented
  corridor/SCC exactness, shortest first sample, bounded further samples and
  preserved frontiers/writers/hypotheses. The
  [local record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-connections/20261018/README.md)
  separates finite checking, compiled mutations, captures and remote limits.

- [Frame-path model](AriadneFramePaths.tla) and
  [F0–F4 plan](../.agents/plans/frame-path-enumeration.md) — strict output count, valid
  structural paths, bounded work and preservation of memory writers; the
  [2026-10-20 finite qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-paths/20261020/README.md)
  records model checks separately from runtime/capture evidence.

- [Memory refinement model](AriadneMemoryRefinement.tla) and
  [implementation ledger](../.agents/plans/memory-provenance-refinement.md) — specified
  candidate-preservation and backward-value contract. Local Apalache/TLC checking
  passes in the section-5 record after adding the sequence type annotation;
  [remote M4/Scanner acceptance](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md)
  now passes for the selected profile; the broader audited model suite remains separate.

- [Selected I5c design](../docs/Ariadne/address-wrap-design.md) and
  [W0 model/oracle stage](../.agents/plans/i5c-address-wrap.md#w0--freeze-semantics-and-independent-expectations)
  — [address-wrap decision model](AriadneAddressWrap.tla), qualified in the
  [2026-10-20 W0 record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w0/README.md):
  52 scenarios, one Apalache typecheck and six TLC configurations on exact
  promoted sources. No bounded-SMT, ISA or runtime conformance result is claimed.

- [I5b question-level decision model](AriadneZeroBaseOffset.tla) — admission,
  output availability and zero-base/nonzero-displacement conclusions; the
  [source review](../docs/Ariadne/zero-base-offset-design.md#decoded-record-and-independent-oracle) separates finite checking
  from Rust/native and hardware evidence.

- [Native analysis replay and qualification](../docs/Ariadne/bap-analysis-core-design.md#native-qualification) — records native-helper observations, mutation sensitivity and CLI ownership separately from the retained Rust replay; neither finite campaign is a universal proof.

- [Rust implementation](../docs/implementation.md) — maps model actions to executable analysis.
- [Stateflow design](../docs/machine-state-design.md) — extends a frozen recovered CFG with supplied abstract transitions.
- [Assurance decision](../docs/Ariadne/semantic-assurance.md) — separates active analysis models from retired ISA proofs.

**What remains unresolved.** Finite conformance checks do not prove the Rust implementation correct for every valid request. A universal refinement proof remains open, and adapter facts remain premises. Independent architectural instruction-step proofs are retired.

For the wider context, see the optional [documentation map](../docs/documentation-map.md).

`AriadneTypes.tla` defines semantic Apalache aliases shared across the suite.
`AriadneMachineCommon.tla` defines stateless knowledge shared by the machine
models. `Ariadne.tla` specifies the machine-code analysis engine for binary and
crash-dump inputs, while `AriadneMachineState.tla` consumes its frozen local CFG.
`AriadneLLVMIR.tla` separately specifies analysis of verified LLVM IR supplied
directly as `.ll` or `.bc`. The [Rust library](../src/lib.rs), built with Cargo,
implements the `Ariadne.tla` machine-analysis core. The LLVM IR and abstract
machine-state models also have Rust implementations and finite generated replay. See the
[implementation guide](../docs/implementation.md) for the Rust correspondence
and validation boundary.

The independent ISA specifications, initial instruction rules and coverage
inventories are available in Git history. Their removal leaves the active CFG,
dataflow, slicing, input/effects, stateflow, supplied-IR, memory-refinement,
frame-path and question-level models in this directory. The
[semantic assurance decision](../docs/Ariadne/semantic-assurance.md#dependency-audit-and-retained-references)
records the archive location, retained [Lean reference](../lean/README.md),
BAP's trusted role and the analysis-model boundary.

Current validation follows the [executable test matrix](../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.

## Frame connections: Stage 5.2

Run `bash Specs/check-frame-connections.sh` for Apalache type checking, 13 TLC
configurations with safety and fair termination, and the independent literal
oracle. Configurations cover diamond/cycle/self-loop/parallel/disconnected/
unknown-reconnect/equal/conditional/missing-anchor cases, zero work/search,
NP=1 and multiple samples. `AriadneFrameConnections.tla` computes a finite
least closure, requires its completed relation to equal independently enumerated
finite paths, derives forward/backward corridor and mutual-reachability
components, and checks quotient acyclicity and first-witness minimality.

`src/investigation/frame_connections.rs` implements bounded graph projection,
forward/reverse worklists, iterative Kosaraju SCCs and BFS/detours. The model
abstracts those traversals into closure rounds. Its queue models a first shortest
loop-free witness; subsequent sample choices abstract bounded detours by valid
node paths with strict NP. Typed edge facts remain in the modeled graph, while
parallel sample identity and independent concrete layer scheduling are erased.
The literal Python oracle uses Floyd–Warshall and path permutations across
all 512 three-node directed graphs plus four named cases; Rust tests compare
actual typed routes, SCCs and quotient edges. Capture checking separately uses
Tarjan SCCs, DFS closure and distance relaxation.

Source admission, activation-qualified identity, captured bytes, E8 anchors,
function extents, trusted lifting and source hashes are premises. Concrete
codec validation, allocation accounting, source publication preservation,
clock observations and deterministic deadline-prefix replay are Rust contracts
and separate tests. Preserving a modeled writer set says samples cannot remove
candidates; this module performs no writer analysis. The checks do not prove
universal refinement, instruction semantics, feasibility, execution history or
program-level disconnection. The dated evidence records local Windows WSL
results; the [2026-10-19 remote record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md)
now closes the finite FC5/FC6 gate on the exact declared sources. It is separate from the later [S3 finite suite qualification](#specification-synchronization-s3-qualification-2026-10-20).

## Current model ownership

The historical 2026-10-11 source audit covers **17 active modules and five replay modules**.
The indirect-target extension adds one active module and five configurations on
2026-10-13, with its own source-bound qualification below.
The loop-target extension adds a component module and 25 configurations on
2026-10-15, with a separate premise interface and qualification scope below.
The 2026-10-16 [structural-frame model](AriadneFrameStructure.tla) adds the
recovery-prefix, independent-frame and captured-call contract for
[Stage 5.1](../docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow).
It seals in `Recover`, including a drained queue, and never executes
`FinishRecovery`, dataflow or slicing. Concrete BAP lifting, capture/proof
validation and byte sizing remain explicit premises. Its finite checker is
`bash Specs/check-frame-structure.sh`; the independent literal oracle and
compiled behavioral mutations have separate observers and evidence.
[AriadneAlignmentHypothesis.tla](AriadneAlignmentHypothesis.tla) adds per-point
masked residue propagation and conditional normal-selection invariants without
changing the original root-premise authority. Its
[qualified finite scope](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/alignment-hypotheses/20261016/README.md)
does not establish accumulated-path feasibility or universal refinement.
The [synchronization plan](../.agents/plans/specification-sync.md) separates source
corrections and bounded local evidence from remote qualification. A model's
age alone does not imply drift; unchanged executable contracts retain their
original bytes and replay bindings.

| Models | Current source/contract owner | Audit result and boundary |
| --- | --- | --- |
| [Types](AriadneTypes.tla), [common machine facts](AriadneMachineCommon.tla) | `src/model.rs`, `src/machine_state.rs`, `src/llvm_ir.rs` | Current shared vocabulary and normalized request constraints; transparent aliases and mathematical integers remain representation abstractions. |
| [Core](Ariadne.tla), [general examples](AriadneExample.tla), [calls](AriadneCalls.tla), [pipeline](AriadnePipeline.tla) | `src/engine.rs`, `native/bap-core/recovery.ml` | Current recovery/dataflow/slicing phases. Native indexes, transport, batching and limits have separate contracts; neither adapter adds CPU execution to this model. |
| [Abstract stateflow](AriadneMachineState.tla), [example](AriadneMachineStateExample.tla) | `src/machine_state.rs`, `native/bap-core/stateflow.ml` | Current supplied finite semantics and structural edge classification. Captured registers do not establish earlier branch outcomes. |
| [Supplied IR](AriadneLLVMIR.tla), [example](AriadneLLVMIRExample.tla) | `src/llvm_ir.rs`, `src/ir/`, `native/llvm_ir/` | Current instruction dependencies and separate block CFG; no binary-to-IR reconstruction. |
| [Input](AriadneInput.tla), [checks](AriadneInputChecks.tla) | `src/input/address_space.rs`, `src/input/materialize.rs` | Current byte agreement, file-offset correspondence and local discovery closure. Actual parser limits, context validity and unwind admission remain reader contracts. |
| [Effects](AriadneEffects.tla), [checks](AriadneEffectsChecks.tla) | `src/effects/`, `src/bap/projection.rs` | Executable projection contract unchanged; producer wording now names trusted BAP lifting and independent LLVM facts. No hardware/ISA proof. |
| [Predicate admission v2](AriadnePredicateAdmission.tla) | `src/bap/guard_admission.rs`, private terminal-control admission, native guard/terminal replay | The 2026-10-15 extension defines 58 finite scenarios: 27 retained configurations plus 31 terminal/load cases. Normal terminals end local normal completion, keep opaque effects and represent exceptional exits. Source recognition and byte extents have separate concrete controls. S5 finite runtime qualification passes on its recorded sources/helper; original-caller completion remains S6 partial. Frozen v1 contracts remain separate. |
| [Zero base/displacement](AriadneZeroBaseOffset.tla) | `src/investigation/zero_base_offset.rs` | Current question-level reduction over admitted coherent evidence and result budgets. Context/decode/BIL admission and full-width arithmetic have separate source/capture tests. |
| [Memory refinement](AriadneMemoryRefinement.tla) | `src/investigation/backward_values.rs`, `src/investigation/memory_refinement.rs` | Updated exact/constrained/unknown meanings, composition/cap stops, conflict distinction and unavailable/candidate preservation. Four-bit words and two-operation chains are finite representatives; worklist and receipt validation remain outside this component model. |
| [Frame paths](AriadneFramePaths.tla) | `src/investigation/frame_paths.rs`, `src/investigation/frame_unwind.rs` | Updated typed-edge DFS, strict NP, work/scan/visit/step guards, fair termination and conservative exhaustion. Activation-qualified node IDs and a bound composed graph are premises. External resource stops abstract byte/graph limits; they do not prove concrete payload sizing or RSS. |
| [Indirect targets](AriadneTargetResolution.tla) | `src/bap/target_resolution.rs`, `src/input/materialize.rs`, native `capture.ml` | Added 2026-10-13: frozen captured-control-data premise, signed-offset candidates, unknown alternatives, coverage invalidation and bounded fair termination. Byte/BIL decoding and machine-width expression recognition are producer premises; five finite scenarios do not establish universal refinement. |
| [Loop-target closure](AriadneLoopTargetClosure.tla) | Private Rust `src/bap/target_resolution/loop_closure.rs`, native `loop_closure.ml`, target/composition validators | Added 2026-10-15: finite local-phase entrance, induction, dispatch-domain and epoch contract. Twenty-five scenarios and an independent concrete oracle exercise this component; accepted receipts supply the coverage premise through the interface below. No mechanically checked inter-model refinement is claimed. |
| [Guarded target composition](AriadneGuardedTargetResolution.tla) | Combined `src/input/materialize.rs`, BAP guard/target validators and native capture | C0 authority added 2026-10-14: fixed scope, source/candidate/final layering, shared epochs and paired receipts. The 2026-10-14 record retains 19 finite remote configurations and its runtime scope; the new loop component is qualified separately. Structural identities abstract concrete hash/codec validation. |
| [Core replay](../mbt/model/AriadneReplay.tla), [stateflow replay](../mbt/stage-e/model/MachineStateReplay.tla) and [cases](../mbt/stage-e/model/MachineStateCases.tla), [IR replay](../mbt/stage-e/model/LLVMIRReplay.tla) and [cases](../mbt/stage-e/model/LLVMIRCases.tla) | `mbt/`, `src/mbt/`, native replay observers | Current deterministic schedules and observation projections; retained corpus/source bindings are preserved. Replay remains finite conformance evidence. |

The address-wrap model was added and qualified separately on 2026-10-20:
its W0 record binds 140 independent oracle rows, 52 scenarios and the exact
typechecking/TLC tier. W1–W3 now have their separate recorded binding, pilot and
finite/native matrix qualification; W4 product/capture gates and W5 full
acceptance remain pending. Its exact two model files received fresh global typing in the later S3 suite; the W0 model/oracle tier remains separate. Retired ISA models and historical Lean research are outside this audit. Earlier source-bound records retain their hashes and qualification scope;
changing a model or its comments does not refresh those records.

The [synchronization record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync-20261011/report.json)
and [artifact manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync-20261011/evidence-manifest.json)
retain source hashes and bounded local checks: all 22 modules and 19
configurations parse; 13 selected frame traces and 22 scalar probes pass;
checker dispatch/failure tests use stub tools; default/core/property tests pass.
These historical checks are separate from the later finite remote S3 qualification below. Historical receipts are unchanged.

## Specification synchronization S3 qualification, 2026-10-20

The [S0–S3 ledger](../.agents/plans/specification-sync.md) and [sealed evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync/20261020/README.md) close the declared finite S3 suite on the exact lookup8 models. The historical 20261011 audit retains its 17 active/five replay counts; the new snapshot types 32 root modules, including the official standard module, pair auxiliaries and two current AddressWrap modules. There are 53 actual typecheck invocations, including repeated specialized checks and five replay types, 40 bounded calls, 24 TLC instances (19 original plus five prerequisites),six original scripts and eight audited core configurations.

The full 120 guarded Java invocations are 53 type +40 bounded +24 TLC +3version/identity calls. The bounded outcomes are30 `NoError` and 10 `ExecutionsTooShort`, all exit0. Each short scenario has a nonempty initial state and intended terminal Next, independently matched by its fresh TLC graph. Its last checked state precedes the unchanged requested maximum; no full-length execution or unbounded proof is inferred. Eight targeted FramePaths preflight checks and three final fold/range TLC controls are separate groups.

Canonical Memory authority remains algebraic. The shared runner deterministically generates a fresh solver copy outside the repository: literal finite operations agree on Values0..15, original 123 Facts/80 Transfers and all admitted chain prefixes. Exact equality of complete inverse records, six clauses and full Safety, operation closure, static/dynamic coverage and the original algebraic Safety TLC are prerequisites. The original IdealSafety/CandidateSafety plus all 20 fact-class/transfer-kind partitions retain their domains, Init/Next, invariant and length 1. This is a finite reduction of the checked model, with no outside-carrier replacement claim.

The official 6,500-byte `Apalache.tla` SHA `a9115b404e72c58fd085f81bc59cc918f8adac49feabfb57f8e285bc7ab5cfac` and unmodified license are adjacent normal sources. Ordinary TLC uses its pinned JAR and this source, not alternate TLC classes. DOMAIN, fold, range and inductive stop-domain compatibility changes preserve the modeled behavior; no action, bound or Safety conjunct was removed. Earlier failures remain uncredited. W0 gets fresh global typing only; its earlier model/oracle tier and W1–W5/runtime qualification remain separate. ISA, universal refinement and wider domains are excluded.


## Indirect-target qualification

Run `Specs/check-target-resolution.sh` with the pinned Apalache and TLC tools.
It typechecks `AriadneTargetResolution.tla` and explores the full, partial-table,
new-incoming, untrusted-memory and zero-budget configurations with one worker.
The [qualification record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json)
retains the five safety/fair-termination results and separate oracle, native,
replay and mutation evidence. These new checks do not refresh the older
specification-synchronization campaign or its pending remote clauses.

## Guarded target composition qualification

Run `Specs/check-guarded-target-resolution.sh` on the authorized remote WSL host
with the pinned Apalache and TLC launchers. The checker runs the independent
[composition oracle](../tests/bap/fixtures/composition/oracle.py), typechecks
[AriadneGuardedTargetResolution.tla](AriadneGuardedTargetResolution.tla), and
checks 19 finite scenarios for safety and fair termination. Cases cover complete
and partial reads, unavailable destination code, a late bypass/backedge,
completeness/barrier/transfer changes without new destinations, pending transfer
havoc, opaque calls, wrong immutable scope, bounded symbolic frontiers and budget exhaustion.

Once the candidate graph can be frozen, finite guard-work exhaustion may publish
paired partial receipts and a stopped final request; it never justifies normal
store effects. Failure to materialize a candidate graph still publishes no query.
A bounded reverse symbolic frontier quantifies over arbitrary register inputs
and every reverse-prefix context; it never becomes a root or entry point.
The infeasible-frontier scenario independently tests a universally empty branch
conjunction without a known table base; its changed-load negative case retains
unknown alternatives and every structural backedge. Ten width-8 oracle cases
require stable symbolic-load identity under the frozen-control-data premise;
address/index changes, unknown writes, opaque calls, unknown subjects or mutable
memory keep independent values. The empty-context receipt uses the explicit
`infeasible` frontier form with zero base and empty indices/entries; original
expressions and guards still require independent replay.

Structural records abstract cryptographic identities. The scope/source to
candidate seal to receipts to final-request ordering has no digest cycle;
model results do not qualify the concrete codecs or captured BIL/table reads.
The [frozen independent cases](../tests/bap/fixtures/composition/contract.json)
also exercise unsigned machine-width arithmetic and tampered identities without
calling the production Rust or native solver. Two independent width-8/16
conditional-write cases enumerate one decrement followed by its taken condition
and a later upper bound: correct indices are `{1,2,3}`; substituting the update
again into an already post-transfer condition incorrectly gives `{0,2,3}`.
This is a finite guard-normalization contract, not an instruction-step proof.
The [2026-10-14 source-bound qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guarded-target-resolution/20261014/README.md) records remote typechecking, all 19 finite model cases, Rust/native controls and 330 generated replay observations. Its candidate/discovery result is historical, including the then-incomplete ninth certificate. The [2026-10-15 loop qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) subsequently closes that certificate and the new loop dispatch through independently checked induction. The [canonical design](../docs/Ariadne/guarded-target-resolution-design.md) keeps both scopes and remaining guard/frame limits explicit.

## Loop-target closure component interface

The [canonical loop design](../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up)
extends the current resolver with a whole-dispatch induction receipt. The
[loop model](AriadneLoopTargetClosure.tla) defines the additional coverage
obligations; the existing target and composition models continue to abstract
an accepted coverage proof as a premise. Their transition systems are unchanged
by this extension. This is an explicit component contract, not a TLA+
`INSTANCE`, a proved refinement mapping or a mechanically checked composition
of the three models.

The interface is the following conditional judgment:

```text
original source and captured reads bound to query Q and candidate revision e
  + whole-dispatch receipt independently accepted at e
  + e still current when the paired request is sealed
  => the dispatch's incoming-coverage obligation is discharged in Q at e
```

The receipt is one alternative to existing prefix-tree coverage. The choice
applies to the entire dispatch obligation; it does not merge arbitrary reverse
prefixes. Retained path/table witnesses still require their ordinary replay.
Coverage of one dispatch does not establish coverage of another dispatch,
caller guard admission, an active call anchor or frame-path availability.

| Component obligation | Executable discharge | Target/composition premise supplied |
| --- | --- | --- |
| `EntranceHolds(revision)` | Independently enumerate region entrances and roots; replay each source base-reset corridor from arbitrary prior values; reject every uncovered bypass. | Every represented entrance at this dispatch satisfies the invariant. |
| `Preservation` | Replay original BIL and each typed edge predicate; check inclusion in the destination assertion. Fresh loads introduce arbitrary values, and flag relations retain their same-iteration definitions. | All finite iterations reaching the dispatch are covered; a repeated instruction address alone closes nothing. |
| `DispatchDomain` and complete edge inventory | Derive the bounded selector domain and captured relative-32 arithmetic; compare all internal, entrance, exit and table-successor edges with the current graph. | Target enumeration covers the dispatch domain without relying on its existing `complete` bit. |
| `EffectsSafe`, `MemoryPremise`, `ScopeBound` | Check original effects, capture contributors, frozen-control-data premise and immutable source/query binding. | The scalar/table proof applies only to the bound capture, source, activation and admitted premises. |
| `inspected`, `Readable`, `targets` | Validate every required table slot; retain known targets when a read or coverage obligation remains unresolved. | Existing target-read and candidate-retention clauses still apply; coverage alone cannot repair a missing table read. |
| `certificateRevision = revision` | Invalidate and replay after graph, source, entrance or completeness changes; seal paired evidence only on the current candidate epoch. | Existing stale-receipt and paired-epoch policies remain mandatory, including changes that add no destination. |
| `spent`, `Budget`, `Terminates` | Charge bounded proposal/replay work and return partial on exhaustion. | Analyzer termination and conservative partial publication; no claim that the analyzed loop terminates. |

In [the target model](AriadneTargetResolution.tla), `incomingCovered` abstracts
the accepted coverage premise; reads, memory trust and revision validation
remain separate requirements for `complete`. In
[the composition model](AriadneGuardedTargetResolution.tla), `covered` abstracts
the required coverage of its modeled dispatch. The production coordinator must
retain all other site/guard obligations and take their required conjunction;
it cannot set global coverage from one successful loop receipt. Both models
continue to retain targets while invalidating completeness after new evidence.

The concrete bridge is source reviewed and replayed in the
[Rust loop checker](../src/bap/target_resolution/loop_closure.rs),
[Rust target validator](../src/bap/target_resolution.rs),
[native loop checker](../native/bap-core/loop_closure.ml), and
[native composition admission](../native/bap-core/composition.ml).
Model/engine/profile identities bind the new contract. Legacy saved combined
reports select their separately frozen checker/model contract; these identities
must not authorize the new coverage fields.

Run `bash Specs/check-loop-target-closure.sh` on remote `windows-dev` WSL. It
executes the independent [concrete oracle](../tests/bap/fixtures/loop-closure/oracle.py),
typechecks the component and checks 25 finite scenarios for safety, expected
outcome and fair termination. The oracle's
[29 cases and four arithmetic controls](../tests/bap/fixtures/loop-closure/oracle-cases.json)
enumerate concrete four-bit scalar/flag transitions independently of production
matching and invariant synthesis. Separate 64-bit arithmetic controls distinguish
signed32 extension, which four-bit target arithmetic alone cannot distinguish.

The finite scope preserves the nine-node local phase, ten internal edges,
four exits and changing pointer/selector values. It erases full AMD64 widths
from the transition state, detailed BIL syntax, physical memory layout,
cryptographic encoding and unrestricted CFGs. Trusted lifting, exact source
transport, concrete budgets and those erased representation obligations still
need Rust/native controls and source-bound replay. Fresh qualification under
the [L0–L6 plan](../.agents/plans/completed/loop-aware-target-resolution.md) records those tiers
separately; none of them is a universal implementation or inter-model proof.

## Shared semantic types

`AriadneTypes.tla` is the shared alias catalogue for specification-level roles.
Machine aliases cover addresses, snapshots, locations, instruction and edge
kinds, byte sources, definition origins, abstract states and values, machine
statuses, and terminal outcomes. LLVM IR aliases cover artifacts, modules,
functions, blocks, instructions, values, value kinds, terminator kinds, and
callees. Analysis phases and obligation reasons are shared where their role is
representation-independent.

Every semantic string position uses a meaningful `$alias` in Snowcat
annotations. `Str` remains only as the underlying representation in alias
declarations. These aliases are documentary and transparent, not nominal
newtypes; set-membership contracts still constrain their permitted values.

## Shared machine contract

`AriadneMachineCommon.tla` owns only knowledge that has the same meaning in CFG
recovery and post-recovery state propagation:

- local machine edge-kind vocabulary;
- the snapshot-scoped, finite, nonempty, nonnegative VA contract;
- snapshot-plus-VA external identity;
- the typed structural edge constructor; and
- well-formed normalized `uses`, `mustDefs`, and `mayDefs` sets.

The module has no constants, variables, phases, transitions, obligations, or
analysis policy. `Ariadne.tla` retains discovery, byte provenance, reaching
definitions, and slicing. `AriadneMachineState.tla` retains abstract valuations,
semantic transitions, fixed-point state propagation, and edge-feasibility
classification. Compatibility aliases in the consumers preserve their existing
public operator names while delegating definitions to the common module.

## Native LLVM IR model

The LLVM IR model consumes one normalized, verifier-accepted function from one
artifact. It does not lift machine code, reconstruct compiler IR, or assert that
an IR instruction corresponds to a machine address. Its identity is the tuple
of `ArtifactId`, `ModuleId`, `FunctionId`, block, and instruction.

The representation has two node domains:

- Basic blocks form the authoritative CFG. `ControlGraph` is derived exactly
  from each terminator's typed successors.
- LLVM instructions form the dependency and slice graph. Direct SSA uses name
  their unique instruction producers; argument, constant, global, and external
  values remain non-instruction inputs.

Phi inputs retain both predecessor block and incoming value. The contract
requires exactly one incoming record per CFG predecessor and keeps all incoming
values for conservative slicing. `MemoryPreds` is a trusted conservative input
for dependencies not represented by ordinary SSA def-use. Passing this model
does not validate an alias analysis or LLVM opcode semantics.

Calls occupy a separate `CallGraph`; they do not become intraprocedural block
CFG edges. Incomplete call targets produce a `call-targets` obligation. Adapter
obligations also preserve unsupported instructions, incomplete semantics,
unknown memory aliases, and unmodeled exceptional, system, or concurrent
behavior. A completed slice may therefore remain partial.

The LLVM IR state machine starts with the requested instruction seeds, adds SSA
and memory producers until dependency closure, and then reaches `done`. Its
properties check normalized input types, exact terminator-derived control
edges, phi/CFG correspondence, valid dependency producers, slice closure, and
fair termination. Interprocedural call/return matching, path feasibility, and
machine/IR correlation remain outside this model.

## Abstract machine-state model

`AriadneMachineState.tla` consumes the frozen decoded-node set and `LocalGraph`
produced by machine recovery. It does not discover instructions, change edges,
or follow `call` edges. A returning call summary is represented by the existing
local `summary` edge and an adapter-supplied semantic transition.

The model uses a finite collecting semantics. `statesAt[a]` contains abstract
state identities that may hold before instruction `a`. Each identity has a
`Valuation` mapping normalized register, flag, or memory locations to nonempty
finite value sets, plus a status. Separate identities can preserve correlations
that a single pointwise join would lose.

`StateSteps` is a trusted nondeterministic relation from a running before-state
through one instruction and one existing structural edge to a running
after-state. `TerminalTransitions` records faults, returns, and stops. Every
transition must preserve locations outside the instruction's `MayDefs`; the
model checks this frame property but does not prove the supplied transitions
faithfully implement an ISA. The relation is supplied under its adapter contract;
the retired x86-64 instruction-rule bridge is archived with the removed ISA models.

Entry states are attached only to declared entry points. Propagation repeatedly
adds after-states along local structural edges until a fixed point. The graph is
never filtered. Instead, the final result partitions structural edges into:

- `FeasibleEdges`, witnessed by a reached semantic transition;
- `ProvablyInfeasibleEdges`, absent at a reached site whose semantics adapter
  supplied a trusted completeness certificate; and
- `UnknownFeasibilityEdges`, where reachability or semantic completeness is
  insufficient for either conclusion.

Missing semantic completeness produces an `incomplete-semantics` obligation.
Additional adapter obligations preserve unknown memory, unmodeled exceptions,
system calls, and concurrency. A crash-time state may seed its exact captured
instruction; the model does not authorize treating it as an earlier state or
using it to rewrite the structural CFG.

## Scope and abstraction boundary

The core `Ariadne.tla` model specifies instruction-level CFG recovery, forward may-reaching
definitions, and a backward data slice over a finite analysis request. It models
the analyzer's execution, not execution of the analyzed program.

An address is the virtual address (VA) of a candidate instruction start in one
fixed address-space snapshot, identified by the nonempty `SnapshotId`. VAs are
nonnegative integers; architecture-specific address widths remain an adapter
constraint.
Apalache annotations represent addresses as the shared `$address` alias backed
by `Int`, and location identifiers as `Str`; record fields and function/set
element types are explicitly declared. The alias documents intent but is not a
nominal type, so the nonnegative-VA contract remains semantically necessary.
`Insn` is a trusted semantic description supplied by a decoder/semantics adapter.
`Decodable` identifies successful decodes. Thus the model verifies what the
engine does with decoded instructions; it does not verify x86 decoding, LLVM,
instruction semantics, PE/minidump parsing, or PDB matching.

The preserved information is instruction identity, typed local and call
edges, byte provenance, reads, may-writes, must-writes, and
explicit unresolved obligations. Concrete bytes, instruction widths, numeric
register values, flag equations, memory contents, thread scheduling, and timing
are abstracted away by the core model. Supplied abstract stateflow and separate
question-level assessments retain their own evidence and semantic contracts;
they do not change those recovery inputs.

The graph has one node per decoded instruction. Edges may also reference
unavailable/invalid local targets or callees outside local discovery. Local
decode failures produce obligations; an unvisited callee alone does not.
Coalescing nodes into basic blocks is a presentation/refinement step, not
modeled here.

## Input contract

| Input | Meaning |
| --- | --- |
| `SnapshotId` | Opaque identity of the one immutable address-space snapshot shared by all inputs |
| `Addresses` | Finite candidate instruction VAs, including every represented target and continuation, even when its bytes are unavailable |
| `EntryPoints` | Nonempty set of roots to analyze; successor discovery does not infer predecessors of arbitrary crash addresses |
| `SliceSeeds` | Instructions whose input dependencies should be traced |
| `InputKind` | `binary` or `dump` |
| `Captured` | Starts with a complete captured instruction-byte span |
| `FileBacked` | Starts with a complete byte span supplied by the binary provider |
| `TrustedFallback` | File-backed starts certified suitable for use when dump bytes are absent |
| `Decodable` | Starts whose selected bytes decode successfully |
| `Insn` | Instruction kind, continuation, known targets, target-completeness certificate, uses, must-defs, and may-defs |
| `Locations` | Finite normalized register/flag/memory locations for this request |

### Virtual addresses and storage mapping

`EntryPoints` contains VAs at which discovery begins, not coordinate origins.
Every address-bearing field uses this same VA domain, including slice seeds,
instruction continuations/targets, edges, provenance keys, and definition sites.
`AddressSpaceContract` requires a nonempty snapshot identity and nonnegative
VAs. It appears both in `ASSUME` and in `TypeOK`, so fixture safety checks
exercise it even when instantiated-module assumptions are not enforced by TLC.
No implicit rebasing occurs. `AddressIdentity(a)` exposes the pair
`[snapshot |-> SnapshotId, va |-> a]` for identifying addresses across requests.
The adapter must assign distinct identities to distinct address-space snapshots;
a matching VA alone does not identify code across processes or capture times.

The provider contract is `resolve(snapshot, VA, length) -> bytes + provenance`
or unavailability. A dump provider locates a captured virtual-memory region;
a binary provider uses the selected module load base and section/segment layout
to locate file bytes. `VA - loadBase` is a module-relative offset, not generally
a file offset, and some virtual spans have no file backing. Standalone binaries
require a chosen virtual load layout. Compact internal node IDs are permitted
in an implementation only with a mapping back to these semantic VAs.

The model consumes the provider's whole-instruction availability and semantic
summaries. It does not implement or verify region tables, storage offsets,
byte lengths, relocation processing, or snapshot-identity uniqueness. All such
inputs must describe the same immutable snapshot. Successors remain explicit;
integer ordering or adjacency does not imply a control-flow edge.

For binary input, file bytes are used. For dump input, captured bytes take
precedence; file fallback requires `TrustedFallback`. File availability alone
does not authorize fallback. Certification must account for matching image
identity, VA mapping, relocations, and possible runtime modifications. A
captured decode failure does not silently trigger file substitution.

Availability is abstracted at the whole-instruction-span level. Mixed-source
spans and overlapping instruction streams need a richer provider refinement.
JIT code can be represented through captured bytes without file backing.
Unknown destinations outside the finite address universe must remain unresolved;
they must not be silently discarded with `complete = TRUE`.

`Locations` must normalize architectural aliasing, such as EAX/RAX overlap, and
conservatively abstract memory aliases. `uses` must include dependencies needed
for the requested slice, including address operands. `mayDefs` includes every
possibly written location; only `mustDefs` kills prior definitions. The latter
must be a subset of the former. Inadequate decoder or alias summaries invalidate
any claimed semantic soundness even if TLC passes.

## Control-flow policy

| Instruction kind | Unified graph effect |
| --- | --- |
| Ordinary | One `next` edge |
| Conditional | Both `taken` and `fallthrough` edges |
| Direct jump | One `jump` edge |
| Indirect jump | Every supplied target, plus an obligation unless the target set is certified complete |
| Call | A `call` edge to each supplied callee target and a potentially returning `summary` edge to the continuation |
| Return / stop | Exit from the current analysis scope |

All edges live in the single mutable `edges` set. `LocalEdgeKinds` is an explicit
allowlist; `EdgeKinds` adds `call`. `LocalGraph` and `CallGraph` are filtered views,
not separately stored state. `InstructionEdges(a)` combines the local and call
edges supplied by an instruction; `LocalSuccessors(a)` filters that result before
queuing addresses. `Preds(a)` consults only `LocalGraph`.

For a call at A to F with continuation B:

```text
A --call----> F
A --summary-> B
```

| Consumer | Local edges, including `summary` | `call` edges |
| --- | --- | --- |
| Graph display/export | Included | Included |
| Local recovery worklist | Follow destination | Do not follow |
| Reaching definitions / backward data slice | Follow local data-flow equations | Do not transmit definitions |

Calls are opaque summaries. Callee destinations are not traversed automatically
and do not receive definitions across call edges, even if independently decoded
through another root or local path. An unknown call can use and
may-write all modeled locations with no must-writes. A precise summary may
narrow that effect only with evidence. A summary edge at a call expresses a
possibility, not a guarantee that the callee returns. An interprocedural model
would need call/return matching and a context policy.

This is a structural CFG: no edge is removed using crash-time registers. Path
feasibility, implicit exceptions, interrupts, unwind edges, nonlocal jumps,
concurrency, self-modifying code, and recorded execution history are outside this
model. `return` and `stop` are scope exits, not missing-target obligations.

## State transitions

1. `Init` queues the entry points and initializes empty results.
2. `Visit(a)` nondeterministically processes a queued address once. Successful
   decoding records provenance, local and call edges, and unresolved target
   obligations. Only local successors enter the worklist. Failure records
   `unavailable` or `decode-failed`.
3. `FinishRecovery` freezes the graph once the worklist is empty.
4. `Propagate(a)` adds reaching definitions until the data-flow fixed point.
5. `FinishDataflow` initializes the slice with decoded seeds.
6. `ExpandSlice` follows instruction definitions of locations used by slice
   members until closure; `FinishSlice` marks the request done.

For each decoded instruction `a`, reaching definitions represent values before
that instruction. The transfer equations are:

```text
OUT(a) = (IN(a) minus definitions of mustDefs(a)) union GEN(mayDefs(a))
IN(a)  = entry definitions, if a is a root
         union OUT(p) for every decoded local predecessor p
```

The implementation model starts at empty sets and applies monotone updates,
computing the least fixed point over the recovered graph. Entry definitions are
tagged separately from instruction definitions. They describe unknown incoming
values and remain available in reaching sets, but do not become slice nodes.

The slice is an instruction-level may-data-dependency closure. It includes all
uses of each included instruction, so it can overapproximate dependencies of a
particular output operand. It does not include control dependencies and is not
a path-feasibility proof. Partial graphs yield results relative to recovered
edges; an unresolved predecessor path can introduce additional definitions.

## Properties

| Property | Checked claim |
| --- | --- |
| `TypeOK` | The address-space contract holds (nonempty snapshot identity, nonnegative VAs), and every state component remains in its declared domain |
| `RecoveryInvariant` | Local-only worklist bookkeeping, exact unified edges/obligations, successful decodes, and byte provenance stay consistent |
| `DefinitionInvariant` | Definitions have valid origins and propagation never exceeds the current transfer equation |
| `ResultInvariant` | Slicing starts only at the data-flow fixed point, includes decoded seeds, and finishes closed under data dependencies |
| `FixtureResult` | Each concrete scenario has the independently specified final decoded set, slice, and obligations |
| `CallPolicy` (call fixture) | Call edges are visible, an independently analyzed callee receives no caller definitions, and a callee reachable only by call stays unvisited |
| `Terminates` | Every weakly fair behavior eventually reaches `done` |

Termination follows from the finite address/definition domains: each visit
consumes a previously unvisited address, each propagation strictly grows a
finite definition set, each slice expansion strictly grows a finite set, and
phase changes move forward. `WF_vars(Next)` prevents infinite stuttering while
work remains. Once done, stuttering is allowed.

`ScopeClosed` means done with no outstanding recovery obligations **relative to
this input contract and control-flow policy**. It is not proof that every real
execution path has been recovered. `MissingSliceSeeds` separately reports seeds
that were not decoded, including seeds outside the reachable region; closed
recovery alone does not establish that the requested slice was available.

## Model checking

### Apalache

All TLA+ modules must remain Apalache-compatible. The check script discovers
and typechecks every `Specs/*.tla` file. Each new executable scenario must also
be registered in the script with its constant initialization, `Init`/`Next`,
safety invariant, and a practical transition bound. Shared parameterized
modules are exercised through those concrete scenarios.

Compatibility here means typechecking and bounded safety checking through
`Init`/`Next`. The fair temporal `Spec` and `Terminates` remain the TLC interface;
a passing Apalache safety run does not establish fair termination.

The modules include Snowcat type annotations. `AriadneExample.tla` exposes
`Init`, `Next`, `Safety`, and four constant initializers (`BinaryConstants`,
`DumpConstants`, `LoopConstants`, and `ClosedConstants`). `Safety` conjoins the
same five invariants used by TLC. Type invariants check record fields and
function domains directly, avoiding large Cartesian products in SMT encoding.

Run the compatibility checks from the repository root:

```sh
bash Specs/check-apalache.sh
```

The script discovers every remaining `Specs/*.tla` module, checks each larger machine scenario through
six transitions, checks `AriadnePipeline.tla` through eight transitions, and
checks `AriadneCalls.tla` through the same configurable bound (six by default).
It checks `AriadneLLVMIRExample.tla` through eight transitions and
`AriadneMachineStateExample.tla` through six. It also registers input closure and
budget scenarios through six, effects and scalar/question decisions through
one, and six typed-edge frame-path scenarios through thirty-two. It generates the pinned Memory solver/control copies in that fresh temporary directory, requires the five ordinary-TLC equality/closure/coverage prerequisites, and checks canonical IdealSafety/CandidateSafety plus all 20 exact pair partitions. It writes all artifacts there and prints the path. Canonical algebraic Memory sources are never overwritten. Set `APALACHE_MC` to select an
executable. To change the bound for the larger scenarios or select one scenario:

```sh
bash Specs/check-apalache.sh 10 Loop
```

Equivalent individual commands, run from `Specs/`:

```sh
apalache-mc --out-dir=/tmp/ariadne-apalache-types typecheck Ariadne.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-binary check \
  --cinit=BinaryConstants --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneExample.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-pipeline check \
  --init=Init --next=Next --inv=Safety \
  --length=8 --no-deadlock AriadnePipeline.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-calls check \
  --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneCalls.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-llvmir check \
  --init=Init --next=Next --inv=Safety \
  --length=8 --no-deadlock AriadneLLVMIRExample.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-machine-state check \
  --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneMachineStateExample.tla
```

The six-step runs primarily cover recovery, not completion of the larger
scenarios. The pipeline fixture uses two instructions: a definition followed by
a use. It exercises recovery, reaching-definition propagation, backward slice
expansion, and completion within eight steps. `NotDone` is a deliberately false
invariant in that fixture; checking it at bound eight provides a reachability
witness ending in `done`, rather than a vacuous completion-property check.

The call fixture has a call at 1, continuation 2 and two known callee targets,
3 and 4. Both callees have readable, decodable instructions, but only 3 is an
independent root. The fixture checks that all three edges are visible, 4 stays
unvisited, and 3 receives only its own entry definitions. The continuation 2
must receive both the caller's incoming and possible new definitions of `x`.
This tests the edge policy even when a callee already exists as a decoded node.
Its six-step Apalache run covers recovery and early propagation, not completion;
TLC checks its complete finite state space. Exploratory Apalache runs at bound
twelve were stopped after prolonged checks at the data-flow boundary, under
both the default strategy and `search.invariant.mode=after`. Those deeper runs
are not recorded as passes or as discovered model errors.

```sh
# Expected result: a counterexample to NotDone, ending with phase = "done".
apalache-mc --out-dir=/tmp/ariadne-apalache-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=8 --no-deadlock AriadnePipeline.tla

# Expected result: a counterexample to NotDone with the exact LLVM IR slice.
apalache-mc --out-dir=/tmp/ariadne-apalache-llvmir-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=5 --no-deadlock AriadneLLVMIRExample.tla

# Expected result: a counterexample with the exact final machine-state map.
apalache-mc --out-dir=/tmp/ariadne-apalache-machine-state-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=5 --no-deadlock AriadneMachineStateExample.tla
```

These commands check **bounded safety**, not fair termination. They deliberately
use `Init`/`Next` instead of the fair temporal `Spec`; `--no-deadlock` permits the
terminal state. The original TLC configurations retain `Spec` and `Terminates`
for exhaustive finite-instance liveness checking. Increasing the Apalache bound
may substantially increase SMT cost.

Tool conventions: [Apalache type annotations](https://apalache-mc.org/docs/HOWTOs/howto-write-type-annotations.html)
and [bounded checking](https://apalache-mc.org/docs/apalache/running.html).

Validated on 2026-09-17 with Apalache **0.57.0**, build `635865a`:

| Instance / check | Bound | Result |
| --- | ---: | --- |
| Binary / `Safety` | 6 | No error |
| Dump / `Safety` | 6 | No error |
| Loop / `Safety` | 6 | No error |
| Closed / `Safety` | 6 | No error |
| Calls / `Safety` (includes `CallPolicy`) | 6 | No error |
| Pipeline / `Safety` | 8 | No error |
| Pipeline / `NotDone` reachability witness | 8 | Expected counterexample; final phase `done`, slice `{1, 2}` (original fixture addresses) |

All four modules passed typechecking, including the instantiated modules in
the bounded checks. The `NotDone` check intentionally exits with code 12;
the safety checks exit with code 0. The TLC results below were rechecked after
the unified call-edge change; all five original scenarios retain their state counts.

### TLC

Current additional entry points are:

| Command | Finite scenarios and limits |
| --- | --- |
| `bash Specs/check-input.sh` | `Input.cfg` and `InputLimit.cfg`: byte agreement, mapping, local closure and preparation-budget termination. |
| `bash Specs/check-effects.sh` | `Effects.cfg`: conservative normalized effects, register cells, memory weak writes and opaque effects. |
| `bash Specs/check-zero-base-offset.sh` | `ZeroBaseOffset.cfg`: admitted/coherent result decisions and evidence/claim budgets. |
| `bash Specs/check-memory-refinement.sh` | `MemoryRefinement.cfg`: mathematical and represented scalar preimages, retained facts at boundaries and candidate preservation; four-bit/two-operation representatives. |
| `bash Specs/check-frame-paths.sh` | Six `FramePaths*.cfg` scenarios: typed parallel paths/loops, acyclic exhaustion, strict NP=1, zero scan/visit budgets and external partial stops; invariants and fair termination. |

The source audit and local probes above do not claim those revised remote gates
have run. The older results below belong to their stated source revisions.

`AriadneExample.tla` instantiates the engine with seven candidate addresses and
two abstract locations. Its configurations exercise:

| Configuration | Coverage |
| --- | --- |
| `Binary.cfg` | Conditional diamond, partial indirect targets, missing bytes, decode failure, unknown call, conservative call writes |
| `Dump.cfg` | Same request with captured precedence, trusted fallback, an available but untrusted file span, and a missing slice seed |
| `Loop.cfg` | Two definitions joining, a back edge, a must-write kill, fixed-point convergence, and data-slice closure |
| `Closed.cfg` | Certified indirect targets, visible call/summary edges, unvisited callee, and obligation-free completion using dump/file bytes |

`Pipeline.cfg` checks the additional two-instruction `AriadnePipeline.tla`
instance, including termination and the exact final reaching definitions/slice.
Its sparse VAs 4096 and 4100 also check that addresses are preserved as supplied,
with an explicit successor rather than an implicit adjacent node index.
`Calls.cfg` checks `AriadneCalls.tla`, including the independent `CallPolicy`
assertions and exact final unified graph and data-flow results.
`LLVMIR.cfg` checks `AriadneLLVMIRExample.tla`: an exact four-block CFG, a phi
join, conservative store/call memory predecessors, a separate call edge, an
incomplete-call obligation, artifact-scoped identity, final dependency slice,
and fair termination.
`MachineState.cfg` checks `AriadneMachineStateExample.tla`: propagation of a
finite entry state through a constant and flag update, preservation of both
structural branch edges, separate feasible/infeasible classification, the
unreachable fallthrough node, the reached return outcome, and fair termination.

Run from `Specs/` with Java and the TLA+ tools available:

```sh
tlc -workers 2 -metadir /tmp/ariadne-tlc-binary -config Binary.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-dump -config Dump.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-loop -config Loop.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-closed -config Closed.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-pipeline -config Pipeline.cfg AriadnePipeline.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-calls -config Calls.cfg AriadneCalls.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-llvmir -config LLVMIR.cfg AriadneLLVMIRExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-machine-state -config MachineState.cfg AriadneMachineStateExample.tla
```

If no `tlc` launcher is installed, substitute `java -cp /path/to/tla2tools.jar
tlc2.TLC`. Each configuration checks the engine invariants, its fixture result,
and `Terminates`. The call fixture additionally checks `CallPolicy`; the smaller
fixtures conjoin their safety checks in `Safety`.
Deadlock checking is disabled because `done` intentionally has no nonstuttering
successor; the termination property still detects premature permanent stalls.
Exhaustive checks of these finite instances are not a proof for every instance
or a validation of the external semantic adapters.

Validation on 2026-09-17 with TLC 2.19 (revision `5a47802`), Java 17,
and two workers completed with no errors:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `Binary.cfg` | 149 | 74 | 17 |
| `Dump.cfg` | 86 | 46 | 16 |
| `Loop.cfg` | 91 | 51 | 15 |
| `Closed.cfg` | 104 | 56 | 15 |
| `Pipeline.cfg` | 11 | 10 | 9 |
| `Calls.cfg` | 27 | 19 | 11 |

The call-edge regression was also checked against two deliberately broken
temporary copies of the model. Queuing all edge destinations (including calls)
and letting `Preds` inspect all edges each caused TLC to reject `Safety`.
The repository model retains the local-edge filters in both operations.

### Virtual-address contract validation (2026-09-17)

After adding `SnapshotId`, `AddressSpaceContract`, and the sparse-VA pipeline,
TLC 2026.03.24.222644 (revision `1476e7f`) passed all six configurations,
including safety and fair termination, with the same state counts listed above.
Two temporary copies of the pipeline were also checked: replacing VA 4096 with
-1 (and importing `Integers` to express it), and replacing `pipeline-snapshot`
with the empty string. Both violated `Safety` in the initial state (exit 12).
This checks contract rejection through `TypeOK`, independently of how TLC
handles assumptions inside instantiated modules.

Apalache 0.61.0 (build `831d473`) passed typechecking of all four final modules
and bounded `Safety` checks for Binary, Dump, Loop, Closed, and Calls through
six transitions, and Pipeline through eight. Binary was rerun after adding
the contract to `TypeOK`; the other bounded runs used that final contract.
The updated pipeline's `NotDone` check at bound eight produced the expected
counterexample (exit 12), ending in `done` with slice `{4096, 4100}`.
These checks do not validate a byte provider or uniqueness of snapshot IDs.

### Native LLVM IR validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked `AriadneLLVMIR.tla` and
`AriadneLLVMIRExample.tla`. Its bounded `Safety` check through eight transitions
reported no error; the fixture has no executions as long as the supplied bound
because it reaches `done` after five transitions.

The full `check-apalache.sh 6 all` run also typechecked all six modules and
reported no safety error for Binary, Dump, Loop, Closed, and Calls through six
transitions or for Pipeline and LLVM IR through eight.

The LLVM IR `NotDone` reachability check at bound five produced the expected
counterexample (exit 12). Its final state is `done` with the exact nine-node
`ExpectedSlice`, demonstrating that the fixture's completion assertion is
exercised rather than vacuous.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers
exhaustively checked `LLVMIR.cfg`, including safety and fair termination:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `LLVMIR.cfg` | 5 | 5 | 5 |

The seven configurations present at that point passed together in the same
environment. The six existing machine fixtures retained their generated and
distinct state counts.

### Abstract machine-state validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked `AriadneMachineState.tla` and
`AriadneMachineStateExample.tla`. Its bounded `Safety` check through six
transitions reported no error and reached the terminal analysis state before
the supplied bound.

The final `check-apalache.sh 6 all` run typechecked all eight modules and
reported no safety error for Binary, Dump, Loop, Closed, and Calls through six
transitions, Pipeline and LLVM IR through eight, or machine state through six.

The `NotDone` reachability check at bound five produced the expected
counterexample (exit 12). Its final state is `done` with `statesAt` equal to
`ExpectedStates`, demonstrating that the final edge classifications are
exercised rather than vacuous.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers
exhaustively checked `MachineState.cfg`, including safety and fair termination:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `MachineState.cfg` | 5 | 5 | 5 |

The full eight-configuration TLC suite passed in the same environment. The
seven prior configurations retained their generated and distinct state counts.

### Shared machine contract extraction validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked
`AriadneMachineCommon.tla`, `Ariadne.tla`, and
`AriadneMachineStateExample.tla`. Bounded `Safety` checks reported no error for
the Binary recovery fixture and the machine-state fixture through six
transitions.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers passed
all eight configurations after the extraction. Generated and distinct state
counts remained unchanged, providing a behavioral-preservation check for both
common-module consumers and the unaffected LLVM IR model.

### Semantic type-alias validation (2026-09-19)

`AriadneTypes.tla` declares Apalache lower-camel aliases for every semantic
`Str` role and `address = Int`. Machine-model annotations use `$address` for
semantic VAs, address-keyed functions, graph endpoints, definition sites, and
obligations. Unrelated numeric quantities remain annotated as `Int`.

Apalache 0.61.0 typechecked all ten modules with the aliases, with no raw `Str`
remaining in `@type` annotations. Bounded `Safety` checks reported no error for
Binary recovery and machine-state propagation through six transitions, or for
LLVM IR through eight. All eight TLC configurations passed with unchanged state
counts; as expected, Snowcat aliases change annotations rather than untyped
TLA+ behavior.

### Retired ISA validation archive

The removed instruction-semantics models and their 2026-09-19 validation
summary remain in the [archived formal-model guide](https://github.com/NzSN/Ariadne/blob/01ae404e8c8556966e219118945082ff8e213f7e/Specs/README.md#x86-64-instruction-semantics-validation-2026-09-19).
Those component results are historical and do not qualify the active analyzer.

## Predicate admission model

[AriadnePredicateAdmission.tla](AriadnePredicateAdmission.tla) is the analysis-level
authority for proof-gated MOVAPS load/store normal admission. It models residue joins and
transfers, qualified entry premises, candidate-graph closure, invalidation after
new incoming evidence, receipt replay and publication. Version 2 additionally
distinguishes certified normal terminals from unsupported Stops, while keeping
general exception graphs and full ISA execution outside the model.

The [original guard design](../docs/Ariadne/justified-branch-pruning-design.md)
and [completed G0–G4 plan](../.agents/plans/completed/justified-branch-pruning.md) retain
the store-only v1 scope. Its exact model/source identities are preserved in
the [legacy contract manifest](../tests/bap/fixtures/caller-coverage/legacy-manifest.json).
The [caller coverage design](../docs/Ariadne/caller-semantic-coverage-design.md)
and [S0–S6 plan](../.agents/plans/caller-semantic-coverage.md) own v2 implementation and
source-bound qualification. Editing this active model does not refresh the
frozen v1 result or authorize its profile to admit new fields.

The new scope is `local-normal-completion/v1`. A certified terminal has no
normal successor; all-location uses/may-defs and empty must-defs preserve opaque
exception effects. The model retains an exceptional-exit annotation and leaves
handler/debugger resumption outside the scope. The `TerminalHandlerResume`
scenario explicitly permits every handler-supplied RSP residue while normal
coverage can still be closed. This is not an assumption that handlers never
resume, nor a whole-machine coverage claim.

`normalTerminals` and unmatched Stop barriers are distinct. Invalid byte/span,
AST, source-rule, scope, successor, effect or generation claims prevent normal
admission. Late terminal completeness/edge/evidence changes advance the epoch,
invalidate receipts and restore conservative barriers. Pending guard relations
commit neither a store nor a vector load; only a current, closed aligned verdict
can select the operation-specific normal effect. Unknown, misaligned,
unreached and budget-stopped results retain their stops.

Run `bash Specs/check-predicate-admission.sh` on the authorized remote WSL host.
It verifies frozen legacy file identities, runs both independent oracles,
typechecks v2 and checks 58 `PredicateAdmission*.cfg` scenarios for safety,
expected outcomes and fair termination. The unchanged
[v1 oracle](../tests/bap/fixtures/guards/oracle.py) retains its 56 graph/premise
cases, three closure histories, 33 receipt controls and 720 numeric transfer
checks. The new [caller oracle](../tests/bap/fixtures/caller-coverage/oracle.py)
and [71 declared cases](../tests/bap/fixtures/caller-coverage/oracle-cases.json)
use a generated ModR/M/SIB extent grammar, concrete 128/256-bit evaluation of
the captured MOVAPS source, finite product-graph traversal and synthetic receipt
tampering. Complete/truncated UD1 grammar productions are also checked; the
actual pinned BAP three-byte versus five-byte discrepancy remains explicit.

Exact bytes/BIL, decoder observations, extent recognition and cryptographic
bindings remain input-check obligations erased by the finite TLA+ abstraction.
The new oracle tests selected concrete representation cases without importing
production matchers; its receipts are not a runtime wire-compatibility test.
Neither tier proves the lifter, a universal Rust refinement or mechanically
checked coupling to the core/target/loop models. Those model files remain
unchanged; native replay and the original-dump gate qualify their concrete
integration separately.

## Caller completion conformance, 2026-10-19

The [S6 evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/caller-semantic-coverage/20261019/README.md)
checks existing core/admission models against compact completed results. The
[completion contract](../docs/Ariadne/caller-semantic-coverage-design.md#s6-bounded-completion-continuation-2026-10-19)
changes storage and completion scheduling. `Ariadne.tla` retains the same
may-reaching equations and enabled propagation actions. RPO selects an enabled
action; ordinary least-VA replay remains unchanged. Membership words project
to the same finite mathematical sets.

Eight selected typechecks, six core and 107 mechanism configurations, 330 native
generated observations, 2,048 directed-graph completion comparisons and 29 unique
compiled mutations pass their declared scope. Exact original requests/full states
and every reaching row have independent checks. This does not complete audited
model S3 or provide a universal representation/refinement proof. Resource limits
and wire validation have separate concrete tests; no ISA semantics is added.

## Frame-path F4 finite qualification, 2026-10-20

The [frame-path contract](../docs/Ariadne/investigation-design.md#f4-post-s6-qualification)
and [execution ledger](../.agents/plans/frame-path-enumeration.md) have
[source-bound evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-paths/20261020/README.md) for
six finite model configurations and typechecking. The source2 capsule contains 1,070
files and has SHA-256
`ed7b76ef6b9ac6f32e66c570d0234780861afe123fe0786916b33d7eba1bb84d`.
The model retains strict NP, typed-edge DFS, explicit resource stops and
conservative writer preservation. Its external resource-stop abstraction does
not prove concrete payload sizing, capture/hash validation or process RSS.

Independent concrete controls cover explicit producer graph admission,
consumer-selected decoder caps, reports-only proof-feature refusal, native/Rust
path equality and original-capture helper-free replay. The final original
32-node/two-visit listing remains partial; the failed initial 512-node policy is
retained separately. Compiled mutations: `6 compiled mutations rejected after 6 passing controls`.
Archive SHA-256: `42feba66c6445de674ddaf0aa7f3ec3d63ca845a5c117c45d02c9e8352eb40ff`. This finite F4 result does not close
specification-sync S3, general unwind/ISA semantics or universal refinement.
