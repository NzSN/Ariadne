import AMD64.SystemState
import AMD64.MachineAccess
import AMD64.IntegerSemantics
import Std

/-!
Concrete MONITORX one-byte access and MWAITX wake protocol.

Authority: AMD APM Volume 3 revision 3.38 PDF pages 280-281, 310-311,
and CPUID function 5 on PDF page 675.  MONITORX delegates segmentation,
canonicality, paging and permission checks to `MachineAccess.resolveSpan`.
-/

namespace AMD64.Monitor

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics
open AMD64.MachineAccess

structure Range where
  bytes : List Address

def Range.Valid (range : Range) (target : Address) (minimum maximum : Nat) : Prop :=
  minimum > 0 ∧ minimum ≤ range.bytes.length ∧ range.bytes.length ≤ maximum ∧
  target ∈ range.bytes ∧ range.bytes.Pairwise (· ≠ ·)

structure Profile where
  monitorx : Bool
  interruptBreak : Bool
  minimumLineBytes : Nat
  maximumLineBytes : Nat
  rangeFor : Address -> Range

def Profile.Valid (profile : Profile) : Prop :=
  0 < profile.minimumLineBytes ∧
  profile.minimumLineBytes ≤ profile.maximumLineBytes ∧
  ∀ target, (profile.rangeFor target).Valid target
    profile.minimumLineBytes profile.maximumLineBytes

structure State where
  range : Option Range
  pending : Bool

def State.Valid (state : State) : Prop := state.pending = state.range.isSome

inductive Fault where
  | ud
  | gp
  | memory (faults : List IndexedFault)

inductive MonitorOutcome where
  | armed (cpu : CPUState) (monitor : State) (span : ResolvedSpan)
  | fault (kind : Fault) (cpu : CPUState) (monitor : State)
  | sourceUnspecified (cpu : CPUState) (monitor : State) (candidate : Range)
  | modelingUnavailable (reason : String) (cpu : CPUState) (monitor : State)

def request (cpu : CPUState) (addressSize : AddressSize) (segment : SegmentReg)
    (memoryType : AMD64.MemoryTypes.Resolution) : SpanRequest := {
  address := {
    rawEffective := cpu.rax
    addressSize
    segment
    access := { kind := .read }
    byteCount := 1
    alignmentBits := 0
  }
  memoryType
}

noncomputable def bindResolved (profile : Profile) (cpu : CPUState)
    (before : State) (span : ResolvedSpan) : MonitorOutcome := by
  classical
  let candidate := profile.rangeFor span.access.linear
  exact if ¬candidate.Valid span.access.linear profile.minimumLineBytes
      profile.maximumLineBytes then
    .modelingUnavailable "invalid processor monitor geometry" cpu before
  else match span.memoryType with
    | .resolved .wb => .armed cpu { range := some candidate, pending := true } span
    | .resolved _ => .sourceUnspecified cpu before candidate
    | .undefinedCombination =>
        .modelingUnavailable "undefined effective memory type" cpu before
    | .unsupportedProfile =>
        .modelingUnavailable "unsupported memory-type profile" cpu before
    | .unknownConfiguration =>
        .modelingUnavailable "memory type unavailable" cpu before

noncomputable def ExecuteMONITORX (architecture : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (profile : Profile)
    (addressSize : AddressSize) (segment : SegmentReg)
    (memoryType : AMD64.MemoryTypes.Resolution) (cpu : CPUState)
    (before : State) : MonitorOutcome := by
  classical
  exact if !profile.monitorx then .fault .ud cpu before
  else if unsignedValue cpu.rcx 32 ≠ 0 then .fault .gp cpu before
  else
    match resolveSpan architecture config pages cpu
      (request cpu addressSize segment memoryType) with
    | .faultCandidates faults => .fault (.memory faults) cpu before
    | .resolved span => bindResolved profile cpu before span

def overlaps (range : Range) (committedLinearBytes : List Address) : Prop :=
  ∃ address, address ∈ range.bytes ∧ address ∈ committedLinearBytes

noncomputable def observeCommittedStore (before : State)
    (committedLinearBytes : List Address) : State := by
  classical
  exact match before.range with
  | some range => if decide (overlaps range committedLinearBytes)
      then { range := none, pending := false } else before
  | none => before

inductive WakeCause where
  | matchingStore (committedLinearBytes : List Address)
  | timerExpired (elapsedP0Clocks : Nat)
  | interrupt (unmasked : Bool)
  | nmi | smi | init | reset | farTransfer

structure WakeObservation where
  cause : WakeCause

def wakeAllowed (profile : Profile) (cpu : CPUState) (monitor : State)
    (observation : WakeObservation) : Prop :=
  let ecx := unsignedValue cpu.rcx 32
  let timerEnabled := ecx.testBit 1 && unsignedValue cpu.rbx 32 ≠ 0
  match observation.cause with
  | .matchingStore bytes => monitor.pending ∧
      ∃ range ∈ monitor.range, overlaps range bytes
  | .timerExpired elapsed => timerEnabled ∧ unsignedValue cpu.rbx 32 ≤ elapsed
  | .interrupt unmasked => unmasked ∨ (ecx.testBit 0 ∧ profile.interruptBreak)
  | .nmi | .smi | .init | .reset | .farTransfer => True

inductive WaitOutcome where
  | woke (cpu : CPUState) (monitor : State) (observation : WakeObservation)
  | fault (kind : Fault) (cpu : CPUState) (monitor : State)
  | modelingUnavailable (reason : String) (cpu : CPUState) (monitor : State)

noncomputable def ExecuteMWAITX (profile : Profile) (cpu : CPUState) (before : State)
    (observation : Option WakeObservation) : WaitOutcome := by
  classical
  exact let ecx := unsignedValue cpu.rcx 32
  if !profile.monitorx then .fault .ud cpu before
  else if ecx / 4 ≠ 0 || (ecx.testBit 0 && !profile.interruptBreak) then
    .fault .gp cpu before
  else match observation with
  | none => .modelingUnavailable "wake observation unavailable" cpu before
  | some observed => if decide (wakeAllowed profile cpu before observed)
      then .woke cpu { range := none, pending := false } observed
      else .modelingUnavailable "wake observation violates MWAITX contract" cpu before

theorem monitor_request_is_one_byte (cpu : CPUState) (addressSize : AddressSize)
    (segment : SegmentReg) (memoryType : AMD64.MemoryTypes.Resolution) :
    (request cpu addressSize segment memoryType).address.byteCount = 1 := rfl

theorem wait_frames_cpu_on_wake (profile : Profile) (cpu after : CPUState)
    (before monitor : State) (observation : WakeObservation)
    (result : ExecuteMWAITX profile cpu before (some observation) =
      .woke after monitor observation) :
    after = cpu := by
  classical
  simp only [ExecuteMWAITX] at result
  split at result <;> simp_all
  split at result <;> simp_all
  split at result <;> simp_all

end AMD64.Monitor
