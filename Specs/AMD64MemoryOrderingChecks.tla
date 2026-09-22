---------------- MODULE AMD64MemoryOrderingChecks ----------------
EXTENDS AMD64MemoryOrdering

Event(id, processor, po, kind, memoryType, address, readValue, writeValue) ==
  [id |-> id, processor |-> processor, po |-> po, kind |-> kind,
   memoryType |-> memoryType, address |-> address,
   readValue |-> readValue, writeValue |-> writeValue,
   sideEffectfulDevice |-> FALSE, cacheableAligned |-> TRUE]

PData == Event(1, 0, 0, "streamStore", "WC", 100, -1, 42)
Release == Event(2, 0, 1, "lockedRMW", "WB", 200, 0, 1)
Acquire == Event(3, 1, 0, "lockedRMW", "WB", 200, 1, 1)
CData == Event(4, 1, 1, "streamLoad", "WC", 100, 42, -1)
PositiveEvents == {PData, Release, Acquire, CData}
PositiveOrder == {
  [left |-> 1, right |-> 2],
  [left |-> 3, right |-> 4]}
PositiveRF == {
  [left |-> 0, right |-> 2],
  [left |-> 2, right |-> 3],
  [left |-> 1, right |-> 4]}

NData == Event(11, 0, 0, "streamStore", "WC", 100, -1, 42)
NSignal == Event(12, 0, 1, "store", "WB", 200, -1, 1)
NSeen == Event(13, 1, 0, "load", "WB", 200, 1, -1)
NStale == Event(14, 1, 1, "streamLoad", "WC", 100, 0, -1)
NegativeEvents == {NData, NSignal, NSeen, NStale}
NegativeOrder == {}
NegativeRF == {
  [left |-> 12, right |-> 13],
  [left |-> 0, right |-> 14]}

FLoad0 == Event(21, 0, 0, "streamLoad", "WC", 300, 0, -1)
LF == Event(22, 0, 1, "lfence", "unknown", -1, -1, -1)
FLoad1 == Event(23, 0, 2, "streamLoad", "WC", 304, 0, -1)
FStore0 == Event(24, 1, 0, "streamStore", "WC", 400, -1, 1)
SF == Event(25, 1, 1, "sfence", "unknown", -1, -1, -1)
FStore1 == Event(26, 1, 2, "store", "WB", 500, -1, 1)
MStore == Event(27, 2, 0, "streamStore", "WC", 600, -1, 1)
MF == Event(28, 2, 1, "mfence", "unknown", -1, -1, -1)
MLoad == Event(29, 2, 2, "streamLoad", "WC", 700, 0, -1)
FenceEvents == {FLoad0, LF, FLoad1, FStore0, SF, FStore1,
                MStore, MF, MLoad}
LFStore == Event(33, 3, 0, "store", "WB", 900, -1, 1)
LFOnly == Event(34, 3, 1, "lfence", "unknown", -1, -1, -1)
LFLoad == Event(35, 3, 2, "streamLoad", "WC", 904, 0, -1)
LFStoreLoadEvents == {LFStore, LFOnly, LFLoad}

UnknownLoad == Event(31, 0, 0, "load", "unknown", 0, 0, -1)
DestructiveStream == [Event(32, 0, 0, "streamLoad", "WC", 0, 0, -1)
  EXCEPT !.sideEffectfulDevice = TRUE]
BusLockedWC == [Event(36, 0, 0, "lockedRMW", "WC", 0, 0, 1)
  EXCEPT !.cacheableAligned = TRUE]
BusLockedMisalignedWB == [Event(37, 0, 0, "lockedRMW", "WB", 0, 0, 1)
  EXCEPT !.cacheableAligned = FALSE]

\* WB store-buffering witness: both non-conflicting loads may pass the local
\* stores, so an empty required order remains admissible. This prevents the
\* bounded model from silently claiming global sequential consistency.
SBStore0 == Event(41, 0, 0, "store", "WB", 800, -1, 1)
SBLoad0 == Event(42, 0, 1, "load", "WB", 804, 0, -1)
SBStore1 == Event(43, 1, 0, "store", "WB", 804, -1, 1)
SBLoad1 == Event(44, 1, 1, "load", "WB", 800, 0, -1)
StoreBufferEvents == {SBStore0, SBLoad0, SBStore1, SBLoad1}
StoreBufferRF == {
  [left |-> 0, right |-> 42],
  [left |-> 0, right |-> 44]}

