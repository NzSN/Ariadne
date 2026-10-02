# Stage E result contracts

## Context and follow-up

**Status.** Current distinct stateflow and supplied-IR result families.

**Why this document exists.** [Stage E design](stage-e-mirrorrust-design.md) requires results to retain machine-specific identity and semantics.

**What this document establishes.** The contracts preserve separate machine-state and IR identities, semantic premises, feasibility/dependency results and uncertainty in strict result envelopes.

**Where to go next.**

- [Stage E delivery](stage-e-completion.md) — records CLI/report acceptance.
- [Reports guide](modules/reports.md) — documents rendering and codec interfaces.
- [Supplied-IR guide](modules/ir.md) — shows verifier-backed input and query construction.

**What remains unresolved.** A stateflow feasibility label is relative to supplied entry facts and transitions. An IR report analyzes supplied verified IR, not reconstructed original machine-code IR.

For the wider context, see the optional [documentation map](../documentation-map.md).

These are separate result families for [Stage E completion](stage-e-completion.md).
The [completed Stage E](stage-e-completion.md) adds optional stateflow input to
the minidump investigator CLI and a separate verifier-backed IR CLI. Their
versioned [input/report schemas](modules/reports.md) preserve these families
independently.
The [first MirrorRust integration stage](../../Plans/completed/stage-e-mirrorrust-integration.md)
connects these result families to separate compiler-generated replay ports.
The [Stage E completion plan](../../Plans/completed/stage-e-completion.md) completes their
generated replay and versioned reporting/CLI integration stage.

| Path | Identity and fixed input | Mutable result | Derived observations |
| --- | --- | --- | --- |
| `ariadne::machine_state` | Recovery snapshot, decoded local nodes, full typed structural edges, finite state-ID catalogue, entry facts, trusted running/terminal transitions and completeness assertions | `Phase::Stateflow/Done`; possible state IDs **before** each node | Feasible, model-relative infeasible and unknown edges; reached terminal rows; not-reached nodes; adapter and incomplete-semantics obligations |
| `ariadne::llvm_ir` | SHA-256-bound directly supplied IR artifact, module/function identity, verifier-accepted block/SSA/phi/memory/call tables | `Phase::Slice/Done`; LLVM instruction-ID slice | Terminator-derived block CFG, separate call graph, direct SSA and conservative memory predecessors, incomplete-call and adapter obligations |

The machine-state recovery handoff retains the **full** recovery graph,
provenance, missing seeds and recovery obligations separately. Its stateflow
request excludes call-only edges but keeps summary edges. A stateflow
`complete_sites` assertion is supplied by an adapter and never inferred from a
decoded instruction's control-target completeness.

The IR path uses block, instruction, value and callee IDs scoped to the hashed
artifact and selected function. It does not assign machine VAs, reconstruct
original IR from a binary, or claim correspondence between native IR values
and crash-time register values. The LLVM helper's verifier certifies LLVM IR
well-formedness, while the adapter's all-writer memory predecessor set is a
coarse conservative policy carrying `unknown-memory-alias` obligations.

Both paths expose owned requests and results through shared-reference accessors.
They deliberately do not share the recovery analyzer's phase or obligation
enums. The CLI envelopes preserve each path's identity and uncertainty
without coercing one result into the other's graph.
