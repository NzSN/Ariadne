import AMD64.IntegerShiftExecution
import AMD64.IntegerExecutionChecks

namespace AMD64.IntegerShiftExecution.Checks

open AMD64.Arch
open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.IntegerShiftExecution

def base := AMD64.IntegerExecution.Checks.stateWithRax (wordOfNat 129)

def stateWithRCX (value : IWord) : CPUState :=
  { base with gpr := fun index => if index.val = 1 then value else base.gpr index }

def operand (ref : OperandRef) (access : AccessIntent) (order : Nat) : ExecutableOperand := {
  ref, sourceText := "fixture", accessIntent := access, evaluationOrder := order,
  registerExtension := match ref with | .gpr r => decide (8 ≤ r.index.val) | _ => false,
  byteCode4To7 := match ref with
    | .gpr r => decide (r.view = .high8 ∨ 4 ≤ r.index.val % 8) | _ => false }

def imm8 (value : Nat) : OperandRef := .immediate {
  encoded := wordOfNat value, encodedWidth := 8, semanticWidth := 8,
  extension := .none }

def legacyInstruction (id : String) (width : Nat) (destination count : OperandRef) :
    ExecutableInstruction := {
  formId := id, operandSize := width, addressSize := 64,
  prefixes := if width = 64 then [.rexW] else [],
  operands := [operand destination .readWrite 1, operand count .read 2],
  implicitResources := [], encodingFamily := .legacy }

def tripleInstruction (id : String) (width : Nat) (destination source count : OperandRef)
    (family : EncodingFamily := .legacy) : ExecutableInstruction := {
  formId := id, operandSize := width, addressSize := 64,
  prefixes := if width = 64 ∧ family = .legacy then [.rexW] else [],
  operands := [operand destination .write 1, operand source .read 2,
    operand count .read 3], implicitResources := [], encodingFamily := family }

def al : GPRRef := ⟨0,.low8⟩
def ax : GPRRef := ⟨0,.low16⟩
def cl : GPRRef := ⟨1,.low8⟩
def rcx : GPRRef := ⟨1,.full64⟩

example : reviewedFormIds.length = 116 := by decide
example : reviewedFormIds.all (fun id => (BindingFor id).isSome) = true := by decide
example : BindingFor "AMD64-F-0687" = some ⟨.rol,8,.immediate,false⟩ := by decide
example : BindingFor "AMD64-F-0815" = some ⟨.shlx,64,.register,true⟩ := by decide
example : BindingFor "not-a-form" = none := by decide

def rol8By8 := legacyInstruction "AMD64-F-0687" 8 (.gpr al) (imm8 8)
def rol8By9 := legacyInstruction "AMD64-F-0687" 8 (.gpr al) (imm8 9)

example : payload ⟨.rol,8,.immediate,false⟩ rol8By8 base =
    .inl ⟨al, none, 8⟩ := by decide
example : unsignedValue (rotateValue .rol (readGPR base al) 8 (8 % 8)) 8 = 129 := by decide
example : (rotateEffects .rol (readGPR base al) 8 8).of = .undefined := by decide
example : unsignedValue (rotateValue .rol (readGPR base al) 8 (9 % 8)) 8 = 3 := by decide
example : (rotateEffects .rol (wordOfNat 3) 8 9).of = .undefined := by decide

def shlClCl := legacyInstruction "AMD64-F-0725" 8 (.gpr cl) (.gpr cl)
def aliasState := stateWithRCX (wordOfNat 3)
example : payload ⟨.shl,8,.cl,false⟩ shlClCl aliasState =
    .inl ⟨cl, none, 3⟩ := by decide
example : unsignedValue (shiftValue .shl (readGPR aliasState cl) 8 3) 8 = 24 := by decide

def shlCountZero := legacyInstruction "AMD64-F-0726" 8 (.gpr al) (imm8 32)
example : BodyStep ⟨.shl,8,.immediate,false⟩ ⟨al,none,32⟩ base base := by rfl

def rclRingValue := carryRotateValue .rcl (wordOfNat 128) true 8 (9 % 9)
example : unsignedValue rclRingValue 8 = 128 := by decide
example : carryRotateCF .rcl (wordOfNat 128) true 8 (9 % 9) = true := by decide

def shld16 := tripleInstruction "AMD64-F-0808" 16 (.gpr ax) (.gpr ax) (imm8 17)
example : payload ⟨.shld,16,.immediate,false⟩ shld16 base =
    .inl ⟨ax, some ax, 17⟩ := by decide
example : doubleShiftAllowed .shld (readGPR base ax) (readGPR base ax) 16 17 zero := by
  simp [doubleShiftAllowed, maskedCount, zero]
example : doubleShiftAllowed .shld (readGPR base ax) (readGPR base ax) 16 17
    (fun bit => bit.val = 0) := by
  simp [doubleShiftAllowed, maskedCount]
  omega

def shlxAlias := tripleInstruction "AMD64-F-0815" 64 (.gpr rcx) (.gpr rcx) (.gpr rcx) .vex
def bmiState := stateWithRCX (wordOfNat 3)
example : payload ⟨.shlx,64,.register,true⟩ shlxAlias bmiState =
    .inl ⟨rcx, some rcx, 3⟩ := by decide
example : unsignedValue (shiftValue .shl (readGPR bmiState rcx) 64 3) 64 = 24 := by decide
example : modeAllowed ⟨.shlx,64,.register,true⟩ .real = false := by decide
example : encodingAllowed ⟨.shlx,64,.register,true⟩ shlxAlias ⟨true,true⟩ = false := by decide
example : encodingAllowed ⟨.shlx,64,.register,true⟩ shlxAlias ⟨false,true⟩ = true := by decide

end AMD64.IntegerShiftExecution.Checks
