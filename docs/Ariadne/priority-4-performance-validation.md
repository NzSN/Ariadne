# Priority 4: measured workload decision

Measured **2026-09-29 23:26 CST** under the
[Priority 4 design](priority-4-workload-performance-design.md) and
[implementation plan](priority-4-workload-performance-plan.md). The
[validation record](priority-4-validation.json) binds 28 stable source
hashes, all four tool binaries, query identity, host and a **predeclared
2,000 ms local CLI budget**. Raw observations are retained as
[CLI](priority-4-cli.csv), [stage](priority-4-stage.csv) and
[synthetic](priority-4-synthetic.csv) CSV files. One warm-up and five
measured repetitions were used per completed workload.

The supported release CLI opened the external Priority 1 Chromium dump,
decoded 34 starts, analyzed its possible predecessor slice and published
text/DOT/JSON in a median **1,299 ms** (range 1,276–1,346 ms). Median
peak resident memory was **52,416 KiB**. Its separate in-process stage
measurement attributed a median 1,156 ms to preparation and native decoder
launches, 49 ms to core analysis, 169 ms to rendering and less than 1 ms to
opening the dump. Those stage timings exclude process startup and output
publication, so they are not interchangeable with the CLI timing. The
benchmark allocator counted cumulative allocation requests/bytes only in
its process, excluding memory allocated by LLVM helper processes. The
four-node Stage B Windows CLI reference had a 198 ms median.

| Synthetic graph | 128 nodes median | 256 nodes median |
| --- | ---: | ---: |
| Linear | 17.0 ms | 72.7 ms |
| Loops | 191.8 ms | 2,551.8 ms |
| Joins | 35.5 ms | 219.7 ms |
| Opaque calls | 16.8 ms | 86.1 ms |
| Dense alias set | 223.0 ms | 1,362.2 ms |

The attempted five-repeat 512-node synthetic suite exceeded its 180-second
bound; the [timeout record](priority-4-512-timeout.json) is retained as a
limit result, not a passing measurement. The bounded follow-up completed
128 and 256 nodes without weakening the real-workload target.

## Larger real-capture search

The local Breakpad processor test corpus has 53 `.dmp` files. The plausible
AMD64 dumps with matching crash-module symbols did not supply a qualifying
larger memory-fault path: `linux_inline.dmp` does not capture bytes at its
exception RIP; `linux_null_read_av.dmp` has a matching `crash()` symbol that
starts at RIP, with no earlier local producer; `linux_overflow.dmp` reaches
`gsignal` in libc for an abort rather than a faulting memory read; and the
`linux_stacksmash.dmp` libgcc symbols do not establish a captured function
start near RIP. The older `driver` and Windows `crash.exe` fixtures lack
matching symbol artifacts in this corpus. This is a bounded local candidate
audit, not proof that no suitable capture exists elsewhere.

**Decision:** the current 34-node real query is within the local budget, so
no production solver or decoder change is justified by this case. Preparation
is the measured stage to examine if a larger real case proves slow; synthetic
loops and dense aliases expose scaling risk in the core. The plan's target of
at least **64 decoded starts in one qualifying real capture** remains unmet.
Release-scale performance qualification is therefore **open**, and the
synthetic timeout must not be used to claim a real investigator bottleneck.
No `Analyzer::step()` schedule, result, provenance or report contract was
changed by the benchmark harness.
