# Ariadne documentation network

Designs are organized by feature: one canonical document owns each design's
decisions and contracts. Implementation stages live in [Plans](../.agents/plans/README.md);
source-review and validation summaries stay with their owning feature, while
raw evidence retains its original identities and scope. Use the
[design index](Ariadne/README.md#canonical-designs) to find the canonical owner.

Implementation plans now live under `.agents/plans/`. Immutable evidence and
source capsules may retain the former `Plans/` paths from their recorded
checkout; use the [current plan index](../.agents/plans/README.md) for navigation.

Each document's **Context and follow-up** section explains its status,
motivating problem, contribution, direct next reading and unresolved limits.
Readers can follow the subject without returning to this map.

The [terminology convention](terminology.md) defines shared words and required
qualifiers across active contracts, reports, plans and historical evidence.

## Main problem-to-delivery paths

```mermaid
flowchart TD
    Goal[Snapshot crash investigation] --> Input[Captured input and entry evidence]
    Input --> BAP[BAP semantics and native analysis]
    BAP --> Explain[Fault-address investigation]
    Explain --> Numeric[Separate fault-time numeric questions]
    Explain --> Memory[Proposed memory provenance refinement]
    BAP --> Reports[Rendering and minidump reports]
    BAP --> Replay[Typed replay and separate stateflow / IR contracts]
    Explain --> Performance[Investigation performance]
    Performance --> Workload[Workload measurement contract]
    BAP --> Assurance[Trust and proof boundaries]
    Numeric --> Evidence[Source-bound qualification records]
    Replay --> Evidence
    Workload --> Evidence
```

| Question | Canonical design or contract | Implementation and evidence | Remaining boundary |
| --- | --- | --- | --- |
| How do captured instructions yield possible origins? | [Analysis model](../Specs/README.md), [BAP design](Ariadne/bap-analysis-core-design.md) | [Rust reference](implementation.md), [native qualification](Ariadne/bap-analysis-core-design.md#native-qualification) | [Universal refinement and trusted lifting](Ariadne/semantic-assurance.md). |
| Which bytes and instruction entries are justified? | [File-reader design](Ariadne/file-reader-design.md) | [Input guide](Ariadne/file-reader-design.md#public-interface), [selected capture](Ariadne/file-reader-design.md#windows-replacement-capture-and-bounded-query) | Capture-only production reader; further file formats remain deferred. |
| Can captured data resolve an indirect jump? | [Indirect-target resolution](Ariadne/indirect-target-resolution.md) | [R0–R6 plan](../.agents/plans/indirect-target-resolution.md), [captured table inspection](Ariadne/indirect-target-resolution.md#motivating-windows-capture) | Implemented finite profile with source-bound qualification; incoming-state coverage and captured-memory premises remain explicit. |
| Can a pointer-changing loop have complete captured-table targets? | [Guarded target composition and loop-closure design](Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up) | [C0–C6 delivery ledger](../.agents/plans/completed/guarded-target-resolution.md), [L0–L6 loop-aware plan](../.agents/plans/completed/loop-aware-target-resolution.md) | Composition and local-region induction are qualified within their captured-table scope; DA09/DADD and all nine original certificates close. Full frame paths remain separate. |
| How are instruction dependencies projected? | [BAP projection](Ariadne/bap-analysis-core-design.md#projection) | [Pinned source review](Ariadne/bap-analysis-core-design.md#pinned-projection-source-review), [accepted admission plan](../.agents/plans/completed/bap-projection-admission.md) | Unsupported semantics remain explicit; the accepted corpus is finite. |
| Which definitions contribute to a fault address? | [Investigation design](Ariadne/investigation-design.md) | [API](Ariadne/investigation-design.md#investigation-module-and-interface), [validation](Ariadne/investigation-design.md#retained-delivery-evidence) | Possible dependencies do not establish execution or a root cause. |
| Can a memory writer be narrowed to the selected load? | [Memory provenance proposal](Ariadne/memory-provenance-refinement.md) | [Retained Scanner query](Ariadne/bap-analysis-core-design.md#admission-resume) | Bounded alias assessment and output-specific refinements remain proposed. |
| Does the fault-time access begin at zero? | [Zero-address design](Ariadne/zero-address-design.md) | [Source review](Ariadne/zero-address-design.md#source-and-finite-admission-review), [native qualification](Ariadne/zero-address-design.md#native-qualification) | Captured-context and finite admission premises apply. |
| Is the encoded base zero with a nonzero displacement? | [Zero-base-offset design](Ariadne/zero-base-offset-design.md) | [Source review](Ariadne/zero-base-offset-design.md#decoded-record-and-independent-oracle), [qualification](Ariadne/zero-base-offset-design.md#retained-qualification) | First-profile forms and source-bound acceptance remain distinct from historical provenance. |
| Did base plus signed displacement wrap? | [Address-wrap design](Ariadne/address-wrap-design.md) | [Implementation plan](../.agents/plans/i5c-address-wrap.md) | Model, implementation and qualification remain pending. |
| How are analysis results presented? | [Rendering and minidump report design](Ariadne/result-rendering.md) | [Presentation validation](Ariadne/result-rendering.md#presentation-acceptance), [examples](Ariadne/result-rendering.md#investigator-cli-examples) | Each result family retains its own meaning and completeness rules. |
| How do replay, supplied IR and stateflow fit? | [Typed replay](Ariadne/typed-replay-design.md), [stateflow](machine-state-design.md) | [Replay guide](../mbt/stage-e/README.md), [completion evidence](Ariadne/typed-replay-design.md#finite-corpus-and-claim-boundary), [IR guide](Ariadne/typed-replay-design.md#direct-verified-ir) | Supplied semantics remain premises; binary input does not reconstruct original LLVM IR. |
| How is performance assessed and improved? | [Workload measurement](Ariadne/workload-performance-design.md), [investigation optimization](Ariadne/workload-performance-design.md#investigation-performance) | [Native investigation qualification](Ariadne/workload-performance-design.md#native-investigation-qualification), [historical workload result](Ariadne/workload-performance-design.md#historical-llvm-workload-qualification) | Budgets and measurements apply to their exact backend, host and workload. |

## Maintaining the network

- Extend the canonical feature design when later work changes its decisions or
  contracts. Keep stage execution in its linked plan and dated progress in
  [checkpoints](../CHECKPOINTS.md).
- Give every design a direct origin link and useful next readings. A map link
  supplements these relationships; it does not replace them.
- State whether a document describes implemented behavior, a proposal, a
  historical result or retired work. Preserve source/tool/corpus qualifications.
- Preserve unique contracts when removing an absorbed document, and redirect
  live references to the canonical owner. Do not leave a stage-design stub.
- Fold module usage, source reviews and dated validation narratives into the
  owning feature document. Preserve recorded evidence bytes, source hashes,
  timestamps and pass flags.
  Historical inventory paths refer to their original Git revisions, even when
  live design paths have been consolidated.
- Link new implementation plans from their owning design in the same change.
- Run `python3 tools/check_doc_links.py` after navigation changes. The check
  verifies local paths, anchors, context fields and reachability; editorial
  review still establishes whether the relationships are meaningful.

## Document catalogue

The catalogue below provides an entry to every document with contextual
navigation, including completed plans and retained evidence.

The [investigation correctness-fix plan](../.agents/plans/completed/investigation-correctness-fixes.md)
addresses two reviewed gaps in the first-question implementation: full Windows
latency enforcement and valid answers when explanation limits are exhausted.
Its [delivery record](Ariadne/investigation-design.md#qualification-and-truncation-repairs) separates
implemented repairs and exercised checks from real-Windows qualification.

### Project and active plans

- [Structural frame report plan: Stage 5.1](../.agents/plans/frame-structure-report.md)
  — recovery-only artifact, validated frame links and separate report;
  [the investigation contract](Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
  owns its scope. SF0–SF6 are complete within the
  [2026-10-16 qualified Windows scope](../evidence/Ariadne/frame-structure/20261016/README.md).

- [Frame connections plan: Stage 5.2](../.agents/plans/frame-connections.md)
  — implemented corridor reachability, SCC condensation and bounded example routes
  over the Stage 5.1 source; the
  [canonical design section](Ariadne/investigation-design.md#structural-corridors-and-cycle-summaries)
  owns meanings and limits. Local implementation and validation pass; remote
  qualification remains open.

- [Complete section-5 investigation program](../.agents/plans/frame-question-investigation.md)
  — [canonical integration design](Ariadne/frame-question-investigation-design.md)
  for all four recommendation items: reuse existing source/connections, then
  add question-directed resolution and local fault-dependency composition.
  New P0–P10 stages remain pending; FC5/M4 keep their separate qualification.

- [Captured indirect-target resolver plan](../.agents/plans/indirect-target-resolution.md)
  — R0–R6 contract, evidence, discovery, native admission and qualification.

- [Active specification synchronization](../.agents/plans/specification-sync.md) —
  source/model audit, preserved replay bindings and qualification boundaries.

- [BAP projection admission and coverage plan](../.agents/plans/completed/bap-projection-admission.md) —
  accepted form validation, capability admission and conservative ordinary
  continuation, with qualified finite-corpus exits and excluded historical real-Linux clauses.

- [I5c address-wrap implementation plan](../.agents/plans/i5c-address-wrap.md).
- [I4 native performance implementation](../.agents/plans/completed/i4-performance-implementation.md).
- [I5b zero-base-plus-displacement implementation plan](../.agents/plans/completed/i5b-zero-base-offset.md).
- [Windows I4 replacement plan](../.agents/plans/completed/i4-windows-repin.md).
- [I5a zero-address implementation plan](../.agents/plans/completed/i5a-zero-address.md).
- [Native I5a qualification plan](../.agents/plans/completed/i5a-native-qualification.md).

- [Ariadne checkpoints](../CHECKPOINTS.md).
- [Ariadne plans](../.agents/plans/README.md).
- [BAP integration plan: semantic backend, then analysis core](../.agents/plans/completed/bap-integration.md).
- [Ariadne investigation-layer implementation plan](../.agents/plans/investigation-layer.md).
- [Ariadne](../README.md).
- [Ariadne roadmap](../ROADMAP.md).

### Feature documents

- [Ariadne architecture](Ariadne/architecture.md).
- [File readers and immutable address-space preparation](Ariadne/file-reader-design.md).
- [Captured indirect control target resolution](Ariadne/indirect-target-resolution.md).
- [BAP semantic and analysis integration](Ariadne/bap-analysis-core-design.md).
- [Fault-address investigation design](Ariadne/investigation-design.md).
- [Zero-address assessment design](Ariadne/zero-address-design.md).
- [Zero-base-plus-displacement assessment design](Ariadne/zero-base-offset-design.md).
- [Fault-time address-wrap assessment design](Ariadne/address-wrap-design.md).
- [Memory provenance refinement for Scanner](Ariadne/memory-provenance-refinement.md).
- [Analysis result rendering and minidump reports](Ariadne/result-rendering.md).
- [Typed replay and analysis result contracts](Ariadne/typed-replay-design.md).
- [Workload performance design](Ariadne/workload-performance-design.md).
- [Structured operands and conservative instruction effects](Ariadne/operand-effects-design.md).
- [Semantic assurance and proof boundaries](Ariadne/semantic-assurance.md).

### Implementation and runtime references

- [Repository terminology convention](terminology.md).
- [Crashpad demo build and capture recipe](../native/crashpad-demo/README.md).
- [Complete Stage 2 execution plan](../.agents/plans/completed/bap-stage2-implementation.md).
- [Stage 2 A0 plan](../.agents/plans/completed/bap-stage2-a0.md).
- [OCaml foundation qualification plan](../.agents/plans/completed/bap-ocaml-qualification.md).
- [Native BAP analysis core](../native/bap-core/README.md) — default algorithms and separately labeled historical A0 probe.
- [BAP Windows workload replacement plan](../.agents/plans/completed/bap-windows-repin.md).
- [Rust machine-analysis implementation](implementation.md).
- [LLVM MC byte-span adapter](llvm-mc-adapter.md).
- [Rust design for abstract machine-state analysis](machine-state-design.md).

### Formal-model, native-tool and evidence guides

- [Ariadne formal model](../Specs/README.md).
- [Retained Ariadne evidence](../evidence/Ariadne/README.md).
- [Model-based tests for Ariadne](../mbt/README.md).
- [Stage E generated MirrorRust replay](../mbt/stage-e/README.md).
- [Pinned BAP instruction helper](../native/bap/README.md).

### Completed plans

- [Stage 1 follow-up: remove the LLVM semantic backend](../.agents/plans/completed/bap-only-semantics.md).
- [Operand and effect implementation plan](../.agents/plans/completed/operand-effects-plan.md).
- [Priority 1 implementation plan: a real-capture predecessor slice](../.agents/plans/completed/priority-1-real-capture-plan.md).
- [Priority 2 implementation plan: effects demanded by captured paths](../.agents/plans/completed/priority-2-path-driven-effects-plan.md).
- [Priority 3 implementation plan: investigator presentation and examples](../.agents/plans/completed/priority-3-investigator-presentation-plan.md).
- [Priority 4 implementation plan: workload-sized performance decision](../.agents/plans/completed/priority-4-workload-performance-plan.md).
- [Consolidate Rust sources and Cargo targets](../.agents/plans/completed/rust-source-layout.md).
- [Stage A implementation plan: memory-immediate MOV effects](../.agents/plans/completed/stage-a-memory-immediate-mov-plan.md).
- [Stage E completion plan](../.agents/plans/completed/stage-e-completion.md).
- [Stage E: first MirrorRust integration stage](../.agents/plans/completed/stage-e-mirrorrust-integration.md).
