import Std

/-!
Typed counterpart of `Specs/AMD64MemoryOrdering.tla` for the reviewed WB/WC
ordering subset. The TLA+ module is authoritative. This file transcribes the
same event predicates, required-edge relation, partial-order validity, and
publication path; it is not a parser or checked translation of TLA+.

Authority: AMD APM Volume 1 revision 3.25 section 4.12.4 and Volume 2
revision 3.45 sections 7.1-7.5, especially Table 7-4 rules a-m.
-/

namespace AMD64.MemoryOrdering

inductive EventKind where
  | load | store | streamLoad | streamStore
  | mfence | lfence | sfence | lockedRMW
  deriving DecidableEq, BEq, Repr

inductive MemoryType where
  | wb | wc | unknown
  deriving DecidableEq, BEq, Repr

structure Event where
  id : Int
  processor : Int
  po : Int
  kind : EventKind
  memoryType : MemoryType
  address : Int
  readValue : Int
  writeValue : Int
  sideEffectfulDevice : Bool
  /-- Explicit profile evidence for the implementation-dependent lock boundary. -/
  cacheableAligned : Bool
  deriving DecidableEq, BEq, Repr

structure Edge where
  left : Int
  right : Int
  deriving DecidableEq, BEq, Repr

def EventKind.isFence : EventKind -> Bool
  | .mfence | .lfence | .sfence => true
  | _ => false

def Event.isLoad (event : Event) : Bool :=
  [.load, .streamLoad, .lockedRMW].contains event.kind

def Event.isStore (event : Event) : Bool :=
  [.store, .streamStore, .lockedRMW].contains event.kind

def Event.isAccess (event : Event) : Bool := event.isLoad || event.isStore

def programBefore (left right : Event) : Bool :=
  left.processor = right.processor && left.po < right.po

/-- Unknown type/device classification is unavailable, never default WB.
Speculative streaming loads cannot target destructive or side-effectful I/O. -/
def supportedEvent (event : Event) : Bool :=
  (if event.kind.isFence then event.memoryType = .unknown
   else event.memoryType = .wb || event.memoryType = .wc) &&
  !event.sideEffectfulDevice &&
  (if event.kind = .streamLoad then
     event.memoryType = .wc else true) &&
  (if event.kind = .streamStore then event.memoryType = .wc else true) &&
  true

inductive LockTransport where
  | notLocked | cacheableLock | busLock
  deriving DecidableEq, BEq, Repr

def lockTransport (event : Event) : LockTransport :=
  if event.kind != .lockedRMW then .notLocked
  else if event.memoryType = .wb && event.cacheableAligned then .cacheableLock
  else .busLock

def orderingApplicable (events : List Event) : Bool :=
  events.all supportedEvent &&
  events.all fun left => events.all fun right =>
    (left.id != right.id || left == right) &&
    (left.processor != right.processor || left.po != right.po || left == right)

def conflicts (left right : Event) : Bool :=
  left.address = right.address && (left.isStore || right.isStore)

/-- Table 7-4 base rules a, c, e/g/h for the WB/WC subset. -/
def baseRequired (left right : Event) : Bool :=
  programBefore left right && left.isAccess && right.isAccess &&
  ((left.isLoad && right.isStore) ||
   (left.isLoad && right.kind = .load && right.memoryType = .wb) ||
   (left.kind = .store && left.memoryType = .wb &&
     right.kind = .store && right.memoryType = .wb) ||
   conflicts left right)

def fenceBetween (events : List Event) (fenceKind : EventKind)
    (left right : Event) : Bool :=
  events.any fun fence =>
    fence.kind = fenceKind && programBefore left fence && programBefore fence right

/-- LFENCE orders load pairs only. This predicate does not claim that LFENCE
blocks all speculative execution. SFENCE orders stores; MFENCE orders accesses. -/
def fenceRequired (events : List Event) (left right : Event) : Bool :=
  programBefore left right && left.isAccess && right.isAccess &&
  (fenceBetween events .mfence left right ||
   (left.isLoad && right.isLoad && fenceBetween events .lfence left right) ||
   (left.isStore && right.isStore && fenceBetween events .sfence left right))

/-- Table 7-4 rules d/k for explicit LOCK and implicitly locked XCHG events. -/
def lockedRequired (left right : Event) : Bool :=
  programBefore left right &&
  ((left.isAccess && right.kind = .lockedRMW) ||
   (left.kind = .lockedRMW && right.isAccess))

def ruleRequires (events : List Event) (left right : Event) : Bool :=
  baseRequired left right || fenceRequired events left right ||
    lockedRequired left right

def requiredEdges (events : List Event) : List Edge :=
  events.flatMap fun left => events.filterMap fun right =>
    if ruleRequires events left right then some ⟨left.id, right.id⟩ else none

