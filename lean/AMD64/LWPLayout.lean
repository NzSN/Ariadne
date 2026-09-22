import AMD64.ConcreteMemory
import AMD64.IntegerSemantics
import Std

/-!
Concrete LWPCB byte layout and normalization.

Authority: AMD APM Volume 2 revision 3.45 PDF pages 535-539 and 545-554.
Architectural decoding reads total concrete memory. Captured memory is exposed
only through a separate `capturedBytes` adapter whose absence is knowledge
unavailability, not an architectural fault or zero.
-/

namespace AMD64.LWPLayout

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory

noncomputable section
open scoped Classical

structure Profile where
  controlBlockQuadwords : Nat
  eventSize : Nat
  maxEvents : Nat
  eventOffset : Nat
  minimumBufferUnits : Nat
  availableFlag : Fin 32 -> Bool
  minimumInterval : Nat -> Nat

def Profile.controlBlockBytes (profile : Profile) : Nat :=
  profile.controlBlockQuadwords * 8

def Profile.validB (profile : Profile) : Bool :=
  profile.eventSize > 0 && profile.maxEvents > 0 &&
  profile.eventOffset ≥ 88 && profile.eventOffset % 8 = 0 &&
  profile.eventOffset + profile.maxEvents * 8 ≤ profile.controlBlockBytes

def byteNat (byte : Byte) : Nat :=
  (List.range 8).foldl (fun total bit =>
    if byte (Fin.ofNat 8 bit) then total + 2 ^ bit else total) 0

def readLE (bytes : List Byte) (offset count : Nat) : Nat :=
  (List.range count).foldl (fun total index =>
    match bytes[offset + index]? with
    | some byte => total + byteNat byte * 2 ^ (8 * index)
    | none => total) 0

def signed26 (raw : Nat) : Int :=
  if raw.testBit 25 then Int.ofNat (raw % (2^26)) - Int.ofNat (2^26)
  else Int.ofNat (raw % (2^26))

structure EventConfig where
  eventId : Nat
  intervalRaw : Nat
  counterRaw : Nat
  interval : Int
  counter : Int
  reservedClear : Bool
  deriving DecidableEq, Repr

structure ControlBlock where
  requestedFlags : Nat
  bufferSize : Nat
  randomBits : Nat
  bufferBase : Address
  bufferHeadOffset : Nat
  missedEvents : Address
  threshold : Nat
  filters : Nat
  baseIP : Address
  limitIP : Address
  bufferTailOffset : Nat
  fixedReservedClear : Bool
  softwareReservedClear : Bool
  events : List EventConfig

def addressAt (bytes : List Byte) (offset : Nat) : Address := fun bit =>
  match bytes[offset + bit.val / 8]? with
  | some byte => byte ⟨bit.val % 8, Nat.mod_lt _ (by decide)⟩
  | none => false

def bytesZero (bytes : List Byte) (start count : Nat) : Bool :=
  (List.range count).all fun index =>
    match bytes[start + index]? with
    | some byte => byteNat byte = 0
    | none => false

def decodeEvent (profile : Profile) (bytes : List Byte) (index : Nat) : EventConfig :=
  let offset := profile.eventOffset + index * 8
  let intervalRaw := readLE bytes offset 4
  let counterRaw := readLE bytes (offset + 4) 4
  { eventId := index + 1
    intervalRaw
    counterRaw
    interval := signed26 intervalRaw
    counter := signed26 counterRaw
    reservedClear := intervalRaw / 2^26 = 0 && counterRaw / 2^26 = 0 }

def decode (profile : Profile) (bytes : List Byte) : Option ControlBlock :=
  if !profile.validB || bytes.length ≠ profile.controlBlockBytes then none
  else some {
    requestedFlags := readLE bytes 0 4
    bufferSize := readLE bytes 4 4 % 2^28
    randomBits := readLE bytes 4 4 / 2^28
    bufferBase := addressAt bytes 8
    bufferHeadOffset := readLE bytes 16 4
    missedEvents := addressAt bytes 24
    threshold := readLE bytes 32 4
    filters := readLE bytes 36 4
    baseIP := addressAt bytes 40
    limitIP := addressAt bytes 48
    bufferTailOffset := readLE bytes 64 4
    fixedReservedClear := bytesZero bytes 20 4 && bytesZero bytes 56 8 &&
      bytesZero bytes 68 4
    softwareReservedClear := bytesZero bytes 72 (profile.eventOffset - 72)
    events := (List.range profile.maxEvents).map (decodeEvent profile bytes) }

