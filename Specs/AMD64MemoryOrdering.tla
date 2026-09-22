-------------------- MODULE AMD64MemoryOrdering --------------------
EXTENDS Integers, FiniteSets

\* Bounded, relational AMD64 memory-ordering contract for the reviewed WB/WC
\* subset. It deliberately does not execute a sequential byte store. Events
\* retain program order while `order` records only visibility/completion edges
\* that the architecture requires.
\*
\* Authority:
\* - AMD APM Volume 1 revision 3.25 section 4.12.4, PDF pages 269-271.
\* - AMD APM Volume 2 revision 3.45 sections 7.1-7.5, especially Table 7-4
\*   and its rules a-m on PDF pages 252-267.

EventKinds == {"load", "store", "streamLoad", "streamStore",
               "mfence", "lfence", "sfence", "lockedRMW"}
MemoryTypes == {"WB", "WC", "unknown"}
FenceKinds == {"mfence", "lfence", "sfence"}

\* @typeAlias: amd64OrderingEvent = {id: Int, processor: Int, po: Int,
\*   kind: Str, memoryType: Str, address: Int, readValue: Int,
\*   writeValue: Int, sideEffectfulDevice: Bool, cacheableAligned: Bool};
\* @typeAlias: amd64OrderEdge = {left: Int, right: Int};

\* @type: $amd64OrderingEvent => Bool;
IsLoad(event) == event.kind \in {"load", "streamLoad", "lockedRMW"}

\* @type: $amd64OrderingEvent => Bool;
IsStore(event) == event.kind \in {"store", "streamStore", "lockedRMW"}

\* @type: $amd64OrderingEvent => Bool;
IsAccess(event) == IsLoad(event) \/ IsStore(event)

\* @type: ($amd64OrderingEvent, $amd64OrderingEvent) => Bool;
ProgramBefore(left, right) ==
  left.processor = right.processor /\ left.po < right.po

\* This component has reviewed ordering rules only for WB/WC processor memory.
\* Unknown type/device classification is an unavailable contract, not WB.
\* Streaming loads from destructive or side-effectful I/O are rejected because
\* Volume 1 identifies MOVNTDQA as speculative.
\* @type: $amd64OrderingEvent => Bool;
SupportedEvent(event) ==
  /\ event.kind \in EventKinds
  /\ event.memoryType \in MemoryTypes
  /\ IF event.kind \in FenceKinds
     THEN event.memoryType = "unknown"
     ELSE event.memoryType \in {"WB", "WC"}
  /\ ~event.sideEffectfulDevice
  /\ (event.kind = "streamLoad" => event.memoryType = "WC")
  /\ (event.kind = "streamStore" => event.memoryType = "WC")

\* The alignment boundary that selects a bus lock is implementation-dependent.
\* `cacheableAligned` is explicit profile evidence, not inferred here.
\* @type: $amd64OrderingEvent => Str;
LockTransport(event) ==
  IF event.kind /= "lockedRMW" THEN "not-locked"
  ELSE IF event.memoryType = "WB" /\ event.cacheableAligned
       THEN "cacheable-lock" ELSE "bus-lock"

\* @type: Set($amd64OrderingEvent) => Bool;
OrderingApplicable(events) ==
  /\ \A event \in events : SupportedEvent(event)
  /\ \A left, right \in events : left.id = right.id => left = right
  /\ \A left, right \in events :
       left.processor = right.processor /\ left.po = right.po => left = right

\* @type: ($amd64OrderingEvent, $amd64OrderingEvent) => Bool;
Conflicts(left, right) ==
  left.address = right.address /\ (IsStore(left) \/ IsStore(right))

\* Table 7-4 base edges for the WB/WC subset. Absence of an edge means the
\* pair may be reordered; it does not require reordering.
\* @type: ($amd64OrderingEvent, $amd64OrderingEvent) => Bool;
BaseRequired(left, right) ==
  /\ ProgramBefore(left, right)
  /\ IsAccess(left) /\ IsAccess(right)
  /\ \/ (IsLoad(left) /\ IsStore(right))                         \* rule c
     \/ (IsLoad(left) /\ right.kind = "load" /\
           right.memoryType = "WB")                              \* rule a
     \/ (left.kind = "store" /\ left.memoryType = "WB" /\
           right.kind = "store" /\ right.memoryType = "WB")    \* rule g
     \/ Conflicts(left, right)                                   \* e/h conflict

\* @type: (Set($amd64OrderingEvent), Str, $amd64OrderingEvent,
\*   $amd64OrderingEvent) => Bool;
FenceBetween(events, fenceKind, left, right) ==
  \E fence \in events :
    fence.kind = fenceKind /\ ProgramBefore(left, fence) /\
    ProgramBefore(fence, right)

\* LFENCE orders loads only; this model does not claim that it blocks all
\* speculative execution. SFENCE orders stores. MFENCE orders both directions.
\* @type: (Set($amd64OrderingEvent), $amd64OrderingEvent,
\*   $amd64OrderingEvent) => Bool;
FenceRequired(events, left, right) ==
  /\ ProgramBefore(left, right)
  /\ IsAccess(left) /\ IsAccess(right)
  /\ \/ FenceBetween(events, "mfence", left, right)
     \/ (IsLoad(left) /\ IsLoad(right) /\
           FenceBetween(events, "lfence", left, right))
     \/ (IsStore(left) /\ IsStore(right) /\
           FenceBetween(events, "sfence", left, right))

