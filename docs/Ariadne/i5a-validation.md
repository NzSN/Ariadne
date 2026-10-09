# Historical I5a source/fixture delivery and validation

## Context and follow-up

**Status.** Historical source/fixture acceptance from the 2026-10-03 working tree
based on `c9eb4c5`: all 12 I5a gates passed with 171 stable source hashes. The full
nested regressions and evidence archive are retained with their original values.
The initial 2026-10-04 native refresh was incomplete. Its failed records remain
historical; the [2026-10-05 native successor](i5a-native-qualification.md) now
qualifies all 14 source/fixture gates and both controlled Windows captures under
the selected dependency snapshot.

**Why this document exists.** The [I5a design](i5a-zero-address-design.md) needs
independent context/admission evidence before a numeric conclusion can be trusted.
The [H0–H5 plan](../../Plans/i5a-zero-address.md) separates implementation and
source/fixture qualification from real Windows capture acceptance.

**What this document establishes.** The delivered scope, exercised corpus,
mutation sensitivity, unchanged outputs and frozen fixture performance results
for the retained 2026-10-03 source and tool identities. These historical results
do not qualify the current native analysis backend. All definite conclusions
remain conditional on the documented capture/lifting premises.

**Where to go next.**

- [Native qualification successor](i5a-native-qualification.md) tracks the
  completed native refresh, passing aggregate gates and controlled-capture qualification.
- [Later Windows demo](crashpad-demo-validation.md) supplied this historical
  run's missing controlled-capture input; its recorded CLI timing condition was
  unmet.
- [Implemented contracts](i5a-contracts.md) define binding, limits, reports and CLI.
- [Source and fixture review](i5a-source-review.md) explains raw field meanings
  and the independently specified arithmetic oracle.
- [Historical acceptance record](../../evidence/Ariadne/i5a-validation.json) and
  [archive manifest](../../evidence/Ariadne/i5a-evidence-manifest.json) bind the
  2026-10-03 gate results, source snapshot, tools, logs and derived reports to
  exact bytes. The acceptance record uses `ariadne.i5a-acceptance/v1`.
- [Investigation stage plan](../../Plans/investigation-layer.md) tracks controlled
  real Windows I5a, active Windows I4 and later capabilities separately.
- [Evidence guide](../../evidence/Ariadne/README.md) explains how source hashes
  limit the use of retained results after changes.

**What remains unresolved.** The historical source/fixture run did not exercise a
controlled Windows capture. The later demo supplied capture evidence but exceeded
its recorded CLI timing limit. The native successor resolves those qualification gaps using a stable, read-only
dependency snapshot and passing aggregate records.
The [user-authorized I4 replacement](i4-windows-repin-validation.md) now uses a
separate independently inspected 98-start Windows capture. Its correctness
checks pass, and the later [performance qualification](i4-performance-validation.md)
meets its fixed CLI budget. The original Electron
query remains unexercised historical evidence. Broader hypotheses and Linux numeric admission remain
outside this delivery.

The [documentation map](../documentation-map.md) is optional navigation.

## Delivered behavior

The reader seals exception parameters and context observations with validity,
artifact-relative spans, raw field bytes and digests. Binding reuses the exact
prepared/analyzer checks and rejects public-metadata or query substitution.
`assess_zero_address` evaluates one selected ordinary scalar MOV access at the
exception site. It returns consistent-with-evidence, refuted-under-premises or
unknown, with typed claims, premises and evidence requirements.

The separate `ariadne.zero-address-assessment/v1` envelope has strict JSON
validation and text/DOT renderers. `--assess-zero-address VA --memory-access N`
supports assessment-only output or atomic publication alongside the original
reports. The question adds a seed without inventing a discovery root. Default
limits are 32 evidence records and 32 claims; exhausted budgets remain valid
unknown/truncated results. Core recovery, reaching definitions, structural edges
and possible-producer explanations are preserved.

## Corpus and sensitivity

The results in this section belong to the retained 2026-10-03 run.

The [41 synthetic artifacts](../../tests/input/fixtures/i5a/manifest.json) have
independently specified raw flags, fields, instruction bytes and expected address
arithmetic. Native BAP/LLVM preparation exercises six MOV forms, including indexed
modular cancellation, signed displacement and RIP-relative zero. Required-register
validity is tested independently of unused registers, including CONTROL-only RSP
and RIP cases. Negative cases cover missing fields, thread-list substitution,
site/kind/data-span disagreement, guarded prefixes, excluded ranges and span wrap.

All 11 recorded [I5a tests](../../tests/input/i5a.rs) passed with `--include-ignored`.
Eight ran without native prerequisites; three covered the native BAP preparation
corpus with Rust analysis, normal CLI/Graphviz publication, and unchanged legacy
Stage B fixtures returning unknown.
Additional checks reject malformed raw extents/counts, conditional or multiple
accesses, unreviewed projection, metadata/query/report tampering and invalid
questions under zero limits. Fifty-six evidence/claim budget combinations preserve
valid reports. A partial producer explanation can coexist with a definite numeric
answer when its separate fault-site premises hold.

All 16 actual [implementation mutants](../../tools/check_i5a_mutations.py) were
detected in that run through unchanged observers: platform/RIP admission,
exception-location substitution, dropped displacement/index scale, double-applied
RIP, prefix/range
bypasses, invalid-register zero filling, thread-list fallback, unknown promotion,
numeric-observation misclassification, missing premises, wrong-query binding and
both output limits. Compile failures and timeouts do not count as detection.

