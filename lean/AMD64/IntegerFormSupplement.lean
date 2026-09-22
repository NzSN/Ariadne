import AMD64.InstructionForms

/-!
Source-reviewed register projections for DEC, INC, NEG and NOT. Authority:
AMD APM Volume 3 revision 3.38, PDF pages 220-221, 232-233, 312-315,
plus prefix rules on PDF pages 48-57. The original form IDs are retained;
register selection is the ModRM.mod=3 instance of each reg/mem row. Memory
instances remain pending memory, exception and LOCK composition.
-/

namespace AMD64.Forms.IntegerSupplement

def commonPrefixes : List Prefix :=
  [.rep, .repne, .operandSize, .addressSize, .cs, .ss, .ds, .es, .fs, .gs, .rex]

def prefixesForWidth (width : Nat) : List Prefix :=
  if width = 8 ∨ width = 64 then commonPrefixes ++ [.rexW] else commonPrefixes

def allModes : List Mode :=
  [.real, .virtual8086, .protectedMode, .compatibility, .long64]

def legacyModes : List Mode := [.real, .virtual8086, .protectedMode, .compatibility]

def unaryRegister (width : Nat) : OperandConstraint := {
  allowedKinds := [.gpr, .memory], allowedWidths := [width],
  allowedEncodedWidths := [width], allowedSemanticWidths := [width],
  allowedExtensions := [.none], allowedIdentities := ["*"],
  allowedAccessIntents := [.readWrite], evaluationOrder := 1
}

def unaryRegisterForm (formId : FormId) (width : Nat)
    (modes : List Mode) : FormConstraint := {
  formId, reviewLevel := .semanticReviewed, constraintsKnown := true,
  openObligations := [], allowedModes := modes, requiredFeatures := [],
  allowedOperandSizes := [width], allowedAddressSizes := [16, 32, 64],
  allowedPrefixes := prefixesForWidth width ++ [.lock],
  requiredPrefixes := if width = 64 then [.rexW] else [],
  encodingFamilies := [.legacy], operands := [unaryRegister width],
  lockMemoryDestinationIndices := [0], implementationStatus := .partialCoverage
}

def embeddedRegisterForm (formId : FormId) (width : Nat) : FormConstraint :=
  { unaryRegisterForm formId width legacyModes with
    allowedPrefixes := prefixesForWidth width
    operands := [{ unaryRegister width with allowedKinds := [.gpr] }]
    lockMemoryDestinationIndices := [] }

def widthModes (width : Nat) : List Mode := if width = 64 then [.long64] else allModes

def dec8 := unaryRegisterForm "AMD64-F-0282" 8 (widthModes 8)
def dec16 := unaryRegisterForm "AMD64-F-0283" 16 (widthModes 16)
def dec32 := unaryRegisterForm "AMD64-F-0284" 32 (widthModes 32)
def dec64 := unaryRegisterForm "AMD64-F-0285" 64 (widthModes 64)
def dec16Embedded := embeddedRegisterForm "AMD64-F-0286" 16
def dec32Embedded := embeddedRegisterForm "AMD64-F-0287" 32
def inc8 := unaryRegisterForm "AMD64-F-0318" 8 (widthModes 8)
def inc16 := unaryRegisterForm "AMD64-F-0319" 16 (widthModes 16)
def inc32 := unaryRegisterForm "AMD64-F-0320" 32 (widthModes 32)
def inc64 := unaryRegisterForm "AMD64-F-0321" 64 (widthModes 64)
def inc16Embedded := embeddedRegisterForm "AMD64-F-0322" 16
def inc32Embedded := embeddedRegisterForm "AMD64-F-0323" 32
def neg8 := unaryRegisterForm "AMD64-F-0549" 8 (widthModes 8)
def neg16 := unaryRegisterForm "AMD64-F-0550" 16 (widthModes 16)
def neg32 := unaryRegisterForm "AMD64-F-0551" 32 (widthModes 32)
def neg64 := unaryRegisterForm "AMD64-F-0552" 64 (widthModes 64)
def not8 := unaryRegisterForm "AMD64-F-0557" 8 (widthModes 8)
def not16 := unaryRegisterForm "AMD64-F-0558" 16 (widthModes 16)
def not32 := unaryRegisterForm "AMD64-F-0559" 32 (widthModes 32)
def not64 := unaryRegisterForm "AMD64-F-0560" 64 (widthModes 64)

def catalog : List FormConstraint :=
  [dec8, dec16, dec32, dec64, dec16Embedded, dec32Embedded,
   inc8, inc16, inc32, inc64, inc16Embedded, inc32Embedded,
   neg8, neg16, neg32, neg64, not8, not16, not32, not64]

inductive UnaryOperation where | dec | inc | neg | not
  deriving DecidableEq, Repr

def binding (formId : FormId) : Option (UnaryOperation × FormConstraint) :=
  match formId with
  | "AMD64-F-0282" => some (.dec, dec8)
  | "AMD64-F-0283" => some (.dec, dec16)
  | "AMD64-F-0284" => some (.dec, dec32)
  | "AMD64-F-0285" => some (.dec, dec64)
  | "AMD64-F-0286" => some (.dec, dec16Embedded)
  | "AMD64-F-0287" => some (.dec, dec32Embedded)
  | "AMD64-F-0318" => some (.inc, inc8)
  | "AMD64-F-0319" => some (.inc, inc16)
  | "AMD64-F-0320" => some (.inc, inc32)
  | "AMD64-F-0321" => some (.inc, inc64)
  | "AMD64-F-0322" => some (.inc, inc16Embedded)
  | "AMD64-F-0323" => some (.inc, inc32Embedded)
  | "AMD64-F-0549" => some (.neg, neg8)
  | "AMD64-F-0550" => some (.neg, neg16)
  | "AMD64-F-0551" => some (.neg, neg32)
  | "AMD64-F-0552" => some (.neg, neg64)
  | "AMD64-F-0557" => some (.not, not8)
  | "AMD64-F-0558" => some (.not, not16)
  | "AMD64-F-0559" => some (.not, not32)
  | "AMD64-F-0560" => some (.not, not64)
  | _ => none

theorem catalog_reviewed : catalog.all readyForLegality = true := by decide

end AMD64.Forms.IntegerSupplement
