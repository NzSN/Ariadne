# Why the first callee jump is still unresolved

This explains **the first jump in case 4**, at **`0x00007ff77443da0e`**. I will use short labels such as `da0e` below; they identify the final digits of addresses in this same function.

**The table bytes are available. Ariadne's bounded backward search explores a complicated incoming region before reaching the instruction that establishes the table base. It exhausts its work budget with that initializer still unprocessed.**

There are two different activities to keep apart: the program computes a destination and jumps forward; Ariadne works backward through possible predecessors to explain that computation. The search stack belongs to Ariadne, not to the program's stack or RSP.

## 1. What is Ariadne trying to determine?

The machine instruction is:

```asm
0x00007ff77443da0e:  jmp rax       ; captured bytes: ff e0
```

It means “continue execution at the address currently held in RAX.” Unlike `jmp 0x1234`, the destination address is not written directly in the instruction bytes.

Ariadne's question is: **which addresses can this instruction's RAX contain under the admitted incoming conditions?** Its target resolver owns the symbolic expressions, predecessor search and captured-table reads. The later loop checker owns a separate coverage certificate. The reader supplies immutable captured bytes.

The requested answer is a set of possible destinations. It is not a claim about which destination the process actually took before the crash.

### Does one incoming edge imply one RAX value?

**RAX is deterministic for one complete concrete machine state. A single control-flow edge can carry many such states.** Knowing the edge tells us which instructions are connected; it does not necessarily fix the input values those instructions operate on.

For this particular jump, there is only **one immediate incoming edge**:

```text
da0b: add rax, r12
          │
          │ one CFG edge
          ▼
da0e: jmp rax
```

There are **two incoming edges at the earlier join d9cd**, from d9c6 and dd4c. The search difficulty does not mean the jump itself has hundreds of incoming edges. The 271 rejected prefixes are longer backward contexts, not 271 immediate edges.

Consider two illustrative local states using the same captured table bases and the shown selector bounds:

| Value entering the lookup | Case index RBX | RAX at JMP | Final incoming edge |
| --- | ---: | --- | --- |
| Selector 65 (`A`) | 95 | `0x00007ff77443da10` | da0b → da0e |
| Selector 43 (`+`) | 47 | `0x00007ff77443e8de` | da0b → da0e |

Each computation has one definite result once its inputs are fixed. Both use the **same final edge**, but the selector values differ, so their RAX values differ. These are conditional local examples; they do not assert that both complete entry-to-jump histories have been proved feasible.

The distinction is:

```text
One concrete state, with relevant register/memory values fixed:
    one definite RAX value

One CFG edge, with relevant input values still variable:
    potentially several RAX values
```

Even fixing a sequence of branch choices does not always fix all data inputs. For example, both 65 and 43 satisfy the same local `selector <= 127` branch and both resulting case indices satisfy `index <= 117`.

Ariadne therefore needs to determine the possible values carried by the edge, and justify them across the relevant predecessor contexts. Here the obstacle is how that search spends its work, together with the remaining coverage checks. It is not a large count of immediate incoming edges at JMP.

## 2. How the program computes RAX: two table lookups

Think of a small switch statement implemented with two arrays:

```text
selector value
    ↓ first table: translate the value to a case index
case index
    ↓ second table: read a signed offset
signed offset + table base
    ↓
code address to jump to
```

Here are the actual ingredients:

| Name | Role | Value or bound |
| --- | --- | --- |
| RDI | Selector for the first lookup | The normal branch requires `0 <= RDI <= 127` |
| R15 | Base of the byte selector map | `0x00007ff77ba91d30` |
| RBX | Index returned by the byte map | The next normal branch requires `0 <= RBX <= 117` |
| R12 | Base of the signed-offset table | `0x00007ff77ba92a10` |
| RAX | Final jump address | Computed from the selected signed offset and R12 |

The important instructions are:

```asm
; Initialization on the entry corridor:
d9b8: lea    r15, [rip + ...]       ; R15 = 0x00007ff77ba91d30
d9bf: lea    r12, [rip + ...]       ; R12 = 0x00007ff77ba92a10

; Other instructions intervene, including loading the selector.
; The relevant normal branches establish the bounds shown above.
d9f8: movzx  ebx, byte ptr [r15+rdi]
da07: movsxd rax, dword ptr [r12+rbx*4]
da0b: add    rax, r12
da0e: jmp    rax
```

`movzx` makes the byte into a nonnegative larger value. `movsxd` interprets the 32-bit table entry as a **signed** offset. Multiplication by four selects one four-byte entry.

### A concrete example using real captured bytes

Choose the selector **65**, which is ASCII `A`. This is an example input to the captured tables, not a recovered earlier value of RDI.

