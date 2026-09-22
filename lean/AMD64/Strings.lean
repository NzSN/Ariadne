import AMD64.ArchitecturalState
import AMD64.Memory
import AMD64.Exceptions
import AMD64.IntegerSemantics
import AMD64.IntegerStateAdapter
import Std

/-!
Control and staging foundation for AMD64 string instructions.

Authority: AMD APM Volume 3, publication 24594 revision 3.38, section 1.2.6
and the reference entries CMPS, INS, LODS, MOVS, OUTS, SCAS, and STOS.

This module proves count, pointer, repeat-condition, stage-order, and restart
properties. It does not manufacture memory or I/O outcomes. A stage names the
next required architectural operation; the memory/I/O layer must discharge it.
Only a `commitReady` iteration may update pointers/count and become a completed
iteration. Generic effect-prefix length remains separate from this iteration
count because one iteration can emit several effects.
-/

namespace AMD64.Strings

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics

inductive Kind where
  | cmps | ins | lods | movs | outs | scas | stos
  deriving DecidableEq, Repr

inductive RepeatMode where
  | none | rep | repe | repne
  deriving DecidableEq, Repr

inductive ElementWidth where
  | byte | word | dword | qword
  deriving DecidableEq, Repr

def ElementWidth.bits : ElementWidth -> Nat
  | .byte => 8 | .word => 16 | .dword => 32 | .qword => 64

def ElementWidth.bytes : ElementWidth -> Nat
  | .byte => 1 | .word => 2 | .dword => 4 | .qword => 8

def addressBits : AddressSize -> Nat
  | .bits16 => 16 | .bits32 => 32 | .bits64 => 64

def Kind.usesSourcePointer : Kind -> Bool
  | .cmps | .lods | .movs | .outs => true
  | _ => false

def Kind.usesDestinationPointer : Kind -> Bool
  | .cmps | .ins | .movs | .scas | .stos => true
  | _ => false

def Kind.updatesStatusFlags : Kind -> Bool
  | .cmps | .scas => true
  | _ => false

def Kind.usesIO : Kind -> Bool
  | .ins | .outs => true
  | _ => false

def RepeatMode.ValidFor : RepeatMode -> Kind -> Prop
  | .none, _ => True
  | .rep, .ins | .rep, .lods | .rep, .movs | .rep, .outs | .rep, .stos => True
  | .repe, .cmps | .repe, .scas | .repne, .cmps | .repne, .scas => True
  | _, _ => False

structure Spec where
  kind : Kind
  element : ElementWidth
  addressSize : AddressSize
  repeatMode : RepeatMode
  mode : OperatingMode
  deriving DecidableEq, Repr

def Spec.Valid (spec : Spec) : Prop :=
  spec.repeatMode.ValidFor spec.kind ∧
  (spec.addressSize = .bits64 -> spec.mode = .long64) ∧
  (spec.mode = .long64 -> spec.addressSize ≠ .bits16) ∧
  (spec.element = .qword -> spec.mode = .long64) ∧
  (spec.kind.usesIO = true -> spec.element ≠ .qword)

structure Control where
  source : IWord
  destination : IWord
  count : IWord
  df : Bool
  status : ArithmeticFlags

def Control.ofCPUState (state : CPUState) : Control := {
  source := state.rsi
  destination := state.rdi
  count := state.rcx
  df := state.rflags.df
  status := projectStatusFlags state.rflags
}

/-!
Address-sized GPR writes are relational outside 64-bit mode. Volume 1 section
3.4.5 says bits 63:32 are inaccessible and undefined in compatibility/legacy
modes and are not preserved across leaving 64-bit mode. A 16-bit write still
preserves observable bits 31:16. In 64-bit mode a 32-bit write clears 63:32.
-/
def addressWriteAllowed (mode : OperatingMode) (size : AddressSize)
    (before value after : IWord) : Prop :=
  ∀ bit : Fin 64,
    if bit.val < addressBits size then after bit = value bit
    else if mode = .long64 ∧ size = .bits32 then after bit = false
    else if size = .bits16 ∧ bit.val < 32 then after bit = before bit
    else True

