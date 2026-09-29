# Stage D first-case execution checkpoint

Checked **2026-09-29 13:42 CST** against the
[Stage D implementation plan](stage-d-register-core-implementation-plan.md).
The [source-bound progress report](stage-d-progress-validation.json) passed its
five component gates with **242 stable source hashes**. This is D0 plus bounded
D1–D3 work, **not D4 case acceptance**: `register-core` remains **0/49**.
The later [assurance priority decision](practical-assurance-priorities.md)
retains this evidence within a long-term formal research track; it does not
turn 0/49 into a prerequisite for practical minidump analysis.

## Delivered within the first candidate

| Plan step | Evidence now retained | Boundary |
| --- | --- | --- |
| D0 baseline | [Baseline manifest](stage-d-baseline.json) pins the three AMD PDF hashes, profile/form/case digests and 23 initial source files; inventory, forms and default profile checks pass. | Initial profile remains 49 paired bodies, zero accepted semantic cases. |
| D1 source and payload | [Reviewed MOV register source](stage-d-mov-reg64-imm32-review.md) and [native observation report](stage-d-mov-observation.json) cover `AMD64-F-0503-R` under both Windows/Linux LLVM 20.1.2 targets. REX.W, signed imm32, extended R8, 66h precedence and negative register/memory/LOCK/ModRM alternatives are checked. | This establishes reviewed candidate shape, not universal decoded-byte-to-form correspondence or architectural execution. |
| D2 body and bounded boundary | `Specs/AMD64RegisterCoreProfileChecks.tla` and `lean/AMD64/RegisterCoreProfileChecks.lean` check a CPL-3 signed register-MOV body, selected GPR/flag frames, and seven-byte fallthrough under explicit fetch/event assumptions. Separate `AMD64RegisterCoreFaultChecks.tla` and Lean rollback lemmas check a zero-commit #UD witness for an inapplicable LOCK prefix. | The LOCK validation rejection and the #UD witness are not yet composed into one proved dispatcher. Fetch/event assumptions remain trusted; `fallthrough-applied` is not named retirement. |
| D3 finite projection | `AMD64RegisterCoreProjectionChecks.tla` and Lean's matching finite check model eight disjoint RAX byte cells. A successful normal continuation may/must-define all eight; a mixed rollback-fault outcome cannot justify a must-kill. | The abstract cell set is source-selected in the fixture; no universal proof yet derives it from every validated register-MOV execution alternative. |
| Negative controls | [Nine isolated mutations](stage-d-mutations.json) are rejected for lost sign extension, wrong next IP/destination, fault commit, missing REX.W and an over-strong fault projection. | These mutants exercise bounded assertions and proofs, not all eight case obligations. |

The pinned Lean 4.33.1 release archive used in this run has SHA-256
`890afd185370f85666025b883914ab4f4b339136f8c96167b69cfb62aecaf235`.
The full default AMD64 suite passed **70 Apalache typechecks, 33 TLC
configurations, 73 Lean build jobs, the combined axiom audit (11,021
declarations, 3,148 theorems), and 50 Python integrity tests**. Fifteen real
LLVM-native effects tests passed. The suite reported that its checked source
hashes stayed stable. A checker naming repair in `Specs/check-amd64.sh` makes
configs already named `*Checks.cfg` select that explicit Checks module, so
the existing register-core fixture is included rather than skipped.

## Acceptance still required

The `Specs/AMD64/coverage.json` ledger still contains **no semantic-case
entries**, and `user64-coverage.json` still cites none for this case. D2 must
prove a complete case-specific successful/faulting instruction boundary for
arbitrary admitted destination/immediate payloads, including exact decoding,
state validity, effects, fault priority/commit/restart and the profile's
asynchronous assumption. D3 must prove the conservative analyzer projection
from those architectural alternatives, with explicit TLA+/Lean
correspondence. Only then may D4 bind source-hashed evidence and close the
eight required obligations for one case. D5 repeats case-specific closure for
the other 48. D6 qualifies the **49/49** milestone.

`python3 tools/amd64_profile.py check` passes integrity. The required
`--require-milestone register-core` gate exits 1 with its expected pending
diagnostic; it was recorded separately and never counted as a passing
acceptance gate. The accepted no-trust `UnknownInstructionFallback` remains in
force. Nothing here certifies a Rust ISA executor or changes the current
minidump input scope.
