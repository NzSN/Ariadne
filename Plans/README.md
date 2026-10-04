# Ariadne plans

## Context and follow-up

**Status.** Plan navigation; completion and retirement are distinct.

**Why this document exists.** [Roadmap](../ROADMAP.md) sets the priorities used to classify work.

**What this document establishes.** Active plans cover BAP integration and investigation. The reviewed qualification/truncation repairs are complete within their recorded tier. Completed plans are archived; retired ISA work is neither pending delivery nor successfully proved.

**Where to go next.**

- [OCaml foundation qualification](../docs/Ariadne/bap-ocaml-qualification.md) — records the completed A0 SDK, native state and transport gates.

- [Unlimited timing policy](../docs/Ariadne/bap-unlimited-validation.md) — records the user-authorized removal of the BAP latency ceiling and refreshed qualification.

- [BAP Windows replacement](bap-windows-repin.md) — creates and pins the controlled
  Crashpad workload authorized after the original artifact was confirmed lost.

- [BAP plan](bap-integration.md) — retains previous R0–R2 evidence and tracks the active replacement workload and A0 core-migration work.
- [Replacement validation](../docs/Ariadne/bap-windows-repin-validation.md) — records completed capture/pinning, 17 passing implementation gates and the former 2,000 ms limit.
- [Previous BAP workload delivery](../docs/Ariadne/bap-windows-workload-validation.md) — preserves the earlier R0–R2 evidence and its original-workload decision.
- [Investigation stage plan](investigation-layer.md) — separates delivered I0–I3, open I4 acceptance and the [implemented I5a question](../docs/Ariadne/i5a-contracts.md).
- [I5a execution plan](i5a-zero-address.md) — sequences the Windows zero-address question from reviewed context evidence through distinct qualification tiers.
- [Completed investigation repairs](completed/investigation-correctness-fixes.md) — records enforcement of the Windows timing condition and valid truncation under explanation limits.

**What remains unresolved.** The isolated OCaml SDK and bounded Init/Visit transport now qualify the A0 foundation. Complete A1–A6 now passes the [Stage 2 qualification](../docs/Ariadne/bap-core-qualification.md), including native default selection and explicit Rust rollback. The user has removed the active BAP latency ceiling; valid capture/correctness evidence and implementation gates remain required. Historical Priority 4/I4 and controlled I5a qualification retain their separate contracts.

For the wider context, see the optional [documentation map](../docs/documentation-map.md).

Updated 2026-10-03. Archived plans live in `completed/`; their recorded results
apply to the sources and workload originally exercised. Archiving a plan does
not refresh qualification evidence.

## Active work

| Plan | Remaining scope |
| --- | --- |
| [Stage 2 A0](bap-stage2-a0.md) | Historical probe; the successor OCaml foundation and full Stage 2 qualify their separate scopes. |
| [Complete Stage 2 execution](bap-stage2-implementation.md) | A1–A6 implemented; 20 aggregate gates pass, native CLI default and explicit Rust rollback verified. |
| [OCaml foundation qualification](bap-ocaml-qualification.md) | OQ0–OQ6: isolated pinned SDK, native helper/state, production transport, clean rebuild and targeted mutations; proposed, not executed. |
| [BAP integration](bap-integration.md) | Replacement capture and pin complete; 17/17 implementation gates pass with 178 stable sources. The user subsequently removed the latency ceiling; valid correctness evidence and passing gates establish full Stage 1 and its prerequisite; the A0 foundation and complete A1–A6 are qualified on their recorded corpora. |
| [Investigation layer](investigation-layer.md) | Full original-Windows I4 qualification; controlled real Windows I5a; broader I5 and I6–I7 capabilities remain unimplemented. |
| [I5a zero-address assessment](i5a-zero-address.md) | H0–H5 source/fixture tier delivered with [12 passing gates](../docs/Ariadne/i5a-validation.md); [controlled Windows capture/answer checks](../docs/Ariadne/crashpad-demo-validation.md) pass, but the CLI timing condition remains open. |
| [Roadmap](../ROADMAP.md) | Current scope and delivery direction; the [Stage F proof boundary](../docs/Ariadne/stage-f-proof-and-performance.md) remains open. |

## Completed plans

| Plan | Completion boundary and evidence |
| --- | --- |
| [BAP Windows replacement](bap-windows-repin.md) | New native Crashpad capture, independent inspection and durable input pin delivered; 59 controlled BAP tests, nine inspector tests and 17 implementation gates pass. [Retained validation](../docs/Ariadne/bap-windows-repin-validation.md) records the 10,667.760921 ms median and former 2,000 ms condition; the later unlimited policy supersedes that timing criterion. |
| [Investigation correctness fixes](completed/investigation-correctness-fixes.md) | Qualification/truncation repairs; [17-gate validation](../docs/Ariadne/investigation-correctness-validation.md). Original-Windows I4 qualification remains separate. |
| [Rust source layout](completed/rust-source-layout.md) | Single root Cargo package and source consolidation; [delivery record](../docs/Ariadne/rust-source-layout.md). |
| [BAP-only semantics](completed/bap-only-semantics.md) | LLVM semantic selector/fallback removed; [removal record](../docs/Ariadne/bap-only-removal-validation.md). Full BAP workload qualification remains in the active integration plan. |
| [Stage E initial integration](completed/stage-e-mirrorrust-integration.md) | Initial typed replay ports and fixture traces; [integration record](../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json). |
| [Stage E completion](completed/stage-e-completion.md) | Finite generated replay, mutations and report/CLI acceptance; [completion record](../docs/Ariadne/stage-e-completion.md). |
| [Operand/effects implementation](completed/operand-effects-plan.md) | Historical LLVM effect preparation; [validation](../docs/Ariadne/operand-effects-validation.md). Production semantics now use BAP. |
| [Stage A MOV effects](completed/stage-a-memory-immediate-mov-plan.md) | Two scoped memory-immediate MOV rules; [validation](../docs/Ariadne/stage-a-validation.md). |
| [Priority 1 real capture](completed/priority-1-real-capture-plan.md) | One controlled Chromium/Linux predecessor slice; [validation](../docs/Ariadne/priority-1-real-capture-validation.md). |
| [Priority 2 path effects](completed/priority-2-path-driven-effects-plan.md) | Selected-path effect review and no-change decision; [validation](../docs/Ariadne/priority-2-effects-validation.md). New path gaps require new scoped work. |
| [Priority 3 presentation](completed/priority-3-investigator-presentation-plan.md) | Instruction overview and platform examples; [validation](../docs/Ariadne/priority-3-presentation-validation.md). |
| [Priority 4 performance](completed/priority-4-workload-performance-plan.md) | Historical LLVM-backed workload optimization; [validation](../docs/Ariadne/priority-4-performance-validation.md). This does not qualify current BAP performance. |

## Retired work

Stage D is retired, not completed. Its sources and evidence remain historical reference
under the [semantic assurance decision](../docs/Ariadne/semantic-assurance.md).
