# AMD64 mul/div execution worktree checkpoint

## Context and follow-up

**Status.** Retired ISA research; links below explain historical dependencies, not an active backlog.

**Why this document exists.** Arithmetic kernels need implicit operands and divide-error outcomes. The motivating contract is [Historical motivation](amd64-integer-semantics.md).

**What this document establishes.** The body work binds explicit and implicit arithmetic operands, overlapping writes, sign extension and divide-error outcomes to register state.

**Where to go next.**

- [Related historical component](amd64-user64.md) — states why individual bodies did not establish complete instruction-step acceptance.
- [Retirement and current boundary](Ariadne/semantic-assurance.md) — ends the instruction-step objective without declaring its proof gaps solved.

**What remains unresolved.** This research is retired. Missing architectural bindings or proof obligations below remain historical gaps, not active release tasks or solved claims. Production instruction effects now follow the BAP trust boundary.

For the wider context, see the optional [documentation map](documentation-map.md).

> **Retired 2026-10-02.** This document and its ISA proof/profile artifacts
> are historical reference, outside active development and qualification.
> Milestones and commands below describe the former research track. See the
> [current semantic assurance decision](Ariadne/semantic-assurance.md).

The Lean module binds the 27 MUL, IMUL, DIV, IDIV and MULX form IDs to CPU
register effects. It snapshots explicit and implicit operands before writes,
orders MULX writes so an overlapping destination retains the documented upper
half, validates IMUL immediate sign extension, and represents divide error as
an outcome containing the unchanged pre-state.

This module is outside the immediate long64/CPL3 common-integer milestone. It
is intentionally not imported by the root library or presented as paired
TLA+/Lean coverage. Memory operands remain unavailable and the authoritative
TLA+ execution transcription is still pending. Its focused Lean checks preserve
the work without broadening the admitted milestone.
