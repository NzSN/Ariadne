# Priority 4 real-path control review

Reviewed 2026-09-30 for the Windows Electron workload in the
[qualification plan](../../Plans/completed/priority-4-workload-performance-plan.md#2026-09-30-qualification-run).
The eight bindings below admit ordinary continuation while retaining opaque
effects: every catalogue cell remains a possible input and write, with no
definite replacement. They do not execute an instruction or assert fault
retirement, stack validity, historical control flow, or a formal user64 case.

Source: [AMD Volume 3 revision 3.38](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB),
SHA-256 `e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee`,
checked against the downloaded PDF. PDF pages are one-based. The forms refer
to GPR/ordinary-memory operations; segment-register and control-register
variants are excluded. Memory and stack faults remain possible, so the
continuation is a static local possibility rather than proof of execution.

| Exact LLVM 20.1.2 opcode | Native bytes at VA 4096 | Admitted operands | AMD entry and PDF pages |
| --- | --- | --- | --- |
| `PUSH64r` | `4156` | One 64-bit GPR; implicit stack effects stay opaque | V3-GP-110, 339–340 |
| `POP64r` | `415e` | One 64-bit GPR; implicit stack effects stay opaque | V3-GP-104, 327–328 |
| `ADD32rm` | `034807` | Tied 32-bit destination/source GPR, 32-bit memory input | V3-GP-007, 131–132 |
| `ADD64rm` | `480307` | Tied 64-bit destination/source GPR, 64-bit memory input | V3-GP-007, 131–132 |
| `MOV8mi` | `c644242000` | 8-bit memory destination and 8-bit immediate | V3-GP-080, 282–284 |
| `CMP8mi` | `807f0c01` | 8-bit memory input and 8-bit immediate | V3-GP-044, 204–206 |
| `ADD32i32` | `05d3feffff` | Implicit EAX and encoded 32-bit immediate | V3-GP-007, 131–132 |
| `CMP32i32` | `3df0000000` | Implicit EAX and encoded 32-bit immediate | V3-GP-044, 204–206 |

The reviewed envelope accepts no legacy prefix and at most one REX.
`REX.W` is required only for `ADD64rm` and excluded on the other seven forms.
Memory uses default 64-bit address registers or RIP-relative addressing,
scales 1/2/4/8 and no segment override. Register widths, operand counts,
ADD ties, immediate containers and native ordinary-control observations are
checked. Adjacent widths, memory PUSH/POP, REX.W aliases, LOCK/REP, duplicate
prefixes and address/operand overrides remain outside these new bindings.

The existing native matrix exercises every binding on Windows and Linux.
Additional tests check retained earlier origins, all-cell uncertainty,
empty definite replacements and rejected prefix/shape/control variants.
The preparation identity advances to `user64-effects-v1.2`; prior versioned
report identities are historical records. Analyzer scheduling and the formal
AMD64 acceptance ledger are unchanged.
