# Ariadne loop-aware resolver — implemented

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

The existing resolver now proves whole-dispatch coverage for bounded local loops. It independently checks base initialization, every entrance and internal edge, current selector/flag constraints, captured table arithmetic and every successor. Unknown pointer and selector loads remain fresh across iterations.

The first rule supplies coverage for table entries already validated by ordinary path receipts. Larger unsupported loops and missing table witnesses remain explicit partial results.

The original dump `dump_03958DA4FCA844A786262A1053` was retried successfully, using thread 23668 and frame pair 1 → 0:

| Dispatch | Result |
| --- | --- |
| `0x00007ff77440da09` | Complete; four targets; accepted induction receipt |
| `0x00007ff77440dadd` | Complete; four targets; accepted induction receipt |

All nine original table sites are complete. Their 370 entries and 64 destinations match the independent captured witness, and all 51 formerly missing starts were attempted. The caller has 10/10 complete target sites including DADD. Both completed frame requests and full states match exactly between native and Rust.

The full-dump retry exposed and helped correct a publication bug: non-followed call targets and unattempted slice seeds must appear as represented Stop endpoints before graph-bound proofs are produced. They remain unattempted and do not become roots. The final stale-proof rejection is preserved.

Validation passed on remote Windows WSL:

- 227 default and 46 core-only tests; format, Clippy and layout checks.
- Seven focused loop tests plus the publication regression.
- 41 native controls and eight successful behavioral mutation checks.
- 49 finite model configurations and the independent loop oracle.
- 330 core/stateflow replay observations; wrong-digest controls reject before dispatch.
- Actual legacy minidump/frame semantic replay and old-helper capability rejection.

Frame paths remain **unavailable**, with zero returned paths and `missing-or-ambiguous-active-call-anchor`. Caller guard coverage retains 30 barriers and the initial MOVAPS is unknown; the callee retains 12 barriers. Successful target closure does not establish an executed path.

The qualified source capsule is `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee`. The successful dump run is `051409`; native/Rust parity and both loop proofs pass its acceptance gates. Documentation and both completed plans have been reconciled and archived.

[Qualification and evidence](../../evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) · [Canonical design](../../docs/Ariadne/guarded-target-resolution-design.md) · [Completed loop plan](../plans/completed/loop-aware-target-resolution.md)


## Context and follow-up

**Status.** Restored historical chat explanation. The original text and its evidence scope remain dated.

**Why this document exists.** It preserves an explanation presented through `wslview`; the [chat-document convention](../../../skills/skills/productivity/chatdoc/SKILL.md) gives it a durable home.

**What this document establishes.** The body records the mechanism, observations and limits stated in that conversation.

**Where to go next.** The [chat report index](ariadne-reports-index.md) links related reports; the [assurance contract](../../docs/Ariadne/semantic-assurance.md) defines current responsibilities.

**What remains unresolved.** Restoration does not verify the report against the current implementation or refresh its original qualification.
