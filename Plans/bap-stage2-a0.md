# Stage 2 A0: freeze the BAP analysis interface

## Context and follow-up

**Status.** Historical A0 contract/capability probe from 2026-10-03. The
[OCaml foundation](../docs/Ariadne/bap-ocaml-qualification.md) subsequently closed
its SDK/state-exchange gaps; [complete Stage 2 qualification](../docs/Ariadne/bap-core-qualification.md)
records delivered A1–A6 and native default adoption.

**Why this document exists.** The [integration plan](bap-integration.md#stage-2-bap-analysis-core)
requires real BAP-owned recovery, dataflow, slicing and stateflow, preserving
incremental model observations. Lifting alone does not supply those algorithms.

**What this document establishes.** A0 freezes ownership, versioned messages,
finite-domain mappings, attribution and failure semantics. Executable contract
checks and a pinned-runtime capability probe make the design reviewable.

**Where to go next.**

- [OCaml qualification plan](bap-ocaml-qualification.md) — records the completed SDK, real state exchange and transport gates.

- [A0 validation](../docs/Ariadne/bap-stage2-a0-validation.md) — distinguishes passing contract/probe checks from the remaining full-exit clause.

- [Stage 2 contract](../docs/Ariadne/bap-analysis-core-design.md) — defines the
  interface and exact mappings to both analysis specifications.
- [Integration plan](bap-integration.md) — sequences A1 recovery through A6 adoption.
- [Stage 1 prerequisite](../docs/Ariadne/bap-unlimited-validation.md) — records
  the source-bound prerequisite under the authorized unlimited timing policy.

**What remains unresolved.** The [OCaml successor](../docs/Ariadne/bap-ocaml-qualification.md)
qualified the isolated SDK and bounded Init/Visit state exchange with
all OQ gates passing. The later [complete Stage 2 result](../docs/Ariadne/bap-core-qualification.md)
independently qualifies recovery, dataflow, slicing, stateflow and production
adoption. This earlier capability probe does not supply those claims.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Work and exit evidence

1. Verify the complete retained Stage 1 source inventory and analysis tools.
2. Freeze the recovery and stateflow input/action/observation/result contract,
   including strict identities and deterministic replay scheduling.
3. Exercise the installed BAP runtime's BIR term, address and graph behavior;
   record actual outputs and unsupported facilities without claiming a solver.
4. Test the executable protocol admission rules with positive and negative
   cases. These are contract tests, not native analysis conformance.
5. Record A0's delivered and unresolved clauses, update the design/plan links,
   and leave the production Rust core selected until A5/A6 qualify a replacement.

Use `native/bap-core/` for experimental Stage 2 native work, separate from the
qualified Stage 1 lifter build. Put qualification utilities/tests under `tools/`.
Future Rust sources belong under `src/bap/`, with Rust tests under `tests/bap/`.
No analysis algorithms are duplicated into a transport validator or observer.

## Current result

The seven envelope/attribution tests and fresh native probes pass. The native
TID graph collapses parallel labels, so the implementation retains a separate
typed edge relation. The [OCaml successor](../docs/Ariadne/bap-ocaml-qualification.md)
now passes OQ0–OQ6: isolated SDK, actual Init/Visit state, Rust transport,
clean rebuild and mutation sensitivity. Full A0 exit is qualified against
fresh Stage 1 prerequisites. The earlier facility-only record stays historical.

Complete A1–A6 were delivered by the [Stage 2 execution plan](bap-stage2-implementation.md).
The [native qualification](../docs/Ariadne/bap-core-qualification.md) records
passing algorithm, generated replay, product and default-adoption acceptance.
The production minidump CLI now uses native BAP analysis; Rust is the explicit
reference/rollback. This earlier probe record retains its limited claims.
