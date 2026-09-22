# AMD64 WB/WC memory ordering

The authoritative bounded relation is
[AMD64MemoryOrdering.tla](../Specs/AMD64MemoryOrdering.tla). Its typed Lean
counterpart is [MemoryOrdering.lean](../lean/AMD64/MemoryOrdering.lean).
This component models required ordering and publication edges between events;
it does not turn concrete bytes into a globally sequential store.

## Source boundary

The reviewed sources are:

| Source | Pages | Contract used here |
| --- | ---: | --- |
| AMD Volume 1 revision 3.25, section 4.12.4 | PDF 269-271 | WC streaming loads can be weakly ordered; streaming buffers need not be snooped; fences are required for ordering; locked release/acquire examples order WC producer/consumer traffic; speculative streaming loads cannot target destructive or side-effectful I/O |
| AMD Volume 2 revision 3.45, sections 7.1-7.2 | PDF 252-256 | WB ordering, store buffering, non-conflicting load/store relaxation, and MFENCE/locked synchronization examples |
| AMD Volume 2 revision 3.45, sections 7.3.2-7.3.3 | PDF 258-260 | naturally aligned access atomicity and cacheable-lock versus bus-lock classification |
| AMD Volume 2 revision 3.45, sections 7.4-7.5 | PDF 260-267 | WB/WC behavior, Table 7-4 rules a-m, and buffer-drain effects of fences and locked instructions |

The small number of streaming buffers, re-fetch behavior, latency, and cache
implementation are performance facts erased by this relation. SIMD execution
is outside the Volume 3 general-purpose instruction target, but its documented
WB/WC ordering requirements constrain the shared memory-system model.

## Event and order model

Each event retains processor identity, program-order position, access kind,
resolved memory type, address, read/write values, and whether the address maps
to a side-effectful device. The supported subset is processor memory with an
explicit WB or WC type. Unknown memory type returns an unavailable contract;
it never defaults to WB. Every side-effectful device access is unavailable in
this relation because device completion is not modeled; the source gives the
stronger specific prohibition that speculative streaming loads must never
target destructive or side-effectful I/O.

Addresses here identify normalized, disjoint abstract locations (or individual
byte granules). Concrete access widths, overlapping spans, and virtual/physical
aliases must be normalized before this layer; distinct base addresses alone do
not establish that machine accesses are non-conflicting.

`RequiredEdges` derives edges from event facts rather than a synchronization
flag:

- a later store cannot pass a prior load;
- a WB load cannot pass a prior WB/WC load;
- WB stores preserve order with prior WB stores;
- conflicting accesses preserve order;
- LFENCE orders prior and later loads, without claiming that it blocks all
  speculative execution;
- SFENCE orders prior and later stores;
- MFENCE orders prior and later memory accesses;
- a locked RMW completes after prior accesses and before younger accesses.

An admissible execution supplies a strict partial order containing these
required edges. Pairs for which Table 7-4 permits reordering need no edge.
Consequently, the relation does not impose global sequential consistency.

Read-from is an explicit relation between event identities. Matching address
and value only validates a selected edge; it never chooses a source, because
two writes can store the same value. Every read has exactly one selected writer
or the explicit initial-zero source. Self-sourcing and a source ordered or
program-ordered after its reader are rejected. Publication is derived from a
concrete path:

```text
producer data write
  -> locked release on signal
  -> locked acquire that reads the release value
  -> consumer data read
```

The fixture instantiates Volume 1's WC producer/consumer example. The positive
case orders the WC stores before the locked release and the younger streaming
loads after the locked acquire, with explicit RF edges for the signal and data.
The synchronized-value check is restricted to a single-writer address; racing
writers need a future coherence order. Separate counterexamples prove that
duplicate values do not create false synchronization and that a racing writer
can be the selected RF source. The negative case replaces the locked events
with ordinary WB signal accesses; a stale WC read and reordered pairs are then
admissible. A separate WB store-buffering fixture admits both processors
reading zero, which guards against accidental whole-model SC.

## TLA+ and Lean pairing

The correspondence is a reviewed operator-by-operator transcription:

| Semantic rule | TLA+ | Lean |
| --- | --- | --- |
| event classification | `IsLoad`, `IsStore`, `IsAccess`, `SupportedEvent` | `Event.isLoad`, `Event.isStore`, `Event.isAccess`, `supportedEvent` |
| program order and conflicts | `ProgramBefore`, `Conflicts` | `programBefore`, `conflicts` |
| base Table 7-4 edges | `BaseRequired` | `baseRequired` |
| fence edges | `FenceBetween`, `FenceRequired` | `fenceBetween`, `fenceRequired` |
| locked-operation edges | `LockedRequired` | `lockedRequired` |
| required partial order | `RequiredEdges`, `StrictPartialOrder`, `AdmissibleOrder` | `requiredEdges`, `strictPartialOrder`, `admissibleOrder` |
| explicit read-from | `ValidRFEdge`, `ReadFromWellFormed`, `ReadsFrom` | `validRFEdge`, `readFromWellFormed`, `readsFrom` |
| release/acquire publication | `PublishedBefore`, `SingleWriterAddress`, `PublicationConsistent` | `publishedBefore`, `singleWriterAddress`, `publicationConsistent` |
| litmus evidence | `AMD64MemoryOrderingChecks.tla` | `MemoryOrderingChecks.lean` |

Lean uses lists where TLA+ uses finite sets. Event and program-order identity
uniqueness makes duplicate representation irrelevant to the checked fixtures.
Neither language parses the other; the pairing is a trusted transcription
guarded by mirrored definitions and independent fixtures.

The earlier atomic layer has a narrower pairing boundary. TLA+
`AtomicityFor`, `AtomicAccessPermitted`, and `AtomicPreAccessLegality` pair with
Lean operation locking, request validation, and the pre-access checks. Lean
`executeMemory` additionally binds resolved physical bytes and complete CPU
updates. There is no matching authoritative TLA+ CPU-state transition yet, so
that adapter remains a typed implementation contract rather than an accepted
cross-language instruction-body correspondence.

## Remaining boundary

`AdmissibleOrder` means only that the proposed strict partial order contains
the source-backed edges implemented by this bounded tranche. It is a necessary
ordering/publication contract, not a characterization of every allowed AMD
execution. In particular, locked RMWs are not yet placed in a global coherence
or serialization order here; [AMD64AtomicOrdering.tla](../Specs/AMD64AtomicOrdering.tla)
has only a separate two-increment locked-RMW fixture. The two models must be
composed before claiming a complete atomicity or multiprocessor proof.

This tranche does not define UC/CD/WP/WT/WC+, device completion, cache state,
TLB ordering, non-temporal instruction bodies, unlocked-RMW interleavings, or
the complete AMD multiprocessor model. Cacheable versus bus lock is retained as
a source obligation but not simulated: aligned WB locked RMW is a cacheable
lock, while non-WB or implementation-defined misalignment uses a bus lock.
Both are atomic barriers in the current relation. The alignment threshold and
bus-lock reporting mechanisms remain profile/system dependencies.
