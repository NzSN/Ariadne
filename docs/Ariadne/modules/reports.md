# Stage E inputs and reports

## Context and follow-up

**Status.** Current codecs and rendering for separate Stage E results.

**Why this document exists.** [Result contracts](../stage-e-report-contracts.md) keep machine VAs and IR identities distinct.

**What this document establishes.** The module validates and renders separate stateflow and IR result families, preserving identity and uncertainty across formats rather than merging their meanings.

**Where to go next.**

- [Report/CLI delivery](../stage-e-completion.md) — records validation and publication behavior.
- [IR usage](ir.md) — shows one consumer of the report interfaces.

**What remains unresolved.** Serialization agreement does not prove the semantic inputs true. Each producer/handoff needs its own acceptance, and claim scope must survive rendering.

For the wider context, see the optional [documentation map](../../documentation-map.md).

`ariadne::reports` keeps serialization out of the dependency-free analysis core.
It supplies strict normalized request codecs for the replay harness, a semantic
input codec for the minidump handoff, and independent machine-state/LLVM IR
JSON, text and DOT reports.

Schemas are `ariadne.machine-state-request/v1`,
`ariadne.machine-state-semantics/v1`, `ariadne.llvm-ir-request/v1`,
`ariadne.machine-state-report/v1` and `ariadne.llvm-ir-report/v1`.
Machine VAs are strings with `0x` and exactly 16 lowercase hex digits.
Request inputs reject unknown fields, duplicate object/table/set entries,
noncanonical addresses and invalid model contracts. JSON input defaults to an
8 MiB cap; the native IR protocol retains its existing 32 MiB cap.

Semantic inputs contain `snapshot_id`, `value_domain`, `catalogue`,
`entry_states`, `steps`, `terminal_transitions`, `complete_sites` and
`adapter_obligations`. They supply no graph or instruction effects: those come
from the frozen recovery handoff. Catalogue rows contain `status` and a total
`valuation`; entry rows use `va` and `states`; each step carries its typed
`edge`, `before` and `after`; terminal rows carry `site`, `before`, `after` and
`outcome`. See the checked examples in
[the generated request catalogue](../../../mbt/stage-e/corpus/inputs/MachineStateReplay.json)
and `encode_semantics()` for producing the semantic-only schema.

A supplied transition relation and a `complete_sites` assertion are caller
premises. Feasibility is relative to those premises and entry facts. The engine
never derives past states from crash-time registers. Machine reports retain
the state catalogue, complete state map, structural/feasible/infeasible/unknown
edges, terminal outcomes and obligations. A minidump report also links the
separately versioned core input/preparation report, preserving its gaps.

IR reports retain artifact/module/function identity, normalized input,
instruction slice, block CFG, calls, dependency predecessors and obligations.
Their IDs remain distinct from machine VAs. A verifier acceptance does not
establish machine-address correspondence or precise memory aliasing.

Run the source-bound acceptance with `python3 tools/check_stage_e.py`.
[Completion plan](../../../Plans/completed/stage-e-completion.md) and
[report contracts](../stage-e-report-contracts.md).
