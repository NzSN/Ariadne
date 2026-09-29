# Stage D register-core acceptance audit

Audited **2026-09-29 10:16 CST** against the active
[`amd64-user64-v1` profile](../amd64-user64.md). This is a checkpoint for
[Stage D](remaining-implementation-plan.md#d--close-the-scoped-amd64-semantics-gate-separately),
not a promoted instruction case.
The [standalone implementation plan](stage-d-register-core-implementation-plan.md)
sets the first-case and 49-case acceptance sequence.
The later [D0–D3 progress record](stage-d-progress.md) adds checked source,
fixture and mutation evidence without changing this **0/49** audit outcome.
The [assurance priority decision](practical-assurance-priorities.md) now treats
the intact 49-case gate as a long-term formal purpose, separate from practical
minidump delivery.

The source-reviewed register-only `MOV reg64, imm32` candidate
`register-core:AMD64-F-0503-R` has source-form SHA-256
`d45a228c0720624d73a267ced2b728de85f0058ef94601f61e459329f8fbaa29`.
The form records encoded imm32, sign-extended semantic width 64, a register
destination, rFLAGS preservation and a LOCK-triggered #UD. Its paired TLA+/Lean
body and Rust `MOV64ri32` effect binding are **components**, not a completed
instruction step. The exact profile case has no accepted `semantic_cases`
reference and retains its instruction-boundary/fault/frame/projection
obligation. The Stage A memory alternative `AMD64-F-0503` belongs instead to
`ram-data` and has a separate unresolved source-form binding.

The active profile requires closure of eight case obligations: decoded-form
legality, operand-payload binding, state validity, effects/flags/frames,
fault/commit behavior, instruction boundary, TLA–Lean correspondence, and
conservative analysis projection. The supplied Rust effects and Stage E
stateflow/IR engines do not discharge these ISA obligations. An end-to-end
case must first bind the decoded payload to the exact source-form hash,
compose the successful/faulting boundary and checked state frames, and record
source-hashed positive and negative TLA+/Lean evidence. Then the other 48
register-core cases must receive the same case-specific closure before the
milestone gate can pass.

`python3 tools/amd64_profile.py check` passed integrity in the B–F run.
`python3 tools/amd64_profile.py check --require-milestone register-core`
returned exit 1 with **49 paired bodies, 0/49 verified** and the expected
pending-milestone diagnostic. The 72 near-control-stack and 156 RAM cases
also have zero verified steps. No coverage ledger or profile hash was changed.
This preserves the accepted no-trust unknown-instruction fallback.
