# I5c address-wrap implementation plan

## Context and follow-up

**Status.** W0 is qualified on 2026-10-20 for the finite model/oracle and
synthetic-input scope in the [durable record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w0/README.md).
Its 23 normal source files were promoted byte-identically after one Apalache
typecheck and six TLC configurations. The separate [W1 record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w1/README.md)
qualifies 10 binding tests, 4 I5b tests, 666 unchanged legacy files and 36 CLI
comparisons; 3 native tests remain ignored in that W1 tier. The separate
[W2 pilot](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w2/README.md) passes the
public assessor, seven native synthetic cases and required Rust gates.
[W3 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/w3/README.md) passes
all 140 decisions, 44 binding controls, 24 serialized controls and 114 fresh
native cases. W4 sources are implemented with product/capture gates pending;
W5 and full acceptance remain pending.
The [W4/W5 execution preparation](../../docs/Ariadne/address-wrap-design.md#w4w5-execution-preparation-2026-10-21) adds
source tooling and retained-baseline verification without closing those gates.
No I5c assessor, capture, timing or full-feature acceptance is granted by W0/W1. The
[canonical design](../../docs/Ariadne/address-wrap-design.md#w0-finite-contract-2026-10-20)
owns the exact inventory, publication accounting and qualification boundaries.

**Why this document exists.** The [selected design](../../docs/Ariadne/address-wrap-design.md)
defines a distinct fault-time address-wrap question. Existing I5a/I5b calculate
modular EA but do not report its signed-displacement sum before reduction as a
separate assessment. A staged plan must preserve their existing contracts.

**What this document establishes.** Exact stage ownership, independent oracles,
admission and serialization controls, product integration, historical-byte
preservation and separately gated source/fixture and controlled Windows tiers.

**Where to go next.**

- [Design and predicate](../../docs/Ariadne/address-wrap-design.md#exact-selected-question)
  — unsigned B, signed encoded D, exact T and inherited range limit.
- [Source-origin table](../../docs/Ariadne/address-wrap-design.md#source-grounded-reuse-and-new-work)
  — existing binding/admission/receipt code and the specific new calculation.
- [I5b contracts](../../docs/Ariadne/zero-base-offset-design.md) and
  [source review](../../docs/Ariadne/zero-base-offset-design.md#decoded-record-and-independent-oracle) — reusable finite forms
  and decoded/BAP agreement with source-bound old outputs.
- [Investigation ledger](investigation-layer.md) — selected I5c and the other
  history, canonicality, lifetime and cross-capture questions still deferred.
- [Formal-model guide](../../Specs/README.md) and
  [snapshot runner](../../tools/with_mirrorrust_snapshot.py) — modeled authority
  and qualification through a sealed read-only dependency view.

**What remains unresolved.** W4 product/native-build/owned-capture gates and W5
full acceptance remain pending.
The v1 assessment profile covers upper wraps and no-wrap cases only within the
inherited lower-range access profile. Mathematical underflow stays unknown for
fault assessment. General canonicality, indexed/32-bit/Linux admission, earlier
executed arithmetic and lifetime remain separate work. Existing qualified
I4/I5a/I5b records cannot supply new I5c acceptance.

For the wider context, see the [documentation map](../../docs/documentation-map.md).

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

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

The table retains each stage's intended outputs; W0 sources and the W1 binding seam now exist.
Implement stages sequentially; a partial matrix or partial tier remains partial.

| Stage | Owned sources and outputs | Exit |
| --- | --- | --- |
| W0 — Contract, source review and independent oracle | Source-review findings and the [W0 finite contract](../../docs/Ariadne/address-wrap-design.md#w0-finite-contract-2026-10-20) in the existing canonical design; `Specs/AriadneAddressWrap.tla`, generated `AriadneAddressWrapCases.tla`, six `AddressWrap*.cfg` files and `check-address-wrap.sh`; `tests/input/fixtures/make_i5c.py` and new `i5c/` fixture/contract files | Exact signed-displacement arithmetic, readiness/range/budget decision model and complete independent case inventory frozen; model checks and oracle calculations agree before runtime code. |
| W1 — Bind and share finite admission facts | `src/input/investigation.rs`; new private `src/investigation/scalar_base_displacement.rs`; narrow use from `zero_base_offset.rs`; new bound type in `address_wrap.rs`; exports | Sealed selected-site receipt/context binding; shared existing decoded/BAP facts with old I5a/I5b results and bytes unchanged. |
| W2 — First vertical slice | `src/investigation/address_wrap.rs`; root Cargo test target; new investigation/input tests | MOV32mi upper-wrap, no-wrap, signed-negative no-wrap, unknown/error and tiny-budget cases pass through the same bound assessment interface as callers. |
| W3 — Complete finite matrix and serialization | Assessor, new `src/reports/address_wrap.rs`, report exports, dedicated tests and the [actual-contract section](../../docs/Ariadne/address-wrap-design.md#w0-result-and-publication-contract) of the existing canonical design | All six forms, boundary/negative controls and strict recomputation pass; conditional arithmetic versus unknown fault assessment is unambiguous in text/JSON/DOT. |
| W4 — Product and controlled capture recipes | `src/bin/ariadne-minidump.rs`; native demo profile dispatch/witness/build/capture/inspector additions; new assembly file and input/native CLI tests | Explicit modes, seed/root behavior, atomic publication and eight independently inspected owned partial/full captures. No old profile/capture bytes rewritten. |
| W5 — Executable qualification | `tools/check_i5c.py`, contract/equivalence/mutation/measurement tools, `src/bin/i5c.rs`; compact expected vectors under tests; transient run products under target; dated summaries in the canonical design | Separate source/fixture, controlled partial/full and fixed-budget tests pass on current sources/tools/dependencies. No archival or LFS-publication gate remains. |

## W0 — Freeze semantics and independent expectations

Read the [I5b source review](../../docs/Ariadne/zero-base-offset-design.md#decoded-record-and-independent-oracle),
[receipt implementation](../../src/llvm_mc/address_reference.rs),
[I5a decision](../../src/investigation/zero_address.rs) and
[fault-field validation](../../src/investigation/fault_context.rs).
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

### W0 frozen inventory and qualification, 2026-10-20

The canonical design owns source review, actual result contracts and later dated
qualification summaries. No separate `i5c-source-review.md` or second contracts
design is created. Preserve every acceptance clause above and in W1–W5.

Freeze 140 decision rows (114 synthetic captures and 26 bound-unit controls),
19 binding negatives at full and zero budgets (38 invocations), 24 strict-result
negatives, 12 CLI controls and 24 compiled behavioral mutants with passing
controls. Ten fixture timing workloads and eight newly owned partial/full
Windows captures remain distinct. The old-output gate has 666 outputs: 246 I5a,
342 I5b, six I5b upstream-call and 72 base/explanation outputs, including the
explicit Rust/native/default ownership choices. Preserve all rows, not just the
performance subset.

Materialize all 114 synthetic raw inputs under `tests/input/fixtures/i5c/dumps/`
and freeze their exact file inventory before W1. The normal W0 checker binds
every dump and its manifest before and after the model run. Review a separate
114-row current-product preparation probe before freezing receipt/admission
premises; its observations cannot replace independent arithmetic expectations.

The question-level model preserves exact 64-bit values as four 16-bit limbs;
signed-displacement carry correction yields q=-1/0/1 and the full lower-range
span/reported-byte predicate. One typecheck and six TLC configurations cover
52 scenarios. The natural-number sequence recurrence has uncapped controls at
length 64; this tier makes no Apalache bounded-SMT claim. Source admission, raw
parsing and ISA semantics remain explicit premises. The independent Python integer/encoding oracle and its 52-case model
projection crosscheck are separate evidence from runtime conformance.

The largest admitted source bundle is 46 evidence and 49 claims; ordinary
two-parameter full contexts require 33/36. Counts above 15 exception parameters
are binding errors before budgets, never clamped. Defaults remain 64/64. Five
arithmetic claims form one atomic bundle; an early gap or mandatory omission
removes it, while late range/reported-byte gaps retain conditional arithmetic
with an Unknown assessment. The design fixes exact field/claim ordering and
wide-decimal validation. The [2026-10-20 W0 record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w0/README.md)
qualifies the exact 140-row/52-scenario/114-raw-input tier, 12 oracle controls,
88 sequence controls, one typecheck and six TLC configurations. Failed model,
producer and packaging attempts remain uncredited. The 666-output pre-W1
baseline remains the W0 BEFORE evidence. The separate W1 record below qualifies
the later AFTER comparison; W2–W5 acceptance remains pending.

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

### W1 exit, 2026-10-20

The [W1 evidence record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w1/README.md)
and [canonical qualification summary](../../docs/Ariadne/address-wrap-design.md#w1-qualification-2026-10-20)
close this stage for the retained 1,213-file source snapshot. Ten binding tests
and four I5b tests pass; three native I5b tests remain ignored. A fresh release
build and unchanged batch driver produce all 666 legacy files byte-identically
and pass all 36 CLI comparisons. The record retains 251 command receipts,
actual Cargo artifact selection, raw streams and the uncredited initial pin
mixup/correction. Source and all 184 release dependencies are retained before
later changes; export verification uses retained copies rather than the live
ROOT/target. This exit grants no W2–W5 or full-I5c acceptance.

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

### W2 exit, 2026-10-21

The [dated pilot record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261020/w2/README.md)
passes five ordinary tests and one explicitly exercised native test on seven
freshly prepared/completed synthetic captures, including four native budget
controls. Formatting, default/core-only tests and all-features/all-targets Clippy
pass remotely with unchanged source/tool/dependency/native/runtime bindings.
Exact sum/reduction, early versus late gaps, tiny/exact budgets and binding
errors run through the public API. Earlier failed setup/test/collector attempts
remain recorded; the passing continuation verifies the original pilot logs.
W3's helper refactor preserves all six test bodies and gets a new source-bound
qualification. This exit grants no complete W3 matrix, owned capture or W5 gate.

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

### W3 exit, 2026-10-21

The [dated matrix/report record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/w3/README.md)
passes all 140 frozen decisions, 44 expanded binding invocations, 24 strict
serialized controls and fresh native preparation/completion for all 114 raw
cases. The 26 typed unit cases remain a separate scope. Matrix, pilot, reports,
formatting, default/core-only tests and all-features/all-targets Clippy pass on
the exact remote source/tool/dependency snapshot. The first incomplete source
package is uncredited; the corrected package verifies all named case records.
Fresh runtime validation remains with W5; persistent log sealing is retired. W4 source implementation follows;
its CLI, build and owned capture gates remain pending.

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

Run the required tests on the current source/tool/input identities. Keep their
logs, measurements and result summaries in ignored run directories. Under the
[test-only validation policy](../../tests/README.md), do not create a retained
archive, copy source trees into publication bundles or upload LFS evidence.
Missing native, capture or timing tests remain unmet gates. The current native
matrix replaces historical W2/W3 stream import, and the checked-in 666-output
size/digest vector replaces the old raw-output baseline.

## W4/W5 execution preparation, 2026-10-21

Execution resume: the [recovered-host record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/execution-resume/README.md)
verified the retained producer and captures; source transfer was then approved.
The [current campaign](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/w4-w5-execution/README.md)
reported root/model, native114 matrix, strict-report and CLI12 success. Ten of 24
compiled mutants were last confirmed detected. New owned I5c/I5b captures and a
new I5a null-write cohort passed raw inspection. The current I5a qualifier binds
the extended six-source producer while retaining its original historical contract.
SSH subsequently began closing before authentication. Resume by inspecting
`results/qualification-02` in the existing task, then retrieve and verify all
remaining gates. The later test-only policy retires archive sealing; aggregate W4/W5 acceptance stays pending.

The [canonical execution guide](../../docs/Ariadne/address-wrap-design.md#w4w5-execution-preparation-2026-10-21)
and [preparation evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/w4-w5-preparation/README.md)
record the new CLI-control runner, eight-case Windows capture wrapper, all-24
mutation driver with focused frozen-case observers, original-baseline comparator,
W2/W3 runtime exporter and aggregate qualification/sealing runner. These sources
initially had local Python/source checks only; the current execution above
supersedes that preparation limit for its reported completed gates.
Three stale I5b mutation definitions now follow their shared admission owner;
the fifteen source seams have checks but no fresh compiled campaign credit.

All 2,713 members of the original W1 archive and all 666 retained output payloads
(34,365,159 bytes) are freshly stream-verified. The original pre-W1 baseline SHA
`e1adb5a375f67398ddbd4fb17189729aee40a13e049ae52b50a154d0c758e002` and
36 retained public-API/CLI parity rows remain fixed. This does not compare current
outputs or refresh W1/W2/W3 acceptance. Historical payloads and stage exits stay
unchanged.

Next execution requires the retained remote Windows/WSL host. Recovered W3
controllers map `/campaign` to the host's
`/home/jlc/ariadne-target-r6-20261020/artifacts`; those paths are historical
evidence rather than present access. Use a new isolated task containing the
final source/tool inventory and the sealed read-only dependency view. Run the
W4 native build, twelve CLI controls and all eight independently inspected owned
captures before W5 qualification. Execute the current native matrix and supply
the checked-in legacy expectation vector, applicable I5a/I5b captures and I4
profile baseline to the aggregate runner. Historical runtime exports are retired.

That preparation-time local preflight recorded missing native dependencies and
uncached Cargo inputs. The later test-only migration supplies ordinary fixtures
and fresh local Rust checks; these historical blockers do not describe current
portable-test coverage. Full native/capture and timing prerequisites remain
explicit and are not waived by portable tests.
No local native/model run, new capture, compiled mutation, replay or timing
acceptance is credited. W4, W5 and full-I5c acceptance remain pending.
