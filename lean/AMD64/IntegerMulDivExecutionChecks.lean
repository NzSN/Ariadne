import AMD64.IntegerMulDivExecution
import AMD64.IntegerExecutionChecks

namespace AMD64.IntegerMulDivExecution.Checks

open AMD64.Arch
open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.IntegerMulDivExecution

def base := AMD64.IntegerExecution.Checks.stateWithRax zero

def stateWith (rax rdx rbx rcx : IWord) : CPUState :=
  { base with gpr := fun index =>
      if index.val = 0 then rax else if index.val = 2 then rdx
      else if index.val = 3 then rbx else if index.val = 1 then rcx else zero }

def op (ref : OperandRef) (access : AccessIntent) (order : Nat) : ExecutableOperand := {
  ref, sourceText := "fixture", accessIntent := access, evaluationOrder := order,
  registerExtension := match ref with | .gpr r => decide (8 ≤ r.index.val) | _ => false,
  byteCode4To7 := match ref with
    | .gpr r => decide (r.view = .high8 ∨ 4 ≤ r.index.val % 8) | _ => false }

def unary (id : String) (width : Nat) (source : GPRRef) : ExecutableInstruction := {
  formId := id, operandSize := width, addressSize := 64,
  prefixes := if width = 64 then [.rexW] else [],
  operands := [op (.gpr source) .read 1], implicitResources := [], encodingFamily := .legacy }

def triple (id : String) (width : Nat) (destination source : GPRRef)
    (immediate : ImmediateRef) : ExecutableInstruction := {
  formId := id, operandSize := width, addressSize := 64,
  prefixes := if width = 64 then [.rexW] else [],
  operands := [op (.gpr destination) .write 1, op (.gpr source) .read 2,
    op (.immediate immediate) .read 3], implicitResources := [], encodingFamily := .legacy }

def mulxInstruction (high low source : GPRRef) : ExecutableInstruction := {
  formId := "AMD64-F-0547", operandSize := 64, addressSize := 64, prefixes := [],
  operands := [op (.gpr high) .write 1, op (.gpr low) .write 2,
    op (.gpr source) .read 3], implicitResources := [], encodingFamily := .vex }

def al : GPRRef := ⟨0,.low8⟩
def ah : GPRRef := ⟨0,.high8⟩
def bl : GPRRef := ⟨3,.low8⟩
def rcx : GPRRef := ⟨1,.full64⟩
def rdx : GPRRef := ⟨2,.full64⟩
def rbx : GPRRef := ⟨3,.full64⟩

example : reviewedFormIds.length = 27 := by decide
example : reviewedFormIds.all (fun id => (BindingFor id).isSome) = true := by decide

def mul8Before := stateWith (wordOfNat 3) zero (wordOfNat 4) zero
def mul8Product := unsignedMul (readGPR mul8Before al) (readGPR mul8Before bl) 8
def mul8Status : ArithmeticFlags :=
  { cf := false, pf := false, af := false, zf := false, sf := false, of := false }
def mul8After := writeStatus
  (writeGPR (writeGPR mul8Before al mul8Product.low) ah mul8Product.high) mul8Status

example : unsignedValue mul8Product.low 8 = 12 := by decide
example : BodyStep ⟨.mul,8,.none,false⟩ (unary "AMD64-F-0542" 8 bl)
    mul8Before (.bodyApplied mul8After) := by
  have noOverflow : (unsignedMul (readGPR mul8Before al)
      (readGPR mul8Before bl) 8).overflow = false := by decide
  simp only [al] at noOverflow
  refine ⟨_, _, mul8Status, writeGPR_is_allowed _ _ _,
    writeGPR_is_allowed _ _ _, ?_, rfl⟩
  simp [EffectsPermit, FlagChoice.permits, mulEffects, mul8Status,
    noOverflow]

def div8Before := stateWith (wordOfNat 256) zero (wordOfNat 2) zero
def div8Correct : Bool := match unsignedDivide (readGPR div8Before ah)
    (readGPR div8Before al) (readGPR div8Before bl) 8 with
  | .ok quotient remainder => unsignedValue quotient 8 = 128 && unsignedValue remainder 8 = 0
  | .divideError => false
example : div8Correct = true := by decide

def zeroDivisor := stateWith (wordOfNat 256) zero zero zero
example : BodyStep ⟨.div,8,.none,false⟩ (unary "AMD64-F-0288" 8 bl)
    zeroDivisor (.divideError zeroDivisor) := by rfl

def overflowDividend := stateWith (wordOfNat 512) zero (wordOfNat 2) zero
example : BodyStep ⟨.div,8,.none,false⟩ (unary "AMD64-F-0288" 8 bl)
    overflowDividend (.divideError overflowDividend) := by rfl

def signedBefore := stateWith (wordOfNat 65533) zero (wordOfNat 2) zero
def signedCorrect : Bool := match signedDivide (readGPR signedBefore ah)
    (readGPR signedBefore al) (readGPR signedBefore bl) 8 with
  | .ok quotient remainder => unsignedValue quotient 8 = 255 && unsignedValue remainder 8 = 255
  | .divideError => false
example : signedCorrect = true := by decide

def minusOne8 : ImmediateRef := {
  encoded := wordOfNat 255, encodedWidth := 8, semanticWidth := 64,
  extension := .sign }
example : signedValue minusOne8.value 64 = -1 := by decide
example : signedImmediate (.immediate minusOne8) ⟨.imulThree,64,.imm8Sign,false⟩ =
    .inl minusOne8.value := by rfl

def mulxBefore := stateWith zero (wordOfNat 2) (wordOfNat 3) (wordOfNat 99)
def mulxOverlap := mulxInstruction rcx rcx rbx
def mulxProduct := unsignedMul (readGPR mulxBefore rdx) (readGPR mulxBefore rbx) 64
def mulxAfter := writeGPR (writeGPR mulxBefore rcx mulxProduct.low) rcx mulxProduct.high
example : unsignedValue (readGPR mulxAfter rcx) 64 = 0 := by decide
example : BodyStep ⟨.mulx,64,.none,true⟩ mulxOverlap mulxBefore
    (.bodyApplied mulxAfter) := by
  exact ⟨_, writeGPR_is_allowed _ _ _, writeGPR_is_allowed _ _ _⟩

example : modeAllowed ⟨.mulx,64,.none,true⟩ .real = false := by decide
example : encodingAllowed ⟨.mulx,64,.none,true⟩ mulxOverlap ⟨true,true⟩ = false := by decide

end AMD64.IntegerMulDivExecution.Checks
