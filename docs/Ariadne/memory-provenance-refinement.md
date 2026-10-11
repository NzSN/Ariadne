# Memory provenance refinement for Scanner

## Context and follow-up

**Status.** Source implementation and finite probes added on 2026-10-11 from
`8007236`: candidate-preserving symbolic assessment, opt-in transfer evidence,
bounded scalar predecessor inference, a strict separate report and CLI mode.
The original source inspection used `53fe1ff` and the retained Scanner record.
The independent oracle is frozen; source/root checks and small pinned-runtime
probes pass. Remote model checking, real-code mutations and the full Scanner
campaign remain pending, so the complete design is not yet qualified.

**Why this document exists.** The [Scanner resume record](bap-analysis-core-design.md#admission-resume)
preserves a completed but partial explanation. Its `unknown-memory-alias` gaps
expose both the shared memory abstraction and conservative unknown-output
dependencies. The [investigation design](investigation-design.md) requires
these limits to remain visible while making possible origins more useful.

**What this document establishes.** A bounded recommendation: clarify the
diagnostics, then assess individual candidate memory writers for one selected
load using captured access expressions and justified address relations. Reuse
the completed analysis and preserve every unresolved alternative. For the later
numerical layer, distinguish exact values, surviving constraints and unknowns;
stop only an affected expansion that has no useful admitted constraint left.
The implementation section identifies existing seams, missing transfer evidence,
proposed types, algorithms, limits and report validation.

**Where to go next.**

- [Active specification synchronization](../../Plans/specification-sync.md) —
  current finite scalar/alias model and its separate remote-check boundary.

- [Implementation plan](../../Plans/memory-provenance-refinement.md) — M0–M4
  contract, symbolic assessment, backward values, product and qualification.

- [Investigation contracts](investigation-design.md) — exact query binding,
  before-instruction address expressions and permitted explanation claims.
- [Bounded frame-path query](investigation-design.md#bounded-frame-to-frame-path-listing)
  — frame evidence and fewer than `NP` listed alternatives; an incomplete path
  list cannot justify excluding a memory writer.
- [BAP projection contract](bap-analysis-core-design.md#projection) — current
  load/store effects and the prohibition on killing the whole memory cell.
- [Analysis model](../../Specs/Ariadne.tla) and
  [formal-model guide](../../Specs/README.md) — authority for existing transfer
  rules and the starting point for a proposed refinement contract.
- [Investigation module](investigation-design.md#investigation-module-and-interface) — ownership and current bound
  result interfaces; implementation planning follows an explicit design/model
  contract and must be linked here when created.

**What remains unresolved.** General memory regions, loop-instance identities,
joint machine-state reconstruction and broader inverse operations remain outside
the first finite profile. The new model still needs remote checking, and the
mutation/Scanner acceptance clauses need their source-bound campaigns. No
executed writer or bad-RSI cause is established. The
[accepted P4 scope](file-reader-design.md#windows-replacement-capture-and-bounded-query)
qualifies its earlier implementation and corpus rather than these changed sources.

## The concrete Scanner problem

The retained query has entry `0x7ff77443d960` and fault seed
`0x7ff77443dd6e`. Its explanation records this immediate dependency:

```asm
0x7ff77443dd6a: mov rax, qword ptr [rsi+0x28]
0x7ff77443dd6e: cmp byte ptr [rax+0x38], 0x76
```

All eight RAX-byte origin groups identify the load at `0x7ff77443dd6a` as their
sole immediate instruction producer under the recovered graph. The unanswered
memory question is which earlier write could have supplied the eight bytes
loaded into RAX.

The current projection places every load and store in one abstract location,
`memory:any`. A load depends on that cell and its address inputs. A store adds
a possible definition of the cell, while preserving earlier memory origins:
writing one range cannot overwrite all modeled memory.

At this load, the retained explanation has 12 memory-origin alternatives:
one entry-memory origin and 11 instruction origins, comprising eight stack
pushes and three stores. They are candidates admitted by the coarse model;
they do not establish that each write touched the loaded bytes.

The [retained summary](../../evidence/Ariadne/bap-admission/remote-20261010/report.json)
records five `unknown-memory-alias` labels:

| Site | Instruction | Relevant limitation |
| --- | --- | --- |
| `0x7ff77443dd6a` | `mov rax, [rsi+0x28]` | Loaded value depends on the shared memory cell. |
| `0x7ff77443d973` | `mov rax, [rip+...]` | The projected address is already the constant `0x7ff77c9b2040`; its memory provenance is still coarse. |
| `0x7ff77443d986` | `mov rax, [rcx+0x18]` | Known symbolic address expression, unresolved memory provenance. |
| `0x7ff77443d98e` | `mov rax, [rcx+0x20]` | Known symbolic address expression, unresolved memory provenance. |
| `0x7ff77443d97a` | `xor rax, rsp` | No memory access; undefined AF introduces conservative dependencies on every tracked location. |

Thus five labels describe four actual loads and one unknown-output
overapproximation. They do not imply five missing numerical addresses.

The detailed counts above come from member
`artifacts/0/external/scanner/explanation.json` in the
[retained archive](../../evidence/Ariadne/bap-admission/remote-20261010/evidence.tar.gz).
Its SHA-256 is
`f48ca41bd52bdd233cf115c19f14a9f73d04ac02d8aa155f8c77793a9959892a`,
verified against the [member manifest](../../evidence/Ariadne/bap-admission/remote-20261010/evidence-manifest.json)
during this inspection. This is retained-evidence inspection, not a new
Scanner execution.

## Recommended design direction

### Clarify diagnostics before changing dependency semantics

Distinguish a load's unresolved memory provenance from uncertainty introduced
by an undefined output. Preserve the original evidence and the uncertainty.

The current [BIL projector](../../src/bap/projection.rs) gives `Expr::Unknown`
dependencies on all catalogue locations. It then unions the dependencies of
changed outputs into one instruction-wide `uses` set. The
[producer visitor](../../src/investigation/explain.rs) emits
`unknown-memory-alias` whenever that set contains `memory:any`.

This explains the XOR label. Improving its wording is separate from narrowing
its dependency set. Narrowing requires reviewed per-output semantics and
regressions; merely deleting `memory:any` would discard a conservative fact
without replacing its justification.

### Assess access pairs over the completed analysis

Use a separate, bounded alias assessment over the immutable
[`BoundInvestigation`](../../src/investigation/validate.rs). Retain the original
core result and attach evidence-backed findings to individual access pairs.
Do not rerun discovery with invented roots or silently rewrite the original
reaching-definition sets.

[`AddressUse`](../../src/investigation/model.rs) already carries the access
index, load/store role, width, affine address expression, address inputs,
attribution and gaps. These are useful inputs, but they do not establish
cross-instruction register-value equality by themselves.

For each candidate writer to the selected load, report:

| Finding | Treatment | Evidence needed |
| --- | --- | --- |
| Proven disjoint byte ranges | Exclude from the refined candidate view only within the proven scope. | Bound access identities, widths and an address relation covering all represented relevant instances. |
| Proven overlapping byte ranges | Retain as a possible writer. | Bound overlap relation; overlap alone does not establish execution or last-writer status. |
| Unknown relation | Retain with an explicit reason. | Missing base identity, unsupported expression, unresolved paths, calls, loops or exhausted assessment limits. |
| Entry memory | Retain unresolved earlier provenance. | Additional accepted evidence is needed to identify earlier writers. |

A pair-specific proof may explain two accesses without excluding an entire
static producer site. If other represented executions of that site remain
unresolved, its candidate must remain.

This separation follows a useful established design pattern: query aliases
using an address and access size, then consult those results while traversing
memory definitions. See the primary descriptions of
[LLVM alias queries](https://llvm.org/docs/AliasAnalysis.html) and the
[MemorySSA walker](https://www.llvm.org/docs/MemorySSA.html). They are design
references; BAP remains Ariadne's semantic producer under its existing
[trust boundary](semantic-assurance.md).

### Start with constants and justified equal-base relations

Numerical register reconstruction is unnecessary for some useful exclusions.
For two eight-byte accesses with the same base value:

```text
store: [base + 0x18, base + 0x20)
load:  [base + 0x28, base + 0x30)
```

The ranges are disjoint. Scanner has a store at `0x7ff77443dd66` using
`[rsi+0x18]`, immediately before the selected load using `[rsi+0x28]`.
The relation is a useful first local case, conditional on the same RSI value
for the compared executions. Any address comparison must respect the modeled
64-bit arithmetic, access width and wrapping behavior.

Across a larger graph, the same register name or defining instruction site
does not prove the same runtime value. Core
[`Definition`](../../src/model.rs) identities contain location, site and origin
kind; they do not distinguish loop iterations. Begin with exact constants or
a proved unchanged base across the relevant paths. Otherwise report unknown.

Never partition memory into disjoint regions solely because one address uses
RSP and another uses a different register. A register can point into the stack,
and captured crash-time values do not automatically describe earlier accesses.

### Preserve interaction with unknown memory

`memory:any` must continue to overlap every precise region. It cannot become
a disjoint "other memory" cell alongside named regions. Unknown stores and
opaque calls must retain possible effects on any candidate range.

The [current transfer](../../Specs/Ariadne.tla) removes origins by exact
location membership in `must_defs`. A precise store cannot justify adding
`memory:any` to that set. Introducing overlapping memory regions into the core
would require an explicit new contract rather than a change of location names.

This is why the first recommendation is a query-specific assessment that
preserves the original result. Even a fully overlapping store remains a
possible writer until ordering, intervening writes and other relevant
premises are established.

### Add backward numerical constraints later

After access-pair reasoning can consume value constraints, add a separate,
bounded numerical layer over the same completed analysis. Its first scope is
reviewed straight-line relations such as `rax_after = rax_before + 8` modulo
2^64. The current
[fault-context contract](zero-address-design.md) binds register observations at the
selected exception instruction; extending them backward requires its own
justification. A recovered edge is a possible transition, not evidence that it
executed. Every result remains conditional on its admitted semantic and path
premises.

#### Precision outcomes

Use three proposed value outcomes, independently of whether expansion continues:

| Outcome | Meaning | Treatment |
| --- | --- | --- |
| `Exact` | One earlier bitvector is established within the declared premises and scope. | Continue through supported predecessors within the budget. |
| `Constrained` | Several earlier values remain, with a useful admitted predicate, known bits or value relation. | Preserve the constraint and continue where supported; lack of a unique value is not a stopping reason. |
| `Unknown` | No useful numerical constraint on this value can be established from the admitted evidence and relations. | Stop this numerical expansion with an explicit boundary; preserve provenance and independent facts. |

These are proposed precision categories, not additions to the existing
explanation schema. A `Constrained` or `Exact` result may also reach an unsupported
predecessor or exhaust its budget. Retain its established facts and record why
further expansion stopped; do not downgrade them to an unconstrained value.

For an admitted instruction relation `R`, reverse inference computes possible
predecessors rather than assuming a unique inverse:

```text
Before = {s | there exists t in After with R(s, t)}
```

The result must cover every predecessor compatible with the declared premises.
At joins, preserve the alternatives and their scope; never select the apparent
crashing branch from a later register value alone. An empty predecessor set
means that the admitted relation and constraints are inconsistent. Record that
conflict rather than converting it to an ordinary unknown or dropping a path
without a justified exclusion.

#### Stop only the affected numerical expansion

Stop at information loss when the admitted relation supplies no useful earlier
constraint for the requested value. Apply the boundary to that value, program
point and path/instance scope, not to the whole instruction, slice or query.

Preserve partial bits, constraints on other values, unchanged memory ranges and
established address relations. Independent captured-instruction evidence or
forward facts may still constrain the earlier value even when inversion through
one instruction is uninformative. Continue existing provenance traversal and
independent alias checks; retain unresolved memory-origin candidates.

Distinguish information erasure from unsupported semantics, an unresolved
predecessor/call, unavailable memory history and budget exhaustion. An exact
inverse may exist mathematically while the admitted model or evidence is
insufficient to use it. None of these boundaries justifies fabricating a value,
discarding unknown origins or declaring the explanation complete.

Each stopped expansion must record:

- Requested location, bit width, program point and bound query/snapshot identity.
- Boundary instruction and the reason expansion stopped.
- Surviving constraints and value relations, with their premises and evidence.
- Covered predecessor alternatives and any unresolved path/instance scope.
- Applicable resource limit and truncation status when a budget was exhausted.

A static defining site is not a dynamic value version across loop iterations.
If that distinction is needed but cannot be established, retain the unknown
scope instead of identifying values solely by register name or producer site.

#### Examples and information-loss boundaries

These examples assume the stated instruction relation connects the before and
after states; they do not assert that a captured instruction executed.

| Instruction and later evidence | Earlier result | Expansion decision |
| --- | --- | --- |
| `add rax, 8`, later RAX = `0x1008` | `Exact`: earlier RAX = `0x1000`, using 64-bit modular arithmetic. | Continue through supported predecessors. |
| `and rax, 0xff`, later RAX = `0x34` | `Constrained`: `(earlier RAX & 0xff) = 0x34`; upper bits remain unknown. | Preserve the low-byte constraint and continue where useful. |
| `xor rax, rax`, later RAX = zero | `Unknown` for earlier RAX through this relation: every earlier RAX gives the same register result. | Stop this RAX inversion; other evidence and provenance remain usable. |
| `mov rax, [rcx]`, later RAX known but earlier memory unavailable | The loaded value does not uniquely determine RCX or the writer; multiple addresses may hold the same value. | Retain the load dependency and stop unsupported address/content inversion unless additional admitted constraints exist. |
| A store overwrites eight bytes with zero | Earlier contents of those bytes may be unknown; other memory can retain its established relations. | Bound the loss to the affected range; never treat the store as erasing all memory history. |

Numerical uncertainty also does not prevent a symbolic alias result. Two
eight-byte accesses at `[base+0x18]` and `[base+0x28]` remain disjoint under a
justified equal-base relation even when the base number is unknown. Preserve
that relation and its dynamic scope while stopping any uninformative numerical
expansion of the base.

General reverse execution and a memory solver are larger design steps. They
are not prerequisites for constant-address or justified equal-base checks.

## Implementation details

The [implementation plan](../../Plans/memory-provenance-refinement.md) tracks
M0–M4. The source now supplies the entry point and separate v1 report described
below; the model and complete qualification gates remain pending. Logical type
sketches are explanatory where their names differ from the exported Rust types.

### Ownership and entry point

Keep refinement above the completed core analysis, with a small question-specific
interface. All Rust implementation and generated bindings remain under `src/`;
standalone tests and fixtures remain under `tests/`.

| Responsibility | Existing seam | Proposed addition |
| --- | --- | --- |
| Completed request and state | [`AnalysisView`](../../src/analysis_view.rs), [`BoundInvestigation`](../../src/investigation/validate.rs) | Private `BoundMemoryRefinement` combining the original bound analysis with validated refinement receipts. |
| Access expression and footprint | [`AddressUse`](../../src/investigation/model.rs), [BAP address projection](../../src/bap/address.rs) | Scoped access keys and checked byte-range comparison in `src/investigation/memory_refinement.rs`. |
| Instruction transfer relations | [BAP preparation](../../src/bap/prepare.rs), [typed AST](../../src/bap/ast.rs) | Bounded normalized transfer receipts in a proposed private `src/bap/refinement.rs`. |
| Numerical domain and inverse worklist | No current general inverse evaluator | `src/investigation/backward_values.rs`, using the admitted receipts and per-value stopping policy. |
| Capture/query binding | [`bind_investigation`](../../src/input/investigation.rs) | Capture-owned binding of receipts and optional reader-owned fault observations, without another helper or core-analysis run. |
| Strict report and rendering | [Existing investigation codec](../../src/reports/investigation.rs) | Separate codec/renderer in `src/reports/memory_provenance.rs`; existing explanation v1 remains the baseline result. |

The proposed public operation is conceptually:

```text
assess_memory_origins(
    bound: &BoundMemoryRefinement,
    selected_load: AccessKey,
    limits: MemoryRefinementLimits
) -> Result<MemoryProvenanceAssessment, Error>
```

`AccessKey` includes snapshot/query binding, instruction VA and the exact BIL
access index. Reject mismatched identities, out-of-domain VAs, invalid indices
and store-role questions independently of resource budgets. A valid access with
unavailable semantics or an unsupported expression yields an explicit unavailable
assessment; it never becomes a discovery root. Keep bound fields private and
expose immutable results only after validation.

### Retain the missing transfer evidence during preparation

Today, [`SemanticEvidence`](../../src/effects.rs) retains the AST hash and memory
access evidence, while `BoundInvestigation` retains request/state/site evidence.
Neither retains the BIL expressions needed to reconstruct register assignments.
`uses`/`may_defs`/`must_defs` identify effects and origins; reversing those sets
cannot recover an arithmetic relation.

During the original, successful BAP preparation, retain a bounded optional
refinement sidecar containing canonical typed BIL and normalized transfer
receipts. Generate it only after exact-byte, decoded-control, operand and typed
admission succeed. Bind each receipt to VA/bytes, target, helper/runtime hashes,
AST hash, projection identity and a separate refinement-profile version. The
existing serialized BIL bytes must hash to the recorded `ast_sha256`.

Normalize sequential BIL assignments and virtual temporaries into expressions
over before-instruction architectural values. Record destination bit ranges,
preserved bits, definite versus conditional replacement, memory-access
attribution and unknown-output reasons. A virtual-variable name is not a
cross-instruction value identity. An unsupported relation or opaque instruction
is a barrier, with its original conservative effects retained.

At binding, recompute the normalized receipts from the retained, hash-checked
AST using the same bounded extractor and validate their source attribution.
The hash binds identity; it does not prove the extractor correct. Independent
tests and the frozen model establish its finite conformance obligations.
This sidecar is not silently inserted into a strict existing report schema.

If a retained analysis has only an AST hash and no sidecar, symbolic comparisons
can still use its admitted `AddressUse` facts. Report transfer evidence as
unavailable for numerical inversion; do not re-lift instructions, invoke LLVM
effects or reread crash-time memory as earlier memory.

### Types and scoped value facts

Use the original [investigation identity](../../src/investigation/model.rs) and
add a digest of the selected access, refinement profile, sidecar, premises and
limits. Suggested logical records are:

```text
ValueKey       = {program_point, location, width, instance_scope}
ValueFact      = Exact(bitvector) | Constrained(predicate) | Unknown(reason)
Expansion      = Active | Stopped(boundary, reason) | Conflict(evidence)
Candidate      = {original_definition, store_accesses, disposition, evidence}
Disposition    = Retained | ExcludedWithinScope | Unresolved(reason)
PairFinding    = Disjoint(witness) | Overlapping(witness) | Unknown(reason)
```

Precision and expansion status are separate: stopping at a budget preserves an
already established `Exact` or `Constrained` fact. `instance_scope` describes
the justified path/value scope or explicitly records its absence; it is never
an invented loop-iteration ID. Bitvectors use canonical width-checked unsigned
representations, without floating-point conversion.

A whole-GPR fact must share a compatible state/premise scope across all eight
tracked bytes. Independently choosing byte origins from merged reaching sets
does not establish that they co-occurred as one pointer. Without that relation,
retain partial facts and alternatives instead of constructing an exact 64-bit
value from unrelated byte producers.

The first constraint vocabulary needs constants, known-bit masks and bounded
symbolic equalities/predicates over admitted modular expressions. Keep dependency
and premise references with each fact. Do not claim a singleton, inconsistency
or alias exclusion merely because a predicate was constructed: the relevant
checked rule must establish that conclusion.

### Candidate collection and range comparison

For the selected load, read definitions with location `memory:any` from the
completed state's reaching set before that instruction. Freeze the complete
candidate universe before evaluating exclusions. Preserve entry origins and
the identity of every instruction-origin candidate.

For each instruction origin, consult its admitted memory accesses and footprint
receipt. A candidate with multiple possible stores can be excluded only if all
of them are proved disjoint in the covered scope. Opaque calls, ordinary opaque
effects, missing expressions and incomplete footprints remain unresolved.
Absence of a recorded store is not proof of no memory effect.

The first alias evaluator supports:

1. Two constant addresses with admitted access sizes.
2. Two expressions sharing a proved identical base value and coefficient, where
   their constant offsets and sizes determine overlap.
3. Unknown for everything outside those checked cases.

The first alias profile admits 8/16/32/64-bit accesses with 64-bit addresses;
other widths remain unknown until their contract is added. Convert bit widths
to bytes only after this admission.
For a start `a` and length `n`, represent the modular byte range using `u128`
intermediates and split at 2^64 when needed. Compare both pieces. For a common
base, translation invariance permits comparison of the offset ranges under the
same modular semantics. Overlap covers any shared byte, not merely equal starts.

Establish base identity from admitted relations or preservation of every
relevant register byte across all covered paths. The initial cross-site
equal-base witness should require a closed acyclic relevant prefix, without an
unknown call/effect or relevant recovery obligation that can invalidate the
witness. A proof for an adjacent execution pair does not exclude another
dynamic instance of that static store. Cyclic or incompletely covered cases
retain candidates until a stronger scope contract exists. Constant-address
comparisons need no dynamic base witness, but still require complete bound
footprints and retain all independent recovery gaps.

Return exclusions as additional witnesses attached to the original candidates.
Keep the original core graph, reaching sets, slice, `memory:any` and definite-write
rules intact. Never interpret an `Overlapping` finding as a last-writer proof.

### Backward worklist and first numerical profile

The first inverse evaluator handles reviewed whole-GPR 64-bit copies,
add/subtract by a known constant, AND with a known mask and constant-result
overwrites. It works from normalized BIL relations, not opcode spelling.
Narrow/partial writes, zero extension, conditional assignments and other widths
need explicit transfer rules and independent cases before admission.

For numerical seeding, use only capture-owned observations validated at the
selected exception instruction/access under the new refinement profile. The
existing MOV-only zero-address profile does not automatically admit Scanner's
CMP or justify values at its earlier pointer load. Without an admitted seed,
continue symbolic alias assessment and retain a numerical unknown.

```text
enqueue(seed value fact, bound premises)
while work remains within the limits:
    take a deterministic value/program-point task
    obtain its admitted predecessor alternatives and transfer receipts
    compute a sound predecessor fact for each supported alternative
    preserve partial constraints and record each independent barrier
    enqueue only new useful facts, keyed by value scope and premises
validate candidate coverage, witnesses, boundaries and result identity
```

Use substitution into bounded predicates when a supported inverse does not
produce a singleton. Keep alternative path predicates separate before forming
a conservative union. A generic load cannot be inverted from its loaded value
to a unique address; an erased value stops that expansion. Preserved unrelated
values remain eligible for their own tasks.

Memoization keys include program point, location/width, instance scope,
constraint digest and premise digest. A site-only cache would conflate loop
instances and different constraints. Unsupported loops stop scoped expansion
rather than triggering guessed iteration counts. A proved empty predecessor
set produces an explicit conflict or checked model-relative exclusion; it
cannot silently become an ordinary unknown.

### Limits, diagnostics and publication

The current implementation uses these defaults:

| Limit | Default |
| --- | ---: |
| Candidate origins admitted for a refined table | 128 |
| Access-pair comparisons | 4,096 |
| Numerical worklist tasks | 4,096 |
| Numerical predecessor alternatives expanded across the assessment | 256 |
| Assessment graph nodes | 8,192 |
| Numerical path and expression depth | 64 |

These counters bound assessment work, but do not supply an assessment-wide
deadline or a hard RAM limit. Input validation runs before the refinement
input-size checks, and common-base proofs traverse the recovered graph.
The CLI currently uses the defaults; library callers can supply
`MemoryRefinementLimits`. Instruction discovery is bounded separately by
`--max-starts`.

Check counters and sizes before allocation or expansion, with overflow-safe
arithmetic. Admission and identity checks still run when limits are zero;
exhaustion never relaxes them. If the complete candidate universe exceeds the table limit, return
a bounded unavailable refinement with the total count and base-result identity;
the original analysis retains every candidate. Exhaustion during assessment
marks remaining candidates unresolved and records truncation. It never grants
an exclusion or discards already established constraints.

For the XOR case, use per-output receipt attribution to explain the undefined-AF
dependency separately from actual load/store provenance. This first assessment
does not narrow the existing instruction-wide effect summary or rewrite its
baseline gap. Changing those semantics requires a separately reviewed profile
and projection/native/report regression campaign.

Publish a separately versioned proposed
`ariadne.memory-provenance-assessment/v1` envelope. Include the base identity,
selected access, profile/receipt/premise digests, limits, original candidate
coverage, pair witnesses, numerical facts, boundaries, conflicts and gaps.
Strict validation rejects duplicate/unknown fields, noncanonical values,
dangling evidence, wrong identities, excluded entry origins and exclusions
without complete scoped witnesses. Completing the assessment does not make the
original fault explanation `explained`.

JSON, text and DOT must derive from one validated result. Integrate opt-in
publication through the [existing CLI](../../src/bin/ariadne-minidump.rs) only
after the schema and invocation contract are frozen; keep default behavior and
original report bytes as the compatibility baseline. A failed admission is an
error, not an accepted empty candidate set. No numerical confidence or
executed-writer/root-cause claim is introduced.

### Model, oracle and implementation acceptance

Specify the new assessment and stopping rules in an analysis-level model,
proposed `Specs/AriadneMemoryRefinement.tla`, before runtime implementation.
Model candidate preservation, scoped exclusion, numerical precision versus
stopping, conflicts and budget exhaustion. This extends analysis assurance;
it does not revive the retired instruction-step/Lean track.

Use independent Python-integer modular-range expectations and exhaustive
small-width predecessor sets as the oracle, plus hand-reviewed 64-bit boundary
vectors. Proposed standalone tests belong in
`tests/investigation/memory_refinement.rs` with oracle data under
`tests/investigation/fixtures/`; hostile codec tests belong with the existing
report contracts. Generated bindings remain compiler-owned under `src/`.

Validate wrong query/AST/receipt identities, incomplete store footprints,
partial overlaps and wrapping, lost information with surviving relations,
unsupported prefixes/operations, loops, opaque calls and every exact budget
boundary. Mutations must detect an unjustified exclusion, a widened memory kill,
a guessed pre-state or a dropped constraint/barrier. The exact Scanner candidate
table then becomes one retained acceptance case with source/tool/receipt hashes,
not a substitute for the independent oracle.

## First milestone and validation boundary

The first milestone should be a candidate table for the selected Scanner load:
each of its 12 retained origins is kept or excluded in the refined view, with
the exact access evidence, rule, premises and unresolved scope recorded. The
outcome may legitimately retain all candidates if the available proofs are
insufficient. Success is a justified precision result, not merely changing the
answer from `partial` to `explained`.

Before implementation, define the bounded result/model contract and independent
expected outcomes for at least:

- Equal-base disjoint, equal-start, partially overlapping and mixed-width accesses.
- Constant addresses, address wrapping and unsupported address expressions.
- Register redefinitions, joins, loop iterations and unknown call effects.
- Unknown memory interacting with every precise region; no global must-kill.
- Undefined AF remaining visible without falsely describing a physical XOR load.
- Missing evidence and budget exhaustion preserving unresolved candidates.
- Exact inversions, partial-bit constraints and complete register erasure, with
  the expected `Exact`/`Constrained`/`Unknown` result and boundary metadata.
- A stopped value expansion leaving independent provenance, other register
  constraints and symbolic alias checks intact.
- Memory overwrite affecting only the justified range, without replacing
  earlier contents by crash-time captured bytes.
- Contradictory predecessor constraints remaining explicit rather than becoming
  a fabricated value, an ordinary unknown or an unjustified path exclusion.

Separate diagnostic changes from semantic dependency changes in that design.
Runtime work must follow the relevant root, model, native and investigation
qualification contracts. Heavy build/model/mutation and large-query work
remains remote. This documentation change provides no new runtime acceptance.

## Implementation checkpoint (2026-10-11)

The [source-bound validation record](../../evidence/Ariadne/memory-refinement/source-validation.json)
records the exercised tiers and failed/unexercised prerequisites. The
[model revision](../../evidence/Ariadne/memory-refinement/contract-revision.json)
binds the corrected type-annotation placement while preserving the original
freeze. Neither record grants full design acceptance.

The source API is `bind_memory_refinement(prepared, completed)` followed by
`assess_memory_origins(bound, question, limits)`. Existing analysis state and
the baseline explanation are retained. Receipt retention is explicitly enabled
through `FileSnapshot::prepare_with_bap_refinement`; ordinary preparation keeps
its previous behavior and report bytes.

The opt-in product invocation is:

```sh
target/debug/ariadne-minidump DUMP --decoder-reference target/ariadne-llvm-mc \
  --entry ENTRY --seed FAULT --assess-memory-provenance LOAD \
  --memory-access 0 --assessment-only --format json
```

This question selects an already discovered load and adds neither a discovery
root nor an implicit slice seed. Output-directory mode publishes the unchanged
base report and `memory-provenance.txt`, `.json` and `.dot` together. The separate
schema is `ariadne.memory-provenance-assessment/v1`; decoded assessments recompute
the result from their bound evidence inputs, and `validate_for` additionally
checks equality with a live bound analysis.

The numerical seed profile admits coherent Windows AMD64 access violations at
ordinary scalar memory instructions with supported address evidence. It checks
exception/context identity, reported operation/address, the captured GPR validity
groups and the inherited lower-range access guard. It does not reuse the MOV-only
question as permission for other forms. Scalar records are path-scoped and
`derived_under_premises`; they do not claim jointly reconstructed pointers.

The [independent contract freeze](../../evidence/Ariadne/memory-refinement/contract-freeze.json)
binds 784 modular-range cases and 1,280 exhaustive small-width inverse cases.
The source regressions check entry/candidate preservation, constants and common
bases, loops/recovery gaps, budgets, invalid questions, forged exclusions,
receipt alterations, register-bank mapping and independent numerical barriers.
The controlled five-node pinned-lifter probe preserves the baseline JSON bytes
and distinguishes unknown-output dependencies. A one-site Windows capture
exercises RBX/RCX seeds and exact native/Rust assessment parity using the restored,
hash-verified accepted native helper.

The cached older helper failed the completion-capability handshake; that result
is a prerequisite failure, not a semantic pass. Restoring the exact accepted
binary from sealed evidence allowed the finite probe without rebuilding the SDK.
These small checks do not qualify the full Scanner workload or replace the
pending model/mutation campaign. The execution ledger preserves that boundary.