The recorded [output comparison](../../tools/compare_i5a_cli.py) preserved all 24
existing CLI reports byte-for-byte across Stage B Windows/Linux, BAP precision and the
retained controlled Linux query. Retained hashes are comparison oracles; the
old acceptance result is not reused as current qualification. Each measured I5a
case also preserved its original report bytes when assessment was enabled.

That run's first-question regression detected its 13 existing mutants and retained
the controlled Linux workload below the unchanged 250 ms phase condition: the
sum of binding, explanation and rendering medians is 170.853 ms. The 11-gate
minidump regression also passed, including its external artifact, formal input
and mutation checks. These results qualify their recorded scopes, not a real
Windows I5a question or the missing original-Windows I4 workload.

The retained nested campaign passed all 17 investigation gates, 12 Stage E
gates and 11 minidump gates. Stage E repeated 64 complete traces and matched
326 observations over its 16 machine-state and 16 LLVM IR cases; all 15 model
mutants were detected. The historical outer I5a record owns that assessment's
verdict; nested first-question and model records retain their own scopes and premises.

## Fixture measurements

The [performance contract](../../tests/input/fixtures/i5a/performance.json) was
frozen after the first-form pilot and before acceptance. It requires one warm-up
and five measured repeats per mode, a combined binding/assessment/all-format
rendering median at most 10 ms, and an assessment-CLI median at most 1,500 ms.
The pilot observed 0.990 ms combined phases and 791.923 ms assessment CLI; it is
retained as a pilot, not an acceptance run.

The following values are unchanged from the 2026-10-03
`ariadne.i5a-fixture-measurements/v1` record nested in the
[historical acceptance record](../../evidence/Ariadne/i5a-validation.json).

| Fixture | Combined phase median (ms) | Base CLI median (ms) | Assessment CLI median (ms) |
| --- | ---: | ---: | ---: |
| `zero-store` | 1.029 | 812.340 | 1,052.562 |
| `nonzero-store` | 1.444 | 874.421 | 819.027 |
| `load32-zero` | 1.304 | 1,517.041 | 1,147.145 |
| `load64-indexed` | 1.795 | 1,455.049 | 947.542 |
| `store32-negative` | 1.439 | 1,663.042 | 1,179.540 |
| `store64-zero` | 1.025 | 918.808 | 1,028.129 |
| `indexed-wrap` | 1.039 | 774.456 | 754.883 |
| `rip-zero` | 1.363 | 742.848 | 766.887 |
| `missing-integer` | 0.859 | 964.589 | 863.086 |

All nine historical cases met the frozen I5a criteria. The raw records retain 90
measured CLI samples plus warm-ups, 45 measured phase samples plus warm-ups, output hashes,
per-phase costs and CLI peak RSS (at most 84,196 KiB in this run). Both modes vary
substantially; the differences do not demonstrate a speedup. These are small
synthetic workloads on this host, not realistic Windows performance qualification.
The original I4 250 ms incremental and 2,000 ms Windows CLI conditions are unchanged.

## Rerun and qualification boundary

The [retained archive](../../evidence/Ariadne/i5a-evidence.tar.gz) contains 1,610
files: original root/nested records, gate logs, raw measurement samples, derived
reports, comparison baselines, the pilot and a snapshot of the 334 source files
in the combined recorded inventories. Its [manifest](../../evidence/Ariadne/i5a-evidence-manifest.json)
records every entry hash and maps original run paths to archived paths. All
entry hashes, then-current source hashes and measured/native tool identities were
verified after retention for that historical source snapshot. This does not
establish a current source or tool match. The archive contains synthetic test
dumps only; real capture artifacts remain external. Earlier evidence files are unchanged.

After stabilizing the current source inventory, rerun with the pinned native
helpers/runtime, Graphviz and existing regression artifacts:

```sh
python3 tools/check_i5a.py
python3 tools/check_doc_links.py
```

The current I5a runner emits `ariadne.i5a-acceptance/v2` and explicitly executes
fixture determinism, format, default/core tests, all-feature and investigation-only
Clippy, source layout, native corpus/CLI,
mutations, output equivalence, measurements and the full investigation regression.
The latter includes the active Stage E/model replay and minidump gates. Mutation
and replay builds have separate root `target/` subdirectories. No retired
instruction-step/Lean gate is added. Current native checks also validate backend,
build, snapshot and query bindings and default/explicit native equivalence.

Controlled assessment requires a fresh passing v2 source/fixture record with
matching complete source and tool inventories. Supply that record through
`--source-fixture-record` to `native/crashpad-demo/assess.py`, following the
[native qualification procedure](i5a-native-qualification.md). The historical v1
record and the historical 12-of-14 aggregate are ineligible prerequisites.

| Tier | Recorded result on 2026-10-03 |
| --- | --- |
| I5a source/fixture acceptance | Pass: all 12 gates, stable source/tool identities, frozen fixture criteria and verified retained evidence. |
| Controlled real Windows I5a | Unexercised in this retained source/fixture run. The [later demo](crashpad-demo-validation.md) subsequently passed capture/answer checks but exceeded its recorded CLI budget. |
| Original-Windows I4 | Open: the original pinned artifact and exact-query timing evidence remain unavailable. |

The initial native refresh passed nine fixture measurements and sixteen mutants,
but recorded 12/14 source/fixture gates and 16/17 investigation gates because
external MirrorRust changes invalidated formatting and dependency identity.
Those records retain their failed flags. The
[2026-10-05 successor](i5a-native-qualification.md) resolves the dependency boundary
and separately records complete native source/fixture and controlled acceptance.