def advancePointerAllowed (mode : OperatingMode) (size : AddressSize)
    (element : ElementWidth) (df : Bool) (before after : IWord) : Prop :=
  let delta := wordOfNat element.bytes
  let low := if df then subWord before delta false (addressBits size)
             else addWord before delta false (addressBits size)
  addressWriteAllowed mode size before low after

def decrementCountAllowed (mode : OperatingMode) (size : AddressSize)
    (before after : IWord) : Prop :=
  addressWriteAllowed mode size before
    (subWord before one false (addressBits size)) after

def repeatCountZero (spec : Spec) (control : Control) : Bool :=
  isZero control.count (addressBits spec.addressSize)

def shouldExecute (spec : Spec) (control : Control) : Bool :=
  spec.repeatMode == .none || !repeatCountZero spec control

/-- Continuation condition after one completed iteration and count decrement. -/
def shouldContinue (repeatMode : RepeatMode) (countAfter : IWord) (addressSize : AddressSize)
    (zfAfter : Bool) : Bool :=
  let nonzero := !isZero countAfter (addressBits addressSize)
  match repeatMode with
  | .none => false
  | .rep => nonzero
  | .repe => nonzero && zfAfter
  | .repne => nonzero && !zfAfter

/-- Relational control commit for one successful iteration. -/
def commitControlAllowed (spec : Spec) (before : Control)
    (statusAfter : ArithmeticFlags) (after : Control) : Prop :=
  (if spec.kind.usesSourcePointer then
      advancePointerAllowed spec.mode spec.addressSize spec.element before.df
        before.source after.source
    else after.source = before.source) ∧
  (if spec.kind.usesDestinationPointer then
      advancePointerAllowed spec.mode spec.addressSize spec.element before.df
        before.destination after.destination
    else after.destination = before.destination) ∧
  (if spec.repeatMode = .none then after.count = before.count
    else decrementCountAllowed spec.mode spec.addressSize before.count after.count) ∧
  after.df = before.df ∧
  after.status = if spec.kind.updatesStatusFlags then statusAfter else before.status

/-- CMPS uses source minus destination; SCAS supplies accumulator as `left`. -/
def comparisonResult (element : ElementWidth) (left right : IWord) : ArithmeticResult :=
  subResult left right false element.bits

def applyComparisonFlags (before : RFlags) (element : ElementWidth)
    (left right : IWord) : RFlags :=
  applyStatusFlags before (comparisonResult element left right).flags

theorem comparison_zf_matches_control (before : RFlags) (element : ElementWidth)
    (left right : IWord) :
    (applyComparisonFlags before element left right).zf =
      (comparisonResult element left right).flags.zf := by
  rfl

theorem comparison_preserves_df (before : RFlags) (element : ElementWidth)
    (left right : IWord) :
    (applyComparisonFlags before element left right).df = before.df := by
  exact apply_status_preserves_df before (comparisonResult element left right).flags

/-- Apply already-computed pointer/count storage without changing unrelated GPRs. -/
def writeNamedGPR (bank : Fin 16 -> IWord) (register : GPR) (value : IWord) :
    Fin 16 -> IWord :=
  updateAt bank register.toFin value

def applyControlRegisters (before : CPUState) (control : Control) : CPUState :=
  let sourceWritten := writeNamedGPR before.gpr GPR.rsi control.source
  let destinationWritten := writeNamedGPR sourceWritten GPR.rdi control.destination
  let countWritten := writeNamedGPR destinationWritten GPR.rcx control.count
  { before with gpr := countWritten }

def applyControlState (before : CPUState) (control : Control) : CPUState :=
  { applyControlRegisters before control with
    rflags := applyStatusFlags before.rflags control.status }

