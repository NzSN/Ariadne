# Case 4: the two remaining callee indirect jumps

**The dump contains both jump tables. The remaining blocker is resolver search/coverage, with shared-budget starvation at the second jump.** Direct reads recover 21 conditional destinations for the first dispatch and 13 for the second. Ariadne has not certified these as complete target sets.

## Context and follow-up

**Status.** Analysis completed on 2026-10-15; no production correction is qualified by this record. **Motivating problem.** Item 4 of the remaining-blocker inventory has two unresolved callee indirect jumps after terminal coverage improved from 12 barriers to two. **Contribution.** This report reproduces the exact resolver result, verifies captured table bytes, reconstructs dispatch arithmetic and identifies search and loop-matching limits. **Next reading.** The [existing target-resolution design](../../docs/Ariadne/indirect-target-resolution.md) owns target evidence; the [loop/composition design](../../docs/Ariadne/guarded-target-resolution-design.md) owns checked incoming coverage. The [caller-coverage qualification](../../evidence/Ariadne/caller-semantic-coverage/20261015/README.md) records the preceding delivery. **Limits.** Table arithmetic is conditional on the shown base/range facts and `FrozenCapturedControlData`; it proves neither executed history nor complete incoming-state coverage. Additional discovery may expose further obligations.

## What each instruction does

| Jump | Bytes / semantics | Captured dispatch data | Conditional destinations |
| --- | --- | --- | ---: |
| `0x00007ff77443da0e` | `ff e0`, LLVM `JMP64r`, BAP `jump RAX` | 128-byte selector map at `0x00007ff77ba91d30`; relative32 table at `0x00007ff77ba92a10` | 21 through the captured selector map |
| `0x00007ff77443e200` | `ff e0`, LLVM `JMP64r`, BAP `jump RAX` | 111 relative32 slots at `0x00007ff77ba92be8` | 13 |

Both jump instructions have projected BAP semantics without a semantic gap. The tables lie in a committed read-only `MEM_IMAGE` region of `electron.exe`. Object state supplies selectors; the final target values come from these fixed image tables.

The first dispatch is:

```text
R15 = 0x00007ff77ba91d30             // RIP-relative LEA at 0x7ff77443d9b8
R12 = 0x00007ff77ba92a10             // RIP-relative LEA at 0x7ff77443d9bf
RDI = zero_extend(load32[RSI+0x38])
require unsigned RDI <= 127         // normal arm at 0x7ff77443d9f2
RBX = zero_extend(load8[R15+RDI])    // 0x7ff77443d9f8
require unsigned RBX <= 117         // normal arm at 0x7ff77443da01
RAX = sign_extend(load32[R12+4*RBX]) // 0x7ff77443da07
jump R12 + RAX                     // 0x7ff77443da0e
```

All 128 selector-map bytes are captured. They contain 31 distinct indices, all within `0..117`, which select 21 distinct destinations. Reading all 118 offset slots without using the selector map gives a conservative 22-destination envelope; the additional target is `0x00007ff77444133a`. This distinction matters: finite byte-domain enumeration can safely retain that extra candidate, while 21 requires the captured map relationship.

The second dispatch is:

```text
EAX = low32(R14 - 10)               // 0x7ff77443e1e9
require unsigned EAX <= 110         // normal arm at 0x7ff77443e1f0
RCX = 0x00007ff77ba92be8             // RIP-relative LEA at 0x7ff77443e1f2
RAX = sign_extend(load32[RCX+4*RAX]) // 0x7ff77443e1f9
jump RCX + RAX                     // 0x7ff77443e200
```

All 111 slots are captured and yield 13 distinct destinations. Every numerically derived destination lies inside the captured runtime-function bounds `[0x7ff77443d960, 0x7ff774442634)`. This bounds check is separate from decoding/discovering those destinations.

## Why Ariadne still reports unresolved

The reproduced preparation has the original root `0x7ff77443d960`, 778 attempted starts and the same exact target report as final-helper run `075602`. Its target resolver makes **zero captured control-data reads**.

| Site | Receipts and residuals |
| --- | --- |
| DA0E | 271 receipts, all `infeasible`; no targets. Residuals: `cyclic-incoming-state`, `guard-work-limit`, `resolution-work-limit`. |
| E200 | No receipts or targets. Residual: `resolution-work-limit`. |

Three mechanisms explain this result.

1. **The later incoming subtree runs before the short table-base corridor.** The predecessor list at `d9cd` is ordered `d9c6`, then `dd4c`. The resolver pushes both onto a vector and pops the last, so it explores the `dd4c` incoming subtree first. This branch goes to an earlier address; it does not establish an outgoing `da0e → dd4c` edge. The direct corridor is queued, but the retained used-transfer set never reaches `d9bf`, where R12's table base becomes known. There is a 45-node/44-edge structural root corridor with no calls, and only 19 reverse edges from the jump to the base initializer. The 271 explored prefixes instead have 85–155 reverse edges. See [predecessor construction](../../src/bap/target_resolution.rs#L1078), [stack pop](../../src/bap/target_resolution.rs#L1111) and [predecessor push](../../src/bap/target_resolution.rs#L1285).

