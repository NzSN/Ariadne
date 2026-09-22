# AMD64 concrete memory and captured knowledge

The architectural memory layer is defined in
[AMD64ConcreteMemory.tla](../Specs/AMD64ConcreteMemory.tla) and
[ConcreteMemory.lean](../lean/AMD64/ConcreteMemory.lean). It separates a total
architectural byte store from the finite bytes known to an analyzer.

## Two different objects

`ConcreteMemory` denotes one byte at every address in the modeled physical
domain. TLA+ represents it as a concrete default byte plus finite overrides;
Lean represents the same semantic object directly as a total address-to-byte
function inside `Store`. The default byte is chosen architectural state. It is
not inferred from a missing dump byte.

`MemoryState` remains captured knowledge. It has a finite captured domain and
returns `available(byte)` or `unavailable`. An address outside that domain
places no constraint on a concrete store and never becomes zero, #PF, or an
impossible execution.

The TLA+ finite-default representation and Lean total-function representation
are reviewed counterparts, not a mechanically proved representation
isomorphism. TLA+ requires unique non-default overrides; Lean quantifies over
arbitrary total stores.

## Contracts

Concrete read and write provide the usual laws for arbitrary addresses and
bytes:

- reading a just-written address returns the written byte;
- writing one address preserves every different address;
- a concrete write preserves the store's modeled physical width when its
  address satisfies that width;
- concrete refinement requires every captured address to be within the
  concrete physical domain and to have the same byte;
- writing any valid uncaptured address preserves refinement of an unchanged
  snapshot;
- writing the same valid address and byte to concrete memory and captured
  knowledge preserves refinement, assuming the list-backed snapshot remains
  well formed.

`ConcreteMachineState` is the composition boundary for CPU plus concrete
memory. Its validity combines `ValidCPUState`, memory-width validity, and
equality between the memory and architecture-profile physical widths. It does
not include devices, MMIO, bus failures, caches, or concurrency.

## Page-table evidence

Page-walk entries are no longer accepted as free raw certificate words.
`ConcreteBytesAt` validates each four- or eight-byte little-endian entry against
actual concrete reads at explicitly carry-checked consecutive physical
addresses. Lean's executable page walker likewise receives a concrete `Store`
and compares every evidence byte with the store.

Captured availability remains separate. If a required page-table word is not
captured, the certificate is incomplete even when a compatible concrete state
exists. This is analysis incompleteness, not a not-present page and not #PF. A
not-present fault requires available, concrete-backed bytes whose raw P bit is
clear.

## Boundary before D1

Concrete bytes describe ordinary architectural storage values. The following
remain separate contracts:

- MMIO and device responses;
- physical layout and holes;
- memory types and cacheability;
- bus errors and machine checks;
- atomicity, visibility, ordering, coherency, and multiprocessor execution;
- TLB state and speculative paging-structure effects.

No result in this component turns the total byte function into sequentially
consistent RAM or claims that every physical address is backed by DRAM.

The executable fixtures check default and override reads, same-address writes,
frame behavior, captured refinement, snapshot promotion, unavailable reads,
and concrete-backed page-table evidence without enumerating the 64-bit address
space. Lean proofs are admitted-free and quantify over arbitrary stores.
