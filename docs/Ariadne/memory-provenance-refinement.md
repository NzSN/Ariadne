# Memory provenance refinement for Scanner

## Context and follow-up

**Status.** Proposed design direction, recorded on 2026-10-11 after inspecting
source at `53fe1ff` and the retained Scanner explanation. No alias-refinement
implementation, model contract or qualification is delivered by this note.

**Why this document exists.** The [Scanner resume record](bap-analysis-core-design.md#admission-resume)
preserves a completed but partial explanation. Its `unknown-memory-alias` gaps
expose both the shared memory abstraction and conservative unknown-output
dependencies. The [investigation design](investigation-design.md) requires
these limits to remain visible while making possible origins more useful.

**What this document establishes.** A bounded recommendation: clarify the
diagnostics, then assess individual candidate memory writers for one selected
load using captured access expressions and justified address relations. Reuse
the completed analysis and preserve every unresolved alternative.

**Where to go next.**

- [Investigation contracts](investigation-design.md) — exact query binding,
  before-instruction address expressions and permitted explanation claims.
- [BAP projection contract](bap-analysis-core-design.md#projection) — current
  load/store effects and the prohibition on killing the whole memory cell.
- [Analysis model](../../Specs/Ariadne.tla) and
  [formal-model guide](../../Specs/README.md) — authority for existing transfer
  rules and the starting point for a proposed refinement contract.
- [Investigation module](investigation-design.md#investigation-module-and-interface) — ownership and current bound
  result interfaces; implementation planning follows an explicit design/model
  contract and must be linked here when created.

**What remains unresolved.** Precise memory regions, dynamic base-value identity,
per-output dependency relations and backward numerical reconstruction remain
unimplemented in this path. This proposal does not identify an executed writer
or remove Scanner's other gaps. The [accepted P4 scope](file-reader-design.md#windows-replacement-capture-and-bounded-query)
qualifies its recorded implementation and corpus, not this proposed extension.

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

After access-pair reasoning can consume value constraints, consider bounded
straight-line inversions such as `rax_after = rax_before + 8` modulo 2^64.
Retain alternatives across branches and unknowns across lost bits, calls and
unmodeled effects. The current
[fault-context contract](zero-address-design.md) binds register observations at the
selected exception instruction; extending them backward requires its own
justification.

General reverse execution and a memory solver are larger design steps. They
are not prerequisites for constant-address or justified equal-base checks.

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

Separate diagnostic changes from semantic dependency changes in that design.
Runtime work must follow the relevant root, model, native and investigation
qualification contracts. Heavy build/model/mutation and large-query work
remains remote. This documentation change provides no new runtime acceptance.