@[simp] theorem apply_control_rcx (before : CPUState) (control : Control) :
    (applyControlRegisters before control).rcx = control.count := by
  simp [applyControlRegisters, writeNamedGPR, CPUState.rcx, CPUState.gprValue,
    updateAt, GPR.toFin, GPR.index]

@[simp] theorem apply_control_rsi (before : CPUState) (control : Control) :
    (applyControlRegisters before control).rsi = control.source := by
  simp [applyControlRegisters, writeNamedGPR, CPUState.rsi, CPUState.gprValue,
    updateAt, GPR.toFin, GPR.index]

@[simp] theorem apply_control_rdi (before : CPUState) (control : Control) :
    (applyControlRegisters before control).rdi = control.destination := by
  simp [applyControlRegisters, writeNamedGPR, CPUState.rdi, CPUState.gprValue,
    updateAt, GPR.toFin, GPR.index]

inductive Stage where
  | sourceRead
  | destinationRead
  | ioRead
  | accumulatorWrite
  | destinationWrite
  | ioWrite
  | flagsWrite
  | commitReady
  deriving DecidableEq, Repr

def firstStage : Kind -> Stage
  | .cmps | .lods | .movs | .outs => .sourceRead
  | .ins => .ioRead
  | .scas => .destinationRead
  | .stos => .destinationWrite

def nextStage (kind : Kind) : Stage -> Option Stage
  | .sourceRead => match kind with
      | .cmps => some .destinationRead
      | .lods => some .accumulatorWrite
      | .movs => some .destinationWrite
      | .outs => some .ioWrite
      | _ => none
  | .destinationRead => match kind with
      | .cmps | .scas => some .flagsWrite
      | _ => none
  | .ioRead => if kind = .ins then some .destinationWrite else none
  | .accumulatorWrite => if kind = .lods then some .commitReady else none
  | .destinationWrite => if kind = .movs ∨ kind = .ins ∨ kind = .stos
      then some .commitReady else none
  | .ioWrite => if kind = .outs then some .commitReady else none
  | .flagsWrite => if kind = .cmps ∨ kind = .scas then some .commitReady else none
  | .commitReady => none

/-!
Constrained memory request for a memory stage. Source override legality is
I2-owned. Stages express data/effect dependencies; they do not choose the
priority of pure address prechecks, which may be discharged before a data
operation by the eventual instruction binding.
-/
def memoryRequest (spec : Spec) (control : Control) (sourceSegment : SegmentReg) :
    Stage -> Option AddressRequest
  | .sourceRead => if spec.kind.usesSourcePointer then some {
      rawEffective := control.source
      addressSize := spec.addressSize
      segment := sourceSegment
      access := { kind := .read }
      byteCount := spec.element.bytes
    } else none
  | .destinationRead => if spec.kind = .cmps ∨ spec.kind = .scas then some {
      rawEffective := control.destination
      addressSize := spec.addressSize
      segment := .es
      access := { kind := .read }
      byteCount := spec.element.bytes
    } else none
  | .destinationWrite => if spec.kind = .movs ∨ spec.kind = .ins ∨ spec.kind = .stos
      then some {
        rawEffective := control.destination
        addressSize := spec.addressSize
        segment := .es
        access := { kind := .write }
        byteCount := spec.element.bytes
      } else none
  | _ => none

/-- Bind a memory stage to M2's real segment/page/alignment resolver. -/
noncomputable def resolveMemoryStage (profile : ArchitectureProfile) (config : SystemConfig)
    (cpu : CPUState) (pages : PageMap) (spec : Spec) (control : Control)
    (sourceSegment : SegmentReg) (stage : Stage) :
    Option (Except ResolutionError ResolvedAccess) :=
  (memoryRequest spec control sourceSegment stage).map fun request =>
    resolveAccess profile config cpu pages request

