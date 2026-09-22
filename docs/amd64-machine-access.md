# AMD64 machine access boundary

[AMD64MachineAccess.tla](../Specs/AMD64MachineAccess.tla) is the authoritative
composition of canonical CPU state and total concrete architectural memory for
one resolved memory span. [MachineAccess.lean](../lean/AMD64/MachineAccess.lean)
provides the typed executable counterpart.

## State and capture boundary

`MachineState` contains CPU state and `ConcreteMemory` only. Concrete memory is
total over the modeled physical domain. Captured `MemoryState` is not part of
architectural execution; absent capture remains unavailable analysis knowledge
and never supplies zero, a translation, or an architectural fault.

A `SpanRequest` retains the raw effective address, address size, segment,
access intent, byte count, ordinary-alignment requirement, and an explicit
memory-type resolution. The memory type may be unresolved. Successful address
translation never defaults it to WB.

The immediate verified profile is long64 at CPL3 over ordinary processor RAM
with a complete explicit architectural page map. MMIO/device completion is
outside this interface. An analysis adapter with missing mapping evidence must
report unavailable instead of passing an incomplete page map as architectural
not-present state. MachineAccess can transport an unresolved memory type for
diagnosis and composition, but instruction executors in the verified milestone
reject it.

## Resolution

TLA+ `ResolveSpan` checks every byte in ascending effective-address order. The
only witness fields are full-width effective and segment-addition results plus
their carry chains; `WordAddWithCarry` and `SegmentLinearWithCarry` verify each
one. Page selection comes from the unique matching member of the explicit
well-formed page map. Physical bytes are derived per byte, so a virtual span
crossing a page boundary need not be physically contiguous.

`SpanFaultCandidates` reports indexed address, page-permission, not-present,
and ordinary-alignment candidates. A fault on the second byte remains distinct
from a first-byte fault. Instruction-specific candidates and implementation-
dependent same-group selection compose above this layer.

Lean `resolveSpan` delegates to the existing executable
`MemoryModel.resolveAccess` and attaches the explicit memory-type resolution.
That executable path returns its selected common fault. The general candidate
set and profile-aware exception selector remain the next composition layer;
the singleton Lean result must not be presented as a universal ordering of
instruction-specific group-7 alternatives.

## Reads, effects, and commit

`MachineRead` reads concrete bytes in exact resolved physical order.
`PlanWrites` creates indexed tentative byte effects containing physical
address, before byte, and proposed after byte. It does not mutate memory or
choose a commit policy.

An `EffectPlan` carries the instruction-selected policy and committed count:

- `rollback` requires zero committed writes;
- `committedPrefix` retains an explicit prefix;
- `bodyAll` applies every planned byte for a successfully applied body;
- `instructionSpecific` leaves the justified count to the instruction rule.

`ApplyCommittedPrefix` applies exactly that prefix. `BodyApplied` composes the
resulting concrete memory with an explicit CPU result. It does not fetch the
next instruction, advance RIP, select asynchronous events, or retire the
instruction.

## TLA+ and Lean pairing

| Contract | TLA+ | Lean |
| --- | --- | --- |
| canonical composition | `machineState`, `MachineStateWellFormed` | `MachineState`, `ConcreteMachineState.Valid` |
| request/result | `machineAccessRequest`, `machineResolvedSpan` | `SpanRequest`, `ResolvedSpan` |
| executable resolution | `ResolveSpan` | `resolveSpan` delegating to `resolveAccess` |
| ordered physical bytes | `resolved.physicalBytes` | `physicalBytes` |
| concrete read | `MachineRead` | `read` |
| tentative effects | `PlanWrites` | `planWrites` |
| commit validity | `EffectPlanWellFormed` | `EffectPlan.Valid` |
| prefix application | `ApplyCommittedPrefix` | `applyCommittedPrefix` |
| body-only result | `BodyApplied` | `BodyApplied` |

TLA+ uses a finite default-plus-overrides store while Lean uses a total
function. Existing concrete-memory refinement laws are the representation
boundary. Neither language parses the other.

The fixtures exercise a CPL3 two-byte access spanning linear `0xFFF` and `0x1000`
whose physical bytes are `0xFFF` and `0x100000`, a protection fault at the
second byte, ordered reads, tentative writes, full-body commit, rollback, and a
single-byte committed prefix.
