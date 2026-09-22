import AMD64.ConcreteMemory
import AMD64.IntegerExecution
import AMD64.IntegerSemantics
import AMD64.MemoryTypes
import Std

namespace AMD64.Atomic

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.Operands

noncomputable section
open scoped Classical

abbrev Word := IWord

def wordBit (word : Word) (index : Nat) : Bool :=
  if h : index < 64 then word ⟨index, h⟩ else false

def bytesToWord (bytes : List Byte) : Word := fun bit =>
  match bytes[bit.val / 8]? with
  | some byte => byte ⟨bit.val % 8, by omega⟩
  | none => false

def wordBytes (word : Word) (width : Nat) : List Byte :=
  (List.range (width / 8)).map fun byteIndex => fun bit =>
    wordBit word (byteIndex * 8 + bit.val)

def readBytes (memory : Store) (physical : PhysicalAddress) (count : Nat) : List Byte :=
  (List.range count).map fun offset =>
    memory.read (addAddress physical (addressOfNat offset))

def writeBytes (memory : Store) (physical : PhysicalAddress)
    (bytes : List Byte) : Store :=
  (bytes.zipIdx).foldl (fun current pair =>
    current.write (addAddress physical (addressOfNat pair.2)) pair.1) memory

/-- Read the exact physical byte sequence authorized by `resolveAccess`.
This avoids assuming that a virtual access remains physically contiguous at a
page boundary. -/
def readResolved (memory : Store) (access : ResolvedAccess) : List Byte :=
  access.bytes.map fun byte => memory.read byte.physical

/-- Write only the physical bytes authorized by `resolveAccess`. -/
def writeResolved (memory : Store) (access : ResolvedAccess)
    (bytes : List Byte) : Option Store :=
  if access.bytes.length ≠ bytes.length then none
  else some ((access.bytes.zip bytes).foldl
    (fun current pair => current.write pair.1.physical pair.2) memory)

structure Event where
  kind : String
  physical : PhysicalAddress
  width : Nat
  before : List Byte
  after : List Byte
  locked : Bool
  /-- An RMW event is indivisible only when locking is implicit or selected. -/
  atomic : Bool
  memoryType : MemoryTypes.Resolution

structure XchgOutcome where
  memory : Store
  register : Word
  event : Event

def xchg (memory : Store) (physical : PhysicalAddress) (source : Word)
    (width : Nat) (memoryType : MemoryTypes.Resolution) : XchgOutcome :=
  let before := readBytes memory physical (width / 8)
  let after := wordBytes source width
  { memory := writeBytes memory physical after
    register := truncate (bytesToWord before) width
    event := Event.mk "xchg" physical width before after true true memoryType }

structure XAddOutcome where
  memory : Store
  destination : Word
  source : Word
  flags : ArithmeticFlags
  event : Event

def xadd (memory : Store) (physical : PhysicalAddress) (source : Word)
    (width : Nat) (locked : Bool) (memoryType : MemoryTypes.Resolution) : XAddOutcome :=
  let before := readBytes memory physical (width / 8)
  let oldDestination := bytesToWord before
  let result := addResult oldDestination source false width
  let after := wordBytes result.value width
  { memory := writeBytes memory physical after
    destination := result.value
    source := truncate oldDestination width
    flags := result.flags
    event := Event.mk "xadd" physical width before after locked locked memoryType }

structure CompareExchangeOutcome where
  memory : Store
  accumulator : Word
  destination : Word
  flags : ArithmeticFlags
  equal : Bool
  event : Event

def activeEqual (left right : Word) (width : Nat) : Bool :=
  (List.range width).all fun bit =>
    wordBit left bit == wordBit right bit

def compareExchange (memory : Store) (physical : PhysicalAddress)
    (accumulator source : Word) (width : Nat) (locked : Bool)
    (memoryType : MemoryTypes.Resolution) : CompareExchangeOutcome :=
  let before := readBytes memory physical (width / 8)
  let destination := bytesToWord before
  let comparison := subResult accumulator destination false width
  let equal := activeEqual accumulator destination width
  let after := if equal then wordBytes source width else before
  { memory := if equal then writeBytes memory physical after else memory
    accumulator := if equal then truncate accumulator width else truncate destination width
    destination := if equal then truncate source width else truncate destination width
    flags := comparison.flags
    equal
    event := Event.mk "cmpxchg" physical width before after locked locked memoryType }

