# Why `cyclic-incoming-state` remains

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

**It means the target resolver encountered a loop in the possible incoming control flow and could not certify coverage across that loop.** The captured jump-table targets are available; the missing part is a proof covering every incoming state at the jump.

For dump `dump_03958DA4FCA844A786262A1053`, the latest retained probe `dump-20261014T121127` reports:

| Caller dispatch | Known targets retained | Complete? | Remaining reason |
| --- | ---: | --- | --- |
| `0x00007ff77440da09` | 4 | `false` | `cyclic-incoming-state` |
| `0x00007ff77440dadd` | 4 | `false` | `cyclic-incoming-state` |

## What “incoming state” means

An incoming edge tells us which instruction can precede the jump. An incoming state includes the register values and accumulated branch constraints with which execution could arrive there. Returning to the same instruction address after a loop does not establish that those values and constraints are unchanged.

The resolver works backward from the indirect jump: it reconstructs the target expression, substitutes earlier register definitions and collects branch predicates. A complete certificate must cover every incoming candidate context, either through a checked bounded frontier or a checked exclusion. One successfully resolved route does not close an uncovered loop alternative. See [reverse traversal](../../src/bap/target_resolution.rs#L1040), [frontier meaning](../../src/bap/target_resolution.rs#L1204) and [complete-coverage replay](../../src/bap/target_resolution.rs#L1684).

## The concrete loop in this dump

At the original dispatch, the captured relative-32 table has base **`0x00007ff77ba909a8`**. Entry **3** selects **`0x00007ff77440d9eb`**, which leads back toward the same dispatch:

```text
0x00007ff77440da09   jmp r8
         │ table entry 3
         ▼
0x00007ff77440d9eb   mov rcx,[rcx]                 ← RCX is reassigned
0x00007ff77440d9ee   test rcx,rcx
0x00007ff77440d9f1   jz ...                       ← null alternative exits
0x00007ff77440d9f7   movzx r8d,byte ptr [rcx+0x78] ← potentially a new address
0x00007ff77440d9fc   cmp r8,9
0x00007ff77440da00   ja ...                       ← other branch also retained
0x00007ff77440da02   movsxd r8,dword ptr [rdx+r8*4]
0x00007ff77440da06   add r8,rdx
         │
         └───────────────────────────────────────► same dispatch
```

The mirror dispatch `0x00007ff77440dadd` has the same structure: table base **`0x00007ff77ba909d0`**, entry **3**, and pointer update **`mov rcx,[rcx]` at `0x00007ff77440dabf`**.

The pointer update is the relevant state change. If the first iteration uses pointer `p`, the next can use the pointer loaded from `[p]`. The selector loads can therefore be from `[p+0x78]` and a different address on the next iteration. No invariant establishes that their values agree. The short cycle contains no calls or stores, but it writes an input register used to address the selector load.

These loops are reconstructed from captured instructions, candidate controls and table-entry receipts. They describe structural possibilities, not an observed execution trace. The report does not retain a transcript of every rejected reverse context.

## The exact implementation rule

When extending a reverse path, the current implementation records `cyclic-incoming-state` if either:

1. The incoming predecessor is the queried dispatch itself; or
2. The reverse path repeats an instruction and the enabled local-cycle rule cannot validate it.

That branch sets `complete = false` and stops exploring that context. It preserves targets found through the other checked contexts. See [the rejection branch](../../src/bap/target_resolution.rs#L1216) and [retained-target publication](../../src/bap/target_resolution.rs#L1275).

The local-cycle rule supports one bounded simple-cycle unfolding. Its stability check rejects calls, unknown memory writes, original BIL stores, missing transfers and writes/clobbers of registers used in symbolic load addresses. Consequently, the `mov rcx,[rcx]` loop does not satisfy this stability rule. The return-to-dispatch check is also an explicit limitation of the current traversal. See [cycle shape](../../src/bap/target_resolution.rs#L874), [stability checks](../../src/bap/target_resolution.rs#L896) and [native replay checks](../../native/bap-core/capture.ml#L421).

## A smaller cycle was successfully discharged

Each dispatch also retains an `infeasible` receipt for a different cycle. That smaller cycle repeats the selector test **without** executing `mov rcx,[rcx]`. It requires the same unchanged byte load to be both greater than 9 on one pass and at most 9 on another. With the load-address and memory stability checks satisfied, the resolver can exclude that contradictory context.

Thus, the remaining reason does not represent a blanket rejection of all loops. It represents the incoming cyclic contexts left uncovered after the supported local reasoning.

## What would close the remaining reason

A suitable follow-up would prove an invariant separating the stable **RDX table base** from the changing **RCX object pointer**, preserve the selector bound on every dispatch-reaching iteration, and cover all incoming loop edges. Under the recorded frozen-control-data premise, that could justify a complete target set without treating successive object-byte loads as equal.

That is proposed work, not an implemented or accepted certificate. These two caller rows report only `cyclic-incoming-state`; increasing a work budget does not remove the explicit cycle rule or supply the missing invariant. See the [proposed invariant follow-up (historical line 133)](../../docs/Ariadne/guarded-target-resolution-design.md).

This label does not establish that execution entered the loop, that the program ran forever, or that a fifth target exists. It states that **the four witnessed candidates have not been certified as covering every incoming context**. That incompleteness contributes to the caller's remaining guard-coverage barriers.

## Context and follow-up

**Status:** source-grounded explanation, 2026-10-15, of the retained 2026-10-14 probe. The inspected Rust resolver and native checker match the qualification's recorded source hashes. No dump analysis, build or solver was rerun.

**Motivating problem:** understand why candidate targets can be present while `complete` remains false. **Contribution:** ties the diagnostic to its implementation rule and the captured pointer-following loop, while separating accepted infeasible receipts from rejected contexts.

Read the [canonical design](../../docs/Ariadne/guarded-target-resolution-design.md) for coverage contracts, the [active plan](../plans/completed/guarded-target-resolution.md) for the unresolved acceptance gate, and the [blocker inventory](ariadne-remaining-blockers-before-loop-20261015.md) for independent stops.

Evidence: [caller target receipts](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/target-report.json), [captured instructions and candidate graph, gzip](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/minidump-rust.json.gz), and [qualification scope](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md). A complete rejected-context transcript and executed history are not present in these records.
