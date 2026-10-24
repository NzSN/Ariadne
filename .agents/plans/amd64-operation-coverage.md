# AMD64 operation coverage program

## Context and follow-up

**Current checkpoint: fixed-64 near-branch hypothesis accepted, 2026-10-24.**
The [selected contract](../../docs/Ariadne/amd64-coverage-design.md#1025-selected-fixed64-near-branch-hypothesis)
considers fixed-64 near branches and excludes their possible operand-16
alternatives. Its checker projection remains pending. Other smaller operands
and address-size rules remain required. The preceding
[native-64 execution](../../docs/Ariadne/amd64-coverage-design.md#1024-h64-source-projection-and-native64-inventories)
implements the source-checked non-64-only MOVD exclusion and native-64
size/LOCK/REP inventories. Smaller operands, address-32 forms and legacy
encodings valid in 64-bit mode remain required. The
user subsequently requested a concrete P2 completion task list and continued
execution until an actual external blocker. Follow the
[P2 completion contract](../../docs/Ariadne/amd64-coverage-design.md#1022-p2-completion-task-execution); unfinished implementation
and unreviewed source are work, not evidence of an external blocker. The
[P1 completion](../../docs/Ariadne/amd64-coverage-design.md#1020-p1-source-selection-and-structural-migration-completed)
now accepts the exact five-edition source pool and closes its structural
migration/adoption gate. The subsequent
[P2 execution](../../docs/Ariadne/amd64-coverage-design.md#1021-p2-clause-and-reference-execution)
adds architectural clauses, current cell/reference dispositions and accepted
source/section review objects. Detailed P2 completeness and P3 legal domains
remain open.
The
[per-form mapping continuation](../../docs/Ariadne/amd64-coverage-design.md#1014-per-form-source-rule-mapping-resumed)
completes the five outstanding dependencies and the affected source,
binding and register-native refresh. The
[memory-native continuation](../../docs/Ariadne/amd64-coverage-design.md#1015-memory-mov8-native-consumer-continuation)
also completes its finite address-64 consumer/address-32 refusal gate. Wider
source, legal-domain and architectural coverage remain open. The
[publisher entry review](../../docs/Ariadne/amd64-coverage-design.md#1016-publisher-migration-entry-review)
now completes the P1 structural migration subgate; it grants no corpus or
semantic adoption. The
[conversion constraint slice](../../docs/Ariadne/amd64-coverage-design.md#1017-conversion-family-source-constraints)
now validates selected source facts for four base/X variants while retaining
conflicts and withholding admission. The
[remaining paired-family continuation](../../docs/Ariadne/amd64-coverage-design.md#1018-remaining-paired-family-source-constraints)
resumes selected predecessor/publisher constraint review for GF2 inverse affine,
MOVD and scalar negative multiply-add. The
[section-5 execution](../../docs/Ariadne/amd64-coverage-design.md#1019-section-5-execution-and-current-exit-gates)
adds derived migration dispositions, cross-volume displacement rules and a
frame-path output-budget repair; full-stage exits remain unmet. The
[stopped checkpoint](../../CHECKPOINTS.md#2026-10-24--amd64-constraint-and-mov8-continuation-stopped-for-publication)
records the previous stop and its then-unapplied five-rule per-form mapping.
The current resume instruction supersedes that stop; prior results retain their
pre-adjustment source identities.
The previous recovery remains complete for its finite scope. The
[recovery checkpoint](../../CHECKPOINTS.md#2026-10-23--pinned-tool-recovery-and-current-source-replay)
records exact PDF/producer recovery, full source/authority replay and the
reviewed helper-build migration v1. The [migration record](../../docs/Ariadne/amd64-coverage-design.md#1012-helper-build-migration-v1-and-renewed-finite-qualification)
qualifies refreshed v2/v3/MOV8 bindings and N's finite native gate. Seven bounded
adjudications and 33 checked table relations retain the wider source/constraint
limits. The earlier resume,
stopped entry and dated results retain their original scopes.

**Status.** Resumed at the user's request on 2026-10-23 from the
[stopped checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request).
The [resume record](../../CHECKPOINTS.md#2026-10-23--amd64-guard-replay-and-composed-fixture-resumed)
records source fixes, the approved native continuation and remaining gates. Instruction
inventory, broader semantics and advanced producer integration remain partial.
The [Basic candidate follow-up](../../CHECKPOINTS.md#2026-10-23--current-basic-v9-candidate-compatibility-checked)
passes three native tests under an isolated candidate pin; production adoption
and historical identity remain separate.
The [plain REP and accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting)
adds a separately selected v12 three-form dependency contract and executable
full-coverage obligations. The [source/domain findings](../../docs/Ariadne/amd64-coverage-design.md#101-source-corpus-execution-c1)
adds a five-volume candidate corpus, historical-gap accounting and finite v2/v3
legal-domain/binding registries; their full C1–C4 exits remain open. S4/Q0 remain partial.
The [memory-string successors](../../docs/Ariadne/amd64-coverage-design.md#104-default-address-memory-rep-execution-r1)
add finite v13/v14 plain dependency scopes with separate source and qualification
gates; the R1 source boundary passes 416 native parity instances and 259 refusal
controls. The AMD-specific v15 successor adds canonical address-32 forms. Its current
finite native gate now passes locally with recovered producers and the reviewed
helper-build migration; no private-source handoff was needed.
Full coverage is the target, not an achieved result. Implementation proceeds on both
machine-instruction semantics and Windows unwind operations. A representative
family survey is not an exhaustive instruction-form inventory.
The [historical-gap checkpoint](../../CHECKPOINTS.md#2026-10-23--historical-amd-manual-gap-backlog-accounted-for)
records all 2,657 assigned records with seven explicit source conflicts. The
remaining execution plan below starts
from published `08dcab9` and defines the next source, domain and implementation
deliveries. It is proposed work; preparing it adds no qualification result.

**Why this document exists.** The [BAP semantic design](../../docs/Ariadne/bap-analysis-core-design.md#amd64-operation-coverage-program)
and [frame investigation design](../../docs/Ariadne/investigation-design.md#amd64-unwind-coverage-program)
currently expose finite admission and unwind profiles. The user requested a
plan followed by implementation to close operation coverage across AMD64.
The [coverage completion design](../../docs/Ariadne/amd64-coverage-design.md)
owns the source, legal-domain, authoritative-binding and remaining REP
architecture and its dated finite implementation findings; this plan owns stage
execution.

**What this document establishes.** One execution ledger coordinates two
separately testable tracks. It defines the meaning of support, implementation
order, compatibility boundaries and the gates required before claiming full
coverage. Existing designs remain the canonical contract owners.

**Where to go next.** Start with the remaining execution plan below, then read the [plain REP/accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting),
[coverage completion design](../../docs/Ariadne/amd64-coverage-design.md),
[test matrix](../../tests/README.md),
[BAP trust boundary](../../docs/Ariadne/semantic-assurance.md), and the two design
sections above before implementing a stage.

**What remains unresolved.** The pinned BAP producer has missing lifts; the
current projection excludes architectural state and control constructs. Windows
unwind metadata versions and exceptional transitions also need separate work.
No unknown, unexercised or merely decoded operation counts as semantic coverage.

## Remaining coverage execution plan

**Execution status: resumed; full AMD64 coverage remains incomplete.** The 2026-10-24 mapping continuation
closes the earlier missing dependencies; finite memory-native consumption and
selected source reviews have their own later entries below. The recovered pinned PDF runtime now passes full source-ledger and
authority extraction/check. Table decisions and MOV8 framing have additional
rejection controls. The reviewed helper-build migration now passes fresh
source/BAP/oracle/Rust binding campaigns and N's native parity/compatibility
gates. Broader source, domain and consumer completion remains open.
The [current P1 source-selection exit](#p1-source-selection-completed-2026-10-24)
is now complete; the older whole-required-source gate below is superseded.
The [resume record](#resumed-source-review-and-local-native-checks) separates
completed checks from the remaining P0–P8/N exits.

**Planning baseline: 2026-10-23, `08dcab92aabb1695c4f2b6748bb23f1ec822d72e`.**
This continuation addresses the open instruction-coverage items from the
[current checkpoint](../../CHECKPOINTS.md#2026-10-23--historical-amd-manual-gap-backlog-accounted-for).
The [canonical design](../../docs/Ariadne/amd64-coverage-design.md) owns the
contracts. The [HTML plan](../chatdocs/ariadne-amd64-coverage-remaining-plan-20261023/index.html)
presents this section. Windows unwind work keeps its separate stage ledger.

The first delivery is a checked source-obligation ledger. The main promotion
sequence is **P0 → P1 → P2 → P3 → P4 → P5/P6/P7 → P8**. The current native
qualification **N** runs independently of the source audit and joins P8.
Pilot implementation can start once its own source inputs are reviewed; it
does not require waiting for every family. Full-stage completion requires the
whole declared scope. No calendar estimate for full AMD64 is justified before
P0–P3 expose the complete constraint and implementation worklists.

### Starting counters and completion meanings

| Counter | Current state | What must change |
| --- | --- | --- |
| Historical extraction records | 2,657 assigned; zero unassigned | Preserve all original IDs and objects. This completed counter stays separate from source completeness. |
| Source conflicts | Seven records/five issues have checked bounded publisher adjudications; original raw records remain preserved | Complete the separate corpus-identity/adoption and scope review. |
| Cross-page table relations | All 33 checked: 26 local-row series and seven independent tables | Preserve the checked ownership and original identities while expanding constraint extraction. |
| Source scope and constraints | Five documents/4,128 pages/eleven required region clauses accounted; constraints and supplementary scope incomplete | Establish authority, enumerate every selected constraint and resolve its references. Page counts alone cannot close this work. |
| Full symbolic-domain bindings | 10,569 candidates; zero complete authoritative candidate bindings | Reconcile whole legal domains, retaining AMD forms absent from XED and justified exclusions. |
| Finite memory-REP support | 56 AMD byte/environment points and 111 profile observations | Preserve this qualified finite domain while adding independently checked domains and consumer contracts. |
| Current v15 native gate | Complete for the migrated finite environment: current core audit, 341 refusal controls, 448 parity instances and compatibility pass | Preserve these identities; wider domains/consumers retain separate P6/P7/P8 gates. |

### P0 — Baseline and obligations

**Work.** Freeze the intended AMD long-mode scope, selected publications,
extension/mode/environment axes and required consumer set. Use the existing
application and privileged/system scope; record the 24 extension-family
discovery candidates and their supplementary-source decisions. Intel-specific
forms need separate vendor dispositions. Scope exclusions must be justified
before constructing domains, and later changes must be versioned visibly.

Create a stable obligation graph linking source cells, conflicts, table pairs,
constraints, legal forms, XED relations, bindings and required validation. Seed
it with all seven conflict records and all 33 table candidates. Distinguish
`accounted`, `adjudicated`, `implemented` and `validated`; retain unresolved
constraints even when their containing text is classified as non-encoding.

**Files.** Extend the existing source/geometry inputs. Proposed new files are
`tools/amd64_source_obligations.py`, its tooling tests and reviewed decision
inputs under `tests/bap/fixtures/amd64-semantics/`. These files now exist;
the final full-source extraction/check now passes after exact runtime recovery. Keep generated ledgers and checker results under
ignored `target/`; maintain schemas, source-decision inputs and small fixtures.

**Exit.** Every initial obligation has a stable ID, exact source references,
dependencies, an explicit current state and an executable check to close it.
Deletion, duplicate identity, wrong ownership and source/hash drift controls
fail. A generated ledger cannot grant itself acceptance through stored flags.

### P1 — Source authority and structural conflicts

**Work.** Recheck publisher availability for the pinned Vol4/5 revisions;
the recorded HTTP failures are historical. Establish exact official-byte
identity, or prepare a separately pinned replacement corpus and review its
PDF/text/geometry/outline/row/constraint/scope migration. Preserve every old
lock. Local structural work can proceed while source adoption is unresolved.

Adjudicate these five issues using authoritative AMD revisions, errata or
explicit source rules. Preserve the raw literals and all seven old-gap IDs.

| Vol4 issue | PDF page | Original gap ordinals |
| --- | ---: | --- |
| VADDPD contains `xmmVGETEXPPD2,` and a dependent operand continuation | 78 | 1, 2 |
| `VMOVMSKB` rows disagree with PMOVMSKB/VPMOVMSKB section headings | 612 | 542, 543 |
| VPMOVZXWD has literal malformed field `X.1323r33111.` | 645 | 574 |
| `SHA256MSG1` row appears in the SHA256MSG2 section | 807 | 744 |
| `PMADCSWD` row appears in the VPMADCSWD section | 1350 | 1603 |

Store adjudication separately from the immutable transcription. Heading
similarity, XED/LLVM agreement or hardware accepting one witness cannot alone
establish an intended manual correction or a complete AMD legal domain.

For every cross-page pair, compare section headings, column meanings,
intervening material, explicit continuation markers and complete local rows.
Vol4 includes apparent semantic-table-to-encoding-table transitions at PDF
138→139, 142→143, 487→488 and 903→904; check them as independent-table
candidates. Do not invent a continuation to eliminate a counter.

**Exit.** All seven conflict records have checked adjudications and all 33
relations have justified non-unresolved outcomes. Accepted corpus identities
and scope migration are independently checked. A missing authoritative answer
keeps that obligation open while other records continue. This exit closes
structural/source-authority work; P2 still owns constraint completeness.
The [2026-10-24 completion](#p1-source-selection-completed-2026-10-24) records
the accepted editions, marking-variant rule and fresh executable exit.

### P2 — Architectural constraints

**Work.** Add typed source-constraint and cross-reference extraction. Current
`region_accounting()` only enumerates pages; source cells have unresolved
footnote parsing. Replace that limitation with explicit obligations for:

1. Prefix precedence/order/repetition, operand/address size, REX/high-byte
   registers and ModRM/SIB/displacement/immediate restrictions.
2. VEX/EVEX/XOP fields, reserved combinations, CPUID/mode/privilege/OS-state
   applicability and feature-dependent aliases.
3. Exception/outcome conditions, memory/order premises, diagram-derived
   effects and other selected architectural constraints.
4. Footnotes, cross-volume references, opcode maps and supplementary sources.

**Files.** Proposed `tools/amd64_source_constraints.py` and tests; source-rule
inputs under `tests/bap/fixtures/amd64-semantics/`; integrate with the corpus,
geometry and obligation tools. Every typed clause retains exact source cells,
its applicable owner/domain and referenced rules. Review the clause inventory
independently from the parser's own output.

**Exit.** Every selected region and clause has a checked disposition, all
required references resolve, and no required constraint remains unparsed.
Omitted notes, swapped footnote targets, mislabeled diagrams, stale ownership
and unknown clauses classified as harmless must fail. Reproduce the pinned
corpus before `check-products --require-all`, then reconstruct geometry and
regions. C1/C2 completeness requires this clause-level result as well as P1.

### P3 — Legal domains and XED reconciliation

**Work.** Introduce a general domain/relationship path alongside the frozen
v2/v3 REP registries. The existing enumerator handles finite literal prefixes,
opcodes and independent fields; it has no general dependent ModRM/SIB grammar.
Proposed modules are `tools/amd64_domains.py` and
`tools/amd64_reconciliation.py`, with schema and executable tests.

Implement grammar in increasing complexity: finite prefix/opcode/register
fields; dependent ModRM/SIB/address/displacement/immediate fields; then
VEX/EVEX/XOP and applicability/alias predicates. Exhaustively enumerate small
domains. For larger domains, add a restricted symbolic checker with explicit
budgets and independently replayable witnesses/counterexamples. Unsupported
constraints, timeouts and solver unknowns remain unresolved.
Witness replay checks satisfying cases; it cannot establish that no hole or
overlap exists. Bind each symbolic query to the grammar/translation, solver,
compiler and configuration identities and execute it freshly. Require checked
UNSAT certificates where supported, or explicitly review and state the trusted
solver boundary. A self-reported absence of counterexamples cannot supply
unqualified totality evidence.

Reconcile in both directions: each frozen XED candidate gets a source-backed
relation, and every selected AMD legal form gets an obligation even when XED
has no matching record. Relations may split, merge or alias domains. Keep
encoding membership, architectural applicability and profile admission separate.
Each candidate region needs an explicit `in-scope legal`, `justified scope/vendor
exclusion` or `unresolved` disposition. Absence from the current manual-derived
domain is unresolved unless authoritative evidence establishes exclusion or
invalidity. Missing source coverage cannot shrink the denominator.

**First vertical slice: source/projection qualified.** Register-only byte MOV
with opcodes 88/8A, ModRM.MOD=3 and no prefix or one REX from 40/41/44/45
has 640 byte points: two opcodes × (64 no-REX + four × 64 REX combinations).
The reviewed Vol3 source pack checks 292 anchors/nine clauses. Fresh BAP/LLVM
observations and the Rust byte-origin observer exercise operand direction,
extended registers, high-byte/REX low-byte aliases and partial writes. Native
consumer qualification remains a separate active gate. Neither XED candidate
has a complete full-domain binding. Preserve all other prefix regions as
obligations. The active successor adds dependent memory addressing; a
source-reviewed feature-alias slice follows separately.

**Exit.** Source/domain membership, complete reconciliation and overlap/alias
rules pass independent checks across the declared scope. Domain narrowing,
omitted AMD-only forms, lost ModRM/REX combinations and unaccounted aliases
produce concrete failures or explicit unknowns. Passing the first slice earns
only that slice's result; full P3 requires the entire legal denominator.

### P4 — Authoritative bindings and coverage reports

**Work.** Add a versioned general registry and report path without changing
candidate-only `coverage/v1` or the finite v2/v3 contracts. The current
`amd64_coverage.py` deliberately reports zero authoritative full-domain
bindings; do not replace that with a name-association count. Reuse strict
identity/partition checking from `amd64_legal_forms.py`, but generalize rule
dispatch, source derivation and required consumer/outcome capabilities.

Each binding connects a legal domain to a named semantic contract, exact
producer/BIL query, implementation rule, profile/consumer set and current
validation obligations. Require `S ∪ U ∪ X = D` with disjoint disposition
partitions and binding-domain inclusion: S is an implemented named contract,
U is explicitly unsupported and X is unresolved. A contract may include both
normal and possible fault outcomes; those architectural alternatives are not
the S/U/X partitions. Complete implementation separately requires
`S = D` and empty unsupported/unresolved partitions. Architectural aliases and
exceptions count as supported only through implemented contracts.

**Exit.** Every required domain has checked total accounting, and every
supported partition has actual current producer and Rust/native observations.
Replaying satisfying examples supplements domain checking; it cannot establish
totality. Reject wrong bytes/extent/environment/VA/snapshot, stale source or
producer, missing consumer capability, unjustified overlaps and solver unknown
promoted to success. Report source coverage, authoritative domain bindings,
implementation support and exercised validation separately.

### N — Current v15 native qualification

**Completed finite gate, 2026-10-23.** The [helper-build migration](../../docs/Ariadne/amd64-coverage-design.md#1012-helper-build-migration-v1-and-renewed-finite-qualification)
uses exact recovered producers and separately reviewed current-source BAP/LLVM
helper builds. A fresh local core passes fourteen native-source and seventeen
SDK/compiler/model/engine identity checks, 341 refusal controls, 448 native/Rust
parity instances and all named compatibility regressions. The final six-test
suite uses release optimization with unchanged cases/assertions/work limits.
The earlier [remote handoff proposal](#native-amd-address-size-qualification-pending-approval)
retains its historical boundary; recovery supplied the local alternative and
no private-source transfer occurred.

**Exit.** Current-source native and local behavior match across the finite
v15 domain, with final artifact/source stability checked. Close this baseline
before promoting native REP proof-policy changes. N closes the existing finite
gate; wider REP domains and consumers still have P6/P7 obligations.

### P5 — Instruction-family implementation

Generate the implementation queue from P3/P4 gaps, distinguishing missing BAP
lifts, transport types/resources, architectural state, projection/control and
consumer support. Start the queue early; its complete acceptance depends on
the completed denominator. Prioritize shared capabilities: scalar/control/flags,
atomic and ordering behavior, x87/MMX aliases and FP state, wider SIMD/masks,
then system/privileged/exceptional and remaining extension families. Retain
every discovered family even when implementation is difficult.

**Files.** Pinned producers under `native/bap/source-coverage/`; transport/state
and effects in `src/bap/{ast,admission,registers,projection}.rs`; control and
matching native/checker modules as required. Wider vectors require typed state
and alias contracts; raising a byte/tree limit alone cannot provide them.
BAP supplies actual production semantics; LLVM remains decode/control reference.

**Exit per family.** Source legality → actual BAP BIL → named effect/control
contract → required consumers → exact-byte and independent behavioral tests →
current native parity are all connected. Missing lifts and generic unknown
effects remain implementation gaps. An implemented conservative contract may
retain justified environmental unknowns, with its invariant and limits tested.

### P6 — Wider REP and fault/I/O outcomes

Implement separately versioned source-derived domains for prefix ordering,
redundancy, segment selection and ignored/reserved combinations while freezing
v12–v15. Preserve zero-iteration origins, weak writes, lane rules, overlap,
iteration-dependent addresses, pointer wrapping and explicit exhaustion.

Before fault-sensitive or I/O admission, extend the outcome contract to normal
completion, possible completed-iteration prefixes, faults and restart boundaries.
Represent external I/O state and ordering explicitly. Coordinate transport,
effects, investigation/report consumers and native replay; a normal-completion
oracle cannot qualify partial effects. The current narrow terminal-control
contract cannot simply be relabeled as general REP restart support.

**Exit.** Each required prefix/outcome domain passes legal-domain checks,
fresh BAP and independent behavior checks, transport/refusal controls and
current Rust/native parity. Fault and I/O domains need dedicated observers and
fixtures that exercise partial completion and external side effects. Unsupported
domains remain visible until their own gates pass.

### P7 — Consumer contracts and proof admission

Freeze the shared loop/outcome premises with P6, then implement guard admission,
captured targets, memory refinement and composition as independently versioned
capabilities. Start with conservative whole-loop transfers: preserve entry
origins, havoc every possibly written architectural/virtual binding, and treat
possibly reached stores as barriers unless a checked footprint excludes them.
Keep structural CFG edges and snapshot/query identity throughout.

**Files and models.** `src/bap/{guard_admission,target_resolution,refinement,composition,core_protocol}.rs`
and matching native code; the owning predicate-admission, target-resolution,
loop-target-closure, memory-refinement and guarded-target TLA+ models. Update
input/effects/core models when their contracts change. The retired instruction-step
ISA proof track stays retired.

**Exit per consumer.** Model checks, model-derived replay, actual Rust/native
parity and saved-proof tampering pass under the new profile/receipt generation.
Direct and framed entry points reject unsupported profiles, including empty
and all-null domains, lookalike tokens and overall/site identity disagreement.
Later-iteration writes, zero count and partial outcomes cannot inherit a
first-iteration or normal-only proof. Whole-loop memory/target soundness must
be exercised by behavioral mutations with unchanged observers.

### P8 — Integrated full-coverage gate

Freeze the final scope, domains, source closure, producers, profiles, consumers
and workload partitions. Run applicable affected tests and root formatting,
default/core-only tests, strict Clippy and layout checks. Execute owning
analysis-model checks, generated replay, compiled mutations, actual producer
and native comparisons, and the declared capture/compatibility/resource suites.
Keep each replay/mutation build in its own ignored directory.

Require a passing unchanged control before mutant credit; a changed SUT must
compile and fail the intended unchanged observer. Recheck restored source,
observer and helper identities. Missing prerequisites, skipped/ignored tests,
solver unknowns, stale reports, timeouts and compilation failures supply no
positive qualification credit. Maintain executable tests and small inputs;
keep generated campaigns and acceptance outputs outside maintained source.

**Exit.** C1/C2 source and constraint completeness, C3 domain/reconciliation,
C4 bindings, all required P5/P6/P7 capabilities and current N/P8 validation pass
for the frozen scope. Required domains have no unsupported or unresolved
implementation partitions. Only then may scoped full AMD64 coverage become
true. The claim remains conditional on trusted BAP lifting, reviewed
grammar/solver boundaries and stated environmental premises; it does not
establish a universal ISA or Rust proof.

### Delivery order, parallel work and checkpoints

1. **Current source delivery:** complete the remaining P0/P1 corpus-identity,
   migration/adoption and extension-scope work. The ledger, seven bounded
   adjudications and 33 table relations already pass their full source replay.
2. **Current constraint/domain delivery:** broaden P2 prefix/size/register and
   addressing constraints; follow the qualified register-byte MOV pilot with
   dependent memory-address forms and its separate native-consumer gate.
   Finish general constraint/reconciliation coverage iteratively by family.
3. **Current integration:** expand the P4 binding/report path while preserving
   existing schemas and proving partial pilots cannot increment complete
   candidate counts.
4. **Parallel execution:** a source lane owns corpus/constraint tooling; a
   domain lane owns grammar/reconciliation/bindings; runtime lanes own producer,
   state, REP and consumers in disjoint modules. N uses an isolated native build.
   Coordinate shared outcome/schema changes before integration and serialize
   native source freezes and final qualification.
5. **Every completed slice:** preserve exact scope, executable regressions and
   counter deltas; update the canonical design, this ledger and `CHECKPOINTS.md`.
   Re-run source-bound binding campaigns after relevant source changes.
   Publication follows the user's commit/push instruction for that delivery.

The plan can be reviewed and implemented in these bounded deliveries. Seven
adjudicated conflicts or a passing 640-point pilot must never be reported as
completion of the entire source or AMD64 domain.

### Resumed source review and local native checks

2026-10-23: resumed from `43588f9`; the [canonical validation record](../../docs/Ariadne/amd64-coverage-design.md#1010-resumed-source-review-and-validation)
owns implementation details, source review and check results. The following
bullets describe the initial resume boundary; approved recovery and migration
below supersede its missing-tool and stale-binding clauses.

- P0/P1 integration computes authority corrections afresh from publisher
  PDFs, preserves all original conflict objects and refuses serialized pass
  reports. Independent visual review corroborates all five source issues.
  Full pinned replay and ledger extraction/check remain unavailable because
  the exact Poppler/MuPDF/Python/native-library closure is missing.
- Table review adds an explicit distinction between separately complete EVEX
  element-width tables and local row series. These source decisions do not
  establish complete architectural constraint parsing.
- P2/P3 retains the 640-point MOV8 pilot and all 10,994 XED records, including
  10,569 candidate obligations. P4 now rejects malformed numeric completion
  fields and missing/extra producer frames. Zero complete candidate bindings
  remain; v2/v3/MOV8 source identities have not been resealed.
- The verified SDK on this host supports a fresh local native core build.
  Fourteen source hashes and seventeen SDK/compiler/model/engine fields pass
  audit, and all 341 refusal controls pass. Two reproduced REP-address bundles
  agree with one another but differ from the original v15 pin; the available
  advanced bundle also differs from its pin. Native parity and compatibility
  tests stop at pin admission. N remains incomplete; no source transfer occurs.
- The root lock corrects only MirrorRust package metadata to the actual
  `1.0.0` source. The existing read-only I5b dependency snapshot supports
  passing default/core-only Rust tests, strict Clippy and formatting. The
  sibling checkout and its edits remain intact.

**Approved recovery follow-up.** All three PDF executables and 71 unique
libraries now match their existing pins. Thirteen fresh full-source campaign
stages pass, preserving all 2,657 historical records and checking seven bounded
adjudications plus all 33 table relations. The MOV8 source pack replays 292
anchors/nine clauses. P1/C2/global source completeness remain false, with 41
unresolved graph nodes; see the canonical recovery record above.

**Helper-build migration v1 completed.** Exact advanced/LODS/REP-address
producer manifests and executables are recovered. The two historical helper
binaries remain unrecovered; current-source BAP/LLVM builds pass an explicitly
versioned independent review and all three fresh binding campaigns. Old
identities remain at immutable `43588f9` and in the canonical migration record.
The tested registry inputs are promoted byte-for-byte and pass normal-filesystem
checks afterward. Domains/contracts/profiles, BAP runtime and producer locks
remain unchanged. N passes all 448 parity instances, named compatibility and
341 refusal controls with the same audited core and migrated helper environment.

**Next executable boundary.** Continue the unresolved corpus-adoption/scope and
P2 constraint work, then widen the P3/P4 domain/consumer worklists. MOV8 native
consumer validation, broader REP policies and P5–P8 implementation remain open.
Finite source, binding and native results do not close full AMD64 coverage.

### Per-form source-rule mapping resumed: 2026-10-24

Resumed from `8317f4d` under the user's new instruction. Both memory-MOV8 forms
now explicitly require `prefix-group-order`, `legacy-prefix-byte-groups`,
`rex-placement-count`, `instruction-length-limit` and `operand-size-override`.
The validator enforces all five dependencies; a regression removes each rule
from each form and checks rejection. The encoding/environment domain remains
byte-for-byte equivalent as 5,760 points, with no production admission change.

Fresh source-ledger extraction and independent check pass with all 2,657
historical gaps and seven adjudications preserved. Six fresh binding/reconciliation
steps pass, including the expected incomplete-gate exit. Register and memory
campaigns exercise 1,280 and 11,520 observations respectively. The two affected
candidate registries are promoted byte-for-byte; maintained-path checks pass,
and both reject pre-adjustment observations. Unaffected v2/v3 source seals stay
unchanged.

The register-native gate passes all four named release tests again after
promotion: 1,280 instances/twenty batches, host/native refusal controls and the
address-32 bad-lift barriers. Its 755 current source bindings, executed test
artifact, helpers and libraries remain stable. Root validation passes 473 default
tests/164 ignored, 64 core-only/22 ignored, strict all-feature/all-target Clippy,
format/layout, 209 focused controls, 460 tooling tests and 145 BAP Python tests.
Disposable products remain under ignored
`target/coverage-20261024/mapping-resume-01/`.

**Next boundary.** Memory-MOV8 native-consumer validation remains separate from
these producer/projection observations. Continue that P3/P4 consumer gate and
the wider source program: 115 corpus-review obligations, ten unresolved
architectural references, 516 unparsed selected cells and complete symbolic
domains remain open. No production prefix policy, source corpus, producer/helper
pin or full-coverage flag changed in this mapping continuation.
See the [canonical continuation](../../docs/Ariadne/amd64-coverage-design.md#1014-per-form-source-rule-mapping-resumed).

### Memory-MOV8 native consumer continuation: 2026-10-24

The user resume implements the separate P3/P4 memory-native gate. Preserve
the producer/projection assessment and its refusal policy. Add test-only native
observers and a source/tool-bound checker with these exits:

1. Independently generate the same 2,880 address-64 and 2,880 address-32 byte
   encodings, including REX/high-byte, ModRM/SIB, displacement and RIP-relative
   alternatives. Keep the finite source/domain denominator unchanged.
2. For both target labels, prepare synthetic minidumps with independent roots,
   a following consumer and RET. Check captured bytes/provenance, normalized
   effects and complete native/Rust observations against independent entry,
   instruction and preserved byte origins. Stores keep old memory origins.
3. Check every address-32 encoding in both target labels: no decoded precise
   instruction, known address, definite write or consumer execution is granted.
   Captured slice seeds never become additional roots.
4. Require exact named-test markers, current source/helper/library identities,
   a stable executed test binary and normal read-only dependency selection.
   Add protocol/lifecycle rejection controls. Generated products stay ignored.

The native gate remains conditional on BAP lifting and reader-normalized effects;
it does not independently prove ISA semantics or reject self-consistent forged
semantics. No runtime admission, memory alias precision, full-domain flag or
production pin changes are authorized by a passing finite observer. The
[canonical contract](../../docs/Ariadne/amd64-coverage-design.md#1015-memory-mov8-native-consumer-continuation)
owns the scope and current outcome.

**Finite gate completed.** The final `memory-native-02` run passes all seven
exact named release tests with stable source/tool/library/input/test-artifact
identities. Its three memory tests independently enumerate 2,880 encodings per
address size, execute 5,760 supported instances in ninety synthetic minidump
batches and stop 5,760 address-32 instances in ninety further batches. Loads
preserve the other seven destination bytes; stores preserve prior memory origins.
Actual prepared target identities, roots and seeds are checked for both labels.
The four existing register/barrier tests pass in the same freeze, including
1,280 register instances, structural refusals and the real bad-lift guards.

The portable domain test, all 24 checker/lifecycle controls, 474 default Rust
tests/166 ignored, 64 core-only/22 ignored, 467 tooling and 145 BAP Python tests,
strict all-feature/all-target Clippy, formatting/layout and navigation pass.
All four producer/projection source seals remain current and unchanged in this
consumer extension. No production projection or native helper source changes.
The first native run remains an earlier test-source result; the final run adds
explicit prepared target/root/seed checks. Disposable output stays under ignored
`target/coverage-20261024/memory-native-02/` and `memory-native-checks-01/`.

**Next:** corpus adoption/scope and the ten unresolved architectural references,
516 unparsed cells and wider domains/consumers remain open. Passing this
synthetic finite consumer gate does not close any full symbolic candidate,
repair/admit address-32 production behavior or establish real execution history.

### Publisher migration entry review: 2026-10-24

The next user instruction starts P1 source-corpus review after the finite
consumer gate. Recheck current publisher bytes, then independently map every
added/removed instruction-entry record to actual predecessor/replacement source
sections. Five prior-family heading changes and genuinely additional sections
must remain distinct; mnemonic resemblance is not semantic equivalence.

Maintain reviewed title/extent links and small actual source inputs, not saved
review outputs. A fresh checker must reconstruct the seven predecessor/
publisher PDFs, retain all 2,657 historical gap objects and all 115 original
obligations, bind every section's raw text/geometry and normalized rows, and
reject missing/duplicate/wrong-owner links or a claimed adoption/semantic pass.
Full-text/constraint changes and the Vol5 source-status conflict remain open
unless separately established. A complete structural entry map is a P1
subgate, not corpus adoption or P2 legality/constraint completion.
See the [canonical review contract](../../docs/Ariadne/amd64-coverage-design.md#1016-publisher-migration-entry-review).

**Completed structural subgate.** Both live publisher downloads return HTTP 200
and match their existing exact PDF pins. Fresh extraction and independent
replay reconstruct the seven source PDFs and map all 110 entry records: five
prior-family links (ten added/removed records) and 100 additional sections.
Each selected source section binds its raw pages, word geometry, normalized
row observations and constraint references. All 2,657 historical gap objects
and every original obligation remain intact. Twenty-six focused controls,
477 tooling tests, 145 BAP Python tests and format/layout/navigation pass.
No Rust/native behavior or source/producer pin changes in this source review.

**Still open:** all 115 original semantic/adoption obligations remain unresolved.
Source-family continuity is now explicit, but whole-text/encoding/constraint/
extension review and the Vol5 public-use/confidential marking conflict are not
settled. Source adoption, parsed-constraint, legal-domain and full-coverage flags
remain false. Generated source/review products remain ignored under
`target/coverage-20261024/corpus-review-01/`; older native results keep their own
test/source snapshots and are not requalified by these source-only checks.

### Conversion-family source constraints: 2026-10-24

Continue P1/P2 with the paired PH2PS/PS2PH conversion sections before declaring
them equivalent or adopting a corpus. Add separately reviewed, source-anchored
facts for four base/X variants: element/lane widths, register/memory direction,
broadcast, rounding selectors, denormal/FTZ/DAZ statements, masks, encoding maps
and feature statements. Preserve exact table ownership and new publisher pins.

Contradictory upper-clear ranges, legacy denormal statements and unresolved
embedded-rounding/feature scope must produce explicit blockers. Query kernels
may describe selected source constraints; they never establish IEEE numeric
conversion, legal encoding completeness, runtime admission or must-defs.
Reconstruct the original source-entry review and independently check new source
anchors and outputs. Retain all 115 original obligations and existing source
gaps. The [canonical P2 slice](../../docs/Ariadne/amd64-coverage-design.md#1017-conversion-family-source-constraints)
owns its source/code boundaries and current validation outcome.

**Selected source gate completed.** The candidate conversion pack validates
22 typed source claims against 205 exact physical anchors in the two publisher
Vol4 r3.27 sections. Fresh seven-PDF reconstruction and independent replay pass.
Two source conflicts and two unresolved-scope references remain explicit:
overlapping PH2PS YMM clear/result bits, legacy no-denormal/F16C exception-row
disagreement, PS2PHX embedded-rounding scope and aggregate feature-width scope.
No intended hardware correction is inferred from those discrepancies.

Ten focused tests include 1,024 immediate/MXCSR selector combinations and
source/owner/anchor/boundary rejection controls. All 487 tooling, 145 BAP Python
tests and format/layout/navigation checks pass. Descriptive query results
withhold legal/admission verdicts and vector must-defs. All 115 original
migration obligations, the earlier ten references and 516 unparsed cells remain
unchanged; this candidate pack does not count them as completed. No source lock,
producer/profile/runtime or full-coverage flag changes. Disposable products
remain ignored under `target/coverage-20261024/conversion-constraints-01/`.

**Successor:** the [remaining paired-family continuation](#remaining-paired-family-source-constraints-2026-10-24)
reviews selected constraints in the other three families. Review additional
sections, adjudicate or precisely scope these candidate conflicts, then connect
source-complete constraints to wider legal domains. Corpus adoption and P2
completion remain open; this source-only gate supplies no new native/ISA proof.

### Remaining paired-family source constraints: 2026-10-24

Resumed from `3d33273` under the user's new instruction. Review selected claims
from both exact Vol4 revisions for the remaining GF2 inverse affine, MOVD and
scalar negative multiply-add families. The
[canonical contract](../../docs/Ariadne/amd64-coverage-design.md#1018-remaining-paired-family-source-constraints)
owns the source facts, conflict boundaries and replay commands. Preserve all
115 original migration obligations and the preceding conversion pack.

The separately reviewed input binds 24 selected clauses to 328 physical anchors
(165 predecessor, 163 publisher). Compare selected text explicitly while
retaining complete raw sections through fresh entry review. Changed headings
or table extraction order cannot become whole-family equivalence. Four source
conflicts, two unresolved cross-reference scopes and one unreviewed inverse
table boundary remain explicit. No numerical GF/FMA evaluator, opcode repair,
legal-domain admission or definite vector write follows from these claims.

The system zlib update broke the extractor library pin. Recover the exact
`1:1.3.dfsg+really1.3.1-1ubuntu3.1` package from Ubuntu's official dated snapshot
into the ignored isolated tool root, then check all three tool/library closures.
Do not change the source or extractor locks. Current run products belong under
ignored `target/coverage-20261024/paired-constraints-01/`.

**Selected source gate completed.** Fresh seven-PDF extraction and independent
output reconstruction pass, including the preceding conversion pack, all
2,657 historical gaps and 115 original unresolved migration obligations.
Nineteen selected text comparisons agree and five differ; neither count is a
semantic coverage percentage. Rendered publisher-page review confirms selected
GF feature rows and MOVD/FMA table/prose observations.

The twelve focused controls, all 499 tooling and 145 BAP Python tests, Ariadne
formatting, layout and navigation checks pass. Workspace-wide formatting fails
in unchanged MirrorRust tests. Default offline strict Clippy lacks `minidump`;
the alternate local Cargo cache requires a lock refresh rejected by `--locked`.
These checks remain unpassed. No Rust/native behavior or lock changes occur;
existing native/model/capture results retain their dated source identities.

**Next:** review the 100 additional sections and whole-document constraints,
adjudicate or precisely scope candidate conflicts and resolve cross-references.
Full source adoption, P1/P2 exits and legal-domain translation remain open.

### Section-5 execution and exit gates: 2026-10-24

**Successor:** [P1 completion](#p1-source-selection-completed-2026-10-24)
supersedes this earlier attempt's P1 blocker and its acceptance-counter scope.

The user requested performing the remaining stages in section 5 of the
[open-gate report](../chatdocs/ariadne-amd64-open-gates-20261024/index.html#next).
This authorizes implementation and applicable validation through P1–P8;
it does not relax any stage exit. The
[canonical execution contract](../../docs/Ariadne/amd64-coverage-design.md#1019-section-5-execution-and-current-exit-gates)
owns the new source tooling and current blockers. The
[frame-path repair](../../docs/Ariadne/investigation-design.md#frame-path-final-output-budget-repair)
owns the runtime issue discovered during P8 validation.

| Stage | Work executed | Current full exit |
| --- | --- | --- |
| P1 | Added original-ID-preserving current dispositions and a strict adoption check. Seven-PDF extraction/reconstruction and negative controls pass. | Blocked: 115 whole-required-source reviews remain, including the Vol5 status decision. Structural mapping closes 110 entry facets and one aggregate facet; it closes no whole-source acceptance record. Strict check exits 2. |
| P2 | Added nine cross-volume source clauses/53 anchors, signed `Disp8*N` and displacement-choice kernels, generic ER/SAE facts and a precise MOV displacement cross-reference boundary. | Partial: one reference has a checked source-rule disposition; nine earlier reference scopes and all 516 unparsed cells remain. Memory-shape admission and specific ER-prose conflicts remain separate. |
| P3 | Reran strict finite memory-domain/XED reconciliation. It accounts for 5,760 points and two partial source relations. | Strict full-domain check exits 1: all 10,569 candidate full domains remain unresolved and authoritative full-domain bindings remain zero. |
| P4 | Executed current memory-native preflight; recovered the exact adopted BAP helper from the existing qualification host without source upload. | Decoder pin remains unavailable; preflight exits 1 before native tests. Available core bytes also differ from its fixed required pin. No new consumer acceptance. |
| P5/P6 | Exercised the production family survey with the packaged producer, then the pinned advanced opt-in producer under a child-only runtime-path alias. | The final 171-case survey passes all nine declared effect expectations and reports 54 supported projections, 75 missing lifts, 31 control/semantic refusals, eight unknowns, two encoding disagreements and one query error. It supplies no full-family or fault/restart/I/O closure. |
| P7/P8 | Fixed the generated frame-path output-cap failure; reran root checks and the full generated-validation command with core and Stage E replay. | Applicable portable checks pass. Expanded REP consumers, current native/capture prerequisites and the upstream full-source/domain/implementation exits remain open. |

The [migration disposition tool](../../tools/amd64_migration_dispositions.py)
replays the full paired-source chain before deriving current facets. It keeps
all original IDs, objects and hashes, distinguishes source entries from document
reviews, and never credits replacement-only conversion anchors to predecessor
sections. The missing whole-section validator is an explicit premise, rather
than a Boolean callers may set. Nine focused controls pass.

The [extended source tool](../../tools/amd64_extended_constraints.py) checks its
[reviewed pack](../../tests/bap/fixtures/source-migration/extended-constraints-v1.json)
against both exact Vol1/Vol3 PDFs. Nine controls include all 1,792 signed byte/
access-size combinations and 458,752 signed-16 displacement-choice cases. The
original architectural pack is unchanged: its ten original unresolved reference
records and 516 cells remain visible alongside a separate checked disposition
for `evex-disp8-scaling`. The new current reference list has nine entries.

The live MirrorRust checkout declares 0.1.0, while the root lock requires 1.0.0.
A hash-verified, read-only snapshot of revision
`5049e99886a3d1f775e60190478c26e39c9aefc9` matches the locked package version.
The root lock and sibling checkout remain untouched. Use the selected snapshot
and existing populated Cargo cache for the current checks. The first generated
run's failing frame-path property and missing LLVM loader environment retain
their failed scope; the repaired-source rerun passes all seven suites, 3,200
configured generated cases, core replay and Stage E replay/mutations.

Current checks pass 475 default Rust tests/166 ignored, 64 core-only/22 ignored,
23 focused frame-path tests, strict all-feature/all-target Clippy, workspace
formatting through the read-only dependency snapshot, 517 tooling and 145 BAP
Python tests, layout and navigation. No ignored native/capture prerequisite is
inferred from these portable passes. Products remain ignored under
`target/coverage-20261024/section5-*` and the recovered-tool directories.

**Next executable boundary:** finish whole-source/constraint review and the
Vol5 authority/status disposition, recover or separately qualify the required
decoder/core artifacts, then run their fresh producer/native campaigns. Broader
domain translation, implementation waves, partial-outcome REP/I/O and consumer
expansion retain the earlier P3–P8 exits. This execution does not close the
requested full program and supplies no source/producer-pin relaxation.

### P1 source selection completed: 2026-10-24

The user requested finishing P1. Apply the source-authority/structural exit
defined above, with P2 clause interpretation and P3 legality kept separate.
The [canonical completion contract](../../docs/Ariadne/amd64-coverage-design.md#1020-p1-source-selection-and-structural-migration-completed)
owns the selected editions, variant proof, commands and claim limits.

The reviewed policy selects official Vol1/2/3 revisions 3.25/3.45/3.38 and
Vol4/5 revisions 3.27/3.16. Fresh downloads from all five publisher URLs return
HTTP 200 and match their exact pins. All old locks and 2,657 historical gap
objects are retained. All 110 entry records and five document reviews receive
explicit P1 dispositions, with required P2/P3 work retained under the same
original IDs. No added source section is excluded from future clause work.

The Vol5 source-variant rule preserves both markings and checks all 368 pages.
Outside the exact marking words and four individually reviewed bibliography
word relocations, 85,023 physical word boxes agree. The raw source is unchanged;
the source choice makes no claim that the markings themselves were erroneous.
The owning adjudicator freshly validates all seven original conflict records;
the actual rederived geometry validates all 33 table relations as 26
continuations/seven independent tables.

Source-adoption extraction and independent full reconstruction pass. Current
disposition schema v2 removes `whole-required-source-review`, runs the P1
adoption validator and reports 115 P1 dispositions closed/zero remaining.
Strict extraction and independent check with `--require-adoption` both exit 0.
All 527 tooling
and 145 BAP Python tests, format/layout/navigation checks pass. No Rust/native
behavior or producer/profile pin changes occur in this source-only extension.

**Next:** P2 clause/reference coverage under the accepted source pool, followed
by P3 legal domains and later implementation/consumer stages. The nine current
reference scopes, 516 original unparsed cells and named semantic conflicts
remain explicit. P1 completion does not mark any of those later exits complete.
Run products stay ignored under `target/p1-completion-20261024/`.

### P2 clause and reference execution: 2026-10-24

The user requested executing P2 after P1 was published in `e7a594b`. The
[canonical P2 contract](../../docs/Ariadne/amd64-coverage-design.md#1021-p2-clause-and-reference-execution)
owns interpretation, executable commands, source conflicts and claim limits.

1. Review the original 516 unparsed cells and nine reference scopes against
   accepted editions, including rendered table/diagram pages. Preserve every
   original object and digest.
2. Add 30 reviewed clauses and 804 context/clause/conflict anchors for prefix/size/register tables,
   diagrams, MOV offsets, UAI, segment bases and source-specific LOCK/REP lists.
   Check kinds, owners, dependencies and physical identity. Keep applicability
   and legal domains separate from descriptive source rules.
3. Add current dispositions: 492 supporting named clauses, 16 individually
   reviewed structural/context cells, five conflicting cells and three
   unparsed figure-reference cells. Resolve four more reference scopes; retain
   the earlier scaling resolution and five open scopes. Preserve six newly identified
   conflicts and all inherited boundaries.
4. Reconstruct seven actual PDFs and P1 adjudications before the P2 pass. Carry
   all 100 added sections and 4,340 selected PDF pages into addressed
   clause-review worklists. Checked anchors do not grant page completeness.
5. Run independent fresh reconstruction, strict P2 exit, negative/arithmetic
   controls, tooling/BAP regressions and documentation/navigation checks.
   Record reconstruction separately from the incomplete stage exit.

**Remaining exit:** five original references, three unparsed/five conflicting
original cells, new/inherited boundaries, all 100 added-section complete clause
reviews and whole-region completeness. The executable counts these objects.
P2 is active
and incomplete; P3–P8 retain their separate exits. Products stay ignored under
`target/p2-execution-20261024/`.

**Validation:** final extraction `run-04` passes. Independent strict `check`
reconstructs the full source chain and matches all artifacts, then exits 2 for
the incomplete P2 gate. Current source/input seals and original digests pass.
All 13 focused P2 controls, 540 tooling and 145 BAP Python tests pass, as do
layout/navigation checks. No Rust/native behavior changes require a new
runtime campaign in this source-tooling continuation.

### P2 completion tasks: 2026-10-24

The user requested developing tasks to finish P2 and continuing until a blocker
that cannot be resolved locally. The
[canonical completion follow-up](../../docs/Ariadne/amd64-coverage-design.md#1022-p2-completion-task-execution)
owns the data contract, implementation findings and dated validation.

| Task | Concrete delivery and exit | Execution state |
| --- | --- | --- |
| P2-A — Review-disposition engine | Bind every selected cell/word and clause/reference to exact source ownership; derive section/page completion from validated dispositions. Reject missing cells, overlaps, wrong owners, fabricated context and saved completion flags. Replace unconditional open-state assignments. | Implemented. Tested page/section closure, exact population coverage and dependency refusal; source-reviewed page 85 closes, page 68 retains its diagram dependency. This completes the engine delivery, not the remaining page reviews. |
| P2-B — Current obligation reconciliation | Preserve all original IDs/digests. Give each inherited boundary a current scoped resolution, still-open prerequisite or explicitly owned successor; derive counts from current dispositions. Link the three Figure 1-6 prose cells to their actual target without erasing its conflict. | Implemented for all 21 original boundary objects. Executed source-proof recipes close the old MOV-offset boundary and the alleged REX-x conflict. The three prose cells now have checked reference mappings. Nineteen source boundaries remain open under their original IDs. |
| P2-C — Architectural source inventories | Complete the fixed/default-size and mandatory-prefix exception inventories behind the five remaining references; review Appendix B, instruction-specific clauses and cross-volume rules. Parse supported table/diagram constraints explicitly. | Partly implemented in the [H64 continuation](#h64-source-projection-and-c-inventory-execution): full Appendix B heading/note population, default-64 owned clauses, invalid/reassigned tables and LOCK/REP source selectors. Full B-1 per-form qualifications and mandatory-prefix inventories remain open. |
| P2-D — Existing-family clause follow-ups | Replay the GF inverse table against its source definition; review conversion, MOVD and FMA reference/exception/encoding discrepancies. Reconcile each of the 14 inherited boundaries, retaining unresolved alternatives. | GF table replay implemented for all 256 entries in both Vol4 revisions. A noninvertible literal at input F1 requires an authoritative source answer. Other family follow-ups remain pending. |
| P2-E — Source-conflict adjudication | Search the accepted editions, independent publisher editions and official errata for each new conflict. Require exact evidence for an interpretation; source disagreement is preserved if an authoritative or justified explicit source rule cannot resolve it. | Resolved REX lowercase-x meaning through Table 1-17 note 1. Fresh official Vol3, Vol4 and combined-manual retrievals match their pins. The combined manual repeats the GF F1 value; no correcting answer was found in the searched publisher index/results. The GF interpretation is externally blocked. |
| P2-F — Added sections | For every one of the 100 added sections, build and independently review the complete clause/reference inventory, including feature, mode, privilege, OS-state, exceptions, memory and diagrams. No unmatched source material may disappear. | Pending source rules and P2-A. |
| P2-G — Complete region review | Give all 4,340 accepted pages checked clause/context dispositions, including global rules, supplementary references and nonarchitectural material. A page count or selected anchor count cannot close this task. | Pending P2-A and clause inventories. |
| P2-H — Final source and mutation replay | Reproduce actual pinned PDFs, replay every disposition and minimized omission/ownership/target/context mutation, run applicable tests and the strict exit. Complete P2 only if no required clause/reference is left unresolved. | Pending all required source interpretations. |

An external blocker must name the exact unavailable source answer, artifact or
decision, the attempts to obtain it and its affected tasks. Ordinary missing
implementation, a large review population or failing code within local control
does not qualify. Continue independent tasks while an answer is being sought.
No production admission, P3 legality or later runtime qualification is implied.

**Stopping condition encountered.** Vol4 revision 3.27 PDF page 228 and the
publisher's combined revision 4.10 PDF page 2229 both define `inverse(F0)=5B`
and `inverse(F1)=5B`. This is not an injective inverse on nonzero elements.
For F1, multiplication by the listed 5B under the documented polynomial 011B
gives 5A rather than 01; independent field inversion gives 23. Both predecessor
and selected tables retain 5B. Full geometric reconstruction and rendered-page
inspection confirm the literal; it is not a PDF extraction failure.

Required external answer: an AMD correction or an authoritative interpretation
reconciling the literal lookup with the claimed Galois inverse semantics.
Replacing the published value with 23 is not source adjudication. P2-D/E and
the full P2-H exit require that answer. P2-C/F/G still contain local inventory
and review work; they are unfinished work, not additional external blockers.
The user's stop condition is reached at this source-authority question.

**Validation at the stopping point.** Final `run-02` extraction passes.
Independent `check --require-complete` reconstructs all source products and
matches every artifact, then exits 2 for current unresolved obligations.
Current implementation/input seals, all 29 focused controls, 556 tooling
tests and 145 BAP Python tests pass, as do layout/navigation checks. The first
successful extraction is retained only as an intermediate source snapshot;
the final run includes explicit Table 1-10 ownership for GPR byte codes.
No Rust/native behavior changes or later qualification are claimed.

### P2-C architectural source inventory details

This describes C's full exit; the [later H64 execution](#h64-source-projection-and-c-inventory-execution)
delivers part of it. Its purpose is to turn general prefix/size rules and their
exceptions into exact instruction-form applicability records. Locating a note
or reading a mnemonic list does not enumerate every form covered by that note.

| Open reference | Required C inventory | Shared source question |
| --- | --- | --- |
| `prefix-note-2` | Classify when 66h is an operand-size override, an opcode selector, ignored or otherwise restricted, with exact instruction/form ownership. | Generic prefix rules do not enumerate SIMD and instruction-specific exceptions. |
| `prefix-note-5` | Inventory LOCK-eligible forms and their memory-destination/applicability predicates, including the complete source-specific mnemonic lists. | Vol1 omits CMPXCHG16B while Vol3 includes it; its disposition also belongs to E. |
| `prefix-note-6` | Separate count-only REP, ZF-conditioned REPE/REPNE and SIMD opcode-selector uses of F2/F3. | The table note and dedicated REP section differ in scope; its disposition also belongs to E. |
| `operand-note-2` | Inventory exceptions to the typical 32-bit operand-size default. | Requires the actual Appendix B rows, definitions and notes. |
| `default64-instruction-exceptions` | Bind the exact default/fixed-size forms and near-branch/implicit-stack qualifications. | Overlaps the previous reference; it is not a separate instruction population. |

**C.1 — Source and ownership map.** Review selected Vol3 Chapter 1 prefix/size
rules (especially PDF 49–56), Appendix B (PDF 627–656), the corresponding
Vol1 branch/stack/operand-size rules and each relevant instruction's own
section. Retain exact PDF identities, physical cells, table rows and footnote
targets. Appendix B covers general-purpose instructions; mandatory-prefix
exceptions in SIMD and other subsets require their own instruction sources.

**C.2 — Default/fixed-size matrix.** Parse B.1 definitions, all applicable
Table B-1 rows/notes, B.3 invalid/reassigned forms and B.4/Table B-5 default-64
forms. Classify each form as fixed size, variable/promoted size, special
default, unavailable in the selected mode or reassigned encoding. Keep operand,
address, immediate, displacement and implicit-count widths separate. A
no-REX-needed list is not itself a default-64 operand-size inventory.

**C.3 — Prefix-role matrix.** For each relevant instruction form, record the
role and applicability of 66h/F2h/F3h and the interaction with REX.W or an
extended encoding's prefix selector. Required opcode selection, size override,
ignored prefix and explicit invalid/undefined use are distinct source
dispositions. General rules can be reused only after their premises apply to
the form; instruction-specific exclusions remain explicit.

**C.4 — LOCK/REP form inventories.** Bind each source-listed operation to its
actual forms and predicates, rather than treating a mnemonic as sufficient.
For LOCK, distinguish a memory-writing destination from a register destination.
For REP, distinguish repetition from opcode selection, retain the count-width
and ZF qualifications, and carry the two source disagreements into E. This
inventory does not implement string loops or partial-fault/restart behavior.

**C.5 — Typed source records and independent review.** Give each owned form
selector its source clauses, mode/applicability predicates, size/prefix rules,
exceptions, dependencies and current disposition. The selector identifies the
source instruction form/opcode family; P3 later supplies the complete byte
grammar. Preserve raw rows and repeated physical note occurrences while
sharing semantic rule identities where justified. Independently compare the
reviewed inventory against the manual, including unmatched material. Do not
let a parser certify completeness merely by counting its own matches.

**C.6 — Executable closure.** Reconstruct actual pinned products; replay rows,
diagrams, notes and ownership; integrate the records with the A/B disposition
engine. Omitted fixed/default-size rows, swapped prefix-note-2/operand-note-2
targets, byte forms incorrectly promoted to 64 bits, false mandatory-prefix
roles, register-only forms admitted to LOCK, stale source identities and
unsupported clauses labeled harmless must fail. Close the five references only
after their full required scopes have checked current dispositions. Passing
selected-rule tests is insufficient.

Current code explicitly retains `exhaustiveInstructionApplicability=False`,
`instructionExceptions="required-separate-inventory"` and
`fullOpcodeExceptionInventory=False` in its selected clauses. C supplies the
missing inventories behind those limits; changing the flags does not supply
the evidence. No complete reviewed C form count is currently established.

The GF inverse-table question belongs to D/E and the full H exit. It does not
prevent most of C.1–C.6 from proceeding with the available pinned sources.
LOCK and repeat source-scope decisions are C's specific shared dependencies
on E. C remains unfinished local review/implementation work.

### H64: native AMD64 execution only

The user proposed a 64-bit-only platform hypothesis. The
[canonical H64 contract](../../docs/Ariadne/amd64-coverage-design.md#1023-h64-native-amd64-execution-only)
interprets it as native AMD64 64-bit execution, excluding legacy/compatibility
execution and 32-bit/WOW64 target execution. The source scope already selects
`long-64`; do not mutate frozen manifests or delete historical evidence.

1. **Mode ownership.** Distinguish explicitly 64-bit rows from explicitly
   non-64-only rows. Preserve shared notes and cross-mode context needed to
   interpret selected rows. Execution mode, operand/address width and encoding
   family are separate properties.
2. **Scoped dispositions.** Add an executable mode-evidence recipe for the
   non-64-only MOVD store-row conflict, preserving its original ID and literal.
   Keep the note-1 native-64 row required. Other source questions need their
   own proven scope; do not exclude them by analogy.
3. **P2-C under H64.** Review native-64 default/fixed-size rows, 8/16/32/64-bit
   operands, 67h address-32 forms, applicable legacy/VEX/EVEX/XOP encodings and
   prefix/LOCK/REP qualifications. Classify material out-of-selected-mode only
   after exact source ownership establishes that restriction.
4. **Controls.** Reject exclusions based only on 32-bit data, address-32,
   a legacy-encoding label or a 64-bit host. Require the exact row/note mode
   predicate and reject swapped note-1/note-2 ownership. Keep GF in scope.

Status at the hypothesis checkpoint: documentation only. The
[following execution](#h64-source-projection-and-c-inventory-execution)
implements the exclusion and source inventories. H64 does not itself complete
P2-C or the full P2 exit. Runtime handling, source locks and producer/helper
pins remain unchanged.

### H64 source projection and C inventory execution

The user resumed P2 under H64. The [canonical source contract](../../docs/Ariadne/amd64-coverage-design.md#1024-h64-source-projection-and-native64-inventories)
owns the implementation and its limits.

- B/D: source-check the non-64-only MOVD row in both editions, bind the exact
  `long-64` scope and use a distinct mode-exclusion disposition. Preserve all
  original boundary objects, the raw 6E literal and the native-64 row.
- C.1/C.2: replay Appendix B's 30 pages, 172 B-1 headings/3,910 body words and
  150 physical notes. Reconstruct all 21 B-5 defaults, the separate 27-entry
  no-REX relation and all 22/5/2 B-2/B-3/B-4 rows. These finite source
  populations do not establish complete opcode semantics.
- C.2/C.5: bind 21 default-64 records to their instruction-owned clauses and
  extents. Separate counter/address size, stack payload, immediate and branch
  displacement. Keep per-form 66h qualification explicit.
- C.4/C.5: bind all 19 LOCK mnemonics/195 source selectors and seven REP
  string families to exact source clauses. Require a memory-writing
  alternative; retain XCHG's automatic memory lock and INS/OUTS data limits.
- C.6/H: execute omission, geometry, target/owner, predicate-direction,
  mode/width and source-reconstruction controls. Fresh extraction passes;
  independent strict replay reconstructs the chain, matches every artifact
  and exits 2 for the incomplete P2 gate. All 52 focused controls, 579 tooling
  and 145 BAP tests pass, with current-source seals/layout/navigation passing.

Remaining C work includes full per-form B-1 qualifications, mandatory media
prefix roles and source-list adjudication. The literal PREFETCHlevel summary
`/0-3, 7, 8` remains a source-review question alongside the instruction-owned
`/6` and `/7` rows; no byte domain is generated from it. P2-F/G's section and
whole-region reviews remain local work. The GF authority answer is still an
external dependency of full P2 acceptance; it is not used to close these tasks.

The subsequent C.2 review verifies an additional native-64 source conflict:
Vol1 PDF 128's near-branch Table 3-9 permits operand-size 16, while PDF 129
says the near-branch actions/operand size are forced/fixed at 64. Rendered
pages and the current publisher PDF confirm both; targeted AMD searches found
no correction. Required answer: reconcile the 66h behavior for the seven
near-branch groups, or explicitly select a conditional source-precedence
hypothesis. Existing records keep per-form 66h qualification pending; no new
source correction or machine-adjudicated boundary is claimed. Other C/F/G
local work remains unfinished rather than externally blocked.

The [following user decision](#fixed64-near-branch-hypothesis-follow-up)
selects the fixed-64 case, so this broader source question no longer prevents
continuation under that hypothesis.

### Fixed64 near-branch hypothesis follow-up

The user selected fixed-64 operands for the seven near-branch groups and
instructed that the possible operand-16 overrides be ignored for that case.
The [canonical contract](../../docs/Ariadne/amd64-coverage-design.md#1025-selected-fixed64-near-branch-hypothesis)
owns the scope and limits. The next user instruction was to record, commit
and push; no checker or input changes have been made for this hypothesis.

Resume in this order:

1. Add a versioned current-scope projection for CALL near, Jcc, JrCXZ, JMP
   near, LOOP, LOOPcc and RET near: selected operand size 64 and excluded
   operand-16 alternatives. Bind it to native `long-64`, exact owners and the
   accepted user hypothesis. Preserve the frozen source manifest, original
   records and conflicting table/prose observations.
2. Annotate the current near-branch qualifications without presenting the
   old unresolved source property as a source correction. Keep address-32,
   implicit-count width, displacement width and other instruction families'
   smaller operands separate. Do not treat this scope decision as authority
   to strip or automatically admit a 66h byte prefix.
3. Add controls for wrong modes/owners, blanket smaller-operand exclusions,
   conflated operand/address/count sizes and false prefix admission. Verify
   the chosen fixed-64 case and preservation of every original obligation.
4. Replay the actual sources and current dispositions after implementation,
   run the affected checks and evaluate the strict P2 gate. Close only the
   scoped obligations actually satisfied; full reference/section/page review
   and GF source interpretation remain separate.

The source conflict remains recorded, but an external answer about the
excluded operand-16 alternative is not required to begin this selected case.
The current checker remains at the earlier implementation snapshot until
steps 1–4 execute. This documentation publication creates no new acceptance.

### Continuation stopped for publication: 2026-10-24

The user requested stopping current work, then committing and pushing. All
workers and campaigns are stopped. The [canonical continuation record](../../docs/Ariadne/amd64-coverage-design.md#1013-constraint-and-mov8-continuation-stopped-for-publication)
owns source/algorithm details, exact validation scopes and remaining limits.

- P1: additive eleven-dimension comparison freshly reconstructs five old PDFs
  and two publisher replacements, preserving all 2,657 historical gap identities.
  Volume 4 adds 105/removes five titles; Volume 5 retains a source-status marking
  conflict despite equal normalized rows. The candidate is unadopted, with 115
  explicit migration-review obligations. Sixteen controls pass.
- P2: 24 architectural clauses/1,118 anchors, 26 references (sixteen located,
  ten unresolved) and 516 unparsed cells are integrated into the source ledger.
  The optional publisher branch remains separate from mandatory corpus adoption.
  Full ledger extraction/check passes; 17 constraint and 25 ledger controls pass.
  P1/C2/global source completeness remain false.
- P3/P4: a separate dependent ModRM/SIB/displacement grammar covers 5,760 selected
  memory-MOV8 points. Fresh 11,520 BAP/LLVM observations and the Rust observer
  pass the declared 2,880 supported address-64/2,880 refused address-32 partition.
  Existing prefix barriers protect the discovered address-32 producer errors.
  Memory native-consumer and whole-candidate domain coverage remain open.
- Register-MOV8 native qualification passes four exact named release tests:
  1,280 instruction instances in twenty minidump analysis batches, independent
  byte-origin assertions, host/native boundary refusals and guarded bad-lift
  regressions. The plain native consumer continues to trust reader-normalized
  semantics; no independent native ISA validation is claimed.
- All four registries have fresh source/BAP/oracle/Rust build/check campaigns.
  The twelve final steps and source stability pass, including expected
  incomplete-gate exits and 89 focused controls. Default Rust passes 473/164
  ignored; strict Clippy, format/layout, 459 tooling and 145 BAP Python tests
  pass. No new core-only run was completed during this continuation.

**Unfinished at stop.** The five additional per-form dependency links
`prefix-group-order`, `legacy-prefix-byte-groups`, `rex-placement-count`,
`instruction-length-limit` and `operand-size-override` were requested but not
applied. These facts already reside in the bound/replayed architecture pack;
the explicit form mapping still needs review completion. No subsequent reseal
or rerun occurred. Existing passing campaigns cover the preserved source and
do not satisfy that pending requirement.

**Next resume boundary.** Apply and review the mapping change, freeze its
sources and refresh affected ledger/binding/native campaigns. Then continue
corpus adoption/scope, remaining constraints, wider domains and implementation/
consumer stages. Full AMD64 coverage remains open. Generated outputs stay
ignored under `target/coverage-20261024/`; publication includes only code,
reviewed inputs, small actual fixtures and documentation.

## Completion contract

An operation is supported when legal forms under its declared architecture and
execution-mode premises have implemented control, use, possible-write and
definite-write behavior, or implemented unwind transitions, with independent
executable expectations. Runtime/environment values may legitimately remain
unknown; an unimplemented operation must not be relabeled supported by giving
it generic unknown effects. Illegal/reserved encodings require explicit
rejection and negative tests; they are not missing legal operations.

The coverage denominator must be a versioned authoritative operation/form
inventory, not discovered instructions in a sample capture or a list of opcode
spellings. It must distinguish 64-bit forms, operand/address widths, prefixes,
architectural extensions, privilege/mode premises and aliases. The target
includes general/system instructions, x87/MMX, SIMD/vector/mask state, atomics,
string/repeated operations and newer published extension families. Compatibility
or 16-bit-only forms are recorded as mode-inapplicable rather than counted as
64-bit implementation successes. AMD and Intel extension differences stay
explicit. Windows unwind metadata v1/v2 and published v3/APX are separate rows.

Primary references:

- [AMD architecture manuals](https://www.amd.com/en/search/documentation/hub.html) —
  authoritative versioned instruction forms and architectural state; pin exact
  revisions before claiming an exhaustive denominator.
- [AMD Volume 3 revision 3.37](https://docs.amd.com/v/u/en-US/24594_3.37) — initial
  general/system reference, not the complete SIMD/x87/extension denominator.
- [Microsoft x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170) —
  conventional unwind operations, ordering and chained metadata.
- [Microsoft unwind v3/APX](https://learn.microsoft.com/en-us/cpp/build/x64-unwind-information-v3?view=msvc-170) —
  separately versioned descriptor format; Ariadne replay profile v3 must not
  be confused with this Windows metadata version.

This program expands implementation coverage. It does not revive the retired
independent instruction-step proof project or replace trusted BAP lifting with
automatic LLVM semantic fallback. A changed lifter is a new pinned dependency
that needs qualification. Analysis-level formal contracts remain active.

## Baseline

Source baseline: `9184c4ce9fcd775295735927e9b13b2997c07e77`.
Fresh initial checks: default Rust 362 passed/129 ignored, core-only 64/22,
251 Python controls, formatting, all-feature/all-target Clippy, layout and local
documentation links pass on Rust 1.96. No edits were present at that boundary.
The installed native analysis helper fails current source identity validation;
its files exist, but this is not a current native qualification.

Machine semantics currently use projection profile v6 with GPR/RIP, seven flags,
memory and XMM/YMM0–15, bounded at 256 bits. General loops, specials, exceptions,
several prefixes and missing upstream lifts remain outside supported admission.
The unwind parser accepts ordinary-body Windows metadata v1 with flags zero;
its Ariadne profile v2 adds captured SAVE_XMM128 bytes but has no dedicated
operation-specific regressions at the baseline.

## Stage ledger

| Stage | Work and exit | Status |
| --- | --- | --- |
| C0 | Link canonical contracts and define separate instruction/unwind coverage, gaps and compatibility. | Passed: linked contracts and plan navigation |
| S0 | Executable family survey using actual instruction bytes; probe actual BAP lifting and Ariadne projection, preserve distinct outcomes and exact source/tool identities. | Passed finite survey: 49 families / 170 byte cases; not S1 completeness |
| S1 | Expand S0 into a pinned exhaustive legal-form denominator across the declared AMD64 manuals/extensions; independent inventory completeness check. | Partial: five-volume candidate corpus, all 2,657 historical gap dispositions and 56-point AMD legal/binding registry; seven bounded source-conflict adjudications and all 33 table relations pass; corpus authority/adoption, constraints and full grammar remain open |
| S2 | Close missing producer lifts in a reviewed BAP source build; pin and validate the replacement producer and retain existing semantic compatibility. | Partial: finite advanced/Basic candidate checks, frozen LODS producer and separate AMD address-size producer pass their scoped checks; Basic adoption, historical identity and other producer gaps remain open |
| S3 | Extend typed transport, state banks/aliases and width handling for all required SIMD, mask, x87, control/system and extended registers. | Partial finite v10/v11 FP-control state and coarsened data projection; wider banks/widths remain pending |
| S4 | Implement exact prefix distinctions and bounded loop summaries; preserve zero-iteration paths, conditional writes, faults and resource stops. | Partial: R1's 28 default-address tuples pass at their recorded native boundary; AMD v15 adds 28 canonical address-32 tuples with local gates passing. Current finite v15 native qualification passes under helper-build migration v1; wider prefixes, proof consumers and partial faults remain open |
| S5 | Implement and qualify remaining floating-point, system, exception and special-operation contracts with explicit mode/environment premises. | Pending |
| U0 | Preserve old v1/v2 receipts and add a separate new replay profile with conventional opcode tests. | Passed finite v4 tests, preserving v1/v2/v3 replay |
| U1 | Complete near/far saved-vector operations and validated saved-register ordering, bounds, alignment and budget behavior. | Passed selected synthetic and Windows reference cases |
| U2 | Implement machine-frame restoration and exact interrupted-PC provenance; prevent ordinary-call/alignment inference across exceptional transitions. | Passed both machine-frame layouts, null interrupted PC and consumer regressions |
| U3 | Implement handler/chained metadata and partial-prologue execution with bounded chain/cycle and frame-establishment checks. | Passed selected metadata-v1 cases; chained operation restrictions remain explicit |
| U4 | Implement documented epilog suffixes and Windows metadata v2 descriptors, with independent reference comparison. | Implemented finite v1/v2 scope: 53 focused tests and 103 Windows comparisons pass; sparse capture and malformed terminal contexts have separate controls |
| U5 | Implement Windows v3/APX descriptor and extended-context support as its own versioned profile; do not reinterpret earlier formats. | Pending: extended-context/canonical-frame layouts and working V3 reference not admitted |
| Q0 | Current-source native rebuild, independent per-operation expectations, Rust/native parity where applicable, focused mutations and models, capture and root regression checks. | Partial: R1 records 416 native parity instances and 259 controls. The current v15 helper-build migration passes 448 native parity instances, 341 refusal controls and compatibility. The earlier four compiled mutants retain their source scope; broader qualification remains open |
| Q1 | Every legal inventory row supported and exercised; all stage exits complete; document exact operation/form denominator and remaining environmental premises. | Pending |

Stages may run in parallel when their source ownership does not overlap.
Passing an earlier stage never closes S1/S2/S3/S4/S5/U4/U5/Q1 by implication.

## Machine-semantics implementation

1. Add a data-only catalogue in `tests/bap/fixtures/amd64-semantics/`, a public
   native test that calls the actual BAP preparation API, and a Python driver.
   Inventory-only mode records unexercised rows. Live mode records decode/lift,
   actual projected effects and explicit unsupported reasons separately.
2. Require catalogue uniqueness, real byte strings, architecture/mode/family
   identity and independent effect expectations where available. A decoded or
   projected instruction alone does not prove ISA-correct semantics. Freeze
   representative negative/missing-producer cases as well as positive examples.
3. Use the survey to identify producer gaps before changing admission. Review
   and patch the BAP lifter or select a qualified successor; Ariadne must not
   synthesize instruction effects from LLVM opcode names to conceal missing BIL.
4. Version changes to producer/admission semantics. Preserve replay of old
   profiles. Expand architectural state and control semantics with explicit
   alias, exceptional-completion and must-definition rules before admitting
   new families. Unknown producer constructs remain visible until implemented.
5. Each family stage adds actual-byte expectations, malformed controls and
   source-bound native comparisons. Expand the catalogue into exact legal forms
   before any overall percentage or full-coverage statement is published.

## Unwind implementation

The new Ariadne replay profile preserves the v1/v2 algorithms and exact read
sequences when replaying their saved products. New successful frames record
whether their transition to the older frame is a normal return or a machine
frame. The optional field is omitted for old profiles, preserving old serialized
bytes and hashes. A machine frame restores exact RIP/RSP; it must not use the
ordinary return-PC-minus-one lookup or manufacture an active CALL witness.

Conventional legal operation inventory: PUSH_NONVOL, both ALLOC_LARGE forms,
ALLOC_SMALL, SET_FPREG, SAVE_NONVOL/FAR, SAVE_XMM128/FAR, PUSH_MACHFRAME with and
without error code. Windows v2 EPILOG is a separate format stage; reserved
SPARE_CODE stays rejected. CLR Unix SET_FPREG_LARGE is not silently treated as
a Windows operation. Windows v3 WOD descriptors require their own inventory.

Handlers are opaque data; reading their metadata never executes a handler or
establishes exception resumption. Chained records require bounded, cycle-checked
captured traversal and valid register/allocation relationships. Partial
prologues apply only operations completed at the captured instruction boundary.
Epilog interpretation consumes captured instruction bytes and admits only
documented validated forms. Missing code/stack bytes stop with an explicit gap.

Machine-frame stack switches may be represented only to the extent supported
by captured stack evidence. Frame/path consumers must preserve exceptional or
unavailable-call boundaries rather than treat such frames as normal ancestry.
Vector save evidence is not a fabricated captured vector register context.

## Validation and source ownership

- Runtime: `src/investigation/frame_unwind.rs`, `src/input/frame_paths.rs`,
  affected frame/path consumers; machine admission/transport in `src/bap/` and
  `native/bap/` only after matching producer work.
- Tests: independent synthetic captures under `tests/input/`, instruction bytes
  and projection probes under `tests/bap/`; validation tools under `tools/`.
- Positive/negative unwind tests cover every legal code/info/register boundary,
  offsets, truncation, alignment, budgets, partial prologues, chains/cycles,
  epilogs, machine layouts and same-capture old/new profile replay.
- Compare applicable unwind cases against an independent Windows
  `RtlVirtualUnwind` harness; synthetic Rust tests are not credited as that tier.
- Use existing independent BIL oracles, native/core replay and focused mutants
  for semantics. Isolate probe/replay/mutation builds below separate `target/`
  directories. Do not publish generated reports or copied runtimes in source.
- Run affected tests, formatting, default/core-only Cargo tests, strict
  all-feature/all-target Clippy, layout and documentation-link checks after
  integration. Native helpers, model tools and actual captures remain explicit
  prerequisites of their selected tests.

## Execution log

2026-10-22: baseline analysis completed; two-track coverage program started.
Initial parallel work owns the actual BAP survey, unwind implementation,
independent unwind fixtures and exceptional-transition consumers separately.
No full-coverage or native qualification claim is made at program creation.

2026-10-22, first finite implementation boundary: Ariadne unwind profile v3
passes 37 focused input tests and 79 fresh Windows RtlVirtualUnwind comparisons
with stable sources. The stage-v3 default suite passes 389 tests (131 ignored).
The first 78-case run matched values but failed source stability and remains a
failed run; a separate RET-immediate comparison exposed a real SP mismatch,
fixed before the successful 79-case run. These are finite adapter results.

The actual production semantic survey observes 44 projected cases, 8 conservative
unknowns, 79 missing lifts, 33 unsupported control/semantic cases, 2 unsupported
state cases, 2 decode disagreements and 2 query errors. Five independent effect
expectations pass. Seven source-producer controls and the actual baseline/patched
BAP experiment prove CLC/STC/CMC/STD gap closure on the four exact plain forms
plus CLD: 20 flag input combinations and 30 observations per executable. The
pilot is not production integration and does not close full S2. The SDK and
packaged runtime are unchanged. A fresh native analysis helper was rebuilt,
with the previous binary/manifest backed up under ignored target storage.

### Integrated execution boundary

The initial finite stages have been implemented and tested. **The full AMD64
objective is not complete.** S1, wider S2, S3–S5, U5 and Q1 remain open; no
representative survey or conservative unknown result closes those exits.

- Fresh Ariadne unwind profile v4 supports conventional Windows metadata v1/v2
  operations, bounded handler/chained records, partial prologues, explicit
  machine transitions and metadata-selected epilogs. Saved v1/v2/v3 replay
  remains separate. Fifty-three focused tests pass, including sparse capture and
  malformed terminal-PC controls. All 103 complete-image synthetic Windows
  RtlVirtualUnwind comparisons pass with stable sources. Sparse capture tests
  are Rust-only, not native sparse-input qualification.
- Source-built BAP CLC/STC/CMC/STD support is an explicit opt-in v9 producer path.
  Two independent builds reproduce the pinned executable/manifest. Eight Rust
  controls include actual native transport, Windows/Linux capture parity,
  tampering and saved-mode refusals; four direct native validator controls and
  sixteen Python producer/survey controls pass. Fifty-seven unaffected cases
  retain their effects under the changed opt-in identity. Guards, target
  resolution and memory refinement are explicitly excluded for v9, including
  their saved/native admission boundaries.
- The final 171-encoding/49-family survey has 44 projected and 80 missing lifts
  by default, versus 48 projected and 76 missing lifts with the extension.
  Exactly the four selected flags change status; all nine independent expected
  effects pass with the extension. Default missing flag expectations remain
  failed. Other unknown, unsupported, disagreement and query-error categories
  remain unchanged. This is not an exhaustive legal-form inventory.
- On Rust 1.96, default tests pass 410 with 134 ignored; core-only passes 64 with
  22 ignored. Strict all-feature/all-target Clippy, formatting, layout and
  navigation pass. Three property tests pass 384 configured unwind cases; 251
  general Python controls pass. One compiled current-body guessed-stack-slot
  mutant is detected by the allocation/save observer. Six existing mutation
  selectors are unique; the entire six-mutant campaign was not rerun.
- The mutation experiment first failed to compile because the isolated-copy
  helper omitted the alignment model. That attempt earns no mutation credit.
  The helper now includes all required model/native compile-time inputs; the
  fresh mutant compiles and fails for the intended behavioral assertion. New
  native compile-time inputs also participate in source inventories.

Windows V3/APX has a separate public preview format. The current reader and
minidump dependency retain only the legacy AMD64 context; authoritative APX
context/canonical-frame layouts and a working independent reference remain
unmet prerequisites. A base-only V3 capability attempt errored in an isolated
Windows reference process and grants no support credit; it does not establish a
complete diagnosis of OS V3 availability. No guessed layout was admitted.

All generated observations, failed attempts, binaries, copied mutation sources
and backups remain under ignored target/ or temporary storage. The maintained
files are implementations, fixtures, executable controls and dependency pins.

Final address-boundary review added checked construction for runtime-table and
chained virtual addresses, plus the legacy unwind-code pointer. Three new tests
exercise explicit refusal at the half-open endpoint at 2^64 through saved-chain
replay. They separately retain the current minidump reader's omitted-module
result and reject a manually supplied module premise during live rebinding.
The final current-source Windows matrix still passes all 103 bounded-image cases;
these high-address and sparse-input tests are Rust-only. The final source also
passes the selected compiled stack-slot mutation, 384 generated unwind cases,
410 default Rust tests, 64 core-only tests and strict root checks.


### User-requested stop: items 1–3

2026-10-22: implementation and native campaigns stopped before completion.
The [checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request)
records the exact source/test boundary and failures; resume only when requested.
S1 now has reproducible pinned XED templates and AMD manual transcriptions with
explicit unresolved extraction/legality gaps. S3/S4 have finite v10/v11
FP-control, NOP, data-path-join and mandatory-count admission work. At that stop,
REP remained refused; its independent numeric oracle was not production admission. The
separately pinned advanced producer and versioned guard/target/refinement
integration are saved with a failing native matrix and incomplete count replay,
compatibility and mutation gates. Earlier ledger statuses are historical stage
exits; none of S1, broader S2–S5 or Q1 is closed by this stopped snapshot.

### Resume: guard replay and composed fixture

2026-10-23: resumed from `3024fcb`. The empty guard report is reproducible with
the packaged producer and CLD, without the source flag extension or native core.
It is a `guard-closure-round-limit` stop: combined discovery advances the epoch
on source/control changes, exceeding the default eight epochs. The advanced
table fixture now explicitly selects 64 epochs and requires its MOVAPS guard.
A separate actual-BAP/LLVM test checks both the default stopped result and the
selected-budget aligned result. Production defaults and expected targets stay
unchanged; empty reports remain valid stopped products.

Saved guard replay now recovers opcode identity for the eighteen byte-exact
mandatory-count forms already admitted under v10/v11. Previously its generic
`typed-transfer` opcode caused a count/bytes mismatch and lost RSP facts. Both
transfer derivation and coverage replay use the same scoped byte matcher. A
portable regression checks all eighteen forms, old-profile refusal and hostile
saved bytes; a fresh-BIL test checks their actual lifts and saved guard replay.
An additional native integration test composes counts, CLC, MOVAPS and a rooted
table with independent target expectations, full-state parity and saved replay;
all eighteen forms now pass that actual native gate. A further downstream bug
was exposed by it: composition's original-control replay used the default
projection. Advanced sources now retain their declared profile there; legacy
sources keep the previous path. The separate portable composition regression
covers the same eighteen byte forms and altered-prefix/old-profile refusals.

The unused default-profile wrapper is now test-only, and two test mutations
replace boxed contents without allocating replacement boxes. Two stale guard
mutation selectors are repaired, and count-replay/composition-profile mutants
are added. All eight selectors are unique. Their optimized Rust campaigns
detect eight mutants through nine named assertion rejections after passing
controls, with independent source/build trees, restored source and unchanged
observers. Seven qualify before the final observer-diagnostic refinement;
the composition-profile case qualifies after a standard-assertion rerun.
Production/checker sources remain frozen across these runs. The initial custom
panic message, startup failures and interrupted serial attempt are uncredited.

The local Cargo cache is `target/mbt-cargo-home`; the lockfile records the
current sibling MirrorRust package version `0.1.0` in place of stale `1.0.0`.
Packaged BAP loading was restored with libtinfo5. The exact LLVM 20.1.2 library
and its libxml2 ABI dependency were extracted into ignored local work; no newer
LLVM version was substituted. Fresh numeric oracles pass 4,020 count and 720
repeated-string comparisons. REP production admission remains refused under
these v10/v11 profiles; the later plain v12 continuation is separate.

The original SDK was located on `win10` at
`/home/jlc/ariadne-p4-20261010/work/Repos/Ariadne/target/bap-core-sdk`.
Its lock and both public dependency archive hashes match the current pins.
Direct execution in the outer WSL distribution fails its tool/libc checks.
The approved continuation instead reuses the original compatible isolated
userspace; the unchanged SDK inventory and project/term/storage smoke pass.
The current source/test bundle was transferred with approval and mounted
read-only. Git history, generated evidence and the real Windows archive were
excluded. Build, replay and mutation outputs remain disposable.

Two independent advanced producer builds are byte-identical under that SDK.
Their identity differs from the saved advanced pin, so only the advanced
runtime lock is explicitly updated to the reproduced manifest/executable.
The Basic v9 builder and lock remain immutable. Its exact old runtime is not
available; a mismatching fresh Basic build is rejected, and positive v9
producer compatibility under the historical pin remains unexercised. The
candidate check below separately exercises the available Basic build.

After source freeze and helper rebuild, all eight advanced tests pass: the
eighteen count compositions and seven remaining guard/target/writer/codec
tests. Legacy v7/v8 capture controls pass with one detected native dependency
mutant. Current proof compatibility passes 88 controls and nine compiled
checker mutants, with actual reader-produced v8 load/terminal wires and
saved legacy/current proof units. The retired legacy driver's evidence path
is replaced by the maintained small byte/BIL fixture and checked by policy.

Generated native replay matches 168 core and 162 finite-stateflow observations;
both wrong-digest controls reject with zero dispatch. Predicate oracles pass,
and restored installed model-tool assets permit Apalache typechecking and all
58 TLC configurations to pass safety/expected outcomes/fair termination. No
TLA+ model body was changed. This does not establish universal refinement or
ISA correctness. Inventory legality gaps, general REP consumer contracts,
broader S2–S5, U5, real-capture/timing/release qualification and Q1 remain open.

Final local validation passes 424 default Rust tests (145 ignored), 64 core-only
tests (22 ignored), strict Clippy, 46 BAP Python controls, 251 general Python
controls, layout and navigation. Required root format/default/core-only/Clippy
checks pass under the existing read-only MirrorRust snapshot workflow; only
the copied `tests/protocol.rs` is formatted. The sibling checkout stays
unchanged. Direct root formatting against that original sibling still reports
its existing style differences. Core-only normal dependencies stay empty.
Fresh count effects, eighteen actual guard replays and the two-budget packaged
table control retain their separate exercised scopes.

### Current Basic v9 candidate check

2026-10-23, source `faf75f7`: the follow-up tests the available Basic runtime
under the v9 contract. The [canonical candidate contract](../../docs/Ariadne/bap-analysis-core-design.md#current-basic-v9-candidate-compatibility)
records its manifest/executable identities and the
[checkpoint](../../CHECKPOINTS.md#2026-10-23--current-basic-v9-candidate-compatibility-checked)
records the result.

1. Verify the current shared inputs: 647 source/test/native and Cargo files
   match the checkout. The unrelated real Windows archive is not transferred.
2. Run the three existing native v9 tests against each available bundle with
   the unchanged Basic lock. Both Basic and advanced bundles are rejected at
   the manifest hash check before semantic dispatch, as required.
3. Compare their actual typed BIL for F5/F8/F9/FD on Windows and Linux. All eight
   cases agree apart from the separately bound build IDs.
4. Copy the current sources to disposable work, change only the copied Basic
   pin to the genuine current Basic manifest/executable, and run
   `bap::source_extension::tests::native_` with default features and
   `--ignored --test-threads=1`. All three tests pass: four flags/unchanged corpus,
   forbidden composed modes/tamper poisoning, and synthetic Windows/Linux
   capture/native parity with opaque-site and target-resolution refusal checks.
5. Restore the copied lock and verify the original source identity, production
   lock and candidate artifacts are unchanged. Reports, logs and copied trees
   remain ignored run products.

This establishes the candidate's tested Basic v9 behavior under its own pin.
It does not adopt that pin or reproduce the historical artifact. A separate
explicit Basic pin review is the adoption step; historical identity still needs
the original artifact or a matching build. Wider S2–S5/U5/Q1 and real-capture,
timing and release gates remain open.

### Resume: plain REP and coverage accounting

2026-10-23, baseline `e44ce2b`: process the remaining REP/full AMD64 item with
the [canonical v12/accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting).
This stage is partial S4/Q0 work. It does not close S1, wider S2–S5 or Q1.

1. Add explicit `Config::with_repeated_strings(dir)` and environment mode
   `repeated-strings`, binding the unchanged pinned advanced flag bundle to
   plain `bap-bit-provenance-v12`. Preserve packaged/default, Basic v9 and
   advanced v10/v11 interpretations and pins.
2. Admit only `F3 A4`, `F3 AA` and `F3 A6` with exactly one top-level typed
   loop, preserved definite virtual bindings and no external control, RIP
   writes, special semantics, nested loops or extra loops. Retain zero-iteration
   origins and possible body writes through a dependency fixed point. Weak
   `memory:any` writes never kill all old memory origins. Keep 262,144 work
   steps and 4,096 fixed-point rounds as explicit `Resource` failure limits.
3. Mark loop memory addresses unknown and iteration-dependent; havoc target
   and native-transfer architectural/virtual outputs written by loops. Refuse
   guard, target and memory-refinement proof modes before helper dispatch,
   including zero-root requests. Native transports and direct proof entry
   points recognize the exact colon-delimited v12 token from overall
   `semantic_profile` or site projection, including empty/all-null site
   collections, across all nine proof transports. Recovery separately refuses
   empty domains. Plain saved captures trust validated
   reader-supplied normalized effects bound to v12 captured bytes, profile and
   query evidence. They do not independently replay raw REP BIL/effect
   semantics; the capture trust boundary is unchanged. This introduces no hardware
   partial-fault or general REP acceptance.
4. Add [coverage accounting](../../tools/amd64_coverage.py) with symbolic-form,
   manual-row, transcription-gap and exact-byte domains kept separate.
   Candidate associations bind exact form/case/bytes and input identities but
   establish no authoritative legality or complete template expansion. Rebind
   optional surveys to current source/native observations and recompute their
   classifications. Strict mode writes a deterministic worklist and exits
   nonzero for any unmet full-coverage gate.

Completed finite validation at this record:

- Eight portable projection tests, six consumer tests and the early proof-mode
  refusal test pass. Actual BIL covers six Windows/Linux form/target pairs,
  54 altered-prefix controls and refusal under v10/v11.
- Before final native identity-boundary hardening, three plain REP native
  integration tests pass, including 24 Windows/Linux sequences, full
  native/Rust state equality and hostile saved-capture controls; all eight
  existing advanced regressions pass at that source boundary. The final rebuilt
  helper passes 41 compiled direct controls and 54 framed-dispatch controls,
  95 total, superseding the earlier nine-control run. Its three plain REP native
  tests and one positive old-advanced composition/tampering regression also
  pass. This is a compatibility recheck, not a ninth distinct advanced test.
  All 14 source hashes bound by the final native helper match the checkout.
- Fresh numeric equations pass 720 comparisons. Current root checks pass 439
  default Rust tests (149 ignored), 64 core-only tests (22 ignored), strict
  all-feature/all-target Clippy, formatting and Rust layout (213 sources).
  All four optimized Rust mutants are detected by exact named assertions after
  passing controls, with selected observers/SUT sources restored and campaign
  source stability verified. They completed before final native proof-policy
  hardening; their Rust SUT and selected observers remain byte-identical. The
  later native policy is checked separately by the 95 controls, three plain REP
  tests and positive old-advanced proof recheck against the final helper.
- The completed 171-case v12 native survey records 57 supported projections,
  eight conservative unknowns, 75 missing producer lifts, 28 unsupported
  control/semantics, two encoding disagreements and one query error. All nine
  independent expectations match. PUSHFQ (`9C`) reproduces `BIL AST budget
  exceeded` with direct fresh lifting. The initial all-decoder-EOF local attempt
  lacked the exact library path and earns no semantic credit; the completed
  rerun uses unchanged LLVM 20.1.2 and its matching libxml2 library.
- Fifteen new accounting controls and 31 existing AMD64 inventory/manual/survey
  controls pass. Actual pinned XED accounting reports 10,994 templates,
  10,569 long-mode candidates and 425 exclusions, with all candidates lacking
  authoritative form-to-byte bindings. Fresh byte accounting reports 57
  supported, eight opaque and 106 missing cases; strict mode returns 2 as
  intended. Pinned manual-denominator fields retain 4,118 rows and 2,657 gaps
  even when accepted manual products are omitted.
- The three public pinned PDFs reproduce outline/content/counts and retain
  2,657 gaps. `pdftotext` 26.01 changes the full-layout hash, so unchanged
  strict manual pins reject regenerated outputs. No hash or source pin is
  relaxed. Official-download byte identity for Volumes 4/5, source-row legality
  and exact concrete-domain coverage remain unresolved.

The first default-suite attempt found an old negative test using newly assigned
v12 as an unknown profile; that control now uses unassigned sentinel v999. The
existing guard deadline passes its serial rerun under contention. The initial
mutation attempt was interrupted to correct that fixture and receives no
completed-campaign credit; the later completed four-mutant campaign supplies
its own result. Neither failed default attempt is credited as a
passing gate; the complete final suite supplies its own result. All reports,
transcripts, copied sources, raw
logs and generated build products remain ignored disposable work. Full AMD64
support remains false until every legal form and its exercised concrete domain
satisfy the completion contract; finite REP success supplies no overall coverage
percentage or full acceptance.

### Coverage completion design stages

2026-10-23: the [canonical completion design](../../docs/Ariadne/amd64-coverage-design.md#9-delivery-sequence-and-stop-rules)
specifies the remaining architecture. These execution slices of S1–S5/Q0–Q1
now include the finite C1–C4 work and completed R1 tuple gate recorded below;
C1–C4 retain their broader open exits.
The design's initial publication supplied no runtime/source/encoding qualification;
its later executable findings have their own scopes. Windows unwind stages
remain separate under their existing owner.

| Slice | Program stage | Concrete exit | Status |
| --- | --- | --- | --- |
| C1 — Source scope | S1 | Freeze vendor/publication/extension and mode scope; resolve official Vol4/5 identities or explicitly adopt a reviewed replacement corpus/toolchain. | Partial: candidate v2 reproduces all five volumes; fresh official V1–3 bytes match. Separate official V4r3.27/V5r3.16 inputs now support bounded adjudications; old-pin identity, reviewed adoption and extension/global-rule audits remain open. |
| C2 — Transcription | S1 | Account for selected global rules/appendices and every source region; give each old gap a source-backed disposition with geometry/continuation/footnote ownership. | Historical backlog accounted: 2,657 source-backed dispositions, zero unassigned and seven explicit source-conflict records. All 4,128 pages/11 required region clauses accounted. Seven bounded adjudications and all 33 table relations now pass full source replay. C2 remains partial for corpus adoption, diagram constraints, global rules and footnotes. |
| C3 — Legal domains | S1 | Reviewed legal-form grammar and bidirectional manual/XED dispositions, including AMD forms absent from XED and feature-dependent aliases. | Partial: v3 memory-REP domain enumerates 56 canonical AMD points from 516 source anchors. Vendor denominator, XED reconciliation and wider grammar remain open. |
| C4 — Binding checker | S1/Q0 | Separate authoritative schema; checked domain totality, overlaps and dispatch; solver unknowns and unbound required domains remain open. | Partial: v3 validates 111 fresh profile observations; supported counts are 3/24/28/56 for v12–v15. v15 completes this finite plain-dependency domain; all 10,569 full symbolic-domain bindings remain open. |
| R1 — Memory REP | S2/S4 | Review recipes and fresh BIL for the remaining default-address memory-string tuples; qualify a successor profile while freezing v12. The 28-tuple planning matrix is not an encoding denominator. | Complete for the finite 28-tuple scope: v13/v14 producer/oracle/transport gates, 416 native parity instances, 259 native refusal controls and compatibility regressions pass. Full encoding, fault and proof-consumer coverage remain separate. |
| R2 — Address/prefix variants | S3/S4 | Source-backed address-size, segment and prefix domains with zero-count/upper-lane/width/wrap controls. | Partial implementation: AMD v15 covers 28 default and 28 canonical address-32 tuples; 178,080 oracle comparisons and 448 local capture instances pass. Helper-build migration v1 now passes 448 native parity instances, 341 refusal controls and compatibility; segment/redundant/reordered prefix domains remain open. |
| R3 — Proof consumers | S4/Q0 | Versioned guard/target/refinement/composition capabilities, outcome premises, direct/native replay and refusal controls for empty/all-null domains. | Proposed; open |
| R4 — I/O and faults | S3/S5 | Explicit external I/O state, privilege and partial-completion/restart contracts with independent controls; no normal-only oracle substitution. | Proposed; open |
| A1 — Architecture families | S2–S5 | Close producer/transport/state/projection/control/consumer gaps by legal-form domain, with implementation rules and independently exercised partitions. | Proposed; open |
| Q1 — Scoped full coverage | Q1 | Required source/domain, implementation, consumer and current validation obligations all close for the frozen scope; proof/environmental limits remain stated. | Pending |

Continue the remaining C1/C2 source audit and wider R2 domains after the qualified finite native gate. Keep missing legal
authority distinct from a missing producer lift or an unavailable test runtime.
Do not enable generic F2/F3/While admission or populate mnemonic-only bindings
as a substitute for these exits. Source/tool migrations retain old locks and
receive explicit versioned review; generated transcriptions and run products
stay outside maintained source.


### Source and domain execution: C1–C4

2026-10-23: this executes the [canonical source/domain design](../../docs/Ariadne/amd64-coverage-design.md#101-source-corpus-execution-c1)
while preserving v1 source locks and candidate accounting. Generated PDFs,
transcriptions, observations and reports remain ignored run products.

1. **C1 candidate source corpus.** Freeze candidate AMD long-64 application and
   privileged/system scope with all five APM volumes and five architectural
   subsets. The new source-corpus tool pins publication/PDF identities,
   extractor sources, `pdftotext` 26.01.0, MuPDF 1.27.0, Python 3.14.4,
   89 runtime-library identities, options, locale and schemas. Fresh publisher
   V1/V2/V3 downloads match exact existing pins. Indexed official V4 r3.26 and
   V5 r3.16 content endpoints return HTTP 404; archive-byte equivalence remains
   unverified. Fresh reproduction/check covers all five volumes. Fourteen
   controls pass. Scope/extension review, supplementary publications, global
   rules and versioned migration review remain open; candidate adoption is
   never inferred from equal normalized hashes or a passing products check.
2. **C2 geometry and source ownership.** The first 2026-10-23 pass gave
   1,726 dispositions/931 unresolved; the next added 350. The historical-gap
   completion pass adds the remaining 581: 145 Vol3, 269 Vol4 and 167 Vol5.
   Fresh extraction/check preserves every original ID, ordinal, object and
   source address, with all earlier dispositions unchanged. Current totals
   are 159/1,987/511 dispositions and zero unassigned records. Seven Vol4
   records explicitly retain source conflicts; no intended encoding correction
   is invented. Grouped CMOV/SETcc cells, literal fragments, heading overlays,
   word-box splitting and repeated-line assignments have narrowly bounded
   rules. Material records retain unparsed constraints. Actual fixtures and
   adversarial controls cover all these rules, including omitted/duplicated
   source occurrences and foreign column material. The generic parser's
   refusal controls remain separately exercised.
   Geometry and region products bind the nine-module extraction dependency
   closure; editing a recovery helper invalidates both finite binding registries.
   All five volumes' 4,128 pages and eleven required region clauses pass
   region enumeration/checking. Complete constraint parsing, source conflicts,
   footnotes and all 33 cross-page continuation candidates remain open.
   [Canonical C2 findings](../../docs/Ariadne/amd64-coverage-design.md#102-geometry-and-source-region-execution-c2)
   distinguish `oldGapBacklogClosed` from the still-false C2/source-completeness
   gates. Continue those wider audits, not a deleted or renumbered backlog.
3. **C3/C4 finite legal-domain pilot.** Versioned legal-form/profile-binding
   fixtures enumerate 24 canonical F3 MOVS/STOS/CMPS byte/environment points,
   with three supported and 21 explicit unsupported points for v12 plain
   dependencies. Twenty-four controls check holes, domain narrowing, overlaps,
   unknown grammar/budgets, malformed provenance and stale bindings. Initial
   source-bound producer observations pass 720 independent comparisons and
   the exact-lift Rust admission observer. After source freeze, the final
   historical-gap campaign reseals thirty-nine implementation identities, obtains fresh BIL and
   reruns the oracle/Rust observer; `check --require-bindings` passes. Further
   bound source changes require that fresh campaign again. Full
   source grammar, bidirectional XED reconciliation and implementation remain
   open, and the pilot establishes no vendor-wide coverage percentage.

The historical-gap continuation passes 61 geometry controls, thirteen original
extraction controls, 145 BAP Python tests and 328 tooling tests. Both finite
binding campaigns are rerun with actual BAP and Rust observers after source
freeze: v2 binds 39 implementation sources and v3 binds 61, including all three
volume helpers. The v3 domain remains 56 points/111 profile observations.
The current reading view is refreshed; the preceding 581-gap view is preserved
as a distinct archive version. Record this scoped result in `CHECKPOINTS.md`
and commit/push the continuation under the user's publication instruction.

Run a fresh `tools/amd64_source_corpus.py reproduce` campaign before
`check-products --require-all`; checking a stored product set does not rerun
PDF extraction. Geometry and source-region checks reconstruct their supplied
inputs and retain that fresh extraction premise. Consult the canonical dated
findings for the exact scope and limits. Continue unresolved source audits
independently of REP implementation; do not delete old obligations or relax
source/tool identity checks to produce a passing gate.

### Memory REP execution: R1

2026-10-23: the [successor profile contract](../../docs/Ariadne/amd64-coverage-design.md#104-default-address-memory-rep-execution-r1)
records the 24-form v13 and 28-form v14 default-address scopes. v12 stays frozen.
Two independent LODS builds match; the separate new lock binds actual BAP source
and runtime identity. Source gates pass 4 new typed forms, 38 negative prefix
neighbors, 4 trailing sequences and 10 unchanged baseline observations.
Independent normal-completion equations pass 43,200 comparisons for 24 original
producer forms and 14,400 for 4 source-built LODS forms. Five source controls,
twelve portable transport controls and one actual 4-form/two-target Rust
projection test pass. The user approved the prepared source-only transfer and
the fresh native campaign below closes R1's finite gate. Wider proof-consumer
capabilities remain with R3. No commit or push is requested for this execution.

The local captured-input matrices pass 192 v13 and 224 v14 instances across
OS/count/DF combinations, checking roots/seeds, normalized effects, weak writes,
memory gaps, origins and investigation binding. Final serial default tests pass
457/155 ignored, core-only 64/22, with strict Clippy, format, layout and links.
An initial concurrent run hit an existing guard deadline and receives no credit.
All four optimized compiled loop mutants are detected by named assertions after
passing unchanged controls, with current source identities, isolated builds,
restored SUTs and unchanged observers verified. All 81 BAP Python controls and
304 tooling controls also pass. The separately exercised native campaign passes
all 416 parity instances and 259 direct/protocol refusal controls after a fresh
source-verified build. The v12 saved-capture and old advanced-composition
positive/tampering regressions pass with that same helper.

### Address-size assessment: R2

2026-10-23: the [canonical address-size findings](../../docs/Ariadne/amd64-coverage-design.md#105-address-size-assessment-r2)
record 504 fresh BAP/LLVM observations. All 28 canonical address-32 forms agree
on decoded extent; only four MOVS lifts are nonempty, and those use incorrect
64-bit count/pointers. Thirty-two bounded counterexamples cover low-32 zero
count, high pointer bits and both wrap directions. Three equation controls pass.
Seven hostile prefix families remain raw observations, not admissions. R2 needs
a separately versioned BAP source correction; current profiles stay frozen.

<a id="native-memory-rep-qualification-pending-source-approval"></a>

### Native memory REP qualification

**Completed finite gate, 2026-10-23.** The user explicitly approved the prepared
source-only transfer and native qualification, resolving the earlier automatic
approval-review rejection. The isolated destination is
`/home/jlc/ariadne-rep-20261023`; the payload contains no captures, Git history
or historical evidence. All results below are scoped to the verified sources
and finite fixtures; C1–C4, R2–R4, A1 and Q1 retain their separate exits.

The ordered gates executed were:

1. Verified `target/rep-native-handoff/memory-policy.tar.gz` SHA256
   `6a78e471959a549506ede02e0d47e9e5e0a488fb81f947727cd1933763ff1e0c`
   and every current file in `memory-policy-manifest.json`. The archive contains
   25 current native source/control files. All thirteen existing bound
   Rust/model/legacy inputs also matched before installation.
2. Transferred and unpacked the archive into the isolated `inputs/Ariadne`.
   The original SDK and producer pins remain unchanged. `run.sh` supplies the
   compatible environment; SDK inventory verification passes.
3. Built and checked the fresh native helper inside that launcher:

   ```sh
   python3 native/bap-core/build.py --output target/rep-core-memory-current
   python3 tests/bap/rep_transfer_native_controls.py --native-dir target/rep-core-memory-current --output target/rep-memory-native-controls
   ```

   All 97 direct and 162 framed controls pass, with current source, runner,
   driver, helper and manifest hashes verified. Outputs remain ignored run
   products. Future campaigns require fresh output directories.
4. Retrieved the helper, manifest and bounded control report. All fourteen
   native source identities, the SDK lock and seventeen SDK/compiler/model/
   engine fields match the checkout and pinned SDK. This explicit source audit
   supplements runtime manifest/ready consistency and the runner's four-source
   policy check. The helper SHA256 is
   `b01c3bf697eb53c355c88716b4ee41a0010809bd71c501fbb3ac9be86698a7bf`.
5. Selected the new helper with `ARIADNE_BAP_CORE_DIR`, the advanced flag
   bundle with `ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION`, and the independently
   pinned LODS bundle with `ARIADNE_BAP_LODS_SOURCE_EXTENSION`. Run
   `cargo test --offline --locked --lib memory_rep_recipe_matrix_preserves_roots_effects_and_origins -- --ignored --test-threads=1`.
   This common substring selects both `native_memory_rep_recipe_matrix` and
   `native_lods_memory_rep_recipe_matrix`; the former prefix alone misses v14.
   Both tests pass: all 192 v13 and 224 v14 tuple instances across sixteen
   synthetic capture queries have complete Rust/native state equality and
   every existing effects/origin/query assertion. The v12 saved-capture and
   advanced-composition positive/tampering regressions also pass.
6. Rechecked source/helper identities after execution and updated the canonical
   design, checkpoint and HTML archive. This completes finite R1, without
   closing source/full-domain, address-size, fault or proof-consumer coverage.

### AMD address-size implementation and bindings: R2 / C3–C4

2026-10-23: the [v15 contract](../../docs/Ariadne/amd64-coverage-design.md#107-amd-address-size-rep-implementation-r2)
and [expanded bindings](../../docs/Ariadne/amd64-coverage-design.md#108-expanded-source-to-consumer-bindings-c3c4)
record the next finite slice. R1's prior native results retain their source
boundary; the current v15 native policy needs the fresh gate below.

- Two independent AMD producer builds match manifest
  `815fc8842899d05f6db51aa53cf21b4c82fd50fdae42200b43df4e6735cf48d4`
  and executable `e834c5e9e25a4b2f93de448a01326482493a93430ea1ce43428289b2685c727e`.
  The new pin covers four default LODS and 28 canonical address-32 sequences.
  Four incorrect nonempty MOVS lifts are replaced under explicit selection;
  all 28 default-address behaviors are preserved.
- AMD Ryzen 9 7950X and Intel Core 5 220H probes expose different zero-count
  upper-lane behavior. v15 binds an AMD premise and records it per address-32
  site; an AMD64 target label does not establish CPU vendor. Both hosts confirm
  contiguous element access across 4 GiB followed by 32-bit index wrapping.
- The independent oracle passes 178,080 comparisons and 15 runtime refusals;
  fifteen portable oracle controls and fifteen transport tests pass. The latter
  include 64 actual form/target cases. All 448 local capture instances pass with
  high count/index bits, exact premises, effects, origins, roots and memory gaps.
- The separate v3 registry has 56 points and 516 source anchors. Fresh producer
  queries and Rust admission validate 111 profile observations, with supported
  counts 3/24/28/56 for v12–v15. All 47 checker controls and the refreshed v2
  campaign pass. All 10,569 candidate full-domain bindings remain open.
- Current root gates pass 472 default Rust tests/159 ignored, 64 core-only/22
  ignored, Clippy, format, layout, 107 BAP Python and 327 tooling controls.
  Four optimized loop mutants are detected after passing unchanged controls;
  source restoration, observer identity and the frozen source inventory verify.

<a id="native-amd-address-size-qualification-pending-approval"></a>

### Native AMD address-size qualification: finite gate completed

**Completed local successor:** the [reviewed helper-build migration](../../docs/Ariadne/amd64-coverage-design.md#1012-helper-build-migration-v1-and-renewed-finite-qualification)
closes the finite gate with current core identity audit, 341 refusal controls,
448 native parity instances and named compatibility. The remote handoff below
is the earlier unexecuted proposal, superseded by local recovery; no transfer
was needed. Its historical approval discussion does not block this local gate.

At the earlier checkpoint, automatic approval review rejected the changed v15
source/control payload because prior approval covered the earlier handoff.
Specific approval was requested for the isolated `win10` destination. The
following procedure was pending then; the local successor above now supplies
native qualification without executing that transfer.

1. After approval, verify `target/rep-native-handoff/address-policy.tar.gz`
   SHA256 `ac080543a2951b6606e87d63d3085f6f5df9d2c829553182443b970cfdae2440`
   and `address-policy-manifest.json` against all 25 current files. Transfer
   this source-only payload to `/home/jlc/ariadne-rep-20261023` and verify/install
   with `verify_install_address.py`; no captures or history are included.
2. Through the compatible `run.sh`, run
   `python3 native/bap-core/build.py --output target/rep-core-address-current`,
   then `python3 tests/bap/rep_transfer_native_controls.py --native-dir target/rep-core-address-current --output target/rep-address-native-controls`.
   Require 125 direct plus 216 framed controls, 341 total.
3. Retrieve the new helper, manifest and report into ignored work. Audit all
   fourteen native sources, SDK lock and seventeen SDK/compiler/model/engine
   fields against current inputs; manifest/ready consistency alone is insufficient.
4. Select that helper with `ARIADNE_BAP_CORE_DIR`, the advanced flag bundle and
   `ARIADNE_BAP_REP_ADDRESS_SOURCE_EXTENSION=target/rep-address-build-a01/runtime`.
   With pinned BAP/LLVM dependencies, run
   `cargo test --offline --locked --lib native_amd_address_memory_rep_recipe_matrix_preserves_roots_effects_and_origins -- --ignored --test-threads=1`.
   Require 448 native/Rust parity instances and recheck v12 saved-capture plus
   old advanced-composition positive/tampering compatibility with the same helper.
5. Verify final source/artifact stability and update the canonical/checkpoint/
   archive results. Wider prefix/segment and full AMD64 gates remain separate.
