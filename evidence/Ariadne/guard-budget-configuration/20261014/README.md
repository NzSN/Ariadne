# Guard-budget configuration qualification

## Context and follow-up

**Status.** G5 implemented and finitely checked on remote WSL on 2026-10-14. All final gates pass. No local Cargo/native build was run.

**Why this document exists.** The [previous diagnosis](../../guard-evidence-budget/20261014/README.md) showed that the captured caller exceeded 4 MiB, while profile validation rejected a larger requested budget.

**What this document establishes.** Source-bound tests for releasing guard-policy ceilings, strict CLI configuration, full unsigned native budgets, unchanged conservative stops and a bounded original-dump retry. The [validation record](validation.json) records 686 source/tool/document hashes; the [artifact manifest](artifact-manifest.json) binds 86 archived files.

**Where to go next.** Read the [canonical configurable-budget contract](../../../../docs/Ariadne/justified-branch-pruning-design.md#configurable-guard-budgets) and [completed G5 ledger](../../../../Plans/completed/guard-budget-configuration.md) for usage and scope. [BAP integration](../../../../docs/Ariadne/bap-analysis-core-design.md) owns the separate native transport contract.

**What remains unresolved.** The original caller has incomplete candidate coverage and an unknown MOVAPS verdict. Its larger report cannot fit native initialization's independent 8 MiB frame. No core steps or path enumeration were performed on that retry. Full-dump, release/performance and universal-refinement qualification remain open.

## Implementation and final checks

The seven defaults remain unchanged. Higher and lower finite caller budgets are accepted; Rust checks unsigned representability and counter overflow, while native admission reuses checked unsigned-64 parsing/comparisons. The native guard's additional 8,192-site and 32,768-edge ceilings are removed. Actual budget exhaustion, complete candidate coverage, unknown decisions and exact budget/proof binding remain enforced.

`--guard-admission-limits PATH` supplies a strict seven-field JSON object in guarded frame mode. Duplicate/unknown/missing fields, invalid numeric values, incompatible options and configurations over 8,192 bytes are rejected before dump access. An exactly 8,192-byte file is exercised successfully. Native CLI controls cover a one-frame guarded fixture and a three-frame diamond, retaining the same configured limits in every frame's proof.

| Fresh tier | Result |
| --- | --- |
| Guard unit controls | 14 tests, including each above-default field, full unsigned maxima and changed-budget proof rejection. |
| Root Rust | 189 default tests, 46 core-only tests, format and all-feature/all-target Clippy. |
| Pinned native | 12 kernel tests, nine captured/native tests and two frame-path tests. Full unsigned budgets and zero-deadline stopped MOVAPS retain native/reference parity. |
| Independent/model | Frozen independent guard oracle; predicate typecheck and all 27 finite safety/fair-termination configurations. |
| Contract controls | Python native contract checks and six mutation source/observer seam checks. Seam checks are not a new mutation campaign. |

The [initial failed attempt](artifacts/validation-20261014T063703/native-frame-path.log) requested three frames from the single guarded fixture. The test was corrected to use separate fixtures; [final checks](artifacts/validation-20261014T064305/gates.json) pass. No production change was needed for that correction. Independent read-only source/test reviews found no concrete issue.

## Original captured caller retry

The original dump SHA-256 remains `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668. Both probes use the same captured function entry `0x00007ff7744033a0`, recovered activation and explicit normal-call entry premise, with no image/symbol fallback or extra roots.

| Probe | Outcome |
| --- | --- |
| 32 MiB guard evidence; original discovery budgets | Configuration accepted; preparation stops at the caller-selected 4,096 instruction starts, after 61,440 prefix bytes. |
| 32 MiB guard evidence; expanded discovery/guard work budgets | Preparation succeeds for 4,764 candidate sites, 4,744 decodable sites and 4,943,346 raw AST bytes. Guard input is 6,934,822 bytes; report is 9,001,701 bytes. |
| Predicate outcome | `candidate-coverage-incomplete`; MOVAPS at `0x00007ff7744033b3` remains `unknown`, with `normal-or-alignment-fault-unresolved`. |
| Native initialization only | Rejects with `core request oversized`; independent 8 MiB frame bound is unchanged. No native analysis state, core steps or paths are published. |

[Original-budget outcome](artifacts/probe-original-discovery/preparation-outcome.json) and [expanded outcome](artifacts/probe-expanded/preparation-outcome.json) record exact limits and observations. Older-frame unwind still stops independently at `unsupported-unwind-operation`; both requested frames are recovered. Higher budgets do not supply missing semantic/control coverage or justify alignment through an incomplete candidate graph.

The [immutable archive](remote-evidence.tar.gz) retains the final sources, both qualification attempts, native build identity, original probe results and exact model/tool/source logs. Rust diagnostic/formatted sources are materialized as `.rs.txt`; their original archive names and bytes remain recorded in the manifest. Prior source-bound evidence is retained unchanged.
