# Priority 4 design: workload-based performance decision

## Context and follow-up

**Status.** Measurement and equivalence criteria; each backend needs its own evidence.

**Why this document exists.** [Initial baseline](stage-f-proof-and-performance.md) lacked a representative larger real-capture performance decision.

**What this document establishes.** The design fixes artifact/query identity, latency budget and repeated timing before optimization. It requires preserved results and visible scheduling alongside phase and resource measurements.

**Where to go next.**


- [Active investigation performance](i4-windows-repin-validation.md) — binds the new 98-start Windows question to its preserved 2,000 ms CLI limit and measured failure.

- [Completed historical plan](../../Plans/completed/priority-4-workload-performance-plan.md) — freezes workloads, budgets and optimization checks.
- [Historical delivery](priority-4-performance-validation.md) — records the measured optimization.
- [BAP qualification](../../Plans/bap-integration.md) — records the separately qualified native backend and its unlimited timing policy.
- [Investigation qualification repair](../../Plans/completed/investigation-correctness-fixes.md#1-enforce-the-windows-i4-latency-condition) — applies the fixed Windows total-query budget to the investigation acceptance decision; see its [validation record](investigation-correctness-validation.md) for the exercised tier.

**What remains unresolved.** Each backend and workload needs its own qualification. Each result stays bound to its original backend and query. [Native BAP qualification](bap-core-qualification.md) measures its own corpus under an unlimited timing policy. The separately [re-pinned Windows I4 question](i4-windows-repin-validation.md) retains its fixed 2,000 ms limit and has a later [passing native performance qualification](i4-performance-validation.md).

For the wider context, see the optional [documentation map](../documentation-map.md).

Design decision, **2026-09-29**. The scoped
[Priority 4 implementation plan](../../Plans/completed/priority-4-workload-performance-plan.md)
applies this design. It builds on the current
[Stage F baseline](stage-f-proof-and-performance.md), the separate
[`bench/` harness](modules/bench.md), and the supported
[minidump CLI/report contract](stage-c-report-schema.md). The long-term Rust
refinement proof remains independent of this performance decision.

## Decision to be made

Measure whether a representative Windows/Linux AMD64 minidump investigation
has a reproducible delay or resource problem. If it does, identify the stage
and operation responsible before changing code. A faster synthetic graph alone
does not justify a solver or decoder change for investigators. A no-change
decision with measured evidence is a valid result.

The unit of comparison is one **frozen query**: exact dump SHA-256, platform,
entry and seed VAs, preparation limits, decoder build/protocol/target, effect
ruleset/catalogue and output formats. Source revision, host, toolchain and
measurement settings are part of the measurement record. Before/after claims
compare the same query and host. Results from different hosts or artifact
versions remain separate observations.

## Workload set and measurement layers

| Workload | Purpose | Claim limit |
| --- | --- | --- |
| Priority 1 real-capture query, after Priority 2 classifies path blockers | Investigator workload through the supported CLI; seek at least 64 decoded starts and a meaningful slice | Without a qualifying larger capture, release-scale behavior remains unqualified |
| Existing four-node Stage B minidump | Stable end-to-end regression and startup-cost reference | Too small to motivate graph-solver optimization by itself |
| Synthetic linear, loop, join, opaque-call and dense-alias graphs at bounded growing sizes | Isolate graph and reaching-definition scaling | Does not measure reading, decoding or reporting |

Two measurements answer different questions. **End-to-end CLI time** includes
process startup, opening/validating the dump, local discovery and native LLVM
MC launches, analysis, rendering and publishing text/DOT/JSON. Measure it with
a prebuilt release binary and fresh output destination. **Stage measurements**
locate cost in reader/materializer, decoder, core and report; they may extend
`bench/` but must use the same query facts. The core's `AnalyzerMetrics` record
actions, incoming evaluations, full edge scans, transfer evaluations and
reaching-set sizes. The benchmark allocator counts allocation requests and
cumulative requested bytes in its own process, not peak live memory or LLVM
helper allocations. Use an external measurement for process peak resident
memory where available.

Retain one warm-up and at least five measured repetitions, median and spread,
raw observations, graph sizes and operation counts. Keep cold-process CLI
numbers separate from warm in-process stage numbers. Preserve source/artifact
hashes and resource-limit outcomes, including timeouts. The previous
`stage-f-baseline.csv` remains a historical result, not a file to overwrite.

## Optimization decision and invariants

Set and record the investigation's practical latency/resource budget **before**
editing performance-sensitive code. An optimization candidate requires a
qualifying real workload that exceeds that budget or hits a documented limit,
plus stage/counter evidence for a specific bottleneck. If the real workload is
within budget, record no change. If no larger real capture exists, record an
inconclusive real-workload decision even if synthetic graphs are slow.

Candidate remedies follow the measured cause. A private predecessor index is
plausible only if repeated full-edge scans dominate. Decoder batching or a
persistent helper is plausible only if launch overhead dominates. Dense-alias
cost needs its own profile before selecting a representation change. Select
one change and a concrete before/after improvement target before editing.

The change must preserve the analyzer's externally observable `step()`
schedule, graph, reaching definitions, slice, obligations, byte provenance and
report identities for fixed input. Benchmark-only counters and timers must not
alter semantic state. A change that genuinely needs a different public result
or replay contract is a separate design decision, not an incidental speedup.
After an implementation change, compare exact fixed-input results and replay
traces, then rerun the applicable core, minidump, MBT and mutation gates.

## Decision record

Publish raw CSV and a short validation record with frozen workload identities,
host/tool versions, distributions, stage/counter attribution, selected budget,
decision, and any remaining limits. For an optimization, include before/after
results on the same workloads and source-bound conformance evidence. For no
change, state the measured range in which the current implementation is
acceptable. Neither result asserts a universal performance bound, formal Rust
refinement, or AMD64 instruction-step correctness.
The first [measurement record](priority-4-performance-validation.md) is
bounded by the initial 34-node real capture. The
[2026-09-30 qualification and optimization stage](../../Plans/completed/priority-4-workload-performance-plan.md#2026-09-30-qualification-run)
uses a larger Windows Electron capture, exact control bindings, a frozen
scanning reference and successive measurements before making the final
performance decision.
