# AMD64 port-I/O foundation

Status: IO1 provides source-grounded permission, device-environment, event,
direct IN/OUT CPU body binding, and successful INS/OUTS contracts. Shared form
acceptance remains open. Mixed permission/memory/device failure ordering
and cross-FFFF device behavior remain explicit obligations. No instruction
entry or form is complete.

## Authority and scope

The pinned sources are:

- Volume 1 revision 3.25 sections 3.8.1 through 3.8.3, PDF pages 134–136;
- Volume 2 revision 3.45 section 12.2.4, PDF pages 436–440;
- Volume 2 section 10.3.8, PDF page 402, for SMM I/O restart;
- Volume 3 revision 3.38 IN, INS, OUT, and OUTS entries on PDF pages 230–235
  and 319–321; and
- Volume 3 section 1.2.6 for repeated INS/OUTS.

`Specs/AMD64/io-form-supplement.json` records all 24 current forms without
editing the shared `forms.json`. Shared form rows remain pending semantic review
and missing implementation, so the supplement cannot close them.

## Port, width, and data

Port I/O uses a separate 16-bit address space. Requests carry direction, base
port, a width of 1, 2, or 4 bytes, least-significant-first output data, and a
strong-order sequence number.

Immediate port operands are zero-extended from eight bits. DX supplies its low
16-bit unsigned value. IN and OUT use AL, AX, or EAX for 8, 16, or 32-bit data.
An effective 64-bit operand size still performs a 32-bit I/O operation. INS and
OUTS use DX and support the same three data widths.

A word covers two consecutive byte ports and a doubleword covers four. Port
alignment is not required. Cross-FFFF device behavior is not stated precisely
enough by the pinned sources to choose wrapping or rejection when IOPL bypasses
the bitmap, so that case returns `boundaryUnspecified`. If bitmap checking is
required, uncovered consecutive bits produce #GP before device binding.

## Permission contract

The permission bitmap is consulted when the mode is virtual-8086 or CPL is
numerically greater than RFLAGS.IOPL. Otherwise IOPL authorizes the access
without reading the bitmap.

When the bitmap is required, every consecutive byte-port bit must be
represented and clear. A set bit or a port beyond the represented TSS bitmap
yields #GP(0). `PermissionSnapshot` distinguishes:

- a ready effective covered/denied map;
- a real TSS bitmap page fault retaining `AccessFault`, CR2, and PFEC; and
- unavailable captured bitmap bytes, which are an analysis obligation.

`permissionSnapshotFromReads` accepts one captured result per required port bit
and produces a ready snapshot only when the reads exactly cover the request's
port span and every bit is available. A missing or unavailable result produces
the unavailable alternative. TSS resolution faults use the page-fault
constructor.

Unavailable bytes never become a clear bit, set bit, zero, or architectural
fault. The older M2 `ioPermitted` Boolean remains an effective projection and
is insufficient evidence for IO1.

Complete virtual-8086/VME variations, additional TSS descriptor/read faults,
and task-switch interactions remain open.

## Explicit device environment

`DeviceEnvironment` is a finite list of rules. Each rule fixes direction, base
port, width, exact output or returned input bytes, and byte-transaction order.
`DeviceStep` is relational over matching valid rules and cannot mutate CPU or
memory. Multiple matching rules represent device nondeterminism declared by
the environment. No matching rule produces `deviceUnavailable`, not a fault or
zero-valued input.

Every completed `IOEvent` is marked strongly ordered. Request sequence and
internal byte-transaction order are separate fields. Aligned accesses use
increasing byte order. For unaligned multi-byte accesses, Volume 1 says bus
transaction order is implementation-dependent, so a rule may supply any
permutation of the byte offsets.

The ordering context requires prior writes to have completed and fixes the next
event sequence. This represents that IN waits for earlier writes, OUT blocks
following progress until its write completes, and port operations remain
strongly ordered against I/O and memory operations.

## Transfer dispositions

The shared pre-body relation distinguishes:

```text
completed(event)
generalProtection
pageFault(accessFault)
permissionUnavailable
boundaryUnspecified
waitingForOrdering
deviceUnavailable
```

Permission denial, page fault, capture gaps, device absence, and ordering wait
cannot collapse into an arbitrary instruction callback. General protection
maps through the exception foundation to #GP(0).

The direct IN/OUT execution lane will compose a completed event with AL/AX/EAX
read or writeback and its `bodyApplied` boundary. IO1 does not claim that
composition itself. It provides checked immediate8/DX request constructors,
least-significant-first accumulator output bytes, and the relational AL/AX/EAX
input-write contract needed by that lane.

## Successful INS and OUTS bindings

INS and OUTS are bound only when all required operations succeed under an
explicit device rule.

For successful OUTS:

1. M2 resolves and reads the complete source memory element.
2. Missing captured source bytes return modeling-unavailable.
3. The output request contains exactly those bytes.
4. Permission, ordering, boundary support, and a matching device rule produce
   the I/O event.
5. Effect order is memory-read then I/O-write.
6. RSI and RCX update through C4 control and produce continuation or
   `bodyApplied`.

For successful INS:

1. M2 establishes a resolved writable destination for the successful case.
2. Permission and the device rule produce exact input bytes.
3. The event precedes the memory write in the ordered effect list.
4. `MemoryState.write` stores all bytes and updates capture state.
5. RDI and RCX update through C4 control and produce continuation or
   `bodyApplied`.

Successful-case prevalidation does not assert priority when destination
resolution and permission/device failure coexist. Those alternatives return
`orderingOpen` with named possible effect kinds rather than an empty committed
effect claim. INS records the possible I/O read before a destination fault.
OUTS records the unresolved commitment of a source read before a permission
fault. OUTS also preserves concrete prior source-read candidates when a later
result is unavailable, while final event commit policy remains open.

Effect-prefix count remains independent from completed-iteration count. SMM's
choice to retry or proceed after interrupted I/O is a later system transition,
not ordinary instruction-body behavior.

## Form supplement

The supplement records for each form its stable IDs, direction, byte width,
immediate8 versus DX source, 64-to-32-bit normalization, repeat availability,
permission/unaligned/boundary obligations, and owning binding lane.

Direct IN/OUT forms are `direct-body-bound-shared-form-open`. INS/OUTS remain
`partial-success-binding-ordering-open`. Full-entry and full-form counts are
zero.

## Validation

```sh
python3 tools/check_amd64_io.py check
python3 tools/check_amd64_strings.py check
cd Specs
apalache-mc typecheck AMD64IOChecks.tla
apalache-mc typecheck AMD64IOStringsChecks.tla
tlc -deadlock -cleanup -config AMD64IO.cfg AMD64IOChecks.tla
tlc -deadlock -cleanup -config AMD64IOStrings.cfg AMD64IOStringsChecks.tla
cd ../lean
lake build AMD64.IO AMD64.IOStrings
lake env lean AMD64/IOAudit.lean
```

Fixtures cover IOPL bypass, mandatory VM86 bitmap use, multi-byte denial,
strong events, explicit unaligned byte order, boundary handling, successful
OUTS read-before-I/O, successful INS I/O-before-write, capture updates, C4
pointer/count commits, and the named mixed-failure obligation.