structure BlockCompareExchangeOutcome where
  memory : Store
  expected : List Byte
  observed : List Byte
  zf : Bool
  event : Event

inductive BlockError where
  | invalidLength
  | cx16Unavailable
  | generalProtectionAlignment
  deriving DecidableEq, Repr

def aligned16 (physical : PhysicalAddress) : Prop :=
  ∀ bit : Fin 64, bit.val < 4 -> physical bit = false

def compareExchangeBlock (memory : Store) (physical : PhysicalAddress)
    (expected replacement : List Byte) (byteCount : Nat)
    (cx16 lockPrefix : Bool) (memoryType : MemoryTypes.Resolution) :
    Except BlockError BlockCompareExchangeOutcome :=
  if byteCount ∉ [8, 16] ∨ expected.length ≠ byteCount ∨
      replacement.length ≠ byteCount then .error .invalidLength
  else if byteCount = 16 ∧ !cx16 then .error .cx16Unavailable
  else if byteCount = 16 ∧ ¬ aligned16 physical then
    .error .generalProtectionAlignment
  else
    let observed := readBytes memory physical byteCount
    let equal := observed = expected
    let after := if equal then replacement else observed
    .ok {
      memory := if equal then writeBytes memory physical replacement else memory
      expected := if equal then expected else observed
      observed
      zf := equal
      event := Event.mk (if byteCount = 16 then "cmpxchg16b" else "cmpxchg8b")
        physical (byteCount * 8) observed after lockPrefix lockPrefix memoryType }

theorem xchg_memory_is_implicitly_atomic (memory : Store)
    (physical : PhysicalAddress) (source : Word) (width : Nat)
    (memoryType : MemoryTypes.Resolution) :
    (xchg memory physical source width memoryType).event.atomic = true := rfl

theorem xadd_without_lock_is_not_atomic (memory : Store)
    (physical : PhysicalAddress) (source : Word) (width : Nat)
    (memoryType : MemoryTypes.Resolution) :
    (xadd memory physical source width false memoryType).event.atomic = false := rfl

theorem cmpxchg_without_lock_is_not_atomic (memory : Store)
    (physical : PhysicalAddress) (accumulator source : Word) (width : Nat)
    (memoryType : MemoryTypes.Resolution) :
    (compareExchange memory physical accumulator source width false memoryType).event.atomic =
      false := rfl

/-!
## Permission-checked CPU and concrete-memory binding

The helpers above expose value kernels. The adapter below is the instruction
boundary: it resolves a read/write operand through the shared segmentation,
paging, protection, and ordinary-alignment path before reading or changing
concrete memory. Resolution failure returns the exact memory-layer error and
leaves construction of a successful outcome impossible.

Form decoding remains a separate reviewed boundary. `MemoryInstruction` is
accepted only after its form layer has selected the operation, explicit source
register, prefix, byte count, and address request.
-/

inductive Operation where
  | xchg | xadd | cmpxchg | cmpxchg8b | cmpxchg16b
  deriving DecidableEq, Repr

def Operation.width : Operation -> Nat
  | .xchg | .xadd | .cmpxchg => 0
  | .cmpxchg8b => 64
  | .cmpxchg16b => 128

def Operation.kind : Operation -> String
  | .xchg => "xchg"
  | .xadd => "xadd"
  | .cmpxchg => "cmpxchg"
  | .cmpxchg8b => "cmpxchg8b"
  | .cmpxchg16b => "cmpxchg16b"

def Operation.locked (operation : Operation) (lockPrefix : Bool) : Bool :=
  operation = .xchg || lockPrefix

structure Capabilities where
  cmpxchg8b : Bool
  cmpxchg16b : Bool

structure MemoryInstruction where
  operation : Operation
  width : Nat
  source : GPRRef
  request : AddressRequest
  lockPrefix : Bool
  capabilities : Capabilities
  memoryType : MemoryTypes.Resolution

inductive ExecutionError where
  | invalidWidth
  | invalidSource
  | invalidAccessIntent
  | cmpxchg8bUnavailable
  | cmpxchg16bUnavailable
  | cmpxchg16bMode
  | generalProtectionAlignment
  | memoryResolution (cause : ResolutionError)

structure ExecutionOutcome where
  state : ConcreteMachineState
  event : Event
  resolved : ResolvedAccess

def viewForWidth : Nat -> Option GPRView
  | 8 => some .low8
  | 16 => some .low16
  | 32 => some .low32
  | 64 => some .full64
  | _ => none

