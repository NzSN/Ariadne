# I5b source and independent admission review

## Context and follow-up

**Status.** B0 source/encoding review frozen on 2026-10-07 before admission code.
The finite decision model and fixture generator are independent validation;
they do not qualify native lifting, reports or real Windows captures.

**Why this document exists.** The [selected design](i5b-zero-base-offset-design.md)
requires an encoded base-role receipt rather than guessing from merged BIL terms.

**What this document establishes.** Exact LLVM row positions for the six forms,
the independent encoding/arithmetic fixture oracle, output accounting and frozen
measurement contract.

**Where to go next.**

- [B0–B5 plan](../../Plans/i5b-zero-base-offset.md) — binding and implementation exits.
- [Independent fixture generator](../../tests/input/fixtures/make_i5b.py) and
  [manifest](../../tests/input/fixtures/i5b/manifest.json) — exact bytes/context and expected results.
- [Decision model](../../Specs/AriadneZeroBaseOffset.tla) and
  [check script](../../Specs/check-zero-base-offset.sh) — finite admission-gated conclusions.
- [Performance contract](../../tests/input/fixtures/i5b/performance.json) — frozen budgets before measurement.

**What remains unresolved.** B0 does not provide universal opcode coverage,
hardware semantics or capture acceptance. Indexed/Linux/historical-provenance
questions remain outside this first profile.

## Native decoded record source

[decode.cpp](../../native/llvm_mc/decode.cpp) emits protocol 2 operand count,
registers, signed MC immediate values, descriptor facts and control tail from
LLVM MC 20.1.2. Register number zero is explicitly emitted as `r:NONE`.
[protocol.rs](../../src/llvm_mc/protocol.rs) validates bounded framing, counts,
tags and control classification. The inspected decoder SHA-256 is
`45dad913d912aed489a99a150edc846389877ef72cb9218b46b8e2e555ad813c`.

Zero-based row positions, all with exactly six operands:

| Forms | Memory tuple | Other operand | Width / operation |
| --- | --- | --- | --- |
| MOV32mi, MOV64mi32 | 0 base, 1 scale, 2 index, 3 displacement, 4 segment | 5 immediate payload | 32/64 bits; store |
| MOV32mr, MOV64mr | 0 base, 1 scale, 2 index, 3 displacement, 4 segment | 5 source register | 32/64 bits; store |
| MOV32rm, MOV64rm | 1 base, 2 scale, 3 index, 4 displacement, 5 segment | 0 destination register | 32/64 bits; load |

The six native rows were inspected at distinct semantic VAs with independently
chosen encodings for `[RAX+8]`. For example, `c7400805000000` decodes as
MOV32mi with `r:RAX i:1 r:NONE i:8 r:NONE i:5`; `8b4008` decodes as
MOV32rm with `r:EAX r:RAX i:1 r:NONE i:8 r:NONE`.
The immediate/source payload is not an address input.

## Independent encoding and arithmetic oracle

The fixture generator supplies explicit reviewed byte strings, not decoder-
generated encodings. ModRM memory forms select implicit displacement zero,
signed disp8 or signed disp32; REX extension and SIB base/index sentinel cases
have separate fixtures. MC signed displacement must agree with those bytes.
`c704050800000005000000` is an index-only RAX form, while
`c704250800000005000000` has neither a GPR base nor index. Neither is admitted
as a base simply because the normalized arithmetic resembles a base case.

The 57-case manifest independently supplies affine terms/constant, register
observations and expected EA computed with Python integers modulo 2^64. It
includes positive/nonzero-base/no-displacement controls for each of the six
forms, negative disp8/disp32, RSP/RBP/R12/R13 addressing, SIB/index-only/absolute/
RIP controls, payload changes, data-span/context/exception negatives and aliases.
The expected hypothesis is captured encoded base zero AND displacement nonzero;
admission negatives explicitly override the answer to unknown. Arithmetic does
not call the Rust evaluator or consume BAP/LLVM output as an oracle.

The TLA+ model uses representative zero/nonzero bases and negative/zero/positive
displacements. Its decision predicate does not depend on magnitude. Real u64
arithmetic remains independently exercised by the fixture/Rust tests, including
nonzero base with EA zero. Model checking and Rust conformance are separate.

## Limits and timing frozen before implementation

The existing full I5a context bundle has 32 evidence records and 32 claims.
I5b adds its decoded receipt and derived roles/base/displacement/decision. Its
separate 64/64 defaults fit this finite bundle; the original I5a 32/32 defaults
are preserved. Exact-fit/zero/tiny budget controls remain mandatory.

The performance contract freezes one warm-up and five measured release repeats,
10 ms combined binding/assessment/all-format render median and 1,500 ms native-
default CLI median on the declared small corpora. No performance measurements
or acceptance are claimed by this source review.
