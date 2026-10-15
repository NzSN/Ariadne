# Captured caller guard-evidence budget diagnosis

## Context and follow-up

**Status.** Fresh read-only remote WSL diagnosis on 2026-10-14. The original dump still fails preparation under the unchanged reviewed guard profile. No production code or budget was changed.

**Why this record exists.** The [shift-count correction](../../../../docs/Ariadne/bap-shift-count-design.md#original-dump-retry-2026-10-14) fixed XORPS operand-width admission, but the frame-path listing remained unavailable.

**What this record establishes.** Exact instruction-level BIL byte accounting at the new failure, with a production-helper baseline and a diagnostic helper wrapper that preserve identical materialization progress. [Structured diagnosis](diagnosis.json), [accounting summary](artifacts/summary.json) and [artifact manifest](artifact-manifest.json) retain the measurements and source identities.

**Where to go next.** Read the [guard contract](../../../../docs/Ariadne/justified-branch-pruning-design.md#usage-and-implemented-contracts) for complete candidate closure and finite limits, and the [frame-path contract](../../../../docs/Ariadne/investigation-design.md) for required per-frame queries. Any larger or more compact evidence contract requires separate design and qualification.

**What remains unresolved.** Discovery aborts before candidate closure, predicate checking or final query publication. This diagnosis does not establish an alignment proof, enumerate paths, determine executed history or qualify a larger budget. The adjacent instruction-start and prefix-byte bounds remain unexercised beyond the observed failure.

## Observed failure

Dump `dump_03958DA4FCA844A786262A1053`, SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, frame pair 1:0, NP=10. The same expanded captured-read/runtime-table budgets recover both requested frames. Recovery of an older frame stops separately at `unsupported-unwind-operation`.

The guard profile permits 4,194,304 evidence bytes. Its early materialization check sums the compact serialized original typed BIL AST once per lifted candidate instruction. It retains every candidate's BIL so the guard checker can reconstruct transfers, barriers and incoming coverage. The counter does not measure the dump size or just the MOVAPS instructions; duplicate candidate sources are rejected.

| Measurement | Observed value |
| --- | --- |
| Successfully charged candidate sources | 4,003 |
| BIL bytes before failure | 4,192,674 |
| First refused source | `CMP32rm` at `0x00007ff77440423d`, bytes `413b4f14` |
| Refused source BIL | 4,457 bytes, seven statements |
| Proposed cumulative BIL bytes | 4,197,131; 2,827 over the cap |
| Attempted/lifted sources, including complete failing batch | 4,012 unique sites |
| Completed discovery batches | 239; batch 239 was lifted but not committed |
| Whole failing batch | Ten sources; eight after the refused source remain uncharged |
| All returned source BIL | 4,212,963 bytes |
| Captured prefixes read / decoded instruction bytes | 60,180 / 17,962 bytes |

All 4,012 attempted sites lie within the caller's runtime function range, `0x00007ff7744033a0` to `0x00007ff77440deba`. The cost is distributed across the candidate graph: CMP-family lifts alone occupy 1,549,137 bytes. The largest individual AST is 5,157 bytes. Exact XORPS at `0x00007ff7744075b3` contributes 3,756 bytes in batch 51; it is passed long before the budget failure in batch 239.

The full failing batch is lifted before the materializer charges its sources. `MaterializationReport.attempted` therefore includes all ten batch sites, while `decoder_batches` counts only the 239 fully committed earlier batches. The 4,212,963-byte total is the sum of returned lifts, not the successfully retained `guard_bytes` value.

## Why the listing says unavailable

The preparation returns `materialization limit: guard evidence bytes` before creating a guard report or final frame query. The retry driver records that error and stops its preparation loop, leaving no frame queries to compose. Frame-path composition reports `missing-frame-query`, and the listing returns `coverage: unavailable` before enumeration. Zero returned paths therefore represents an unavailable query; it does not prove that no path exists.

The ordinary CLI propagates the preparation error directly. The secondary `missing-frame-query` wording comes from the diagnostic retry driver's decision to render a listing after recording preparation failure.

`Limits::validate` permits only tightening the reviewed defaults. The separately recorded 32 MiB request fails immediately with `guard profile limit exceeded`. The raw AST sum is only an early lower bound: serialized guard input/report checks also charge escaped ASTs, graph metadata and proof fields. Changing one literal cannot qualify a larger evidence contract. The 4,096-start and 61,440-prefix-byte limits are also close to exhaustion, with 84 starts and 1,260 prefix bytes remaining, although neither triggered this run.

## Measurement and evidence boundary

Standalone diagnostic Rust programs were compiled on remote WSL against the existing library and dependencies. The production-helper baseline reproduced the error. A separate transparent stdout wrapper retained original helper response lines; the measurement program used the identical `ast::Lift`/`Stmt` definitions, AST validation and `serde_json::to_vec` serialization to compute exact lengths and hashes. Its exported materialization progress matches the baseline byte for byte, and every response maps to one unique attempted address.

The wrapper has a different helper identity and is explicitly diagnostic. No measured evidence was used to admit a guard or publish an analysis. The source hashes for the five relevant implementation files match the local checkout; the archive records the existing library and actual pinned helper hashes. Original dump bytes and the bulk lift log remain remote. Four representative lifts are retained in [selected-lifts.json](artifacts/selected-lifts.json).

The [immutable archive](remote-evidence.tar.gz) contains 29 members. Rust diagnostic sources are materialized locally as `.rs.txt`, with original archive names and byte hashes retained in the manifest. Initial diagnostic setup errors—an omitted standalone serde link argument and an export attempted inside a namespace without `/mnt/d`—were corrected; they receive no validation credit and do not alter the completed analysis measurements. [reproduction.sh](artifacts/reproduction.sh) includes the corrected setup/export commands.
