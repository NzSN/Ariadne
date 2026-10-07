# I4 performance on the native machine-code investigation path

## Context and follow-up

**Status.** Measured design on 2026-10-07, based on `44413f8`. D0–D3 are implemented and qualified for the exact 98-start capture/query. The [validation](i4-performance-validation.md) records 1,692.696 ms against the unchanged 2,000 ms CLI ceiling and source-bound regression/archive checks.

**Why this document exists.** The [I4 replacement plan](../../Plans/i4-windows-repin.md)
requires a measured diagnosis of the native pipeline before a performance patch.

**What this document establishes.** A preserved baseline, ranked/falsifiable
hypotheses, phase evidence and two bounded optimization seams for machine-code
bug debugging, while preserving captured instruction/dataflow evidence.

**Where to go next.**

- [Qualification result](i4-performance-validation.md) — exact samples, preserved outputs and verified evidence.
- [Scoped implementation plan](../../Plans/i4-performance-implementation.md) —
  D0–D3 execution, regression and exact-query acceptance.
- [Frozen investigation contract](investigation-contracts.md) — separate 2,000 ms
  Windows CLI and 250 ms Linux phase clauses.
- [Existing I4 record](i4-windows-repin-validation.md) — immutable prior capture,
  producer/query and over-budget source-bound history.

**What remains unresolved.** The recorded query meets its full-CLI and separate Linux phase budgets. Qualification is finite and source/tool/dependency-bound; later changes require renewed evidence. No executed path, general latency bound or root cause is inferred.

## Baseline and hypotheses

The retained exact-query loop measured 5,463.647 ms median, one warm-up/five
release repeats, with 98 starts, expected producer and identical report bytes.
The phase profiler measured median reference decoding 1,909.410 ms, native
dataflow 1,756.914 ms, slicing 410.580 ms, and binding/explanation/explanation
rendering approximately 39 ms combined. Native CPU probes attribute roughly
970–1,020 ms to dataflow and 220–260 ms to slicing, leaving transport/validation
and serialization as significant costs. Initial profiler samples are diagnostics,
not final qualification.

Ranked predictions: repeated decoder/lifter preparation dominates if reusing the
decoder removes launch cost; full-state per-action traffic dominates if transport
timings remain high after reducing helper computation; native solver rescanning
dominates if caching predecessor work reduces helper CPU; explanation rendering
dominates only if its incremental phase is large. The measured explanation phase
does not support the last hypothesis as the primary cost.

## Preserve the contracts

The dump, entry/fault/access query, 98-start discovery, checksum producer, weak
memory/call alternatives, normalization, report meaning and fixed budgets remain
unchanged. Do not replace captured bytes with PE bytes, infer an earlier branch
from crash-time values, select a concrete producer or skip evidence validation.
The Rust reference, stepwise native replay and retired ISA boundary remain intact.

## First optimization: independent decoder lifetime

The existing pinned LLVM helper already reads rows until EOF and flushes before
its next stdin read. A direct three-batch probe completed in 23.447 ms through
one unchanged process. Reuse one checked-protocol reference process per BAP
snapshot/target instead of launching one per discovery batch. Keep the existing
wire rows, helper bytes and semantic producer unchanged.

Bound line/frame sizes, stdout/stderr queues and request/exit deadlines. Validate
exact row counts/addresses and executable identity across the whole preparation.
Require clean EOF shutdown before publication; failures poison and reap the
process. Cross-snapshot/target reuse is rejected. Standalone one-shot decoding
remains available. The regression must exercise real Backend batches and count
actual decoder process launches, not mirror an internal implementation detail.

## Native follow-up

Remeasure after the decoder change. If native costs still prevent acceptance,
profile computation versus observation/attribution serialization and Rust
validation. Prefer caching immutable predecessor/static evidence work or
structurally unchanged native observation rows while preserving every model
action, full typed validation and canonical observations. Any transport/protocol
extension requires a separate explicit contract and hostile-frame controls;
it cannot silently change finish/read-only/action-count semantics.

The complete exact explanation CLI, frozen old outputs and full source/tool/
dependency qualification decide acceptance, not the diagnostic profiler.

## Measured implementation

The repeated decoder cost fell to roughly 47–55 ms for the complete preparation,
including reference identity checks, after reusing one process. Native probes
showed the full response path transmitting about 93.55 MB per query. After
immutable row caching, a CPU probe still attributed 707.863 ms to response string
construction and 57.447 ms to writes. Keeping bounded JSON chunks avoids large
intermediate frame copies; it preserves all full observations and evidence.

Derived predecessor/outgoing/incoming/enabled-action caches belong to one native
query. Updates recompute affected destinations and retain canonical minimum-VA
scheduling. The Rust adapter can reuse previously validated, exact-equal reaching
rows only while their decoded-site domain remains valid. Transport retains exact
validated frame bytes and parses them for unchanged-state checks on read-only or
rejected operations. It never computes a native state through the Rust solver.

Runtime validation reads and hashes every file in the existing compiled pin,
using independent streaming workers with bounded buffers. Both constructor and
helper-start validation remain; the library digest from that validation supplies
the existing semantic receipt without a duplicate read/hash. Tampering with any
pinned file must still reject preparation.

The diagnostic release CLI median is 1,673.048 ms, with 98 starts and byte-stable
reports across repeats. The completed D3 campaign separately checks the normal CLI, Linux phase,
original report hashes, native model/replay/mutations and I5 regressions;
[validation](i4-performance-validation.md) records its passing result.

### Cache invariants

For decoded site `a`, the cached outgoing set remains exactly
`GenMay(a) union filter(not Must(a), Reaching(a))`. The incoming cache equals
entry definitions at decoded roots plus outgoing sets of decoded non-call
predecessors; summary edges participate. The enabled set contains exactly sites
whose incoming definitions are not a subset of their reaching definitions.
Selecting its smallest canonical VA preserves the original schedule.

`Propagate(a)` changes only `Reaching(a)`, so only `Outgoing(a)`, incoming sets
at its local destinations, and enabled membership at `a` and those destinations
need refresh. Recovery initializes these derived caches only after discovery,
using decoded sites; unavailable/unreachable starts do not allocate definition
caches. The abstract reaching state and emitted observations remain complete.
These are source-level invariants exercised by replay, not a universal refinement
proof or an independent ISA proof.