structure NormalizedEvent where
  eventId : Nat
  interval : Nat
  counter : Nat
  deriving DecidableEq, Repr

structure Normalized where
  enabledFlag : Fin 32 -> Bool
  bufferSize : Nat
  randomBits : Nat
  bufferBase : Address
  bufferHeadOffset : Nat
  missedEvents : Address
  threshold : Nat
  filters : Nat
  baseIP : Address
  limitIP : Address
  bufferTailOffset : Nat
  tailProtocolValid : Bool
  reservedProtocolValid : Bool
  events : List NormalizedEvent

def normalizeEvent (profile : Profile) (event : EventConfig) : NormalizedEvent :=
  let interval :=
    if event.interval < 0 then
      if event.eventId = 1 then 0 else profile.minimumInterval event.eventId
    else max event.interval.toNat
      (if event.eventId = 1 then 0 else profile.minimumInterval event.eventId)
  let counter := if event.counter < 0 then 0 else event.counter.toNat
  { eventId := event.eventId, interval, counter }

def normalize (profile : Profile) (block : ControlBlock) : Option Normalized :=
  if !profile.validB then none
  else
    let size := block.bufferSize - block.bufferSize % profile.eventSize
    let minimum := 32 * profile.minimumBufferUnits * profile.eventSize
    if size < minimum || size = 0 then none
    else some {
      enabledFlag := fun bit => block.requestedFlags.testBit bit.val &&
        profile.availableFlag bit
      bufferSize := size
      randomBits := block.randomBits
      bufferBase := block.bufferBase
      bufferHeadOffset := if block.bufferHeadOffset ≥ size then 0
        else block.bufferHeadOffset - block.bufferHeadOffset % profile.eventSize
      missedEvents := block.missedEvents
      threshold := block.threshold - block.threshold % profile.eventSize
      filters := block.filters
      baseIP := block.baseIP
      limitIP := block.limitIP
      bufferTailOffset := block.bufferTailOffset
      tailProtocolValid := block.bufferTailOffset < size &&
        block.bufferTailOffset % profile.eventSize = 0
      reservedProtocolValid := block.fixedReservedClear &&
        block.softwareReservedClear && block.events.all (·.reservedClear)
      events := block.events.map (normalizeEvent profile) }

def concreteBytes (memory : Store) (addresses : List PhysicalAddress) : List Byte :=
  addresses.map memory.read

def decodeConcrete (profile : Profile) (memory : Store)
    (addresses : List PhysicalAddress) : Option ControlBlock :=
  decode profile (concreteBytes memory addresses)

def capturedBytes (captured : MemoryState) : List PhysicalAddress -> Option (List Byte)
  | [] => some []
  | address :: rest =>
      match captured.readByte address, capturedBytes captured rest with
      | .available byte, some tail => some (byte :: tail)
      | _, _ => none

inductive CaptureDecode where
  | decoded (block : ControlBlock)
  | unavailable
  | invalidLayout

def decodeCaptured (profile : Profile) (captured : MemoryState)
    (addresses : List PhysicalAddress) : CaptureDecode :=
  match capturedBytes captured addresses with
  | none => .unavailable
  | some bytes => match decode profile bytes with
      | some block => .decoded block
      | none => .invalidLayout

theorem captured_bytes_match_concrete (concrete : Store) (captured : MemoryState)
    (addresses : List PhysicalAddress) (refines : RefinesCaptured concrete captured)
    (covered : ∀ address ∈ addresses, address ∈ captured.captured) :
    capturedBytes captured addresses = some (concreteBytes concrete addresses) := by
  induction addresses with
  | nil => rfl
  | cons address rest induction =>
      have member : address ∈ captured.captured := covered address (by simp)
      have head := (refines.2.2 address member).2
      have tailCovered : ∀ candidate ∈ rest, candidate ∈ captured.captured := by
        intro candidate candidateMember
        exact covered candidate (by simp [candidateMember])
      simp [capturedBytes, concreteBytes, head, induction tailCovered]

end
end AMD64.LWPLayout
