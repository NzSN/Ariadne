# I5a source and finite admission review

## Context and follow-up

**Status.** H0 source/fixture baseline, 2026-10-03. The interpretations and
independent expectations were established before admission implementation; the
implemented native tests now exercise the finite corpus.

**Why this document exists.** The [I5a design](i5a-zero-address-design.md) requires
exception-context evidence and exact-form admission before a definite zero-address
assessment can be made. Existing producer fixtures lack that context evidence.

**What this document establishes.** Reviewed field layouts, validity groups,
finite instruction/address cases and the corresponding independent fixture oracle.
It is not instruction-step verification or real Windows acceptance.

**Where to go next.**


- [2026-10-05 Windows I4 replacement](i4-windows-repin-validation.md) — supersedes the older missing-artifact obligation with an independently inspected active case; correctness passes; the later [native performance qualification](i4-performance-validation.md) meets the unchanged CLI budget.

- [Delivery and validation](i5a-validation.md) records native checks, mutation
  sensitivity and the separate acceptance tiers.
- [Implemented contracts](i5a-contracts.md) show how these facts are bound and
  assessed, including limits and report validation.
- [H0–H5 implementation plan](../../Plans/i5a-zero-address.md) owns implementation
  and qualification of this first profile.
- [Fixture generator](../../tests/input/fixtures/make_i5a.py) lists raw bytes,
  context facts and expected arithmetic without using the assessment evaluator.
- [Fixture manifest](../../tests/input/fixtures/i5a/manifest.json) binds the
  synthetic artifacts and their expected conclusions.

**What remains unresolved.** Matching this finite corpus is not universal form
coverage. The [native I5a successor](i5a-native-qualification.md) qualifies the
source/fixture and both controlled Windows tiers; the earlier
[demo timing miss](crashpad-demo-validation.md) remains historical. At the
source-review checkpoint, original-Windows I4 was unexercised. The
[later I4 re-pin](i4-windows-repin-validation.md) passes correctness, and its
[performance successor](i4-performance-validation.md) meets the separate fixed CLI budget.

The [documentation map](../documentation-map.md) is optional navigation.

## Reader and field meanings

Baseline: `minidump`/`minidump-common` 0.26.1 from the root lockfile, BAP helper
and runtime pinned by `native/bap/toolchain.lock.json`, and LLVM MC 20.1.2 as the
independent decoded-fact reference. The crate's `format.rs` definitions of
`MINIDUMP_EXCEPTION_STREAM`, `MINIDUMP_EXCEPTION` and `CONTEXT_AMD64` agree with
the reviewed little-endian offsets below. Existing range/count validation remains
in the reader; zero-filled bytes do not override context validity flags.

Within the 168-byte exception stream: thread ID is at offset 0 (u32), code at 8
(u32), flags at 12 (u32), chained record at 16 (u64), exception location at 24
(u64), parameter count at 32 (u32), and up to 15 u64 parameters begin at 40.
The context descriptor contains byte size at 160 and artifact RVA at 164.
These RVAs are file offsets, not semantic virtual addresses.

The [Windows exception contract](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception/)
defines access-violation parameters independently of exception location. The
first parameter identifies operation and the second inaccessible data. I5a
admits only read/write access violations with coherent selected-site evidence.
The hardware/pre-access interpretation stays an explicit premise; record flags
cannot independently prove a hardware origin.

The AMD64 context places flags at 48 (u32), RFLAGS at 68 (u32), GPRs from RAX at
120 through R15 at 240 in the declared struct order, and RIP at 248 (u64).
CONTROL (bit 0) permits RIP/RSP/RFLAGS; INTEGER (bit 1) permits the other GPRs.
The AMD64 architecture flag must be present. Preserve the exception stream's own
context rather than merging values from a thread-list context.

## Exact forms and oracle

The generator lists six scalar MOV forms already observed in the BAP corpus:
`MOV32mi`, `MOV64mi32`, `MOV32rm`, `MOV64rm`, `MOV32mr` and `MOV64mr`. Its forms
exercise base-only, base/index/scale, positive and negative displacement, and
RIP-relative addresses. Immediate/store payloads do not contribute address terms.

Expected values use Python integers and an explicit modulo 2^64 calculation over
manually listed terms/constants, not the Rust evaluator or BAP's output. For the
RIP-zero case, `48 8b 05 f9 ef bf ff` at `0x401000` has next IP `0x401007` and
signed displacement `-0x401007`; the expected address is zero. The ordinary RIP
case uses next IP plus eight. Neither case substitutes a different captured RIP
into the already normalized constant.

The 41-case finite corpus includes invalid/missing groups and parameters, different
contexts, RIP/location/data-span disagreements, operation/platform exclusions,
guarded prefixes, stack instructions, excluded ranges and span limits. Old Stage
B artifacts remain unchanged and produce unknown in the native regression for
this new question. Separate reader tests reject malformed extents/counts, and
domain tests exclude conditional/multiple accesses and unreviewed projections.

## Resource accounting

A full ordinary two-parameter context contains eight exception/descriptor fields,
two parameters, one context-flags field and eighteen register observations
(sixteen GPRs, RIP and RFLAGS). With record/context extents and one instruction,
this is at most 32 evidence records. Twenty-nine observed field claims, one
instruction observation, one numeric fact and one conclusion fit 32 claims.
Extra retained parameters or tighter caller limits can produce unknown/truncated
output. This bounds record construction, not a universal latency guarantee.