| Calculation | Result |
| --- | --- |
| Read byte at `0x00007ff77ba91d30 + 65` | `95` |
| Select four-byte slot `0x00007ff77ba92a10 + 4 × 95` | `0x00007ff77ba92b8c` |
| Read those four captured bytes | `00 b0 9a f8` |
| Interpret little-endian word `0xf89ab000` as signed 32-bit | `-124,080,128`, or `-0x07655000` |
| Add the signed offset to R12 | `0x00007ff77ba92a10 - 0x07655000` |
| Destination | **`0x00007ff77443da10`** |

So, when these base and selector conditions hold, this particular lookup is straightforward.

The 128 selector-map bytes contain 31 distinct indices. Those indices lead to **21 distinct destinations**. Several selector values can choose the same index, and several slots can choose the same destination. The full 118-slot offset table contains 22 destinations; the selector map does not select one of them in this `0..127` range.

<!--TARGET_DEMO-->

## 3. Why doesn't Ariadne simply do those same reads?

Because, at the unresolved jump, it initially has a **formula**, not a justified numeric value for every register in that formula.

It starts with the question “what produced RAX?” Walking backward substitutes earlier assignments:

```text
At jmp rax:
    target = RAX

Across add rax,r12:
    target = old_RAX + R12

Across the signed table load:
    target = sign_extend(load32[R12 + 4*RBX]) + R12

Across the byte lookup:
    RBX is explained by load8[R15 + selector]
```

This is symbolic substitution. Ariadne is not running the machine instructions backward. It is replacing names in an expression with the expressions that produced their values.

The table expression still needs a justified R12 base. The instruction at `d9bf` supplies exactly that constant, but the resolver must reach it through its predecessor search—or find another sufficient source-bound frontier proof. Merely seeing a register named R12 does not supply the constant.

Also, learning the value on the entry corridor is one piece of evidence. To close the entire jump, Ariadne must justify the relevant base/range facts across all represented incoming contexts, including later returns to the same code region and intervening effects.

## 4. Where the backward search branches

At address **`d9cd`**, the represented graph has two incoming edges:

```text
entry corridor
    ... d9b8 sets R15
    ... d9bf sets R12
    ... d9c6 --------------------┐
                                 ↓
                               d9cd → ... → dispatch checks → ... → da0e → ?
                                 ↑
              dd4c --------------┘
              known branch to an earlier address
```

“Incoming” is from **d9cd's point of view**: both `d9c6` and `dd4c` can immediately precede it in the represented CFG.

The graph also contains a structural route from `d9cd`, through another branch at `d9f2` and other code, to `dd4c`. That route does not need an outgoing edge from `da0e`. Its branch conditions have not been proved jointly feasible just by drawing the route.

This matters because **we do not know a `da0e → dd4c` edge**. DA0E's destination remains unresolved. Calling the later incoming branch “loop-side” is shorthand for the cyclic predecessor region explored by the analyzer; it is not proof that the CPU executed a loop through this unresolved jump.

<!--CFG_DIAGRAM-->

## 5. Why Ariadne chooses the complicated side first

The resolver stores waiting work in a Rust vector named `pending` and takes work using `pending.pop()`. That is a stack: **last in, first out**.

At this join, the predecessor list is ordered by address:

```text
[d9c6, dd4c]
```

The code pushes the first one and then the second one:

```text
push entry-side item d9c6
push later incoming item dd4c
pop()                       → dd4c is selected next
```

Picture the waiting stack from bottom to top:

```text
TOP     dd4c — selected next
        d9c6 — entry corridor waits
BOTTOM
```

While expanding the `dd4c` side, the search can push additional predecessor work above the waiting entry item. Those newer items are selected first too. This is depth-first exploration.

The entry-side initializer is close: from the jump, the represented path to `d9bf` needs only **19 reverse edges**. A full structural entry-to-jump corridor has 45 nodes and no calls. In contrast, the retained rejected prefixes have **85–155 reverse edges**.

The source determines the initial selection order. The evidence also records `d9c6` in the used-transfer set, but does not record `d9bf`. Importantly, a parent enters that used set when the resolver **considers/queues it**; this does not mean it was fully explored. Together, these facts support the search-order explanation. The report does not retain a complete push/pop log of every operation.

<!--STACK_DEMO-->

## 6. What consumes the 2,097,152-step budget?

The budget limits the analyzer's work. It does not count CPU loop iterations, program instructions executed before the crash, or just the number of graph edges visited.

A pending item contains:

| Field | Plain meaning |
| --- | --- |
| `cursor` | Where this backward explanation currently stands |
| `term` | The current formula for the jump destination |
| `guards` | Branch conditions that this candidate context requires |
| `path` | The predecessor sequence accumulated so far |

