# Stage E typed MirrorRust integration

The [first-stage implementation plan](../../Plans/completed/stage-e-mirrorrust-integration.md)
connects the existing Stage E engines to `~/Repos/MirrorRust` through the
prepared Mirrors compiler's `mirrorrust-v1` target.

Status 2026-10-01: the first stage is implemented and its two-fixture
[integration record](../../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json) passes.
Stage E completion is recorded in the [completion report](stage-e-completion.md)
and its [source-bound evidence](../../evidence/Ariadne/stage-e-completion-validation.json).
The [Stage E completion implementation plan](../../Plans/completed/stage-e-completion.md)
covers the generated replay, mutation, handoff and report/CLI stage. Its
2026-10-02 scope update removes retired Stage D from qualification; the
[semantic assurance decision](semantic-assurance.md) preserves all Stage E clauses.

## Completion interfaces

The completion stage introduces an optional `reports/` crate with strict,
versioned machine-state request/semantic-input codecs and separate machine-state
and LLVM IR result envelopes. JSON, text and DOT derive from one validated
owned result. Machine addresses are canonical full-width hex; IR IDs remain
artifact/function-scoped strings. Input schemas reject unknown fields and
duplicates before constructing model requests.

`ariadne-minidump --stateflow-input PATH` accepts explicit trusted finite
semantic facts, checks their snapshot identity against the prepared dump,
and uses the frozen recovery handoff. Its additional reports retain the full
recovery graph, provenance and gaps beside stateflow classifications. No
instruction semantics or completeness assertion is inferred from crash registers.
The separate `ariadne-ir` CLI verifies a directly supplied `.ll`/`.bc`, then
reports its own block/instruction/call identities. Both paths finish validation
before publishing output.

Replay accepts a typed case-ID initializer bound to a fixed independently
generated request catalogue. Expected transitions come only from the original
TLA+ specifications. Deterministic generated cases expand the bounded corpus;
mechanical engine mutants establish that the unchanged observation seam can
detect failures in every relevant result family. This remains finite conformance
evidence, with the supplied semantic relation and native adapter as explicit
boundaries.

An independent `mbt/stage-e` package owns application ports and negotiated
factories. Generated modules own codecs, dispatch and lifecycle validation.
Factories construct the ports only after exact semantic-digest admission.
Each port owns its fixed request and resets a fresh real analyzer on initialization;
observations come only from that analyzer, never expected or previous model state.

Replay wrappers invoke the authoritative models' actions. Machine-state replay
chooses the lowest enabled address, matching Rust. Its observations retain phase,
the entire state map, structural graph, edge classifications, terminal outcomes,
not-reached nodes and obligations. LLVM IR retains phase, slice, control/call
graphs, dependency predecessors and obligations. Their identities remain separate.

The address-map wire projection uses explicit `{va, states}` rows with an
exact inverse check. String-keyed LLVM dependency maps keep their native map
representation. Raw model witnesses and projected type evidence remain retained.

The historical first corpus used the five-node machine-state and four-block IR
examples for transport, admission, binding ownership and actual-engine observations.
The completion stage expands to 32 inputs, checks 15 engine mutants and delivers
independent report/CLI envelopes. These finite checks establish the recorded
Stage E acceptance tier; ISA semantics and universal Rust refinement remain
separate research obligations.
