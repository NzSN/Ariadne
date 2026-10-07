# I5c address-wrap implementation plan

## Context and follow-up

**Status.** W0–W5 plan written on 2026-10-07 against `1344c99`. The selected
design is delivered as documentation; all implementation, model, capture,
measurement and acceptance stages remain pending.

**Why this document exists.** The [selected design](../docs/Ariadne/i5c-address-wrap-design.md)
defines a distinct fault-time address-wrap question. Existing I5a/I5b calculate
modular EA but do not report its signed-displacement sum before reduction as a
separate assessment. A staged plan must preserve their existing contracts.

**What this document establishes.** Exact stage ownership, independent oracles,
admission and serialization controls, product integration, historical-byte
preservation and separately gated source/fixture and controlled Windows tiers.

**Where to go next.**

- [Design and predicate](../docs/Ariadne/i5c-address-wrap-design.md#exact-selected-question)
  — unsigned B, signed encoded D, exact T and inherited range limit.
- [Source-origin table](../docs/Ariadne/i5c-address-wrap-design.md#source-grounded-reuse-and-new-work)
  — existing binding/admission/receipt code and the specific new calculation.
- [I5b contracts](../docs/Ariadne/i5b-contracts.md) and
  [source review](../docs/Ariadne/i5b-source-review.md) — reusable finite forms
  and decoded/BAP agreement with source-bound old outputs.
- [Investigation ledger](investigation-layer.md) — selected I5c and the other
  history, canonicality, lifetime and cross-capture questions still deferred.
- [Formal-model guide](../Specs/README.md) and
  [snapshot runner](../tools/with_mirrorrust_snapshot.py) — modeled authority
  and qualification through a sealed read-only dependency view.

**What remains unresolved.** Nothing in W0–W5 is implemented or accepted yet.
The v1 assessment qualifies upper wraps and no-wrap cases only within the
inherited lower-range access profile. Mathematical underflow stays unknown for
fault assessment. General canonicality, indexed/32-bit/Linux admission, earlier
executed arithmetic and lifetime remain separate work. Existing qualified
I4/I5a/I5b records cannot supply new I5c acceptance.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Frozen delivery intent

Ask whether the selected instruction's `T = unsigned(B) + signed(D)` leaves
`[0, 2^64-1]` before reduction. This is different from unsigned addition of D's
bit pattern, arithmetic in earlier instructions, access-span wrapping or an
inferred root cause. W0 must preserve that definition in the model and oracle.

Reuse the six reviewed Windows AMD64 scalar MOV base/displacement forms,
reader-owned fault context, decoded receipt and completed analysis. Keep the
existing nonwrapping lower-range span and reported-byte/operation association.
No new root, solver run, LLVM effect fallback, native action or old schema field.
New implementation/examples live under `src/`; standalone tests/fixtures under
`tests/`; one root Cargo manifest/lock/target. Replay and mutation builds use
separate named target subdirectories.

## Stages, ownership and exits

The file names below are proposed new outputs, not links to files that exist.
Implement stages sequentially; a partial matrix or partial tier remains partial.

| Stage | Owned sources and outputs | Exit |
| --- | --- | --- |
| W0 — Contract, source review and independent oracle | New `docs/Ariadne/i5c-source-review.md`; `Specs/AriadneAddressWrap.tla`, `AddressWrap.cfg`, `check-address-wrap.sh`; `tests/input/fixtures/make_i5c.py` and new `i5c/` fixture/contract files | Exact signed-displacement arithmetic, readiness/range/budget decision model and complete independent case inventory frozen; model checks and oracle calculations agree before runtime code. |
| W1 — Bind and share finite admission facts | `src/input/investigation.rs`; new private `src/investigation/scalar_base_displacement.rs`; narrow use from `zero_base_offset.rs`; new bound type in `address_wrap.rs`; exports | Sealed selected-site receipt/context binding; shared existing decoded/BAP facts with old I5a/I5b results and bytes unchanged. |
| W2 — First vertical slice | `src/investigation/address_wrap.rs`; root Cargo test target; new investigation/input tests | MOV32mi upper-wrap, no-wrap, signed-negative no-wrap, unknown/error and tiny-budget cases pass through the same bound assessment interface as callers. |
| W3 — Complete finite matrix and serialization | Assessor, new `src/reports/address_wrap.rs`, report exports, dedicated tests and new actual contracts document | All six forms, boundary/negative controls and strict recomputation pass; conditional arithmetic versus unknown fault assessment is unambiguous in text/JSON/DOT. |
| W4 — Product and controlled capture recipes | `src/bin/ariadne-minidump.rs`; native demo profile dispatch/witness/build/capture/inspector additions; new assembly file and input/native CLI tests | Explicit modes, seed/root behavior, atomic publication and eight independently inspected owned partial/full captures. No old profile/capture bytes rewritten. |
| W5 — Qualification and durable evidence | New `tools/check_i5c.py`, contract/equivalence/mutation/measurement tools, `src/bin/i5c.rs`; root manifest; new evidence/validation guide and status updates | Separate source/fixture, controlled partial/full and fixed-budget flags pass under stable source/tool/dependency inventories; full evidence archive verifies. |

## W0 — Freeze semantics and independent expectations

Read the [I5b source review](../docs/Ariadne/i5b-source-review.md),
[receipt implementation](../src/llvm_mc/address_reference.rs),
[I5a decision](../src/investigation/zero_address.rs) and
[fault-field validation](../src/investigation/fault_context.rs).
Verify no-displacement and signed disp8/disp32 for every reviewed form and the
physical base/access tuple. LLVM remains a decoded-fact reference; BAP remains
the instruction-semantic producer.

The independent fixture manifest must retain exact bytes/site/opcode, encoded
base/index/scale/displacement and width, register/context fields and validity,
mathematical T, q, modular EA, reported inaccessible byte, operation/span,
expected arithmetic facts, gaps and final conclusion. Compute expectations with
Python mathematical integers and explicit hand-reviewed encodings, without
calling the SUT evaluator or using BAP/LLVM agreement as the oracle. Annotate
malformed/tampered cases separately from legitimate unsupported inputs.

Create a question-level TLA+ model over representative **64-bit** boundary
bases, signed displacement extremes, access widths, readiness/coherence and
budget flags. Admission must calculate its actual lower-range/span condition;
it cannot be an arbitrary boolean that accidentally admits negative underflow.
Check at least these invariants:

1. `EA = T - q*2^64`, `0 <= EA < 2^64`, and q is exactly -1/0/1 by T's range.
2. A definite conclusion requires complete coherent instruction/context/receipt,
   admitted span/reported-byte association and retained mandatory evidence/claims.
3. Consistency implies wrap; refutation implies no wrap under all premises.
4. Negative underflow and excluded/wrapping spans produce unknown in v1.
5. Missing/coherence failures never imply refutation; budget omission implies
   unknown/truncation and removes unsupported dependent arithmetic facts.
6. Ordinary signed-negative offsets do not become wraps from displacement-bit
   unsigned carry; store payload changes do not change the predicate.

The model owns the question decision contract, not ISA instruction steps,
history or native-core transitions. Rust conformance against its representative
cases is separate evidence. Keep full-width arithmetic extremes in independent
fixture tests even if the finite model uses fewer representative displacements.
Resolve any discrepancy against the modeled contract before accepting runtime
code. The retired independent ISA/Lean track receives no new milestones.

Freeze proposed 64/64 evidence/claim defaults after counting the full bundle,
including arithmetic and decision claims. Freeze 10 ms combined phases / 1,500 ms
CLI, one warm-up/five measured repeats for declared I5c workloads. Existing
I4/I5a/I5b contracts/manifests and source-bound Stage 2 design/plan bytes remain
unchanged. Record W0 results and their exact source/tool/dependency identities.

## W1 — Exact binding and private admission reuse

`bind_address_wrap(prepared, completed, question)` reuses `bind_fault_context`,
then checks the receipt against retained preparation bytes, length, opcode/raw
row and selected access. Bind snapshot/artifact/query/request/semantic-profile,
question/context/receipt/profile digests. Preserve missing receipt as unknown;
reject substitutions/tampering, invalid sites/indexes and mutable public metadata
changes. No arbitrary public-evidence constructor and no new decoder call.

Extract only the shared decoded one-base/no-index/width/constant agreement facts
from the existing I5b implementation into the private module. Keep common fault
admission in the existing I5a `decide` path. The new arithmetic module uses its
computed EA and late range/reported-byte gaps; check separately that the wide
sum reduces to that EA. Structural receipt/BAP disagreement removes arithmetic
readiness, even if a convenient captured register happens to suggest a result.

Preserve I5b's current suppression of base/displacement fields when any gap
remains. Do not change its gap strings/order, serialized evidence tags, IDs or
conclusions through the shared module. Freeze and compare legacy output bytes
before and after this extraction, including I5b unknowns and I5a outputs.
If factoring causes a difference, repair the extraction before W2 rather than
regenerating the baseline to hide it.

## W2 — Pilot calculation and bounded output

The module takes the proposed sealed `BoundAddressWrapContext` and
`AddressWrapLimits`, returning owned `AddressWrapAssessment`. Default limits
are 64/64 only after W0 accounting. Runtime arithmetic uses exact wide signed
T from distinct conversions of B and D, classifies q, calculates EA and checks
agreement with the admitted BAP modular expression. Casts/saturating arithmetic,
signed reinterpretation of B and unsigned-carry tests are not the predicate.

Construct conditional arithmetic facts when their own valid input evidence is
retained. A late range or reported-byte gap keeps the final assessment unknown;
text must explain that gap before displaying any upper/lower arithmetic fact.
Missing base validity, shape/receipt/BAP disagreement or prerequisite record
omission removes the arithmetic facts themselves. Refutation needs the same
complete admission as consistency.

Process malformed identities/sites before applying output budgets. Zero/tiny/
exact-fit limits must produce valid unknown/truncated results or the appropriate
binding error, without dangling references or leaked definite conclusions.
Test through the public binding/assessment interface, with native preparation
and a completed native analyzer in the integration pilot.

## W3 — Mandatory oracle and negative-control matrix

Each of the six forms needs an upper-wrap-to-lower-range case, an ordinary
no-wrap case and a zero-displacement case. Full source/fixture acceptance needs
all forms, plus every category below; W0 records the final case count.

| Category | Required observation/outcome |
| --- | --- |
| Exact upper boundary | T = 2^64, EA = 0: consistent; captured base is nonzero. |
| Beyond upper boundary | B = 2^64-8, D = 16, EA = 8: consistent, q = 1. |
| Signed-negative ordinary offsets | B = 8, D = -8 gives zero, and B = 16, D = -8 gives eight: refuted, q = 0 despite unsigned carry from D's bits. |
| Mathematical underflow | B = 0, D = -8: final unknown with range gap; conditional T = -8/q = -1 survives only with its complete arithmetic evidence. |
| Displacement extremes | Signed disp8 -128/127 and disp32 -2^31/(2^31-1): exact sign and classification independent of the SUT. |
| Range/span boundaries | Exclusive end exactly H can admit; end above H or u64 span wrap yields unknown. No wrap of B+D does not refute an unsupported access. |
| Reported byte/operation | Start and last in-span bytes admit; past-span/wrong-operation parameters yield unknown. |
| RSP/RBP/R12/R13 | Reviewed encodings and appropriate CONTROL/INTEGER validity; missing required group yields unknown. |
| Shape/prefix exclusions | Indexed, index-only, absolute, RIP, segments, address-size, repeated/locked/vector/multiple-access cases stay unknown, including zero-valued indexes. |
| Receipt/semantic checks | Missing receipt or legitimate decoded/BAP disagreement yields unknown; substituted identity/raw row/encoding/claims fail validation. |
| Fault-context checks | Missing/invalid context, wrong site/RIP/exception kind/operation, execute/chained/unsupported records and thread-list fallback stay unknown. |
| Payload and history independence | Changing store payload or adding an opaque predecessor call does not invent arithmetic inputs or an executed producer. |
| Budgets and strict result | Zero/tiny/exact-fit limits, duplicate/unknown fields, wide-value spelling/bounds, wrong q/EA, altered digests and dangling claims are controlled. |

New schema `ariadne.address-wrap-assessment/v1` must recompute T/q/EA, readiness,
conclusion, content/scope IDs and reference closure from retained inputs. The
wide sum uses canonical signed decimal text, not a VA/u64/float. Define missing
arithmetic data explicitly; never serialize absent facts as zero/no-wrap.
Renderers share the same typed result, with full JSON preserved in DOT metadata.

## W4 — Product and real controlled Windows evidence

Add only the proposed `--assess-address-wrap VA --memory-access N` question.
Support existing assessment-only format selection and new transactional
`address-wrap-assessment.{txt,json,dot}` bundles. Reject combinations with another
assessment, explanation or supplied stateflow question. Requested site adds a
slice seed only. Test unavailable/unreachable sites, bad indices, mutually
exclusive flags and render/infrastructure failures before publication.

Build new owned native Windows recipes with uploads disabled and the minimal
child environment policy. Use caller-supplied RCX with the selected assembly
access as the independently identified entry/fault site; do not infer these
facts from intended source. Verify actual disassembly/bytes after compilation.

| Recipe | Controlled operands and candidate exact bytes | Required final answer |
| --- | --- | --- |
| Upper wrap | RCX = `0xfffffffffffffff8`; `c7411005000000` (`mov dword ptr [rcx+16],5`); EA = 8 | Consistent. |
| No wrap | RCX = 8; `c70105000000` (`mov dword ptr [rcx],5`); EA = 8 | Refuted. |
| Signed-negative no wrap | RCX = 16; `c741f805000000` (`mov dword ptr [rcx-8],5`); EA = 8 | Refuted, despite the displacement-bit unsigned carry. |
| Unsupported indexed | RCX = `0xfffffffffffffff8`, RDX = 0; `c744111005000000` (`mov dword ptr [rcx+rdx+16],5`); EA = 8 | Unknown; a zero index does not admit the excluded shape. |

The byte recipes are independently specified candidates, not evidence that a
capture has occurred. W4 produces partial and full modes for all four recipes:
**eight distinct capture cases**. Preserve old I5a/I5b sources/build/capture
records and pins as historical before producing new builds. Freeze the new
artifact/dump/witness/build identities and exact question per case.

The independent raw minidump/PE inspector must not invoke Ariadne, LLVM or BAP.
Check captured instruction bytes/length/roles, valid RCX/RDX/RIP observations,
AV operation and inaccessible byte, memory stream/mode, process/module/build
matching, code-range capture and independently calculated T/q/EA. Witness intent
alone cannot establish observed operands. PE remains comparison evidence and
must never supply production fallback bytes. No crash or upload is generated
by this documentation delivery.

## W5 — Qualification, mutation sensitivity and evidence

Run affected unit/native tests and all applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Run explicitly ignored native cases with the freshly built pinned helper path.
Run the new question model, analysis-model/native replay and relevant
input/BAP/Stage E/investigation regressions. Use a sealed read-only MirrorRust
snapshot and distinct replay/mutation target directories. No source/tool/fixture
inventory may be silently narrowed to reuse an old result after changed files.

Real-code mutants must exercise, at minimum: interpreting B as signed;
interpreting D as unsigned; using unsigned carry; ignoring negative D; wrong
`>=` upper-bound comparison; calculating T after u64 reduction; omitting range
or reported-byte checks; dropping receipt/BAP or context-validity checks;
refuting missing/unsupported evidence; retaining unsupported arithmetic after
budget omission; changing a decision/rendered field without strict recomputation;
and turning the question seed into a root. Reuse unchanged independent observers.
Compile errors, unsupported transformations, timeouts or missing helpers are
not detected mutants. Freeze the exact mutant list/count before campaign credit.

Capture byte-exact legacy base/explanation/I5a/I5b outputs before W1, including
unknown/range/index cases. Preserve their bytes and independently validate any
necessary native build-receipt change without discarding substantive claims.
Keep the old source-bound Stage 2 design/plan and historical evidence unchanged.
Refresh current I5a/I5b finite and controlled tiers after shared source changes;
recheck independent I4 2,000 ms Windows / 250 ms Linux criteria on its exact pin.
New I5c timing is not a substitute for those gates.

The new native phase benchmark must bind a completed native analysis, then time
only binding + assessment + all-format rendering, with exact snapshot/query/
helper/profile identities. The normal release CLI separately measures each
frozen fixture/controlled workload after warm-up. Use one warm-up/five measured
repeats and enforce the W0-frozen 10 ms phase / 1,500 ms CLI ceilings.
Measure the eight owned controlled cases separately; fixture success cannot
satisfy either partial or full controlled acceptance.

Publish distinct source/fixture, controlled-Windows-partial,
controlled-Windows-full and full-I5c flags. Each tier requires all its named
cases, raw samples, independent inspections and source/tool/dependency closure.
Unavailable, malformed, skipped, over-budget or stale evidence cannot qualify.
All synthetic underflow diagnostics remain outside the supported v1
fault-assessment tier, even if their arithmetic kernel/oracle is correct.

Retain source snapshots, formal/Rust/native outcomes, raw samples/reports,
mutant observations, rejected attempts, independent capture witnesses and a
complete verified archive. Use LFS for large artifacts. Verify every archive
member's size/hash, exact report/archive digest and tool/dependency identity;
a manifest flag alone is insufficient. Update the design's status, actual
contracts, qualification guide, plan ledger/checkpoints and direct successor
links only to the demonstrated scope. Packaged-release and universal-refinement
acceptance remain separate.
