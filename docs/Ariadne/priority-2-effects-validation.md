# Priority 2: path-driven effect decision for the first real case

Reviewed **2026-09-29 23:26 CST** against the
[Priority 2 plan](priority-2-path-driven-effects-plan.md) and the
[controlled Chromium case](priority-1-real-capture-validation.md). The
[source-bound record](priority-2-3-validation.json) includes the exact gap
inventory, a fresh real-capture replay and the 11-gate minidump regression.

The 29 captured instruction starts before the crash-IP seed have 22 reviewed
effect summaries and seven `CALL64pcrel32` sites with reviewed control but
opaque callee effects. Two reviewed `TEST` sites expose undefined AF. There
are no missing bytes or unsupported-control sites before the seed. The
faulting `MOV32rm EAX,[RBX]`, its possible `MOV64rm RBX,[RBX]` producer and
the relevant conditional branch all have exact reviewed bindings. The later
`INT3` at `0x566817922e5b` remains an explicit unsupported-control obligation
after the seed.

| Observed shape | Decision | Reason |
| --- | --- | --- |
| Seven pre-seed `CALL64pcrel32` sites | Retain opaque effects and reviewed control | A source review of CALL itself cannot establish the effects of each uncaptured callee. Narrowing RBX on ABI assumptions would hide possible origins. |
| `TEST64rr` and `TEST8rr` | Keep reviewed rules and visible undefined AF | Their flag behavior is already represented; the annotation is not an instruction-step acceptance claim. |
| Later `INT3` | Keep unsupported control | It is after the seed and does not block the accepted predecessor slice. |

No exact opcode/operand/prefix effect rule was added. This is the plan's
**source-bound no-change decision for this selected real path**: no
source-reviewable form blocks the claimed possible address producer. It is
not a claim that calls preserve RBX or that broader real workloads have full
effect coverage. New observed blockers on a different path reopen the queue.

The Priority 1 checker passed again with 28 stable focused source hashes.
Its JSON and DOT reports are byte-identical to the pre-presentation result;
the text report changed only for Priority 3. The existing minidump gate
passed all 11 components with 57 stable source hashes, including the effects
and MBT regression, native Windows/Linux decoding, formal input fixtures,
reader mutations and the two older Breakpad artifacts. No formal user64
case was promoted.
