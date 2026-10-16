# Current frame-to-frame outcome — dump03958

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

**Two frames are recovered. Frame-to-frame path enumeration is unavailable, and no path search ran.** Zero returned paths does not mean that no path exists.

This is the latest completed dump run, **2026-10-14**, probe `dump-20261014T121127`. Inspected on **2026-10-15**: all **711 recorded source-file hashes match the current checkout**. This inspection did not rerun the dump or builds.

Dump: `dump_03958DA4FCA844A786262A1053` · thread **23668** · requested transition **frame 1 → frame 0** · requested maximum **10 paths**.

## Recovered frame relationship

| Frame | Role | Function entry | Frame PC | Stack pointer |
| --- | --- | --- | --- | --- |
| 1 | Caller, recovered by unwind | `0x00007ff7744033a0` | `0x00007ff77440410d` — unwound return PC | `0x000000bea89fa930` |
| 0 | Callee, captured context | `0x00007ff77443d960` | `0x00007ff77443dd6e` — captured PC | `0x000000bea89fa890` |

Frame 0's recovered return address is **`0x00007ff77440410d`**, read from stack slot **`0x000000bea89fa928`**. This supports the recovered stack relationship under the recorded unwind premises. The caller's final graph still lacks the active call anchor needed to connect the two local graphs for path enumeration.

## Exact path result

| Field | Result |
| --- | --- |
| `available` | `false` |
| `coverage` | `unavailable` |
| `returned_count` | **0** |
| `stop_reason` | `missing-or-ambiguous-active-call-anchor` |
| `enumeration_exhausted` | `false` |
| `truncated` | `false` |
| Search states expanded | **0** |
| Search edges scanned | **0** |
| Frontier remaining | **0** |
| Search elapsed | **0 ms** |

This is a failure to establish the query's required call anchor before searching. It is not an exhausted search, a ten-path cutoff, or a proof that the caller cannot reach the callee.

## Supporting control-flow analysis

| Query | Candidate instruction sites | Final decoded instructions | Final edges | Candidate guard barriers |
| --- | ---: | ---: | ---: | ---: |
| Caller — frame 1 | 9,590 | 9 | 9 | 32 |
| Callee — frame 0 | 778 | 768 | 895 | 12 |

The caller's initial **MOVAPS store at `0x00007ff7744033b3`** remains `unknown`, with `normal-or-alignment-fault-unresolved`. The guard checker reports `candidate-coverage-incomplete`, so final caller recovery stops there, before recovering the active call anchor. The Windows normal-call entry premise is already supplied.

Candidate recovery made substantial progress: all **nine original jump-table candidate sets** match the captured witness, giving **64 destinations**, and all **51 previously absent starts were attempted**. Eight original certificates are complete. The original jump at `0x00007ff77440da09` and new jump at `0x00007ff77440dadd` each retain four known destinations with incomplete cyclic incoming-state coverage.

The callee retains two unresolved indirect jumps, semantic stops and work-limit residuals. Those remain relevant to later coverage; the current frame-path result stops at the missing caller anchor first.

Both completed frame analyses have **exact Rust/native normalized-request and full-state agreement**. This checks consistency of the bounded results, while the unavailable path listing remains explicit.

## Context and follow-up

**Status:** current source-matching retained result; frame recovery is available, path enumeration is unavailable. **Motivating problem:** understand what the latest dump analysis actually produced. **Contribution:** records the recovered frame relationship, exact unavailable result and the graph coverage behind it.

Read the [remaining-blockers report](ariadne-remaining-blockers-before-loop-20261015.md) for all 44 guard barriers and individual residuals, the [canonical design](../../docs/Ariadne/guarded-target-resolution-design.md) for the analysis contract, and the [active plan](../plans/completed/guarded-target-resolution.md) for the open closure gate.

Exact extracted fields: [compact result JSON](ariadne-frame-to-frame-outcome-20261015.json). Original evidence: [full frame-path report, gzip](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-paths.json.gz), [recovered frames, gzip](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frames.json.gz), and [probe summary](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/probe-summary.json).

Further unwinding stops at `unsupported-unwind-operation`, beyond the requested pair. Recovered frames and possible control-flow alternatives do not establish the executed instruction history or a root cause.
