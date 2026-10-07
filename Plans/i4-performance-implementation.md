# I4 native performance implementation plan

## Context and follow-up

**Status.** D0–D3 complete for the exact controlled capture on 2026-10-07. The qualified Windows explanation-CLI median is 1,692.696 ms / 2,000 ms; the separate Linux incremental phase sum is 182.924 ms / 250 ms. Current source/tool/dependency inventories and retained archives were rechecked before completion.

**Why this document exists.** The [performance design](../docs/Ariadne/i4-performance-design.md)
identifies repeated decoder launches and native analysis/transport as measured
costs on the exact machine-code fault-address explanation query.

**What this document establishes.** Scoped ownership, real regression signals,
semantic equivalence and full I4 qualification requirements.

**Where to go next.**

- [Completed qualification](../docs/Ariadne/i4-performance-validation.md) — exact samples, verified archives and remaining scope limits.
- [Design](../docs/Ariadne/i4-performance-design.md) — evidence and predictions.
- [Original follow-up](i4-windows-repin.md#remaining-i4-performance-qualification)
  — unchanged active capture and timing obligation.
- [Investigation contracts](../docs/Ariadne/investigation-contracts.md) — exact
  query identity, possible producers and separate phase/CLI requirements.

**What remains unresolved.** The recorded exact-query acceptance passes. Later source/tool/dependency changes require fresh or complete identity-verified qualification. This finite controlled-capture result does not qualify the original Electron crash, a packaged release, universal refinement or a general performance bound.

## Stages and ownership

| Stage | Owned work | Exit |
| --- | --- | --- |
| D0 — Baseline and measured diagnosis | `src/bin/i4_profile.rs`; retained loop/phase/CPU samples under target; historical records untouched | Exact 98-start CLI repeatedly fails the original ceiling; phase/profile probes distinguish ranked hypotheses. |
| D1 — Snapshot-scoped decoder process | `src/llvm_mc/protocol.rs`, `src/llvm_mc/reference.rs`, `src/bap/prepare.rs`, focused native/protocol tests | Real batch regression goes red before fix, then one process serves a snapshot; identical decoded facts/reports and clean bounded shutdown. |
| D2 — Native measured cost | Native core/recovery/project observation and Rust core adapter only if profiling justifies changes | Reduce identified computation/serialization/validation costs while preserving step scheduling, full observations, evidence admission and source/model contracts. |
| D3 — Exact-query qualification | Dedicated performance tool/record, investigation/I5a/I5b/native-core/model/mutation regressions and docs | One warm-up/five native-default release explanation repeats at most 2,000 ms; Linux phase at most 250 ms; exact source/tool/dependency closure and preserved old outputs. |

Apply one measured change at a time and rerun the exact feedback loop. Retain
previous baseline reports/hashes and complete negative/over-budget evidence.
Existing source-bound Stage 2 design/plan bytes and older archives remain immutable.

Use a sealed read-only MirrorRust snapshot. New replay/mutation campaigns get
separate root target subdirectories. Run affected native tests explicitly,
default/core-only Cargo tests, formatting, all-feature/all-target Clippy, Rust
layout and documentation checks. Requalify changed source/tool inventories;
missing helpers, captures, timeouts or compile failures are not passes.

Final record must validate the active capture/case digest, exact roots/seeds,
98 decoded starts, expected address producer and native build receipt; calculate
the verdict from raw explanation-mode CLI samples, excluding warm-up. Preserve
old base/explanation/I5 outputs or account for exact validated tool receipts
without stripping substantive claims. Retain profiles, raw samples, independent
oracles, mutation observations and a verified evidence archive. Update the I4
ledger only after full acceptance is demonstrated.

## Execution boundary on 2026-10-07

The initial exact loop was red at 5,463.647 ms. Decoder reuse reduced it to
3,505.141 ms. Native immutable row/attribution encoding, bounded chunk output,
incoming/selected-action caches and Rust validated-row/frame reuse then reduced
the loop to 2,207.334 ms. Parallel streaming validation of every pinned runtime
file, at both existing validation boundaries, plus reuse of the validated library
digest reduced the loop to 1,673.048 ms. No runtime digest check was removed.

Native response chunking avoids repeated large frame copies while retaining the
same complete JSON responses, frame limits, action indices and read-only checks.
Rust caches only exact-equal definition rows while the decoded domain grows;
changed rows or a shrinking domain are freshly validated. Cached frame bytes are
parsed for complete read-only/rejection equality instead of deep-cloning every
state after every step. LLVM failures poison/reap the session and require clean
EOF, including trailing-output and timeout controls.

Some intermediate direct-write/Rust-cache wall timings competed with a separate
Chromium build and are retained as diagnostics, not isolated performance claims.
The direct-write experiment was reverted. Native tests must name the freshly
built `ARIADNE_BAP_CORE_DIR`; a default test directory can contain an older helper.

D3 runs `tools/check_i5b.py` under the sealed dependency snapshot to refresh core,
Stage E, input/BAP, I5a/I5b, replay and mutation gates. Then run
`tools/check_i4_performance.py --regressions REPORT --profiles-root target/i4-performance-20261007 --output NEW_DIRECTORY`.
That tool rejects stale/regressed source/tool/environment records, rebuilds the
normal CLI, remeasures both fixed budgets, verifies original report hashes and the
216-action native schedule, and verifies a complete evidence archive. Diagnostic
success alone is not full I4 acceptance.

The first D3 run was interrupted after early passing gates to correct unnecessary
cache allocation for inactive sites. Flow caches now allocate only after recovery,
from decoded sites and decoded entry roots. Its incomplete logs remain under
`target/i4-regressions-20261007`; the fresh aggregate uses a separate directory.
No partial run supplies acceptance credit.

The second run retained a real no-default-feature Clippy failure: the shared
reference path's decoder parameter is used only when investigation hashing is
compiled. Its effects/minidump nested records remain failed historical evidence.
The feature boundary is corrected and both core-only and all-feature Clippy are
checked before the next complete run. No failed record is promoted.

## Completed D3 — 2026-10-07

The later complete campaign passes 18 I5b aggregate gates, 20 native-core gates,
14 I5a gates and nested 17-gate investigation/Stage 1 regressions. Native
generated replay and algorithm/boundary mutations pass; all 15 I5b mutants
are detected. Both new ignored native tests ran against the pinned helpers.
Legacy I5a and default report comparisons pass. Separately verified controlled
I5a partial/full records meet their unchanged 1,500 ms CLI / 10 ms phase budgets
with current source/tool/dependency and input/sample identities. Six exact native profiles retain
the baseline output digest and 99 recovery / 102 dataflow / 15 slice actions.

The normal release CLI passes the fixed Windows ceiling at 1,692.696 ms after
one warm-up and five repeats. The separate 34-start Linux reference phase
benchmark passes at 182.924 ms, using the contract's sum of binding, explanation
and rendering medians. The earlier diagnostic loop alone supplied no acceptance.

The [retained result](../evidence/Ariadne/i4-performance-qualification.json) binds
712 sources, 12 tools and the sealed dependency manifest. Its
[verified archive](../evidence/Ariadne/i4-performance-evidence-manifest.json)
contains 3,625 entries. Completion follows an exact current-inventory audit,
including all members of that archive and the nested regression/core archives.
The [rejected attempts](../evidence/Ariadne/i4-performance-history/2026-10-07-rejected/evidence-manifest.json)
retain both earlier phase-budget failures and their raw samples. Historical
records, fixed budgets, capture pins and source-bound Stage 2 design/plan bytes
remain unchanged. The [validation guide](../docs/Ariadne/i4-performance-validation.md)
provides reproduction and separates source-bound reuse from fresh tests.
