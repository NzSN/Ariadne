# AMD64 atomic CPU and memory execution

[AMD64AtomicExecution.tla](../Specs/AMD64AtomicExecution.tla) is the
authoritative instruction-body relation for memory XCHG, XADD, CMPXCHG,
CMPXCHG8B, and CMPXCHG16B. [AtomicExecution.lean](../lean/AMD64/AtomicExecution.lean)
exposes the existing permission-checked Lean `Atomic.executeMemory` under the
same boundary and projects successful results into `MachineAccess` effects.

## Execution boundary

The relation accepts only a `ResolvedSpan` produced by MachineAccess. It reads
the exact physical byte sequence from total concrete memory, reads every CPU
source from the before state, computes values and flags, creates tentative byte
effects, applies the body-selected full effect plan, and returns
`bodyApplied`. It does not advance RIP, perform the next fetch, select external
events, deliver an exception, or retire the instruction.

The immediate verified profile is long64/CPL3, ordinary RAM, complete mapping
evidence, and a resolved memory type. TLA+ `AtomicRequestCompatible` and the
public Lean `AtomicExecution.execute` reject unresolved memory types. MMIO,
missing page-map evidence, and unresolved ordering/type behavior are explicit
unavailable cases rather than silently inheriting RAM or WB semantics.

Feature and mode preflight precedes translation. Unsupported CMPXCHG8B/16B
and non-long64 CMPXCHG16B therefore do not become page faults. Scalar source
views include the legacy high-byte registers. Long64 low32 writes zero-extend;
legacy upper dword behavior remains relational in TLA+.

## Bodies

- Memory XCHG is implicitly locked and preserves rFLAGS. Memory receives the
  source register and the source register receives the observed destination.
- XADD uses the shared ADD kernel. Memory receives the sum, the source register
  receives the old destination, and the six arithmetic status flags are
  updated. Without LOCK its RMW event remains non-atomic.
- CMPXCHG uses the shared SUB/compare kernel. Success writes the source to
  memory. Failure loads the observed destination into the selected accumulator
  and still plans the architecturally required same-value memory write.
- CMPXCHG8B uses EDX:EAX and ECX:EBX. CMPXCHG16B uses RDX:RAX and RCX:RBX.
  Success writes the replacement pair; failure updates the expected pair.
  Only ZF changes.

Every event carries the exact physical byte sequence and explicit memory-type
resolution. No translation path invents WB.

## Group-7 exception alternatives

CMPXCHG16B mandatory-alignment #GP is added to the common address/page/#AC
candidate set before selection. Volume 2 places #GP, data #PF, and #AC in the
same priority group and defines within-group ordering as implementation
dependent.

`AtomicFaultSelected` and Lean `FaultSelected` therefore accept either:

- an unknown implementation profile, which preserves every candidate; or
- a concrete profile with stable distinct GP/PF/AC ranks.

The ranks describe one implementation and are never promoted to a universal
AMD rule. Preflight #UD remains in the higher architectural priority group.

## TLA+ and Lean pairing

| Contract | TLA+ | Lean implementation/helper |
| --- | --- | --- |
| entry point | `AtomicBody` after `ResolveSpan` | resolved-type `AtomicExecution.execute` delegates to `Atomic.executeMemory` |
| preflight | `AtomicPreflight` | `Atomic.preAccessLegality` inside `executeMemory` |
| access shape | `AtomicRequestCompatible` | `Atomic.requestCompatible` |
| exact read order | `ReadSpanBytes` | `Atomic.readResolved` |
| GPR views/writes | `ReadGPR`, `WriteGPRAllowed` | `IntegerExecution.readGPR`, `writeGPR` |
| flags | `ApplyStatus`, shared integer kernels | `applyStatusFlags`, shared integer kernels |
| tentative/full body effects | `FinishAtomicBody`, `PlanWrites`, `BodyApplied` | `effectPlan`, `projectBody`, `MachineAccess.BodyApplied` |
| scalar bodies | `ScalarAtomicBody` | `Atomic.executeScalar` through public `executeMemory` |
| block bodies | `BlockAtomicBody` | `Atomic.executeBlock` through public `executeMemory` |
| event atomicity | `ExecutionEvent`, `AtomicityFor` | `Atomic.eventForResolved`, `Operation.locked` |
| same-group selection | `AtomicFaultSelected` | `FaultSelected` |

Private Lean helper names in the table identify the reviewed implementation
decomposition; external consumers use only `execute`. TLA+ and Lean do not
parse each other. The correspondence is an operator review plus mirrored
fixtures, not a general mechanized translation theorem.

The TLA+ fixture covers a high8 XCHG, a non-LOCK 16-bit XADD across two
virtually adjacent but physically noncontiguous bytes, CMPXCHG8B success and
failure, ZF and low32 zero-extension, same-value failure writeback, feature
preflight, combined alignment/page candidates, and unknown versus concrete
group-7 policies. Lean checks the public delegation, register-view laws,
block-pair framing, unlocked CMPXCHG atomicity, and group-7 policy behavior.

## Remaining obligations

The current TLA+ body is authoritative for these reviewed operations and
widths. A general proof that Lean total-function stores refine every TLA+
default-plus-overrides transition remains a trusted representation boundary.
Global locked-RMW coherence and serialization still require composition with
the ordering/coherence work; a single body result alone is not a
multiprocessor atomicity proof. Instruction retirement and profile-specific
group-7 choice remain higher-level composition steps.
