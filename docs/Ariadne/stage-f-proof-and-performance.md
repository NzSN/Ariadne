# Stage F proof boundary and measured core baseline

## Context and follow-up

**Status.** Open universal refinement boundary and historical benchmark baseline.

**Why this document exists.** [Executable correspondence](../implementation.md) provides deterministic model actions but not a checked Rust refinement proof.

**What this document establishes.** The record distinguishes executable model correspondence and finite tests from a universal Rust refinement proof, and supplies an initial repeatable cost baseline.

**Where to go next.**

- [Performance follow-up](priority-4-performance-validation.md) — addresses the historical real-workload measurement gap.
- [Finite conformance checks](../../mbt/stage-e/README.md) — supply bounded evidence while universal proof remains open.
- [Assurance decision](semantic-assurance.md) — keeps this proof boundary separate from retired ISA work.

**What remains unresolved.** Finite conformance checks do not prove the Rust implementation correct for every valid request. A universal refinement proof remains open, and adapter facts remain premises. The historical workload optimization later addressed the representative-performance gap, but not the proof gap.

For the wider context, see the optional [documentation map](../documentation-map.md).

Recorded **2026-09-29 10:16 CST** for Stage F proof boundary.
The [source-bound progress report](../../evidence/Ariadne/stage-b-f-validation.json) passed 19
implementation/formal/benchmark gates. Its [raw benchmark data](../../evidence/Ariadne/stage-f-baseline.csv)
is a baseline, not a release-scale performance guarantee or a Rust refinement
proof.
The [Priority 4 workload-performance implementation plan](../../Plans/completed/priority-4-workload-performance-plan.md)
specified the real-capture measurement and optimize/no-change decision, later
recorded in the [historical performance delivery](priority-4-performance-validation.md).
The [Priority 4 design](priority-4-workload-performance-design.md) defines the
workload identity, measurement layers and decision boundary.

## What is established and what is open

The Rust `Analyzer` executes the transition phases of `Specs/Ariadne.tla` on
validated, owned inputs. Generated-request regressions and the prior six-fixture
MBT gate (12 complete traces, 168 matched states, five engine mutants) provide
bounded conformance evidence. This run rechecked that existing gate within the
effects regression. TLA+ and Rust still need an explicit proved representation
relation from finite TLA+ addresses/sets/maps to `u64` and ordered Rust
collections, plus obligations for input validation, initialization, each
`step()` action, the deterministic schedule as an allowed TLA+ choice, result
views and finite termination. A proof about an abstract machine does not by
itself connect compiled Rust to that proof. The decoder, effect rules, captured
bytes and semantic projection remain additional trusted or checked boundaries.
The independent Stage D ISA campaign is [retired](semantic-assurance.md);
retirement does not establish a proof of BAP lifting.
**No universal Rust refinement claim is made.**

## Baseline method and observations

The dependency-free core now exposes `AnalyzerMetrics` without changing its
analysis state or schedule. The separate [`bench/`](../../Cargo.toml)
package counts allocation calls and cumulative requested bytes with a
benchmark-only allocator. It reports analyzer actions, incoming evaluations,
full edge scans, applicable transfer evaluations, maximum reaching-definition
set at one site and total fixed-point reaching entries. The synthetic runs
measure request validation plus analysis, excluding request construction. The
minidump row includes reader, native decoder launches, preparation and core
analysis; its allocation counter does **not** include allocations inside the
external LLVM helper processes. Timings are process-local wall time.

At 128 decoded synthetic nodes, three optimized runs gave these median
observations on Linux/WSL with Rust 1.96.0:

| Workload | Median elapsed | Edge scans | Transfer evaluations | Allocation calls | Final reaching entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| Linear | 15.2 ms | 1,064,768 | 8,255 | 168,303 | 2,176 |
| Loops | 169.3 ms | 3,554,752 | 27,862 | 1,505,506 | 5,963 |
| Joins | 31.7 ms | 1,333,056 | 10,335 | 323,721 | 4,224 |
| Opaque calls | 15.7 ms | 1,198,912 | 8,255 | 168,310 | 2,176 |
| Dense alias set | 194.0 ms | 1,064,768 | 8,255 | 1,683,141 | 24,640 |

The pinned Windows tool-produced minidump path (four decoded nodes) took a
median **127.6 ms** end to end, with 42 core edge scans and 9 applicable
transfers. Its input fixture SHA-256 is
`f3a0407bff881356c0128e7587c03ea9f143dbd5fee59abbe8fc5edb75ad30bf`.
The synthetic scan counts show the current `incoming()` implementation scans
the entire frozen edge set for each destination. Loops and dense may-definition
sets dominate this small baseline. That is a measured optimization candidate,
not evidence that a private predecessor index or worklist already passed
conformance. The real four-node minidump does not yet justify changing the
solver; a larger representative capture and preserved MBT schedule are needed
before an optimization decision.

The baseline CSV, the 83 source SHA-256 entries, gate commands, and the exact
temporary log locations are retained in the linked report. Allocation counts
are cumulative allocation requests, not peak live heap or allocator-independent
memory usage. CPU scheduling, LLVM process startup and cold-cache effects were
not normalized. Stage F remains **partial** until the refinement obligation is
resolved or its trusted boundary is explicitly accepted, and optimization is
supported by broader repeatable workloads and conformance reruns.
