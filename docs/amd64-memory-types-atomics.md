# AMD64 memory types and atomic RMW foundation

`AMD64MemoryTypes` resolves explicit PAT index bits and MTRR range facts into a
memory type. UC/CD/WC/WP/WT/WB combinations supported by the reviewed Volume 2
table are resolved; unimplemented, overlapping, unsupported, and unknown cases stay
explicit. No path defaults to WB. PWT/PCD/PAT select one of eight PAT fields;
MTRR-disabled configurations resolve to UC. Full fixed-range, extended IORR,
SME, and overlapping-MTRR precedence remain open.

`AMD64Atomic` models XCHG, XADD, CMPXCHG, and block CMPXCHG as memory RMW
events over `ConcreteMemory`. An RMW event is not automatically atomic. XCHG
with a memory operand is implicitly locked whether or not LOCK is encoded;
XADD, CMPXCHG, CMPXCHG8B, and CMPXCHG16B are marked atomic only when their
validated form selected LOCK. An unlocked event remains an RMW operation but
cannot be placed in the bounded locked-RMW order.

The Lean instruction adapter takes a `MemoryModel.AddressRequest`, requires a
read/write intent and exact operand byte count, and runs `resolveAccess` before
reading or changing CPU or concrete memory. The resulting physical-byte list
is used directly, so an access crossing a page boundary is not assumed to be
physically contiguous. Arithmetic values and flags use the shared ADD/SUB
kernels. CMPXCHG failure loads the observed destination into the selected
accumulator and still records the architecturally required write-back of the
same memory value. XADD returns the old destination in its source register.

CMPXCHG8B uses EDX:EAX as expected data and ECX:EBX as replacement data;
CMPXCHG16B uses RDX:RAX and RCX:RBX. Failure writes the observed block into the
expected pair, success writes the replacement, and only ZF changes. The typed
adapter requires the corresponding explicit CPUID capability and long64 mode
for CMPXCHG16B. Its 16-byte linear-address misalignment result is #GP(0).
Feature and mode checks run before memory translation: Volume 2 Table 8-9
places #UD above a data-access #PF. Mandatory-alignment #GP and data-access #PF
are both in priority group 7, where Volume 2 says within-group priority is
implementation dependent. The Volume 3 entry states both causes without
ordering them. That pair therefore remains explicitly unresolved; the current
adapter learns the linear address from successful `resolveAccess` before
applying the #GP check and must not be cited as a general priority rule.

Atomicity does not imply a globally sequential byte store. The bounded
`AMD64AtomicOrdering` fixture declares one coherent-WB profile and checks that
two atomic increments occupy distinct positions in its RMW order. It makes no
claim about surrounding ordinary accesses, UC/WC/MMIO, fences, cache
coherency, or general AMD ordering. Those relations remain D1 follow-up work.

Authority: AMD Volume 2 revision 3.45 sections 7.3-7.8 and the pinned Volume 3
XCHG/XADD/CMPXCHG entries. The source-reviewed facts and stable form IDs are
recorded in [atomic-form-supplement.json](../Specs/AMD64/atomic-form-supplement.json).
The shared form inventory still marks these entries pending; the supplement
does not by itself make an unvalidated decoded instruction executable.