\* Table 7-4 rules d/k: a locked operation completes after earlier loads and
\* stores and before younger loads and stores. XCHG reaches this event kind via
\* implicit locking; other instruction families require validated LOCK.
\* @type: ($amd64OrderingEvent, $amd64OrderingEvent) => Bool;
LockedRequired(left, right) ==
  /\ ProgramBefore(left, right)
  /\ \/ (IsAccess(left) /\ right.kind = "lockedRMW")
     \/ (left.kind = "lockedRMW" /\ IsAccess(right))

\* @type: (Set($amd64OrderingEvent), $amd64OrderingEvent,
\*   $amd64OrderingEvent) => Bool;
RuleRequires(events, left, right) ==
  BaseRequired(left, right) \/ FenceRequired(events, left, right) \/
  LockedRequired(left, right)

\* @type: Set($amd64OrderingEvent) => Set($amd64OrderEdge);
RequiredEdges(events) ==
  UNION {
    {[left |-> left.id, right |-> right.id] :
      right \in {candidate \in events : RuleRequires(events, left, candidate)}} :
    left \in events}

\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge)) => Bool;
StrictPartialOrder(events, order) ==
  LET ids == {event.id : event \in events}
  IN /\ \A edge \in order : edge.left \in ids /\ edge.right \in ids
     /\ \A id \in ids : [left |-> id, right |-> id] \notin order
     /\ \A first, second \in order : first.right = second.left =>
          [left |-> first.left, right |-> second.right] \in order

\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge)) => Bool;
AdmissibleOrder(events, order) ==
  OrderingApplicable(events) /\ StrictPartialOrder(events, order) /\
  RequiredEdges(events) \subseteq order

\* @type: (Set($amd64OrderEdge), $amd64OrderingEvent,
\*   $amd64OrderingEvent) => Bool;
Ordered(order, left, right) == [left |-> left.id, right |-> right.id] \in order

\* Read-from is explicit evidence. Edge.left=0 denotes the initial zero source;
\* event identifiers are therefore required to be nonzero.
\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge),
\*   $amd64OrderEdge) => Bool;
ValidRFEdge(events, order, edge) ==
  IF edge.left = 0
  THEN \E reader \in events :
         reader.id = edge.right /\ IsLoad(reader) /\ reader.readValue = 0
  ELSE \E writer, reader \in events :
         /\ writer.id = edge.left /\ reader.id = edge.right
         /\ writer /= reader
         /\ IsStore(writer) /\ IsLoad(reader)
         /\ writer.address = reader.address
         /\ writer.writeValue = reader.readValue
         /\ ~ProgramBefore(reader, writer)
         /\ ~Ordered(order, reader, writer)

\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge),
\*   Set($amd64OrderEdge)) => Bool;
ReadFromWellFormed(events, order, rf) ==
  /\ \A event \in events : event.id /= 0
  /\ \A edge \in rf : ValidRFEdge(events, order, edge)
  /\ \A reader \in events : IsLoad(reader) =>
       Cardinality({edge \in rf : edge.right = reader.id}) = 1

\* @type: (Set($amd64OrderEdge), $amd64OrderingEvent,
\*   $amd64OrderingEvent) => Bool;
ReadsFrom(rf, writer, reader) ==
  [left |-> writer.id, right |-> reader.id] \in rf

\* A producer/consumer publication path is derived entirely from event kinds,
\* values, addresses, and order: prior data -> locked release, a same-address
\* locked acquire that reads from it, then acquire -> younger data load.
\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge), Set($amd64OrderEdge),
\*   $amd64OrderingEvent, $amd64OrderingEvent) => Bool;
PublishedBefore(events, order, rf, writer, reader) ==
  \E release, acquire \in events :
    /\ release.kind = "lockedRMW" /\ acquire.kind = "lockedRMW"
    /\ release.processor /= acquire.processor
    /\ Ordered(order, writer, release)
    /\ ReadsFrom(rf, release, acquire)
    /\ Ordered(order, acquire, reader)

\* The strong published-value rule is used only for an address with one
\* non-initial writer. Racing writers require a future coherence order.
\* @type: (Set($amd64OrderingEvent), $amd64OrderingEvent) => Bool;
SingleWriterAddress(events, writer) ==
  \A other \in events :
    IsStore(other) /\ other.address = writer.address => other = writer

\* @type: (Set($amd64OrderingEvent), Set($amd64OrderEdge),
\*   Set($amd64OrderEdge)) => Bool;
PublicationConsistent(events, order, rf) ==
  /\ ReadFromWellFormed(events, order, rf)
  /\ \A writer, reader \in events :
    PublishedBefore(events, order, rf, writer, reader) /\
      writer.address = reader.address /\
      SingleWriterAddress(events, writer) => ReadsFrom(rf, writer, reader)

====================================================================
