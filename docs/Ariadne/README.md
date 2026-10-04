# Ariadne documentation

## Context and follow-up

**Status.** Current documentation entry point.

**Why this document exists.** [Project overview](../../README.md) introduces the workflow these guides explain.

**What this document establishes.** This index separates current usage/contracts from delivery evidence. Use the topic table to choose a component; each linked document explains its own prerequisites and successors.

**Where to go next.**

- [Documentation map](../documentation-map.md) — traces motivation, implementation, validation and open questions.
- [Plan index](../../Plans/README.md) — identifies active implementation work.

**What remains unresolved.** Full original-Windows I4 and controlled real Windows I5a qualification remain open. Native BAP recovery, dataflow, slicing and finite stateflow are implemented; [Stage 2 qualification](bap-core-qualification.md) records passing aggregate acceptance and default adoption. Possible-producer and zero-address questions are implemented; other hypothesis, object/source-context and cross-capture questions remain later work.

For the wider context, see the optional [documentation map](../documentation-map.md).

Start with the current interfaces and assurance boundary. Active implementation
work is listed in the [plan index](../../Plans/README.md); completed plans live
under `Plans/completed/`.

| Topic | Current documentation |
| --- | --- |
| Minidump input and CLI | [Input guide](modules/input.md), [examples](minidump-investigator-examples.md), [report schema](stage-c-report-schema.md) |
| BAP semantics | [Backend guide](modules/bap.md), [protocol and projection design](bap-semantic-backend-design.md), [source review](bap-projection-source-review.md) |
| Fault-address investigation | [Module guide](modules/investigation.md), [producer contracts](investigation-contracts.md), [I5a zero-address contracts](i5a-contracts.md), [design](investigation-layer-design.md). |
| Stateflow and supplied LLVM IR | [Stage E contracts](stage-e-report-contracts.md), [IR guide](modules/ir.md), [report guide](modules/reports.md) |
| Rendering and analysis concepts | [Rendering](result-rendering.md), [static-analysis learning guide](static-analysis-learning.md) |
| Assurance and scope | [Semantic assurance](semantic-assurance.md), [roadmap](../../ROADMAP.md), [checkpoints](../../CHECKPOINTS.md) |

## Delivery evidence

The [source-layout record](rust-source-layout.md),
[BAP-only delivery](bap-only-removal-validation.md),
[workload qualification repair](bap-windows-workload-validation.md),
[controlled Windows replacement](bap-windows-repin-validation.md),
[unlimited BAP timing policy](bap-unlimited-validation.md),
[Stage 2 A0 start](bap-stage2-a0-validation.md),
[investigation validation](investigation-validation.md) and
[Stage E completion](stage-e-completion.md) explain their exercised scopes.
The later [investigation correctness record](investigation-correctness-validation.md)
qualifies the timing-decision and truncation repairs within the available tier.
The [I5a delivery record](i5a-validation.md) documents the new numeric question's
corpus, measurements and separate Windows capture requirements.
The later [Crashpad Windows demo](crashpad-demo-validation.md) provides real
capture/answer evidence, with CLI performance still over its criterion.
Validation JSON, CSV samples and evidence archives retain their original
identities under [evidence/Ariadne](../../evidence/Ariadne/README.md).
A historical passing record is not fresh qualification after changes.

Older priority, effect-rule and source-review documents remain evidence for their
original backend and workload. The original Windows capture requirement and
the [universal Rust proof boundary](stage-f-proof-and-performance.md) remain open.
The independent ISA proof project is retired. Obsolete plan/status Markdown is
removed; Git retains its history.
