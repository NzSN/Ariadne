# BAP workload qualification repair and source refresh

## Context and follow-up

**Status.** Historical R0–R2 delivery on 2026-10-03, superseded for active qualification by the [controlled replacement](bap-windows-repin-validation.md): repairs and all 17 current
implementation gates pass with 177 stable source hashes. Full Stage 1 exit and
the Stage 2 prerequisite remain unmet because the original Windows workload is
unavailable. BAP-owned analysis has not started.

**Why this document exists.** The [integration plan](../../Plans/bap-integration.md)
identified a Linux benchmark bookkeeping defect and inconsistent qualification
predicates before refreshing Stage 1 evidence.

**What this document establishes.** The repaired evidence contract, controlled
decision regressions, exercised native tier and exact remaining Windows input
requirement. The final source-bound record distinguishes implementation gates
from full workload qualification.

**Where to go next.**

- [Authorized replacement](bap-windows-repin-validation.md) — records the new
  controlled Crashpad workload requested after the original artifact was
  confirmed unavailable; the result below remains historical.

- [Integration plan](../../Plans/bap-integration.md#original-windows-input-and-commands)
  — supplies the pinned artifact/query and commands for the remaining S4/S5 run.
- [BAP module guide](modules/bap.md) — describes the Linux analysis pipeline and
  its native prerequisites.
- [Controlled Windows demo](crashpad-demo-validation.md) — explains the separate
  real partial/full captures used for supplemental smoke coverage.

**What remains unresolved.** For this historical record, Neither controlled decision tests nor the small
Windows demo replaces the original 98-instruction capture. The unchanged
2,000 ms original-workload condition is unexercised. Stage 2 A0–A6 remain gated.

For the wider context, see the [documentation map](../documentation-map.md).

## Repaired evidence contract

Windows denotes the input's origin and AMD64 target. Ariadne, BAP and both
qualification scripts run on Linux; this delivery does not introduce a native
Windows Ariadne runner.

The old `measure_bap.py` reused `before` for both the source-hash map and the
Windows seed's reaching-definition list. The final comparison therefore marked
unchanged Windows runs unstable and serialized the wrong `sourceHashes` type.
Distinct `source_hashes_before` and `seed_definitions` now preserve both values.

Workload schema `ariadne.bap-workloads/v2` retains every warm-up and measured CLI
sample. The producer checks the independent address-origin witness and requires
exactly one captured preparation entry for every decoded address. The shared
validator requires the pinned artifact and exact query, Windows target, release
profile, BAP-only semantics, output hashes, workload counts and consistent raw
samples. It recomputes
the median and rejects contradictory summaries, nonfinite/negative timings,
missing samples and older records without the new evidence.

The aggregate `ariadne.bap-only-removal/v3` derives its own qualification result
instead of trusting the producer's stored success flags. Its workload reuse
boundary requires complete current source and tool inventories. The fixed
2,000 ms budget applies inclusively to the measured median.

| Evidence result | Implementation gates | Full Stage 1 / Stage 2 prerequisite |
| --- | --- | --- |
| Original Windows capture unavailable | May pass for the exercised corpus | False |
| Invalid or incomplete evidence | Cannot establish the required workload gate | False |
| Valid original evidence above 2,000 ms | May pass for correctness | False |
| Valid original evidence at or below 2,000 ms, all implementation gates pass | Pass | True |

This is the conservative current interpretation of the plan's full-exit
condition. Existing BAP-only default selection was separately authorized; it
does not establish qualification or waive the workload condition.

## Validation and retention

The campaign runs controlled Python decision tests, the 41-case native corpus,
transport/projection checks, complete-observation model comparisons, actual
adapter mutations and available release workloads. Stage E reuse is permitted
only after checking its complete current source inventory and native tool
identities. The initial aggregate exposed a missing Graphviz environment for a
root native rendering test; the harness now configures the existing local
Graphviz bundle using the same convention as Stage E.

The [source-bound record](../../evidence/Ariadne/bap-windows-workload-validation.json)
passes **17/17 implementation gates** with **177 stable source hashes**. The
[archive manifest](../../evidence/Ariadne/bap-windows-workload-evidence-manifest.json)
verifies all **238 retained entries**. Earlier BAP acceptance files remain
unchanged as historical evidence.

| Evidence | Result and scope |
| --- | --- |
| Controlled Python regressions | 39 tests: 15 actual producer-entry tests, 14 pure-validator tests and 10 actual aggregate-entry tests. Native subprocesses and evidence are stubbed in this tier. |
| Native corpus and integration | 41 exact byte cases, 30 admitted forms; helper build, transport/projection, CLI and native rendering gates pass. |
| Fresh BAP model comparison | Eight cases, 99 matched states, all nine observation fields; 162 current source hashes. Solver conformance is relative to supplied BAP summaries. |
| Fresh producer/adapter mutations | All 16 mutations detected by the intended checks; 159 current source hashes and unchanged observers. |
| Fresh available release workloads | Both Stage B platforms, controlled NOT and the real Linux capture pass; one warm-up and five CLI samples per case, separate stage samples, 167 current source hashes and all six tool bindings. |
| Retained Stage E regression | 12 gates, complete 315-entry current source inventory and native IR/MC/Graphviz hashes verified. Reused from the I5a campaign; not rerun here. |
| Supplemental real Windows inputs | Both controlled Crashpad partial/full inputs pass the Linux BAP phase benchmark with two decoded instructions and a one-site slice. These are not the original workload. |

The final aggregate reran its native and controlled gates after the Graphviz
repair, then reused this campaign's independently stable model, mutation and
workload records after identity checks. The archive keeps the initial failed
aggregate separately as diagnostic evidence, including its missing Graphviz
environment and parent source changes during repair. That failed aggregate is
not credited as a pass.

Available-workload CLI medians were **1,027.67 ms** (Stage B Linux),
**1,072.66 ms** (Stage B Windows), **1,027.82 ms** (controlled NOT) and
**1,830.96 ms** (real Linux). The real Linux result retains 34 decoded sites,
45 edges, a 28-site slice and one obligation. These measurements do not qualify
the original Windows budget.

The supplemental partial/full Windows benchmark total medians were
**1,932.24 ms** and **1,925.79 ms**, including preparation, lifting, analysis and
rendering. They are separate from the I5a numeric-only phase and its CLI budget.
Raw samples and exact artifact/tool hashes are retained; raw dumps and
executables are excluded from the archive.

The final record reports `implementationGatesPassed=true`,
`stage1ExitPassed=false`, `stage2PrerequisiteSatisfied=false` and
`defaultPromotionEligible=false`. Its Windows status is `unavailable`.

## Remaining original-Windows requirement

The [pinned case](../../evidence/Ariadne/priority-4-real-capture-case.json) is
`f13d18cd-9ade-4eff-947c-15a649b636fa.dmp`, 2,028,400 bytes, SHA-256
`4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86`.
The query uses entry `0x7ff6451d52d0`, seed `0x7ff6451d530f` and independent
address producer `0x7ff6451d530b`.

At this run, bounded local searches had not located the capture. The user later
confirmed it no longer exists and authorized the [replacement](bap-windows-repin-validation.md).
The historical interface required its path to allow
the existing Linux runner to verify its identity, perform the exact query and
collect one warm-up plus five release measurements. At that checkpoint, full Stage 1
exit, the Stage 2 prerequisite and default-promotion eligibility remain false.
