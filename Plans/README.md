# Ariadne plans

## Context and follow-up

**Status.** Current plan navigation as of 2026-10-05. Native BAP analysis and
controlled Windows I5a are qualified within their recorded scopes. The Windows
I4 re-pin is complete; its unchanged CLI budget remains unmet.

**Why this document exists.** The [roadmap](../ROADMAP.md) sets the priorities
used to distinguish current work, delivered plans and retired research.

**What this document establishes.** The stage ledgers below identify remaining
work. Delivered plans preserve their implementation and acceptance contracts;
keeping a plan outside `completed/` does not make its completed steps pending.

**Where to go next.**

- [Investigation ledger](investigation-layer.md) — tracks active Windows I4
  performance, delivered I5a and later hypothesis/object/cross-capture work.
- [I4 replacement result](../docs/Ariadne/i4-windows-repin-validation.md) — records
  the exact active capture, 17 passing gates and 4,774.451 ms against 2,000 ms.
- [BAP integration ledger](bap-integration.md) — records completed semantic and
  analysis migration with remaining proof, source/tool and release limits.
- [Native core qualification](../docs/Ariadne/bap-core-qualification.md) and
  [native I5a qualification](../docs/Ariadne/i5a-native-qualification.md) — bind
  accepted corpora, helper identities and the read-only dependency snapshot.
- [Evidence guide](../evidence/Ariadne/README.md) — distinguishes retained results,
  failed progress records and fresh qualification after changes.

**What remains unresolved.** Full Windows I4 acceptance needs an explanation-CLI
median at most 2,000 ms on the active 98-start case. Broader I5 hypotheses, Linux
numeric admission, I6/I7, PE/ELF image and ELF-core inputs, universal refinement
and packaged cross-platform release qualification remain outside the delivered
scope. BAP's unlimited timing policy does not waive I4 or I5a budgets.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Current work and delivery ledgers

| Plan | Current state and next work |
| --- | --- |
| [Investigation layer](investigation-layer.md) | I0–I3 and active Windows producer correctness pass. I4 remains over its fixed CLI budget; I5a is qualified, while broader I5 and I6/I7 remain later work. |
| [BAP integration](bap-integration.md) | Stage 1 and native A0–A6 are qualified on their exercised corpora. Maintain source/tool-bound regressions after changes; universal proof and packaged release acceptance remain separate. |
| [Roadmap](../ROADMAP.md) | Current input and product direction, deferred readers and the [Stage F proof boundary](../docs/Ariadne/stage-f-proof-and-performance.md). |

## Delivered implementation and qualification plans

| Plan | Completion boundary and evidence |
| --- | --- |
| [Complete Stage 2 execution](bap-stage2-implementation.md) | Native recovery, definitions, slicing, finite stateflow, generated replay and adoption delivered; [20-gate qualification](../docs/Ariadne/bap-core-qualification.md) verifies default selection and explicit Rust rollback. |
| [OCaml foundation qualification](bap-ocaml-qualification.md) | OQ0–OQ6 qualified the pinned SDK, bounded native state exchange, transport, clean rebuild and mutations; [foundation record](../docs/Ariadne/bap-ocaml-qualification.md). |
| [Stage 2 A0](bap-stage2-a0.md) | Historical interface/capability probe; the foundation and complete Stage 2 successors independently close its implementation gaps. |
| [Windows I4 replacement](i4-windows-repin.md) | Capture/pin delivery complete with 17 passing gates; [validation](../docs/Ariadne/i4-windows-repin-validation.md) retains the unmet 2,000 ms CLI clause. This does not mark full I4 complete. |
| [I5a zero-address assessment](i5a-zero-address.md) | H0–H5 delivered; [12-gate historical source/fixture result](../docs/Ariadne/i5a-validation.md) precedes the separately qualified native/controlled tiers. |
| [Native I5a qualification](i5a-native-qualification.md) | [Native result](../docs/Ariadne/i5a-native-qualification.md): 14 source/fixture gates, 17 investigation gates and both controlled captures pass under the selected dependency snapshot and unchanged budgets. |
| [BAP Windows replacement](bap-windows-repin.md) | New real Crashpad capture, independent inspection and durable input pin delivered; [historical validation](../docs/Ariadne/bap-windows-repin-validation.md) preserves the former bounded-policy failure. The [later unlimited policy](../docs/Ariadne/bap-unlimited-validation.md) supersedes that BAP timing criterion. |

## Archived completed plans

Archived plans live in `completed/`; their records apply to the source, backend
and workload exercised at the original run. Archiving does not refresh evidence.

| Plan | Completion boundary and successor |
| --- | --- |
| [Investigation correctness fixes](completed/investigation-correctness-fixes.md) | Timing enforcement and valid truncation; [17-gate repair record](../docs/Ariadne/investigation-correctness-validation.md). The later active I4 re-pin retains its separate performance failure. |
| [Rust source layout](completed/rust-source-layout.md) | Single root Cargo package and source consolidation; [delivery](../docs/Ariadne/rust-source-layout.md). |
| [BAP-only semantics](completed/bap-only-semantics.md) | LLVM semantic selector/fallback removed; [historical removal](../docs/Ariadne/bap-only-removal-validation.md). Later Stage 1 and native Stage 2 records qualify their own scopes. |
| [Stage E initial integration](completed/stage-e-mirrorrust-integration.md) | Initial typed replay ports and fixture traces; [record](../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json). |
| [Stage E completion](completed/stage-e-completion.md) | Finite generated replay, mutations and report/CLI acceptance; [completion](../docs/Ariadne/stage-e-completion.md). |
| [Operand/effects implementation](completed/operand-effects-plan.md) | Historical LLVM effect preparation; [validation](../docs/Ariadne/operand-effects-validation.md). Production minidump semantics use BAP. |
| [Stage A MOV effects](completed/stage-a-memory-immediate-mov-plan.md) | Two scoped immediate-store rules; [validation](../docs/Ariadne/stage-a-validation.md). |
| [Priority 1 real capture](completed/priority-1-real-capture-plan.md) | One controlled Chromium/Linux predecessor slice; [validation](../docs/Ariadne/priority-1-real-capture-validation.md). |
| [Priority 2 path effects](completed/priority-2-path-driven-effects-plan.md) | Selected-path review and no-change decision; [validation](../docs/Ariadne/priority-2-effects-validation.md). New gaps need new scoped work. |
| [Priority 3 presentation](completed/priority-3-investigator-presentation-plan.md) | Instruction overview and platform examples; [validation](../docs/Ariadne/priority-3-presentation-validation.md). |
| [Priority 4 performance](completed/priority-4-workload-performance-plan.md) | Historical LLVM-backed workload optimization; [validation](../docs/Ariadne/priority-4-performance-validation.md). It does not qualify native BAP or the active I4 query. |

## Retired work

Stage D and the independent AMD64/Lean instruction-step track are retired;
their obligations were not discharged. Their sources and historical records
remain under the [semantic assurance decision](../docs/Ariadne/semantic-assurance.md).
