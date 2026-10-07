# Native I4 performance qualification

## Context and follow-up

**Status.** D0–D3 complete for the exact controlled Windows query on 2026-10-07.
The recorded release explanation CLI meets 2,000 ms and the separate Linux
incremental phase benchmark meets 250 ms. Completion rechecked current source,
tool and dependency identities and every retained archive member; the runtime
campaign was retained, not rerun during the completion audit.

**Why this document exists.** The [Windows re-pin result](i4-windows-repin-validation.md)
passed correctness but measured 4,774.451 ms against its fixed CLI budget.
The [performance design](i4-performance-design.md) and
[D0–D3 implementation plan](../../Plans/i4-performance-implementation.md)
require measured changes and exact-query regression evidence before closing I4.

**What this document establishes.** The implemented performance changes,
raw fixed-budget measurements, unchanged output/action checks, exercised
regressions and durable source/tool/dependency-bound evidence.

**Where to go next.**

- [Qualification record](../../evidence/Ariadne/i4-performance-qualification.json)
  — original campaign decisions, raw samples and complete nested regressions.
- [Evidence manifest](../../evidence/Ariadne/i4-performance-evidence-manifest.json)
  and [completion audit](../../evidence/Ariadne/i4-performance-audit.json) —
  verified retained bytes and current-inventory checks.
- [Investigation contracts](investigation-contracts.md) — meaning of possible
  producers, query binding, separate phase/CLI budgets and uncertainty.
- [Stage ledger](../../Plans/investigation-layer.md) — delivered questions and
  later hypothesis, object/source-context and cross-capture work.
- [BAP trust boundary](semantic-assurance.md) — finite analysis qualification
  and trusted lifting remain separate from universal ISA/refinement proofs.

**What remains unresolved.** This qualifies one exact controlled 98-start
Windows capture/query and the declared finite regression corpora under a sealed
MirrorRust view. Later source/tool/dependency changes require fresh or complete
identity-verified evidence. It does not qualify the missing original Electron
crash, general latency, executed history, object lifetime, root cause or a
packaged cross-platform release.

For the wider context, see the [documentation map](../documentation-map.md).

## Implemented changes and preserved contracts

BAP preparation reuses one checked LLVM reference process for a snapshot/target.
Bounded row transport, deadlines, poison/reap behavior and clean EOF remain
required. The standalone LLVM adapter stays one-shot. BAP remains the sole
production instruction-semantic producer; unsupported semantics stay explicit.

Native recovery initializes derived incoming/outgoing/enabled-action caches
only after discovery. Updates refresh affected destinations and preserve the
canonical minimum-VA action. Query-owned immutable reaching-row and attribution
encoding avoids repeated serialization; chunked output still carries every full
observation within the existing frame limit. Rust reuses exact-equal validated
rows only while the decoded domain remains valid, and retains frame bytes for
complete read-only/rejection equality checks.

Every compiled runtime pin is still hashed at both existing validation boundaries,
using streaming buffers and one worker per file in the finite compiled pin.
The validated library digest supplies the existing receipt without another read.
No capture pin, question, fixed budget, possible-origin semantics, report schema
or source-bound Stage 2 design/plan bytes changed.

## Exact fixed-budget results

The active case remains `crashpad-windows-checksum-98-i4-v1`, with discovery entry
`0x00007ff7382f4840`, fault/seed `0x00007ff7382f49b4`, producer
`0x00007ff7382f49b1` and access index zero. The capture digest, captured-byte
precedence, 98 starts, expected producer and native receipts pass. The matching
PE remains independent comparison evidence.

| Requirement | Recorded result | Fixed limit |
| --- | --- | --- |
| Native-default release explanation CLI, exact Windows case | **1,692.696 ms median** | 2,000 ms |
| 34-start Linux reference binding + explanation + all-format rendering | **182.924 ms sum of phase medians** | 250 ms |
| Native profile schedule, all six runs | 99 recovery + 102 dataflow + 15 slice actions | Baseline 216 actions |
| Native profile reports, all six runs | Baseline output SHA-256 preserved | Exact equality |
| Full I4 real-capture acceptance | `true` | All applicable gates and identities pass |

One warm-up is excluded from five Windows measurements:
**1,688.915; 1,706.412; 1,650.545; 1,727.445; 1,692.696 ms**.
The warm-up measured 1,671.475 ms. Full-CLI measurements use the normal release
executable and explanation mode; base CLI and diagnostic phases supply no
substitute acceptance credit.

