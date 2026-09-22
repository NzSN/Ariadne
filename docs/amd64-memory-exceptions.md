# AMD64 memory and exception foundation

This component defines the shared address, access, protection, exception,
commit, and restart contracts used by later general-purpose instruction rules.
It is a foundation, not complete Volume 2 execution. The authoritative rules
are in [AMD64Memory.tla](../Specs/AMD64Memory.tla) and
[AMD64Exceptions.tla](../Specs/AMD64Exceptions.tla). Lean provides typed
definitions, general proofs, and a reviewed transcription boundary in
[Memory.lean](../lean/AMD64/Memory.lean) and
[Exceptions.lean](../lean/AMD64/Exceptions.lean).

The complete dependency inventory is machine-readable in
[system-dependencies.json](../Specs/AMD64/system-dependencies.json). Its source
IDs refer to [source-sections.json](../Specs/AMD64/source-sections.json), whose
page numbers are one-based PDF pages in the pinned manuals. The relevant source
baseline is AMD Volume 1 revision 3.25 from May 2026, Volume 2 revision 3.45
from July 2026, and Volume 3 revision 3.38 from July 2026.

## The address and access machine

An access passes through these states:

```text
decoded form and CPU state
  -> validate mode/default/address-size pair
  -> truncate the raw effective offset to 16, 32, or 64 bits
  -> select the effective segment cache and base
  -> validate segment type, privilege, and complete offset span
  -> add the segment base to obtain a linear address
  -> validate canonicality where long mode requires it
  -> translate every byte through the effective page map
  -> validate effective page permissions
  -> apply ordinary alignment checking
  -> emit ordered access events and read or update byte values
```

The model keeps effective offsets, linear addresses, and physical addresses as
distinct types or fields. It never treats a virtual address as a file offset.
All architectural addresses are full 64-bit Boolean vectors. TLA+ addition is
a relation with a checked 65-bit carry certificate; it does not convert the
word to a TLC host integer or choose an arbitrary result. Lean computes the
same ripple-carry operation directly.

Volume 1 sections 2.1 and 2.2, PDF pages 47-56, define the basic distinction.
Volume 2 sections 1.1 and 1.2, PDF pages 64-73, add the system view. The
foundation preserves the following rules:

- Compatibility mode accepts 16-bit or 32-bit effective-address calculations,
  then zero-extends them for long-mode paging.
- The 64-bit submode accepts 64-bit or 32-bit address size. Prefix 67h selects
  32 bits; a 16-bit address size is not available there.
- Real and virtual-8086 mode default to 16-bit address size and can use the
  32-bit alternate size.
- After segment-base addition, protected, compatibility, real, and virtual-8086
  modes retain a 32-bit linear carrier. A20 is an explicit later physical-
  address transformation. With A20 enabled, `FFFF:0010` reaches linear and
  physical `0x100000`; with A20 disabled, physical bit 20 is masked.
  The evaluator reports an explicit unsupported boundary for disabled-A20
  combined with paging; it does not return an unchecked translation for that
  configuration.
- I2 still owns the binding from the decoded prefix and CS.D/CS.L to the chosen
  size. `AddressSizePermitted` rejects impossible combinations but does not
  decode prefix 67h.

Canonicality uses the profile's implemented linear-address width. Every bit
above the implemented sign bit must equal that sign bit. A non-canonical
ordinary data reference produces #GP(0); an implied stack reference produces
#SS(0). Volume 1 section 2.2.2 is on PDF page 53. Volume 2 sections 1.1.3 and
5.3.1 are on PDF pages 67 and 204.

## Segmentation

The component consumes the architectural-state worker's `CPUState`: execution
mode, CPL, RFLAGS.AC, RIP, and effective hidden segment caches. It does not
create a second CPU-state representation.

In the 64-bit submode, ordinary DS, ES, and SS references use base zero and
ignore their cached limits and attributes. FS and GS retain their effective
bases. Compatibility, protected, real, and virtual-8086 modes use the cached
base and access attributes. The common legacy predicate checks:

