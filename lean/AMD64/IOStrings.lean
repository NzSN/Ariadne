import AMD64.IO
import AMD64.StringsMemory
import Std

/-!
Successful INS/OUTS binding to the explicit IO environment and C4 control.

Mixed memory/permission/device failure ordering is retained as `orderingOpen`
unless the result is source-independent. No device rule can mutate CPU state.
-/

namespace AMD64.IOStrings

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics
open AMD64.Strings
open AMD64.StringsMemory
open AMD64.IO

inductive Effect where
  | memory (event : MemoryEvent)
  | io (event : IOEvent)

inductive ModelingReason where
  | capturedSourceUnavailable
  | permissionUnavailable
  | deviceUnavailable
  | portBoundaryUnspecified
  | memoryWriteShapeMismatch
  deriving DecidableEq, Repr

inductive OrderingReason where
  | permissionVersusMemoryFault
  | waitingForPriorWrites
  deriving DecidableEq, Repr

inductive Execution where
  | bodyApplied (cpu : CPUState) (memory : MemoryState) (effects : List Effect)
      (completedIterations : Nat)
  | inProgress (cpu : CPUState) (memory : MemoryState) (effects : List Effect)
      (continuation : Continuation)
  | fault (error : ResolutionError) (cpu : CPUState) (memory : MemoryState)
      (effects : List Effect) (restart : Restart)
  | modelingUnavailable (reason : ModelingReason) (cpu : CPUState)
      (memory : MemoryState) (priorEffects : List Effect)
  | orderingOpen (reason : OrderingReason) (cpu : CPUState)
      (memory : MemoryState) (candidateEffects : List Effect)
      (unresolvedEffectKinds : List String)

def ioWidth : ElementWidth -> Option Width
  | .byte => some .byte
  | .word => some .word
  | .dword => some .dword
  | .qword => none

def wrapMemoryEffects (events : List MemoryEvent) : List Effect :=
  events.map .memory

/-- Shared pointer/count commit after a completed I/O and any memory effect. -/
def FinishControl (beforeCPU : CPUState) (afterMemory : MemoryState)
    (continuation : Continuation) (effects : List Effect) (afterControl : Control)
    (result : Execution) : Prop :=
  commitControlAllowed continuation.spec continuation.control
    continuation.control.status afterControl ∧
  let finalCPU := applyControlRegisters beforeCPU afterControl
  let completed := continuation.completedIterations + 1
  if shouldContinue continuation.spec.repeatMode afterControl.count
      continuation.spec.addressSize afterControl.status.zf then
    result = .inProgress finalCPU afterMemory effects {
      continuation with
        control := afterControl
        stage := firstStage continuation.spec.kind
        completedIterations := completed }
  else result = .bodyApplied finalCPU afterMemory effects completed

structure OUTSReady where
  request : PortRequest
  memoryEvents : List MemoryEvent

inductive OUTSPreparation where
  | ready (value : OUTSReady)
  | skipped
  | fault (error : ResolutionError)
  | sourceUnavailable
  | invalidSpec

noncomputable def prepareOUTS (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (cpu : CPUState) (memory : MemoryState) (spec : Spec)
    (sourceSegment : SegmentReg) (sequence : Nat) : OUTSPreparation :=
  let control := Control.ofCPUState cpu
  if spec.kind ≠ .outs then .invalidSpec
  else if !shouldExecute spec control then .skipped
  else match ioWidth spec.element with
  | none => .invalidSpec
  | some width =>
      match readStage profile config cpu pages memory spec control sourceSegment .sourceRead with
      | .fault error => .fault error
      | .unavailable _ => .sourceUnavailable
      | .unsupportedStage => .invalidSpec
      | .ready _ bytes memoryEvents => .ready {
          request := {
            direction := .output
            base := portFromDX cpu
            width
            writeData := bytes
            sequence
          }
          memoryEvents
        }

def FinishOUTS (beforeCPU : CPUState) (beforeMemory : MemoryState)
    (continuation : Continuation) (preparation : OUTSPreparation)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment)
    (disposition : TransferDisposition) (afterControl : Control)
    (result : Execution) : Prop :=
  match preparation with
  | .skipped => result = .bodyApplied beforeCPU beforeMemory []
      continuation.completedIterations
  | .invalidSpec => False
  | .fault error => result = .fault error beforeCPU beforeMemory []
      (restartAtBoundary beforeCPU.rip continuation)
  | .sourceUnavailable => result = .modelingUnavailable
      .capturedSourceUnavailable beforeCPU beforeMemory []
  | .ready ready =>
      TransferDispositionAllowed beforeCPU snapshot ordering environment ready.request disposition ∧
      match disposition with
      | .completed event => FinishControl beforeCPU beforeMemory continuation
          (wrapMemoryEffects ready.memoryEvents ++ [.io event]) afterControl result
      | .permissionUnavailable => result = .modelingUnavailable .permissionUnavailable
          beforeCPU beforeMemory (wrapMemoryEffects ready.memoryEvents)
      | .deviceUnavailable => result = .modelingUnavailable .deviceUnavailable
          beforeCPU beforeMemory (wrapMemoryEffects ready.memoryEvents)
      | .boundaryUnspecified => result = .modelingUnavailable .portBoundaryUnspecified
          beforeCPU beforeMemory (wrapMemoryEffects ready.memoryEvents)
      | .waitingForOrdering => result = .orderingOpen .waitingForPriorWrites
          beforeCPU beforeMemory (wrapMemoryEffects ready.memoryEvents) []
      | .generalProtection | .pageFault _ => result = .orderingOpen
          .permissionVersusMemoryFault beforeCPU beforeMemory
          (wrapMemoryEffects ready.memoryEvents)
          ["memory-read-commit-versus-permission-fault"]

