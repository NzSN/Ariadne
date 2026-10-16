# Instructions that calculate RAX at the first callee jump

Restored on 2026-10-16 from the retained captured instruction/table evidence. The jump is at **`0x7ff77443da0e`**. Other instructions separate the setup and dispatch blocks below.

```asm
; Initialize the table bases on the entry corridor:
0x7ff77443d9b8  lea    r15, [rip+0x07654371] ; R15 = 0x7ff77ba91d30
0x7ff77443d9bf  lea    r12, [rip+0x0765504a] ; R12 = 0x7ff77ba92a10

; ... intervening instructions ...

; Load and constrain the selector:
0x7ff77443d9eb  mov    edi, dword ptr [rsi+0x38]
0x7ff77443d9ee  cmp    rdi, 0x7f
0x7ff77443d9f2  ja     0x7ff77443e9f1

; Translate selector to case index:
0x7ff77443d9f8  movzx  ebx, byte ptr [rdi+r15]
0x7ff77443d9fd  cmp    rbx, 0x75
0x7ff77443da01  ja     0x7ff77444133a

; Form the final jump address:
0x7ff77443da07  movsxd rax, dword ptr [r12+rbx*4]
0x7ff77443da0b  add    rax, r12
0x7ff77443da0e  jmp    rax
```

The normal path through these checks has selector at most 127 and index at most 117. The two instructions directly forming the final RAX are `movsxd` and `add`:

```text
slot   = R12 + RBX × 4
offset = signed 32-bit value read from slot
RAX    = sign_extend_64(offset) + R12
```

## Example from captured table bytes

With the shown bases and selector 65 (`A`), the byte map returns index 95:

```text
slot   = 0x7ff77ba92a10 + 95 × 4
       = 0x7ff77ba92b8c
bytes  = 00 b0 9a f8
offset = -0x07655000

After MOVSXD:
    RAX = 0xfffffffff89ab000
After ADD:
    RAX = 0x00007ff77443da10   (64-bit addition)
After JMP:
    RIP = 0x00007ff77443da10
```

The selector is used by the earlier lookup. `jmp rax` consumes the destination address already in RAX. These are conditional table calculations, not a recovered earlier selector value or an executed-path claim.

[Detailed first-jump explanation](ariadne-first-callee-jump-explained-20261015.html), [case-4 report](ariadne-case4-analysis-20261015.html).

## Context and follow-up

**Status.** Retained instruction and table-arithmetic explanation, restored on 2026-10-16.

**Why this document exists.** It preserves the conversation explanation associated with the [captured table evidence](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/captured-tables.json) and [first-jump explanation](ariadne-first-callee-jump-explained-20261015.md).

**What this document establishes.** The body records the stated mechanism, examples and evidence boundaries as of the report date.

**Where to go next.** Use the [captured table evidence](../../evidence/Ariadne/callee-dispatch-analysis/20261015/artifacts/captured-tables.json) and [first-jump explanation](ariadne-first-callee-jump-explained-20261015.md); the [report index](ariadne-reports-index.md) links related explanations.

**What remains unresolved.** The illustrated selector fixes a conditional destination; the report does not establish the selector on every incoming path.