Ariadne spends work on processing an item and on recursively visiting expression nodes while rewriting the target formula and its accumulated guards. For example, rewriting `base + 4*index` visits several expression nodes. Rewriting many accumulated guards repeats that work over larger expressions.

In the observed run, the first jump exhausts the shared **2,097,152 resolver work units**. Guard rewriting cannot finish, so it records `guard-work-limit`; pending work then records `resolution-work-limit`.

This budget is different from the **1,000,000 core-analysis-action limit** discussed for the large caller graph. They belong to different analyses.

## 7. Are branch constraints ignored?

No. The resolver rejected **271 predecessor contexts** because their accumulated conditions were contradictory.

A simple recorded contradiction is:

```text
the same rewritten symbolic value must be <= 255
AND
that value must be >= 256
```

No value satisfies both. Nine rejected contexts have this form. The other 262 combine a `<=255` condition with a bit-mask equality that cannot hold in that range.

The `255` condition comes from other code in those retained prefixes; it is not a replacement for the first dispatch's own `<=127` check.

Ariadne must compare conditions after substituting the intervening assignments. A register can hold one value in an earlier pass and a different value later. It would be unsound to treat two conditions on the same register name at different times as automatically contradictory.

Rejecting these 271 contexts is useful and conservative. It does not prove every incoming context impossible. It also consumes work to construct, rewrite and reject each context.

The outcome is therefore:

```text
271 contexts rejected
+ unresolved cyclic incoming contexts
+ work exhausted
+ no retained table witness
= jump remains incomplete
```

## 8. Why doesn't the existing loop-aware checker finish the job?

There are two separate obstacles.

**First, its current job is coverage after a table witness exists.** It requires an existing `relative32` witness with entries and nonempty targets. This jump has only infeasible receipts, so that prerequisite is absent. The checker does not start by independently finding the table.

**Second, its current shape matcher is narrower than this dispatch.** It takes the initial jump register, RAX, as the selector and requires the reconstructed table index to be that same input bank. Here:

```text
RBX chooses a slot in the table.
RAX receives the loaded offset and then the final jump address.
```

Distinguishing the index register from the result register is normal machine code, but this particular matcher does not yet accept this shape. After byte-lookup substitution, the index is a nested load expression, which also requires deliberate handling.

So selecting the short entry corridor sooner could help obtain the first table witness. It would not, by itself, establish complete loop/incoming-state coverage.

## 9. What is known, and what still needs proof?

| Statement | Status |
| --- | --- |
| The first jump is `jmp rax` | Captured and decoded |
| Both relevant table byte ranges exist in the dump | Directly read and hash-checked |
| The shown bounds and captured tables yield 21 destinations | Verified conditional arithmetic |
| The source uses a stack and selects dd4c before the queued d9c6 item at the join | Verified from source and represented predecessor order |
| The initializer at d9bf is absent from the retained used transfers | Observed in the reproduced report |
| Every represented incoming context satisfies the needed base/range facts | Not established |
| All 21 destinations were executed, or one particular destination was taken | Not established by these results |
| Raising the budget alone will complete the analysis | Not demonstrated |

The practical correction has two parts: make the search give timely progress to short prefixes and later dispatches within a finite total budget; then extend the existing loop matcher to represent the actual index expression independently of the jump-result register.

## 10. Source and evidence

The original dump is `dump_03958DA4FCA844A786262A1053`, thread 23668, frame 0. The focused remote reproduction `case4-20261015T081221` exactly matches the retained target report and leaves the qualified sources unchanged. No build or dump execution is needed to produce this explanation.

- [Detailed case-4 analysis](../../evidence/Ariadne/callee-dispatch-analysis/20261015/README.md).
- [Captured selector/offset tables and slot arithmetic](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/captured-tables.json).
- [Reproduced resolver summary](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/resolver-summary.json).
- Resolver work initialization and predecessor construction: `src/bap/target_resolution.rs:1073–1081`.
- Pending stack selection: `src/bap/target_resolution.rs:1111`.
- Parent iteration and queueing: `src/bap/target_resolution.rs:1285–1337`.
- Expression-node work accounting: `src/bap/target_resolution.rs:306–343`.
- Loop witness prerequisite: `src/bap/target_resolution/loop_closure.rs:1263–1273`.
- Loop selector/index restriction: `src/bap/target_resolution/loop_closure.rs:685–735`.

<!--ADVANCED_START-->

## Optional technical appendix: a small model of the resolver

This appendix is for connecting the walkthrough back to the implementation. The earlier sections contain the explanation needed to understand the case.

