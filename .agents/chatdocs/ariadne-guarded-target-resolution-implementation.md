# Ariadne guarded target resolution — implementation result

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

Implemented the combined preparation, paired Rust/native proof validation and versioned reports. All compilation and runtime checks ran in remote Windows WSL.

The retry of dump `03958DA4FCA844A786262A1053` recovered **all nine table candidate sets: 64 destinations, with all 51 previously missing starts attempted**. Both completed frame queries have identical Rust/native requests and states.

Eight original jumps have complete certificates. `0x7ff77440da09` retains four witnessed targets and incomplete cyclic incoming-state coverage. A newly discovered jump at `0x7ff77440dadd` also retains four targets with a cycle residual.

The caller retains 32 coverage barriers. Its initial MOVAPS remains unknown, and frame paths `1:0`, NP10 remain unavailable with `missing-or-ambiguous-active-call-anchor`.

Validation passed: 218 default tests, 46 core-only, affected native suites, 19 finite model configurations, 330 generated replay observations and 273 actual infeasible-receipt replays. Three of four native implementation mutants received behavioral credit; the fourth remains rejected by an independent check.

The implementation and candidate-recovery gates are delivered. The plan remains active for the ninth full-closure certificate and subsequent guard/path coverage.

[Canonical design](../../docs/Ariadne/guarded-target-resolution-design.md) · [Qualification evidence](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md) · [Active execution plan](../plans/completed/guarded-target-resolution.md)


## Context and follow-up

**Status.** Restored historical chat explanation. The original text and its evidence scope remain dated.

**Why this document exists.** It preserves an explanation presented through `wslview`; the [chat-document convention](../../../skills/skills/productivity/chatdoc/SKILL.md) gives it a durable home.

**What this document establishes.** The body records the mechanism, observations and limits stated in that conversation.

**Where to go next.** The [chat report index](ariadne-reports-index.md) links related reports; the [assurance contract](../../docs/Ariadne/semantic-assurance.md) defines current responsibilities.

**What remains unresolved.** Restoration does not verify the report against the current implementation or refresh its original qualification.
