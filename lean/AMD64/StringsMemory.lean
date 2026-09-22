import AMD64.Strings
import Std

/-!
Actual CPU/memory iteration binding for the memory-only AMD64 string entries:
CMPS, LODS, MOVS, SCAS, and STOS.

INS/OUTS are deliberately excluded until a constrained device/port executor
defines their observable effects and fault ordering. Missing captured bytes
produce `unavailable`, never architectural zero and never a fabricated fault.

Preparation reads every source from the before-memory snapshot before any
write. MOVS then writes the captured source bytes, so overlapping later
iterations observe the memory produced by earlier committed iterations.
-/

namespace AMD64.StringsMemory

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics
open AMD64.Strings

def readResultsToBytes : List MemoryReadResult -> Option (List Byte)
  | [] => some []
  | .available byte :: rest => (readResultsToBytes rest).map (byte :: ·)
  | .unavailable :: _ => none

def bytesToWord (bytes : List Byte) : IWord := fun bit =>
  match bytes[bit.val / 8]? with
  | some byte => byte ⟨bit.val % 8, Nat.mod_lt _ (by decide)⟩
  | none => false

def wordToBytes (word : IWord) (byteCount : Nat) : List Byte :=
  (List.range byteCount).map fun byteIndex bit =>
    getBit word (byteIndex * 8 + bit.val)

theorem wordToBytes_length (word : IWord) (byteCount : Nat) :
    (wordToBytes word byteCount).length = byteCount := by
  simp [wordToBytes]

@[simp] theorem bytesToWord_empty : bytesToWord [] = zero := by
  funext bit
  simp [bytesToWord, zero]

@[simp] theorem unavailable_head_is_not_data (rest : List MemoryReadResult) :
    readResultsToBytes (.unavailable :: rest) = none := rfl

theorem bytesToWord_singleton_low (byte : Byte) (bit : Fin 8) :
    bytesToWord [byte] ⟨bit.val, by omega⟩ = byte bit := by
  simp [bytesToWord, Nat.div_eq_of_lt bit.isLt, Nat.mod_eq_of_lt bit.isLt]

def byteMemoryType (byte : ResolvedByte) : Option MemoryType :=
  byte.page.bind fun page => page.memoryType

def eventsForAccess (kind : MemoryEventKind) (access : ResolvedAccess)
    (values : List Byte) : List MemoryEvent :=
  (access.bytes.zip values).map fun pair => {
    kind
    linear := some pair.1.linear
    physical := some pair.1.physical
    size := 1
    value := [pair.2]
    memoryType := byteMemoryType pair.1
  }

theorem read_after_write_byte (memory : MemoryState) (physical : PhysicalAddress)
    (value : Byte) :
    (memory.writeByte physical value).readByte physical = .available value := by
  simp [MemoryState.writeByte, MemoryState.readByte]

inductive ReadAttempt where
  | ready (access : ResolvedAccess) (bytes : List Byte) (events : List MemoryEvent)
  | fault (error : ResolutionError)
  | unavailable (access : ResolvedAccess)
  | unsupportedStage

noncomputable def readStage (profile : ArchitectureProfile) (config : SystemConfig)
    (cpu : CPUState) (pages : PageMap) (memory : MemoryState) (spec : Spec)
    (control : Control) (sourceSegment : SegmentReg) (stage : Stage) : ReadAttempt :=
  match resolveMemoryStage profile config cpu pages spec control sourceSegment stage with
  | none => .unsupportedStage
  | some (.error error) => .fault error
  | some (.ok access) =>
      match readResultsToBytes (memory.read access) with
      | none => .unavailable access
      | some bytes => .ready access bytes (eventsForAccess .read access bytes)

inductive WriteAttempt where
  | ready (access : ResolvedAccess) (memory : MemoryState) (events : List MemoryEvent)
  | fault (error : ResolutionError)
  | shapeMismatch
  | unsupportedStage

noncomputable def writeStage (profile : ArchitectureProfile) (config : SystemConfig)
    (cpu : CPUState) (pages : PageMap) (memory : MemoryState) (spec : Spec)
    (control : Control) (sourceSegment : SegmentReg) (stage : Stage)
    (bytes : List Byte) : WriteAttempt :=
  match resolveMemoryStage profile config cpu pages spec control sourceSegment stage with
  | none => .unsupportedStage
  | some (.error error) => .fault error
  | some (.ok access) =>
      match memory.write access bytes with
      | none => .shapeMismatch
      | some after => .ready access after (eventsForAccess .write access bytes)

structure AccumulatorUpdate where
  width : Nat
  value : IWord

structure Ready where
  memory : MemoryState
  events : List MemoryEvent
  status : ArithmeticFlags
  accumulator : Option AccumulatorUpdate

inductive Preparation where
  | skipped
  | ready (value : Ready)
  /-- `priorReads` occurred in data-dependency order; event commit is not claimed here. -/
  | fault (error : ResolutionError) (priorReads : List MemoryEvent)
  | unavailable (priorReads : List MemoryEvent)
  | unsupportedKind
  | shapeMismatch

