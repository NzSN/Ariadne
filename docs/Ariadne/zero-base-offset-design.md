# Zero-base-plus-displacement assessment design

## Context and follow-up

**Status.** Implemented and qualified within the recorded finite source/fixture
and controlled partial/full Windows corpora on 2026-10-07. The design baseline
`ae987bc` is historical. See the qualification for
the 18 gates, exact source/tool inventory and separate controlled Windows tiers.

**Why this document exists.** The [investigation design](investigation-design.md)
motivates separate fault-time questions. [Zero-address assessment](zero-address-design.md)
can refute zero-start for `[RAX + 8]` with captured RAX zero, while leaving the
distinct zero-base question unanswered.

**What this document establishes.** One fault-time predicate, a finite scalar-MOV
admission profile, the additional decoded-role evidence needed, a small assessment
interface, and separate acceptance tiers. The claim concerns an observed register
value at the selected instruction, not historical null provenance.

**Where to go next.**

- [I5b implementation plan](../../Plans/i5b-zero-base-offset.md) — B0–B5 source
  ownership, fixtures, reports, mutation and controlled-capture qualification.
- [Investigation stage ledger](../../Plans/investigation-layer.md) — delivered numeric
  questions, selected address-wrap work and the other deferred hypotheses.
- [Existing fault-context contract](zero-address-design.md) — the capture/context
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

## Historical baseline and decoded-evidence seam

The design baseline established the following reusable facts and missing seam.
The implemented receipt and sealed binding described below close that seam;
statements about missing roles in this table refer to the historical baseline:

| Inspected source | Consequence for I5b |
| --- | --- |
| [AddressExpression](../../src/effects/address.rs) and [BIL extraction](../../src/bap/address.rs) retain canonical affine terms and a constant. | They support arithmetic, but erase encoded base/index roles and can merge or cancel terms. A coefficient-one term alone does not establish an encoded base. |
| [InstructionEvidence](../../src/effects.rs) retains decoded operands and the raw LLVM record. | This is an existing decoded-fact seam; LLVM remains a reference rather than an effect provider. |
| [Decoded operand projection](../../src/llvm_mc/reference.rs) then created a typed Memory operand only for the two immediate-store MOV forms. | The other four candidate forms need reviewed row-layout projection before their decoded base role can be admitted. |
| [SiteEvidence](../../src/investigation/model.rs) and [capture binding](../../src/input/investigation.rs) omit decoded operand roles from the strict question evidence. | Existing BoundFaultContext alone cannot support the new encoded-base assertion. The new binding adds question-specific evidence, without extending the old v1 schemas. |
| [Fault context](../../src/investigation/fault_context.rs) and [I5a assessment](../../src/investigation/zero_address.rs) validate immutable observations and bounded arithmetic. | Reuse context acquisition and admission premises; preserve every existing I5a decision and serialization behavior. |

The implementation retains a decoded-address receipt during existing
preparation. It binds the exact VA, consumed bytes, length, opcode,
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

The selected question is bound once, preventing evidence for one access from
being assessed as another. Store payloads never enter the address predicate.
The assessment consumes one completed normalized analysis and returns a typed
answer; capture, semantic preparation and formatting keep their existing owners.

## First admission profile

Implemented profile: `windows-amd64-av-scalar-mov-base-displacement-v1`.

