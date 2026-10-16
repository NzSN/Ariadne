# Can an existence hypothesis support DFS?

**Yes. A DFS phase can search for one justified path or table witness first. Ariadne already uses DFS; the useful changes would be the objective and scheduling.** This restores the earlier design explanation, rather than adding an implementation.

## Meaning of the hypothesis

```text
At least one feasible path reaches the jump at DA0E.
```

That statement does not identify the path, fix its earlier register inputs or make the first path searched feasible. Search can also start without this hypothesis; finding a justified witness would establish existence under its admitted premises. A supplied hypothesis remains an explicit assumption.

| Goal | Required evidence |
| --- | --- |
| Structural path | Represented edges connect the entry and jump. A 44-edge corridor is already known in the recovered graph. |
| Feasible or conditional witness | Symbolic transfers and accumulated conditions justify the witness or its conditional table arithmetic. |
| Complete target coverage | All relevant incoming contexts are covered by target evidence or an accepted coverage proof. |

A contradiction checker may reject an impossible context. A context that it has not rejected is not automatically a proved feasible execution.

## Why DFS can still exhaust its budget

At D9CD the source pushes D9C6, then DD4C. A stack pops DD4C first. Expanding that incoming region can keep newer work above the queued entry corridor, even when a short useful corridor exists elsewhere.

The shown entry corridor reaches the R12 initializer D9BF in 19 reverse edges from the jump. Giving it timely work could help obtain an initial table witness. That structural distance does not certify every condition along the corridor.

The existence assumption changes neither this ordering nor the fixed resource allowance.

## A useful witness-first strategy

1. Preserve the original graph, entry roots, capture and value premises.
2. Search fairly for a first source-bound witness. Prioritize the initialization corridor or use bounded-depth DFS with increasing limits.
3. Check accumulated constraints; prune proved contradictions and retain unresolved conditions explicitly.
4. Retain the first valid table evidence and possible targets as partial progress.
5. Prove remaining incoming/loop coverage before marking the target result complete.

```text
first-witness search
    → conditional path/table evidence
    → remaining incoming-coverage proof
    → complete only if the coverage gate passes
```

With finite branching, a finite witness and terminating checks, a fair search can eventually reach a witness given sufficient resources. A fixed work budget can still expire. Address-only visited sets establish structural reachability but cannot safely discard all distinct symbolic states and constraints.

## One path does not always fix RAX

Even one local branch sequence can allow both selectors 65 and 43 under the shown bounds. Captured table arithmetic gives different RAX values for them. A symbolic witness can therefore yield a set of possible values rather than one numeric result.

A suitable partial result would say:

```text
One justified table witness found.
Targets under its conditions: retained.
Remaining incoming coverage: unresolved.
Complete: false.
```

For DA0E, the existing loop matcher also needs to distinguish the result register RAX from the index register RBX and its byte-classifier expression. Finding an initial witness does not remove that separate limitation.

## Relationship to current frame-path listing

The [frame-to-frame semantics report](ariadne-frame-to-frame-semantics-20261015.html) describes a separate forward structural DFS. Its `NP=2` setting retains at most one structural path, but does not add a feasibility proof or bypass missing bound frame graphs. The witness-first proposal above concerns the earlier target-resolution stage.

[Detailed first-jump explanation](ariadne-first-callee-jump-explained-20261015.html), [case-4 analysis](ariadne-case4-analysis-20261015.html).

## Context and follow-up

**Status.** Retained design discussion, restored on 2026-10-16; the proposed witness-first strategy is not an implementation claim.

**Why this document exists.** It preserves the conversation explanation associated with the [target-resolution design](../../docs/Ariadne/indirect-target-resolution.md) and [frame-path explanation](ariadne-frame-to-frame-semantics-20261015.md).

**What this document establishes.** The body records the stated mechanism, examples and evidence boundaries as of the report date.

**Where to go next.** Use the [target-resolution design](../../docs/Ariadne/indirect-target-resolution.md) and [frame-path explanation](ariadne-frame-to-frame-semantics-20261015.md); the [report index](ariadne-reports-index.md) links related explanations.

**What remains unresolved.** A path-existence premise does not supply a witness or remove feasibility and coverage obligations.