- usable and present state;
- CPL, selector RPL, and descriptor DPL for the selected segment class;
- executable, readable, or writable type as required by the access;
- both the first and last effective byte against a normal segment limit;
- the lower and upper bounds for expand-down segments, using the descriptor's
  default-size attribute.

These contracts come from Volume 2 chapter 4, especially sections 4.3.3,
4.5, 4.9-4.13 on PDF pages 139-188. Descriptor loads, table lookup, null
selector distinctions, and far-transfer gate checks remain separate tasks.
The segment cache retains the conforming-code attribute and validity requires
it only on executable segments. Conforming versus non-conforming code privilege
rules are not closed by the ordinary data-access predicate; C3 must apply them
to direct, gate, and return control transfers. The loaded-cache access
predicate must not be mistaken for those operations.

## Paging and protection

`PageMap` is an explicit set or list of effective page mappings. A mapping has
a full-width linear tag, physical tag, page offset width, effective U/S, R/W,
NX, present, reserved, shadow-stack, protection-key, and memory-type facts.
Valid maps require aligned tags and a common-prefix disagreement between every
pair of mappings, so address lookup is unique without an unconstrained
callback.

The abstraction implements effective checks for:

- present and reserved state;
- user versus supervisor access;
- read-only pages and CR0.WP;
- NX and EFER.NXE;
- SMEP instruction fetches;
- SMAP data accesses, implicit supervisor accesses, and RFLAGS.AC;
- PKRU access-disable and write-disable behavior for user pages;
- ordinary versus shadow-stack page and access combinations.

It produces the common page-fault error facts: P, W/R, U/S, RSVD, I/D, PK,
and SS. The record also states whether I/D and SS are architecturally defined:
I/D requires EFER.NXE and CR4.PAE, while SS requires CR4.CET. A not-present
fault still records whether the failed access was a user write, and records an
instruction fetch only when I/D is defined. The PK bit is set only when
protection-key state denied that actual access.

The sources are Volume 2 sections 5.1-5.10 on PDF pages 190-233. The current
map is a derived page-walk result. It deliberately leaves these mechanisms
open:

- CR3-rooted legacy, PAE, four-level, and five-level walks;
- combining permissions and reserved-bit legality at every hierarchy level;
- Accessed and Dirty bit updates and their possible faults;
- TLB state, PCID, global pages, and invalidation;
- physical-address-width checks, nested paging, RMP, PKRS, and the complete
  extended page-fault error code.

Those omissions are recorded as coverage obligations. They prevent this
foundation from closing full paging or protection coverage.

## Memory values, observations, and ordering

The byte store is a finite projection used to state architectural read and
write values. Byte sequences are little endian: the first byte corresponds to
the lowest physical address and least-significant value byte.

A finite dump is not total architectural memory. `MemoryState` therefore has
an explicit captured domain, and reads return either `available(value)` or
`unavailable`. An absent cell never becomes zero, #PF, or an impossible
execution. A later Ariadne bridge must emit a missing-data obligation rather
than prune an outcome when a required byte is unavailable.

The byte store also is not an AMD memory-ordering model. `MemoryEvent` retains
the access kind, address, size, value, and effective memory type so D1 can add
processor and device ordering. Volume 1 sections 3.8-3.9, PDF pages 133-140,
and Volume 2 chapter 7, PDF pages 248-305, require separate treatment of:

- single-processor reordering and fences;
- multiprocessor coherence and atomicity;
- cacheable locks and bus locks;
- MTRR/PAT memory types and memory-mapped I/O;
- write combining, non-temporal operations, direct stores, and prefetches.

No result from this component claims sequential consistency or full atomic
instruction execution.

## I/O permissions

