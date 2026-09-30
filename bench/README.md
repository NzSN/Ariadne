# Analyzer baseline benchmark

The separate benchmark package measures five deterministic synthetic graph
families and, optionally, the pinned Stage B Windows minidump path. It uses
the root analyzer's operation counters and a benchmark-only allocation
counter. It does not alter the analyzer's public result or fixed schedule.
The [Priority 4 implementation plan](../docs/Ariadne/priority-4-workload-performance-plan.md)
sets the next captured-workload measurement and decision criteria.
Its [measurement design](../docs/Ariadne/priority-4-workload-performance-design.md)
defines what the harness can and cannot claim.

```sh
ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" \
  cargo run --offline --locked --manifest-path bench/Cargo.toml \
  --release --bin ariadne-bench -- 128 3 minidump
```

The output is CSV. Arguments are node count, repetitions and optional literal
`minidump`. Timing includes validation and analysis for synthetic workloads;
the minidump row includes reading, native decoding, preparation and analysis.
Allocation counters exclude external helper-process allocations. See the
[Stage F baseline and proof boundary](../docs/Ariadne/stage-f-proof-and-performance.md).

The separate `real_minidump` binary measures open, preparation, analysis and
three-format rendering stages for one frozen external query. Run it through
the [Priority 4 measurement tool](../tools/measure_priority4.py) so its
in-process counters are paired with repeated end-to-end CLI publication and
the existing synthetic graph families. The first
[validation record](../docs/Ariadne/priority-4-performance-validation.md)
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
