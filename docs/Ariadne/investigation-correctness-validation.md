# Investigation qualification and truncation repairs

## Context and follow-up

**Status.** Implemented and validated on 2026-10-02 within the recorded
fixture/Linux tier. All 17 investigation gates passed with 123 stable source
hashes. Full original-Windows I4 qualification remains unavailable.

**Why this document exists.** Review of the first-question implementation found
two failures in the [investigation contract](investigation-contracts.md): full
Windows acceptance could ignore its latency budget, and claim-budget exhaustion
could create invalid producer references instead of a partial answer.

**What this document establishes.** The repairs recompute Windows qualification
from bound CLI samples and preserve explanation invariants during truncation.
The [fix plan](../../Plans/completed/investigation-correctness-fixes.md) defines the scope
and regression criteria; this record distinguishes exercised checks from full
real-Windows acceptance.

**Where to go next.**

- [Updated contracts](investigation-contracts.md) describe zero budgets,
  unavailable/partial truncation and the operational v2 qualification records.
- [Investigation plan](../../Plans/investigation-layer.md) retains full I4 and
  later I5–I7 capabilities as separate work.
- [Evidence guide](../../evidence/Ariadne/README.md) explains the source and tool
  identities required to reuse a recorded result.

**What remains unresolved.** No synthetic or mocked timing result qualifies the
unavailable original Windows capture. These repairs add no historical execution,
root-cause, ISA-step or universal Rust refinement claim.

The [documentation map](../documentation-map.md) remains optional navigation.

## Windows acceptance

The workload record retains individual warm-up and measured CLI times, artifact
and query identities, selected question and report digest. Both measurement and
acceptance use the same decision function, which recomputes the median from raw
measured samples and checks the reported summary. Full acceptance requires the
release explanation CLI for the pinned Windows query, at least five measured
repeats after warm-up, and a median at most 2,000 ms. It also requires passing
gates and stable source/tool identities.

Fast base-mode timing, phase-only timing, malformed or insufficient samples,
wrong identities and legacy records cannot substitute. The narrower `passed`
field retains its exercised implementation/fixture/Linux meaning. The separate
Windows outcome distinguishes unavailable, invalid, over-budget and met results.

## Explanation limits

The builder reports whether each fact/claim was admitted. Producers are appended
only after their required records fit, and dependent expansion stops on budget
exhaustion. Retained claims can be reused without consuming another claim slot.
The strict explanation validator is unchanged.

If the selected site's evidence cannot fit, the result is unavailable and
truncated, with no selected address or origins. A retained supported address
with incomplete expansion yields a partial truncated answer. Zero budgets are
valid; invalid question sites or indices still fail independently of budgets.

## Validation scope

Focused regressions cover the original 9,000 ms/2,000 ms false-acceptance case,
threshold equality, malformed/missing measurements, gate/source failures, and
the actual measurement and acceptance runners using controlled subprocesses.
These are decision-logic tests, not real Windows measurements.

Rust API tests cover the reproduced claim/evidence failures, invalid questions,
480 combinations of zero/one/boundary budgets across straight-line and cyclic
fixtures, strict validation, serialization round trips and all report formats.
Before/after comparison on Linux/Windows fixtures, a NOT-chain fixture and the
retained controlled Linux capture preserves all 24 normal report bytes.

The [source-bound repair record](../../evidence/Ariadne/investigation-correctness-validation.json)
retains all 17 passing investigation gates, including the nested 12-gate Stage E
and 11-gate minidump campaigns. All 13 investigation/producer mutants were
detected, including the two new truncation faults. Two controlled Python mutants
also failed the unchanged observers: bypassing the latency threshold and trusting
the reported median instead of measured samples. Compile failures/timeouts were
not credited as mutation sensitivity.

Root checks passed: formatting, default tests (72 passed, 53 ignored), core-only
tests (45 passed, 22 ignored), all-feature/all-target Clippy and release build.
The nested campaigns separately exercised their required native, replay and
mutation tests; ignored default tests were not counted as executed.

Fresh controlled-Linux measurements recorded approximately 159 ms combined
binding/explanation/rendering phase median against the unchanged 250 ms ceiling.
Normal CLI medians were approximately 1,355 ms without explanation and 1,535 ms
with explanation. These numbers apply to the retained query and this run only.

The [evidence manifest](../../evidence/Ariadne/investigation-correctness-evidence-manifest.json)
binds the [archive](../../evidence/Ariadne/investigation-correctness-evidence.tar.gz),
including detailed gate logs, controlled regression/mutation checks, measurements
and default-output comparisons. No raw minidumps or build caches are included.
Historical evidence files remain unchanged. `fullI4RealCaptureAcceptance` is
false, with the original Windows capture explicitly listed as missing.