def registerForWidth (register : GPR) (width : Nat) : Option GPRRef := do
  let view <- viewForWidth width
  pure { index := register.toFin, view }

def requestCompatible (instruction : MemoryInstruction) : Bool :=
  instruction.request.access.kind = AccessKind.readWrite &&
  instruction.request.byteCount = instruction.width / 8 &&
  match instruction.operation with
  | .cmpxchg8b => instruction.width = 64
  | .cmpxchg16b => instruction.width = 128
  | .xchg | .xadd | .cmpxchg => instruction.width ∈ [8, 16, 32, 64]

/-- Feature and mode faults whose priority is above data-access translation.
Volume 2 Table 8-9 places #UD above data-access #PF, so these checks must run
before `resolveAccess`. -/
private def preAccessLegality (instruction : MemoryInstruction)
    (state : CPUState) : Except ExecutionError Unit := do
  match instruction.operation with
  | .cmpxchg8b =>
      if !instruction.capabilities.cmpxchg8b then throw .cmpxchg8bUnavailable
      else pure ()
  | .cmpxchg16b =>
      if !instruction.capabilities.cmpxchg16b then throw .cmpxchg16bUnavailable
      else if state.execution.mode ≠ .long64 then throw .cmpxchg16bMode
      else pure ()
  | .xchg | .xadd | .cmpxchg => pure ()

def splitBytes (bytes : List Byte) (half : Nat) : List Byte × List Byte :=
  (bytes.take half, bytes.drop half |>.take half)

def pairRegisterBytes (state : CPUState) (low high : GPR) (halfWidth : Nat) :
    List Byte :=
  match registerForWidth low halfWidth, registerForWidth high halfWidth with
  | some lowRef, some highRef =>
      wordBytes (readGPR state lowRef) halfWidth ++
        wordBytes (readGPR state highRef) halfWidth
  | _, _ => []

def writeRegisterBytes (state : CPUState) (register : GPR) (width : Nat)
    (bytes : List Byte) : CPUState :=
  match registerForWidth register width with
  | some reference => writeGPR state reference (bytesToWord bytes)
  | none => state

def writeExpectedPair (state : CPUState) (halfWidth : Nat)
    (observed : List Byte) : CPUState :=
  let halves := splitBytes observed (halfWidth / 8)
  let withLow := writeRegisterBytes state .rax halfWidth halves.1
  writeRegisterBytes withLow .rdx halfWidth halves.2

def withZF (state : CPUState) (zf : Bool) : CPUState :=
  { state with rflags := { state.rflags with zf } }

private def eventForResolved (instruction : MemoryInstruction)
    (resolved : ResolvedAccess) (before after : List Byte) : Event :=
  { kind := instruction.operation.kind
    physical := match resolved.bytes with
      | first :: _ => first.physical
      | [] => resolved.linear
    width := instruction.width
    before
    after
    locked := instruction.operation.locked instruction.lockPrefix
    atomic := instruction.operation.locked instruction.lockPrefix
    memoryType := instruction.memoryType }

private def executeScalar (instruction : MemoryInstruction)
    (before : ConcreteMachineState) (resolved : ResolvedAccess) :
    Except ExecutionError ExecutionOutcome := do
  let sourceRef := instruction.source
  if sourceRef.width ≠ instruction.width ∨ ¬ sourceRef.Valid before.cpu.execution then
    throw .invalidSource
  let oldBytes := readResolved before.memory resolved
  let destination := bytesToWord oldBytes
  let source := readGPR before.cpu sourceRef
  match instruction.operation with
  | .xchg =>
      let newBytes := wordBytes source instruction.width
      let some memory := writeResolved before.memory resolved newBytes
        | throw .invalidWidth
      let cpu := writeGPR before.cpu sourceRef destination
      pure { state := { cpu, memory }
             event := eventForResolved instruction resolved oldBytes newBytes
             resolved }
  | .xadd =>
      let result := addResult destination source false instruction.width
      let newBytes := wordBytes result.value instruction.width
      let some memory := writeResolved before.memory resolved newBytes
        | throw .invalidWidth
      let cpu := writeStatus (writeGPR before.cpu sourceRef destination) result.flags
      pure { state := { cpu, memory }
             event := eventForResolved instruction resolved oldBytes newBytes
             resolved }
  | .cmpxchg =>
      let some accumulatorRef := registerForWidth .rax instruction.width
        | throw .invalidWidth
      let accumulator := readGPR before.cpu accumulatorRef
      let comparison := subResult accumulator destination false instruction.width
      let equal := activeEqual accumulator destination instruction.width
      let newBytes := if equal then wordBytes source instruction.width else oldBytes
      /- CMPXCHG performs a memory RMW even on comparison failure. The total
         store is extensionally unchanged when the same bytes are written. -/
      let some memory := writeResolved before.memory resolved newBytes
        | throw .invalidWidth
      let compared := if equal then before.cpu else writeGPR before.cpu accumulatorRef destination
      let cpu := writeStatus compared comparison.flags
      pure { state := { cpu, memory }
             event := eventForResolved instruction resolved oldBytes newBytes
             resolved }
  | _ => throw .invalidWidth

