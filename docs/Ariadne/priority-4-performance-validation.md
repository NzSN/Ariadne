# Priority 4: qualified workload and performance decision

## Context and follow-up

**Status.** Historical LLVM-backed optimization evidence; not current BAP qualification.

**Why this document exists.** [Measurement design](priority-4-workload-performance-design.md) requires a fixed query, budget and preserved results.

**What this document establishes.** The historical optimization reduced the selected 98-instruction Windows query below its fixed median budget while preserving the tested schedule and reports; synthetic measurements recorded broader bounded behavior.

**Where to go next.**


- [Active Windows I4 result](i4-windows-repin-validation.md) — records the separate replacement query and its unmet unchanged 2,000 ms ceiling.

- [Benchmark guide](modules/bench.md) — documents the measurement harness.
- [Native BAP qualification](bap-core-qualification.md) — measures and qualifies the later backend on its own corpus; this historical LLVM result supplies no native performance acceptance.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. The original capture remains historical; it does not qualify the later [native BAP backend](bap-core-qualification.md). The separately [re-pinned Windows I4 question](i4-windows-repin-validation.md) exceeds its unchanged CLI budget. No worst-case performance guarantee follows.

For the wider context, see the optional [documentation map](../documentation-map.md).

Qualified **2026-09-30** under the
[design](priority-4-workload-performance-design.md) and
[implementation plan](../../Plans/completed/priority-4-workload-performance-plan.md).
**Priority 4 is complete for the frozen Windows Electron query below.**
The [delivery record](../../evidence/Ariadne/priority-4-validation.json) retains the real-capture
qualification, before/after measurements, source-bound regression evidence,
report comparisons and remaining limits. The initial 34-node Linux
measurement is retained separately as
[historical evidence](../../evidence/Ariadne/priority-4-20260929-validation.json).

## Qualifying captured workload

The external `f13d18cd-9ade-4eff-947c-15a649b636fa.dmp` is a historical Windows
Electron application access violation, not a generated graph fixture.
The [case manifest](../../evidence/Ariadne/priority-4-real-capture-case.json) pins its 2,028,400 bytes
and SHA-256 `4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86`.
Its companion has SHA-256
`8ed58d015ad328da011e0bc889c2fa431cc13944610a5ead8b9a353bb91fe9a9`.
Dump and PE match RSDS GUID `{119B016B-57EF-43EC-4C4C-44205044422E}`, age 1,
timestamp `0x69f08473` and image size `0xd8e7000`.

The matching PE runtime-function table independently establishes entry RVA
`0x48652d0`, with the function ending at RVA `0x486543f`. Its entire 367-byte
body is captured. Forward disassembly supplies 101 instruction boundaries;
all bytes match MemoryList entry 156, whose 512-byte range starts at
`0x7ff6451d528f`, dump file offset `0x1ed710`. The companion establishes the
entry and boundaries; the CLI reads code exclusively from the dump.

The selected entry `0x7ff6451d52d0` reaches exception RIP
`0x7ff6451d530f`, reviewed `MOV64mr [RCX],RAX`. The earlier reviewed
`MOV64rm RCX,[RDI+0x20]` at `0x7ff6451d530b` remains a possible origin of all
eight RCX byte cells before the seed. The query has **98 captured decoded
instructions, 113 edges and a 19-node backward slice**, with no missing seed.
The [qualification record](../../evidence/Ariadne/priority-4-real-capture-validation.json) checks
local reachability, captured forward boundaries, cross-format agreement,
Graphviz parsing and the seed-only negative control. The
[identity/byte negative controls](../../evidence/Ariadne/priority-4-negative-controls.json) reject
wrong module identity and changed captured function bytes before publication.

Eight path blockers gained [source-reviewed ordinary control](priority-4-control-source-review.md)
with fully opaque effects under `user64-effects-v1.2`. Calls and stack effects
remain uncertain. Two later `INT3` sites remain unsupported after the seed,
so the recovery scope is partial. This is a possible predecessor slice, not
an execution trace or proof that the faulting store committed.

## Same-query release measurements

The budget was **2,000 ms CLI median**, fixed before optimization. Each
workload used one warm-up and five measured repetitions with prebuilt release
binaries, default reader/preparation limits and fresh report directories.
The measured host was WSL2 Linux `6.6.87.2`, Intel Core i5-1240P, 12 logical
CPUs, Rust `1.95.0`, and the pinned LLVM MC `20.1.2` helper. CLI time includes
opening, discovery, analysis and publication of text/DOT/JSON. Stage timings
include benchmark allocation counters and omit process startup/publication;
they must not be substituted for CLI timings.

| Measurement | Before | Predecessor cache | Cache + checked helper |
| --- | ---: | ---: | ---: |
| CLI median | 3,845.7 ms | 2,712.3 ms | **1,787.6 ms** |
| CLI measured range | 3,756.3–4,163.8 ms | 2,667.2–2,830.1 ms | 1,680.0–2,450.0 ms |
| Peak RSS median | 270,000 KiB | 270,084 KiB | 270,180 KiB |
| Instrumented preparation median | 1,734.4 ms | 1,675.9 ms | 704.1 ms |
| Instrumented core median | 2,288.4 ms | 259.1 ms | 193.0 ms |
| Instrumented rendering median | 1,047.3 ms | 1,048.3 ms | 899.9 ms |
| Incoming evaluations | 8,561 | 170 | 170 |
| Incoming edge scans | 967,393 | 188 | 188 |
| Analyzer actions | 277 | 277 | 277 |

