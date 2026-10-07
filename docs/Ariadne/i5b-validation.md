# I5b implementation and qualification

## Context and follow-up

**Status.** B0–B5 implemented and qualified on 2026-10-07 for the recorded finite source/fixture and controlled partial/full Windows tiers. All 18 aggregate gates pass under the sealed dependency snapshot. This is machine-code bug-debugging qualification for the declared corpus, not a packaged release or universal proof.

**Why this document exists.** The [I5b execution plan](../../Plans/i5b-zero-base-offset.md) requires exact instruction/context evidence, independent oracles and separate acceptance tiers for the zero-base-plus-nonzero-displacement question.

**What this document establishes.** Fresh results, timings, exact source/tool and dependency identity, old-output preservation and retained evidence closure.

**Where to go next.**

- [Implemented contracts](i5b-contracts.md) — actual interface, strict result and CLI.
- [Source review](i5b-source-review.md) — independent encoding/arithmetic expectations.
- [Aggregate record](../../evidence/Ariadne/i5b-qualification.json) — all gates, nested results, raw samples and source/tool inventories.
- [Evidence manifest](../../evidence/Ariadne/i5b-evidence-manifest.json) and [controlled case pins](../../evidence/Ariadne/i5b-controlled-cases.json) — archive digests, individual retained bytes and exact per-capture questions.
- [Investigation ledger](../../Plans/investigation-layer.md) — other hypotheses and I4.

**What remains unresolved.** Indexed, Linux, historical null provenance and object lifetime are outside this profile. Full process-memory capture, hardware origin, executed history and root cause are not inferred. The independent I4 CLI budget remains open. Later source/tool changes require fresh or exact-inventory-verified qualification; this record does not automatically qualify a later checkout.

## Delivered machine-code question

The first profile admits the six reviewed Windows AMD64 scalar MOV forms with one GPR base and no index, and asks whether its valid captured base is zero with a nonzero signed displacement. Byte/role/BIL/context/span agreement is required before a definite conclusion. Missing, unsupported, inconsistent or budget-omitted prerequisites produce unknown. The result does not identify a historical producer as executed or a source-language null-pointer root cause.

The controlled positive instruction is exactly `c7410805000000`, `mov dword ptr [rcx+8], 5`. Independent dump/PE inspection observes RCX zero and reported inaccessible address eight. The zero-displacement control is exactly `c70105000000`, with RCX zero and data address zero, refuting I5b while remaining consistent with I5a zero-start. The indexed control is `c744110805000000`, with RCX/RDX zero and data address eight; its I5b answer stays unknown.

## Fresh gates and independent evidence

The [aggregate](../../evidence/Ariadne/i5b-qualification.json) records:

- 18 passing gates with stable inventories of 294 source files and 11 tools.
- Apalache typechecking and TLC decision invariants over representative categories; 144 predicate combinations are checked by Safety over two states. This is question-level modeling, distinct from hardware semantics and Rust refinement.
- 57 independent synthetic cases and one upstream-call auxiliary fixture. Seven release tests explicitly exercise all native/reference/oracle comparisons, six MOV forms, decoded-role/context negatives, strict/budget handling, CLI transactionality, seed/root separation and the opaque-call numeric case.
- Default and core-only Cargo tests, formatting, all-feature/all-target Clippy, Rust layout and 16 Python acceptance controls pass. The core-only build retains no activated external dependencies.
- Refreshed I5a 14-gate, investigation/minidump/Stage E regressions and native-core 20-gate qualification pass under the same dependency view. Their narrower passed fields do not waive the separately unmet I4 Windows budget.
- All 15 actual I5b code mutants are detected by unchanged independent observers. Compile failures and timeouts receive no behavioral sensitivity credit.
- All 246 pre-change I5a assessment hashes remain byte-exact across 41 fixtures, two analyzer selections and three formats. The separate 24 old default/explanation hashes also remain byte-exact. Historical hashes are comparison oracles, not new acceptance claims for their former sources.

The selected read-only MirrorRust snapshot manifest SHA-256 is `a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`. The record retains its exact origin/content inventory and qualification environment. The archive's nested native-core dependency record preserves the sealed view.

## Frozen timing and controlled Windows tiers

One warm-up and five measured release repeats are retained per declared case. Frozen ceilings are 1,500 ms end-to-end native-default assessment CLI median and 10 ms combined binding/assessment/all-format-render phase median. Each sample binds artifact/query, native receipt/build and stable output hashes. Phase outputs must match the CLI assessment; phase-only or base-mode samples cannot replace CLI qualification.

All nine frozen fixture workloads pass. The largest fixture CLI median is **805.819 ms** and the largest phase median is **1.348 ms**.

| Controlled case | CLI median (ms) | Phase median (ms) | Result |
| --- | ---: | ---: | --- |
| Positive partial | 801.855 | 1.293 | Consistent; both ceilings pass |
| Positive full | 886.727 | 1.335 | Consistent; both ceilings pass |
| Refuted partial | 800.879 | 1.308 | Refuted; both ceilings pass |
| Refuted full | 898.798 | 1.422 | Refuted; both ceilings pass |
| Indexed-unknown partial | 801.059 | 1.193 | Unknown; both ceilings pass |
| Indexed-unknown full | 900.772 | 1.129 | Unknown; both ceilings pass |

All six are actual native Windows captures from the isolated controlled build, with uploads disabled and a minimal child environment. The independent inspector reads raw dump/context and supplied PE bytes without invoking Ariadne, BAP or the captured process. Positive, refuted and unknown controls each have partial/full capture evidence; edited synthetic fields are not labeled fresh real captures.

## Acceptance and retained closure

| Field | Recorded result |
| --- | --- |
| `sourceFixtureAcceptance` | true |
| `controlledWindowsPartialAcceptance` | true |
| `controlledWindowsFullAcceptance` | true |
| `fullI5bAcceptance` | true, within the declared corpus/profile |
| `sourcesStable` / `toolsStable` | true / true |

The [retained archive](../../evidence/Ariadne/i5b-evidence.tar.gz) contains 2,005 verified entries: exact source bytes, qualification logs/reports/samples, mutation observations, nested core evidence and the six controlled captures with witness and executable bytes. SHA-256: `4b256fc48a5b18c0a929b8f64adeefcc57f58ff042cb31766e0113348bc6229c`. Every entry's size and digest was rechecked after archive creation. Existing I4, I5a and Stage 2 historical records and source-bound contract/plan bytes remain unchanged. Raw Windows build/capture paths in the record identify the exercised environment; archived bytes and case pins provide the retained local closure.

The [runner](../../tools/check_i5b.py) remains the fresh qualification entry point. Run it through the sealed dependency view with explicit `--output`, `--captures` and `--baseline` paths; missing, skipped, malformed, stale or over-budget evidence cannot qualify. This evidence provides no I4 performance waiver, full ISA proof, arbitrary-indexed hypothesis support or cross-platform release acceptance.
