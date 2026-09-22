import AMD64.ControlExecution
import AMD64.IntegerExecutionChecks

namespace AMD64.Control.Execution.Checks

open AMD64.Arch
open AMD64.IntegerSemantics

example : enterLevel 0 = 0 := rfl
example : enterLevel 31 = 31 := by decide
example : enterLevel 32 = 0 := by decide
example : enterLevel 255 = 31 := by decide

example : enterCopyIndices 0 = [] := rfl
example : enterCopyIndices 1 = [] := rfl
example : enterCopyIndices 3 = [1, 2] := by decide

example : (enterProgram 0).map (·.kind) =
    [.pushOldRBP, .finalAccessCheck] := by decide

example : (enterProgram 3).map (·.kind) =
    [.pushOldRBP, .readFrame, .pushFrame, .readFrame, .pushFrame,
     .pushFramePointer, .finalAccessCheck] := by decide

example : pushaProgram[4]?.map (·.register) = some "original-rsp" := by decide
example : popaProgram[3]?.map (·.kind) = some .discardPop := by decide

def vmState : CPUState :=
  let base := AMD64.IntegerExecution.Checks.stateWithRax AMD64.IntegerSemantics.zero
  { base with
    execution := { base.execution with mode := .virtual8086, cpl := ⟨3, by omega⟩ }
    rflags := { base.rflags with
      virtual8086 := true
      iopl := AMD64.Arch.Bits.zero
      virtualInterrupt := true
      virtualInterruptPending := true } }

def poppedIF : Address := fun bit => bit.val = 9
def poppedTF : Address := fun bit => bit.val = 8

example : virtualFlagGuard vmState 16 true = .allowed := by decide
example : virtualFlagGuard vmState 16 false = .generalProtection := by decide
example : virtualFlagGuard vmState 32 true = .generalProtection := by decide
example : pushedFlagsWord vmState 16 true ⟨9, by omega⟩ = true := by decide
example : pushedFlagsWord vmState 16 true ⟨12, by omega⟩ = true := by decide
example : pushedFlagsWord vmState 16 true ⟨13, by omega⟩ = true := by decide
example : virtualPopFlagsFault vmState poppedTF 16 true = true := by decide
example : virtualPopFlagsFault vmState poppedIF 16 true = true := by decide
example : (applyPoppedFlagsWithVME vmState poppedIF 16 true).rflags.virtualInterrupt =
    true := by decide
example : (applyPoppedFlagsWithVME vmState poppedIF 16 true).rflags.interruptEnable =
    vmState.rflags.interruptEnable := by decide

theorem frame_read_indices_are_positive (rawLevel index : Nat)
    (member : index ∈ enterCopyIndices rawLevel) : 0 < index := by
  simp [enterCopyIndices] at member
  omega

end AMD64.Control.Execution.Checks