theorem io_stages_have_no_fake_memory_request (spec : Spec) (control : Control)
    (segment : SegmentReg) :
    memoryRequest spec control segment .ioRead = none ∧
    memoryRequest spec control segment .ioWrite = none := by
  simp [memoryRequest]

structure Continuation where
  spec : Spec
  control : Control
  stage : Stage
  completedIterations : Nat

inductive Boundary where
  /-- String body finished; RIP/fallthrough/retirement is composed later. -/
  | bodyApplied (control : Control) (completedIterations : Nat)
  | inProgress (continuation : Continuation)

def begin (spec : Spec) (control : Control) : Boundary :=
  if shouldExecute spec control then
    .inProgress { spec, control, stage := firstStage spec.kind, completedIterations := 0 }
  else .bodyApplied control 0

def advanceStage (continuation : Continuation) : Option Continuation := do
  let stage <- nextStage continuation.spec.kind continuation.stage
  pure { continuation with stage }

/--
Commit one fully discharged iteration. `completedIterations` increases by one;
no generic effect count occurs in this type.
-/
def commitIteration (continuation : Continuation) (statusAfter : ArithmeticFlags)
    (afterControl : Control) (after : Boundary) : Prop :=
  continuation.stage = .commitReady ∧
  commitControlAllowed continuation.spec continuation.control statusAfter afterControl ∧
  let completed := continuation.completedIterations + 1
  if shouldContinue continuation.spec.repeatMode afterControl.count
      continuation.spec.addressSize afterControl.status.zf then
    after = .inProgress {
      continuation with
        control := afterControl
        stage := firstStage continuation.spec.kind
        completedIterations := completed }
  else after = .bodyApplied afterControl completed

structure Restart where
  faultingIP : Address
  control : Control
  completedIterations : Nat

/-- Interruption/fault restart records only already committed iterations. -/
def restartAtBoundary (ip : Address) (continuation : Continuation) : Restart := {
  faultingIP := ip
  control := continuation.control
  completedIterations := continuation.completedIterations
}

def remainingIterations (continuation : Continuation) : Nat :=
  unsignedValue continuation.control.count (addressBits continuation.spec.addressSize)

/-- Bind a resolved memory fault to the corrected independent-count outcome contract. -/
def accessFaultOutcome (afterPrefix : State) (faultingIP : Address)
    (fault : AccessFault) (effects : List Effect) (committedEffects : Nat)
    (continuation : Continuation) : AMD64.Exceptions.Outcome State Effect :=
  let mapped := AMD64.Exceptions.ofAccessFault fault
  AMD64.Exceptions.prefixFault afterPrefix faultingIP mapped.1 mapped.2.1 mapped.2.2
    effects committedEffects continuation.completedIterations
    (remainingIterations continuation)

theorem access_fault_keeps_effect_and_iteration_counts_independent
    (afterPrefix : State) (ip : Address) (fault : AccessFault)
    (effects : List Effect) (committedEffects : Nat) (continuation : Continuation) :
    (accessFaultOutcome afterPrefix ip fault effects committedEffects continuation).committed =
      committedEffects ∧
    ((accessFaultOutcome afterPrefix ip fault effects committedEffects continuation).progress.map
      (fun restart => restart.completedIterations)) =
      some continuation.completedIterations := by
  simp [accessFaultOutcome, AMD64.Exceptions.prefixFault]

theorem no_repeat_executes_with_zero_count (spec : Spec) (control : Control)
    (noRepeat : spec.repeatMode = .none) : shouldExecute spec control = true := by
  simp [shouldExecute, noRepeat]

theorem repeated_zero_count_skips (spec : Spec) (control : Control)
    (repeated : spec.repeatMode ≠ .none) (zero : repeatCountZero spec control = true) :
    shouldExecute spec control = false := by
  simp [shouldExecute, repeated, zero]

theorem repe_stops_when_zf_clear (count : IWord) (size : AddressSize) :
    shouldContinue .repe count size false = false := by
  simp [shouldContinue]

