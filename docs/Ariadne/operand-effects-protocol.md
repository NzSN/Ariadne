# LLVM MC protocol 2

## Context and follow-up

**Status.** LLVM decode protocol reference; legacy semantic rules are not the production backend.

**Why this document exists.** [Effects design](operand-effects-design.md) requires typed operands and instruction facts rather than assembly text.

**What this document establishes.** Protocol 2 carries lengths, control facts and structured operands across the LLVM helper boundary. These facts can validate decoding independently of BAP semantics.

**Where to go next.**

- [Historical rule matrix](operand-effects-rules.md) — records how decoded shapes were originally bound to effects.
- [BAP boundary](bap-semantic-backend-design.md) — specifies which decoded facts still serve as independent reference checks.

**What remains unresolved.** Decoded operand metadata alone is not a sound complete instruction-effect model. Production effect derivation belongs to the BAP projection; the old rule path is reference material.

For the wider context, see the optional [documentation map](../documentation-map.md).

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
record count plus 128 bytes for a checked header, stderr by 4096 bytes. Each process exchange has a 30-second
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

The checked observations for all 147 admitted opcode identities are frozen in
[effects-v2.tsv](../../tests/fixtures/effects-v2.tsv). Their purpose is detecting
changes in decoder layouts. The tests also separately assert architectural
read/write expectations and resulting analysis behavior. Updating snapshots
alone cannot justify a semantic change.


## Explicit Linux target profile

The legacy flags above retain the Windows AMD64 target. A Linux request uses
`--protocol-version=linux`, requiring exactly:

```text
ariadne-llvm-mc 20.1.2 protocol 2 target x86_64-unknown-linux-gnu
```

Decode with `--protocol=2-linux`. The row grammar is unchanged. The Rust
`prepare_with_target()` method and `prepare_captured_batch()` seam record the
selected target triple in `PreparationIdentity`; default `prepare()` remains
Windows-compatible. Minidump input selects the target from validated platform
metadata. Calls remain opaque under both profiles; no ABI preservation rules
are inferred. The input native gate exercises the full frozen opcode registry
under both targets.

## Checked batch invocation

The checked one-shot preparation mode uses `--protocol=2-checked` or
`--protocol=2-checked-linux`. A single invocation emits the exact version/target
line above, followed by the unchanged protocol-2 records. The parser requires
that header before accepting any rows. This replaces a separate version
process for each batch; legacy version and decode modes remain available.
Raw per-instruction records, evidence identities and row/error bounds keep
their existing meaning. Rebuild the helper together with the updated Rust
adapter; an older helper lacking the checked mode is rejected.


## Snapshot-owned production reference session

The BAP production backend now reuses one checked LLVM reference process across
batches for one snapshot/target. It uses the same checked header and unchanged
protocol-2 rows; each batch must return exactly its requested addresses before
its deadline. Malformed, duplicate, unsolicited, missing or trailing rows poison
the session. Shutdown closes input, requires clean EOF/exit and reaps the child.
Reference-executable digests are checked across the preparation lifetime.

The standalone LLVM byte-span/effect adapter remains one-shot. This process
reuse adds no LLVM effect fallback. The [I4 performance delivery](i4-performance-validation.md)
qualifies the changed BAP preparation, and the [current backend guide](modules/bap.md)
describes ownership and shutdown.