def strictPartialOrder (events : List Event) (order : List Edge) : Bool :=
  let ids := events.map (·.id)
  order.all (fun edge => ids.contains edge.left && ids.contains edge.right) &&
  ids.all (fun id => !order.contains (Edge.mk id id)) &&
  order.all fun first => order.all fun second =>
    first.right != second.left || order.contains (Edge.mk first.left second.right)

def admissibleOrder (events : List Event) (order : List Edge) : Bool :=
  orderingApplicable events && strictPartialOrder events order &&
  (requiredEdges events).all order.contains

def ordered (order : List Edge) (left right : Event) : Bool :=
  order.contains (Edge.mk left.id right.id)

def validRFEdge (events : List Event) (order : List Edge) (edge : Edge) : Bool :=
  if edge.left = 0 then
    events.any fun reader =>
      reader.id = edge.right && reader.isLoad && reader.readValue = 0
  else events.any fun writer => events.any fun reader =>
    writer.id = edge.left && reader.id = edge.right &&
    writer != reader &&
    writer.isStore && reader.isLoad && writer.address = reader.address &&
    writer.writeValue = reader.readValue &&
    !programBefore reader writer && !ordered order reader writer

def readFromWellFormed (events : List Event) (order rf : List Edge) : Bool :=
  events.all (fun event => event.id != 0) &&
  rf.all (validRFEdge events order) &&
  events.all fun reader =>
    !reader.isLoad || (rf.filter fun edge => edge.right = reader.id).length = 1

def readsFrom (rf : List Edge) (writer reader : Event) : Bool :=
  rf.contains (Edge.mk writer.id reader.id)

def publishedBefore (events : List Event) (order rf : List Edge)
    (writer reader : Event) : Bool :=
  events.any fun release => events.any fun acquire =>
    release.kind = .lockedRMW && acquire.kind = .lockedRMW &&
    release.processor != acquire.processor && ordered order writer release &&
    readsFrom rf release acquire && ordered order acquire reader

def singleWriterAddress (events : List Event) (writer : Event) : Bool :=
  events.all fun other =>
    !(other.isStore && other.address = writer.address) || other == writer

def publicationConsistent (events : List Event) (order rf : List Edge) : Bool :=
  readFromWellFormed events order rf &&
  events.all fun writer => events.all fun reader =>
    !(publishedBefore events order rf writer reader &&
      writer.address = reader.address &&
      singleWriterAddress events writer) || readsFrom rf writer reader

namespace Fixture

def event (id processor po : Int) (kind : EventKind) (memoryType : MemoryType)
    (address readValue writeValue : Int) : Event :=
  { id, processor, po, kind, memoryType, address, readValue, writeValue,
    sideEffectfulDevice := false, cacheableAligned := true }

def pData := event 1 0 0 .streamStore .wc 100 (-1) 42
def release := event 2 0 1 .lockedRMW .wb 200 0 1
def acquire := event 3 1 0 .lockedRMW .wb 200 1 1
def cData := event 4 1 1 .streamLoad .wc 100 42 (-1)
def positiveEvents := [pData, release, acquire, cData]
def positiveOrder := [Edge.mk 1 2, Edge.mk 3 4]
def positiveRF := [Edge.mk 0 2, Edge.mk 2 3, Edge.mk 1 4]

def nData := event 11 0 0 .streamStore .wc 100 (-1) 42
def nSignal := event 12 0 1 .store .wb 200 (-1) 1
def nSeen := event 13 1 0 .load .wb 200 1 (-1)
def nStale := event 14 1 1 .streamLoad .wc 100 0 (-1)
def negativeEvents := [nData, nSignal, nSeen, nStale]
def negativeRF := [Edge.mk 12 13, Edge.mk 0 14]

def fLoad0 := event 21 0 0 .streamLoad .wc 300 0 (-1)
def lf := event 22 0 1 .lfence .unknown (-1) (-1) (-1)
def fLoad1 := event 23 0 2 .streamLoad .wc 304 0 (-1)
def fStore0 := event 24 1 0 .streamStore .wc 400 (-1) 1
def sf := event 25 1 1 .sfence .unknown (-1) (-1) (-1)
def fStore1 := event 26 1 2 .store .wb 500 (-1) 1
def mStore := event 27 2 0 .streamStore .wc 600 (-1) 1
def mf := event 28 2 1 .mfence .unknown (-1) (-1) (-1)
def mLoad := event 29 2 2 .streamLoad .wc 700 0 (-1)
def fenceEvents := [fLoad0, lf, fLoad1, fStore0, sf, fStore1,
  mStore, mf, mLoad]
def lfStore := event 33 3 0 .store .wb 900 (-1) 1
def lfOnly := event 34 3 1 .lfence .unknown (-1) (-1) (-1)
def lfLoad := event 35 3 2 .streamLoad .wc 904 0 (-1)
def lfStoreLoadEvents := [lfStore, lfOnly, lfLoad]

