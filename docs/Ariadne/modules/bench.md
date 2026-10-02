# Analyzer baseline benchmark

## Context and follow-up

**Status.** Measurement harness and output interpretation.

**Why this document exists.** [Measurement design](../priority-4-workload-performance-design.md) separates stage costs and ties results to fixed workloads.

**What this document establishes.** The benchmark exposes deterministic synthetic families, analyzer operation counts and optional minidump measurements. It separates observed cost from semantic output.

**Where to go next.**

- [Historical results](../priority-4-performance-validation.md) — records the measured optimization and its scope.
- [Proof boundary](../stage-f-proof-and-performance.md) — separates performance observations from universal refinement.

**What remains unresolved.** Allocation counters do not measure every external-helper allocation. Measured families and repeats do not establish universal scale or worst-case guarantees.

For the wider context, see the optional [documentation map](../../documentation-map.md).

The root package's `bench` feature enables five deterministic synthetic graph
families and, optionally, the pinned Stage B Windows minidump path. It uses
the root analyzer's operation counters and a benchmark-only allocation
counter. It does not alter the analyzer's public result or fixed schedule.
The [Priority 4 implementation plan](../../../Plans/completed/priority-4-workload-performance-plan.md)
set the captured-workload criteria for the historical optimization. The
[performance delivery](../priority-4-performance-validation.md) records its result;
the [BAP plan](../../../Plans/bap-integration.md) tracks the separate current-backend requirement.
Its [measurement design](../priority-4-workload-performance-design.md)
defines what the harness can and cannot claim.

```sh
ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" \
  cargo run --offline --locked --features bench \
  --release --bin ariadne-bench -- 128 3 minidump
```

The output is CSV. Arguments are node count, repetitions and optional literal
`minidump`. Timing includes validation and analysis for synthetic workloads;
the minidump row includes reading, native decoding, preparation and analysis.
Allocation counters exclude external helper-process allocations. See the
[Stage F baseline and proof boundary](../stage-f-proof-and-performance.md).

The separate `real_minidump` binary measures open, preparation, analysis and
three-format rendering stages for one frozen external query. Run it through
the [Priority 4 measurement tool](../../../tools/measure_priority4.py) so its
in-process counters are paired with repeated end-to-end CLI publication and
the existing synthetic graph families. The first
[validation record](../priority-4-performance-validation.md)
keeps the raw CSV and the observed 512-node timeout separate from any
release-scale claim.

The real-capture checker supplies `--qualification` to the measurement tool;
a graph's node count alone cannot close the workload gate. Completed CLI,
stage and synthetic-size data remain available when a later size times out.
`compare_schedule DUMP DECODER ENTRY_HEX SEED_HEX` compares every public state
transition and the completed result against the frozen pre-optimization
scanning engine. The optimized engine caches incoming sets and invalidates
local successors when a predecessor's reaching set grows; operation counters
therefore describe less work while the visible schedule is preserved.