theorem repne_stops_when_zf_set (count : IWord) (size : AddressSize) :
    shouldContinue .repne count size true = false := by
  simp [shouldContinue]

theorem address32_long64_zeroes_high (before value after : IWord)
    (allowed : addressWriteAllowed .long64 .bits32 before value after)
    (bit : Fin 64) (high : 32 ≤ bit.val) : after bit = false := by
  simpa [addressWriteAllowed, addressBits, show ¬ bit.val < 32 by omega]
    using allowed bit

theorem address16_preserves_observable_mid (mode : OperatingMode)
    (before value after : IWord)
    (allowed : addressWriteAllowed mode .bits16 before value after)
    (bit : Fin 64) (low : 16 ≤ bit.val) (high : bit.val < 32) :
    after bit = before bit := by
  simpa [addressWriteAllowed, addressBits, show ¬ bit.val < 16 by omega, high]
    using allowed bit

theorem nonrepeat_preserves_count (spec : Spec) (before : Control)
    (status : ArithmeticFlags) (after : Control)
    (allowed : commitControlAllowed spec before status after)
    (noRepeat : spec.repeatMode = .none) : after.count = before.count := by
  simpa [noRepeat] using allowed.2.2.1

theorem kind_without_source_preserves_source (spec : Spec) (before : Control)
    (status : ArithmeticFlags) (after : Control)
    (allowed : commitControlAllowed spec before status after)
    (unused : spec.kind.usesSourcePointer = false) :
    after.source = before.source := by
  simpa [commitControlAllowed, unused] using allowed.1

theorem kind_without_destination_preserves_destination (spec : Spec)
    (before : Control) (status : ArithmeticFlags) (after : Control)
    (allowed : commitControlAllowed spec before status after)
    (unused : spec.kind.usesDestinationPointer = false) :
    after.destination = before.destination := by
  simpa [commitControlAllowed, unused] using allowed.2.1

theorem movs_stage_order :
    nextStage .movs .sourceRead = some .destinationWrite ∧
    nextStage .movs .destinationWrite = some .commitReady := by decide

theorem ins_stage_order :
    nextStage .ins .ioRead = some .destinationWrite ∧
    nextStage .ins .destinationWrite = some .commitReady := by decide

theorem outs_stage_order :
    nextStage .outs .sourceRead = some .ioWrite ∧
    nextStage .outs .ioWrite = some .commitReady := by decide

theorem restart_preserves_completed_control (ip : Address) (continuation : Continuation) :
    (restartAtBoundary ip continuation).control = continuation.control ∧
    (restartAtBoundary ip continuation).completedIterations =
      continuation.completedIterations := by
  constructor <;> rfl

namespace Source

/-!
Reviewed transcription of selected control operators in
`Specs/AMD64Strings.tla`. These theorems check the typed transcription; they do
not parse TLA+ or prove a general translation.
-/

def shouldContinue (repeatMode : RepeatMode) (countAfter : IWord)
    (addressSize : AddressSize) (zfAfter : Bool) : Bool :=
  let nonzero := !isZero countAfter (addressBits addressSize)
  match repeatMode with
  | .none => false
  | .rep => nonzero
  | .repe => nonzero && zfAfter
  | .repne => nonzero && !zfAfter

theorem shouldContinue_correspondence (repeatMode : RepeatMode) (count : IWord)
    (size : AddressSize) (zf : Bool) :
    AMD64.Strings.shouldContinue repeatMode count size zf =
      Source.shouldContinue repeatMode count size zf := by
  rfl

def firstStage : Kind -> Stage
  | .cmps | .lods | .movs | .outs => .sourceRead
  | .ins => .ioRead
  | .scas => .destinationRead
  | .stos => .destinationWrite

theorem firstStage_correspondence (kind : Kind) :
    AMD64.Strings.firstStage kind = Source.firstStage kind := by
  cases kind <;> rfl

end Source

end AMD64.Strings
