# Workload performance design and qualification

## Context and follow-up

**Status.** Canonical measurement design, benchmark usage, investigation
optimizations and dated qualification. The 2026-10-07 native investigation
campaign met its exact Windows CLI and separate Linux phase budgets; earlier
LLVM and over-budget native records remain historical.

**Why this document exists.** The [investigation contract](investigation-design.md)
requires useful latency without losing captured evidence, possible origins or
query identity. Backend replacement and capture replacement each need their
own measurements.

**What this document establishes.** Fixed-query measurement and optimization
invariants, benchmark and reproduction interfaces, native process/cache
mechanisms, and source-bound results with failures and successors preserved.

**Where to go next.**

- [Completed original workload plan](../../Plans/completed/priority-4-workload-performance-plan.md)
  — historical LLVM query, budget and equivalence checks.
- [Windows replacement plan](../../Plans/i4-windows-repin.md) — independent capture
  identity and retained timing failure.
- [Investigation performance plan](../../Plans/i4-performance-implementation.md)
  — D0–D3 measured optimizations and exact-query qualification.
- [Investigation qualification repair](../../Plans/completed/investigation-correctness-fixes.md#1-enforce-the-windows-i4-latency-condition)
  — enforcement of the Windows total-query budget.
- [Backend design](bap-analysis-core-design.md) — production ownership and separate
  native-backend qualification under its own timing policy.
- [Semantic assurance](semantic-assurance.md#universal-rust-refinement-boundary)
  — universal proof and retired ISA boundaries.

**What remains unresolved.** Each record qualifies only its recorded source,
tools, dependency snapshot, host and corpus. Original Electron evidence does
not qualify the replacement backend/capture; fixed-budget investigation and
BAP's unlimited policy remain separate. No worst-case latency, historical
execution, root cause or packaged cross-platform release follows. Later code
changes require fresh or complete identity-verified evidence.

For the wider context, see the [documentation map](../documentation-map.md).
The original measurement decision dates to **2026-09-29**; its stage names
remain only in plan/evidence identities.

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
| Qualified real-capture query after effect/control blockers are classified | Investigator workload through the supported CLI; seek at least 64 decoded starts and a meaningful slice | Without a qualifying larger capture, release-scale behavior remains unqualified |
| Existing four-node minidump fixture | Stable end-to-end regression and startup-cost reference | Too small to motivate graph-solver optimization by itself |
| Synthetic linear, loop, join, opaque-call and dense-alias graphs at bounded growing sizes | Isolate graph and reaching-definition scaling | Does not measure reading, decoding or reporting |

Two measurements answer different questions. **End-to-end CLI time** includes
process startup, opening/validating the dump, local discovery and the selected
native backend, analysis, rendering and publishing text/DOT/JSON. The original
campaign measured LLVM MC launches; later BAP runs identify their own helper
and runtime costs. Measure it with a prebuilt release binary and fresh output
destination. **Stage measurements**
locate cost in reader/materializer, decoder, core and report; they may extend
the `bench` feature but must use the same query facts. `AnalyzerMetrics` records
actions, incoming evaluations, full edge scans, transfer evaluations and
reaching-set sizes. The benchmark allocator counts allocation requests and
cumulative requested bytes in its own process, not peak live memory or external
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
The first [measurement record](../../evidence/Ariadne/priority-4-20260929-validation.json)
is bounded by the initial 34-node real capture. The
[2026-09-30 qualification and optimization stage](../../Plans/completed/priority-4-workload-performance-plan.md#2026-09-30-qualification-run)
used a larger Windows Electron capture, exact control bindings, a frozen
scanning reference and successive measurements for the accepted historical
performance decision. The later BAP and investigation qualifications linked
above apply to their own sources and workloads.

## Benchmark harness

The root `bench` feature enables five deterministic synthetic graph families
and an optional pinned Windows minidump. `AnalyzerMetrics` and a benchmark-only
allocator observe cost without changing public results or the fixed schedule.

```sh
ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" \
  cargo run --offline --locked --features bench \
  --release --bin ariadne-bench -- 128 3 minidump
```

Arguments are node count, repetitions and optional literal `minidump`; output
is CSV. Synthetic timing includes validation/analysis; minidump timing includes
reading, decoding, preparation and analysis. External helper allocations are
excluded. The `real_minidump` binary measures open, preparation, analysis and
three-format rendering for a frozen external query. Run it through
[`tools/measure_priority4.py`](../../tools/measure_priority4.py), which pairs
stage counters with repeated CLI publication and synthetic families.

A real-capture checker's `--qualification` is required: node count alone cannot
close the workload gate. Completed data survives later-size timeouts.
`compare_schedule DUMP DECODER ENTRY_HEX SEED_HEX` compares every public
transition and the completed result against the frozen scanning engine. Cache
operation counts describe less work while the visible schedule remains equal.

## Investigation performance

The [D0–D3 plan](../../Plans/i4-performance-implementation.md) was implemented
from baseline `44413f8` and qualified on **2026-10-07** for the exact 98-start
Windows query below. The dump, entry/fault/access, checksum producer, weak
memory/call alternatives, report meaning and budgets stayed fixed. Captured
bytes remain authoritative; no PE substitution, concrete-producer selection,
crash-register branch inference or skipped evidence validation is allowed.

The diagnosis baseline measured **5,463.647 ms** median with one warm-up/five
release repeats, identical reports and 98 starts. Profiler medians were
reference decoding **1,909.410 ms**, native dataflow **1,756.914 ms**, slicing
**410.580 ms**, and approximately **39 ms** combined binding/explanation/rendering.
CPU probes attributed 970–1,020 ms to dataflow and 220–260 ms to slicing,
implicating transport/validation and serialization as well as computation.
These profiler samples were diagnostic, not qualification.

The ranked hypotheses were repeated decoder setup, full-state per-action
traffic, native predecessor rescanning, then explanation rendering. The small
incremental explanation phase ruled out the last as the primary cost. The
normal release explanation CLI and full regression evidence decide acceptance.

### Independent decoder lifetime

The pinned LLVM helper already reads until EOF and flushes before the next
stdin read; an unchanged-process three-batch probe took **23.447 ms**. BAP now
reuses one checked reference process per snapshot/target. The same helper bytes,
checked header and protocol-2 rows remain; standalone LLVM decoding stays
one-shot and supplies no production effect fallback.

Bounded line/frame sizes, stdout/stderr queues, deadlines, exact batch
addresses/counts and lifetime executable-identity checks remain mandatory.
Malformed, missing, unsolicited or trailing rows poison and reap the session.
Publication requires clean EOF/exit; cross-snapshot/target reuse is rejected.
The regression runs real Backend batches and counts actual decoder launches.

### Native caches and validation

The reuse change reduced complete reference preparation to **47–55 ms**.
Probes still observed **93.55 MB** of native responses per query; after immutable
row caching, response-string construction took **707.863 ms** and writes
**57.447 ms** in one CPU probe. Bounded JSON chunks avoid large intermediate
copies while carrying every full observation within existing frame limits.
Query-owned immutable reaching-row and attribution encoding avoids repeated work.

For decoded site `a`, cached outgoing definitions equal
`GenMay(a) union filter(not Must(a), Reaching(a))`. Incoming definitions equal
entry origins at decoded roots plus outgoing sets of decoded non-call
predecessors, including summary edges. Enabled sites are exactly those whose
incoming set is not a subset of their reaching set; choosing the minimum
canonical VA preserves scheduling. `Propagate(a)` refreshes only `Outgoing(a)`,
its local destinations' incoming sets, and affected enabled memberships.
Discovery completes before these caches initialize; unavailable/unreachable
starts do not allocate definition caches. Observations remain complete.

Rust reuses exact-equal, previously validated reaching rows only while their
decoded-site domain remains valid. Exact frame bytes are retained and parsed
for full read-only/rejected-operation equality checks; Rust never recomputes
native state with its own solver. Protocol extensions require explicit contracts
and hostile-frame controls preserving finish, read-only and action-count behavior.

Every compiled runtime pin is still read/hashed at both constructor and
helper-start boundaries using bounded streaming workers, one per file in the
finite pin. The resulting library digest supplies the existing receipt without
a duplicate read. Damage to any pinned file must reject preparation.

The diagnostic CLI median fell to **1,673.048 ms** with stable reports. The
separate qualification below checked the normal CLI, Linux phase, original
hashes, native replay/mutations and I5 regressions. Cache equalities are
source-level invariants exercised by replay, not universal refinement proofs.

## Windows investigation replacement

The **2026-10-05** re-pin selected an existing partial Windows AMD64 Crashpad
capture as `crashpad-windows-checksum-98-i4-v1`; no new host crash was generated.
It replaces the unavailable original Electron artifact as the active I4
obligation under the [replacement plan](../../Plans/i4-windows-repin.md).
The original manifest and failed flags remain unchanged.

| Input/query | Exact pin |
| --- | --- |
| Dump | 217,936 bytes; SHA-256 `1bd80af7a739471a7026776bfb37cbbe5953d01ad122e7cf7db0392f84da0b0a` |
| Matching PE | 428,032 bytes; SHA-256 `00906b04af5dfcfff66b15657e81c08152f3e49479820bf084123c41286fc89e` |
| Discovery entry | `0x00007ff7382f4840` |
| Fault/seed | `0x00007ff7382f49b4`, `mov dword ptr [rcx], 5` |
| Independent producer | `0x00007ff7382f49b1`, `mov rcx, rax` |
| Access/workload | index `0`; 98 starts; 379 captured function bytes |

The [active case](../../evidence/Ariadne/investigation-windows-workload-case.json)
and [independent inspection](../../evidence/Ariadne/i4-windows-capture-inspection.json)
bind raw exception/context fields, every function byte, forward instruction
boundaries and checksum `0x4bea2`. PE bytes are comparison evidence only.
The [capture recipe](../../native/crashpad-demo/README.md) distinguishes this
workload from the smaller I5a question.

The [23-entry input bundle](../../evidence/Ariadne/bap-windows-workload-inputs.tar.gz)
SHA-256 is `8ef47d751829680caa4d9a852e3b9c9d6f2906150a7d9bfec8f96b3487f63222`.
Materialization verifies the entire capture/PE/witness/build/source inventory,
rejects unsafe members and requires explicit dump overrides to match the pin.
The [old Electron manifest](../../evidence/Ariadne/priority-4-real-capture-case.json)
remains byte-identical historical evidence.

The [re-pin record](../../evidence/Ariadne/i4-windows-repin-validation.json)
passed capture/producer checks and **17/17** investigation gates, stable
sources/tools, repeated reports and expected producer evidence. Its one-warm-up,
five-repeat native explanation CLI median was **4,774.451 ms** against **2,000 ms**:
`repinPassed=true`, `fullI4RealCaptureAcceptance=false`. The separate Linux
reference phase met 250 ms. Correctness, base CLI, or BAP's unlimited policy
could not substitute for the failed Windows explanation-CLI clause.

Its nested core qualification passed 20 gates with 632 source files and 1,355
archive entries; I5a passed 14 gates and both controlled capture modes under
1,500 ms CLI / 10 ms phase limits. Those narrower successes did not close I4.
The later qualification below closes the same fixed-budget clause.

## Reproduction and retained evidence

The re-pin campaign used the read-only
[MirrorRust wrapper](../../tools/with_mirrorrust_snapshot.py), manifest SHA-256
`f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56`:

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/qualification-deps/mirrorrust-i5a-complete-20261004 \
  --sha256 f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56 -- \
  python3 tools/check_investigation.py
```

Default measurement materializes the active Windows bundle.
`--windows-dump` on `tools/measure_investigation.py`, or `ARIADNE_I4_WINDOWS_DUMP`,
selects only an exact matching copy. `--skip-windows` is implementation-only
and cannot grant full I4 acceptance. Workload v3 binds the case ID/digest;
legacy records, incomplete inventories, the narrower aggregate `passed` flag
and process exit success cannot override `fullI4RealCaptureAcceptance`.

The [865-entry evidence archive](../../evidence/Ariadne/i4-windows-repin-evidence.tar.gz)
and [manifest](../../evidence/Ariadne/i4-windows-repin-evidence-manifest.json)
retain 18,012,236 bytes of exact sources, inspection, pin, nested records, raw
CSVs and report bundles. Runner paths map to archive members; accepted earlier
core/I5a bundles remain under `2026-10-05-before-i4-repin` history directories.

## Native investigation qualification

The **2026-10-07** [qualification record](../../evidence/Ariadne/i4-performance-qualification.json)
accepts the exact replacement query and finite regression corpora under the
sealed dependency view. Completion independently reverified current identities
and every archive member; it retained the runtime campaign rather than rerunning it.

| Requirement | Recorded result | Fixed criterion |
| --- | --- | --- |
| Native-default release Windows explanation CLI | **1,692.696 ms median** | 2,000 ms |
| 34-start Linux reference binding + explanation + rendering | **182.924 ms sum of medians** | 250 ms |
| Native schedule across six runs | 99 recovery + 102 dataflow + 15 slice actions | Baseline 216 actions |
| Native reports across six runs | Baseline SHA-256 preserved | Exact equality |
| Full I4 real-capture acceptance | `true` | All applicable gates and identities |

Windows measured samples, excluding the **1,671.475 ms** warm-up, were
**1,688.915; 1,706.412; 1,650.545; 1,727.445; 1,692.696 ms**. Linux phase medians
were binding **1.366548**, explanation **95.504280**, rendering **86.053299 ms**.
The phase contract uses their sum and the Rust reference analyzer; diagnostic
native profiles or base CLI results cannot substitute for the normal release
explanation-mode measurement.

Raw [CLI](../../evidence/Ariadne/i4-performance-cli.csv),
[phase](../../evidence/Ariadne/i4-performance-phase.csv) and
[native profile](../../evidence/Ariadne/i4-performance-native-phases.csv) samples
remain byte-exact. Prior re-pin and diagnosis baselines remain historical.
The [rejected-attempt manifest](../../evidence/Ariadne/i4-performance-history/2026-10-07-rejected/evidence-manifest.json)
retains phase failures of **261.578** and **252.488 ms**, with a **2,117.911 ms**
Windows CLI result in the second attempt; their failure flags are unchanged.

Nested I5b passed **18/18** gates, native-core adoption **20/20**, I5a **14/14**,
and Stage 1/investigation **17** each, including input/effects, typed replay,
models and mutations. Native generated replay, algorithm/boundary mutants and
all 15 I5b mutants passed. Ignored native tests actually exercised decoder reuse
and damage to every runtime pin. Root/core-only tests, fmt, all-feature/all-target
Clippy and layout passed in those exact-source records. Old I5a/default outputs
and all 216 native actions stayed equal across six runs.

The [controlled I5a record](../../evidence/Ariadne/i4-performance-i5a-controlled.json)
binds current source/tool/dependency and sample/prerequisite identities:
partial/full CLI **417.978 / 457.633 ms** against 1,500 ms; phase
**1.044 / 1.068 ms** against 10 ms. No criterion was waived.

The [accepted archive](../../evidence/Ariadne/i4-performance-evidence.tar.gz)
contains **3,625** verified entries including **712** source inputs, nested
regression/core archives, baselines, samples, outputs and dependency manifest.
SHA-256: `4a5f05ea02317a3a21a56ad177796f794f87661a3a143694ce80e5d0ea5039d8`.
Nested archives verified 919 regression and 1,432 native-core entries; twelve
tool digests and the dependency identity matched. The
[evidence manifest](../../evidence/Ariadne/i4-performance-evidence-manifest.json)
and [completion audit](../../evidence/Ariadne/i4-performance-audit.json)
separate retained-byte verification from the original runtime campaign.

## Reproduction and retained-byte verification

The passing performance campaign used MirrorRust manifest SHA-256
`a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`, origin
`08d189f18a76845dc15dd23b79424809ae27f406`. The archive retains exact source,
manifest and origin; the wrapper requires the selected view read-only at the
normal dependency path.

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/i5b-dependency-snapshot \
  --sha256 a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854 -- \
  python3 tools/check_i4_performance.py \
    --regressions target/i4-regressions-20261007-v5/report.json \
    --profiles-root target/i4-performance-20261007 \
    --output target/i4-performance-new-run
```

This requires exact-current complete regressions, native helpers/runtime/model
tools and baseline profiles. After source/tool changes, rerun `tools/check_i5b.py`
through the wrapper with new output, capture and baseline directories using the
[I5b qualification procedure](zero-base-offset-design.md#retained-qualification). Missing prerequisites or
changed identities cannot qualify. Temporary paths describe the exercised
environment; archive member names do not guarantee those paths still exist.

Materialize Git LFS before hashing:
`git lfs pull --include="evidence/Ariadne/i4-performance-evidence.tar.gz"`.
Verify report/archive digests against the manifest, then every member hash;
a pointer or manifest flag alone is insufficient.

## Historical baseline (2026-09-29)

Recorded **2026-09-29 10:16 CST**. The
[source-bound progress report](../../evidence/Ariadne/stage-b-f-validation.json)
recorded 19 implementation/formal/benchmark gates. Its
[raw baseline CSV](../../evidence/Ariadne/stage-f-baseline.csv) and 83 source hashes
identify this historical measurement, which is not a release-scale performance
guarantee. Retain the original report and CSV unchanged.

At this baseline, the dependency-free core exposed `AnalyzerMetrics` without
changing its analysis state or schedule. The [benchmark harness](#benchmark-harness)
counted allocation calls and cumulative requested bytes with a benchmark-only
allocator. It reported analyzer actions, incoming evaluations,
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
The synthetic scan counts showed that the baseline `incoming()` implementation
scanned the entire frozen edge set for each destination. Loops and dense may-definition
sets dominated this small baseline. Those observations motivated a candidate
optimization but did not qualify one. The four-node minidump alone was too
small to justify changing the solver. The later
[2026-09-30 performance delivery](workload-performance-design.md#historical-llvm-workload-qualification) supplied
a larger representative query, accepted a predecessor/cache optimization and
checked the preserved visible schedule. Its LLVM-backed result remains separate
from later native BAP qualification.

The baseline CSV, the 83 source SHA-256 entries, gate commands, and the exact
temporary log locations are retained in the linked report. Allocation counts
are cumulative allocation requests, not peak live heap or allocator-independent
memory usage. CPU scheduling, LLVM process startup and cold-cache effects were
not normalized. The larger-workload optimization question was subsequently
answered for the historical LLVM query. The [universal Rust refinement boundary](semantic-assurance.md#universal-rust-refinement-boundary)
remains open independently. Neither this baseline nor its performance successor
qualifies a replacement backend.

## Historical LLVM workload qualification

Qualified **2026-09-30** under the
[completed workload plan](../../Plans/completed/priority-4-workload-performance-plan.md).
The [delivery record](../../evidence/Ariadne/priority-4-validation.json) retains
qualification, source-bound regressions and before/after report comparisons.
The initial 34-node Linux result remains separately in the
[2026-09-29 record](../../evidence/Ariadne/priority-4-20260929-validation.json).
The original Electron artifact is now unavailable; commands below describe the
historical pinned path and require its exact artifacts and source/tool identity.

### Captured workload

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

Eight path blockers gained [source-reviewed ordinary control](operand-effects-design.md#eight-ordinary-control-bindings-2026-09-30)
with fully opaque effects under `user64-effects-v1.2`. Calls and stack effects
remain uncertain. Two later `INT3` sites remain unsupported after the seed,
so the recovery scope is partial. This is a possible predecessor slice, not
an execution trace or proof that the faulting store committed.

### Same-query release measurements

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

### Bounded synthetic scaling

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

### Conformance and decision

The [schedule comparison](../../evidence/Ariadne/priority-4-schedule-validation.json) matches all
277 visible transitions and the completed real-query result against the
[frozen scanning implementation](../../tests/support/scanning_engine.rs).
All 256 generated requests also compare every visible state with that
reference, alongside their independent graph/path oracles. Text, DOT and JSON
hashes are byte-identical across the three performance checkpoints.

The [recorded integration result](../../evidence/Ariadne/current-integration-validation.json) covers
the existing root/input/native/formal/IR checks, MBT replay, effect and reader
mutations, formatting and Clippy. The effect registry is exercised on both
Windows and Linux. The new control bindings retain all possible prior origins
and have no definite replacements; shape/prefix and checked-header negatives
remain enforced. The Linux Breakpad regression now reaches opaque POP/RET
with a closed local graph; its effect uncertainty remains explicit. The
Windows regression retains its later unsupported-control obligation.

The recorded decision accepted both measured changes for this exact LLVM query.
Further optimization needs new workload evidence. Later typed replay has its
own finite acceptance; universal Rust refinement remains open and independent
ISA proofs are retired. This historical result does not qualify BAP.

### Historical reproduction

Keep the raw dump and matching companion external to tracked files. Build the
release CLI and benchmark binaries, plus the pinned native helper, using the
[input build guide](file-reader-design.md#build-and-verification). With the
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