Linux component medians are binding 1.366548 ms, explanation 95.504280 ms and
rendering 86.053299 ms. Their sum is the existing contract's phase criterion.
This phase benchmark uses the Rust reference analyzer; the separate native
profiler is explicitly diagnostic.

[CLI samples](../../evidence/Ariadne/i4-performance-cli.csv),
[phase samples](../../evidence/Ariadne/i4-performance-phase.csv) and
[native profiles](../../evidence/Ariadne/i4-performance-native-phases.csv)
are retained byte-for-byte. The prior 4,774.451 ms re-pin result and the measured
5,463.647 ms diagnosis baseline remain historical; no old flags were promoted.

## Regression and evidence closure

The nested I5b campaign passes **18/18 gates**, the native-core adoption campaign
passes **20/20**, and I5a passes **14/14**. Stage 1 and investigation each retain
17 passing gates, including their input, effects, Stage E/model and mutation
regressions. Native generated replay, algorithm/boundary mutations and all
15 I5b mutants pass. Both new ignored tests ran: real decoder reuse across
snapshot batches and rejection of damage to every pinned runtime file. Root
and core-only tests, formatting, all-feature/all-target Clippy and layout checks
passed in those exact-source records.

The separate [controlled I5a record](../../evidence/Ariadne/i4-performance-i5a-controlled.json)
also matches current source/tool/dependency, fixture-prerequisite and input/sample
identities. Partial/full assessment CLI medians are 417.978 / 457.633 ms against
1,500 ms; phase medians are 1.044 / 1.068 ms against 10 ms. Both pass without
waiving I5a criteria. Its original report remains byte-exact in the accepted archive.

Old I5a and default output comparison gates pass. The independent baseline
profile digest and all 216 native actions remain unchanged across six runs.
Validation preserves possible producers, opaque calls, weak memory and explicit
gaps; a passing performance result adds no executed-history claim.

The [accepted archive](../../evidence/Ariadne/i4-performance-evidence.tar.gz)
contains **3,625 verified entries**, including 712 source inputs, the complete
nested regression/core archives, diagnostic baselines, raw workload/profile
samples, reports and the sealed dependency manifest. Its SHA-256 is
`4a5f05ea02317a3a21a56ad177796f794f87661a3a143694ce80e5d0ea5039d8`.
The separate nested archives verify 919 regression and 1,432 native-core entries.
Twelve current tool digests and the exact dependency identity match the accepted
record. The [completion audit](../../evidence/Ariadne/i4-performance-audit.json)
records that new verification separately from the original runtime campaign.

The [rejected-attempt manifest](../../evidence/Ariadne/i4-performance-history/2026-10-07-rejected/evidence-manifest.json)
preserves both earlier qualification failures and their raw workload reports,
CSV samples and outputs. Their Linux phase sums were 261.578 and 252.488 ms;
the second also measured 2,117.911 ms Windows CLI. Their failed flags remain
unchanged. Older capture, Stage 2, I5a and I5b evidence is preserved.

## Reproduction and retained-byte verification

Run qualification under the sealed dependency view. The exercised MirrorRust
manifest SHA-256 is
`a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`,
with origin revision `08d189f18a76845dc15dd23b79424809ae27f406`.
The archive retains its manifest, exact source contents and origin identity.
The [snapshot wrapper](../../tools/with_mirrorrust_snapshot.py) requires the
selected view to be read-only at the normal dependency path.

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/i5b-dependency-snapshot \
  --sha256 a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854 -- \
  python3 tools/check_i4_performance.py \
    --regressions target/i4-regressions-20261007-v5/report.json \
    --profiles-root target/i4-performance-20261007 \
    --output target/i4-performance-new-run
```

That command requires the exact-current complete regression record, native
helpers/runtime/model tools and baseline profiles. After source/tool changes,
first rerun `tools/check_i5b.py` through the wrapper with new output, capture and
baseline directories as described in [I5b qualification](i5b-validation.md).
Missing helpers, captures, failed gates or changed identities cannot qualify.
Original temporary paths in records identify the exercised environment; archive
member names provide retained bytes, not a guarantee that those paths still exist.

The large accepted archive uses Git LFS. After cloning, materialize it with
`git lfs pull --include="evidence/Ariadne/i4-performance-evidence.tar.gz"` before
checking its digest. Verify report/archive hashes against the manifest, then
verify every member hash; a Git pointer or manifest flag alone is insufficient.
