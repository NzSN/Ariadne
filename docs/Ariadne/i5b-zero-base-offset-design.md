# I5b: zero base plus nonzero displacement

## Context and follow-up

**Status.** Selected design on 2026-10-07, based on checkout `ae987bc`.
B0–B5 are implemented and qualified within the recorded finite corpora. See the
[actual contracts](i5b-contracts.md) and [qualification](i5b-validation.md) for
the 18 gates, exact source/tool inventory and separate controlled Windows tiers.

**Why this document exists.** The [investigation design](investigation-layer-design.md)
leaves null-derived offsets among later questions. [I5a](i5a-contracts.md) can
refute zero-start for `[RAX + 8]` with captured RAX zero, while leaving the
distinct zero-base question unanswered.

**What this document establishes.** One fault-time predicate, a finite scalar-MOV
admission profile, the additional decoded-role evidence needed, a small assessment
interface, and separate acceptance tiers. The claim concerns an observed register
value at the selected instruction, not historical null provenance.

**Where to go next.**

- [Implemented contracts](i5b-contracts.md) and [source review](i5b-source-review.md)
  — actual interface, decoded-role checks and independent fixture expectations.
- [I5b implementation plan](../../Plans/i5b-zero-base-offset.md) — B0–B5 source
  ownership, fixtures, reports, mutation and controlled-capture qualification.
- [Investigation stage ledger](../../Plans/investigation-layer.md) — selected I5b,
  delivered I5a, the open I4 condition and the other deferred hypotheses.
- [Existing fault-context contract](i5a-contracts.md) — the capture/context
  prerequisites reused by the implemented assessment.
- [Assurance decision](semantic-assurance.md) — trusted BAP lifting and active
  analysis-level validation, distinct from retired ISA proofs.

**What remains unresolved.** Qualification is source/tool-bound and corpus-scoped;
later changes require fresh or exact-inventory-verified acceptance.
Indexed, Linux, historical-provenance and object-lifetime questions remain later
deliveries. Existing I4/I5a records do not qualify I5b or waive their own criteria.

## Selected question

For a selected captured memory access, ask:

> Under the admitted exception-context and instruction premises, is its encoded
> GPR base zero while its signed displacement is nonzero?

The first profile admits simple base-plus-displacement addressing with no index:

```text
EA = (B + bitvector64(D)) mod 2^64
H  = (B == 0) AND (D != 0)
```

`B` is a valid full-width captured value of the independently identified encoded
base GPR. `D` is the reviewed signed displacement, including implicit zero.
The predicate is evaluated only after every admission and evidence check passes.
The reported inaccessible byte must be inside the admitted access span; it need
not equal the access start for a multi-byte access.

| Captured operands, with coherent exception evidence | I5b | Relationship to I5a |
| --- | --- | --- |
| `[RAX + 8]`, RAX = 0 | Consistent with the evidence: B = 0, D = 8, EA = 8 | Zero-start is refuted. |
| `[RAX]`, RAX = 0 | Refuted under premises: D = 0 | Zero-start is consistent. |
| `[RAX + 8]`, RAX = 0x1000 | Refuted under premises: B is nonzero | Zero-start is refuted. |
| `[RAX + 8]`, RAX = 0xfffffffffffffff8 | Refuted under premises: B is nonzero, EA = 0 | Zero-start is consistent; arithmetic alone does not establish a zero base. |
| `[RAX + 8]`, raw RAX bytes zero but its validity group absent | Unknown | Raw zeros do not supply a captured register observation. |

These examples specify independent fixture expectations, not new acceptance
claims. Known context/site/data-address contradictions produce unknown.

## Source facts and the missing seam

The current sources establish these reusable facts and limitations:

