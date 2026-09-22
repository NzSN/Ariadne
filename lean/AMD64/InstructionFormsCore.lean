import AMD64.InstructionForms

/-! Closed source-reviewed register/immediate forms for the first execution
bindings. Authority is AMD Volume 3 revision 3.38: the named entry pages and
prefix sections 1.2.1-1.2.7 (PDF pages 48-57). Reg/mem source rows remain open
unless a distinct `-R` register-only variant is named here. -/

namespace AMD64.Forms.Core

def commonPrefixes : List Prefix :=
  [.rep, .repne, .operandSize, .addressSize, .cs, .ss, .ds, .es, .fs, .gs, .rex]

def prefixesForWidth (width : Nat) : List Prefix :=
  if width = 8 ∨ width = 64 then commonPrefixes ++ [.rexW] else commonPrefixes

def viewName : Nat -> String
  | 8 => "low8" | 16 => "low16" | 32 => "low32" | _ => "full64"

def accumulator (width : Nat) (access : AccessIntent) : OperandConstraint := {
  allowedKinds := [.gpr], allowedWidths := [width], allowedEncodedWidths := [width],
  allowedSemanticWidths := [width], allowedExtensions := [.none],
  allowedIdentities := [s!"gpr:0:{viewName width}"], allowedAccessIntents := [access],
  evaluationOrder := 1
}

def anyGPR (width : Nat) (access : AccessIntent) : OperandConstraint := {
  allowedKinds := [.gpr], allowedWidths := [width], allowedEncodedWidths := [width],
  allowedSemanticWidths := [width], allowedExtensions := [.none],
  allowedIdentities := ["*"], allowedAccessIntents := [access], evaluationOrder := 1
}

def immediate (encodedWidth semanticWidth : Nat)
    (extension : ValueExtension) : OperandConstraint := {
  allowedKinds := [.immediate], allowedWidths := [encodedWidth],
  allowedEncodedWidths := [encodedWidth], allowedSemanticWidths := [semanticWidth],
  allowedExtensions := [extension], allowedIdentities := [""],
  allowedAccessIntents := [.read], evaluationOrder := 2
}

def registerImmediateForm (formId : FormId) (width encodedWidth : Nat)
    (extension : ValueExtension) (destination : OperandConstraint) : FormConstraint := {
  formId := formId, reviewLevel := .semanticReviewed, constraintsKnown := true,
  openObligations := [],
  allowedModes := if width = 64 then [.long64]
    else [.real, .virtual8086, .protectedMode, .compatibility, .long64],
  requiredFeatures := [], allowedOperandSizes := [width],
  allowedAddressSizes := [16, 32, 64], allowedPrefixes := prefixesForWidth width,
  requiredPrefixes := if width = 64 then [.rexW] else [],
  encodingFamilies := [.legacy], operands := [destination, immediate encodedWidth width extension],
  lockMemoryDestinationIndices := [], implementationStatus := .missing
}

def arithmeticFamily (ids : FormId × FormId × FormId × FormId)
    (access : AccessIntent) : List FormConstraint :=
  [registerImmediateForm ids.1 8 8 .none (accumulator 8 access),
   registerImmediateForm ids.2.1 16 16 .none (accumulator 16 access),
   registerImmediateForm ids.2.2.1 32 32 .none (accumulator 32 access),
   registerImmediateForm ids.2.2.2 64 32 .sign (accumulator 64 access)]

def addALImm8 := registerImmediateForm "AMD64-F-0026" 8 8 .none (accumulator 8 .readWrite)
def addAXImm16 := registerImmediateForm "AMD64-F-0027" 16 16 .none (accumulator 16 .readWrite)
def addEAXImm32 := registerImmediateForm "AMD64-F-0028" 32 32 .none (accumulator 32 .readWrite)
def addRAXImm32 := registerImmediateForm "AMD64-F-0029" 64 32 .sign (accumulator 64 .readWrite)
def addForms := [addALImm8, addAXImm16, addEAXImm32, addRAXImm32]

def andALImm8 := registerImmediateForm "AMD64-F-0047" 8 8 .none (accumulator 8 .readWrite)
def andAXImm16 := registerImmediateForm "AMD64-F-0048" 16 16 .none (accumulator 16 .readWrite)
def andEAXImm32 := registerImmediateForm "AMD64-F-0049" 32 32 .none (accumulator 32 .readWrite)
def andRAXImm32 := registerImmediateForm "AMD64-F-0050" 64 32 .sign (accumulator 64 .readWrite)
def andForms := [andALImm8, andAXImm16, andEAXImm32, andRAXImm32]

