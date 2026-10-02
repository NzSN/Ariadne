# Stage E completion plan

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Prepared 2026-10-01 against `518ed9e`. Design:
[Stage E replay and reporting](../../docs/Ariadne/stage-e-mirrorrust-design.md).
The [Stage E delivery record](../../docs/Ariadne/stage-e-completion.md) documents the result.

Status **complete, 2026-10-01**, within the finite conformance/report scope.
The [retained completion record](../../evidence/Ariadne/stage-e-completion-validation.json)
passes all 12 gates with stable source hashes: 32 generated inputs, 64 complete
traces, 326 matched observations, 15 genuine engine mutation mismatches,
verifier/recovery handoffs and independently parsed CLI reports. The minidump
regression record is reused only after every bound source hash matches.
All six implementation steps below are delivered. Scope update 2026-10-02:
Stage D is [retired](../../docs/Ariadne/semantic-assurance.md); Stage F remains separate.
The retained record above predates the qualification-runner changes.

## Acceptance

| Clause | Required evidence |
| --- | --- |
| Validators and transitions | Existing contract negatives plus typed input/identity failures; completed request domains remain validated before initialization |
| Generated replay | Deterministically generated finite machine-state and IR requests, authoritative TLA+ action traces, all mutable fields and public derived views compared through generated MirrorRust ports |
| Case coverage | Machine joins, loops, empty roots, sparse/high addresses, equal-valued distinct IDs, incomplete semantics, summary edges, unreached sites and fault/return/stop outcomes; IR phi alternatives, loops, memory/call uncertainty, empty seeds and exit/exception edges |
| Mutation sensitivity | Mechanical edits to temporary copies of real engines; unchanged observers/bindings; wrong propagation, premature completion, infeasibility, terminals, phi/dependency/control/call/obligation mutations fail as genuine `StepMismatch` results |
| Handoffs | Frozen recovery preserves full graph/provenance and excludes call-only stateflow edges; pinned native LLVM verifies `.ll`/`.bc` before request admission |
| Reports and CLI | Separate versioned JSON/text/DOT envelopes with exact identities and uncertainty; optional trusted semantic input on minidump CLI; direct IR CLI; positive and malformed/identity/output failures checked before publication |
| Retained gate | Installed ModelMirrors, client, compiler, model, corpus, implementation and report identities recorded; hashes stable; relevant core/minidump/native regression gates pass |

## Implementation sequence

1. Define a small optional `reports/` crate for strict Stage E input codecs and
   independent result envelopes; keep the root core dependency-free. Public
   machine addresses use canonical full-width hex. Semantic relations and
   completeness assertions remain explicit caller-supplied premises.
2. Generate normalized case inputs and TLA+ input tables independently of Rust
   execution. Replay wrappers instantiate the original specifications; only
   machine-state scheduling selects the lowest enabled address. Add a case-ID
   initializer to generated ports so repeated traces reset the correct request.
3. Generate and preflight complete traces for every case, then run negotiated
   replay using the installed ModelMirrors executable. Check all actions and
   their adjacent pairs across the corpus, repeated reset, digest rejection
   and actual port ownership.
4. Run temporary engine mutants through the same corpus, recording each first
   mismatch. Build each evaluator to a distinct artifact location and verify
   binding/observer hashes, avoiding stale mutation binaries in a shared target.
5. Add the optional minidump stateflow handoff and direct IR report CLI. Verify
   semantic snapshot binding, native verifier rejection, cross-format agreement,
   preserved structural edges, uncertainty and transactional publication.
6. Run the completion gate, retain source-bound evidence, and update status in
   the design, roadmap, remaining plan and checkpoints. Completion is bounded
   conformance/report acceptance; Stage F universal Rust refinement remains
   separate, and retired Stage D is outside the gate.

No new ISA executor, PE/ELF reader, IR lifting, crash-history reconstruction or
interprocedural call/return matching is introduced. Commit/push is a separate
publication step after the completed changes are reviewed.