Reuse the [I5a context checks](zero-address-design.md#evidence-and-admission): immutable
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
   Reviewed SIB encodings with a real GPR base and no index are admitted;
   their mere use of SIB does not establish an index. RSP/RBP/R12/R13 addressing
   special cases require explicit fixtures and the appropriate context groups.
   RSP requires CONTROL validity; other base GPRs require INTEGER validity.
3. The decoded tuple agrees with the BAP expression and the selected access.
   Store payload values never enter the address predicate.
4. Compute EA modulo 2^64, then apply the existing nonwrapping access-span
   condition wholly below `0x0000800000000000`. This intentionally narrow range
   is an admission condition, not a general noncanonical-address classifier.
   A zero base with a negative displacement outside that range returns unknown.
5. Every required evidence item and decision claim survives the selected budgets.

The implemented finite matrix covers reviewed `MOV32mi`, `MOV64mi32`,
`MOV32rm`, `MOV64rm`, `MOV32mr` and `MOV64mr` base/displacement cases; opcode names alone do not grant coverage. Unsupported
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

The full context already consumes the older 32/32 budget; the separate 64/64
defaults leave room for the decoded receipt and decision claims. A definite
conclusion requires every mandatory record and claim. All formats expose the
same conclusion and gaps; preserved base reports and older v1 schemas keep their
existing meanings.

## CLI and publication

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

## Acceptance scope

The [qualification runner](../../tools/check_i5b.py) requires a sealed dependency
snapshot, the pre-change legacy baseline and independently inspected controlled
captures. The [performance contract](../../tests/input/fixtures/i5b/performance.json)
freezes 10 ms combined phase / 1,500 ms CLI medians, one warm-up and five measured
release repeats. No fixture-only result satisfies real-Windows acceptance.

The [implementation plan](../../Plans/i5b-zero-base-offset.md#b5--qualification-and-evidence)
defines independent fixtures, actual-code mutation controls, old-result
equivalence and controlled Windows capture work. Source/fixture and real-capture
acceptance are separate decisions. Existing zero-displacement zero-address
captures are refutation controls, not positive zero-base-offset evidence.

The retained [qualification](#retained-qualification) records 18 passing aggregate
gates, nine frozen fixture timing workloads and six controlled partial/full
Windows cases spanning positive, refuted and indexed-unknown answers. Its
reported source/fixture and both controlled Windows acceptance fields pass for
that finite corpus and exact source/tool/dependency inventory. The 10 ms phase
and 1,500 ms CLI ceilings are implemented frozen criteria; the separate
first-question and zero-address budgets retain their own acceptance records.
The first-question Windows timing condition is met by its later
[performance qualification](workload-performance-design.md#native-investigation-qualification).

Qualification excludes indexed numeric admission, Linux, historical null
provenance and object lifetime. A later checkout requires fresh or complete
identity-verified evidence; no new runtime or packaged-release qualification is
claimed by this documentation consolidation.

## Decoded record and independent oracle

The 2026-10-07 pre-implementation review inspected
[decode.cpp](../../native/llvm_mc/decode.cpp), emitting checked protocol 2 from
LLVM MC 20.1.2, and [protocol validation](../../src/llvm_mc/protocol.rs) for
bounded framing/counts/tags/control classification. Register zero is `r:NONE`.
The reviewed decoder SHA-256 was
`45dad913d912aed489a99a150edc846389877ef72cb9218b46b8e2e555ad813c`.
Every reviewed row has six operands, at these zero-based positions:

| Forms | Memory tuple | Other operand | Width / role |
| --- | --- | --- | --- |
| MOV32mi / MOV64mi32 | 0 base, 1 scale, 2 index, 3 displacement, 4 segment | 5 immediate payload | 32/64 bits; store |
| MOV32mr / MOV64mr | 0 base, 1 scale, 2 index, 3 displacement, 4 segment | 5 source register | 32/64 bits; store |
| MOV32rm / MOV64rm | 1 base, 2 scale, 3 index, 4 displacement, 5 segment | 0 destination register | 32/64 bits; load |

Six native rows were inspected at distinct VAs with independently chosen
`[RAX+8]` bytes: for example, `c7400805000000` yields MOV32mi with
`r:RAX i:1 r:NONE i:8 r:NONE i:5`; `8b4008` yields MOV32rm with
`r:EAX r:RAX i:1 r:NONE i:8 r:NONE`. Payloads do not enter the address.
The [generator](../../tests/input/fixtures/make_i5b.py) supplies explicit bytes,
not decoder-generated encodings. Independent ModRM/REX/SIB checks distinguish
implicit zero, signed disp8/disp32, extension and index/base sentinels.
`c704050800000005000000` is index-only RAX; `c704250800000005000000` has neither
GPR base nor index. Neither becomes an encoded base through affine normalization.

The [57-case manifest](../../tests/input/fixtures/i5b/manifest.json) provides
terms/constants, observations and EA using Python integers modulo 2^64, independently
of Rust/BAP/LLVM evaluation. It covers positive/nonzero-base/zero-displacement
controls for all six forms, signed negatives, RSP/RBP/R12/R13, SIB/index-only/
absolute/RIP, payload changes, span/context/exception negatives and aliases.
Admission negatives explicitly yield unknown. The
[TLA+ model](../../Specs/AriadneZeroBaseOffset.tla) and
[checker](../../Specs/check-zero-base-offset.sh) use representative zero/nonzero
bases and signed negative/zero/positive displacement classes; their decision
predicate is magnitude-independent. Full-width arithmetic, including nonzero
base with zero EA, has separate fixture/Rust coverage. This finite decision
model does not prove ISA semantics or native lifting.

The frozen [performance contract](../../tests/input/fixtures/i5b/performance.json)
and output accounting predate implementation: 64/64 limits extend the existing
32/32 context bundle, with exact-fit/zero/tiny controls. One warm-up/five measured
release repeats and 10 ms phase / 1,500 ms native CLI medians remain mandatory.
Source review alone supplies no capture or timing acceptance.

## Retained qualification

The [2026-10-07 aggregate](../../evidence/Ariadne/i5b-qualification.json) retains
18 passing gates, stable inventories of 294 sources and eleven tools, and
source/fixture plus controlled partial/full acceptance for the declared corpus.
Its `fullI5bAcceptance`, `sourcesStable` and `toolsStable` fields are true within
that scope. These are retained results, not a new qualification of this edit.

| Evidence component | Retained scope |
| --- | --- |
| Formal decisions | Apalache typechecking and TLC invariants; Safety checks 144 predicate combinations over two states. Question-level model, separate from Rust conformance and hardware semantics. |
| Runtime corpus | 57 independent synthetic cases plus one upstream-call fixture; seven release tests exercise native/reference/oracle agreement, six forms, decoded-role/context negatives, budgets/reports/CLI and seed/root separation. |
| Root and acceptance checks | Default/core-only tests, format, all-feature/all-target Clippy, Rust layout and sixteen Python controls pass; core-only has no activated external dependencies. |
| Regressions | Fourteen I5a gates, investigation/minidump/Stage E and twenty native-core gates pass under the same dependency view. Their narrower flags did not waive I4's then-unmet budget. |
| Sensitivity and preservation | All fifteen real implementation mutants detected by unchanged observers; no compile-failure/timeout credit. All 246 old I5a hashes (41 fixtures × two analyzers × three formats) and 24 default/explanation hashes remain exact comparison oracles. |

The selected read-only MirrorRust manifest SHA-256 is
`a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`.
The aggregate and nested native-core dependency record retain its full identity.
All nine frozen fixture timing cases pass; the largest CLI median is 805.819 ms
and phase median 1.348 ms. Each sample binds artifact/query, native receipt/build
and output hashes; phase output agrees with CLI output. Phase-only or base-mode
timings cannot substitute for assessment CLI samples.

The six independently inspected native Windows captures came from the isolated
controlled build with uploads disabled and a minimal child environment. The
inspector reads raw dump/context and matching PE bytes without invoking Ariadne,
BAP or the captured process. Positive bytes `c7410805000000` encode
`mov dword ptr [rcx+8], 5`, with RCX zero and reported byte eight. Refutation bytes
`c70105000000` have RCX/data byte zero. Indexed-unknown bytes
`c744110805000000` have RCX/RDX zero and data byte eight. Synthetic edits are not
counted as real captures; positive, refuted and unknown cases each have partial/full
capture evidence.

| Controlled case | CLI median (ms) | Phase median (ms) | Conclusion / budgets |
| --- | ---: | ---: | --- |
| Positive partial | 801.855 | 1.293 | Consistent; both pass |
| Positive full | 886.727 | 1.335 | Consistent; both pass |
| Refuted partial | 800.879 | 1.308 | Refuted; both pass |
| Refuted full | 898.798 | 1.422 | Refuted; both pass |
| Indexed-unknown partial | 801.059 | 1.193 | Unknown; both pass |
| Indexed-unknown full | 900.772 | 1.129 | Unknown; both pass |

The [manifest](../../evidence/Ariadne/i5b-evidence-manifest.json),
[controlled-case pins](../../evidence/Ariadne/i5b-controlled-cases.json) and
[archive](../../evidence/Ariadne/i5b-evidence.tar.gz) retain exact sources,
logs/reports/samples, mutations, nested native-core evidence and all six dumps,
witnesses and matching executable bytes. The 2,005 members were size/hash checked;
archive SHA-256 is `4b256fc48a5b18c0a929b8f64adeefcc57f58ff042cb31766e0113348bc6229c`.
Historical source/contract/plan bytes and original build paths remain in retained
records. Current canonical documentation does not replace those source identities.

Run [check_i5b.py](../../tools/check_i5b.py) through the sealed dependency view
with explicit `--output`, `--captures` and `--baseline` paths. Missing, skipped,
malformed, stale or over-budget evidence cannot qualify; fixture-only results
cannot satisfy controlled Windows acceptance. The independent I4 performance
successor retains its separate result. Full process memory, hardware origin,
executed history, indexed numeric support, object lifetime, universal ISA proof
and packaged cross-platform release remain outside this acceptance.