def unknownLoad := event 31 0 0 .load .unknown 0 0 (-1)
def destructiveStream : Event :=
  { event 32 0 0 .streamLoad .wc 0 0 (-1) with sideEffectfulDevice := true }
def busLockedWC : Event :=
  { event 36 0 0 .lockedRMW .wc 0 0 1 with cacheableAligned := true }
def busLockedMisalignedWB : Event :=
  { event 37 0 0 .lockedRMW .wb 0 0 1 with cacheableAligned := false }

def sbStore0 := event 41 0 0 .store .wb 800 (-1) 1
def sbLoad0 := event 42 0 1 .load .wb 804 0 (-1)
def sbStore1 := event 43 1 0 .store .wb 804 (-1) 1
def sbLoad1 := event 44 1 1 .load .wb 800 0 (-1)
def storeBufferEvents := [sbStore0, sbLoad0, sbStore1, sbLoad1]
def storeBufferRF := [Edge.mk 0 42, Edge.mk 0 44]

def dData := event 51 0 0 .streamStore .wc 1000 (-1) 7
def dRelease1 := event 52 0 1 .lockedRMW .wb 1100 0 1
def dRelease2 := event 53 2 0 .lockedRMW .wb 1100 0 1
def dAcquire := event 54 1 0 .lockedRMW .wb 1100 1 1
def dRead := event 55 1 1 .streamLoad .wc 1000 0 (-1)
def duplicateEvents := [dData, dRelease1, dRelease2, dAcquire, dRead]
def duplicateOrder := [Edge.mk 51 52, Edge.mk 54 55]
def duplicateRF := [Edge.mk 0 52, Edge.mk 0 53, Edge.mk 53 54, Edge.mk 0 55]

def racing := event 61 2 0 .streamStore .wc 100 (-1) 99
def racingRead := event 62 1 1 .streamLoad .wc 100 99 (-1)
def racingEvents := [pData, release, acquire, racing, racingRead]
def racingOrder := [Edge.mk 1 2, Edge.mk 3 62]
def racingRF := [Edge.mk 0 2, Edge.mk 2 3, Edge.mk 61 62]
def futureReader := event 71 4 0 .load .wb 1200 5 (-1)
def futureWriter := event 72 4 1 .store .wb 1200 (-1) 5
def futureEvents := [futureReader, futureWriter]
def futureRF := Edge.mk 72 71
def selfRF := Edge.mk 2 2

example : admissibleOrder positiveEvents positiveOrder = true := by decide
example : publishedBefore positiveEvents positiveOrder positiveRF pData cData = true := by decide
example : publicationConsistent positiveEvents positiveOrder positiveRF = true := by decide
example : readsFrom positiveRF release acquire = true := by decide

example : admissibleOrder negativeEvents [] = true := by decide
example : readFromWellFormed negativeEvents [] negativeRF = true := by decide
example : publishedBefore negativeEvents [] negativeRF nData nStale = false := by decide
example : nStale.readValue != nData.writeValue := by decide
example : ruleRequires negativeEvents nData nSignal = false := by decide
example : ruleRequires negativeEvents nSeen nStale = false := by decide

example : fenceRequired fenceEvents fLoad0 fLoad1 = true := by decide
example : fenceRequired fenceEvents fStore0 fStore1 = true := by decide
example : fenceRequired fenceEvents mStore mLoad = true := by decide
example : fenceRequired lfStoreLoadEvents lfStore lfLoad = false := by decide
example : lockTransport release = .cacheableLock := by decide
example : lockTransport busLockedWC = .busLock := by decide
example : lockTransport busLockedMisalignedWB = .busLock := by decide
example : supportedEvent unknownLoad = false := by decide
example : supportedEvent destructiveStream = false := by decide

example : admissibleOrder storeBufferEvents [] = true := by decide
example : readFromWellFormed storeBufferEvents [] storeBufferRF = true := by decide
example : sbLoad0.readValue = 0 ∧ sbLoad1.readValue = 0 := by decide

example : readFromWellFormed duplicateEvents duplicateOrder duplicateRF = true := by decide
example : publishedBefore duplicateEvents duplicateOrder duplicateRF dData dRead = false := by decide
example : readsFrom duplicateRF dRelease2 dAcquire = true := by decide
example : readFromWellFormed racingEvents racingOrder racingRF = true := by decide
example : publishedBefore racingEvents racingOrder racingRF pData racingRead = true := by decide
example : singleWriterAddress racingEvents pData = false := by decide
example : readsFrom racingRF racing racingRead = true := by decide
example : validRFEdge futureEvents [] futureRF = false := by decide
example : validRFEdge positiveEvents positiveOrder selfRF = false := by decide

end Fixture
end AMD64.MemoryOrdering