\* Equal values do not identify a read-from source. The acquire selects the
\* second release, so data ordered before the first release is not published.
DData == Event(51, 0, 0, "streamStore", "WC", 1000, -1, 7)
DRelease1 == Event(52, 0, 1, "lockedRMW", "WB", 1100, 0, 1)
DRelease2 == Event(53, 2, 0, "lockedRMW", "WB", 1100, 0, 1)
DAcquire == Event(54, 1, 0, "lockedRMW", "WB", 1100, 1, 1)
DRead == Event(55, 1, 1, "streamLoad", "WC", 1000, 0, -1)
DuplicateEvents == {DData, DRelease1, DRelease2, DAcquire, DRead}
DuplicateOrder == {
  [left |-> 51, right |-> 52],
  [left |-> 54, right |-> 55]}
DuplicateRF == {
  [left |-> 0, right |-> 52],
  [left |-> 0, right |-> 53],
  [left |-> 53, right |-> 54],
  [left |-> 0, right |-> 55]}

\* A racing writer disables the single-writer publication-value rule. Its RF
\* choice remains explicit rather than being silently forbidden.
Racing == Event(61, 2, 0, "streamStore", "WC", 100, -1, 99)
RacingRead == Event(62, 1, 1, "streamLoad", "WC", 100, 99, -1)
RacingEvents == {PData, Release, Acquire, Racing, RacingRead}
RacingOrder == {
  [left |-> 1, right |-> 2],
  [left |-> 3, right |-> 62]}
RacingRF == {
  [left |-> 0, right |-> 2],
  [left |-> 2, right |-> 3],
  [left |-> 61, right |-> 62]}
FutureReader == Event(71, 4, 0, "load", "WB", 1200, 5, -1)
FutureWriter == Event(72, 4, 1, "store", "WB", 1200, -1, 5)
FutureEvents == {FutureReader, FutureWriter}
FutureRF == {[left |-> 72, right |-> 71]}
SelfRF == {[left |-> 2, right |-> 2]}

Contracts ==
  /\ AdmissibleOrder(PositiveEvents, PositiveOrder)
  /\ PublishedBefore(PositiveEvents, PositiveOrder, PositiveRF, PData, CData)
  /\ PublicationConsistent(PositiveEvents, PositiveOrder, PositiveRF)
  /\ ReadsFrom(PositiveRF, Release, Acquire)
  /\ AdmissibleOrder(NegativeEvents, NegativeOrder)
  /\ ReadFromWellFormed(NegativeEvents, NegativeOrder, NegativeRF)
  /\ ~PublishedBefore(NegativeEvents, NegativeOrder, NegativeRF, NData, NStale)
  /\ NStale.readValue /= NData.writeValue
  /\ ~RuleRequires(NegativeEvents, NData, NSignal)
  /\ ~RuleRequires(NegativeEvents, NSeen, NStale)
  /\ FenceRequired(FenceEvents, FLoad0, FLoad1)
  /\ FenceRequired(FenceEvents, FStore0, FStore1)
  /\ FenceRequired(FenceEvents, MStore, MLoad)
  /\ ~FenceRequired(LFStoreLoadEvents, LFStore, LFLoad)
  /\ LockTransport(Release) = "cacheable-lock"
  /\ LockTransport(BusLockedWC) = "bus-lock"
  /\ LockTransport(BusLockedMisalignedWB) = "bus-lock"
  /\ ~SupportedEvent(UnknownLoad)
  /\ ~SupportedEvent(DestructiveStream)
  /\ AdmissibleOrder(StoreBufferEvents, {})
  /\ ReadFromWellFormed(StoreBufferEvents, {}, StoreBufferRF)
  /\ SBLoad0.readValue = 0 /\ SBLoad1.readValue = 0
  /\ ReadFromWellFormed(DuplicateEvents, DuplicateOrder, DuplicateRF)
  /\ ~PublishedBefore(DuplicateEvents, DuplicateOrder, DuplicateRF,
                       DData, DRead)
  /\ ReadsFrom(DuplicateRF, DRelease2, DAcquire)
  /\ ReadFromWellFormed(RacingEvents, RacingOrder, RacingRF)
  /\ PublishedBefore(RacingEvents, RacingOrder, RacingRF, PData, RacingRead)
  /\ ~SingleWriterAddress(RacingEvents, PData)
  /\ ReadsFrom(RacingRF, Racing, RacingRead)
  /\ ~ValidRFEdge(FutureEvents, {}, [left |-> 72, right |-> 71])
  /\ ~ValidRFEdge(PositiveEvents, PositiveOrder,
                   [left |-> 2, right |-> 2])

VARIABLE
  \* @type: Bool;
  checked

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ Contracts

==================================================================
