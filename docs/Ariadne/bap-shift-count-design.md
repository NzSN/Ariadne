# BAP shift-count widths and captured XORPS

## Context and follow-up

**Status.** X0–X4 implemented and finitely validated on remote WSL on 2026-10-14. The [execution record](../../.agents/plans/completed/bap-shift-counts.md) is complete. Original XORPS admission succeeds; the initial full captured retry reached the guard-evidence limit. The later [configurable-budget delivery](justified-branch-pruning-design.md#configurable-guard-budgets) releases that profile ceiling, with separate source-bound validation and remaining coverage/transport limits.

**Why this document exists.** The earlier [guarded dump retry](justified-branch-pruning-design.md#captured-retry-and-remaining-boundary) aborted at captured `XORPS xmm0,xmm0`, VA `0x00007ff7744075b3`, bytes `0f57c0`, with `BIL operand type/width mismatch`.

**What this document establishes.** The source-grounded diagnosis, generic BIL shift contract, count/provenance safeguards, producer identities, implementation ownership and separate original-dump retry boundary.

**Where to go next.** Read [BAP integration](bap-analysis-core-design.md#projection) for typed transport and projection, [semantic assurance](semantic-assurance.md) for trusted lifting, and the [execution plan](../../.agents/plans/completed/bap-shift-counts.md) for tasks and gates. The [pinned-source research](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-shift-width/20261014/pinned-bap-source-research.md) retains primary source provenance.

**What remains unresolved.** This fixes BIL shift typing/projection compatibility. It does not introduce exact vector values, general SIMD coverage, new scalar/address/target-resolution precision, hardware shift-count assumptions, executed history or a full-dump path guarantee. Existing incomplete control, unwind and resource limits remain separate.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Reproduction and diagnosis

A public `bap::Backend::prepare` regression containing only the captured three bytes reproduces the same failure against the current pinned producer on remote WSL. Both runs fail before projection with the identical operand-width message; the full dump is unnecessary for this loop.

The [captured lift](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guard-admission/20261014/artifacts/next-blocker-bil.json) has fourteen statements. At `bil[3].value.rhs`, operator 11 is BIL LSHIFT:

```text
cast128(lane_result32) << (lane_index8 * 0x20:8u)
```

The value is 128 bits; the count expression is eight bits. Multiplication remains eight-bit modular arithmetic. The final YMM0 assignment concatenates its preserved old upper 128 bits with the assembled low half, representing legacy XMM0 behavior.

Ranked hypotheses were: a blanket host type rule, bridge/operator disagreement, and a malformed pinned lift. Primary source resolves the type-rule question: pinned BAP `bap_exp.ml` specially permits two immediate shift operands with independent widths and returns the left type; the locked header maps 9/10/11 to ARSHIFT/RSHIFT/LSHIFT. Ariadne's Rust admission instead applies `same(left,right)` to every binary operation. Its projector and native guard type checker repeat that assumption. The bridge preserves the original widths and operator.

The source archive SHA-256 is `b0f28f00e78958f671d84de918f36be8b068ea2ec4459dc72c6f7fe3a0ecf428`, revision `baa902209ee4be975bdd8db7d1160b0a0ec2831f`. Source and locked assets have separate provenance; source correspondence alone is not a source-to-binary build attestation.

## Required typing and count contract

For exactly BIL operators 9, 10 and 11:

```text
Bits(w_value) shift Bits(w_count) : Bits(w_value)
1 <= w_value,w_count <= 256
```

Both operands remain scalar; memory operands are rejected. Other arithmetic, comparison and bitwise operators retain their equal-width checks. Unknown or unsupported values retain the existing explicit conservative policy.

Interpret the RHS bitvector as an unsigned count. Preserve its own width and any modular arithmetic that produced it. Do not pad it to the value width, truncate it to a machine word, mask it modulo the data width, or import x86 instruction-specific masking into a BIL primitive.

For a known count `n` and value width `w`, logical left/right shifts return zero when `n >= w`; arithmetic right shifts fill with the original sign bit. Count zero preserves all source bits. A bounded comparison/extraction may saturate an already known count at `w` because all larger counts have the same fill outcome; it must work for constant count bitvectors wider than 64 bits. Unknown counts conservatively retain data/count dependencies and uncertainty.

## Provenance and identity safeguards

Bit metadata equality is not proof that two computed values are equal. Distinct unknown shifts can have identical dependency/origin metadata; XOR must not cancel them merely because their abstract vectors compare equal. Permit cancellation only for justified equality such as the same bound variable, equal known constants, or matching preserved source-bit identities. Add independent dependency controls for different and unknown shift counts.

Preserve shared XMM/YMM backing, legacy upper-half origins and the coarse `state:other` gap. Vector writes may-define that aggregate and never must-kill it. Shift-count compatibility alone does not make packed XORPS values concretely known: existing abstract multiplication of lane counts can remain conservative.

Default preparation uses new producer `bap-bit-provenance-v6`; guarded preparation uses `bap-bit-provenance-v7`. Older v4/v5 evidence keeps its original identity and finite scope. Update consumer allowlists and migration controls explicitly. Capture/report field schemas need not change because the typed policy is represented by the producer/checker identities.

## Ownership and exclusions

| Module | Responsibility |
| --- | --- |
| `src/bap/admission.rs` | Shift-only width distinction; strict non-shift typing. |
| `src/bap/projection.rs` | Left-width result, full count interpretation, safe provenance and XOR equality. |
| `native/bap-core/guard.ml` | Equivalent shift typing in strict and opaque-data validation; guard shifts into RSP stay TOP. |
| Producer/profile consumers and tools | Versioned identities and conservative legacy compatibility. |
| `tests/bap/` and native capture tests | Captured regression, independent count/origin controls and mirrored native admission. |

Scalar refinement, affine addresses and target-expression extraction keep their existing limits and explicit unknown results. Expanding their mixed-width numerical precision would require separate paired Rust/native work; this delivery does not coerce wide inputs into those domains. The active analysis models remain authoritative for analysis-level behavior; this is not a revived ISA-proof track.

## Validation and dated execution

The [source-bound validation](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-shift-width/20261014/validation.json) and [268-member artifact manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-shift-width/20261014/qualification/artifact-manifest.json) record 680 source/tool/fixture hashes against the shift-count implementation as qualified then. Later G5 guard-validator/CLI changes have separate qualification; the original records remain immutable. All builds and campaigns ran in a task-private WSL namespace on `windows-dev`; no local Cargo/native compilation was performed.

| Tier | Result and scope |
| --- | --- |
| Reproduction | The exact public Backend three-byte loop failed twice before edits; three unit regressions failed at their intended seams. The fixed captured-lift and producer cases pass. |
| Typing | All 65,536 data/count width pairs × three shift operations pass; unequal-width non-shift and memory/out-of-range controls stay rejected. |
| Independent numeric oracle | 2,133,324 Python integer-equation cases; 18,504 Rust bit/branch-probe rows cover both width axes, representative cross-pairs and boundary counts. These are separate finite tiers. |
| Exact pinned asset | 3,096 Word primitive/literal expression controls pass with observed argument/result widths, signed metadata and loaded-library hash. Constructor-folded literal expressions are recorded explicitly. Direct binary static inference is unexercised because the C API does not export it. |
| Root checks | 186 default tests, 46 core-only tests, format, all-feature/all-target Clippy and layout pass. Ignored suites retain their own prerequisite boundaries. |
| Native | Nine producer, 12 kernel, eight captured/native and one frame-path tests pass. This includes exact XORPS after MOVAPS and fully rehashed non-shift type rejection. |
| Mutations | Five Rust and one native mutant trigger exact named runtime failures after passing controls. Private SUT/helper builds are source-restored and hash-bound; compile errors/timeouts receive no credit. |
| Analysis models/replay | Predicate model typechecks and all 27 finite safety/fair-termination configurations pass; 168 core and 162 stateflow observations match, with both wrong-digest controls rejected. Model bodies are unchanged. |

The initial generic `Unknown` test was corrected to preserve the existing opaque-data policy; it did not justify a runtime relaxation. Typed variable counts with unknown values remain projected conservatively. The first API probe failure exposed smart-constructor folding, and the first mutation classifier missed a custom assertion message; their raw failures remain retained, with later successful runs separately identified. Empty preliminary native filters receive no execution credit; exact nonempty tests and full affected suites were rerun.

A read-only review found no concrete issue in bounded count extraction, justified XOR equality, alias preservation or the scoped numerical exclusions. Finite controls do not prove universal refinement or hardware semantics.

## Original dump retry, 2026-10-14

The original 962,600,678-byte dump retains SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, frame pair 1:0 and NP=10. Reader/runtime-table/output budgets are the same declared expanded API budgets as the prior attempt; roots and bytes remain capture-only.

V6 default still stops at the unproved MOVAPS alignment branch: nine caller and 768 callee sites are decoded, with no usable active-call anchor. V7 guarded preparation no longer aborts on the XORPS operand-width error. It now stops at `materialization limit: guard evidence bytes` under the existing 4 MiB profile cap, before publishing a final query or guard receipt. The listing remains unavailable with zero paths; that is not evidence that no path exists.

A separate attempted 32 MiB evidence cap is rejected as `guard profile limit exceeded`: this reviewed profile permits tightening limits, not increasing them. No limit relaxation was implemented or qualified here. Larger guard-evidence contracts, complete incoming coverage, unwind and full-dump path qualification need separate work. New profiles distinguish this correction without rewriting old v4/v5 evidence or its measured outcomes.

A later [read-only budget diagnosis](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guard-evidence-budget/20261014/README.md) reproduces the same failure with unchanged production limits. The first refused source is the 4,004th lifted instruction, `CMP32rm` at `0x00007ff77440423d`, bytes `413b4f14`: its 4,457-byte BIL would raise the raw AST sum from 4,192,674 to 4,197,131 bytes, exceeding the 4,194,304-byte cap. All 4,012 sources in the returned batches are unique and within the caller's runtime function range. CMP-family BIL accounts for 1,549,137 bytes; exact XORPS was already passed in batch 51. The cost comes from retaining original BIL throughout the candidate graph, with no duplicate-site charge found. Preparation aborts before guard checking and final query publication, so the retry driver's subsequent `missing-frame-query` listing never enters path enumeration. The separately enforced full input/report, instruction-start and prefix-byte budgets remain part of any future larger-evidence design.


The subsequent [G5 budget delivery](justified-branch-pruning-design.md#g5-budget-configuration-validation-2026-10-14) releases the profile ceilings without changing shift semantics or defaults. Its fresh original caller retry prepares 4,764 candidate sites under explicitly expanded budgets, with a 9,001,701-byte report, but retains incomplete candidate coverage and an unknown MOVAPS verdict. Native initialization separately rejects the request above its 8 MiB frame bound. The initial 4 MiB rejection above is historical; no full-dump paths are qualified by either finite correction.


The later [request-budget delivery](bap-analysis-core-design.md#request-budget-validation-2026-10-14) admits that original larger caller natively with an explicit 32 MiB request budget. This resolves the dated transport rejection, while incomplete candidate coverage and unknown MOVAPS alignment remain. Native initialization success is separate from full core/path qualification.
