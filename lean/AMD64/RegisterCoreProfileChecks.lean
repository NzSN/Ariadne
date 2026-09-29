import AMD64.IntegerExecutionChecks
import AMD64.Exceptions

/-!
Focused Stage D fixture for the register-only MOV reg64, imm32 candidate.
These proofs cover normalized payload, body and assumed fallthrough facts;
they do not certify fetch, event delivery or architectural retirement.
-/

namespace AMD64.RegisterCoreProfileChecks

open AMD64.Arch
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.IntegerExecution.Checks

def userBefore : CPUState :=
  { stateWithRax (fun _ => false) with execution := { context64 with cpl := 3 } }

theorem userBefore_valid : ValidCPUState architecture userBefore := by
  simp [ValidCPUState, ValidProfile, ModeSupported, architecture, capabilities,
    userBefore, stateWithRax, context64, flags, RFlags.Valid, x87, X87Control.Valid,
    X87Control.init, mxcsr, MXCSR.Valid, segments, SegmentContext.Valid,
    segment, cache, SegmentCache.Valid]

def mov64OneInstruction : ExecutableInstruction :=
  sizedInstruction "AMD64-F-0503-R" 64
    (gprOperand 0 .full64 .write 1) (immediateOperand 1 32 64 .sign) [.rexW]

def mov64OneAfter : CPUState :=
  writeGPR userBefore ⟨0, .full64⟩
    (readSource userBefore (.immediate (immediateRef 1 32 64 .sign)))

theorem mov64One_validated :
    validateExecutable architecture userBefore formProfile
      AMD64.Forms.Core.movReg64Imm32Sign mov64OneInstruction =
      .formResult .validated := by
  classical
  simp [validateExecutable, invalidPayloadIndices, invalidEncodingIndices,
    invalidImplicitIndices, mov64OneInstruction, sizedInstruction, gprOperand,
    immediateOperand, immediateRef, architecture, userBefore, stateWithRax,
    context64, segments, segment, cache, selector, formProfile,
    ExecutableOperand.encodingCoherent, OperandRef.Valid, GPRRef.Valid,
    ImmediateRef.Valid, GPRRegisterAvailable,
    AMD64.Forms.Core.movReg64Imm32Sign,
    AMD64.Forms.Core.registerImmediateForm, AMD64.Forms.Core.anyGPR,
    AMD64.Forms.Core.immediate, AMD64.Forms.validate]
  split
  · decide
  · rename_i missing
    exact (missing fun bit high => wordOfNat_one_high bit (by omega)).elim

theorem mov64One_body : ExecuteReviewed architecture formProfile mov64OneInstruction
    userBefore (.bodyApplied mov64OneAfter) := by
  unfold ExecuteReviewed
  rw [show reviewedBinding mov64OneInstruction.formId =
    some (.mov, AMD64.Forms.Core.movReg64Imm32Sign) by rfl]
  simp only
  rw [if_pos userBefore_valid, mov64One_validated]
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, mov64OneInstruction,
    sizedInstruction, gprOperand, immediateOperand, immediateRef, BodyStep,
    mov64OneAfter, GPRRef.width]

def negativeImmediate : ImmediateRef :=
  immediateBitsRef (lowOnes 32) 32 64 .sign

theorem negativeImmediate_all_ones (bit : Fin 64) :
    negativeImmediate.value bit = true := by
  by_cases low : bit.val < 32
  · simp [negativeImmediate, immediateBitsRef, lowOnes, ImmediateRef.value, low]
  · simp [negativeImmediate, immediateBitsRef, lowOnes, ImmediateRef.value, low]
      <;> decide

def mov64Evidence : FallthroughEvidence := {
  beforeIP := userBefore.rip
  instructionLength := 7
  nextIP := truncateInstructionPointer
    (addWord userBefore.rip (wordOfNat 7) false 64) 64
  fetchAcceptedAssumption := true
  synchronousEventsResolvedAssumption := true
  asynchronousEventsCheckedAssumption := true
}

theorem mov64Evidence_valid : mov64Evidence.ValidFor mov64OneAfter := by
  exact ⟨rfl, by decide, by decide, rfl⟩

def mov64BoundaryAfter : CPUState :=
  { mov64OneAfter with rip := mov64Evidence.nextIP }

theorem mov64_assumed_fallthrough :
    ApplyFallthrough (.bodyApplied mov64OneAfter) mov64Evidence
      (.fallthroughApplied mov64BoundaryAfter) := by
  exact fallthrough_sets_rip _ _ mov64Evidence_valid rfl rfl rfl

theorem mov64_frames_flags : mov64BoundaryAfter.rflags = userBefore.rflags := rfl

theorem mov64_writes_full_rax :
    mov64OneAfter.gpr 0 =
      readSource userBefore (.immediate (immediateRef 1 32 64 .sign)) := by
  simp [mov64OneAfter, writeGPR, writeViewForMode, userBefore,
    stateWithRax, context64, AMD64.qword_replaces]

theorem mov64_frames_other_gpr (other : Fin 16) (different : other ≠ 0) :
    mov64OneAfter.gpr other = userBefore.gpr other := by
  exact writeGPR_other userBefore ⟨0, .full64⟩
    (readSource userBefore (.immediate (immediateRef 1 32 64 .sign)))
    other different

def mov64Locked : ExecutableInstruction :=
  { mov64OneInstruction with prefixes := [.rexW, .lock] }

def mov64WithoutW : ExecutableInstruction :=
  { mov64OneInstruction with prefixes := [] }

theorem mov64_lock_form_invalid :
    AMD64.Forms.validate AMD64.Forms.Core.movReg64Imm32Sign
      (mov64Locked.erase userBefore.execution) formProfile =
      .architecturalInvalid [.prefixIllegalForForm, .lockRequiresMemoryDestination] := by
  decide

theorem mov64_missing_w_form_rejected :
    AMD64.Forms.validate AMD64.Forms.Core.movReg64Imm32Sign
      (mov64WithoutW.erase userBefore.execution) formProfile =
      .normalizationError [.requiredPrefixMissing] := by
  decide

def mov64LockFault : AMD64.Exceptions.Outcome CPUState String :=
  AMD64.Exceptions.rollbackFault userBefore userBefore.rip
    .ud .none none ["gpr:rax"]

theorem mov64_lock_fault_no_write :
    mov64LockFault.state = userBefore ∧
    mov64LockFault.committedEffects = [] := by
  simp [mov64LockFault, AMD64.Exceptions.rollbackFault,
    AMD64.Exceptions.Outcome.committedEffects]

theorem mov64_lock_fault_restarts_at_ip :
    mov64LockFault.detail.map
      (fun detail => (detail.restart.savedIP, detail.restart.resumeIP)) =
      some (userBefore.rip, userBefore.rip) := by
  simp [mov64LockFault, AMD64.Exceptions.rollbackFault]

theorem mov64_lock_fault_valid : mov64LockFault.Valid := by
  simp [mov64LockFault, AMD64.Exceptions.rollbackFault,
    AMD64.Exceptions.Outcome.Valid]

end AMD64.RegisterCoreProfileChecks
