# LLVM MC protocol 2

Implemented for LLVM MC 20.1.2. Default invocation and `--version` retain
protocol 1 behavior. `--protocol-version` must return exactly:

```text
ariadne-llvm-mc 20.1.2 protocol 2
```

Invoke `--protocol=2` with the existing `decimal-VA hex-bytes` input lines.
Each response is one newline-terminated, whitespace-separated record:

```text
v2 OPCODE N OPERAND... DEFS FLAGS U IMPLICIT_USE... D IMPLICIT_DEF... TIE... VA STATUS LENGTH KIND TARGET
```

- `OPCODE` is the pinned LLVM opcode name, or `-` for invalid decode.
- `N` is the operand count; exactly N operands and N trailing tie indices occur.
- Operands are `r:REGISTER`, `i:SIGNED_I64` or `x:unsupported`.
  `r:NONE` is LLVM's zero-register sentinel in address tuples.
- `DEFS` is the descriptor's explicit definition count, at most N.
- `FLAGS` is a three-bit mask: possible load (1), possible store (2),
  unmodeled effects (4). These fields are inspection evidence, not kill rules.
- `U` and `D` count the implicit register names that follow each count.
- Each tie is `-1` or a different operand index in `0..N`.
- The final five fields have the same meanings as protocol 1. A successful
  decode has length 1..15 and a control kind. `invalid` requires length zero,
  absent kind/target, `-` opcode and empty metadata. `unsupported` retains
  successful-decode operands/length but no kind/target.

Counts are bounded by 32; names are 1..96 ASCII letters/digits/underscores.
Records are shorter than 4096 bytes; stdout is bounded by 4096 times the input
record count, stderr by 4096 bytes. Each process exchange has a 30-second
limit, including exit after stream closure. All streams are drained concurrently;
limit/error handling kills and reaps the helper. The helper is a trusted local
executable, not an isolation interface for arbitrary descendant processes.

The parser rejects malformed or duplicate/unexpected/missing records and
contradictory control targets. Preparation additionally validates the decoded
length against selected bytes and matches only reviewed opcode/operand shapes.
An unfamiliar well-formed instruction yields an analysis gap; a corrupt
protocol response fails preparation.

Example (`mov rax, rbx`):

```text
v2 MOV64rr 2 r:RAX r:RBX 1 0 0 0 -1 -1 4096 ok 3 ordinary -
```

The checked observations for all 137 admitted opcode identities are frozen in
[effects-v2.tsv](../../tests/fixtures/effects-v2.tsv). Their purpose is detecting
changes in decoder layouts. The tests also separately assert architectural
read/write expectations and resulting analysis behavior. Updating snapshots
alone cannot justify a semantic change.
