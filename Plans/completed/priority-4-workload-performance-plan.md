# Priority 4 implementation plan: workload-sized performance decision

## Context and follow-up

**Status.** Completed plan, archived; acceptance is limited to the recorded scope.

**Why this document exists.** [Motivating design](../../docs/Ariadne/priority-4-workload-performance-design.md) defines the problem and contract this plan implements.

**What this document establishes.** The historical optimization reduced the selected 98-instruction Windows query below its fixed median budget while preserving the tested schedule and reports; synthetic measurements recorded broader bounded behavior.

**Where to go next.**

- [Delivery and follow-up](../../docs/Ariadne/priority-4-performance-validation.md) — records what was exercised and which limits remain.
- [Active plan index](../README.md) — prevents completed steps from being mistaken for pending work.

**What remains unresolved.** The implementation steps below are archived, not a current task list. These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. The original capture remains historical; it does not qualify the later [native BAP backend](../../docs/Ariadne/bap-core-qualification.md). The separately [re-pinned Windows I4 question](../../docs/Ariadne/i4-windows-repin-validation.md) exceeds its unchanged CLI budget. No worst-case performance guarantee follows.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Plan dated **2026-09-29** for practical priority 4 in the
[assurance queue](../../docs/Ariadne/practical-assurance-priorities.md). It executes the
[workload-performance design](../../docs/Ariadne/priority-4-workload-performance-design.md)
and specializes the performance half of
[Stage F proof boundary](../../docs/Ariadne/stage-f-proof-and-performance.md);
the separate Rust-refinement proof remains long-term research. The current
[baseline](../../docs/Ariadne/stage-f-proof-and-performance.md) covers five 128-node synthetic graphs
and a four-node tool-produced Windows minidump, not a representative real-capture
workload.
The first [workload measurement](../../docs/Ariadne/priority-4-performance-validation.md)
retains a 34-node real query, five-repeat 128/256-node synthetic data and a
bounded 512-node timeout. Its 64-node real-capture qualification remained open
at that checkpoint.
The later [2026-09-30 delivery](../../docs/Ariadne/priority-4-performance-validation.md) closes
that gate for a 98-instruction Windows capture, retains before/after evidence,
and meets the unchanged 2,000 ms median budget.

## 2026-09-30 qualification run

Audit the available Windows Electron captures against a companion's exact
RSDS GUID/age, image size and timestamp. Use the matching PE runtime-function
table as an independent entry witness and compare its forward-disassembled
function bytes with capture; companion bytes must never enter the analyzer.
The selected candidate is `f13d18cd-9ade-4eff-947c-15a649b636fa.dmp`, with
runtime-function RVA `0x48652d0` and exception RIP RVA `0x486530f`.

This path reopens Priority 2 for eight exact forms: `PUSH64r`, `POP64r`,
`ADD32rm`, `ADD64rm`, `MOV8mi`, `CMP8mi`, `ADD32i32`, and `CMP32i32`.
Review their pinned AMD sources and actual native operand/prefix shapes.
Admit only ordinary control, keeping all effects opaque with empty definite
replacements. Add shape/prefix negative controls and run the existing effect,
minidump, MBT and mutation gates before accepting this larger path.

Retain a separate hash-pinned case manifest and checker for this external
Windows capture. Require at least 64 actually decoded captured instructions,
an entry-to-seed local route and an earlier possible address-register producer;
an exploratory control projection is never acceptance evidence. Then measure
the release CLI and identical stage query with one warm-up and five repeats.
Keep the predeclared **2,000 ms** CLI budget. Preserve completed workload data
if a later synthetic size times out, retaining that size as a bounded limit
result. Update the decision and assurance queue only after the gates close.

The qualified 98-instruction query exceeds that budget in the initial release
runs (roughly 3.8 seconds). Instrumented core analysis takes roughly 2.3 seconds,
with 8,561 incoming evaluations and about 20 million cumulative allocation
requests. Before changing the solver, freeze this baseline. The selected
optimization is a private local-predecessor index and cached incoming sets,
invalidated whenever a predecessor's reaching set grows. Keep the same sorted
scan and one-action `step()` behavior. Compare every transition with the
retained scanning implementation, including the exact real request, then
compare text/DOT/JSON hashes for this same query. Target at least a 50 percent
core-time reduction and the existing 2,000 ms CLI median; retain any residual
budget miss explicitly rather than changing the budget.

