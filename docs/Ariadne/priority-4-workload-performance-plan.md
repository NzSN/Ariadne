# Priority 4 implementation plan: workload-sized performance decision

Plan dated **2026-09-29** for practical priority 4 in the
[assurance queue](practical-assurance-priorities.md). It executes the
[workload-performance design](priority-4-workload-performance-design.md)
and specializes the performance half of
[Stage F](remaining-implementation-plan.md#f--proof-boundary-and-scalability);
the separate Rust-refinement proof remains long-term research. The current
[baseline](stage-f-proof-and-performance.md) covers five 128-node synthetic graphs
and a four-node tool-produced Windows minidump, not a representative real-capture
workload.
The first [workload measurement](priority-4-performance-validation.md)
retains a 34-node real query, five-repeat 128/256-node synthetic data and a
bounded 512-node timeout. Its 64-node real-capture qualification remains open.

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