### State and invariants

The concrete implementation uses a fixed instruction graph, typed BAP transfers, original entry roots, a pending vector, result rows, captured-read evidence and a shared remaining-work counter. Its mutations change the search state and result evidence; they do not change the captured snapshot.

A minimal abstract state is:

```text
State = (fixed_inputs, waiting_stack, current_item, results, read_log, fuel)
Item  = (cursor, target_formula, constraints, predecessor_path)
```

The first abstraction preserves predecessor order, stack order, symbolic dependencies, uncertainty and exhaustion. It erases Rust allocation, string encodings, most register-byte bookkeeping and unrelated instructions.

Useful invariants are that fuel never goes negative, every searched predecessor edge comes from the supplied graph, and exhausted work produces an incomplete result rather than a complete proof. Queue membership is distinct from completed exploration. The recorded used-transfer set is not an execution trace.

### Operations and legal transitions

In plain pseudocode:

```text
take:
    remove the newest waiting item

if fuel is exhausted:
    record an unresolved work limit for that item
else:
    charge item processing
    if accumulated constraints are proved contradictory:
        retain an infeasible-context receipt
    else if a bounded table expression has been established:
        read captured bytes and retain a table witness, subject to its checks
    else:
        for each represented predecessor:
            substitute its transfer into the target and constraints
            charge the visited expression nodes
            queue the resulting predecessor item when supported
```

Initial states have a jump expression and a pending item. Successful terminal states have the required evidence and coverage. Exhausted, unsupported, unanchored or uncovered states remain partial. A missing memory read would be a separate failure; this resolver run stops before attempting the relevant table reads.

A representative abstract trace is:

```text
W = []
W = [entry_item]
W = [entry_item, later_branch_item]
take later_branch_item
W = [entry_item, ...newer predecessor work...]
...fuel is consumed...
record incomplete result when fuel is exhausted
```

This is a source-grounded reconstruction of the relevant policy, not a recording of every intervening operation.

### Expressions, bindings and judgments

We can summarize the expression language as:

```text
term       ::= constant | input-register | operation(term, ...) | load(term)
constraint ::= (predicate-term, required-branch-outcome)
```

An input-register reference is interpreted at the current search cursor. Walking across an assignment substitutes that register's producing expression. The relevant binding is this relation between an expression and its before-state, rather than a lexical variable declaration.

Two useful judgments, written as explanatory notation, are:

```text
constraints prove impossible
inputs and constraints justify a finite table witness
```

These are different judgments: the first rejects one context, while the second supplies target evidence. Neither alone proves whole-dispatch coverage. Typed widths, captured-byte identity and the original graph/root scope constrain admissible witnesses; this note does not replace their implementation checks.

The second abstraction erases the internal arithmetic of each term and keeps only substitution, contradiction, bounded-read and exhaustion operations. A transition spends a cost determined by the concrete expression work; one abstract arrow is not one fuel token.

### Correspondence and remaining mismatch

| Abstract operation | Implementation |
| --- | --- |
| Newest item selected | `pending.pop()` |
| Incoming work queued | predecessor loop plus `pending.push(...)` |
| Formula substitution | `Term::rewrite` |
| Contradictory context rejected | `guards_infeasible` |
| Finite table read/witness | bounded-form and captured-read branches in `resolve_inner` |
| Loop coverage attempted | `loop_closure::propose` after ordinary exploration |
| Work exhaustion retained | unresolved reason plus `complete = false` |

The implementation can represent a queued item that never receives enough work to expand. Its address can already be in the used set. This is exactly why a queued entry corridor must not be described as successfully analyzed.

The model intentionally omits full hardware behavior, exception resumption, detailed heap aliasing and proof of Rust/native refinement. It preserves the search behavior relevant to this case, not a history of what the crashing program executed.

<!--ADVANCED_END-->

## Context and follow-up

**Status.** Retained explanation of the first callee dispatch, restored on 2026-10-16.

**Why this document exists.** It preserves the conversation explanation associated with the [case-4 evidence](../../evidence/Ariadne/callee-dispatch-analysis/20261015/README.md) and [target-resolution design](../../docs/Ariadne/indirect-target-resolution.md).

**What this document establishes.** The body records the stated mechanism, examples and evidence boundaries as of the report date.

**Where to go next.** Use the [case-4 evidence](../../evidence/Ariadne/callee-dispatch-analysis/20261015/README.md) and [target-resolution design](../../docs/Ariadne/indirect-target-resolution.md); the [report index](ariadne-reports-index.md) links related explanations.

**What remains unresolved.** The calculator uses captured table bytes under the stated premises; it does not prove executed history or complete incoming-state coverage.
