# Stage E typed MirrorRust integration

The [first-stage implementation plan](../../Plans/stage-e-mirrorrust-integration.md)
connects the existing Stage E engines to `~/Repos/MirrorRust` through the
prepared Mirrors compiler's `mirrorrust-v1` target.

Status 2026-10-01: the first stage is implemented and its two-fixture
[integration record](stage-e-mirrorrust-integration-validation.json) passes.
The broader Stage E replay campaign and report integration remain open.

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

The first corpus uses the existing five-node machine-state and four-block IR
examples. It checks transport, admission, binding ownership and actual-engine
observations. Broader generated scenarios, mutation sensitivity and result/CLI
acceptance remain separate Stage E obligations. Neither this integration nor
fixture replay proves ISA semantics or universal Rust refinement.