The first solver change reduces instrumented core time by about 89 percent,
but the CLI median remains roughly 2.7 seconds. Preparation remains about
1.7 seconds because each batch launches separate version and decode processes.
The second measured change combines the exact version/target response and
unchanged protocol-2 rows in one checked helper invocation. Retain the legacy
helper modes, reject absent/wrong checked headers, and preserve raw row bytes,
caps, process-error handling, timeout behavior and all report hashes. Keep the
same 2,000 ms target and rerun both platform matrices and protocol negatives.

## 1. Freeze workloads and measurement contract

Start with the accepted or explicitly partial, hash-pinned real minidump query from
[priority 1](priority-1-real-capture-plan.md), after
[priority 2](priority-2-path-driven-effects-plan.md) has classified material blockers.
Seek at least one captured query with substantially more than four decoded nodes (target
**64 or more**) and a meaningful predecessor slice; if no such capture is available,
report the real-workload evidence gap and do not call the release-scale decision
complete. Retain the existing four-node fixture as a stable regression, not the scale
target.

Keep the existing deterministic synthetic families—linear, loops, joins, opaque calls
and dense aliases—and measure bounded sizes 128, 256 and 512, extending only while
time/resource limits allow. Record exact graph shape, node/edge/location counts, source
and artifact hashes, query VAs, limits, OS/host, CPU, Rust profile/version, pinned LLVM
helper identity and build command. A timeout or limit is a result, never silently
discarded.

## 2. Measure the supported CLI path and locate cost

Use prebuilt release binaries and a fresh output directory per run. Repeatedly invoke
the same minidump CLI path that produces text, DOT and JSON, so the end-to-end number
includes input opening, local discovery, native decoding, core analysis and report
publication. Measure process wall time and peak resident memory externally where
available. Extend the existing `bench/` harness only to expose comparable stage timings
and its current action, predecessor-edge-scan, transfer, reaching-set and allocation
counters for the **same query identities**. State clearly that its allocator does not
count memory allocated in LLVM helper processes.

Run at least one warm-up and five measured repetitions per workload. Report median and
spread, not one debug-build time; separate cold-process/end-to-end results from any warm
in-process stage measurements. Compare work counts before interpreting timing. Make the
benchmark write a dated raw CSV plus a concise decision record, and preserve the
existing `stage-f-baseline.csv` as a historical baseline rather than overwriting it.

## 3. Decide whether to optimize

Inspect representative real runs first. If no investigator-visible delay or resource
problem appears, publish a **no-change** decision with the observed limits and stop. If
a bottleneck is reproducible, choose one narrow change tied to the counters: for
example, a private predecessor index if repeated full edge scans dominate, or decoder
batching/session work if launches dominate. Record the pre-change cost and a concrete
latency/resource budget and improvement target before editing the solver or
transport. Do not change
`Analyzer::step()`'s observable schedule, result sets, provenance, or report schema
merely to improve a benchmark; a necessary contract change requires its own review.

For a solver change, compare complete transition traces and final graph, reaching
definitions, slice and obligations on the same fixed requests. For any path change,
compare text/DOT/JSON identity and semantic content on pinned dumps. Re-run root/input
tests, formatting and Clippy, the existing generated-request and MBT replay gates, the
five engine mutants and relevant minidump/effect mutations. A performance gain cannot
compensate for a semantic or evidence regression.

## 4. Acceptance record

Retain `priority-4-performance-validation.md` and raw CSV with commands, repeat
distributions, operation counts, source/artifact identities, limitations and the
optimize/no-change decision. If code changed, show before/after measurements on the same
host/workloads and passing source-bound conformance gates. If no qualifying larger real
capture exists, retain the synthetic data but mark practical workload qualification
**open**. Neither a faster solver nor a stable benchmark establishes a universal Rust
refinement or AMD64 instruction-step proof.
