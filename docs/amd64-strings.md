# AMD64 string and repetition foundation

Status: the C4-S control and staged-iteration foundation is implemented for the
seven assigned Volume 3 entries. No entry or form is reported complete because
data movement, I/O behavior, form legality, and complete fault/outcome binding
remain open.

## Scope and authority

The assigned entries are:

| Entry | PDF pages | Element bytes | Repeat modes |
| --- | ---: | --- | --- |
| V3-GP-045 CMPS | 207–208 | 1, 2, 4, 8 | none, REPE/REPZ, REPNE/REPNZ |
| V3-GP-059 INS | 234–235 | 1, 2, 4 | none, REP |
| V3-GP-072 LODS | 267–268 | 1, 2, 4, 8 | none, REP |
| V3-GP-088 MOVS | 301–302 | 1, 2, 4, 8 | none, REP |
| V3-GP-100 OUTS | 320–321 | 1, 2, 4 | none, REP |
| V3-GP-130 SCAS | 376–377 | 1, 2, 4, 8 | none, REPE/REPZ, REPNE/REPNZ |
| V3-GP-142 STOS | 396–397 | 1, 2, 4, 8 | none, REP |

The pinned Volume 3 source is publication 24594 revision 3.38, July 2026.
Section 1.2.6 on PDF page 54 defines the repeat prefixes. The exact PDF hash is
recorded in `Specs/AMD64/string-coverage.json`.

The dependency boundary also cites Volume 1 section 3.4.5 for upper GPR state,
the `SYS-PARTIAL-PROGRESS` Volume 2 dependency, and Volume 2 section 15.10.3 on
PDF page 601 for intercepted REP INS/OUTS context. The virtualization section
does not by itself define ordinary device execution semantics.

## Canonical implicit registers

`AMD64.Arch.GPR` now fixes the shared register identity order:

```text
0 RAX   1 RCX   2 RDX   3 RBX
4 RSP   5 RBP   6 RSI   7 RDI
8 R8    9 R9   10 R10  11 R11
12 R12 13 R13 14 R14  15 R15
```

Lean exposes `GPR.index`, `GPR.toFin`, `CPUState.gprValue`, and named accessors.
TLA+ exposes `GPRIndex`, `ReadNamedGPR`, and RAX through R15 accessors. Forms,
integer execution, and strings therefore share the same identities.

String instructions use RAX as the accumulator, RCX as the repeat counter, RDX
as the I/O port, RSI as the source pointer, and RDI as the destination pointer.
Address size chooses the low 16, 32, or 64-bit view.

## Concrete state and invariants

The pure control state contains:

```text
source pointer
destination pointer
repeat count
direction flag
six integer status flags
```

The complete status set is retained because CMPS and SCAS update CF, PF, AF,
ZF, SF, and OF as subtraction. Repeat continuation observes ZF, while the other
five flags remain architecturally visible after each completed iteration.

`Spec.Valid` enforces:

- element widths of 1, 2, 4, or 8 bytes;
- no 8-byte INS or OUTS form;
- 8-byte elements only in 64-bit mode;
- 64-bit address size only in 64-bit mode;
- no 16-bit address size in 64-bit mode; and
- REP only for INS, LODS, MOVS, OUTS, and STOS, while REPE/REPNE apply only to
  CMPS and SCAS.

The decoded-form layer still owns default-size and prefix legality. A valid
control specification does not certify one of the 52 inventoried forms.

## Count and pointer rules

Without a repeat prefix, one iteration executes regardless of the current RCX
value and RCX is preserved. With a repeat prefix, initial count zero completes
the string body without any memory or I/O stage.

After every successful repeated iteration, the address-sized count view is
decremented modulo its width. Pointer views advance by the element byte count
when DF is clear and retreat by that count when DF is set.

Address-sized writes are relational outside 64-bit mode. Volume 1 section
3.4.5 states that bits 63:32 are inaccessible and undefined in compatibility
and legacy modes and are not preserved across leaving 64-bit mode. The model
therefore constrains:

- the selected low 16 or 32 bits to the arithmetic result;
- bits 31:16 to remain unchanged after a 16-bit write;
- bits 63:32 to zero after a 32-bit write in 64-bit mode; and
- legacy/compatibility bits 63:32 to no particular value.

It does not encode undefined upper bits as zero, old data, or analysis unknown.
That final concept belongs to `CPUStateKnowledge`, outside architectural state.

## Repeat condition

REP continues when the post-decrement count is nonzero. REPE continues when
the post-decrement count is nonzero and the just-completed comparison set ZF.
REPNE continues when the post-decrement count is nonzero and the comparison
cleared ZF. Count is checked before ZF, but the Boolean result is equivalent to
the conjunction shown here.

The iteration that makes ZF terminate repetition is already committed: its
memory read, flags, pointer updates, and count decrement remain visible.

## Staged iteration order

Each kind has a distinct required sequence:

| Kind | Ordered stages before commit |
| --- | --- |
| CMPS | source memory read, destination memory read, status-flags write |
| INS | I/O read, destination memory write |
| LODS | source memory read, accumulator write |
| MOVS | source memory read, destination memory write |
| OUTS | source memory read, I/O write |
| SCAS | destination memory read, status-flags write |
| STOS | destination memory write |

Only `commitReady` can complete an iteration. Completion updates pointer/count
control and increments `completedIterations` by exactly one. The resulting
`bodyApplied` boundary still excludes RIP/fallthrough, traps, asynchronous
delivery, and architectural retirement; the parent execution layer composes
those afterward. Generic ordered
effect count is intentionally absent from the continuation. One iteration can
emit several effects, so the exception layer carries `committedEffects` and
`completedIterations` as independent values.

These stages express value/effect dependencies. They do not prevent the final
instruction rule from performing pure segment, paging, permission, or alignment
prechecks before an I/O or memory data operation when the manuals require that
priority.

## Memory binding

Lean `memoryRequest` converts source-read, destination-read, and
destination-write stages into real `MemoryModel.AddressRequest` values. It
sets address size, byte count, segment, pointer, and read/write intent.
`resolveMemoryStage` then calls the constrained M2 `resolveAccess` relation,
which performs effective-offset, segment, canonical span, paging, permission,
and alignment checks. It is not a Boolean success callback.

Source segment override selection is supplied explicitly because prefix/form
legality remains I2-owned. Destination references use ES; M2's 64-bit rule
suppresses its ordinary base there. I/O stages deliberately return no memory
request.

`AMD64StringsMemory` and `lean/AMD64/StringsMemory.lean` bind the five
memory-only kinds to resolved and captured bytes:

- MOVS reads the complete source element before replacing destination bytes;
- STOS extracts little-endian bytes from the selected RAX view;
- LODS assembles little-endian bytes and constrains the selected RAX write;
- CMPS reads source before destination and computes source minus destination;
- SCAS reads destination and computes accumulator minus destination.

The M2 `MemoryState.read` result is folded only when every byte is available.
Any unavailable byte produces a modeling-unavailable result with unchanged CPU
and memory. It is never zero and never converted into an architectural fault.

MOVS writes the bytes captured from the before-memory snapshot. A following
iteration consumes the committed after-memory, which gives the correct behavior
for overlapping ranges without copying the entire source in advance. TLA+
fixtures exercise a forward-overlap chain where the second iteration reads the
byte written by the first.

CPU data writes are relational where the architecture leaves legacy upper bits
undefined. Other GPRs and all unrelated CPU fields are framed. A separate
relational commit applies pointer/count control and chooses `bodyApplied` or
the next continuation.

## I/O boundary

IO1 now provides explicit width-aware permission snapshots, finite device
rules, strongly ordered port events, and successful INS/OUTS bindings. Missing
rules or captured permission bytes remain modeling-unavailable without
inventing returned data, acceptance, or faults.