The private predecessor index and incoming-set cache avoid recomputing
unchanged predecessor inputs; predecessor growth invalidates local successors.
The sorted one-action schedule remains unchanged. The checked helper returns
its exact version/target header and unchanged protocol-2 rows in one invocation
per batch, removing a separate version process. No global decoder cache or
persistent process was added. Legacy helper modes remain available; the Rust
adapter requires the checked mode, so the helper must be rebuilt with it.

The final CLI median improved **53.5 percent** and meets the predeclared
budget. One measured run exceeded 2 seconds; this is a median qualification,
not a worst-case latency guarantee. RSS remained essentially unchanged.
Benchmark allocation counters exclude allocations in LLVM helper processes.

Raw data and identities are retained for all three checkpoints:

| Checkpoint | CLI CSV | Stage CSV | Synthetic CSV | Measurement record |
| --- | --- | --- | --- | --- |
| Before | [CSV](../../evidence/Ariadne/priority-4-20260930-before-cli.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-before-stage.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-before-synthetic.csv) | [JSON](../../evidence/Ariadne/priority-4-20260930-before-validation.json) |
| Cache | [CSV](../../evidence/Ariadne/priority-4-20260930-solver-cli.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-solver-stage.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-solver-synthetic.csv) | [JSON](../../evidence/Ariadne/priority-4-20260930-solver-validation.json) |
| Final | [CSV](../../evidence/Ariadne/priority-4-20260930-after-cli.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-after-stage.csv) | [CSV](../../evidence/Ariadne/priority-4-20260930-after-synthetic.csv) | [JSON](../../evidence/Ariadne/priority-4-20260930-after-validation.json) |

## Bounded synthetic scaling

All five families completed one warm-up and five repetitions at 128, 256 and
512 nodes after optimization. The before-change 512-node measured suite
reached its 180-second bound; its
[partial output](../../evidence/Ariadne/priority-4-20260930-before-synthetic-512-measured-partial.csv)
and [outcomes](../../evidence/Ariadne/priority-4-20260930-before-synthetic-outcomes.json) remain limit
evidence rather than a completed baseline. The initial September 29 timeout
and `stage-f-baseline.csv` also remain intact.

| Family | 128 nodes, final median | 256 nodes, final median | 512 nodes, final median |
| --- | ---: | ---: | ---: |
| Linear | 2.4 ms | 7.6 ms | 49.6 ms |
| Loops | 22.1 ms | 261.0 ms | 5,293.9 ms |
| Joins | 3.4 ms | 18.9 ms | 184.6 ms |
| Opaque calls | 2.0 ms | 8.6 ms | 46.6 ms |
| Dense aliases | 22.1 ms | 119.9 ms | 749.9 ms |

Synthetic loops still expose scaling risk. These numbers are not limits on
larger real captures, and no speedup factor is claimed against the timed-out
512-node baseline.

## Conformance and decision

The [schedule comparison](../../evidence/Ariadne/priority-4-schedule-validation.json) matches all
277 visible transitions and the completed real-query result against the
[frozen scanning implementation](../../tests/support/scanning_engine.rs).
All 256 generated requests also compare every visible state with that
reference, alongside their independent graph/path oracles. Text, DOT and JSON
hashes are byte-identical across the three performance checkpoints.

The [current integration record](../../evidence/Ariadne/current-integration-validation.json) covers
the existing root/input/native/formal/IR checks, MBT replay, effect and reader
mutations, formatting and Clippy. The effect registry is exercised on both
Windows and Linux. The new control bindings retain all possible prior origins
and have no definite replacements; shape/prefix and checked-header negatives
remain enforced. The Linux Breakpad regression now reaches opaque POP/RET
with a closed local graph; its effect uncertainty remains explicit. The
Windows regression retains its later unsupported-control obligation.

**Decision:** accept the two measured performance changes for this query and
close Priority 4's larger-workload qualification. Further optimization needs
new real-workload evidence. A universal Rust refinement proof, generated
machine-state/IR replay, and formal AMD64 instruction-step acceptance remain
separate; `register-core` is still **0/49**.

## Reproduction

Keep the raw dump and matching companion external to tracked files. Build the
release CLI and benchmark binaries, plus the pinned native helper, using the
[input build guide](modules/input.md#build-and-verification). With the
exact hash-pinned artifacts available:

```sh
cargo build --offline --locked --release --manifest-path Cargo.toml
cargo build --offline --locked --release --features bench
mkdir -p tmp/priority4
run_dir=$(mktemp -d "$PWD/tmp/priority4/recheck-XXXXXX")

python3 tools/check_priority4_real_capture.py \
  --dump "$ARIADNE_PRIORITY4_DUMP" --companion "$ARIADNE_PRIORITY4_COMPANION" \
  --decoder target/ariadne-llvm-mc --cli target/release/ariadne-minidump \
  --report-dir "$run_dir/report" --validation-json "$run_dir/qualification.json"

python3 tools/measure_priority4.py \
  --dump "$ARIADNE_PRIORITY4_DUMP" --decoder target/ariadne-llvm-mc \
  --entry 0x7ff6451d52d0 --seed 0x7ff6451d530f \
  --qualification "$run_dir/qualification.json" \
  --latency-budget-ms 2000 --synthetic-sizes 128,256,512 \
  --output-dir "$run_dir/measurements"
```

Set the two artifact variables to the exact dump and companion paths. All
output destinations must be new. A missing artifact is an unavailable gate;
a new dump/build requires its own manifest and boundary evidence. The
measurement tool preserves completed workloads if a later size times out and
requires a matching source/tool/query qualification record before closing the
real-workload target.
