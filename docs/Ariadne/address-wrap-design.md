# Fault-time address-wrap assessment design

## Context and follow-up

**Status.** The selected 2026-10-07 design identifies this question as I5c.
The [2026-10-20 W0 qualification](../../evidence/Ariadne/address-wrap/20261020/w0/README.md)
passes its finite model/oracle and synthetic-input gate on the exact promoted
sources. The separate [W1 qualification](../../evidence/Ariadne/address-wrap/20261020/w1/README.md)
passes binding and private-admission preservation: 10 binding tests, 4 I5b tests,
666 unchanged legacy output files and 36 CLI comparisons. Three native I5b tests
remain ignored in W1. The [W2 pilot](../../evidence/Ariadne/address-wrap/20261020/w2/README.md)
passes the public assessor, seven freshly prepared/completed native synthetic
captures, and required Rust gates. The [W3 matrix/report qualification](../../evidence/Ariadne/address-wrap/20261021/w3/README.md)
passes all 140 decisions, 44 binding controls, 24 serialized controls and 114
fresh native cases. W4 CLI/native recipe sources are implemented with their
product/capture gates pending; W5 and full acceptance remain pending.
The [W4/W5 execution preparation](../../.agents/plans/i5c-address-wrap.md#w4w5-execution-preparation-2026-10-21)
adds campaign tooling and retained-baseline verification without advancing those gates.

**Why this document exists.** The [investigation design](investigation-design.md#higher-level-questions-after-the-first-slice)
leaves arithmetic hypotheses open. [I5a](zero-address-design.md) computes an effective
address and asks whether it starts at zero. [I5b](zero-base-offset-design.md) asks whether
the encoded base is zero with a nonzero displacement. Neither makes the
before-reduction address calculation and wrapping predicate a separate result.

**What this document establishes.** One exact arithmetic question, its source
origin, finite admission profile, small interface, strict evidence/result rules
and separate implementation, fixture and controlled-Windows acceptance tiers.
Wrap describes conditional address arithmetic, not a programming error.

**Where to go next.**

- [I5c implementation plan](../../.agents/plans/i5c-address-wrap.md) — W0–W5 ownership.
  Read [W0 contract/model/oracle](../../.agents/plans/i5c-address-wrap.md#w0--freeze-semantics-and-independent-expectations),
  [W1 binding/preservation](../../.agents/plans/i5c-address-wrap.md#w1--exact-binding-and-private-admission-reuse),
  [W2 vertical slice](../../.agents/plans/i5c-address-wrap.md#w2--pilot-calculation-and-bounded-output),
  [W3 complete matrix/reports](../../.agents/plans/i5c-address-wrap.md#w3--mandatory-oracle-and-negative-control-matrix),
  [W4 owned capture/product](../../.agents/plans/i5c-address-wrap.md#w4--product-and-real-controlled-windows-evidence), and
  [W5 qualification](../../.agents/plans/i5c-address-wrap.md#w5--qualification-mutation-sensitivity-and-evidence)
  for the corresponding bounded exit. Source-review findings, actual contracts
  and dated qualification summaries stay in this canonical design.
- [I5b source review](zero-base-offset-design.md#decoded-record-and-independent-oracle) — reviewed encoded base/displacement
  roles, six MOV forms and the existing independent decode/BAP agreement checks.
- [I5a contracts](zero-address-design.md) — sealed fault observations, site/operation
  association, validity groups and the existing narrow access-range policy.
- [Investigation ledger](../../.agents/plans/investigation-layer.md) — I5c is selected,
  I5a/I5b are delivered, and other arithmetic/history/lifetime questions remain open.
- [Formal-model guide](../../Specs/README.md) — W0 must make the question-level
  TLA+ contract authoritative before runtime implementation; model checking,
  Rust conformance and hardware capture evidence remain different tiers.

**What remains unresolved.** W4 product/native-build/owned-capture gates and W5
full qualification remain pending. The first profile
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

## Result, rendering and budgets

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

Default `AddressWrapLimits` are 64 evidence and 64 claim records; I5a/I5b defaults remain untouched. W0 must account for the exact complete
bundle before coding. Omit mandatory records atomically with their dependent
facts/claims. Budget exhaustion yields unknown/truncated; diagnostic arithmetic
cannot survive loss of its own inputs. Validate identities/shape even at zero
limits. Retained references must always resolve within the same scope.

Raw bytes/register fields are observed. Encoded-role interpretation, wide sum,
wrap kind, EA and conclusion are derived under explicit premises. No observed
arithmetic, CPU carry flag, confirmed bug or historical producer is asserted.

The implemented CLI source selects `--assess-address-wrap VA --memory-access N`, with
existing assessment-only text/JSON/DOT and transactional output-directory modes.
Bundle mode adds `address-wrap-assessment.{txt,json,dot}` beside unchanged
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

## W0 finite contract, 2026-10-20

This contract is frozen by the [finite W0 record](../../evidence/Ariadne/address-wrap/20261020/w0/README.md)
and its exact source/tool/raw-input bindings. It does not assert that the
assessor, CLI, native captures or W1–W5 qualification have run. The promoted
23 normal source files are byte-identical to the checked layout. The
[W1 stage](../../.agents/plans/i5c-address-wrap.md#w1--exact-binding-and-private-admission-reuse)
has its own later binding and legacy-preservation qualification below.

Source review confirms that `zero_address::decide` sets modular EA only after
operation, site, context, form and register admission. Only the range and
reported-byte gaps are late. The shared private seam extracts decoded
one-base/no-index and BAP coefficient/constant agreement; I5b keeps its existing
gap precedence: any gap suppresses decoded base/value/displacement, while late
range/reported-byte gaps preserve the admitted evaluated/reported addresses and
computed-address claim. Receipt/base/profile/BIL failures clear the evaluated
address but retain the reported observation; claim-budget failure clears all
operand/address fields. The new I5c arithmetic
survives only late range/reported-byte gaps, never operation mismatch or loss
of its own required evidence.

W1 adds an immutable input-owned seal at final preparation publication: original
request fingerprint and preparation identity, complete instruction-evidence/read
maps and gaps, materialization report and open limits. The new binder compares
all facts before binding, rejecting coherent public edits at unselected sites
as well as the question site. Reader-owned fault metadata remains private;
private refinement receipts are outside this seal. I5b does not consume it.
No completed analysis or reaching-state copy is created.

The independent corpus is fixed at 140 decision rows: six forms times eleven
arithmetic categories (66), 20 boundary/base/payload, 30 exclusion/context,
eight adapter controls and 16 output-budget controls. Of these, 114 use
synthetic capture inputs and 26 use bound-unit substitutions. There are 19
binding negatives, each at 64/64 and 0/0 budgets; 24 strict-result negatives;
12 CLI controls; 24 compiled behavioral mutants; ten fixture timing workloads;
and eight newly owned controlled Windows observations. Required gap sets are
minimum mandatory subsets, while conclusions, arithmetic facts, truncation and
record accounting are exact expectations.

The 114 synthetic inputs must be materialized in the normal fixture layout
with exact hashes, sizes and inventory. The W0 checker binds the actual raw
files and their manifest before and after checking; merely retaining expected
hashes does not satisfy this gate. A separate current-product preparation probe
reviews all 114 decoder/context premises before the promotion freeze. Any
receipt or admission correction is explicit and retains prior failed packets;
SUT preparation observations never supply arithmetic or assessment expectations.

The separate 2026-10-20 preparation probe03 prepared all 114 raw inputs under
unchanged read-only producer files, fresh retained state/cache and pre/post raw
hashes. Its [four selected-instruction facts](../../tests/input/fixtures/i5c/producer-selection-facts.json)
correct receipt absence for operand-size, vector, repeat and lock. In the last
two cases the selected instructions are one-byte prefix records, distinct from
the complete captured MOV sequence. Their conclusions and all 140 independent
arithmetic expectations are unchanged. Excluded-shape offset worksheets are
calculated diagnostics, not observed or admitted linear addresses; they do not
supply an absent FS base or the arithmetic of an isolated prefix. This producer
probe ran no core analysis or I5c assessment and is separate from the model gate.

The formal representation keeps four 16-bit limbs for every 64-bit base and EA,
and sign-extends a two-limb displacement. If c is the unsigned carry, q is
`c-negative(D)`, so signed-negative ordinary offsets do not become wraps.
`(q,EA)` denotes the exact wide T; access-end overflow, H=2^47 and reported-byte
membership are calculated from the whole word. Fifty-two finite scenarios run
under six TLC configurations after one Apalache typecheck. BAP/decoded
admission, context normalization and raw parsing are supplied premises; this
question model supplies no ISA/history proof or runtime refinement result.
The sequence constructor uses an unbounded natural-number recurrence, with
88 finite equivalence controls at lengths 0..42 and 64. No Apalache bounded-SMT
claim is made; typechecking and TLC remain the declared formal tier.

The byte-preservation matrix is 666 outputs: all 41 I5a fixtures times two
backends/three formats (246), all 57 I5b fixtures similarly (342), its
upstream-call auxiliary (six), and four established base/explanation workloads
times Rust/default/explicit-native and all formats (72). Freeze the actual
pre-W1 bytes once. Any necessary native build-receipt replacement is separately
validated and labeled; never normalize substantive fields or refresh the
baseline after extraction. Older controls, fixture bytes and source-bound
contracts remain unchanged.

### W0 result and publication contract

For an admitted full context, E=13+P+R evidence atoms and O=10+P+R observed
claims, with P≤15 exception parameters and R≤18 registers. Five arithmetic
claims plus one assessment give maximum 46/49; ordinary P=2/R=18 needs 33/36.
P>15 is a malformed binding/reader case, independently of output limits.
Defaults stay 64/64; I5a/I5b defaults and schemas do not change.

Preserve instruction, reader-ordered fault atoms and decoded receipt-last
evidence order. Any omitted evidence yields incomplete/Unknown/truncated and
removes arithmetic. The derived decoded-base, captured-base, wide-sum,
wrap-kind and computed-EA claims form one atomic bundle. If the full claim
bundle does not fit, retain only a bounded observed prefix and an Unknown
assessment when a slot remains. No partial arithmetic bundle is published.

The new schema uses one optional arithmetic object containing base register,
base value, signed displacement, displacement bit pattern, canonical decimal
T, wrap kind and EA. q is determined by wrap kind, not another independent wire
field. The complete input-evidence count and retained prefix are explicit.
Malformed identities/receipts are checked before zero budgets. Strict decoding
recomputes arithmetic/readiness/conclusion, canonical spellings, ordered claims,
source/scope/content digests and reference closure. Every renderer validates;
Unknown text precedes any conditional arithmetic, and DOT retains full JSON.

Bindings retain the existing snapshot/query/receipt contract. Scope IDs use the
ordered identity/question/schema/profile/context-digest/receipt-digest tuple;
evidence and claim domains are `i5c-evidence` and `i5c-claim`. The new content ID
hashes the typed compact result with that content-ID field empty. Complete
source digests recompute; incomplete source bindings cannot justify arithmetic.

The four new owned ASM recipes are upper wrap (RCX=M−8,disp16), no wrap
(RCX8,disp0), signed-negative no wrap (RCX16,disp−8) and indexed exclusion
(RCX=M−8,RDX0,disp16). Every recipe is separately captured in partial/full mode,
with uploads disabled and exact native-build/context/bytes/PE observations.
Existing remote WSL access does not prove native Windows SDK/CIPD/llvm-ml
availability; record a fresh read-only preflight before W4. Old I5b captures
remain regressions rather than new I5c acceptance.

Keep later actual-contract corrections and dated validation summaries in this
document, stage execution in the
[existing W0–W5 plan](../../.agents/plans/i5c-address-wrap.md), and raw
qualification evidence under `evidence/Ariadne/address-wrap/`. Full finite
acceptance still requires every original qualification clause above; no new
count, model check or presentation update waives broader unresolved boundaries.

## W0 qualification, 2026-10-20

The [sealed W0 evidence](../../evidence/Ariadne/address-wrap/20261020/w0/README.md)
qualifies 140 independent decision rows, 52 model scenarios, one Apalache 0.58
typecheck and six TLC configurations using the pinned 1.8.0 distribution. Twelve
oracle controls, 88 sequence controls and all 114 synthetic raw inputs pass.
The exact 23 normal source files and 115 raw files are promoted from the
qualified export; no local model/build or raw generation was used. The model
uses full-width limbs and signed-displacement carry correction; no Apalache
bounded-SMT, ISA proof or runtime refinement claim is made.

The separate producer03 review records all 114 preparation shapes: 86 ready and
28 negative/incomplete, 110 receipts and four legitimate receipt absences. The
operand-size/vector/repeat/lock corrections change only preparation input facts
and evidence counts; all independent arithmetic/conclusion expectations remain
unchanged. Earlier failed model/probe/packaging attempts are retained without
credit. All 100 generated producer state logs are retained separately from the
159 immutable runtime files.

Archive SHA-256 is
`5e7b164af51caecc322400f9bcb1425c0ed5bf895087569d56d973685ed701c7`;
all 2,207 members and the publication sidecars are verified. Compiled tools,
dependencies and the pinned static runtime remain in byte-verified remote
retention, with identities in the evidence record. The 666 legacy outputs in
that W0 record remain the BEFORE baseline. The separate W1 record below binds
the later AFTER comparison; W0 itself grants no W1–W5 runtime acceptance.

## W1 qualification, 2026-10-20

The [sealed W1 evidence](../../evidence/Ariadne/address-wrap/20261020/w1/README.md)
qualifies the immutable preparation seal, exact address-wrap binding and private
scalar admission extraction against one retained 1,213-file source snapshot.
All 10 binding tests and 4 existing I5b tests pass; 3 native I5b tests remain
ignored. The scoped formatting check also passes. The source and dependency/tool
inventories stayed stable during the executed tests.

A fresh release build selected its Ariadne and serde_json libraries and CLI
from actual Cargo metadata and compiler-artifact output. The unchanged driver
made 210 analysis runs: all 594 legacy assessment files and 72 base/explanation
files are byte-identical to the sealed BEFORE baseline. All 36 independent CLI
comparisons also pass. The collector retains 251 command receipts and separate
stdout/stderr streams, exact source/artifact identities and actual process-group
absence checks. No normalization or native-receipt replacement was needed.

The first AFTER preflight confused the test-report digest with the launch digest
and stopped before output creation or build/collection. Its controllers and the
explicit correction remain in the archive without credit; no absent raw failure
log is fabricated. The passing launch and report have distinct pinned identities.

Qualified source, all 184 release dependency files, selected compiled artifacts,
native inputs and tool files are retained independently before later changes.
Archive and export verification use those copies and closed evidence after the
retention checkpoint. The full source snapshot, raw tests, AFTER products and
BEFORE archive are included in the transport evidence; compiled payloads and the
static BAP runtime stay in byte-verified remote retention. Later W2 edits do not
change the identity of this W1 qualification.

This closes only W1. I5c arithmetic, reports/CLI, source-fixture, controlled-Windows,
fixed-budget performance, all-features Clippy and full-I5c acceptance are separate
unresolved gates. The ignored native tests are not counted as exercised.

## Design verification on 2026-10-07

A standalone mathematical check verifies all six example rows, including the
signed-negative false-carry controls and the inherited excluded-span policy.
A direct pinned LLVM MC 20.1.2 checked-protocol probe decodes the four proposed
controlled recipes in the plan as MOV32mi with the expected RCX base, absent or
RDX index, and signed displacement 16, 0, -8 or 16. These are design arithmetic
and decode-reference checks; they exercise no BAP address-wrap assessor,
Windows capture, question-level model or new performance workload. At that
date W0–W5 remained pending; the later W0 record has its own exact scope.

## W2 qualification and W3 follow-up, 2026-10-21

The [W2 record](../../evidence/Ariadne/address-wrap/20261020/w2/README.md)
qualifies exact wide arithmetic, conditional-versus-final conclusions and atomic
budgets through the public owned binding on its recorded 1,214-file snapshot.
Five ordinary pilot tests and one explicitly exercised native test pass. The
native test freshly prepares and completes seven synthetic captures, checks four
budget variants, and rejects invalid accesses at full and zero output limits.
Formatting, default tests, core-only tests and all-features/all-targets Clippy
also pass on remote WSL. Root-check receipts and all source/tool/native/runtime
postchecks pass. No local Cargo or native analysis ran.

The source delta and predecessor W1 source reconstruct the exact qualified
snapshot. The local W2 record retains receipts/controllers; raw logs remain
remote and must join W5's sealed runtime campaign. An owned-path test API error
and a singular/plural receipt-parser error are preserved without whole-campaign
credit; the final continuation validates the actual passing pilot logs before
running the remaining root checks. These corrections do not change arithmetic.

W3 adds strict encoding/decoding and text/JSON/DOT rendering, with an internal
shared fixture helper and 24 named serialized-negative controls. Its full
140-case matrix and report qualification remain pending. The later helper
refactor preserves every W2 test body; its new source hashes require their own
checks. W2 supplies no W3–W5, owned-Windows-capture, timing or full-I5c acceptance.

## W3 qualification and W4 follow-up, 2026-10-21

The [dated W3 record](../../evidence/Ariadne/address-wrap/20261021/w3/README.md)
passes all 140 frozen decisions (114 supplied-preparation raw captures and 26
separately named typed unit cases), 44 pre-budget binding controls and all 24
strict serialized controls. Eight representative results roundtrip through
JSON and complete DOT metadata; Unknown and every gap/requirement precede
conditional arithmetic in text. The explicit native gate freshly prepares and
completes all 114 raw cases with pinned decoded facts, BAP and the native core.
None of the 26 unit cases receives raw/native credit.

All ordinary matrix/pilot/report targets, formatting, default/core-only tests
and all-features/all-targets Clippy pass remotely. Source/tool/dependency/native
and immutable-runtime rechecks pass on the exact 1,252-file snapshot. The first
package's omitted untracked files were detected by the declared-count gate and
remain uncredited; the corrected package checks explicit source closure and
actual named 140/44/114 output rows. Full runtime-log sealing remains a W5 gate.

W4 sources now add the explicit CLI selector, transactional report bundle, four
native assembly recipes, new-only witnesses and an independent raw/PE inspector.
Review corrected its post-commit cleanup status before adoption. Native build,
all twelve CLI controls and eight newly owned partial/full captures are still
pending; source review and tiny Python controls do not satisfy them. W5 timing,
compiled mutations, replay, legacy/I4/I5a/I5b refresh and full evidence closure
also remain pending. W3 grants none of those later acceptance flags.

## W4/W5 execution preparation, 2026-10-21

The [W4/W5 stage ledger](../../.agents/plans/i5c-address-wrap.md#w4w5-execution-preparation-2026-10-21)
now has source-prepared execution tooling. Its [preparation evidence](../../evidence/Ariadne/address-wrap/20261021/w4-w5-preparation/README.md)
distinguishes fresh Python/source checks from unavailable native qualification.
No W4 exit, compiled mutation, new capture, timing, replay or full-I5c acceptance
is granted by this preparation. The two new ignored Rust mutation observers
also require compilation and execution in the qualified environment.

| Source | Responsibility |
| --- | --- |
| [Qualification primitives](../../tools/i5c_qualification.py) | Broad source inventory, selected tool identities, explicit prerequisite failures, verbatim command streams and exact Cargo artifact/test admission. |
| [W4 CLI runner](../../tools/check_i5c_cli.py) | Run all twelve named controls, including a hash-pinned Cargo-selected CLI unit executable and retained native failure artifacts. |
| [Windows capture batch](../../native/crashpad-demo/capture_i5c_windows.py) | Produce eight new recipe/mode captures and run the independent inspector; keep incomplete bundles failed. |
| [Mutation runner](../../tools/check_i5c_mutations.py) | All 24 frozen source transformations, selected original oracle cases, passing controls, isolated builds and actual compiled test failures. Anchor checking alone grants no mutation credit. |
| [Legacy comparator](../../tools/compare_i5c_legacy.py) | Compare all 666 named outputs to the exact pre-W1 baseline; refuse a caller-supplied replacement pin. |
| [Retained runtime exporter](../../tools/export_i5c_runtime.py) | Copy W2/W3 streams selected by original receipt paths, sizes and hashes, without executing historical controllers. |
| [Aggregate runner](../../tools/check_i5c.py) | Coordinate required root/model/native/mutation/legacy/I4/I5a/I5b/timing gates and publish positive flags only after verified evidence sealing. |

The legacy comparator consumes the original `ariadne.i5c-legacy-before/v1`
baseline, SHA-256
`e1adb5a375f67398ddbd4fb17189729aee40a13e049ae52b50a154d0c758e002`.
Its enclosing W1 archive SHA is
`bdc1289ad7fa7be9515127bfa891d0b85e1b7cce7966ff813f55097bee2f800e`.
Fresh stream verification checks all 2,713 outer members and all 666 retained
output payloads (34,365,159 bytes), plus the 36 retained CLI parity rows. This
verifies historical bytes; comparison against newly produced outputs remains
unexercised. The original archive and qualification records are unchanged.

Start with a read-only preflight on the qualification host:

```sh
python3 tools/check_i5c.py \
  --output target/i5c-qualification/NEW_PREFLIGHT --preflight-only
```

A successful preflight grants no acceptance flag. The full runner additionally
requires `--captures`, `--build`, `--expected-build-sha256`, the original
`--legacy-baseline` and `--expected-legacy-baseline-sha256`, retained
`--i5a-captures` and `--i5b-captures`, `--i4-profiles-root`, and a verified
`--runtime-index` / `--expected-runtime-index-sha256` pair. Execute through the
[sealed read-only MirrorRust view](../../tools/with_mirrorrust_snapshot.py).

Export old runtime evidence from the host directory previously mounted as
`/campaign`, using a new output directory:

```sh
python3 tools/export_i5c_runtime.py \
  --campaign-root RETAINED_CAMPAIGN_ARTIFACTS \
  --output target/i5c-qualification/NEW_RUNTIME_EXPORT
```

The exporter prints the index path and digest. The index must contain exactly
W2 and W3, each with its original qualification hash and complete exported
pathname/size/hash table. Every stdout/stderr stream referenced by the original
qualified receipts must remain present at its `campaign/...` path. Published
named-case records must also match. An internally consistent reduced export
cannot replace those original stream requirements.

Source review also found stale I5b mutation anchors after W1 moved shared
admission into `scalar_base_displacement.rs`. The corresponding three mutation
definitions now target that owner; all fifteen source seams are checked, but
their fresh compiled campaign remains pending. Historical I5b results retain
their source identities.

The current checkout lacks the native helpers/SDK/runtime and active dependency
snapshot; ordinary offline Cargo checks also stop at the uncached `minidump`
package. Eight required source/evidence inputs remain LFS pointers in the
working tree. Verified I5c metadata and the W1 archive were fetched into the LFS
object cache without replacing historical tracked evidence. The retained
controllers identify host paths below `/home/jlc/ariadne-target-r6-20261020`
and its `artifacts/` directory; no accessible qualification host is established
by those historical paths. Heavy native/model/campaign execution remains remote.
