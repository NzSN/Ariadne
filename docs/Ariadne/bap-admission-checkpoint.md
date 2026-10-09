# BAP v3 admission execution checkpoint

## Context and follow-up

**Status.** Implementation checkpoint on 2026-10-10. P0–P3 are delivered with
focused checks. P4 aggregate acceptance is incomplete, and the external Electron
tier is unexercised. This checkpoint is not release qualification.

**Why this document exists.** The user requested execution of the
[projection-admission plan](../../Plans/bap-projection-admission.md), followed
by publication of its current implementation and plan state.

**What this document establishes.** Implemented behavior, actual passing checks,
the producer-mutation failure, its checked harness repair and the exact
remaining acceptance boundary.

**Where to go next.**

- [Plan execution ledger](../../Plans/bap-projection-admission.md#execution-ledger-2026-10-10)
  and [resume order](../../Plans/bap-projection-admission.md#resume-order) — complete
  the outstanding harness, aggregate, measurements and external-query work.
- [V3 contract](bap-admission-contract.md) — frozen expectations, admitted
  capabilities, failure classes and explicit profile migration.
- [Partial qualification artifacts](../../evidence/Ariadne/bap-admission/checkpoint.json)
  — source/tool-bound checkpoint and retained rejection evidence.
- [Backend design](bap-semantic-backend-design.md) and [backend guide](modules/bap.md)
  — production ownership, configuration and capture-only invariants.

**What remains unresolved.** There is no passing P4 aggregate for this changed
snapshot. The mutation classifier and frozen source pin are repaired against
retained evidence, but their fresh extended campaign must finish. The v2 baseline is pinned to the verified pre-change source revision;
post-commit reproduction still needs a complete fresh run. Fixed-budget and owned-query phase/size/limit
measurements and the original/scoped Electron query still require completion.
No executed path, bad-RSI cause, universal refinement or ISA proof follows.

See the [documentation map](../documentation-map.md) for wider navigation.

## Delivered behavior

Production uses `bap-bit-provenance-v3`. SUB64ri8, MOVZX32rm8, XOR64rr and CMP8mi
project from typed BIL with independent byte-cell, flag and address expectations.
The generic opcode whitelist is removed. Architectural namespace, types, widths,
virtual binding, prefixes, control and decoded operand roles still constrain
admission. Definite kills require justified replacement; stores remain weak.

Valid ordinary instructions with unsupported data-only semantics retain their
structural continuation, all tracked uses/may-defs, no must-defs and
`opaque-ordinary` / `unsupported-data-effects` diagnostics. Malformed input and
resource failures abort the query; empty/unmodeled control stops conservatively.
Calls/returns retain their separate opaque summaries and LLVM supplies decoded
facts without effect fallback.

Rust capture/report binding and the OCaml capture validator check v3 opaque
summaries. The producer–opaque–consumer regression retains both earlier and
opaque origins, produces a partial explanation and preserves diagnostics in
text, JSON and DOT. Direct native tampering tests bypass Rust prevalidation.

The pinned runtime and existing bridge were reused. Native helper rebuilds used
the existing isolated SDK; no BAP source rebuild or new SDK installation was
needed. Current coverage is **58 exact BIL cases / 37 projected forms**. CLC
remains an explicit empty-lift gap. CMP's repeated BIL load expressions retain
their separate attribution while matching one decoded byte-operand footprint.

## Exercised checks and limits

| Check | Actual result at this checkpoint |
| --- | --- |
| P0 contract/baseline | Frozen before runtime edits; four actual rejected queries retained. |
| Initial forms | Thirteen independent boundary encodings pass on Linux/Windows targets. |
| Independent numeric oracle | 104 pinned BIL result/flag/zero-extension comparisons pass. |
| Capability/hostile controls | Composition, malformed alternatives, namespace/control/prefix exclusion, unknown data and resource controls pass. |
| Producer/native boundary tests | Eight producer tests and the expanded disagreement/protocol tests pass. |
| Native capture/CLI | Five ignored capture/parity/report/tampering tests and supplied-stateflow CLI pass. |
| Root checks | Default and core-only tests, formatting, all-feature/all-target Clippy and layout pass; 109 Rust files retain the root layout. |
| Native generated replay | 168 recovery + 162 stateflow observations pass; wrong digests dispatch zero observations. |
| Native algorithm mutants | All twelve cause the intended behavioral mismatches. |
| Native boundary mutants | Eight reported rejections, including lost term snapshot and lifecycle/observation defects. |
| Producer corpus/model | 58 retained BIL cases match; eight model cases match all nine fields over 99 states. |
| Controlled workload decisions | Sixty producer/validator/aggregate Python controls pass. |
| V2/v3 migration | Earlier focused comparison reproduces 24 historical v2 hashes and verifies only declared profile/derived-ID changes; final source-bound refresh remains part of P4. |
| Full P4 / external Electron | **Not accepted.** Remaining clauses are listed in the plan. |

Stage 1's refreshed release samples measured the controlled 98-start Windows
Rust-reference CLI at **657.39 ms** under the unlimited BAP policy. Its 98 starts,
99 edges, 90-site slice and zero obligations pass. These samples are not native
I4 explanation-budget acceptance and do not waive I4/I5 limits.

## Rejected mutation receipt

The first extended producer mutant removes the real prefix guard. The unchanged
corpus test fails on `lock`, at its explicit rejection assertion, with exit code
101 and no compile failure. The harness requires the literal word `assertion`
in the output; Rust's custom assertion message prints only `"lock"`. It therefore
reports `NOT ACCEPTED` and stops the extended mutation campaign.

The [raw failure log](../../evidence/Ariadne/bap-admission/prefix-mutation.log)
and [checkpoint receipt](../../evidence/Ariadne/bap-admission/checkpoint.json)
preserve that distinction. This is a recognition defect in the campaign, not a
passing mutation gate. Repair the classifier against this exact assertion
without weakening the test or accepting compile failures/timeouts as sensitivity.
The repair now recognizes that exact retained assertion; it has not yet been
accepted by a fresh complete mutation campaign. The v2 source pin is fixed at
`ebb2e534e8da339f498f20d0a9e1e0b8506a3bdd`, with all five frozen P0 hashes checked.

The independent producer/adapter/native-capture mutation campaign is intended
to cover 25 cases. Only its observed results may be credited. Older v2 records
remain historical after the source/profile changes.

## Qualification and reproduction

Run the source-frozen campaign through the sealed dependency view:

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/i5b-dependency-snapshot \
  --sha256 a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854 -- \
  python3 tools/check_bap_admission.py --output target/bap-admission-new-run
```

Use new output/build directories for replay and mutations. The failed run uses
`target/bap-admission-qualification-20261010`; paths in retained records identify
that exercised environment and do not guarantee temporary files persist.

The external artifact must match SHA-256
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`
and thread `0x5c74`, or supply the independently bound scoped-derivative proof.
Scanner/PreParser roots and seeds require their exact witnesses. No raw customer
dump or source file is added to the repository by this checkpoint.
