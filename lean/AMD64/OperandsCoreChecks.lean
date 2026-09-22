import AMD64.Operands
import AMD64.InstructionFormsCore

namespace AMD64.Operands.CoreChecks

open AMD64.Arch

def context64 : ExecutionContext := {
  mode := .long64, cpl := 3, x87Enabled := true, sseEnabled := true,
  avxEnabled := true, avx512Enabled := true
}

def encoded (register : GPRRef) (access : AMD64.Forms.AccessIntent)
    (extension highCode : Bool) : ExecutableOperand := {
  ref := .gpr register, sourceText := register.identity,
  accessIntent := access, evaluationOrder := 1,
  registerExtension := extension, byteCode4To7 := highCode
}

def imm8 : ExecutableOperand := {
  ref := .immediate {
    encoded := Bits.zero, encodedWidth := 8, semanticWidth := 8,
    extension := .none
  }
  sourceText := "imm8", accessIntent := .read, evaluationOrder := 2,
  registerExtension := false, byteCode4To7 := false
}

def instruction (destination : ExecutableOperand)
    (prefixes : List AMD64.Forms.Prefix := []) : ExecutableInstruction := {
  formId := "AMD64-F-0026", operandSize := 8, addressSize := 64,
  prefixes := prefixes, operands := [destination, imm8], implicitResources := [],
  encodingFamily := .legacy
}

def al := encoded ⟨0, .low8⟩ .readWrite false false
def ah := encoded ⟨0, .high8⟩ .readWrite false true
def bl := encoded ⟨3, .low8⟩ .readWrite false false
def ax := encoded ⟨0, .low16⟩ .readWrite false false

def immediateOperand (encodedWidth semanticWidth : Nat)
    (extension : ImmediateExtension) : ExecutableOperand :=
  let value : ImmediateRef := {
    encoded := Bits.zero, encodedWidth := encodedWidth,
    semanticWidth := semanticWidth, extension := extension
  }
  { ref := .immediate value, sourceText := "imm", accessIntent := .read,
    evaluationOrder := 2, registerExtension := false, byteCode4To7 := false }

def wideInstruction (formId : String) (destination immediate : ExecutableOperand) :
    ExecutableInstruction := {
  formId := formId, operandSize := 64, addressSize := 64, prefixes := [.rexW],
  operands := [destination, immediate], implicitResources := [], encodingFamily := .legacy
}

def raxRW := encoded ⟨0, .full64⟩ .readWrite false false
def raxW := encoded ⟨0, .full64⟩ .write false false
def profile64 : AMD64.Forms.ArchitectureProfile := {
  modes := [.long64], features := [], operandSizes := [64], addressSizes := [64]
}

example : AMD64.Forms.validate AMD64.Forms.Core.addALImm8
    ((instruction al).erase context64) {
      modes := [.long64], features := [], operandSizes := [8], addressSizes := [64]
    } = .validated := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.addALImm8
    ((instruction ah).erase context64) {
      modes := [.long64], features := [], operandSizes := [8], addressSizes := [64]
    } = .normalizationError [.operandShapeMismatch] := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.addALImm8
    ((instruction bl).erase context64) {
      modes := [.long64], features := [], operandSizes := [8], addressSizes := [64]
    } = .normalizationError [.operandShapeMismatch] := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.addALImm8
    ((instruction ax).erase context64) {
      modes := [.long64], features := [], operandSizes := [8], addressSizes := [64]
    } = .normalizationError [.operandShapeMismatch] := by decide

example : invalidEncodingIndices context64 (instruction ah [.rex]) = [0] := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.addRAXImm32
    ((wideInstruction "AMD64-F-0029" raxRW (immediateOperand 32 64 .sign)).erase context64)
    profile64 = .validated := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.addRAXImm32
    ((wideInstruction "AMD64-F-0029" raxRW (immediateOperand 32 64 .zero)).erase context64)
    profile64 = .normalizationError [.operandShapeMismatch] := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.movReg64Imm64
    ((wideInstruction "AMD64-F-0499" raxW (immediateOperand 64 64 .none)).erase context64)
    profile64 = .validated := by decide

example : AMD64.Forms.validate AMD64.Forms.Core.movReg64Imm32Sign
    ((wideInstruction "AMD64-F-0503-R" raxW (immediateOperand 32 64 .sign)).erase context64)
    profile64 = .validated := by decide

end AMD64.Operands.CoreChecks
