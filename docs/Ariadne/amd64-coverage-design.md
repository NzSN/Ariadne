# Completing REP and AMD64 operation coverage

## Context and follow-up

**Current continuation: stopped at the user's request, 2026-10-23.** The
[stopped-work checkpoint](../../CHECKPOINTS.md#2026-10-23--remaining-amd64-plan-execution-stopped-at-user-request)
records additive source-obligation/authority tooling, the finite MOV8 pilot,
unfinished integration and stale binding identities. The earlier qualified
results below retain their source scope; this WIP does not renew them.

**Status.** Completion design with finite source/domain implementation, 2026-10-23.
The working tree based on `6c3fa96` implements separately selected v12/v13/v14 REP scopes
and an AMD-specific v15 address-size successor, a candidate five-volume source
corpus, historical-gap accounting and v2/v3 finite legal-domain/binding registries. The [dated stage execution](../../.agents/plans/amd64-operation-coverage.md#source-and-domain-execution-c1c4)
distinguishes exercised clauses from the remaining full-stage exits. The broader
encoding grammar, source completeness and consumer expansions remain open;
the finite plain-dependency profiles do not grant proof-consumer admission.
The v15 producer, projection and local capture gates pass; its current native
core handoff is awaiting specific approval after automatic review rejected the
changed payload.

**Why this document exists.** The [current BAP integration](bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting)
owns the original three-form v12 contract; this design records its separately versioned memory-string successors and remaining obligations.
The [origin checkpoint](../../CHECKPOINTS.md#2026-10-23--plain-rep-dependency-projection-and-coverage-accounting)
records the starting 10,569 unbound symbolic candidates and 2,657 manual
extraction gaps. Geometry now gives all 2,657 old gaps source-backed
dispositions, including explicit source conflicts; none lacks a disposition. Neither the candidate count nor a
transcription-gap count is a count of unsupported legal AMD instructions.

**What this document establishes.** This is the canonical design for closing
source, encoding-domain, implementation and consumer coverage. The BAP design
continues to own the implemented semantic interface and profile contracts.
This document owns the completion data model, algorithms, dated finite
implementation findings and remaining exits.

**Where to go next.** Read the [completion stages](../../.agents/plans/amd64-operation-coverage.md#coverage-completion-design-stages)
for execution order, the [test matrix](../../tests/README.md) for executable
validation, and the [BAP trust boundary](semantic-assurance.md) for what testing
can establish. The [remaining coverage execution plan](../../.agents/plans/amd64-operation-coverage.md#remaining-coverage-execution-plan)
breaks the work after historical-gap accounting into P0–P8 and the parallel
native gate, with concrete deliveries and exit checks. The [plan reading view](../../.agents/chatdocs/ariadne-amd64-coverage-remaining-plan-20261023/index.html)
presents proposed work from `08dcab9`; it adds no implementation acceptance.
The [execution HTML](../../.agents/chatdocs/ariadne-amd64-coverage-execution-20261023/index.html)
is the current dated reading view; the [original proposal](../../.agents/chatdocs/ariadne-amd64-coverage-design-20261023/index.html)
preserves the pre-execution version.

**What remains unresolved.** The legal-form denominator, source conflicts and unparsed constraints, wider REP
semantics, architectural state and proof consumers remain incomplete. Official
byte identity for the pinned AMD Volumes 4/5 is unverified. Universal ISA
execution correctness and Rust refinement remain separate obligations.
Windows unwind coverage remains with the [investigation design](investigation-design.md#amd64-unwind-coverage-program).

## 1. Problem and completion target

The work has three distinct deliverables:

1. A complete, source-backed inventory of legal forms within an explicit
   architecture scope, with checked encoding domains and exclusions.
2. Versioned bindings from those domains to implemented BAP transport,
   projection and consumer contracts.
3. Executable validation of every required form and contract partition, with
   gaps, tool failures and environmental premises remaining visible.

The proposed initial source scope is documented AMD64 long mode, including
application and privileged/system operations, the five architectural subsets
already named by the program, and an explicit extension manifest. Each release
must freeze vendor, publication revisions, extensions and execution modes.
Intel-only, future and undocumented XED records retain explicit dispositions;
they are not silently promoted into the AMD denominator or silently dropped.
A combined AMD/Intel claim needs its own pinned Intel source and extension set.
The scope freeze is an implementation gate, not a scope decision already accepted
by this proposal.

All documented forms inside the selected scope remain obligations. Missing
capture state, privilege, CPUID or operating-system state can produce explicit
conditional outcomes; they cannot justify removing a difficult instruction
from the denominator. A later scope change creates a new manifest and a visible
delta. It cannot turn an old incomplete campaign into a complete one.

“Full coverage” here means implementation and validation coverage of that
declared domain. It does not mean every concrete instruction execution has been
tested or that BAP has an independent ISA-correctness proof. A finite sample
cannot establish those stronger claims.

## 2. Current boundary

| Domain | Current state | Consequence |
| --- | --- | --- |
| XED source | 10,994 symbolic records: 10,569 long-mode candidates, 425 exclusions | A frozen candidate grammar, not a legal AMD instruction count. |
| Manual transcription | Historical v1 has 4,118 rows and 2,657 gap records; every old gap now has a source-backed disposition, with zero unassigned gaps and seven explicit source-conflict records | The old lock remains unchanged. Conflict and material dispositions retain unparsed constraints; historical backlog closure does not establish complete source/constraint coverage or a legal encoding. |
| Source provenance | Fresh publisher bytes match Vol1 r3.25, Vol2 r3.45 and Vol3 r3.38; indexed official Vol4 r3.26 and Vol5 r3.16 URLs return HTTP 404 | Vol4/5 remain pinned archive copies with unverified publisher-byte identity. |
| Current extraction | Candidate v2 reproduces all five volumes under pinned `pdftotext` 26.01, MuPDF 1.27 and Python 3.14.4; Vol3–5 normalized content matches v1 while full-layout hashes differ | Existing strict v1 pins remain active. Equal normalized content does not authorize migration or close previously unparsed source regions. |
| Representative v12 survey | 171 exact byte cases: 57 projected, 8 conservative unknowns, 106 remaining gaps | These samples do not bind any symbolic form authoritatively. Nine independent expectations match. |
| REP v12 | Exact `F3 A4`, `F3 AA`, `F3 A6`; plain dependency analysis only | Its three-form admission remains frozen. |
| REP v13/v14 | v13 selects 24 nonempty default-address producer forms; v14 adds four exact LODS forms from a separate pinned BAP source bundle | Both remain plain dependency profiles; address overrides, I/O and guard/target/refinement/composition proof transports remain refused. The recorded R1 source boundary passed 416 native parity instances and 259 refusal controls; the current v15 native policy has a separate pending gate. |
| AMD REP v15 | 56 canonical memory-REP tuples: 28 default-address plus 28 address-32; the new source bundle supplies 32 exact sequences | 178,080 numeric comparisons, 64 actual transport/projection cases and 448 local capture instances pass under an explicit AMD premise. Current native parity/refusal controls remain pending. |
| Accounting v1 | Candidate-only associations remain unchanged | The frozen 10,569 candidates still lack vendor-wide authoritative legal-form bindings. |
| Legal-domain/binding v2 pilot | Three source-derived F3 MOVS/STOS/CMPS families enumerate 24 canonical byte/environment points: 3 supported and 21 explicitly unsupported for v12 | Total disposition of this pilot does not close implementation, source completeness or the vendor denominator; fresh source-bound BIL, numeric and Rust admission checks pass for this pilot. |
| Legal-domain/binding v3 | 56 canonical AMD points, 516 source anchors and 111 fresh profile observations; v15 covers all points in this finite domain | Earlier profiles retain explicit unsupported points. Full source/vendor completeness and all 10,569 symbolic-domain bindings remain open. |

The survey's 106 remaining cases comprise 75 missing producer lifts, 28
unsupported control/semantics outcomes, two encoding disagreements and one
query error. The latter is PUSHFQ (`9C`), whose fresh lift exceeds the helper's
BIL AST budget. These are measured outcomes for selected bytes, not estimates
of how many legal forms remain.

## 3. Architecture

![Source authority, encoding bindings and semantic validation lanes](amd64-coverage-architecture.svg)

The source lane establishes encoding membership and applicability. The semantic
lane implements analysis behavior under pinned BAP lifting. Their join is a
versioned binding registry; the coverage validator checks their common domains
and current validation inputs. XED and LLVM provide independent encoding and
control checks. Neither supplies a substitute instruction-effect implementation.

Maintain source pins, compact grammar/rule definitions, reviewed correction
patches, generators and small regressions in the repository. Reconstruct PDFs,
full layout/geometry products, expanded inventories, solver products, reports
and copied build trees under ignored `target/` or temporary work. Do not restore
a retained qualification-evidence collection.

## 4. Source reconstruction and manual gaps

### 4.1 Freeze a reproducible source corpus

The implemented candidate [`source-corpus/v2` lock](../../tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json)
identifies publication, revision, publisher, retrieval origin, exact PDF
size/digest, selected chapters, appendices and global encoding-rule obligations.
The [source-corpus tool](../../tools/amd64_source_corpus.py) binds extractor
sources, executable and shared-library hashes, versions, options, locale and
normalization schema. Its decision remains `candidate-proposed-unreviewed`;
24 source-listed extension-family candidates are discovery inputs with explicit
unresolved supplementary-publication and CPUID/vendor audits. A live URL alone
is not a reproducible source identity.

Preserve the existing corpus lock. A new extraction toolchain produces a
separate candidate lock. Review PDF identity, full-text/geometry differences,
source-region coverage and normalized row/constraint differences before adopting
it. Reusing the old content digest is insufficient if changed source regions
were never represented by the old extractor.

### 4.2 Recover geometry and ownership

Use PDF word/glyph coordinates, table boundaries and outline ownership to build
source cells. A `sourceCell` has a PDF digest/page, rectangle, glyph span/digest,
table/row/column identity, owning instruction sections, continuation links and
footnote references. Printed page labels are useful annotations; PDF page
indices remain unambiguous source addresses.

The parser must track tables across pages and represent merged cells explicitly.
A spanning encoding cell can cover several operand rows only when geometry and
source structure justify that span. Never fill down a previous opcode merely
because the current cell is blank. Preserve alternative interpretations as
unresolved records.

Every old gap receives a source-backed disposition: resolved cell, justified
continuation, non-encoding material, source conflict, duplicate/alias, or unresolved. Record the
original gap ID, affected source cells, correction rule and review rationale.
Deleting a gap, suppressing a line class, or moving text outside a table does
not resolve an obligation. The implemented [geometry extractor](../../tools/amd64_manual_geometry.py)
now preserves those identities and reconstructs word-coordinate ownership;
[its finite execution](#102-geometry-and-source-region-execution-c2) accounts
for every historical gap while leaving seven source-conflict records, candidate
cross-page relations and unparsed constraints open.

### 4.3 Establish source completeness separately

Account for every selected source region, including prefix rules, operand-size
rules, exception/applicability notes, appendix maps and extension updates.
“All 2,657 gaps resolved” closes the old transcription backlog only. It does not
prove that the previous 4,118 rows contained all instruction forms or all global
constraints. Source-region coverage and legal-form derivation require their own
reviews and executable omission controls.

## 5. Legal forms and authoritative bindings

### 5.1 Keep identities separate

These records define the completion target. The restricted
[`legal-forms/v2` pilot](../../tests/bap/fixtures/amd64-semantics/legal-forms-pilot-v2.json)
and [`profile-bindings/v2` pilot](../../tests/bap/fixtures/amd64-semantics/profile-bindings-pilot-v2.json)
now implement a finite subset; the wider source/domain and semantic-contract
records remain to be completed:

| Entity | Required identity and content |
| --- | --- |
| `CoverageScope` | Vendor/publication/extension set, modes, environment axes, required semantic profiles/consumers and digest. |
| `SourceCell` | Exact source location, ownership, transcription/constraint role and reviewed disposition. |
| `LegalForm` | Source references, operation/operand roles, byte grammar, effective-size rules, prefix constraints and applicability predicates. |
| `TemplateRelation` | Legal-form IDs, frozen XED IDs, relation kind and source-backed explanation for equivalence, splitting, aliasing, overlap or absence. |
| `SemanticContract` | State reads/writes, normal/exceptional outcomes, memory/order/environment effects and conservative-analysis obligations. |
| `ProfileBinding` | Legal-form domain, producer and implementation rule IDs, semantic-contract ID, profile/consumer capabilities, source/ABI digests and validation obligations. |
| `ByteCase` | Exact consumed bytes, decode environment, binding/form IDs, independent expectations and current observations. |

A manual row can describe several legal forms, and several rows can describe
one form. One XED template can intersect multiple forms, and several templates
can cover one form. Store these relations explicitly; mnemonic and IFORM name
agreement is only a search aid.

Source-backed AMD forms absent from XED remain first-class obligations. Their
absence triggers a decoder/producer gap or a reviewed alternate encoding
reference; it must not remove them from the legal inventory. Conversely, each
XED candidate needs an explicit vendor/scope/alias/undocumented/future/unresolved
disposition.

### 5.2 Specify a restricted encoding grammar

Represent consumed instruction bytes, limited to 15 bytes, with declarative
constraints over opcode maps, prefixes and ordering, operand/address size,
REX/VEX/EVEX/XOP fields, ModRM/SIB, displacement, immediate and extension fields.
Preserve operand roles and register restrictions, including high-byte/REX
conflicts and reserved fields. Stream bytes after the consumed instruction are
separate input, not part of its identity.

Keep these predicates distinct:

```text
encoding_member(form, bytes, decode_environment)
instruction_applicability(form, architectural_environment)
profile_admission(binding, consumed_bytes, decode_environment,
                  pinned_producer_identity, typed_BIL, requested_consumers)
```

A recognized encoding can require an architectural exception in a particular
environment. It is not necessarily undecodable. Feature-dependent opcode
aliases need guarded resolution; a disabled feature must not automatically be
treated as either “not in scope” or a generic invalid opcode.
Admission must validate the entire chain from captured consumed bytes through
the legal-form match to the exact producer query/BIL and consumer selection.
Bind snapshot/VA, bytes/extent, target/environment, helper/runtime identity and
AST digest; a well-typed BIL shape for different bytes is insufficient. When a
feature-dependent alias cannot be selected from justified premises, retain the
alternatives under a reviewed join or report the unresolved applicability.

### 5.3 Check totality and overlap

For a legal form `f`, let `D(f)` be its declared byte/environment domain. Each
point must have a checked disposition: implemented binding, architectural alias
or exception contract, explicit unsupported obligation, or unresolved region.
Aliases and exception outcomes count as supported only through their own
implemented contracts. Scope exclusions are accounted before constructing
`D(f)`; removing a point already inside it requires a new reviewed scope manifest.

The validator checks:

```text
S(f) union U(f) union X(f) = D(f)       # total disposition accounting
S(f) = D(f), U(f) = X(f) = empty       # implementation completeness
binding_domain is a subset of its referenced legal-form domains
overlaps have identical meaning or a checked, source-backed dispatch rule
```

Here `S` is the union of implemented binding domains, `U` is explicitly
unsupported, and `X` is unresolved. Covering a region with an unsupported record
completes its accounting, not its implementation.

Use finite enumeration for small fields and a restricted constraint solver for
larger symbolic products. A solver timeout, unsupported constraint or unknown
answer leaves the obligation open. Do not assign success after a work cap.
Independently replay satisfying witnesses and counterexamples; use separate
checks for table/grammar derivation, partition coverage and implementation
dispatch. The grammar and its translation remain reviewed trust premises.

A byte recipe is a witness to membership, not proof of totality. A collection
of passing examples cannot certify `S(f) = D(f)`. Conversely, domain totality
does not prove instruction execution semantics; that remains under the BAP
trust boundary and separately exercised analysis contracts.

### 5.4 Version the authoritative path

Keep `ariadne.amd64-form-case-associations/v1` candidate-only and preserve
`coverage/v1` behavior. The separate [v2 legal-domain checker](../../tools/amd64_legal_forms.py)
implements `legal-forms/v2`, `profile-bindings/v2` and `coverage-assessment/v2`
for the restricted pilot. It rejects unknown fields, duplicate identities,
orphan references, inconsistent aliases and stale source, producer, grammar or
consumer digests. Unsupported grammar and exhausted enumeration return an
unknown outcome; the pilot supplies no wider solver or source-completeness claim.

No `authoritative: true` switch may promote an existing association. The new
checker must validate the source derivation and domain obligations. Digests bind
the reviewed inputs; hashing a claim does not establish its authority.

## 6. Remaining REP design

### 6.1 Expand operation dimensions explicitly

The proposed memory-string progression is:

| Family | Repeat condition | Element widths | Address-size work |
| --- | --- | --- | --- |
| MOVS, STOS, LODS | F3 count-controlled | 8 / 16 / 32 / 64 | Default 64-bit addressing, then separately reviewed 32-bit addressing. |
| CMPS, SCAS | F3 while equal; F2 while not equal | 8 / 16 / 32 / 64 | Same independent address-size progression. |
| INS, OUTS | Separately reviewed F3 I/O repetition | 8 / 16 / 32 | Separate external-state, privilege and exceptional-completion contracts. |

R1 implements the default-address portion through two successor profiles: v13
for 24 nonempty original producer lifts, and v14 for those forms plus four LODS
lifts from a separate BAP source bundle. See the dated execution below for
producer, projection and consumer-validation scopes.

These family/condition/element choices give 28 memory-string planning tuples
at default address size, including the current three, or 56 after adding the
second address-size choice. They are planning tuples, not legal-form or
exhaustive-encoding counts. Prefix/segment variants and environmental domains
still require source-derived bindings. [AMD repeat-prefix tables](https://docs.amd.com/api/khub/documents/BqEoC2FadIAgbrUdEzDJIg/content#page=54)
are the source starting point.

Each recipe records operation, element width, address/count/index width,
repeat condition, applicable source-segment selection, exact prefix constraints
and environment predicates. A MOVSD string encoding must never be selected by
the ambiguous mnemonic alone. Extra prefixes, prefix order, repeated prefixes
and feature modifiers remain unreviewed until their particular domains are
established; F2/F3 never become generic permission bits.

For comparison/scanning repetition, the newly produced ZF controls continuation
after the first iteration. Tests must distinguish an initial ZF from the first
comparison's result. Element size and address/count size are independent.
[Intel's repeat-operation reference](https://cdrdv2.intel.com/v1/dl/getContent/671241#page=573)
provides an independent primary cross-check.

### 6.2 Preserve the abstract loop contract

Retain the v12 zero-or-more dependency fixed point as the minimum conservative
contract. Entry origins survive the zero-iteration alternative; possible body
writes do not become definite kills. LODS/SCAS add accumulator lane and flag
obligations. Element-width changes add multi-byte memory, overlap and arithmetic
wrap cases. Address-size changes add count/index lane rules and upper-half
behavior; test nonzero upper halves with both zero and nonzero effective counts.
Do not infer zero-count upper-lane behavior from a generic register-write rule.

Recognize a reviewed producer loop structure with bound temporaries, typed
conditions and no unreviewed external control. Do not synthesize effects from
an opcode when BAP lacks the lift. A larger legitimate BIL tree needs a reviewed
transport/resource contract; raising an AST limit alone does not implement a
missing architectural state bank.

Preserve bounded work and explicit exhaustion. A more precise range or
closed-form optimization must conservatively refine the established loop
summary and pass the same zero-iteration and loop-carried-origin controls.
Do not concretely iterate a captured RCX value: the snapshot does not establish
the instruction's entry count or earlier executed iterations.

### 6.3 Separate normal completion and fault/restart semantics

Extend the semantic outcome model before claiming fault-sensitive REP support.
Represent normal completion, a possible completed-iteration prefix followed by
a fault, and interruption/restart boundaries under their architectural premises.
Do not make a partial prefix imply the final normal result or attach a
normal-completion guard to a fault outcome. Memory accesses need conditional
width/progress/ordering information, not a first-iteration affine address
reused for the entire operation.

I/O repetition requires explicit external I/O state and side effects; it cannot
be implemented by a `memory:any` rule. A port read can precede a later memory
fault. The [Intel REP INS reference](https://cdrdv2.intel.com/v1/dl/getContent/671241#page=572)
and [comparison fault behavior](https://cdrdv2.intel.com/v1/dl/getContent/671241#page=574)
must be reconciled with the selected AMD contracts before admission. A
normal-completion numeric oracle does not close those gates.

### 6.4 Version every consumer capability

Freeze v12's current meaning. Allocate successor semantic profiles and, where
needed, new receipt/checker generations; numeric version IDs are assigned at
implementation time. Reusing the same producer binary does not make a new
projection or proof contract equivalent to an old one.

| Consumer | Required expansion contract |
| --- | --- |
| Plain dependency projection | Exact recipe admission, bounded closure, lane/flag/memory effects and explicit outcomes. |
| Address evidence | Retain every possible access; iteration-dependent addresses stay unknown unless a separate range contract is validated. |
| Guard admission | Derive transfers over the whole loop; preserve an unaffected register only after checking all writes; no assumption of nonzero count or normal completion. |
| Captured targets | Havoc every possibly written binding or validate a loop summary; preserve original edges, candidates and coverage obligations. |
| Memory refinement | Treat all potentially reached writes as barriers unless a checked footprint proves exclusion; no first-iteration disjointness shortcut. |
| Composition/native replay | Replay the same profile, outcomes, query and proof premises; invalidate receipts when any bound rule changes. |

Use explicit capabilities per profile and consumer. During migration, a
consumer continues to refuse unsupported recipes before work, including empty
and all-null source domains and direct checker entry points. Bind the overall
semantic identity as well as site identities. Old/current transport mixing and
substring lookalikes must remain negative controls.

## 7. Close the rest of AMD64 by contract family

After the denominator is available, generate work by missing capability rather
than selecting convenient mnemonic examples. BAP source gaps, transport gaps,
state-bank gaps, projection gaps and consumer gaps are separate classifications.
PUSHFQ's AST-budget failure belongs to transport/producer assessment until a
reviewed lift is transported; it does not count as supported after a counter
is increased.

Architecture-state stages need explicit alias and partial-write rules for
wider vectors/masks, x87/MMX relationships, control/status state, segment bases,
system registers and external state. Atomic/order effects and system or
exceptional control require contracts beyond ordinary scalar writes. Coarse
`state:other` writes cannot justify killing unrelated aggregate origins.

Each family slice must connect source legality, actual producer BIL, normalized
effects, required consumers, independent tests and an exact profile identity.
An implemented conservative contract may legitimately retain environmental
unknowns. An unimplemented operation cannot close its row by emitting generic
unknown effects. BAP remains the semantic dependency; LLVM remains the
independent decode/control reference. Supplied LLVM IR and abstract stateflow
remain separate APIs.

## 8. Validation and acceptance

Track four independent axes for every binding:

| Axis | States and required evidence |
| --- | --- |
| Source/domain | Unresolved, reviewed member/alias, justified exclusion; source-backed grammar and totality/overlap checks. |
| Implementation | Missing producer/transport/state/projection/consumer, or implemented named contract; no credit from decoding alone. |
| Execution | Unexercised, passed, failed or blocked by prerequisite; exact current source, tools, profile, query and corpus. |
| Capability | Explicit support/refusal for each required consumer and outcome; approved conservative behavior has a stated invariant and precision limit. |

Do not overload one Boolean “supported” with all four meanings. Report source
coverage, binding-domain coverage, tested partitions and semantic outcomes
separately. A full claim names its scope and required consumer set, and requires
all of their obligations. A narrower plain-projection release can state its
own finite support while program-wide Q1 remains open.

The validation suite must include:

- Independent source-region omission and merged/continued-cell regressions;
  legal AMD forms absent from XED; overlapping feature-dependent aliases.
- Exact-byte positives and negatives for widths, address size, prefix fields,
  register restrictions, reserved encodings, length boundaries and trailing
  stream bytes; wrong-byte/environment/producer bindings despite valid typed
  BIL. Unsupported is distinct from architecturally invalid.
- REP zero/one/many counts, both directions, initial/opposite ZF, first/late
  mismatch, overlap, pointer wrap, lane preservation, segment-state uncertainty,
  later-iteration writes, virtual bindings and resource exhaustion.
- Actual fresh BAP BIL with independently supplied numeric/flag/memory
  expectations, Rust/native full-state comparisons and saved-proof tampering.
- Compiled mutants for dropped source regions, narrowed domains, omitted entry
  joins, single-pass loop summaries, stale output equations, first-iteration
  alias exclusion and omitted overall-profile checks.
- Applicable analysis-model/replay checks and root format/default/core-only/
  strict-Clippy/layout checks. New analysis contracts need their owning model
  changes and qualification; an encoding inventory does not replace them.

Mutant credit requires a passing exact control, a compiled changed SUT, the
intended unchanged observer's behavioral rejection, private build outputs and
restored source/observer checks. Missing runtimes, solver unknowns, timeouts,
compile failures, ignored tests and old reports never supply positive credit.
Keep a small actual regression for each closed failure class; regenerate the
large campaigns instead of maintaining their logs or passing flags.

## 9. Delivery sequence and stop rules

The [linked execution stages](../../.agents/plans/amd64-operation-coverage.md#coverage-completion-design-stages)
own scheduling and status. Source and REP work may proceed in parallel, but a
REP slice does not close the inventory gate, and inventory closure does not
qualify a producer or consumer.
The [post-backlog execution plan](../../.agents/plans/amd64-operation-coverage.md#remaining-coverage-execution-plan)
orders the remaining C1–C4, R2–R4, A1 and Q1 work into source adjudication,
constraint extraction, legal-domain construction, bindings, implementation and
integrated validation. Its first delivery tracks all seven conflicts and 33
table relations; its proposed first new domain pilot is register-only byte MOV.

| Stage | Exit |
| --- | --- |
| C1 — Source scope | Freeze corpus, vendor/extension boundaries and official source identities. |
| C2 — Transcription | Account for all selected regions and resolve each old gap with a source-backed disposition. |
| C3 — Legal domains | Complete reviewed grammar, manual/XED reconciliation, aliases and counterexamples. |
| C4 — Binding checker | Versioned authoritative schema; checked totality, overlap and dispatch; no unresolved domain silently omitted. |
| R1 — Memory REP | Review and qualify remaining default-address memory-string tuples under a new profile. |
| R2 — Address/prefix variants | Qualify address-size, segment and prefix domains with lane/zero-count controls. |
| R3 — Proof consumers | Implement each required guard/target/refinement/composition contract and native replay generation. |
| R4 — I/O and faults | Implement environmental and partial-completion/restart contracts; retain explicit gaps until qualified. |
| A1 — Architecture families | Close producer/state/projection/control gaps for every legal form and required consumer. |
| Q1 — Scoped full coverage | All previous required exits and current validation obligations pass for the frozen scope; report proof and environmental limits. |

R1's finite default-address gate is recorded as complete. Next work is the
remaining C1/C2 source/ownership audit, broader C3/C4 domains and the current
v15 native gate; its canonical address-size producer correction is implemented.
Do not first add thousands of name associations or enable generic loop/prefix
admission. If the source corpus, domain solver or semantic producer cannot meet
an exit, retain the specific blocker and continue independent stages without
changing the acceptance predicate.

## 10. Source review and validation status

The implementation seams reviewed for this design are the
[XED extractor](../../tools/amd64_inventory.py),
[manual extractor](../../tools/amd64_manual_inventory.py),
[source-corpus candidate tool](../../tools/amd64_source_corpus.py),
[geometry reconstruction](../../tools/amd64_manual_geometry.py),
[finite legal-domain checker](../../tools/amd64_legal_forms.py),
[candidate accountant](../../tools/amd64_coverage.py),
[v12 matcher](../../src/bap/repeated_strings.rs),
[typed admission](../../src/bap/admission.rs),
[dependency projector](../../src/bap/projection.rs),
[address evidence](../../src/bap/address.rs),
[target transfers](../../src/bap/target_resolution.rs) and
[native capture boundary](../../native/bap-core/capture.ml).

The [current checkpoint](../../CHECKPOINTS.md#2026-10-23--plain-rep-dependency-projection-and-coverage-accounting)
records the prior finite validation. The initial design publication ran only
document/link/SVG checks. The execution below adds independently scoped
source-reconstruction and finite-domain tests; it does not convert the remaining
proposals into accepted source, encoding or semantic coverage. Current helper,
source and observer identity checks remain required after further implementation
changes.

Primary source entry points are the pinned
[AMD Volume 3 revision 3.38](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB),
the repository's [manual source pins](../../tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json)
and [XED source/selection pins](../../tests/bap/fixtures/amd64-semantics/inventory.lock.json).
The Intel cross-checks cited in section 6 are references to review, not a newly
adopted source corpus. They require explicit source pinning before becoming
denominator authority.


### 10.1 Source-corpus execution: C1

2026-10-23: the new candidate lock covers all five APM volumes, AMD long-64
application and privileged/system operations, and the five architectural
subsets. Supplementary AMD publications and source-listed extension families
retain explicit unresolved obligations; the candidate cannot self-assert
reviewed adoption. Vol1/2 global rules and every non-reference chapter/appendix
remain required source regions.

Fresh publisher retrieval matches the exact repository PDF sizes and SHA256
pins for Vol1 r3.25, Vol2 r3.45 and Vol3 r3.38. AMD's indexed
[Vol4 r3.26 content URL](https://docs.amd.com/api/khub/documents/ioQiNhSqxlMkRaU~IyGQYQ/content)
and [Vol5 r3.16 content URL](https://docs.amd.com/api/khub/documents/w13cmcpL4f9MCT4WPN6eDg/content)
return HTTP 404 during the current check. Search-index revision metadata does
not establish equality with the pinned archive bytes. Those two byte-identity
clauses remain open.

A bounded follow-up against AMD's static `26568.pdf` and `26569.pdf`
download endpoints also times out without verified PDF bytes. That result
neither disproves availability nor establishes equality with the archive pins.

The candidate pins `pdftotext` 26.01.0, MuPDF 1.27.0 and Python 3.14.4,
their executables and 89 runtime-library identities, extractor source hashes,
UTF-8/layout/bounding-box options, `LC_ALL=C`, `LANG=C`, `TZ=UTC` and the
normalization schema. Fresh `reproduce` and `check-products --require-all`
exercise all five PDFs. Vol3–5 normalized content hashes match the historical
v1 content, while all three full-layout hashes differ; historical locks are
unchanged. Fourteen source-corpus controls reject missing identities, false
adoption/completion fields, changed tools/libraries/options/locale, altered
PDFs/products, unsafe origins and incomplete or stale migration reviews.

A fresh validation campaign starts with `reproduce` against the pinned PDFs
and tools, then runs `check-products`. The latter verifies current identities
and generated bytes; it does not rerun PDF extraction. Resealing an altered
intermediate manifest cannot replace the fresh extraction premise. Migration
checks bind explicit review inputs and comparison artifacts but never establish
corpus adoption by themselves. C1 remains open pending reviewed scope/extension
boundaries, complete source-region/global-rule coverage, migration review and
official Vol4/5 byte identity.

### 10.2 Geometry and source-region execution: C2

2026-10-23: the first geometry pass established 1,726 source-backed dispositions
and 931 unresolved gaps; the next pass added 350 dispositions. The final
historical-backlog pass accounts for the remaining 581 obligations. All 2,657
gap IDs, ordinals, original objects and legacy source addresses remain present,
and all 2,076 earlier dispositions remain byte-for-byte equivalent as JSON data.

| Publication | Original gaps | Source-backed dispositions | Unresolved |
| --- | ---: | ---: | ---: |
| Vol3, 24594 | 159 | 159 | 0 |
| Vol4, 26568 | 1,987 | 1,987 | 0 |
| Vol5, 26569 | 511 | 511 | 0 |
| Total | 2,657 | 2,657 | 0 |

The last 581 dispositions have distinct source obligations:

- Vol3 accounts for 60 CMOV width-group gaps, 34 SETcc alias-group gaps,
  five wrapped opcode fragments, one literal `F2/F3` encoding and 45 explanatory
  material records. Shared cells require exact named columns, tightly spaced
  and isolated source-owned groups, and a unique centered opcode. Literal
  MOVDIRI/MOVDIR64B `3B` bytes remain unchanged.
- Vol4 accounts for 269 records through explicit notes, footers, semantic/alias
  tables, source headings/prototypes, superscript geometry, named column bounds
  and retained word-box spans for combined cells. AESENC's actual heading
  supplies an ownership overlay while preserving its incorrect historical
  `AESDECLAST VAESDECLAST` bookmark association. Seven records retain
  `source-conflict`: malformed operands/bitfields or disagreements between a
  printed mnemonic and its section heading. Examples include
  `xmmVGETEXPPD2`, `X.1323r33111.` and SHA256MSG1 within the SHA256MSG2 section.
  No intended correction or authoritative legal binding is inferred.
- Vol5 accounts for 166 material records and one FNSTENV operand continuation.
  Owned EPS labels, immediate-field captions, before/after stack labels and
  numeric-result headers bound the material. Repeated and staggered text
  requires unique neighboring anchors, increasing source order and distinct
  source-cell assignments; one PDF cell cannot discharge two historical lines.

Material and conflict records retain `constraintsParsed=false`. Their
disposition establishes where the old parser overreached or what source text
it missed; it does not validate a legal encoding or parse a diagram's operation.
Recovered bindings live in explicit disposition evidence, leaving the historical
inventory and existing derived rows intact. The old generic CMOV/AES refusal
controls remain active; the new rules require additional structural evidence.

The [geometry extractor](../../tools/amd64_manual_geometry.py) dispatches pure
per-volume recovery passes after the original parser. Integration checks reject
mutated context, rewritten IDs or prior dispositions, absent/foreign source
cells, lost legacy source lines and invented entry/row identities. Its
`extractorSources` map binds all nine extraction/dependency modules in both
geometry and region products. The v2/v3 binding registries inherit that closure;
editing any volume helper invalidates both registries. `check` reconstructs the
whole expected output, so resealing an omitted gap or altered owner cannot pass.

Sixty-one geometry controls and thirteen historical extraction controls pass.
Actual PDF excerpts and negative controls exercise missing, duplicated, moved
and wrong-column cells, foreign heads, misplaced superscripts, conflicting
owners, new notes/opcodes and repeated-line aliasing. The complete BAP-side
Python suite passes 145 tests and the tooling suite passes 328. The checked main
extractor SHA-256 is
`f98ac07ecbda55e32d2e2190bd4a216c44bbe28b11462bf783580d2b458ad257`;
its output also binds the eight dependency/helper identities.

Fresh `extract`/`check` cover all three historical instruction-reference
publications. Five-volume `regions`/`check-regions` enumerate all 4,128 PDF
pages and eleven required source-region clauses. The pinned C1 products and
their fresh-extraction premise remain required inputs. Enumeration does not
establish complete parsing of global rules, footnotes, semantic constraints or
the 33 candidate cross-page continuations (25 in Vol3 and eight in Vol4).
`oldGapBacklogClosed` is true; `allSelectedSourceConstraintsParsed`,
`sourceCompletenessEstablished`, `legalEncodingCompletenessEstablished` and
`c2Complete` remain false. The historical backlog is accounted for; C2's wider
source contract remains open.

### 10.3 Finite legal-domain and binding execution: C3/C4

2026-10-23: the separate v2 pilot derives canonical F3 MOVS, STOS and CMPS
families from exact Vol3 r3.38 source cells and enumerates element widths
8/16/32/64 with address widths 32/64. The predeclared scope excludes other
families, alternate prefix order and redundant/segment prefixes before domain
construction. Its 24 byte/environment points partition into three supported
v12 plain-dependency points (`F3 A4`, `F3 AA`, `F3 A6`) and 21 explicit v12
unsupported points. Unsupported points remain obligations for that consumer;
they do not deny another profile's separately qualified capability.

The checker validates total disposition, binding-domain inclusion, disjoint
S/U/X partitions, holes, aliases, exact consumed bytes/environment and source,
producer, typed-BIL and consumer identity. Twenty-four portable controls exercise
missing/narrowed domains, overlaps, wrong bytes, stale inputs, forged claims,
unknown grammar and exhausted work budgets. A total disposition result does
not satisfy implementation completeness while 21 points remain unsupported.
This pilot neither binds the 10,569 XED candidates nor establishes a full AMD
legal-form denominator. Source derivation and the restricted grammar remain
reviewed trust premises; a general constraint solver is still unimplemented.

The historical-gap continuation reseals thirty-nine implementation identities and
obtains three fresh producer BIL observations, 720 independent numeric
comparisons and the passing exact-lift Rust observer
`fresh_producer_loops_project_under_only_the_repeated_string_profile`.
Fresh `build` without `--skip-rust-admission` and `check --require-bindings`
both pass. `totalDisposition` and `profileBindingsValidated` are true only for
this pilot; implementation, source completeness, vendor-wide totality and full
AMD64 support remain false. The final binding digest is
`e303967b3d22daf32a32a4b8dbc2bb389d341117343b43e6a2c80b15ee0f944f`.
Further bound source changes require another fresh producer/oracle/Rust
campaign. C3/C4 remain partial.

### 10.4 Default-address memory REP execution: R1

2026-10-23: the 28-tuple recipe contract freezes MOVS/STOS/LODS at four
widths and CMPS/SCAS at four widths and both repeat conditions. The maintained
`memory-recipes-v2.json` records the original producer's four empty LODS lifts
explicitly. It remains a v13 availability contract; selecting v14 requires a
separate actual producer, rather than changing those old observations.

`Config::with_memory_repeated_strings(flags)` selects
`bap-bit-provenance-v13` and the unchanged advanced flag bundle. It admits
24 exact canonical byte sequences: MOVS/STOS B/W/L/Q under F3, and CMPS/SCAS
B/W/L/Q under F3 or F2. The pinned BAP names 32-bit string forms with L.
Word forms require 66 before F2/F3; REX.W follows F2/F3. Extra, reordered,
segment and address-size prefixes remain refused. v12's three byte forms and
the older packaged/Basic/advanced contracts stay frozen.

`Config::with_memory_repeated_strings_and_lods(flags, lods)` selects
`bap-bit-provenance-v14`. Environment selection requires
`ARIADNE_BAP_SOURCE_EXTENSION_MODE=memory-repeated-strings-with-lods`,
`ARIADNE_BAP_SOURCE_EXTENSION=flags` and
`ARIADNE_BAP_LODS_SOURCE_EXTENSION=lods`. v13 uses mode
`memory-repeated-strings` and only the flag directory. A missing or mismatched
LODS directory fails configuration validation. Older builder methods clear that
additional directory when selecting their own contract.

The separate LODS patch extends the pinned upstream BAP parser/type/lifter
for exact F3 AC, 66 F3 AD, F3 AD and F3 48 AD in long mode. It produces actual
typed BIL: an initialized virtual loop flag followed by one nonempty loop.
The transport validates that structure, architectural namespace and types,
source/SDK/build/executable identity, exact target/snapshot/VA/bytes/extent,
response/AST/time limits and artifact stability before and after a query.
Only an empty original lift with matching independent decode/control facts can
select this producer. BAP remains the sole semantic source; the adapter builds
no opcode effects. Combined runtime identity includes both source bundles.

With the original checked SDK in its compatible build environment, reproduce
the two isolated bundles with:

```sh
python3 native/bap/source-coverage/lods_build.py --output target/lods-source-a
python3 native/bap/source-coverage/lods_build.py --output target/lods-source-b
cmp target/lods-source-a/runtime/manifest.json target/lods-source-b/runtime/manifest.json
cmp target/lods-source-a/runtime/lods-lift target/lods-source-b/runtime/lods-lift
```

Run the selected-bundle Rust transport test with
`ARIADNE_BAP_LODS_SOURCE_EXTENSION=target/lods-source-a/runtime` and
`cargo test --offline --locked --lib native_pinned_bundle_transports_actual_typed_loops_for_both_targets -- --ignored`.
The two `memory_rep_recipe_materialization_v13`/`v14` ignored tests also need
the pinned BAP/LLVM helpers and `ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION`.
Run both native matrices with
`cargo test --offline --locked --lib memory_rep_recipe_matrix_preserves_roots_effects_and_origins -- --ignored --test-threads=1`
and the current source-matching `ARIADNE_BAP_CORE_DIR`. This filter selects
both `native_memory_rep_recipe_matrix` and `native_lods_memory_rep_recipe_matrix`;
the former prefix alone misses v14. A missing or stale native core remains an
unexercised prerequisite.

Two independent corrected builds have identical manifest SHA256
`8565bd4ab05e3592ea6372fe1cceec230b131538836a61800a6f5ea3f17e4d35`
and executable SHA256
`bba596dc1f599090e20259a0d6880ec66cd5c472276678aeb17d1ce2e0b38466`.
These are adopted only in the new `lods.runtime.lock.json`; earlier locks are
unchanged. Each build checks four typed new forms, 38 refused prefix neighbors,
four trailing sequences and ten unchanged baseline observations. The serializer
uses the pinned C API casts LOW=0/HIGH=1/SIGNED=2/UNSIGNED=3; a dedicated control
rejects accidental constructor-order serialization. Earlier wrong-cast builds
and transient compilation failures receive no qualification credit.

Fresh independent equations pass 43,200 comparisons for the 24 v13 forms and
14,400 for the four LODS forms, covering zero/multiple counts, both DF values,
initial flags, comparison termination, overlap, multi-byte elements, accumulator
lanes and supplied memory/address wrap. These finite normal-completion tests
compare all represented registers/flags and complete supplied memory. Five
source/oracle controls and twelve portable transport controls pass. One ignored
Rust test exercises all four actual source lifts on both OS targets, validates
v14 projection and verifies that v13 still refuses them.

The shared zero-or-more dependency fixed point retains entry origins and
weak writes with empty `must_defs`. Iteration-dependent memory addresses stay
explicitly unknown. The two local captured-input matrices pass 192 v13 and 224 v14 tuple
instances across both OS targets, zero/nonzero setup counts and both DF
values. They validate unchanged roots/seeds, exact uses/may-writes, empty
must-writes, unknown iteration-dependent memory evidence, retained entry/REP
origins and investigation binding. Portable proof APIs refuse both profiles
before helper/decode work, including empty roots. The current native gate
also passes all 416 parity instances and 259 direct/protocol refusal controls;
the four compiled loop mutants retain their independently checked scope.
R1 is complete for these 28 default-address planning tuples. This finite
normal-completion/dependency qualification supplies no partial-fault, restart,
I/O, address-override or general ISA guarantee. C1–C4, R2–R4, A1 and Q1 remain
open at their broader exits.


### 10.5 Address-size assessment: R2

2026-10-23: fresh original BAP and LLVM probes cover 28 recipe families,
nine prefix scopes and two target labels: 504 observations. All 28 canonical
67-prefixed forms have matching decoder extents. Four MOVS widths produce
nonempty BIL, but use RCX/RSI/RDI at 64 bits; the other 24 canonical forms have
empty BIL. Thirty-two concrete counterexamples establish incorrect low-32
zero-count loop entry, high-index address behavior and both 32-bit wrap
directions for those MOVS lifts. The zero-count control evaluates loop entry
without concretely iterating a huge count. Three portable equation controls pass.

Seven neighboring prefix families retain raw observations: FS, LOCK,
duplicate address/repeat prefixes, reordered address prefixes, extra REX and
trailing bytes. Decoding a neighbor grants no semantic admission. The report
binds current helpers, libraries, source and actual BIL; its implementation,
full-acceptance and broadened-profile flags remain false. R2 needs a separately
reviewed BAP source correction for count/index/address widths and upper-lane
behavior before any new prefix can be selected. v12/v13/v14 remain unchanged.

### 10.6 Current root checks and remaining qualification

This subsection records the completed R1/v14 source boundary. The subsequent
R2/v15 continuation below has new source identities and separate current gates.

2026-10-23: the final serial default suite passes 457 Rust tests with 155 ignored;
core-only passes 64 with 22 ignored. Strict all-feature/all-target Clippy,
formatting, Rust layout and document navigation pass. The root commands use
the existing read-only, hash-pinned MirrorRust snapshot; the sibling checkout
is unchanged and core-only normal dependencies remain empty. An earlier
concurrent default run exceeded an existing guard publication deadline; it
receives no passing credit. The same frozen source passes the serial run.
All 81 BAP-side Python controls and 304 tooling controls pass, including the
new source, geometry, legal-domain, recipe, LODS and address-size checks.
Four optimized compiled loop mutants are detected at the intended named
assertions after their exact unchanged controls pass: omit zero-iteration entry,
stop after one body application, omit target havoc and permit nested loops.
Each uses a private SUT/build directory; source restoration, unchanged observers,
current source identities and the pinned MirrorRust dependency are verified.
Compile failures and timeouts earn no mutation credit. The Rust campaign and
the native campaign below establish separate finite clauses.

All 416 local memory-REP materialization instances and the separate native
LODS source/transport tests pass in their declared scopes. The user then
explicitly approved the prepared source-only transfer to `win10`, resolving the
automatic approval-review block. The 25-file payload and thirteen existing
Rust/model/legacy inputs match the checkout. The original isolated SDK verifies
its inventory and builds a fresh core whose executable SHA256 is
`b01c3bf697eb53c355c88716b4ee41a0010809bd71c501fbb3ac9be86698a7bf`.

The retrieved helper passes an explicit audit of all fourteen native source
hashes, the SDK lock and seventeen SDK/compiler/model/engine identity fields.
This audit is required: runtime transport verifies manifest/executable and
ready-frame consistency, while the native-control runner checks four policy
sources; neither alone proves that every bound source matches the checkout.
The same identities are checked again after the tests.

All 97 direct and 162 framed native controls pass. Their exact overall/site
profile checks cover v12/v13/v14, empty/all-null domains, direct checker entry
points, malformed proof bodies and lookalike tokens. The two ignored native
matrix tests both pass: 192 v13 and 224 v14 tuple instances across sixteen
synthetic Windows/Linux capture queries, with zero/nonzero setup counts and
both DF values. Every query has complete Rust/native state equality and the
existing effects, weak-write, origin, seed/root, memory-gap and investigation
binding assertions. The v12 saved-capture/tampering and old advanced-composition
positive/tampering regressions also pass against this new helper.

This closes the current R1 finite native gate. It does not enable REP proof
consumers or qualify real-capture timing, partial faults, address-size variants
or full AMD64 coverage. Source-corpus, legal-domain, architecture-family and
full-coverage exits remain open. The [completed native campaign](../../.agents/plans/amd64-operation-coverage.md#native-memory-rep-qualification)
records the approved payload, isolated environment and exact exercised gates.


### 10.7 AMD address-size REP implementation: R2

2026-10-23: v15 implements a finite canonical address-size slice under an
explicit AMD long-mode premise. It selects all 28 default-address memory REP
tuples and the corresponding 28 tuples with leading 67. The existing v12/v13/v14
contracts and producer pins retain their scopes. R2 as a whole remains open for
other prefix orders, redundant prefixes and segment-selection domains.

The new BAP source bundle composes the frozen LODS patch with
`rep_address.patch`. It supplies four default-address LODS forms and all 28
address-32 forms. It corrects the original four nonempty MOVS lifts as well as
supplying missing lifts. Selection requires exact consumed bytes, length and
ordinary-control agreement from the independent decoders; the explicit v15
producer then replaces the original lift even when that original BIL is
nonempty. The adapter transports actual BAP BIL and synthesizes no opcode effects.
All 28 default-address source behaviors remain unchanged in fresh comparisons,
including byte-identical BIL from the earlier v14 LODS runtime.

Two independent final builds have identical manifest SHA256
`815fc8842899d05f6db51aa53cf21b4c82fd50fdae42200b43df4e6735cf48d4`
and executable SHA256
`e834c5e9e25a4b2f93de448a01326482493a93430ea1ce43428289b2685c727e`.
Only the new `rep-address.runtime.lock.json` adopts these identities. Each
build checks 32 typed forms, 252 prefix neighbors, 32 trailing sequences,
28 unchanged original baseline observations and 312 runtime whitelist refusals.
The transport checks six producer-source identities, SDK/build pins, exact
query identity, one seeded nonempty loop, bounded output/time, typed expressions,
family-specific architectural writes, virtual bindings and artifact stability.
Fifteen transport tests pass, including all 32 forms on both target labels.

Address-32 execution tests the low 32 count bits, truncates each starting
source/destination effective address, and zero-extends participating count/index
updates after an actual iteration. Index arithmetic wraps at 32 bits; element
byte lanes remain contiguous in the 64-bit linear address space. A fresh qword
probe at 0xfffffffc reads through 0x100000003 and then advances ESI to 4.
Both inspected CPUs corroborate this element/index distinction.

Zero-count upper-lane behavior requires a vendor premise. On the tested
AuthenticAMD Ryzen 9 7950X, all 28 exact forms preserve count/index/accumulator
upper lanes when low ECX is zero. On the inspected GenuineIntel Core 5 220H,
zero-count RCX clears its upper half; MOVS also clears both indices, STOS clears
RDI, while LODS/CMPS/SCAS preserve their index upper halves. These are finite
hardware observations, not a universal vendor proof. The AMD manual-derived
contract and AMD observations support v15's selected preservation rule; Intel
behavior is not silently included in that contract.

The manifest binds `vendor: AMD` and the premises
`amd-long-mode-memory-rep` and `address32-zero-count-preserves-upper-lanes`.
Select it with
`Config::with_amd_memory_repeated_strings_address_size(flags, rep_address)` or:

```sh
ARIADNE_BAP_SOURCE_EXTENSION_MODE=amd-memory-repeated-strings-address-size
ARIADNE_BAP_SOURCE_EXTENSION=target/selected-advanced-flags/runtime
ARIADNE_BAP_REP_ADDRESS_SOURCE_EXTENSION=target/selected-rep-address/runtime
```

The older LODS directory must be absent in this mode; the new bundle supplies
those four forms itself. Older configuration builders clear the new selection.
For every selected 67 form, semantic evidence records
`amd-address32-zero-count-semantics-premise`. The dump's AMD64 architecture or
Windows/Linux target label does not prove its CPU vendor. Callers explicitly
select the conditional AMD semantic contract; no captured past execution is inferred.

The independent oracle passes 178,080 full represented-register/flag/memory
comparisons across 32 forms and both target labels, plus 15 refused runtime
neighbors. Fifteen portable oracle controls reject wrong count widths,
addresses, casts, termination and unrelated-state changes. Small optional C
hardware probes are retained as test inputs; binaries and results remain
ignored run products. Their 168 AMD observations and 168 Intel contrasts
corroborate the count/index boundary separately from the numeric BIL oracle.

The local v15 capture matrix passes 448 instances: 56 tuples across two OS
fixtures, zero/nonzero low counts and both DF values. Address-32 cases initialize
nonzero high count/index bits and assert the exact AMD premise. Roots/seeds,
uses, possible writes, empty definite writes, entry/REP origins, unknown
iteration-dependent addresses and investigation binding all pass. The three
portable API/configuration controls pass, including early proof refusal.

The current native source/control payload contains 25 files with SHA256
`ac080543a2951b6606e87d63d3085f6f5df9d2c829553182443b970cfdae2440`.
Automatic approval review rejected this changed v15 payload because the earlier
approval covered the previous handoff. Specific approval has been requested.
The remaining gate is a fresh current core build, 125 direct plus 216 framed
refusal controls, and the 448-instance native parity matrix. These results are
unexercised; older helpers or the local-only matrix supply no replacement credit.
The [pending native stage](../../.agents/plans/amd64-operation-coverage.md#native-amd-address-size-qualification-pending-approval)
records the exact payload and commands.

### 10.8 Expanded source-to-consumer bindings: C3/C4

2026-10-23: a separate v3 registry expands the canonical memory-REP domain to
56 exact byte/environment points. Seven family/condition forms combine four
element widths and two address widths. The environment binds AMD vendor,
long mode, flat default segments and finite normal completion; the prefix
policy is optional 67, optional 66, repeat, optional 48, opcode. Other orders,
redundant/segment prefixes, other vendors, I/O and fault/restart domains remain
explicitly outside this finite scope and open in the overall program.

| Plain dependency profile | Supported points | Unsupported points |
| --- | ---: | ---: |
| v12 | 3 | 53 |
| v13 | 24 | 32 |
| v14 | 28 | 28 |
| v15, AMD premise | 56 | 0 |

The checker replays 516 exact PDF/bounding-box source-cell anchors for opcode,
repeat, operand/address size and REX rules. It binds packaged BAP, the frozen
v14 LODS producer and the new AMD address-size producer to their exact code,
manifest, executable, bytes, environment and typed BIL. Fresh execution yields
111 profile observations: 75 packaged-producer queries, four v14 LODS queries
and 32 new-producer queries, representing 60 distinct producer/byte pairs.
The Rust observer checks actual supplied BIL admission across all four profiles.
Forty-eight portable controls pass, including holes, overlaps, wrong source
cells, stale artifacts, rehashed vendor/premise changes and exact JSON-type
identity and stale per-volume recovery helpers in both registries. Missing observations or a skipped Rust observer keep binding validation
false. Fresh `--require-bindings --require-implementation` passes for this
registry's v15 plain-dependency domain; older profiles remain incomplete in
that larger domain as the table shows.

The original 24-point v2 contract is unchanged. Only its current implementation
source digests were resealed; a fresh three-row BAP/oracle/Rust campaign and
`--require-bindings` pass with the same 3 supported/21 unsupported result.
After the historical-gap pass, the v3 registry binds 61 implementation sources
and repeats the complete fresh producer/source-cell/Rust observer campaign.
Its binding digest is
`f74166126ea43d855c7e6cafae61186fda365cd0d6bce41885294c9587c188db`.
The v3 finite domain establishes no complete vendor denominator or full symbolic
binding: `sourceComplete`, `vendorFullDenominator` and `fullAmd64Coverage` remain
false, and `candidateFullDomainBindings` remains zero. All 10,569 candidate
full-domain bindings remain open.

### 10.9 Current continuation checks

2026-10-23: the frozen v15 source passes 472 default Rust tests with 159 ignored,
64 core-only tests with 22 ignored, strict all-feature/all-target Clippy,
formatting and layout. The existing read-only MirrorRust snapshot is used;
core-only normal dependencies remain empty. All 107 BAP-side Python controls
and 327 tooling controls pass. Four current optimized loop mutants are detected
at the intended assertions after passing exact unchanged controls; restored
sources, unchanged observers and the final source inventory are verified.
Native v15 qualification is pending the specific source-handoff approval above.
Earlier R1 results retain their recorded source scope.

The subsequent historical-gap continuation changes Python extraction and
binding provenance, with no Rust behavior change. Its fresh checks pass all
145 BAP Python controls, 328 tooling controls, the three-volume reconstruction
and five-volume region checks, both actual BAP/Rust binding campaigns, Rust
layout and documentation links. The Rust suite and mutation counts in the
preceding paragraph belong to the recorded v15 source campaign; this
continuation reruns the two affected Rust binding observers.