2. **Work is shared across dispatches.** `steps` is initialized once before the ascending-address dispatch loop. Substituting target expressions and every accumulated guard recursively spends this same counter. DA0E exhausts the 2,097,152-step allowance while rewriting guards. E200 sorts later and encounters exhausted work before substantive analysis. Its residual therefore does not diagnose an unsupported table shape or missing bytes. See [shared budget](../../src/bap/target_resolution.rs#L1073), [recursive substitution](../../src/bap/target_resolution.rs#L306) and [guard-work-limit](../../src/bap/target_resolution.rs#L1338).

3. **Current loop coverage cannot bootstrap this dispatch and has a further shape restriction.** It requires an existing relative32 witness and nonempty targets before proposing induction. DA0E has only infeasible receipts, so proposal declines before constructing a loop proof. Even after a witness is obtained, the current matcher takes the initial jump register RAX as its selector and requires the reconstructed table index to be that same input. Here the table index is RBX, then a byte-load expression after substitution; continued backward matching reaches the two-predecessor boundary. See [witness prerequisite](../../src/bap/target_resolution/loop_closure.rs#L1263), [selector selection](../../src/bap/target_resolution/loop_closure.rs#L685), [index equality](../../src/bap/target_resolution/loop_closure.rs#L705) and [join boundary](../../src/bap/target_resolution/loop_closure.rs#L734).

The ordinary resolver already represents byte-load/cast indices. Its 256-value byte domain fits the actual `max_values=4096`. Obtaining an initial table witness is therefore a search/bootstrap issue in this observed run, rather than evidence that byte-classifier syntax is entirely unsupported. Successful production admission still needs a replayed witness and complete coverage.

## Accumulated branch constraints are checked

All 271 rejected prefixes include `low32(RDI) <= 255`:

- 262 also require `(low32(RDI) & 0x1ffc00) == 0xd800`.
- The other nine also require `low32(RDI) >= 256`.

Each combination is contradictory. These are rejected reverse-search contexts, not 271 executed paths. The source checks accumulated guards at [target_resolution.rs](../../src/bap/target_resolution.rs#L1123); it does not establish that every incoming context is infeasible. The run is bounded search over a cyclic graph, not an infinite execution loop.

## What the correction should address

The next implementation should extend the existing resolver in two stages: obtain ordinary table witnesses without starving short prefixes or later dispatches, then extend checked loop matching to distinguish the jump-result bank from the actual table-index expression. Per-site progress must remain within a finite aggregate budget, and all original incoming states, graph/epoch bindings and unknown writes must remain represented.

The ownership is `src/bap/target_resolution.rs` for prefix scheduling, work accounting and candidate enumeration; `src/bap/target_resolution/loop_closure.rs` for induction/shape checks; `TargetResolutionCoordinator` in `src/input/materialize.rs` for discovery rounds and epochs. Table contents must remain captured-read evidence, not extra roots or configured target lists.

These 34 conditional destinations include **31 not yet attempted starts** in the current callee materialization: all 21 first-dispatch destinations and ten of the second's 13. This explains why completed core parity for the current graph can coexist with incomplete callee coverage. Adding these destinations may expose further branches or semantic gaps; the present analysis does not predict complete callee recovery.

## Reproduction and provenance

The fresh remote probe `case4-20261015T081221` returns the intended RED signal, `case4 RED: unresolved callee dispatches remain`. It exactly reproduces the retained target report and verifies all 937 qualified source files unchanged. Heavy execution and driver compilation run only in remote Windows WSL.

- Dump SHA-256: `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`; thread 23668, frame 0.
- Qualified source capsule: `c35459a19b1e2f5f139730bea6c119cfceff603207254b52d42effac68654a5f`.
- Rust release library SHA-256: `d7dca79f2a5e6544ae0fed728415a0a9168b4a482bcf91f4d786586e8cbd8e24`.
- [Captured table bytes and all slot/target pairs](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/captured-tables.json); [comparison and conditional target lists](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/comparison-and-candidates.json); [fresh resolver summary](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/resolver-summary.json); [run result](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/run-result.json); [driver](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/probe.rs.txt).

All three reads use Memory64 stream 9, entry 2219, with complete requested spans and no holes/conflicts:

| Data | VA | Bytes | Dump file offset | SHA-256 |
| --- | --- | ---: | ---: | --- |
| ascii-selector-map | `0x00007ff77ba91d30` | 128 | 871385870 | `1cc2dd6f92df16ae450d8da20bfc5cb5cdfaafd99d2c82766ed0782cd20ce241` |
| da0e-relative32 | `0x00007ff77ba92a10` | 472 | 871389166 | `154ff5db20afdf6e61dab6827d0b368a6cfc22cfef4b9ffd2873efb37f25b9f0` |
| e200-relative32 | `0x00007ff77ba92be8` | 444 | 871389638 | `5ba262117531983477160b23f9a1eedbec6d37c4c17061e0cbb6822fd046b88a` |

The direct reader observations are outside the target resolver, whose report still records zero data reads. Python independently verifies all 229 signed relative-offset calculations against the captured bytes. [The analysis manifest](../../evidence/Ariadne/callee-dispatch-analysis/20261015/manifest.json) binds retained files and the exact reproduced report identity.
