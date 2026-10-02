# Ariadne plans

## Context and follow-up

**Status.** Plan navigation; completion and retirement are distinct.

**Why this document exists.** [Roadmap](../ROADMAP.md) sets the priorities used to classify work.

**What this document establishes.** Two plans remain active: BAP integration and investigation. Completed plans are archived; retired ISA work is neither pending delivery nor successfully proved.

**Where to go next.**

- [BAP plan](bap-integration.md) — tracks missing Windows qualification and the unstarted core migration.
- [Investigation plan](investigation-layer.md) — tracks full I4 acceptance and later investigation questions.

**What remains unresolved.** Full original-Windows qualification is still open. The BAP analysis-core replacement has not started; neither selecting BAP nor passing a fixture closes those requirements. The first fault-address question is implemented, but full original-Windows I4 qualification remains open. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

For the wider context, see the optional [documentation map](../docs/documentation-map.md).

Updated 2026-10-02. Completed plans live in `completed/`; their recorded results
apply to the sources and workload originally exercised. Archiving a plan does
not refresh qualification evidence.

## Active work

| Plan | Remaining scope |
| --- | --- |
| [BAP integration](bap-integration.md) | Original-Windows Stage 1 qualification; Stage 2 analysis-core migration has not started. |
| [Investigation layer](investigation-layer.md) | Full original-Windows I4 qualification and later I5–I7 capabilities. |
| [Roadmap](../ROADMAP.md) | Current scope and delivery direction; the [Stage F proof boundary](../docs/Ariadne/stage-f-proof-and-performance.md) remains open. |

## Completed plans

| Plan | Completion boundary and evidence |
| --- | --- |
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
