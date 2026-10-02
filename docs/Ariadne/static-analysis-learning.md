# Learning the theory behind Ariadne's assembly analysis

## Context and follow-up

**Status.** Conceptual reading guide; not an implementation acceptance record.

**Why this document exists.** [Crash-investigation goal](../../README.md) motivates reasoning about possible origins from incomplete captured state.

**What this document establishes.** The guide explains reaching definitions, fixed points, may/must writes, call summaries and slicing using the questions a crash investigator asks. It connects theory to the actual engine.

**Where to go next.**

- [Concrete engine](../implementation.md) — connects fixed points and slicing to Rust.
- [Formal contracts](../../Specs/README.md) — make the state and transition assumptions explicit.
- [Domain questions](investigation-layer-design.md) — explains how analysis primitives support investigator-facing answers.

**What remains unresolved.** Conceptual examples do not validate a particular capture or instruction lift. Use the implementation and formal contracts to identify the premises of a concrete result.

For the wider context, see the optional [documentation map](../documentation-map.md).

Source review: 2026-09-27. This is a learning note, not an implementation plan.

The relevant field is **static program analysis**: deriving information about
possible program behavior without executing each possible run. Ariadne combines
local control-flow recovery, forward may-reaching definitions, and a backward
data-dependency slice. Procedure summaries explain its treatment of calls.
Its current algorithms are specified in [Ariadne.tla](../../Specs/Ariadne.tla)
and implemented in [engine.rs](../../src/engine.rs).

## 1. Learn the questions before the mathematics

| Concept | Question it answers | Ariadne's current representation |
| --- | --- | --- |
| Control-flow graph, or CFG | Which instruction might follow this one? | Instruction addresses and typed edges |
| Reaching definitions | Which earlier writes might supply a location here? | Sets of tagged definition origins |
| Instruction effects | What is read, possibly written, or definitely written? | `uses`, `may_defs`, `must_defs` |
| Backward data slice | Which producer instructions are connected to these uses? | Closure from instruction seeds |
| Call summary | What effects should the caller allow across a call? | Opaque effects and a continuation edge |

