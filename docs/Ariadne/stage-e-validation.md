# Stage E machine-state and native LLVM IR validation

Current acceptance: [Stage E completion](stage-e-completion.md), with
[source-bound replay, mutation, native and report evidence](stage-e-completion-validation.json).
The sections below retain the earlier component validation.

Validated **2026-09-29 10:16 CST** in the source-bound
[B–F progress report](stage-b-f-validation.json). This is implementation and
focused conformance evidence for [Stage E](remaining-implementation-plan.md#e--implement-the-other-two-formal-analysis-machines),
not a completed model-based replay or runtime ISA proof. The separate
[result contracts](stage-e-report-contracts.md) define their reporting seams.

## Abstract machine state

[`ariadne::machine_state`](../../src/machine_state.rs) implements the finite
`AriadneMachineState.tla` propagation machine over a frozen, endpoint-closed
local CFG and an adapter-supplied state relation. It validates state domains,
entry facts, source-site may-write frames, running/terminal statuses, edge
membership and adapter obligations before initialization. Its deterministic
lowest-VA schedule takes one model action per `step()`, reaches a finite least
fixed point, retains all structural edges, and classifies absent edges as
infeasible **only** at a reached, certified-complete source after completion.

The recovery handoff copies decoded nodes and local effects, keeps `summary`
edges, rejects a local edge to an undecoded endpoint, and retains call edges,
byte provenance and recovery obligations in separate context. It does not use
captured crash-time registers to prune earlier paths.

The Rust tests reproduce the formal five-node fixture's four transitions and
five states exactly, including the feasible taken edge, model-relative
infeasible fallthrough, terminal witness and unreached node. Further tests
cover validation failures, incomplete semantics, summary/call separation,
loops and equal-valuation state IDs with distinct transitions. An independent
pair-reachability oracle agrees with the reached state-ID pairs. Apalache
typechecking/model checking and TLC on the existing fixture passed.

## Direct native LLVM IR

[`ariadne::llvm_ir`](../../src/llvm_ir.rs) validates and executes the separate
`AriadneLLVMIR.tla` slice machine over block CFG, instruction SSA, predecessor-
sensitive phi inputs, conservative memory predecessors and visible call
obligations. The [`ariadne-ir`](../../ir/Cargo.toml) package hashes owned `.ll`
or `.bc` bytes, gives them to a secure temporary snapshot, and accepts only
the versioned output of the **LLVM 20.1.2** native helper after that helper
parses and verifies the module. The helper binary SHA-256 for this run was
`c3cddb345ceec46018b1936aab65c377cc15c762b15f09dfcec59ae763f7de66`.

The source [`diamond.ll`](../../ir/tests/fixtures/diamond.ll) has SHA-256
`3dc51d62e4448958beb960afb9eea9bc7ff9484ec79a617f3637c58ed2ca6dcf`.
Its LLVM 18-assembled backward-compatible bitcode fixture has SHA-256
`bec3302fd1aa62cc39df8dc7351efc9fe472ffa70496dd47a513ef506b2cade6`;
both were **parsed and verified by LLVM 20.1.2** in the native gate. The
diamond's return seed slices through both phi alternatives and both possible
stores; the indirect call remains target-incomplete. Negative tests reject
invalid IR, a false verifier claim, missing phi input and duplicate protocol
rows. A second verifier-accepted function with two phi nodes checks that both
remain valid and contribute to the slice. Apalache typechecking/model
checking and TLC on the formal four-block
fixture passed.

The native adapter currently bounds a function to 4,096 instructions and
100,000 read/write predecessor pairs. Its memory relation includes all
potentially writing instructions for each memory-reading instruction, plus
`unknown-memory-alias` obligations; this is deliberately imprecise. Direct
calls get an exact callee target; indirect calls remain open. There is no
machine-code lifting or IR/machine address correspondence.

## Completed Stage E acceptance

The [completion record](stage-e-completion-validation.json) closes the scoped
Stage E acceptance clauses. The generated campaign has 32 inputs, 64 complete
traces and 326 matched observations. Fifteen mechanical engine mutants produce
genuine model mismatches through the same observers and generated bindings.
The report/CLI tests preserve identities, structural graph context, uncertainty
and native verifier admission; Graphviz independently parses their DOT output.

The earlier [first MirrorRust integration record](stage-e-mirrorrust-integration-validation.json)
remains a historical two-fixture checkpoint. Completion is finite conformance
and reporting acceptance relative to supplied semantic premises. It does not
prove those premises, a universal Rust refinement or AMD64 ISA semantics.
