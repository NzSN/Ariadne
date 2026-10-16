# BAP shift-count compatibility execution

## Context and follow-up

**Status.** X0–X4 implemented and finitely checked on remote WSL on 2026-10-14. The exact original width failure is corrected; the full captured query remains unavailable at the reviewed guard-evidence cap.

**Why this document exists.** The [canonical shift design](../../../docs/Ariadne/bap-shift-count-design.md) explains the captured XORPS failure and pinned BAP type rule.

**What this document establishes.** Scoped stages, ownership and acceptance for shift counts with independent widths; all current unrelated implementation, archival documentation and immutable evidence are preserved. No commit/push is included.

**Where to go next.** Read the [design](../../../docs/Ariadne/bap-shift-count-design.md), [BAP contract](../../../docs/Ariadne/bap-analysis-core-design.md#backend-usage) and [formal-model guide](../../../Specs/README.md) for the distinct semantic and analysis boundaries.

**What remains unresolved.** Exact vector values, general SIMD, additional scalar/address/target precision, unwind and successful full-dump enumeration are excluded. The retry can uncover another independent stop.

## Stages and acceptance

| Stage | Owner / work | Acceptance |
| --- | --- | --- |
| X0 | Root + primary-source research: reproduce public Backend `0f57c0`, bind retained lift/asset/source identities and verify operator/type/count rules. | Deterministic red loop and source-grounded diagnosis; no opcode bypass. |
| X1 | Root owns Rust admission/projector; test worker owns independent fixture/oracle/unit controls. | Shift-only independent scalar widths, left-width result, full unsigned count, saturating fill, safe XOR equality and preserved alias origins. Regression tests go red before edits. |
| X2 | Native/profile worker owns guard type gate, producer/consumer identities and native integration controls. | v6 default/v7 guarded; old identities explicit; valid shifts have native/reference agreement, malformed non-shifts remain rejected. |
| X3 | Root orchestrates remote qualification. | Format/default/core-only/Clippy/layout, affected pinned producer/native suites, independent oracle, meaningful source mutations and existing generated replay; source/tool hashes and distinct failures retained. |
| X4 | Root retries original captured frame pair and reconciles documentation. | Same dump hash, capture-only roots/premises/declared budgets; locate remaining gaps without inventing semantics or claiming executed history. |

All builds run in task-private WSL on `windows-dev`. Reuse verified caches with separate replay/mutation target directories and check free disk. Prefer focused loops before full-dump runs. Retain all prior reports and archives as historical; new evidence lives under `evidence/Ariadne/bap-shift-width/20261014/`.

## Execution checkpoint, 2026-10-14

[Validation](../../../evidence/Ariadne/bap-shift-width/20261014/validation.json) binds the original red loop, independent width/count/origin controls, exact pinned-library probe, v6/v7 profile migration, affected root/native checks, six meaningful source mutants, 27 model scenarios and 330 replay observations. All Cargo/native/model compilation ran remotely. The canonical [design's dated entry](../../../docs/Ariadne/bap-shift-count-design.md#validation-and-dated-execution) owns the exact tier counts, review and retained failed attempts.

The captured XORPS projects with coarse vector effects and retained legacy upper-half origins. No opcode bypass, width padding, count masking/truncation, precise vector aggregate kill or new scalar/address/target precision was introduced. General `Unknown` data keeps its prior opaque policy. The original full frame-pair retry now encounters the 4 MiB guard-evidence cap rather than operand-width admission; a 32 MiB request is rejected by the existing profile contract. No final full-dump query/receipt or path qualification follows. All scoped stages are complete, with those independent limits retained. No commit/push was performed.