This vocabulary is standard dataflow-analysis terminology; the rightmost column
is the mapping to [Ariadne's model](../../src/model.rs). For an approachable
introduction, read Møller and Schwartzbach's [*Static Program Analysis*](https://cs.au.dk/~amoeller/spa/),
especially its sections on reaching definitions and forward/backward, may/must
analyses. A **may** result collects alternatives; it does not assert that each
alternative actually occurs in a concrete execution.

## 2. A small assembly example

Treat these labels as instruction addresses, with entry at `a` and slice seed `d`:

```asm
a:  mov rax, rdi       ; copy an incoming value
b:  call helper       ; effects of helper are opaque here
c:  mov rbx, rax       ; possible continuation after b
d:  mov rcx, [rbx]     ; read memory through rbx
```

This is a hand-worked application of Ariadne's equations. Register names below
stand for their tracked byte cells; `M` abbreviates `memory:any`. The real
[location catalogue](../../src/effects/locations.rs) tracks GPR bytes, flags,
memory, and other state. We show only facts needed for the example.

Write `rax@a` for an instruction-origin fact and `rdi@entry(a)` for an unknown
incoming origin. These identify possible producers, not numeric values.

| Program point | Selected reaching origins before the instruction |
| --- | --- |
| `a` | `rax@entry(a)`, `rdi@entry(a)` |
| `b` | `rax@a` |
| `c` | `rax@a`, `rax@b` |
| `d` | `rbx@c`; for memory, `M@entry(a)` and `M@b` |

At `a`, the definite write to `rax` replaces its old origin. At `b`, the opaque
call may overwrite every tracked location and provides no definite-write
guarantee. Thus both the surviving `rax@a` and the possible write `rax@b`
reach `c`. The call-site origin represents an opaque effect, not a discovered
instruction inside `helper`. These rules come from `Gen`/`Out` in
[Ariadne.tla](../../Specs/Ariadne.tla) and `opaque` in
[effects/rules.rs](../../src/effects/rules.rs).

Starting at `d`, the slice includes `c` for the address in `rbx` and `b` for a
possible memory write. The use of `rax` at `c` adds `a` and `b`. The resulting
instruction set is `{a,b,c,d}`. Entry origins remain visible as unknown inputs
but do not become producer instructions. This follows `Dependencies` and
`SlicePredecessors` in [Ariadne.tla](../../Specs/Ariadne.tla).

The answer means that these producers remain possible under this graph and
these summaries. It does not reconstruct what happened in the crashing run.

## 3. Reaching definitions as a finite fixed-point problem

Let `N` be the decoded instruction nodes and `D` the finite set of possible
facts `(location, site, origin)`, with origin either `entry` or `instruction`.
The state is one set `IN[n] ⊆ D` for every node. The mathematical domain is
the product lattice `P(D)^N`: order by componentwise subset, join by union,
and bottom by an empty set at every node. This is a mathematical reading of
`DefinitionType`, `Init`, and `Propagate` in [Ariadne.tla](../../Specs/Ariadne.tla).

For the fixed effects of instruction `n`, Ariadne's equations are:

```text
GEN[n] = {(l, n, instruction) | l ∈ may_defs[n]}
OUT[n] = {d ∈ IN[n] | d.location ∉ must_defs[n]} ∪ GEN[n]
IN[n]  = ENTRY[n] ∪ ⋃ {OUT[p] | p is a decoded local predecessor of n}
```

`ENTRY[n]` contains an unknown incoming origin for every tracked location if
`n` is an entry root; otherwise it is empty. Bottom does not mean that register
values are zero. It means no reaching-origin facts have yet been accumulated.
Unknown entry values are represented explicitly, not confused with bottom.

At a branch join, if one predecessor supplies `rax@u` and another supplies
`rax@v`, union retains both. A loop can send new origins back to an earlier
node, so a single forward scan is insufficient. The engine repeatedly grows
sets until all node equations hold. It keeps both branches of a conditional
and does not prove their feasibility. See `incoming` and the `Dataflow` phase
in [engine.rs](../../src/engine.rs).

Why does iteration stop? Each update adds a previously absent node/fact pair,
and there are at most `|N| × |D|` such pairs. A fixed kill set does not break
monotonicity: if `X ⊆ Y`, then `(X − K) ∪ G ⊆ (Y − K) ∪ G`. Starting at bottom
and propagating until no equation can grow gives the least fixed point for
this represented graph. This argument is specific to Ariadne's finite domain;
it does not claim that all machine behavior has been represented.

## 4. May-writes, must-writes, and aliasing

A possible write generates a new origin. Only a definite write removes old
origins. For an uncertain store through a pointer, the store may affect a
tracked location without definitely replacing it, so both alternatives survive.
This is the same precision issue illustrated by **weak** versus **strong**
updates in [Møller and Schwartzbach, §11.5](https://cs.au.dk/~amoeller/spa/spa.pdf).

An instruction can definitely write a location while reading its old value.
For `add rax, rbx`, the old `rax` definition is killed in `OUT[add]`, because
the new definition is now the last write. The backward slice still follows the
old definition through `add`'s `uses`, using `IN[add]`. Killing provenance after
an instruction does not erase its input dependencies. Compare `Out` with
`Dependencies` in [Ariadne.tla](../../Specs/Ariadne.tla).

Location granularity matters: a definite write to one byte does not justify
killing origins for unrelated bytes. A write somewhere in an aggregate memory
location does not necessarily replace everything that location represents.
See the [catalogue](../../src/effects/locations.rs) and
[effect rules](../../src/effects/rules.rs) for Ariadne's chosen abstractions.

## 5. Abstract interpretation supplies the semantic framework

Abstract interpretation relates concrete computations to a simpler domain
that retains selected information. An abstract transformer must conservatively
cover the concrete behaviors it represents. The Cousots' original
[1977 paper and author summary](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml)
explain this connection through ordered domains and fixed points.

For Ariadne, the retained information is possible definition provenance.
A soundness proof for that choice would relate the fact sets to concrete
executions equipped with write-origin history. Proving that a finite solver
finds its fixed point is one obligation; proving that decoding, edges, and
effects cover the intended concrete executions is another. This distinction
is a modeling explanation, not a claim that such an end-to-end proof exists.
The current [scope contract](../../src/model.rs) explicitly limits
`scope_closed()` to the supplied request and traversal policy.

## 6. Procedure summaries and the two meanings of “summary edge”

In interprocedural analysis, a procedure summary can map abstract entry states
to abstract exit states. It lets callers reuse information about a callee.
Read the functional approach in
[Møller and Schwartzbach, §8.4](https://cs.au.dk/~amoeller/spa/spa.pdf).

Ariadne currently records these two edges:

```text
call site b --call----> helper entry
call site b --summary-> continuation c
```

The first exposes a target but is excluded from local traversal and dataflow.
The second permits a possible continuation with the call instruction's opaque
effects. The effects live in the instruction record; the edge selects local
propagation. No callee-derived summary or matched callee-return edges are
computed, and the edge does not assert that the call always returns.
See `LocalEdges`, `CallEdges`, and `Preds` in [Ariadne.tla](../../Specs/Ariadne.tla).

In a **system dependence graph**, a summary edge instead connects an
actual-input node to an actual-output node and records a transitive dependency
through a call. These are dependency edges, not Ariadne's call-to-continuation
CFG edges. Horwitz, Reps, and Binkley's
[original paper, §§3–4](https://research.cs.wisc.edu/wpis/papers/toplas90.pdf)
develops these graphs and interprocedural slicing.

For deeper interprocedural theory, [Reps, Horwitz, and Sagiv (1995)](https://research.cs.wisc.edu/wpis/papers/popl95.pdf)
introduce **IFDS**, using finite fact sets and distributive transfer functions.
Its graph-reachability method respects matching calls and returns: entering
through one call must not return to a different call's continuation. “Valid”
here concerns call/return structure, not proof of branch feasibility. Ariadne
does not implement IFDS; the paper explains a possible next subject to learn.

## 7. Slicing and the special difficulty of binaries

Ariadne takes a backward **data** closure over every use of every included
instruction. Its criterion is an instruction seed, rather than a separately
selected output operand. It does not compute control dependencies or a full
program dependence graph. An opaque call reads everything in the tracked
catalogue, so its data slice can become broad. Even if this happens to include
a flag-producing instruction, that is still a data dependency.
See `slice_predecessors` in [engine.rs](../../src/engine.rs).

Full dependence-based slicing also considers control dependence, and
interprocedural slicing must handle calling context. The authors' short
[retrospective](https://research.cs.wisc.edu/wpis/papers/pldi88.retrospective.pdf)
is a useful companion to the original paper; it also distinguishes a dependency
slice from producing a separately executable program.

Binary analysis must recover useful objects from registers, addresses, memory
accesses, and indirect control flow. Balakrishnan and Reps's
[“Analyzing Memory Accesses in x86 Executables”](https://research.cs.wisc.edu/wisa/papers/cc04/BR04.pdf)
introduces abstract memory locations and value-set analysis. Particularly
relevant here, it derives used, killed, and possibly-killed sets for reaching
definitions and data-dependence construction. Ariadne's coarse memory location
does not amount to implementing that paper's value-set analysis.

## 8. A short reading and exercise sequence

1. Read the [course notes](https://cs.au.dk/~amoeller/spa/spa.pdf), Chapters 4–5,
   especially §§5.7–5.8. Compute the example's fact sets by hand.
2. Add two branches that assign `rax` differently, then add a back edge.
   Iterate until nothing changes; explain every surviving origin.
3. Read §8.4 and Chapter 12 of the notes, then the Cousots' paper.
   Separate a summary's precision from a solver's convergence.
4. Read the x86 memory-analysis paper above. Compare a single memory bucket
   with several abstract locations for an uncertain store.
5. Read the slicing retrospective and original paper; study IFDS afterward.
   Draw two calls to one helper and identify a mismatched return path.
