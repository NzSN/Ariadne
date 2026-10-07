# I5c: fault-time address-wrap assessment

## Context and follow-up

**Status.** Selected design on 2026-10-07, source-reviewed against `1344c99`.
This document names the next question I5c. The linked W0–W5 implementation plan
is written; every implementation and qualification stage remains pending.
No new assessment interface, CLI option, model or capture is delivered here.

**Why this document exists.** The [investigation design](investigation-layer-design.md#higher-level-questions-after-the-first-slice)
leaves arithmetic hypotheses open. [I5a](i5a-contracts.md) computes an effective
address and asks whether it starts at zero. [I5b](i5b-contracts.md) asks whether
the encoded base is zero with a nonzero displacement. Neither makes the
before-reduction address calculation and wrapping predicate a separate result.

**What this document establishes.** One exact arithmetic question, its source
origin, finite admission profile, small interface, strict evidence/result rules
and separate implementation, fixture and controlled-Windows acceptance tiers.
Wrap describes conditional address arithmetic, not a programming error.

**Where to go next.**

- [I5c implementation plan](../../Plans/i5c-address-wrap.md) — W0–W5 ownership,
  mandatory controls, model contract, preservation and qualification exits.
- [I5b source review](i5b-source-review.md) — reviewed encoded base/displacement
  roles, six MOV forms and the existing independent decode/BAP agreement checks.
- [I5a contracts](i5a-contracts.md) — sealed fault observations, site/operation
  association, validity groups and the existing narrow access-range policy.
- [Investigation ledger](../../Plans/investigation-layer.md) — I5c is selected,
  I5a/I5b are delivered, and other arithmetic/history/lifetime questions remain open.
- [Formal-model guide](../../Specs/README.md) — W0 must make the question-level
  TLA+ contract authoritative before runtime implementation; model checking,
  Rust conformance and hardware capture evidence remain different tiers.

**What remains unresolved.** All W0–W5 work remains pending. The first profile
cannot grant a definite assessment for mathematical underflow because its
resulting access is outside the inherited lower-range admission policy. Indexed,
32-bit addressing, general canonicality, Linux, earlier executed arithmetic and
object lifetime require separate contracts. No new timing or release acceptance
is claimed. The existing I4/I5a/I5b results retain their original identities.

For the wider context, see the [documentation map](../documentation-map.md).

## Exact selected question

> Under the admitted captured-instruction and exception-context premises, did
> this access's encoded base-plus-signed-displacement calculation leave the
> unsigned 64-bit address interval before modular reduction?

The question concerns the selected instruction at fault time. It does not ask
whether a predecessor overflowed, which path executed, whether source-language
arithmetic was erroneous, or whether wrap caused the crash. Registers and bytes
are captured observations; operand interpretation and arithmetic are derived
under the same declared pre-access/context and trusted-lifting premises.

Let:

- `M = 2^64`;
- `B` be the validity-qualified full 64-bit GPR base, interpreted unsigned;
- `D` be the **signed encoded** disp8/disp32, or zero for no displacement;
- `T = B + D` be an integer sum before reduction;
- `q = -1` if `T < 0`, `q = 1` if `T >= M`, and `q = 0` otherwise;
- `EA = T - q*M` and `wrap = (q != 0)`.

The reviewed displacement domain gives
`-2^31 <= T <= (M-1) + (2^31-1)`, so at most one reduction in either direction
is needed. Rust can calculate `T` exactly in `i128` after converting the
unsigned base and signed displacement separately. No additional crate is needed.
The existing BAP modular expression must evaluate to the same `EA`.

This definition is intentionally representation-aware: `B` is unsigned and `D`
is signed. It is not the carry from `B + (D as u64)`, a CPU flag, or an inference
from the smallness of the fault address. The modular BIL constant alone cannot
recover the displacement's signed interpretation or encoded role; the checked
LLVM decoded receipt is required.

## Examples and the first profile's limit

These examples assume all other instruction/context/evidence premises hold.
`H = 0x0000800000000000` is the inherited admission cutoff, not a discovered
canonical-address width.

| B | D | Integer T | EA | First-profile assessment |
| --- | ---: | --- | --- | --- |
| `0xfffffffffffffff8` | `16` | `18446744073709551624` | `0x8` | Consistent: upper wrap, with a coherent lower-range access. |
| `0xfffffffffffffff8` | `8` | `18446744073709551616` | `0x0` | Consistent: exact upper boundary. Base is nonzero despite EA zero. |
| `0x8` | `-8` | `0` | `0x0` | Refuted: no wrap. Adding the displacement bit pattern would produce a carry, which is not this predicate. |
| `0x10` | `-8` | `8` | `0x8` | Refuted: ordinary negative displacement. |
| `0x0` | `-8` | `-8` | `0xfffffffffffffff8` | Unknown: lower wrap is computable, but the resulting access is outside the profile. |
| `H-4` | `0` | `H-4` | `H-4` | Unknown for an 8-byte access: the span crosses the admitted cutoff even though address arithmetic does not wrap. |

For an access of `S` bytes, require checked nonwrapping `end = EA + S`,
`end <= H`, and `EA <= reported_inaccessible_byte < end`. The reported byte need
not equal EA; a fault can identify a later byte within the selected access.
Address calculation wrap and access-span wrap are different predicates.

Consequently, **the v1 fault-assessment support tier covers upper wrap and no
wrap within the admitted access profile**. Every mathematical underflow produces
an upper-range EA for these displacement widths and therefore remains unknown.
The design does not silently widen I5a/I5b range admission to claim underflow
support. A future profile may do so after a separate exception/address contract.

## Source-grounded reuse and new work

| Current source | Existing responsibility | I5c use or addition |
| --- | --- | --- |
| [Address evidence](../../src/effects/address.rs) | Modular affine expression over before-instruction GPR values. | Preserve the expression and its gaps; do not infer signed encoding from its constant. |
| [Decoded receipt](../../src/llvm_mc/address_reference.rs) | Reviewed finite ModRM/SIB forms, exact base/index/scale and signed displacement, bytes/row/tool identity. | Reuse the receipt without extending decoder protocol, display operands or LLVM effects. |
| [Fault binding](../../src/input/investigation.rs) | Reader-owned context plus the exact completed query; checks receipt bytes/length/raw row against preparation. | Add a question-specific sealed `bind_address_wrap` adapter using those same checks. |
| [I5a decision](../../src/investigation/zero_address.rs) | Common fault/site/form/operation/validity admission, modular EA, lower-range span and reported-byte checks. | Reuse its admission and EA; classify the wide sum separately. Do not derive wrap from its zero-address conclusion. |
| [I5b decision](../../src/investigation/zero_base_offset.rs) | Base/no-index receipt and BAP term/constant agreement. | Share these actual duplicated rules through a private module while preserving all old gaps, optional fields, IDs and serialized bytes. |
| [Fault fields](../../src/investigation/fault_context.rs) | Typed captured fields, source spans, required validity and snapshot identity. | Use valid exception-context values only; raw zero bytes or another thread context cannot substitute. |

`zero_address::decide` already retains a computed EA before its final range and
reported-byte checks. That permits a careful distinction between arithmetic
facts and fault-assessment admission. The existing I5b wrapper suppresses its
base/displacement fields whenever gaps remain; that behavior must stay byte-exact.
The new I5c result may retain independently supported arithmetic facts after a
late range/data-byte gap, while its **assessment remains unknown**.

The private shared module should own decoded base/displacement agreement facts
and their gaps. The existing I5a admission remains the source of fault-access
checks. I5b keeps its current result construction and IDs. I5c adds only its
wide calculation and question-specific evidence/result construction. This
concentrates repeated knowledge without a generic hypothesis registry, pluggable
solver, new dependency configuration or a new native-core protocol.

## Admission, conclusions and errors

Proposed profile:
`windows-amd64-av-scalar-mov-base-displacement-wrap-v1`.

Require the current non-chained Windows AMD64 ordinary read/write AV context,
matching exception RIP/location, reached captured instruction, pinned BAP
`external_lift`/projection evidence and one unconditional access. Admit the six
reviewed MOV32mi/MOV64mi32/MOV32rm/MOV64rm/MOV32mr/MOV64mr forms, with one 64-bit
GPR base and encoded zero/disp8/disp32. RSP needs CONTROL validity; other bases
need INTEGER validity. Every exception/site check still applies.

The exact reviewed receipt, selected bytes/opcode/access, register bank,
coefficient-one BAP term and displacement constant must agree. Require no index,
segment, RIP-relative form, address-size override, unsupported prefixes or
semantic gaps. Reviewed SIB-without-index bases remain eligible. Store payload
registers and immediates never enter `B + D`.

There are two internal readiness predicates:

1. **Arithmetic facts ready:** captured/site/context admission through modular
   evaluation passes; the exact base/displacement receipt agrees with bytes and
   BAP; the valid base observation is present; wide and modular EA agree.
2. **Fault assessment ready:** arithmetic facts are ready, all remaining
   nonwrapping lower-range span/operation/reported-byte checks pass, and all
   mandatory evidence and decision claims survive the output budgets.

| Conclusion | Meaning |
| --- | --- |
| `consistent_with_evidence` | Fault assessment ready and `T < 0 or T >= M`. The current range policy permits only the upper-wrap branch to qualify. |
| `refuted_under_premises` | Fault assessment ready and `0 <= T < M`. This refutes only address wrap at this selected access. |
| `unknown` | Missing, unsupported, conflicting or budget-omitted premises prevent the assessment. It can coexist with conditional arithmetic facts after a late range/data-byte gap. |

Unknown never becomes refutation merely because a base is nonzero or EA is
small. Indexed expressions remain unknown even with a captured zero index.
Malformed bindings/identities, changed preparation or receipt contents, invalid
sites/access indices and forged serialized claims are errors independently of
budgets. Legitimate decoder/BIL disagreement is an explicit gap.

## Proposed small interface

```text
input::investigation::bind_address_wrap(prepared, completed, question)
    -> BoundAddressWrapContext

investigation::assess_address_wrap(bound, AddressWrapLimits)
    -> AddressWrapAssessment
```

The bound value owns the existing sealed fault context, selected question and
optional checked decoded receipt. Only the capture adapter constructs it;
public accessors are read-only. An absent receipt remains assessable as unknown.
Snapshot/artifact/query/request/semantic-profile, instruction bytes, context,
receipt, question and assessment profile bind the result's scope/content digests.

Use one already completed `AnalysisView`; investigation reads no mutable dump
or executable, starts no decoder/lifter and reruns no recovery/dataflow. The CLI
adds the question to slice seeds, never entry roots. BAP stays the native default
and sole production effect producer; Rust remains explicit reference/rollback.

## Proposed result, rendering and budgets

Schema: `ariadne.address-wrap-assessment/v1`. Existing strict schemas remain
unchanged. Retain identity/question/profile/context/receipt digests, source
spans, exact instruction bytes/roles, base register/value, signed displacement,
optional arithmetic facts, reported byte, conclusion, premises, typed claims,
gaps, evidence requirements, limits and truncation.

When their dependencies survive, arithmetic facts contain:

- `sum_before_reduction`: canonical signed decimal string representing T;
- `wrap_kind`: `none`, `upper` or `lower`, equivalent to q = 0, 1 or -1;
- `effective_address`: the existing canonical 64-bit address representation.

The wide sum is a mathematical integer, **not a semantic VA or dump offset**.
Encode zero as `"0"`, other values without a plus sign or leading zeros, and
never use JSON floating-point numbers for the wide sum. Bound the spelling to
21 characters before parsing, then enforce the exact reviewed T domain; the
length cap alone is not numeric admission. Strict decoding parses the bounded
exact integer and recomputes it from retained B/D.
A derived `lower` arithmetic fact in an unknown result is not an accepted
lower-wrap fault diagnosis. Text must lead with the unknown assessment and its
range gap before showing that conditional arithmetic fact.

Default `AddressWrapLimits` are separately proposed as 64 evidence and 64 claim
records; I5a/I5b defaults remain untouched. W0 must account for the exact complete
bundle before coding. Omit mandatory records atomically with their dependent
facts/claims. Budget exhaustion yields unknown/truncated; diagnostic arithmetic
cannot survive loss of its own inputs. Validate identities/shape even at zero
limits. Retained references must always resolve within the same scope.

Raw bytes/register fields are observed. Encoded-role interpretation, wide sum,
wrap kind, EA and conclusion are derived under explicit premises. No observed
arithmetic, CPU carry flag, confirmed bug or historical producer is asserted.

Proposed CLI selection is `--assess-address-wrap VA --memory-access N`, with
existing assessment-only text/JSON/DOT and transactional output-directory modes.
Bundle mode would add `address-wrap-assessment.{txt,json,dot}` beside unchanged
base reports. One numeric question, explanation or supplied stateflow selection
at a time; invalid combinations publish no finished bundle. DOT must preserve
the full typed result, and all formats expose the same conclusion and gaps.

## Qualification boundary

W0 first freezes the independent byte/arithmetic oracle and creates the
question-level TLA+ model. Its admitted-result, mathematical reduction,
unknown/refutation and budget invariants are authoritative for this question.
There is no new ISA-step model, hardware semantics proof or native solver action.
Full-width boundary tests remain independent of a representative finite model.

Source/fixture acceptance requires every reviewed form, mandatory negative and
boundary controls, strict reports/bindings/budgets, meaningful real-code mutants,
legacy-byte preservation, root/native/model/replay regressions and matching
source/tool/dependency identities. Compile failures, skipped helpers and timeouts
receive no sensitivity or acceptance credit.

Controlled Windows acceptance separately requires newly owned positive,
no-wrap, signed-negative-no-wrap and indexed-unknown captures in partial/full
modes, independently inspected from raw context/bytes and matching PE evidence.
An old null or zero-base capture can be a regression, but cannot qualify upper
wrap without the exact required operand observations. PE remains comparison
material; production reading is capture-only.

Proposed I5c budgets follow the existing small-assessment policy: 10 ms combined
binding/assessment/all-format rendering median and 1,500 ms normal native-default
release CLI median on each declared timing case, one warm-up/five measured
repeats. W0 freezes them before implementation. Requalify the independent I4
2,000 ms Windows / 250 ms Linux clauses and preserve I5a/I5b limits. Diagnostic,
fixture, controlled-capture and packaged-release tiers remain explicit.

## Design verification on 2026-10-07

A standalone mathematical check verifies all six example rows, including the
signed-negative false-carry controls and the inherited excluded-span policy.
A direct pinned LLVM MC 20.1.2 checked-protocol probe decodes the four proposed
controlled recipes in the plan as MOV32mi with the expected RCX base, absent or
RDX index, and signed displacement 16, 0, -8 or 16. These are design arithmetic
and decode-reference checks; they exercise no BAP address-wrap assessor,
Windows capture, question-level model or new performance workload. W0–W5
remain pending.