Port I/O uses a separate 16-bit address space. The basic predicate allows a
port when CPL is no less privileged than RFLAGS.IOPL or the current TSS bitmap
allows that port. Denied access yields #GP(0). Multi-byte IN, OUT, INS, and OUTS
must validate every addressed port and retain strongly ordered I/O events.

The source overview is Volume 1 sections 3.8.1-3.8.3 on PDF pages 134-136.
TSS limit reads, complete virtual-8086/VME behavior, device responses, and SMM
I/O restart remain form/system dependencies.

## Exceptions, commits, and restart

Volume 2 sections 8.1.1-8.1.3, PDF pages 306-307, distinguish three important
instruction-boundary outcomes:

| Outcome | Saved instruction pointer | Instruction effects |
| --- | --- | --- |
| Fault | Faulting instruction | Normally rolled back |
| Trap | Following instruction | Fully committed |
| Abort | Not reliably restartable | Instruction-specific or undefined |

`Outcome` records the resulting state, effects in commit order, the committed
prefix length, the exception detail, and any in-progress restart point. The
three commit policies are `rollback`, `committedPrefix`, and
`afterInstruction`. An ordinary fault uses a zero-length committed prefix and
saves the faulting RIP. A trap commits all effects and saves the next RIP.
Repeated string operations and other explicitly restartable forms can expose a
committed prefix with completed and remaining iteration counts. They must opt
into that policy in their own instruction rule.

The common memory fault pipeline has these ordered stages:

1. Segment, span, and canonical-address faults: #SS or #GP.
2. Translation and page-protection faults: #PF, with CR2 equal to the failed
   linear address.
3. Ordinary alignment checking: #AC when CR0.AM, RFLAGS.AC, and CPL=3 enable
   it.

This is not a universal priority table. Volume 2 section 8.5, PDF pages
328-331, defines priority groups for simultaneous interrupts and leaves order
within a group implementation-dependent. Its instruction-fetch note also
allows model-dependent #UD versus boundary-fetch faults. Volume 3 instruction
descriptions can impose mandatory-alignment #GP, suppress a memory access, or
specify a different order. Each form rule must attach those cases explicitly.

Exception delivery is outside the current transition. IDT lookup, gate
validation, stack/IST switching, pushed frames, shadow-stack changes, nested
exceptions, #DF escalation, and IRET are required control-transfer work. The
foundation carries enough vector, class, error-code, CR2, saved-IP, and restart
information for those rules without pretending delivery has occurred.

The exception-code representation distinguishes no pushed error code from an
architecturally pushed zero. Volume 2 section 8.2.17 states that #AC returns
zero, so a common alignment fault maps to vector #AC with a pushed-zero error
code. #GP(0) and #SS(0) retain selector-error-code zero. Ordinary traps commit
all listed effects but carry zero completed iterations; effect count and
restartable-string iteration count are independent quantities.

## Correspondence and validation boundary

Lean's `Source` namespaces are reviewed transcriptions of selected TLA+
operators. They prove address representation round trips, effective-offset
correspondence, rollback correspondence, full-width carry behavior, view/base
properties, and commit/restart laws. They are not a verified TLA+ parser.

The executable fixture
[AMD64MemoryExceptionsChecks.tla](../Specs/AMD64MemoryExceptionsChecks.tla)
covers positive and negative cases for:

- legal and illegal submode/address-size pairs;
- canonical and non-canonical addresses;
- full-width addition certificates;
- DS suppression and FS base use in the 64-bit submode;
- page translation, user/supervisor, R/W, NX, SMEP, and SMAP behavior;
- not-present page-fault access bits;
- segment-limit, #GP, #SS, #PF, and #AC selection;
- byte read/write and unavailable captured memory;
- rollback and committed-prefix outcomes.

Passing this fixture closes only the named foundation operators. Complete form
coverage, hardware page walks, exception delivery, concurrency, string
restart, and native AMD differential execution remain open. The current host
is Intel under Hyper-V, so it cannot provide AMD-specific native conformance
evidence.
