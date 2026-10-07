# I5b zero-base-plus-displacement contracts

## Context and follow-up

**Status.** Implemented and qualified on 2026-10-07 for the recorded source/fixture
and controlled partial/full Windows corpora. [Validation](i5b-validation.md)
records all 18 aggregate gates, timings and exact source/tool/dependency identity.

**Why this document exists.** The [I5b design](i5b-zero-base-offset-design.md)
selects a machine-code debugging question distinct from I5a zero-start: whether
the fault-time encoded base is zero with a nonzero displacement.

**What this document establishes.** The actual binding/assessment interface,
decoded-role evidence, strict result, admission, budget behavior and CLI flow.

**Where to go next.**

- [Execution plan](../../Plans/i5b-zero-base-offset.md) — B0–B5 ownership and acceptance exits.
- [Source review](i5b-source-review.md) — exact encodings, decoded tuple positions and independent oracles.
- [Validation record](i5b-validation.md) — fresh qualification results and exercised scope.
- [I5a contracts](i5a-contracts.md) — the reused context checks and independently preserved question.

**What remains unresolved.** Later changes require fresh or exact-inventory-verified
qualification. Indexed,
Linux, historical provenance and object lifetime remain outside this profile.
This capability does not close the independent I4 timing condition.

## Machine-code debugging question

The result concerns the exact selected captured instruction/access. The predicate
is `captured encoded GPR base == 0 AND signed displacement != 0`, under the
admitted ordinary access/context premises. It does not identify a historical
producer as executed or assert a source-language null-pointer root cause.

For `[RCX+8]` with valid captured RCX zero and coherent write-to-eight exception
parameters, I5b is consistent while I5a zero-start is refuted. For `[RCX]` with
RCX zero, I5b is refuted while I5a is consistent. Effective address zero from a
nonzero base plus modular displacement does not establish a zero base.

## Interface and evidence

```text
input::investigation::bind_zero_base_offset(prepared, completed, question)
    -> BoundZeroBaseOffsetContext
investigation::assess_zero_base_offset(bound, ZeroBaseOffsetLimits)
    -> ZeroBaseOffsetAssessment
```

The bound value is owned and read-only; only the capture adapter can construct it.
It reuses exact completed-query and sealed fault-context binding. The question is
bound once, with semantic VAs kept distinct from artifact file offsets.
Investigation starts no decoder, lifter or dataflow process and reads no mutable
input files. Questions add slice seeds, never entry roots.

Schema: `ariadne.zero-base-offset-assessment/v1`.
Profile: `windows-amd64-av-scalar-mov-base-displacement-v1`.
The existing explanation and I5a v1 schemas remain unchanged.

[DecodedAddressReference](../../src/llvm_mc/address_reference.rs) is retained
during existing LLVM reference preparation. It binds consumed instruction bytes,
VA/length/opcode, raw record, tuple position, base/index/scale/displacement/segment,
widths/RIP-relative classification and decoder executable/version/protocol/target.
Reviewed finite ModRM/SIB checks compare roles with the actual bytes. This is
decoded-fact validation, not LLVM effect fallback or an instruction-step proof.
The BAP session rejects decoder executable changes during/between batches or at
finish. The receipt is joined to the same site's BAP expression and capture spans.

Scope/content digests bind snapshot/artifact/query/request/semantic identity,
selected question, full context digest, new schema/profile and decoded receipt.
Raw fields/bytes are observed; role matching, arithmetic and conclusions are
derived under explicit premises. A complete producer explanation is unnecessary
for this bounded numeric question; an opaque upstream call remains visible.

## Admission and conclusions

Use I5a's Windows AMD64 scalar MOV access-violation context/site/operation/span
checks. Initial forms are the six reviewed MOV32mi/MOV64mi32/MOV32rm/MOV64rm/
MOV32mr/MOV64mr base/displacement variants. Require one unconditional access,
one encoded 64-bit GPR base, no index/segment/address-size override, matching BAP
coefficient-one term/constant, valid full base observation and no decoded gaps.
Implicit zero, signed disp8/disp32 and reviewed SIB-without-index cases are handled.
RSP requires CONTROL validity; other GPR observations require INTEGER validity.

EA is computed modulo 2^64; the ordinary access span must not wrap and must lie
wholly below `0x0000800000000000`. The reported inaccessible byte must be within
that span and have the matching operation. Negative zero-base displacements
outside this narrow range remain unknown. The range is not a general address-
canonicality diagnosis. Thread-list registers are never a fallback.

| Conclusion | Meaning |
| --- | --- |
| `consistent_with_evidence` | All admission/evidence checks hold, base is zero and displacement is nonzero. |
| `refuted_under_premises` | All checks hold, but base is nonzero or displacement is zero. |
| `unknown` | Missing/unsupported/conflicting evidence or output-budget exhaustion prevents the assessment. |

Absolute, RIP-relative, indexed/index-only and merged base/index expressions are
unknown under this profile. Affine terms cannot substitute for the encoded role.
Malformed records, changed bindings and invalid site/index selections are errors
independently of budgets; legitimate decoded/BIL disagreement is an explicit gap.

## Strict result, limits and debugging output

Defaults are 64 evidence and 64 claim records, separate from unchanged I5a 32/32.
The usual full context plus the decoded receipt uses 33 evidence records and 34
claims. Zero/tiny/exact-fit budgets are exercised. Omission of mandatory evidence
or a decision claim yields unknown/truncated, with valid retained references.

The result retains the selected bytes/opcode, decoded role receipt, base register/
value, signed displacement/bitvector, EA and reported inaccessible byte, capture
observations/spans, assumptions, typed claims, gaps and evidence requirements.
Strict decoding recomputes role/encoding/BIL agreement, context admission,
arithmetic, predicate, identities and claim/reference closure. Duplicate/unknown
fields, altered receipts/claims and unjustified conclusions fail. This proves
internal consistency, not authenticity of an arbitrary supplied dump.

Text starts with machine-code facts for debugging. JSON and DOT preserve the same
typed evidence/claims; DOT embeds the complete result in its metadata comment.

## CLI and qualification

```sh
target/release/ariadne-minidump tests/input/fixtures/i5b/mov32mi-positive.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 401000 \
  --assess-zero-base-offset 401000 --memory-access 0 \
  --assessment-only --format text
```

Use a new `--output-dir` instead of assessment-only format for base reports plus
`zero-base-offset-assessment.{txt,json,dot}`. Output publication is transactional.
Unknown is a valid answer; bad options/bindings/infrastructure publish no finished
bundle. Another numeric question, explanation or stateflow cannot be combined
with this first I5b product mode. Native BAP is default; Rust is explicit.

The [qualification runner](../../tools/check_i5b.py) requires a sealed dependency
snapshot, the pre-change legacy baseline and independently inspected controlled
captures. The [performance contract](../../tests/input/fixtures/i5b/performance.json)
freezes 10 ms combined phase / 1,500 ms CLI medians, one warm-up and five measured
release repeats. No fixture-only result satisfies real-Windows acceptance.