private def executeBlock (instruction : MemoryInstruction)
    (before : ConcreteMachineState) (resolved : ResolvedAccess) :
    Except ExecutionError ExecutionOutcome := do
  let halfWidth := if instruction.operation = .cmpxchg16b then 64 else 32
  if instruction.operation = .cmpxchg16b && ¬ aligned16 resolved.linear then
    throw .generalProtectionAlignment
  let observed := readResolved before.memory resolved
  let expected := pairRegisterBytes before.cpu .rax .rdx halfWidth
  let replacement := pairRegisterBytes before.cpu .rbx .rcx halfWidth
  let equal := observed = expected
  let newBytes := if equal then replacement else observed
  let some memory := writeResolved before.memory resolved newBytes
    | throw .invalidWidth
  let compared := if equal then before.cpu else writeExpectedPair before.cpu halfWidth observed
  let cpu := withZF compared equal
  pure { state := { cpu, memory }
         event := eventForResolved instruction resolved observed newBytes
         resolved }

/-- Resolve permissions and all bytes before applying the instruction body.
The returned event is atomic exactly for memory XCHG or a selected LOCK prefix.
Unresolved memory type remains carried as an unresolved `Resolution`; it is
never replaced by WB. -/
def executeMemory (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (instruction : MemoryInstruction)
    (before : ConcreteMachineState) : Except ExecutionError ExecutionOutcome := do
  if !requestCompatible instruction then
    throw (if instruction.request.access.kind = AccessKind.readWrite then
      .invalidWidth else .invalidAccessIntent)
  preAccessLegality instruction before.cpu
  let resolved <- (resolveAccess profile config before.cpu pages instruction.request).mapError
    ExecutionError.memoryResolution
  match instruction.operation with
  | .cmpxchg8b | .cmpxchg16b => executeBlock instruction before resolved
  | .xchg | .xadd | .cmpxchg =>
      match viewForWidth instruction.width with
      | some _ => executeScalar instruction before resolved
      | none => throw .invalidWidth

theorem operation_xchg_implicitly_locked (lockPrefix : Bool) :
    Operation.xchg.locked lockPrefix = true := by simp [Operation.locked]

theorem operation_xadd_unlocked_without_prefix :
    Operation.xadd.locked false = false := by decide

theorem operation_cmpxchg_unlocked_without_prefix :
    Operation.cmpxchg.locked false = false := by decide

theorem unavailable_cmpxchg16b_fails_before_access
    (instruction : MemoryInstruction) (state : CPUState)
    (operation : instruction.operation = .cmpxchg16b)
    (unavailable : instruction.capabilities.cmpxchg16b = false) :
    preAccessLegality instruction state = .error .cmpxchg16bUnavailable := by
  unfold preAccessLegality
  rw [operation, unavailable]
  rfl

theorem xadd_flags_from_add (memory : Store) (physical : PhysicalAddress)
    (source : Word) (width : Nat) (locked : Bool)
    (memoryType : MemoryTypes.Resolution) :
    (xadd memory physical source width locked memoryType).flags =
      (addResult (bytesToWord (readBytes memory physical (width / 8)))
        source false width).flags := rfl

theorem cmpxchg_flags_from_sub (memory : Store) (physical : PhysicalAddress)
    (accumulator source : Word) (width : Nat) (locked : Bool)
    (memoryType : MemoryTypes.Resolution) :
    (compareExchange memory physical accumulator source width locked memoryType).flags =
      (subResult accumulator
        (bytesToWord (readBytes memory physical (width / 8))) false width).flags := rfl

end
end AMD64.Atomic