structure INSReady where
  access : ResolvedAccess
  request : PortRequest

inductive INSPreparation where
  | ready (value : INSReady)
  | skipped
  /-- Destination/permission priority is not closed by the current sources. -/
  | destinationFault (error : ResolutionError)
  | invalidSpec

noncomputable def prepareINS (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (cpu : CPUState) (spec : Spec) (sequence : Nat) : INSPreparation :=
  let control := Control.ofCPUState cpu
  if spec.kind ≠ .ins then .invalidSpec
  else if !shouldExecute spec control then .skipped
  else match ioWidth spec.element with
  | none => .invalidSpec
  | some width =>
      match resolveMemoryStage profile config cpu pages spec control .es .destinationWrite with
      | none => .invalidSpec
      | some (.error error) => .destinationFault error
      | some (.ok access) => .ready {
          access
          request := {
            direction := .input
            base := portFromDX cpu
            width
            writeData := []
            sequence
          }
        }

def FinishINS (beforeCPU : CPUState) (beforeMemory : MemoryState)
    (continuation : Continuation) (preparation : INSPreparation)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment)
    (disposition : TransferDisposition) (afterControl : Control)
    (result : Execution) : Prop :=
  match preparation with
  | .skipped => result = .bodyApplied beforeCPU beforeMemory []
      continuation.completedIterations
  | .invalidSpec => False
  | .destinationFault _ => result = .orderingOpen .permissionVersusMemoryFault
      beforeCPU beforeMemory [] ["io-read-before-destination-fault"]
  | .ready ready =>
      TransferDispositionAllowed beforeCPU snapshot ordering environment ready.request disposition ∧
      match disposition with
      | .completed event =>
          match beforeMemory.write ready.access event.data with
          | none => result = .modelingUnavailable .memoryWriteShapeMismatch
              beforeCPU beforeMemory [.io event]
          | some afterMemory =>
              let writes := eventsForAccess .write ready.access event.data
              FinishControl beforeCPU afterMemory continuation
                (.io event :: wrapMemoryEffects writes) afterControl result
      | .permissionUnavailable => result = .modelingUnavailable .permissionUnavailable
          beforeCPU beforeMemory []
      | .deviceUnavailable => result = .modelingUnavailable .deviceUnavailable
          beforeCPU beforeMemory []
      | .boundaryUnspecified => result = .modelingUnavailable .portBoundaryUnspecified
          beforeCPU beforeMemory []
      | .waitingForOrdering => result = .orderingOpen .waitingForPriorWrites
          beforeCPU beforeMemory [] []
      | .generalProtection | .pageFault _ => result = .orderingOpen
          .permissionVersusMemoryFault beforeCPU beforeMemory []
          ["permission-versus-destination-precheck"]

theorem outs_source_fault_frames_state (cpu : CPUState) (memory : MemoryState)
    (continuation : Continuation) (error : ResolutionError)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment) (disposition : TransferDisposition)
    (afterControl : Control) :
    FinishOUTS cpu memory continuation (.fault error) snapshot ordering environment
      disposition afterControl
      (.fault error cpu memory [] (restartAtBoundary cpu.rip continuation)) := by
  rfl

theorem ins_effect_order_on_success (cpu : CPUState) (memory afterMemory : MemoryState)
    (continuation : Continuation) (ready : INSReady) (event : IOEvent)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment)
    (afterControl : Control) (writes : List MemoryEvent)
    (transfer : TransferDispositionAllowed cpu snapshot ordering environment ready.request
      (.completed event))
    (writeResult : memory.write ready.access event.data = some afterMemory)
    (events : eventsForAccess .write ready.access event.data = writes)
    (result : Execution)
    (finish : FinishControl cpu afterMemory continuation
      (.io event :: wrapMemoryEffects writes) afterControl result) :
    FinishINS cpu memory continuation (.ready ready) snapshot ordering environment
      (.completed event) afterControl result := by
  simp [FinishINS, writeResult, events]
  exact ⟨transfer, finish⟩

end AMD64.IOStrings
