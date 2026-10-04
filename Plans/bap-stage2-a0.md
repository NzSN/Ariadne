# Stage 2 A0: freeze the BAP analysis interface

## Context and follow-up

**Status.** Started on 2026-10-03 after the user requested Stage 2. The retained
Stage 1 prerequisite is checked before this work; A1–A6 remain separate stages.

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
now implements the isolated SDK and bounded Init/Visit state exchange. Its full
A0 decision requires all OQ gates; complete A1 recovery, dataflow/stateflow and
production adoption remain separate. The packaged runtime is not the SDK.

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

Complete A1 recovery, A2/A3 algorithms, generated helper replay, product
integration and adoption remain open. Production analysis still uses Rust.
