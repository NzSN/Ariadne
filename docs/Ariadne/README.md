# Ariadne documentation

## Context and follow-up

**Status.** Current documentation entry point.

**Why this document exists.** [Project overview](../../README.md) introduces the workflow these guides explain.

**What this document establishes.** This index separates current usage/contracts from delivery evidence. Use the topic table to choose a component; each linked document explains its own prerequisites and successors.

**Where to go next.**

- [Architecture overview](architecture.md) — block diagrams, Rust/native ownership, main minidump flow and separate IR/stateflow paths.

- [Accepted P4 real-capture replacement](real-capture-repin-79938.md) — current Windows corpus, distinct baseline, unchanged fixed budgets and excluded historical real-Linux clauses.
- [BAP v3 resume record](bap-admission-resume.md) — recovered tools, preserved earlier failures and the selected successor.
- [Historical BAP v3 execution checkpoint](bap-admission-checkpoint.md) — initial P0–P3 checks and failures before the accepted P4 successor.

- [Historical BAP documentation audit](bap-documentation-sync.md) — earlier v2 source/evidence synchronization and its current successors.

- [Selected I5c address-wrap design](i5c-address-wrap-design.md) and
  [W0–W5 plan](../../Plans/i5c-address-wrap.md) — the next arithmetic question;
  implementation, model and controlled-capture qualification remain pending.

- [Selected I5b design](i5b-zero-base-offset-design.md) and
  [implementation plan](../../Plans/i5b-zero-base-offset.md) — delivered
  fault-time machine-code debugging assessment; [implemented contracts](i5b-contracts.md)
  and [qualification](i5b-validation.md) distinguish its current tiers.

- [Active Windows I4 qualification](i4-windows-repin-validation.md) — exact replacement capture and historical baseline; [native performance qualification](i4-performance-validation.md) meets the fixed CLI budget.

- [Documentation map](../documentation-map.md) — traces motivation, implementation, validation and open questions.
- [Plan index](../../Plans/README.md) — identifies active implementation work.

**What remains unresolved.** Active Windows I4 correctness passes after the [98-instruction re-pin](i4-windows-repin-validation.md); the later [performance qualification](i4-performance-validation.md) meets the unchanged 2 s limit at 1,692.696 ms. Controlled Windows I5a is [qualified under the pinned dependency snapshot](i5a-native-qualification.md). Native BAP recovery, dataflow, slicing and finite stateflow are implemented; [Stage 2 qualification](bap-core-qualification.md) records passing aggregate acceptance and default adoption. Other hypothesis, object/source-context and cross-capture questions remain later work.

For the wider context, see the optional [documentation map](../documentation-map.md).

Start with the current interfaces and assurance boundary. Active implementation
work is listed in the [plan index](../../Plans/README.md); completed plans live
under `Plans/completed/`.

| Topic | Current documentation |
| --- | --- |
| Architecture and process boundaries | [Architecture overview](architecture.md) |
| Minidump input and CLI | [Input guide](modules/input.md), [examples](minidump-investigator-examples.md), [report schema](stage-c-report-schema.md) |
| BAP semantics and native analysis | [Backend guide](modules/bap.md), [projection design](bap-semantic-backend-design.md), [source review](bap-projection-source-review.md), [native qualification](bap-core-qualification.md), [current audit](bap-documentation-sync.md), [admission delivery plan](../../Plans/bap-projection-admission.md) |
| Fault-address investigation | [Module guide](modules/investigation.md), [producer contracts](investigation-contracts.md), [I5a zero-address contracts](i5a-contracts.md), [design](investigation-layer-design.md). |
| Planned address-wrap assessment | [I5c design](i5c-address-wrap-design.md) and [W0–W5 plan](../../Plans/i5c-address-wrap.md); no implemented interface or acceptance yet. |
| Zero-base-plus-displacement assessment | [I5b contracts](i5b-contracts.md), [source review](i5b-source-review.md), [validation](i5b-validation.md), [B0–B5 plan](../../Plans/i5b-zero-base-offset.md). |
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
capture/answer evidence. Its historical timing miss is followed by
[native qualification](i5a-native-qualification.md): all 14 source/fixture gates
and both controlled capture modes pass with a read-only dependency snapshot.
Validation JSON, CSV samples and evidence archives retain their original
identities under [evidence/Ariadne](../../evidence/Ariadne/README.md).
A historical passing record is not fresh qualification after changes.

Older priority, effect-rule and source-review documents remain evidence for their
original backend and workload. The [active Windows I4 re-pin](i4-windows-repin-validation.md) closes the missing
artifact gap; [native performance qualification](i4-performance-validation.md) later meets its fixed CLI budget. The
[universal Rust proof boundary](stage-f-proof-and-performance.md) remains open.
The independent ISA proof project is retired. Obsolete plan/status Markdown is
removed; Git retains its history.