private def readyWithoutAccumulator (memory : MemoryState) (events : List MemoryEvent)
    (status : ArithmeticFlags) : Preparation :=
  .ready { memory, events, status, accumulator := none }

noncomputable def prepareMemoryIteration (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (cpu : CPUState) (memory : MemoryState)
    (spec : Spec) (sourceSegment : SegmentReg) : Preparation :=
  let control := Control.ofCPUState cpu
  if !shouldExecute spec control then .skipped
  else match spec.kind with
  | .ins | .outs => .unsupportedKind
  | .movs =>
      match readStage profile config cpu pages memory spec control sourceSegment .sourceRead with
      | .fault error => .fault error []
      | .unavailable _ => .unavailable []
      | .unsupportedStage => .unsupportedKind
      | .ready _ bytes readEvents =>
          match writeStage profile config cpu pages memory spec control sourceSegment
              .destinationWrite bytes with
          | .fault error => .fault error readEvents
          | .shapeMismatch => .shapeMismatch
          | .unsupportedStage => .unsupportedKind
          | .ready _ after writeEvents =>
              readyWithoutAccumulator after (readEvents ++ writeEvents) control.status
  | .lods =>
      match readStage profile config cpu pages memory spec control sourceSegment .sourceRead with
      | .fault error => .fault error []
      | .unavailable _ => .unavailable []
      | .unsupportedStage => .unsupportedKind
      | .ready _ bytes events => .ready {
          memory
          events
          status := control.status
          accumulator := some { width := spec.element.bits, value := bytesToWord bytes }
        }
  | .stos =>
      let bytes := wordToBytes cpu.rax spec.element.bytes
      match writeStage profile config cpu pages memory spec control sourceSegment
          .destinationWrite bytes with
      | .fault error => .fault error []
      | .shapeMismatch => .shapeMismatch
      | .unsupportedStage => .unsupportedKind
      | .ready _ after events => readyWithoutAccumulator after events control.status
  | .cmps =>
      match readStage profile config cpu pages memory spec control sourceSegment .sourceRead with
      | .fault error => .fault error []
      | .unavailable _ => .unavailable []
      | .unsupportedStage => .unsupportedKind
      | .ready _ sourceBytes sourceEvents =>
          match readStage profile config cpu pages memory spec control sourceSegment
              .destinationRead with
          | .fault error => .fault error sourceEvents
          | .unavailable _ => .unavailable sourceEvents
          | .unsupportedStage => .unsupportedKind
          | .ready _ destinationBytes destinationEvents =>
              let status := (comparisonResult spec.element
                (bytesToWord sourceBytes) (bytesToWord destinationBytes)).flags
              readyWithoutAccumulator memory (sourceEvents ++ destinationEvents) status
  | .scas =>
      match readStage profile config cpu pages memory spec control sourceSegment
          .destinationRead with
      | .fault error => .fault error []
      | .unavailable _ => .unavailable []
      | .unsupportedStage => .unsupportedKind
      | .ready _ destinationBytes events =>
          let status := (comparisonResult spec.element cpu.rax
            (bytesToWord destinationBytes)).flags
          readyWithoutAccumulator memory events status

/-! General GPR write relation, with legacy upper-half nondeterminism. -/
def gprWriteAllowed (mode : OperatingMode) (width : Nat)
    (before value after : IWord) : Prop :=
  ∀ bit : Fin 64,
    if bit.val < width then after bit = value bit
    else if mode = .long64 ∧ width = 32 then after bit = false
    else if mode = .long64 ∨ bit.val < 32 then after bit = before bit
    else True

def CPUDataStateAllowed (before : CPUState) (ready : Ready) (after : CPUState) : Prop :=
  after.rip = before.rip ∧
  after.rflags = applyStatusFlags before.rflags ready.status ∧
  after.segments = before.segments ∧ after.x87 = before.x87 ∧
  after.vectors = before.vectors ∧ after.kMask = before.kMask ∧
  after.mxcsr = before.mxcsr ∧ after.execution = before.execution ∧
  (∀ register : Fin 16, register ≠ GPR.toFin .rax -> after.gpr register = before.gpr register) ∧
  match ready.accumulator with
  | none => after.gpr (GPR.toFin .rax) = before.gpr (GPR.toFin .rax)
  | some update => gprWriteAllowed before.execution.mode update.width
      (before.gpr (GPR.toFin .rax)) update.value (after.gpr (GPR.toFin .rax))

inductive Execution where
  /-- Body effects applied; RIP/fallthrough/retirement is not performed here. -/
  | bodyApplied (cpu : CPUState) (memory : MemoryState) (events : List MemoryEvent)
      (completedIterations : Nat)
  | inProgress (cpu : CPUState) (memory : MemoryState) (events : List MemoryEvent)
      (continuation : Continuation)
  | fault (error : ResolutionError) (cpu : CPUState) (memory : MemoryState)
      (priorReads : List MemoryEvent) (restart : Restart)
  | unavailable (cpu : CPUState) (memory : MemoryState)
      (priorReads : List MemoryEvent) (completedIterations : Nat)
  | unsupported
  | shapeMismatch

def Finish (beforeCPU : CPUState) (beforeMemory : MemoryState)
    (continuation : Continuation) (preparation : Preparation)
    (dataCPU : CPUState) (afterControl : Control) (result : Execution) : Prop :=
  match preparation with
  | .skipped => result = .bodyApplied beforeCPU beforeMemory [] continuation.completedIterations
  | .unsupportedKind => result = .unsupported
  | .shapeMismatch => result = .shapeMismatch
  | .fault error priorReads => result = .fault error beforeCPU beforeMemory priorReads
      (restartAtBoundary beforeCPU.rip continuation)
  | .unavailable priorReads => result = .unavailable beforeCPU beforeMemory priorReads
      continuation.completedIterations
  | .ready ready =>
      CPUDataStateAllowed beforeCPU ready dataCPU ∧
      commitControlAllowed continuation.spec continuation.control ready.status afterControl ∧
      let finalCPU := applyControlRegisters dataCPU afterControl
      let completed := continuation.completedIterations + 1
      if shouldContinue continuation.spec.repeatMode afterControl.count
          continuation.spec.addressSize afterControl.status.zf then
        result = .inProgress finalCPU ready.memory ready.events {
          continuation with
            control := afterControl
            stage := firstStage continuation.spec.kind
            completedIterations := completed }
      else result = .bodyApplied finalCPU ready.memory ready.events completed

theorem fault_preserves_cpu_memory (beforeCPU : CPUState) (beforeMemory : MemoryState)
    (continuation : Continuation) (error : ResolutionError) (reads : List MemoryEvent)
    (dataCPU : CPUState) (afterControl : Control) (result : Execution)
    (finished : Finish beforeCPU beforeMemory continuation (.fault error reads)
      dataCPU afterControl result) :
    result = .fault error beforeCPU beforeMemory reads
      (restartAtBoundary beforeCPU.rip continuation) := by
  exact finished

theorem unavailable_preserves_cpu_memory (beforeCPU : CPUState)
    (beforeMemory : MemoryState) (continuation : Continuation)
    (reads : List MemoryEvent) (dataCPU : CPUState) (afterControl : Control)
    (result : Execution)
    (finished : Finish beforeCPU beforeMemory continuation (.unavailable reads)
      dataCPU afterControl result) :
    result = .unavailable beforeCPU beforeMemory reads
      continuation.completedIterations := by
  exact finished

theorem ready_can_finish (beforeCPU : CPUState) (beforeMemory : MemoryState)
    (continuation : Continuation) (ready : Ready) (dataCPU : CPUState)
    (afterControl : Control)
    (dataAllowed : CPUDataStateAllowed beforeCPU ready dataCPU)
    (controlAllowed : commitControlAllowed continuation.spec continuation.control
      ready.status afterControl) :
    ∃ result, Finish beforeCPU beforeMemory continuation (.ready ready)
      dataCPU afterControl result := by
  let finalCPU := applyControlRegisters dataCPU afterControl
  let completed := continuation.completedIterations + 1
  by_cases continues : shouldContinue continuation.spec.repeatMode afterControl.count
      continuation.spec.addressSize afterControl.status.zf = true
  · refine ⟨.inProgress finalCPU ready.memory ready.events {
        continuation with
          control := afterControl
          stage := firstStage continuation.spec.kind
          completedIterations := completed }, ?_⟩
    simp [Finish, dataAllowed, controlAllowed, continues, finalCPU, completed]
  · refine ⟨.bodyApplied finalCPU ready.memory ready.events completed, ?_⟩
    simp [Finish, dataAllowed, controlAllowed, continues, finalCPU, completed]

theorem non_accumulator_frames_rax (before : CPUState) (ready : Ready) (after : CPUState)
    (none : ready.accumulator = none) (allowed : CPUDataStateAllowed before ready after) :
    after.rax = before.rax := by
  have := allowed.2.2.2.2.2.2.2.2.2
  simp [none] at this
  exact this

namespace Source

/-!
Independent one-based transcription of TLA+ `BytesToWord`. This proves the
zero/one-based bit-index shift inside Lean; it does not parse TLA+.
-/

abbrev Index := { index : Nat // 1 ≤ index ∧ index ≤ 64 }
abbrev Word := Index -> Bool

def fromIndex (bit : Index) : Fin 64 :=
  ⟨bit.val - 1, by have := bit.property; omega⟩

def encode (word : IWord) : Word := fun bit => word (fromIndex bit)

/-- Direct one-based formula: sequence byte index is `(bit-1)/8`; byte bit is `(bit-1)%8`. -/
def bytesToWord (bytes : List Byte) : Word := fun bit =>
  match bytes[(bit.val - 1) / 8]? with
  | some byte => byte ⟨(bit.val - 1) % 8, Nat.mod_lt _ (by decide)⟩
  | none => false

theorem bytesToWord_correspondence (bytes : List Byte) :
    encode (AMD64.StringsMemory.bytesToWord bytes) = Source.bytesToWord bytes := by
  funext bit
  have positive := bit.property.1
  simp only [encode, AMD64.StringsMemory.bytesToWord, Source.bytesToWord]
  rfl

end Source
end AMD64.StringsMemory