The following ordering questions remain explicit:

- whether an INS port read is externally visible if the later destination
  memory write faults;
- the priority of I/O permission failure against destination memory faults;
- whether OUTS resolves/reads memory before every I/O permission and device
  effect in each applicable mode; and
- mixed failure policy for multi-byte port, memory, and device alternatives.

The successful binding requires every permission, boundary, ordering, memory,
and device condition to be discharged. Volume 3 and Volume 2 do not close all
mixed-failure priorities, so those alternatives remain `orderingOpen`.

## Exceptions, interruption, and restart

The exception layer now separates:

```text
committedEffects
completedIterations
remainingIterations
```

The strings continuation and restart record preserve the control state after
the last completed iteration plus its independent completed count. A fault or
interrupt restarts at the original instruction address. The current iteration
does not increment the completed count until all required stages reach
`commitReady`.

`accessFaultOutcome` binds an already resolved M2 `AccessFault` to
`Exceptions.prefixFault` and proves that committed-effect count remains
independent of completed-iteration count. The instruction-specific relation
now preserves the before CPU, before memory, count, and pointers for a failing
current iteration. Successful I/O outcomes now bind device and memory effects
with distinct effect/iteration counts. Source-read event commitment on a later
destination or permission fault remains open. INS is especially open when an
external read may have consequences before a destination-memory failure. The
JSON artifact keeps these obligations visible.

## Comparison kernel

CMPS orders source as the left subtraction operand and destination as the right
operand. SCAS orders the accumulator as left and destination memory as right.
Lean reuses `IntegerSemantics.subResult` and `applyStatusFlags`; TLA+ reuses
`SubResult`. The adapter proves that all six status flags are applied while DF
is preserved.

## Abstraction boundaries

The model preserves element/address sizes, mode, repeat kind, count, DF,
status flags, pointer views, ordered operand stages, committed-iteration count,
and restart address.

It currently erases concrete memory bytes, actual device behavior, decoder
bytes, performance fast-string mechanisms, caches, and microarchitectural
interrupt timing. Memory and I/O effects are separate architectural components,
not erased implementation details; they remain open bindings rather than
arbitrary choices.

## Coverage record

`Specs/AMD64/string-coverage.json` contains seven entry rows and all 52 current
form IDs from `forms.json`. The five memory-only entries are marked partial
memory-iteration bindings. INS and OUTS add successful explicit-device bindings
while retaining mixed-failure ordering obligations. Every form binding is open.
The checker rejects drift from the form/source inventories and rejects any
full-entry claim at this stage.

## Validation

```sh
python3 tools/check_amd64_strings.py check
cd Specs
apalache-mc typecheck AMD64StringsChecks.tla
tlc -deadlock -cleanup -config AMD64Strings.cfg AMD64StringsChecks.tla
apalache-mc typecheck AMD64StringsMemoryChecks.tla
tlc -deadlock -cleanup -config AMD64StringsMemory.cfg AMD64StringsMemoryChecks.tla
cd ../lean
lake env lean AMD64/Strings.lean
lake env lean AMD64/StringsMemory.lean
```

The finite TLA+ control fixture covers initial zero-count body completion, one-iteration
REP body completion, count decrement, source/destination stage order, INS/OUTS I/O
stage order, comparison ZF, relational legacy write witnesses, and 64-bit-mode
32-bit zero extension. The memory fixture covers captured-byte reads, explicit
unavailability, little-endian load/store, comparison flags, memory fault frames,
and two successive overlapping MOVS writes. Lean theorems quantify over arbitrary word values for
the view constraints, repeat conditions, frames, comparison flag projection,
memory-stage separation, captured-byte conversion, CPU/memory fault and
unavailable frames, successful relational completion, and restart preservation.

These results establish the control foundation and partial binding for five
memory-only entries. They do not close any of the seven instruction entries or
52 forms.
