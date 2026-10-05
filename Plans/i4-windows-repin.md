# Re-pin Windows I4 to the controlled 98-instruction capture

## Context and follow-up

**Status.** User-authorized replacement on 2026-10-05. The independently inspected
Windows Crashpad case is pinned and independently inspected for I4. All 17
investigation gates pass. Five measured native-default explanation-CLI repeats
have a 4,774.451 ms median against the unchanged 2,000 ms ceiling, so full I4
acceptance remains false. Source/tool identities and retained archives verify.

**Why this document exists.** The [investigation design](../docs/Ariadne/investigation-layer-design.md)
left I4 tied to an unavailable original Electron dump. The user now authorizes
replacing the active case instead of retaining that missing artifact as an active
obligation. This replacement keeps a real 98-instruction Windows workload.

**What this document establishes.** A new active case identity, independent
capture/PE/query witness, repeatable input materialization and an honest measured
I4 verdict. The original manifest and older records remain historical, and the
2,000 ms I4 explanation-CLI requirement stays unchanged.

**Where to go next.**

- [Delivery and validation](../docs/Ariadne/i4-windows-repin-validation.md) —
  completed re-pin, exact samples, evidence and remaining performance gap.

- [Active case](../evidence/Ariadne/investigation-windows-workload-case.json) — exact
  capture, query, provenance and fixed timing contract.
- [Independent inspection](../evidence/Ariadne/i4-windows-capture-inspection.json)
  — raw captured bytes, PE equality and producer/fault witness.
- [Investigation contracts](../docs/Ariadne/investigation-contracts.md) — meaning
  of possible producers, uncertainty and exact-query acceptance.
- [Original case](../evidence/Ariadne/priority-4-real-capture-case.json) — preserved
  historical identity, not retroactively qualified by this replacement.
- [Capture recipe](../native/crashpad-demo/README.md) — native Windows producer and
  existing independently inspected 98-instruction input bundle.

**What remains unresolved.** The qualified five-sample median exceeds the preserved 2,000 ms limit.
Correct capture/pin success does not imply full I4 performance acceptance. The
replacement does not reconstruct the original crash or establish an executed
history, UAF, object lifetime or general root cause.

## Frozen replacement contract

Use the existing real Windows AMD64 Crashpad capture with 98 reviewed instruction
starts, 379 fully captured function bytes, exact matching PE and independent
checksum/producer inspection. Analyze captured bytes only; PE supplies comparison
evidence and must not become fallback memory. Keep the existing input archive
unchanged. Its BAP unlimited policy is separate from this I4 pin's bounded policy.

Run the native-default release explanation CLI on the exact entry, fault site
and access index. Preserve one warm-up and five measured repeats. Require
repeatable identities, expected producer, explicit uncertainty, unchanged base
analysis and median explanation-CLI time at most 2,000 ms. Keep existing Linux
phase criteria and implementation/model/mutation gates.

## Completed execution

1. Verify the input bundle and independently inspect the raw capture/PE/witness.
2. Publish a new I4 case manifest; retain the original manifest unchanged.
3. Update measurement, acceptance and tests to consume the active I4 pin, its
   input bundle and independent inspection. Reject wrong inputs and stale records.
4. Measure the exact case and run investigation qualification under the recorded
   read-only MirrorRust snapshot. Report correctness and timing separately.
5. Retain source/tool-bound records, raw samples and a verified archive, then
   update status documents to the observed result. Do not promote over-budget
   or partial results, rewrite historical flags, or waive the fixed limit.

The current task re-pins and qualifies the new case. A production performance
change, if needed, must follow a measured diagnosis and its own validation.

## Remaining I4 performance qualification

Re-pin work is complete. The remaining acceptance task is measured diagnosis
and, if justified, a performance change on the same native-default query:

1. Retain the accepted five-sample baseline and current report identities.
2. Measure the current pipeline's decode/lifting, transport/projection, native
   recovery/dataflow/slicing, binding, explanation and rendering costs. The old
   Stage 1 reference-decoding timings do not diagnose this native workload.
3. Apply a scoped change only when those measurements identify its cost. Preserve
   capture identity, possible producers, explicit gaps and base-analysis results.
4. Re-run the exact release explanation CLI with one warm-up and five repeats,
   the 2,000 ms ceiling and complete source/tool/environment checks. Run affected
   behavior tests and applicable native, model, mutation and product qualification
   before assigning full I4 acceptance. A faster base or phase benchmark cannot
   substitute for explanation-mode CLI timing.

No performance implementation or budget change is part of the completed re-pin
or the documentation synchronization. The [current result](../docs/Ariadne/i4-windows-repin-validation.md)
remains the baseline for that separate follow-up.