| Inspected source | Consequence for I5b |
| --- | --- |
| [AddressExpression](../../src/effects/address.rs) and [BIL extraction](../../src/bap/address.rs) retain canonical affine terms and a constant. | They support arithmetic, but erase encoded base/index roles and can merge or cancel terms. A coefficient-one term alone does not establish an encoded base. |
| [InstructionEvidence](../../src/effects.rs) retains decoded operands and the raw LLVM record. | This is an existing decoded-fact seam; LLVM remains a reference rather than an effect provider. |
| [Decoded operand projection](../../src/llvm_mc/reference.rs) currently creates a typed Memory operand only for the two immediate-store MOV forms. | The other four candidate forms need reviewed row-layout projection before their decoded base role can be admitted. |
| [SiteEvidence](../../src/investigation/model.rs) and [capture binding](../../src/input/investigation.rs) omit decoded operand roles from the strict question evidence. | Existing BoundFaultContext alone cannot support the new encoded-base assertion. Add question-specific evidence through a new binding, without extending the old v1 schemas. |
| [Fault context](../../src/investigation/fault_context.rs) and [I5a assessment](../../src/investigation/zero_address.rs) validate immutable observations and bounded arithmetic. | Reuse context acquisition and admission premises; preserve every existing I5a decision and serialization behavior. |

Add a decoded-address receipt during existing preparation, not a new decode launch
inside investigation. It binds the exact VA, consumed bytes, length, opcode,
memory-operand association, GPR base, optional index, scale, signed displacement,
address/access widths and RIP-relative classification to the retained raw record,
decoder version/protocol and executable digest. Preserve explicit unsupported
or disagreement states. Ordinary BAP preparation and old reports remain usable
when I5b-specific decoded facts are unavailable.

Under the admitted shape, require the BAP expression to have exactly the decoded
base bank with coefficient one and constant `bitvector64(D)`. Compare access role,
width and byte identity as well. A legitimate provider disagreement is unknown;
cross-snapshot/query substitution or internally malformed evidence is an error.
Never reconstruct the base role from disassembly text or an affine-term ordering.

## First admission profile

Proposed profile: `windows-amd64-av-scalar-mov-base-displacement-v1`.

