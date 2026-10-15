# Configurable native request-budget qualification

## Context and follow-up

**Status.** T0–T4 implemented and finitely validated on remote WSL on 2026-10-14. All final gates pass; the original larger captured caller request initializes natively with 32 MiB.

**Why this document exists.** The [G5 retry](../../guard-budget-configuration/20261014/README.md) produced a 9,001,701-byte guard report, then failed before native initialization under the fixed inbound 8 MiB frame bound.

**What this document establishes.** Paired host/native configurable request limits, exact capability negotiation, independent reader boundary controls and original-dump initialization. [Validation](validation.json) records 686 matching source/tool/document hashes; the [artifact manifest](artifact-manifest.json) binds 35 archived files.

**Where to go next.** Read the [canonical request contract](../../../../docs/Ariadne/bap-analysis-core-design.md#configurable-native-request-limit) and [completed execution ledger](../../../../Plans/completed/native-request-budget.md) for usage. The [predicate contract](../../../../docs/Ariadne/justified-branch-pruning-design.md) owns incomplete incoming coverage and the still-unknown MOVAPS verdict.

**What remains unresolved.** Raising request capacity does not close the original candidate graph or establish alignment. This retry performs initialization only, with no core steps or path enumeration. Response/result, normalized-input and investigation limits remain independent. No new release/performance, mutation campaign or universal-refinement qualification is claimed.

## Final implementation and tests

`CoreConfig.max_request_bytes` and CLI `--bap-core-max-request-bytes N` select a positive finite budget. The default remains 8 MiB, with no default-based ceiling. Rust and native both count the entire JSON line including its newline. Native parsing/comparisons preserve full unsigned-64 values, including a directly exercised maximum. Zero, malformed and overflowing values are rejected.

ABI 2 keeps existing operations and adds paired request capability fields. Runtime ready declares the exact chosen budget; Rust checks it against the source-bound manifest and selected configuration. The recorded `identity.build` remains immutable, while `identity.transport` records effective request/response budgets separately. Legacy helpers work at the default; nondefault budgets require the capability. Partial/malformed capabilities reject before launch, and wrong ready declarations poison and reap the process. Outbound response frames remain 8 MiB.

| Fresh tier | Result |
| --- | --- |
| Root Rust | Format, 191 default tests, 46 core-only tests, all-feature/all-target Clippy and layout pass. |
| Pinned native kernels | 17 tests, including five new request-budget tests and existing hostile transport, large completion and stateflow controls. |
| Captured/native and CLI | Nine capture tests and two frame-path tests pass; CLI fixtures negotiate a 32 MiB request budget. |
| Python reference contract | 14 tests pass, including exact newline accounting, above-default request admission and invalid finite budgets. |
| Independent guard controls | Frozen guard oracle and 14 guard tests pass; six mutation seam checks retain unique observer anchors. Seam checks are not a new mutation campaign. |

The new tests independently exercise the native reader by bypassing the Rust size check, accepting the exact byte bound and rejecting one byte over. Startup controls reject zero, signs, malformed decimals and unsigned overflow before ready. Compatibility controls cover legacy/default, legacy/nondefault, malformed capability pairs, exact negotiated ready and oversized response rejection under a raised 32 MiB request budget. PID cleanup is asserted. A valid normalized input above 8 MiB succeeds with 32 MiB and matches reference Init/Visit states while keeping responses small.

Independent read-only source, CLI and test review returned no concrete findings. Model bodies/configurations and semantic query/actions are unchanged; the retained G5 model hashes are verified separately in validation. No fresh model campaign is credited here.

## Original captured caller

Original dump SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, caller entry `0x00007ff7744033a0`. The same captured bytes, recovered activation and explicit Windows normal-call entry premise are used; no image/symbol fallback or extra roots are introduced.

Expanded discovery prepares 4,764 candidate sites and the same 9,001,701-byte guard report. The [recorded initialization comparison](artifacts/probe-expanded/preparation-outcome.json) shows:

| Request budget | Outcome |
| --- | --- |
| 8,388,608 bytes | `core request oversized`; native initialization rejected. |
| 33,554,432 bytes | `accepted-no-analysis-steps`; actual native guard/input admission succeeds, with response bound still 8,388,608 bytes. |

The report still records `candidate-coverage-incomplete` and `normal-or-alignment-fault-unresolved` at MOVAPS `0x00007ff7744033b3`. This transport fix does not turn that unknown into an alignment proof. The [original discovery budget](artifacts/probe-original-discovery/preparation-outcome.json) independently stops at 4,096 starts before any native input is available. Older-frame unwind stops separately; both requested frames are recovered.

The [immutable archive](remote-evidence.tar.gz) retains exact sources, helper build identity, validation logs and bounded dump outcomes. Rust diagnostic/formatted sources are materialized locally as `.rs.txt`, retaining original archive names and byte hashes. Historical guard/shift/transport evidence is preserved with its original scope.
