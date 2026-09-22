import AMD64.IntegerStateAdapter

namespace AMD64.IntegerSemantics.Checks

open AMD64.Arch

def baseRFlags : RFlags := {
  cf := false, fixed1 := true, pf := true, reserved3 := false,
  af := false, reserved5 := false, zf := true, sf := false,
  tf := true, interruptEnable := true, df := false, of := true,
  iopl := fun _ => false, nestedTask := false, reserved15 := false,
  resume := false, virtual8086 := false, ac := true,
  virtualInterrupt := false, virtualInterruptPending := false,
  id := true, reservedHigh := fun _ => false
}

def changedStatus : ArithmeticFlags := {
  cf := true, pf := false, af := true, zf := false, sf := true, of := false
}

example : projectStatusFlags (applyStatusFlags baseRFlags changedStatus) = changedStatus := by
  rfl
example : (applyStatusFlags baseRFlags changedStatus).df = false := by decide
example : (setDirectionFlag baseRFlags true).df = true := by decide
example : (setDirectionFlag baseRFlags true).Valid := by
  apply set_direction_preserves_validity
  simp [baseRFlags, RFlags.Valid]
  funext bit
  rfl

end AMD64.IntegerSemantics.Checks