def cmpALImm8 := registerImmediateForm "AMD64-F-0240" 8 8 .none (accumulator 8 .read)
def cmpAXImm16 := registerImmediateForm "AMD64-F-0241" 16 16 .none (accumulator 16 .read)
def cmpEAXImm32 := registerImmediateForm "AMD64-F-0242" 32 32 .none (accumulator 32 .read)
def cmpRAXImm32 := registerImmediateForm "AMD64-F-0243" 64 32 .sign (accumulator 64 .read)
def cmpForms := [cmpALImm8, cmpAXImm16, cmpEAXImm32, cmpRAXImm32]

def orALImm8 := registerImmediateForm "AMD64-F-0561" 8 8 .none (accumulator 8 .readWrite)
def orAXImm16 := registerImmediateForm "AMD64-F-0562" 16 16 .none (accumulator 16 .readWrite)
def orEAXImm32 := registerImmediateForm "AMD64-F-0563" 32 32 .none (accumulator 32 .readWrite)
def orRAXImm32 := registerImmediateForm "AMD64-F-0564" 64 32 .sign (accumulator 64 .readWrite)
def orForms := [orALImm8, orAXImm16, orEAXImm32, orRAXImm32]

def subALImm8 := registerImmediateForm "AMD64-F-0848" 8 8 .none (accumulator 8 .readWrite)
def subAXImm16 := registerImmediateForm "AMD64-F-0849" 16 16 .none (accumulator 16 .readWrite)
def subEAXImm32 := registerImmediateForm "AMD64-F-0850" 32 32 .none (accumulator 32 .readWrite)
def subRAXImm32 := registerImmediateForm "AMD64-F-0851" 64 32 .sign (accumulator 64 .readWrite)
def subForms := [subALImm8, subAXImm16, subEAXImm32, subRAXImm32]

def testALImm8 := registerImmediateForm "AMD64-F-0869" 8 8 .none (accumulator 8 .read)
def testAXImm16 := registerImmediateForm "AMD64-F-0870" 16 16 .none (accumulator 16 .read)
def testEAXImm32 := registerImmediateForm "AMD64-F-0871" 32 32 .none (accumulator 32 .read)
def testRAXImm32 := registerImmediateForm "AMD64-F-0872" 64 32 .sign (accumulator 64 .read)
def testForms := [testALImm8, testAXImm16, testEAXImm32, testRAXImm32]

def xorALImm8 := registerImmediateForm "AMD64-F-0913" 8 8 .none (accumulator 8 .readWrite)
def xorAXImm16 := registerImmediateForm "AMD64-F-0914" 16 16 .none (accumulator 16 .readWrite)
def xorEAXImm32 := registerImmediateForm "AMD64-F-0915" 32 32 .none (accumulator 32 .readWrite)
def xorRAXImm32 := registerImmediateForm "AMD64-F-0916" 64 32 .sign (accumulator 64 .readWrite)
def xorForms := [xorALImm8, xorAXImm16, xorEAXImm32, xorRAXImm32]

def movReg8Imm8 := registerImmediateForm "AMD64-F-0496" 8 8 .none (anyGPR 8 .write)
def movReg16Imm16 := registerImmediateForm "AMD64-F-0497" 16 16 .none (anyGPR 16 .write)
def movReg32Imm32 := registerImmediateForm "AMD64-F-0498" 32 32 .none (anyGPR 32 .write)
def movReg64Imm64 := registerImmediateForm "AMD64-F-0499" 64 64 .none (anyGPR 64 .write)
def movReg64Imm32Sign : FormConstraint :=
  registerImmediateForm "AMD64-F-0503-R" 64 32 .sign (anyGPR 64 .write)

def catalog : List FormConstraint :=
  addForms ++ andForms ++ cmpForms ++ orForms ++ subForms ++ testForms ++ xorForms ++
  [movReg8Imm8, movReg16Imm16, movReg32Imm32, movReg64Imm64, movReg64Imm32Sign]

theorem reviewed_add64 : readyForLegality addRAXImm32 = true := by decide
theorem reviewed_mov64 : readyForLegality movReg64Imm64 = true := by decide
theorem reviewed_mov64_sign : readyForLegality movReg64Imm32Sign = true := by decide
theorem reviewed_all : catalog.all readyForLegality = true := by decide

end AMD64.Forms.Core
