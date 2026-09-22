import AMD64.Control
import AMD64.IntegerExecutionChecks

namespace AMD64.Control.Checks

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics

def flags (cf pf zf sf of : Bool) : ArithmeticFlags :=
  { cf, pf, af := false, zf, sf, of }

example : conditionFromStatus .o (flags false false false false true) = true := by decide
example : conditionFromStatus .no (flags false false false false false) = true := by decide
example : conditionFromStatus .b (flags true false false false false) = true := by decide
example : conditionFromStatus .ae (flags false false false false false) = true := by decide
example : conditionFromStatus .e (flags false false true false false) = true := by decide
example : conditionFromStatus .ne (flags false false false false false) = true := by decide
example : conditionFromStatus .be (flags false false true false false) = true := by decide
example : conditionFromStatus .a (flags false false false false false) = true := by decide
example : conditionFromStatus .s (flags false false false true false) = true := by decide
example : conditionFromStatus .ns (flags false false false false false) = true := by decide
example : conditionFromStatus .p (flags false true false false false) = true := by decide
example : conditionFromStatus .np (flags false false false false false) = true := by decide
example : conditionFromStatus .l (flags false false false true false) = true := by decide
example : conditionFromStatus .ge (flags false false false true true) = true := by decide
example : conditionFromStatus .le (flags false false true false false) = true := by decide
example : conditionFromStatus .g (flags false false false true true) = true := by decide

def minusTwo8 : AMD64.Operands.ImmediateRef := {
  encoded := fun bit => bit.val < 8 && (254 : Nat).testBit bit.val,
  encodedWidth := 8, semanticWidth := 64, extension := .sign
}

example : RelativeReady minusTwo8 64 := by
  constructor
  · refine ⟨by decide, by decide, by decide, by decide, ?_⟩
    intro bit high
    change 8 ≤ bit.val at high
    simp [minusTwo8, show ¬ bit.val < 8 by omega]
  exact ⟨rfl, rfl, by decide, by decide⟩

theorem relative_target_high_zero (fallthrough : Address) (displacement : AMD64.Operands.ImmediateRef)
    (width : Nat) (bit : Fin 64) (high : width ≤ bit.val) :
    relativeTarget fallthrough displacement width bit = false := by
  simp [relativeTarget, truncateIP, show ¬ bit.val < width by omega]

theorem truncate_low (address : Address) (width : Nat) (bit : Fin 64)
    (low : bit.val < width) : truncateIP address width bit = address bit := by
  simp [truncateIP, low]

def stateWithRCX (value : Nat) : CPUState :=
  let base := AMD64.IntegerExecution.Checks.stateWithRax zero
  { base with gpr := fun register =>
      if register = GPR.rcx.toFin then wordOfNat value else base.gpr register }

example : countIsZero (decrementCount (stateWithRCX 1) .bits64) .bits64 = true := by
  decide

example : (decrementCount (stateWithRCX 1) .bits64).rflags = (stateWithRCX 1).rflags := by
  rfl

example : flagStackWidthPermitted (stateWithRCX 0) 64 = true := by decide
example : flagStackWidthPermitted (stateWithRCX 0) 32 = false := by decide

example (state : CPUState) (value : Address) (width : Nat) :
    (flagsAfterPop state value width).resume = false := by rfl

example : executeUndefinedOpcode .ud0 = .invalidOpcodeFault := rfl
example : executeUndefinedOpcode .ud1 = .invalidOpcodeFault := rfl
example : executeUndefinedOpcode .ud2 = .invalidOpcodeFault := rfl

end AMD64.Control.Checks
