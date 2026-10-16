# Resolver pattern matching in structural type theory

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

**Ariadne currently has one indirect-target resolver. Its two target-producing shapes form a sum type: `Relative32 + Pointer64`. Loop properties belong to a separate context, so a relative-table expression can also occur inside a loop. Matching a shape supplies evidence about its structure; completeness requires additional semantic checks.**

Here, “structural type theory” means tagged sums, records/products, structural views, and predicate refinements. The notation below is explanatory pseudocode, not executable Rust or a newly checked formal specification. The existing TLA+ models retain their authority. The proposed general loop-invariant rule is marked explicitly.

For the requested patterns, jump to [11. Abstract syntax](#11-abstract-syntax) and [14. Statics and pattern rules](#14-statics-and-pattern-rules). For overlap with the proposed loop rule, read [19. Model-versus-implementation analysis](#19-model-versus-implementation-analysis).

## 1. Purpose and module boundary

The resolver reconstructs possible indirect-jump destinations from admitted BIL, a fixed candidate graph, captured control-data bytes, branch constraints and finite budgets. It owns symbolic reconstruction, target recognition and receipts. Input materialization owns discovery and captured reads; Rust/native admission independently checks receipts.

Source: [target resolver](../../src/bap/target_resolution.rs#L945), [materialization coordinator](../../src/input/materialize.rs#L682), [native checker](../../native/bap-core/capture.ml#L493).

## 2. Concrete implementation

Rust stores a `Term` record containing a width and a tagged `TermKind`. Its variants are constant, input, unknown, binary operation, unary operation, cast and load. `PathReceipt` stores a string `form` and common fields for paths, guards, indices and table entries. `Resolution` stores targets, receipts, a Boolean `complete` and unresolved reasons.

The coordinator selects rooted `resolve` or local-candidate `resolve_candidate`; both enter `resolve_inner`. That function searches backward, rewrites terms and guards, recognizes bounded target forms and reads captured table slots. It borrows the graph and transfers, owns its worklist/results, and mutates finite counters and a captured-read cache. No concurrent resolver arbitration occurs here. Invalid evidence is an error; unsupported contexts and exhausted work can produce incomplete results.

Source: [term representation](../../src/bap/target_resolution.rs#L89), [receipt representation](../../src/bap/target_resolution.rs#L480), [mode selection](../../src/input/materialize.rs#L722).

## 3. Concrete invariants

| Invariant | Enforcement |
| --- | --- |
| A recognized `relative32` expression uses the same concrete base for table addressing and offset addition | Runtime equality tests in `relative` |
| Recognized indices contain no `Unknown` term | Runtime structural check |
| Candidate entries remain tied to captured reads and signed-offset arithmetic | Runtime receipt validation |
| A complete row has no unresolved reason or stopped report and has coverage receipts | Runtime validation |
| Completeness covers all incoming reverse contexts, ending at roots or justified local frontiers | Runtime prefix-coverage replay |
| Report identity matches the snapshot, graph, profile and premise | Runtime validation |

These are not statically encoded as Rust refinement types. Source: [recognition](../../src/bap/target_resolution.rs#L689), [report binding](../../src/bap/target_resolution.rs#L1386), [coverage](../../src/bap/target_resolution.rs#L1684).

## 4. Representative execution

For the dump's jump at `0x00007ff77440da09`, backward reconstruction obtains a relative table expression and retains four known candidates. The candidate graph also contains a table edge back through `mov rcx,[rcx]`. That assigns an address input used by a later selector-byte load. The existing cycle rules leave a context unresolved, so the row remains `complete=false` with `cyclic-incoming-state`.

The shape match succeeded; incoming-state closure did not. The report also retains a separate stable, contradictory context as `infeasible`. These observations come from the [retained target report](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/target-report.json), not a new analysis run.

## 5. First abstraction boundary

**Preserve:** fixed snapshot/query identity, semantic VAs, expression widths and constructors, variable/read identities, branch direction, incoming graph structure, captured-byte premises, finite resources and incomplete outcomes.

**Erase:** `Box` allocation layout, collection implementations, JSON field order, string formatting and cached-read storage. The cache's captured-read identity and its effect on resource accounting remain relevant. Numeric operation codes become names such as `Add` and `SignedCast`.

## 6. Minimal abstract machine

```text
Context = {
  cursor : VA,
  target : RawTerm,
  guards : List<Guard>,
  reverse_path : List<{ predecessor : VA, taken : Bool }>
}

Machine = {
  fixed : { snapshot, candidate_graph, roots, transfers, premise, limits },
  pending : List<Context>,
  targets : Set<VA>,
  receipts : List<RawReceipt>,
  unresolved : Set<Reason>,
  resources : { steps_remaining, elapsed, read_bytes, ... }
}
```

`pending` contains unprocessed reverse contexts. `guards` preserve the branch constraints for that particular context. `targets` contain witnessed candidates, not an executed-target history. The fixed graph may be replaced by a later discovery epoch outside this invocation; old completeness must then be rechecked.

## 7. Abstract operations

```text
rewrite   : RawTerm × Transfer × Budget -> Option<RawTerm>
matchShape: RawTerm -> Option<TargetShape>
inferDomain : RawTerm × List<Guard> × Limits -> Option<FiniteSet<Word>>
checkContradiction : List<Guard> × Limits -> Bool
checkCycle : Context × CandidateGraph × Transfers -> Bool
readCaptured : VA × ByteCount -> CapturedRead + Error
validate : RawReport × FixedInput -> Accepted + Error
```

`checkContradiction=false` means that the bounded checker did not establish a contradiction. It does not mean satisfiable. `validate=Accepted` means the current runtime checks accepted the report, not that a universal correctness theorem has been proved.

## 8. Reachability and invariants

The initial worklist holds the queried jump expression with no accumulated guards or predecessor steps. Each successful reverse step substitutes a predecessor's outputs and adds its branch condition when present. Recognized frontiers, roots or excluded contexts terminate individual searches. Cycle rejection or resource exhaustion leaves explicit uncertainty; other contexts continue.

The raw record types can represent contradictory combinations such as `complete=true` with unresolved reasons. Such a value is representable but fails admission. A partial result is an intentional terminal outcome, not a stuck machine.

## 9. Abstract execution trace

```text
Context(jump, Input(R8), [], [])
  -- reverse through ADD and table LOAD -->
Context(cursor, B + sext64(load32(B + scale(i))), guards, path)
  -- matchShape -->
Some(Relative32{base=B, index=i})
  -- inferDomain and captured slot reads -->
table receipts and known candidates
  -- encounter uncovered cyclic predecessor -->
Partial{known_candidates, reason=cyclic-incoming-state}
```

The generic trace abstracts multiple substitutions. See [worklist](../../src/bap/target_resolution.rs#L1040), [target-form dispatch](../../src/bap/target_resolution.rs#L1089), and [cycle cutoff](../../src/bap/target_resolution.rs#L1216).

## 10. Second abstraction boundary

The formal presentation below removes the particular DFS schedule and allocation details. It preserves typed expression shapes, finite checks, incoming-context identity and failure/partial distinctions. Runtime counters become an abstract budget. Timing remains observable through budget-stop outcomes.

This presentation does not replace the actual bounded contradiction checker with a general satisfiability oracle.

## 11. Abstract syntax

Read `A + B` as a tagged alternative, `A × B` as a pair of facts and `{field:T,...}` as a record. Within expression syntax, `Add` denotes arithmetic; it is different from type-level `+`.

### Raw recursive type: product containing a sum

```text
RawTerm = μT. {
  width : U8,
  kind :
      Constant { value : HexWord }
    + Input    { key : VariableKey }
    + Unknown  {}
    + Binary   { op : Int, left : T, right : T }
    + Unary    { op : Int, arg : T }
    + Cast     { op : Int, arg : T }
    + Load     { site : VA, address : T }
}
```

`μT` means the record can recursively contain terms. This mirrors the shape of Rust's `Term` and `TermKind`; it does not claim that Rust uses a structural-subtyping language.

### Output shape: a second sum

```text
TargetShape =
    Relative32 { base : Word64, index : RawTerm }
  + Pointer64  { address : VA }
```

This sum has exactly two current target-producing alternatives. `infeasible` is a context-proof case, not a third target shape.

### Shape and control context are separate products

```text
ShapedContext = {
  shape : TargetShape,
  context : Context,
  snapshot : SnapshotIdentity,
  graph_epoch : Epoch,
  match : MatchEvidence(context.target, shape)
}
```

This checked conceptual record includes a refinement connecting its shape to its target term; arbitrarily pairing the two fields would not establish a match. A context can have both a `Relative32` target shape and an incoming graph containing a loop. Those properties are not exclusive alternatives in the same sum.

## 12. Binding structure

In the patterns below, `b`, `a`, `i` and `s` are pattern-bound metavariables. A repeated `b` requires equality of concrete base values; it does not introduce a fresh base with the same spelling.

Program inputs use keys derived from BIL variable identities. The key does not itself give every loop iteration a fresh SSA name. Reverse substitution and the particular path context determine which earlier expression is represented. Load terms preserve their source site and rewritten address. Matching the spelling `RCX` at two iterations does not establish equal values or equal load addresses. BIL `let` binding is handled during extraction before these simplified patterns are inspected.

## 13. Judgment forms

```text
t ⇝ shape
    The structural recognizer extracts a supported target shape from term t.

Γ, L ⊢ i bounded-by D
    The implemented finite-domain/range checks obtain a finite candidate domain D.

Γ, L ⊢ impossible
    The implemented bounded checker establishes a contradiction.

S, G, Q ⊢ receipt accepted
    Runtime replay accepts the receipt under the exact snapshot, graph and query.

Covered(G, Q, receipts)
    Every required incoming context ends in an admitted root/frontier/proof case.
```

`Γ` is the accumulated guard list, `L` the limits, `S` the immutable captured snapshot, `G` the candidate graph and `Q` the fixed query/premise scope. A shape judgment does not imply any of the later judgments.

## 14. Statics and pattern rules

### `pointer64`: match a load whose address is concrete

```text
t = { width=64,
      kind=Load{ site=s,
                 address={ kind=Constant{value=a}, ... } } }
number(address) = a
---------------------------------------------------------------- POINTER64
t ⇝ Pointer64{address=a}
```

This is a structural match over nested records and tagged alternatives. The captured 8-byte read is a later operation. A load from an address that remains symbolic does not match this target form.

### `relative32`: match nested arithmetic, cast and load structure

For a well-formed normalized term, the recognized shape is:

```text
Add(Const(b), SignedCast64(
  Load32(site=s,
    address=Add(Const(b), scale(j)))))

scale(j) ::= ShiftLeft(j, Const(2)) | Multiply(j, Const(4))
index(j) ::= i  when j = UnsignedCast(i)
           | j  otherwise
```

Both `Add` nodes allow the constant base on either side. The scale factor must be on the right of the shift/multiply node. After the optional unsigned cast is removed, the index must contain no `Unknown`.

```text
outer operation = Add
outer constant base = b
offset = SignedCast(width=64, arg=Load(width=32, site=s, address=slot))
slot = Add(Const(b), scale(j))             [either Add operand order]
scale(j) = ShiftLeft(j,Const(2)) or Multiply(j,Const(4))
i = index(j)     noUnknown(i)
---------------------------------------------------------------- RELATIVE32
t ⇝ Relative32{base=b, index=i}
```

The width-64 signed cast and width-32 load are explicit recognizer tests. Width annotations on the other constructors above describe well-formed terms supplied by extraction; they are not all independent raw-field tests in `relative`. See [the exact nested matcher](../../src/bap/target_resolution.rs#L689).

This is not unrestricted algebraic equivalence. For symbolic `i`, the matcher accepts `i*4`; it does not commute `4*i` into that form. Constructors already perform limited constant folding and cast simplification, so recognition is applied to that resulting representation.

### Structural matching versus refinement evidence

We can model a recognized case as a dependent pair:

```text
Recognized(t) = Σ shape : TargetShape. MatchEvidence(t, shape)
```

`Σ` packages a selected shape with evidence that the term matches it. This is an explanatory type; Rust currently returns options, fields and runtime-checked receipts rather than a proof term of this type.

Closing a target-producing context needs a larger product of obligations:

```text
CompleteTargetContextEvidence =
  ShapeEvidence
  × FiniteDomainEvidence
  × FullCapturedReadEvidence
  × TargetArithmeticEvidence
  × SemanticPathReplayEvidence

ContextClosure =
    CompleteTargetContextEvidence
  + CheckedInfeasibleContextEvidence

CompleteEvidence =
  RequiredContextClosures
  × IncomingCoverageEvidence
  × SnapshotQueryEpochBinding
```

For a partial result, only some checked entry/context evidence may exist. Known candidates are retained; the missing components prevent a completeness claim. A zero-target result can also be complete if all required contexts are validly excluded; target count alone decides neither success nor failure.

## 15. Dynamics

### Implemented shape dispatch

```text
matchShape(t):
  match relative(t):
    Some(base,index) -> Some(Relative32{base,index})
    None ->
      match t:
        Load{width=64, address=concrete(a), ...}
          -> Some(Pointer64{address=a})
        _ -> None
```

The target-form match is reached at a root or supported local frontier. In local mode, a checked contradictory context can terminate earlier with an `infeasible` receipt. Extending a predecessor can instead stop at the cycle rule. These checks are therefore a control-flow sequence, not one flat list of competing resolver classes.

### Table candidate evaluation

```text
Relative32(b,i):
  D := supportedFiniteDomain(i, Γ, limits)
  for each retained index k in D:
    slot   := b + 4*k                         modulo 2^64
    offset := signed32(capturedRead32(slot))
    target := b + signExtend64(offset)         modulo 2^64
    retain the entry/read/arithmetic receipt

Pointer64(a):
  target := capturedRead64(a)
  retain the read/arithmetic receipt
```

Guards can narrow domains or exclude values they definitely contradict. An unsupported evaluation returns unknown and cannot remove a candidate. Capture failures and budgets can leave only partial entry evidence.

### Context proof sum

```text
ContextCase =
    TableCase      { shape, domain, entry_evidence, path_evidence }
  + InfeasibleCase { contradiction_evidence, required_cycle_stability }
```

`InfeasibleCase` adds no destination. Existing cyclic exclusions require the reviewed stable-cycle check. A return to the queried dispatch or an unsupported repeated context instead produces `cyclic-incoming-state`.

## 16. Error behavior

```text
ObservedOutcome =
    Complete { candidates, accepted_receipts, incoming_coverage }
  + Partial  { known_candidates, receipts, unresolved_reasons, optional_stop }
  + InvalidEvidence { error }
```

This sum refines the concrete record/Boolean representation for explanation. It does not introduce a new public result type. Unsupported target shapes, unknown bounds, cyclic contexts or budgets can yield partial results. Malformed bindings, altered source bytes/BIL, invalid graph edges or inconsistent receipts fail admission. `Partial` does not imply the candidate set is empty, and `Complete` does not imply that any path executed.

## 17. Implementation correspondence

| Formal concept | Concrete implementation |
| --- | --- |
| Recursive record containing a tagged sum | [Term / TermKind](../../src/bap/target_resolution.rs#L91) |
| Normalized constructors and substitution | [cast](../../src/bap/target_resolution.rs#L174), [rewrite](../../src/bap/target_resolution.rs#L294) |
| Relative32 match and base-equality tests | [relative](../../src/bap/target_resolution.rs#L689) |
| Pointer64 match and target-form selection | [form selection](../../src/bap/target_resolution.rs#L1089) |
| Finite domain and local cut | [values](../../src/bap/target_resolution.rs#L555), [bounded_form](../../src/bap/target_resolution.rs#L752) |
| Bounded contradiction judgment | [guards_infeasible](../../src/bap/target_resolution.rs#L794) |
| Existing cycle predicate | [stable_cycle](../../src/bap/target_resolution.rs#L896) |
| Runtime refinement admission | [validate](../../src/bap/target_resolution.rs#L1386), [native replay](../../native/bap-core/capture.ml#L586) |
| Full incoming coverage | [prefix replay](../../src/bap/target_resolution.rs#L1684) |
| Abstract completeness authority | [target model](../../Specs/AriadneTargetResolution.tla#L67), [composition policies](../../Specs/AriadneGuardedTargetResolution.tla#L341) |

This is a source correspondence table, not a machine-checked refinement proof.

## 18. Final abstraction boundary

The type presentation omits JSON encodings, source-hash algorithms, helper transport and the detailed finite guard evaluator. It retains their obligations as runtime checks. `MatchEvidence` and `CompleteEvidence` express required evidence, without asserting a proven theorem that every accepted runtime record inhabits those formal types.

Structural record views can be written conceptually as:

```text
{ term:T, guards:G, path:P, snapshot:S } <: { term:T }
```

The left record contains the information required by the right view. This is a mathematical information view, not permission to add arbitrary JSON fields: actual receipt schemas use strict field validation. The notation also introduces no new assumption that crash-time registers describe earlier loop states.

## 19. Model-versus-implementation analysis

The abstraction map `α` translates a concrete Rust term recursively into `RawTerm`, retaining widths, operation meaning, keys and read sites. It translates concrete collections and worklist fields into the finite sets/lists of `Machine`. A runtime-invalid receipt can still map to a raw structural record; it does not thereby inhabit an evidence-refined type. Thus the comparison is by this translation and checked predicates, not by treating Rust values and mathematical types as literally the same set. One concrete worklist iteration can realize several abstract operations. No transition-simulation theorem is claimed.

### Why patterns can overlap

Target form and loop properties describe different fields:

```text
RelativeContext = {
  shape:Relative32,
  context:Context,
  match:MatchEvidence(context.target, shape), ...
}
LoopContext(G) = {
  context:Context,
  loop:LoopRegion(G),
  relevance:RelevantIncomingLoop(context, loop), ...
}

RelativeLoopContext(G) = RelativeContext & LoopContext(G)
```

Here `&` is an intersection of compatible record predicates. `LoopRegion(G)` names a cyclic region of the bound candidate graph; `RelevantIncomingLoop` relates it to a candidate incoming route for this context. This is model vocabulary, not a claim that the current resolver runs a separate loop-region matcher. The intersection is inhabited by a relative-table expression whose incoming graph contains a loop. One successfully closed reverse path can still be acyclic. By contrast, the current `Relative32` and `Pointer64` term recognizers require different outer constructors (`Binary(Add,...)` and `Load`), so those two raw target-form cases do not overlap.

### Proposed loop-aware refinement — not implemented

```text
LoopSummaryEvidence = {
  invariant,
  initialization : CheckedForEveryLoopEntrance(invariant),
  preservation   : CheckedForEveryLoopBackedge(invariant),
  dispatch_bound : CheckedAtEveryTableLoad(invariant),
  coverage       : CheckedCoverageOfRequiredEntrancesRecurrencesAndExits,
  source_binding : CheckedSnapshotGraphQueryBinding
}

LoopRelativeContext(G) =
  RelativeContext & LoopContext(G) & { summary : LoopSummaryEvidence }
```

For this dump, a candidate invariant would keep the RDX table base fixed while permitting RCX to follow a different pointer. At the indexed-load point, the selector must be within the admitted table range. At the jump, R8 has already become a target address, so the selector-bound property must not be incorrectly attached to R8 at that later point.

A loop-aware checker would discharge the summary obligations before providing the existing relative-table evaluator with a complete input domain. Merely matching the `LoopContext` fields cannot construct `summary`. The current producer and Rust/native validators reject general dispatch revisits; they need a new checked closure rule before accepting this proposed case.

### What the stronger types intentionally exclude

The actual `form:String` receipt representation can encode inconsistent variants until validation rejects them. `Term.width:U8` and integer operation tags are more permissive than a statically indexed expression grammar. Runtime re-extraction, replay and exact field checks restrict admitted values. The model's refined evidence types intentionally exclude malformed combinations; no type-level implementation change or equivalence proof is claimed here.

Constraint infeasibility remains a soundness-sensitive bounded check: an unknown expression is not a shared symbolic value that can establish contradiction. Loads from potentially different RCX values remain distinct. Existing stable-cycle proofs remain applicable under their original premises; adding a broader invariant rule must not weaken those premises globally.

## Context and follow-up

**Status:** explanatory document created 2026-10-15 from the inspected source. **Motivating problem:** understand resolver matching and overlap through structural types. **Contribution:** reconstructs the concrete implementation into sum/product types, contextual judgments and evidence refinements, with explicit abstraction losses.

The [formal-semantics skill](../../../skills/skills/engineering/formal-semantics/SKILL.md) guided the source-to-model presentation. The [formal-model guide](../../Specs/README.md) remains the entry to authoritative analysis contracts. Read the [canonical composition design](../../docs/Ariadne/guarded-target-resolution-design.md) for current behavior and the proposed invariant follow-up, or the [cyclic-state explanation](ariadne-cyclic-incoming-state-20261015.md) for the concrete dump loop. The [active plan](../plans/completed/guarded-target-resolution.md) retains the open completeness gate.

**Unresolved limits:** these structural types and inference rules have not been encoded or typechecked in a proof assistant. They do not replace the TLA+ authority, establish universal Rust/native refinement, implement a resolver registry, or implement the proposed loop-summary rule. No build, model checker or dump analysis was run to write this explanation.