Reuse the [I5a context checks](i5a-contracts.md#evidence-and-admission): immutable
Windows AMD64 capture, supported non-chained read/write access violation,
valid matching exception RIP/location, reached captured instruction, admitted
BAP semantics, one ordinary unconditional access, required validity-qualified
register observations, and coherent operation/data-address parameters.

The additional profile requirements are:

1. A reviewed decoded-address receipt identifies exactly one 64-bit GPR base,
   no index and no segment/address-size override. RIP-relative, absolute,
   index-only and indexed expressions remain unsupported, even when their
   flattened BIL happens to look like one register plus a constant.
2. No-displacement, signed disp8 and signed disp32 encodings are decoded exactly.
   SIB encodings with a real GPR base and no index may be admitted after review;
   their mere use of SIB does not establish an index. RSP/RBP/R12/R13 addressing
   special cases require explicit fixtures and the appropriate context groups.
3. The decoded tuple agrees with the BAP expression and the selected access.
   Store payload values never enter the address predicate.
4. Compute EA modulo 2^64, then apply the existing nonwrapping access-span
   condition wholly below `0x0000800000000000`. This intentionally narrow range
   is an admission condition, not a general noncanonical-address classifier.
   A zero base with a negative displacement outside that range returns unknown.
5. Every required evidence item and decision claim survives the selected budgets.

Begin with reviewed `MOV32mi` base/disp cases, then qualify base/disp cases for
`MOV64mi32`, `MOV32rm`, `MOV64rm`, `MOV32mr` and `MOV64mr`. All six forms are the
implemented finite matrix; opcode names alone do not grant coverage. Unsupported
prefixes, multi-access, repeated/string, atomic/locked and vector operations
retain unknown outcomes. Linux requires a separate admission profile.

## Decision contract

| Conclusion | Required conditions |
| --- | --- |
| `consistent_with_evidence` | Complete admitted evidence, all consistency checks pass, B = 0 and D != 0. |
| `refuted_under_premises` | Complete admitted evidence and all consistency checks pass, but B != 0 or D = 0. |
| `unknown` | A prerequisite, supported shape, consistency check or required output record is missing, conflicting, unsupported or budget-omitted. |

Shape exclusions precede predicate evaluation. An absolute or indexed address is
unknown, not a refutation of a question the profile cannot interpret. Checking a
convenient nonzero register is insufficient when the required base observation
or receipt is missing. Invalid sites/access indices, malformed identities and
tampered evidence remain errors independently of budgets.

The result preserves base register/value, signed displacement and its bitvector,
the decoded/BIL agreement, EA, width/role, reported data byte, evidence IDs,
premises, gaps and actionable evidence requirements. Raw bytes/register fields
are observed; decoded roles, arithmetic and conclusions are derived under
premises. No result asserts null-pointer causation, actual predecessor execution,
object lifetime or numerical confidence.

## Interface and ownership

```text
input::investigation::bind_zero_base_offset(prepared, completed, question)
    -> BoundZeroBaseOffsetContext

investigation::assess_zero_base_offset(bound, ZeroBaseOffsetLimits)
    -> ZeroBaseOffsetAssessment
```

The new bound value owns the existing fault context plus selected-site decoded
evidence and gaps. Construction is sealed to the input adapter; public callers
cannot manufacture it from an arbitrary register map. The selected question is
bound once, preventing evidence for one access from being assessed as another.

This is a deep module with one domain interface. It accepts completed normalized
inputs and returns a typed answer, with no decoder, solver, file I/O or renderer
inside the assessment. Share a private scalar-access admission/evaluation helper
with I5a only when old outcomes and bytes are demonstrably preserved. Avoid a
generic hypothesis/provider framework for this second numeric question.

The new scope digest binds the existing snapshot/artifact/query/request/semantic
identity, context digest, question, new schema/profile and decoded-role receipt
digest. Receipt changes change scope and content IDs. Keep the original fault-
address explanation and I5a v1 schemas independent.

## Reports, limits and product flow

Proposed schema: `ariadne.zero-base-offset-assessment/v1`.
Proposed CLI question: `--assess-zero-base-offset VA --memory-access N`.
Use the existing `--assessment-only --format text|json|dot` convention or a new
output directory with `zero-base-offset-assessment.{txt,json,dot}` beside the
unchanged base reports. Assessment questions are mutually exclusive with each
other, fault-address explanation and stateflow in this first CLI delivery.

The selected instruction becomes a seed, never a root. Preparation and core
analysis each run once; native BAP remains default with explicit Rust selection.
Publication stages the complete bundle before renaming. Unknown is publishable;
invalid options, bindings, schemas and infrastructure failures are errors.

Freeze separate I5b defaults of 64 evidence and 64 claims. B0 found that the
full existing context already uses 32/32, so retaining that limit would truncate
the new receipt and decision claims. I5a's defaults remain unchanged. Count the
new decoded receipt and its references.
Zero/exhausted limits return unknown with `truncated=true`, explicit budget gaps
and no dangling IDs. Emit a definite conclusion only when all mandatory records
and claims remain. Strict decoding recomputes identities, receipt/BIL agreement,
context admission, arithmetic, predicate and reference closure.

## Acceptance scope

The [implementation plan](../../Plans/i5b-zero-base-offset.md#b5--qualification-and-evidence)
defines independent fixtures, mutation controls, old-result equivalence and
controlled Windows capture work. Source/fixture acceptance and real-capture
acceptance are separate booleans. Existing zero-displacement I5a captures can
be useful refutation controls but cannot supply a positive I5b case.

Proposed new measurement ceilings are a 10 ms combined binding/assessment/all-
format-render phase median and a 1,500 ms assessment-CLI median on the frozen
small workloads. B0 freezes them before measurement. One warm-up and at least
five measured release repeats apply separately to the declared fixture and
controlled-capture corpus. These are new I5b proposal criteria; no measurements
or acceptance are claimed here, and the separate I4/I5a conditions remain intact.
