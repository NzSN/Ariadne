# Stage E: first MirrorRust integration stage

## Context and follow-up

**Status.** Completed plan, archived; acceptance is limited to the recorded scope.

**Why this document exists.** [Motivating design](../../docs/Ariadne/stage-e-mirrorrust-design.md) defines the problem and contract this plan implements.

**What this document establishes.** This first-stage plan delivered generated typed ports and the initial stateflow/IR fixture replay. The later Stage E completion expanded that initial integration to a broader finite acceptance campaign.

**Where to go next.**

- [Delivery and follow-up](../../docs/Ariadne/stage-e-completion.md) — records what was exercised and which limits remain.
- [Active plan index](../README.md) — prevents completed steps from being mistaken for pending work.

**What remains unresolved.** The implementation steps below are archived, not a current task list. These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. Finite conformance checks do not prove the Rust implementation correct for every valid request. A universal refinement proof remains open, and adapter facts remain premises.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Prepared 2026-10-01. Design: [typed replay integration](../../docs/Ariadne/stage-e-mirrorrust-design.md).

This stage connects the two existing Stage E Rust engines to the sibling
`MirrorRust` checkout. It does not close the broader Stage E acceptance campaign.

Completed 2026-10-01. The [retained validation record](../../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json)
contains four complete Stage E fixture traces and 20 matched observations,
both pre-factory wrong-digest rejections, seven supporting tests, formatting
and Clippy checks. The restored core gate also passed its 12 traces,
168 matched states and five mechanical mutation checks. All six steps below
are delivered within this first-stage scope.

1. Restore the existing core harness against MirrorRust's negotiated error API
   and rerun its unchanged corpus and mutation gate.
2. Add an independent `mbt/stage-e` Cargo package with compiler-generated
   `mirrorrust-v1` ports for machine-state and LLVM IR. Keep the core dependency-free.
3. Instantiate the authoritative Stage E models and existing example inputs.
   Select the lowest enabled address for machine-state propagation. Export
   every mutable field and the public derived result observations.
4. Generate type witnesses, reviewed interface locks and typed bindings using
   Apalache and the existing prepared Mirrors compiler. Preserve raw witnesses;
   encode the full address map losslessly, including empty entries.
5. Implement observers over actual Rust engines and deferred negotiated
   factories. Test initialization, transitions, malformed actions, repeated
   initialization, completion, and field-preserving observations.
6. Exercise both fixture traces through real negotiated MirrorRust replay and
   require wrong-digest rejection before adapter creation. Record source/tool
   identities and clarify the bounded fixture scope.

Further Stage E work: expand generated input/trace coverage, mechanical engine
mutants and retained mismatch evidence, recovery/native-adapter coverage, and
independent report/CLI integration. Fixture replay alone is not Stage E completion.
