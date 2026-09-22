import Std

/-!
Typed counterpart of `Specs/AMD64InstructionForms.tla`.

This file formalizes the validation boundary, not the 931-form catalogue and
not instruction execution. `Source.validate` is a reviewed Lean transcription
of the TLA+ operator. The correspondence theorem therefore checks the typed
operation against that transcription; it is not a proof about a parsed TLA+
module.

Decoded operands retain order and access intent for later evaluation. Form
validation compares their architectural kinds, but does not authorize an
evaluator to discard the richer records.
-/

namespace AMD64.Forms

abbrev FormId := String
abbrev Feature := String
abbrev Obligation := String

inductive Mode where
  | real | virtual8086 | protectedMode | compatibility | long64
  deriving DecidableEq, Repr

inductive ReviewLevel where
  | tableExtracted | tableReconciled | semanticReviewed
  deriving DecidableEq, Repr

inductive ImplementationStatus where
  | missing | partialCoverage | implemented
  deriving DecidableEq, Repr

inductive Prefix where
  | lock | rep | repne | operandSize | addressSize
  | cs | ss | ds | es | fs | gs | rex | rexW
  deriving DecidableEq, Repr

inductive EncodingFamily where
  | legacy | vex | xop
  deriving DecidableEq, Repr

inductive OperandKind where
  | gpr | gprOrMemory | memory | memoryComposite | immediate | relativeOffset
  | absoluteMemoryOffset | fixedRegister | segmentRegister
  | addressSizedAccumulator | farPointerImmediate | farPointerMemory
  | xmm | vector | mmx | mask | constant | widthDependent | unclassified
  deriving DecidableEq, Repr

inductive AccessIntent where
  | unknown | noAccess | read | write | readWrite | addressOnly
  deriving DecidableEq, Repr

inductive ValueExtension where
  | none | zero | sign
  deriving DecidableEq, Repr

/-! `DecodedOperandShape` is the legality projection of an executable operand.
It retains canonical register identity but has no immediate value or address
expression. Execution must use an `OperandRef` supplied by the execution lane
and prove/project that each reference has this shape before validation. -/
structure DecodedOperandShape where
  kind : OperandKind
  widthBits : Option Nat
  encodedWidth : Nat
  semanticWidth : Nat
  extension : ValueExtension
  /-- Canonical payload identity, e.g. `gpr:0:low8`; empty only for kinds with no identity. -/
  identity : String
  sourceText : String
  accessIntent : AccessIntent
  evaluationOrder : Nat
  deriving DecidableEq, Repr

abbrev DecodedOperand := DecodedOperandShape

structure OperandConstraint where
  allowedKinds : List OperandKind
  allowedWidths : List Nat
  allowedEncodedWidths : List Nat
  allowedSemanticWidths : List Nat
  allowedExtensions : List ValueExtension
  /-- `"*"` is an explicit wildcard; an empty list is never unrestricted. -/
  allowedIdentities : List String
  allowedAccessIntents : List AccessIntent
  evaluationOrder : Nat
  deriving DecidableEq, Repr

structure FormConstraint where
  formId : FormId
  reviewLevel : ReviewLevel
  constraintsKnown : Bool
  openObligations : List Obligation
  allowedModes : List Mode
  requiredFeatures : List Feature
  allowedOperandSizes : List Nat
  allowedAddressSizes : List Nat
  allowedPrefixes : List Prefix
  requiredPrefixes : List Prefix
  encodingFamilies : List EncodingFamily
  operands : List OperandConstraint
  /-- Zero-based indices whose concrete memory resolution permits LOCK. -/
  lockMemoryDestinationIndices : List Nat
  implementationStatus : ImplementationStatus
  deriving DecidableEq, Repr

structure DecodedInstructionShape where
  formId : FormId
  mode : Mode
  operandSize : Nat
  addressSize : Nat
  prefixes : List Prefix
  operands : List DecodedOperand
  encodingFamily : EncodingFamily
  rexPresent : Bool
  highByteRegister : Bool
  prefixConflict : Bool
  deriving DecidableEq, Repr

/-- Compatibility name for the current legality projection. This is not an
executable instruction AST; see `DecodedInstructionShape`. -/
abbrev DecodedInstruction := DecodedInstructionShape

structure ArchitectureProfile where
  modes : List Mode
  features : List Feature
  operandSizes : List Nat
  addressSizes : List Nat
  deriving DecidableEq, Repr

inductive InvalidReason where
  | formIdMismatch | incoherentDecoderEvidence
  | modeAddressSizeIncompatible
  | modeNotImplementedByProfile | modeIllegalForForm
  | missingRequiredFeature | operandSizeNotImplementedByProfile
  | operandSizeIllegalForForm | addressSizeNotImplementedByProfile
  | addressSizeIllegalForForm | conflictingPrefixes | prefixIllegalForForm
  | requiredPrefixMissing | encodingFamilyMismatch | operandShapeMismatch
  | lockRequiresMemoryDestination | rexHighByteConflict
  deriving DecidableEq, Repr

inductive ValidationResult where
  | validated
  | architecturalInvalid (reasons : List InvalidReason)
  | undefinedEncoding (reasons : List InvalidReason)
  | normalizationError (reasons : List InvalidReason)
  | profileError (reasons : List InvalidReason)
  | undetermined (obligations : List Obligation)
  deriving DecidableEq, Repr

def constraintDataComplete (form : FormConstraint) : Bool :=
  !form.allowedModes.isEmpty &&
  !form.allowedOperandSizes.isEmpty &&
  !form.allowedAddressSizes.isEmpty &&
  !form.encodingFamilies.isEmpty &&
  form.operands.all fun operand =>
    !operand.allowedKinds.isEmpty && !operand.allowedWidths.isEmpty &&
    !operand.allowedEncodedWidths.isEmpty && !operand.allowedSemanticWidths.isEmpty &&
    !operand.allowedExtensions.isEmpty &&
    !operand.allowedIdentities.isEmpty && !operand.allowedAccessIntents.isEmpty

def readyForLegality (form : FormConstraint) : Bool :=
  form.reviewLevel == .semanticReviewed &&
  form.constraintsKnown &&
  form.openObligations.isEmpty &&
  constraintDataComplete form

private def reasonIf (condition : Bool) (reason : InvalidReason) : List InvalidReason :=
  if condition then [reason] else []

private def listSubset [BEq α] (left right : List α) : Bool :=
  left.all right.contains

private def operandShapesMatch (expected : List OperandConstraint)
    (actual : List DecodedOperand) : Bool :=
  expected.length == actual.length &&
  (expected.zip actual).all fun pair =>
    pair.1.allowedKinds.contains pair.2.kind &&
    pair.1.allowedWidths.contains (pair.2.widthBits.getD 0) &&
    pair.1.allowedEncodedWidths.contains pair.2.encodedWidth &&
    pair.1.allowedSemanticWidths.contains pair.2.semanticWidth &&
    pair.1.allowedExtensions.contains pair.2.extension &&
    (pair.1.allowedIdentities.contains "*" ||
      pair.1.allowedIdentities.contains pair.2.identity) &&
    pair.1.allowedAccessIntents.contains pair.2.accessIntent &&
    pair.1.evaluationOrder == pair.2.evaluationOrder

private def lockUseLegal (form : FormConstraint) (decoded : DecodedInstruction) : Bool :=
  !decoded.prefixes.contains .lock ||
  form.lockMemoryDestinationIndices.any fun index =>
    match decoded.operands[index]? with
    | some operand => operand.kind == .memory
    | none => false

private def decoderEvidenceCoherent (decoded : DecodedInstruction) : Bool :=
  let rexPrefix := decoded.prefixes.contains .rex || decoded.prefixes.contains .rexW
  let familyCoherent :=
    if decoded.encodingFamily == .legacy then decoded.rexPresent == rexPrefix
    else !decoded.rexPresent && !rexPrefix
  familyCoherent && (!rexPrefix || decoded.mode == .long64) &&
    (!decoded.highByteRegister ||
      (decoded.encodingFamily == .legacy && !decoded.rexPresent))

def invalidReasons (form : FormConstraint) (decoded : DecodedInstruction)
    (profile : ArchitectureProfile) : List InvalidReason :=
  reasonIf (decoded.formId != form.formId) .formIdMismatch ++
  reasonIf (!decoderEvidenceCoherent decoded) .incoherentDecoderEvidence ++
  reasonIf ((decoded.mode == .long64 && decoded.addressSize == 16) ||
    (decoded.mode != .long64 && decoded.addressSize == 64)) .modeAddressSizeIncompatible ++
  reasonIf (!profile.modes.contains decoded.mode) .modeNotImplementedByProfile ++
  reasonIf (!form.allowedModes.contains decoded.mode) .modeIllegalForForm ++
  reasonIf (!listSubset form.requiredFeatures profile.features) .missingRequiredFeature ++
  reasonIf (!profile.operandSizes.contains decoded.operandSize) .operandSizeNotImplementedByProfile ++
  reasonIf (!form.allowedOperandSizes.contains decoded.operandSize) .operandSizeIllegalForForm ++
  reasonIf (!profile.addressSizes.contains decoded.addressSize) .addressSizeNotImplementedByProfile ++
  reasonIf (!form.allowedAddressSizes.contains decoded.addressSize) .addressSizeIllegalForForm ++
  reasonIf decoded.prefixConflict .conflictingPrefixes ++
  reasonIf (!listSubset decoded.prefixes form.allowedPrefixes) .prefixIllegalForForm ++
  reasonIf (!listSubset form.requiredPrefixes decoded.prefixes) .requiredPrefixMissing ++
  reasonIf (!form.encodingFamilies.contains decoded.encodingFamily) .encodingFamilyMismatch ++
  reasonIf (!operandShapesMatch form.operands decoded.operands) .operandShapeMismatch ++
  reasonIf (!lockUseLegal form decoded) .lockRequiresMemoryDestination ++
  reasonIf (decoded.rexPresent && decoded.highByteRegister) .rexHighByteConflict

private def normalizationReasons : List InvalidReason :=
  [.formIdMismatch, .incoherentDecoderEvidence, .modeAddressSizeIncompatible,
   .requiredPrefixMissing, .encodingFamilyMismatch,
   .operandShapeMismatch, .rexHighByteConflict]

private def profileReasons : List InvalidReason :=
  [.modeNotImplementedByProfile, .operandSizeNotImplementedByProfile,
   .addressSizeNotImplementedByProfile]

private def undefinedReasons : List InvalidReason := [.conflictingPrefixes]

private def architecturalForm (form : FormConstraint) : FormConstraint :=
  { form with implementationStatus := .missing }

private def validateArchitectural (form : FormConstraint) (decoded : DecodedInstruction)
    (profile : ArchitectureProfile) : ValidationResult :=
  if readyForLegality form then
    match invalidReasons form decoded profile with
    | [] => .validated
    | reasons =>
      let normalization := reasons.filter normalizationReasons.contains
      let profileErrors := reasons.filter profileReasons.contains
      let undefined := reasons.filter undefinedReasons.contains
      let architectural := reasons.filter fun reason =>
        !normalizationReasons.contains reason &&
        !profileReasons.contains reason &&
        !undefinedReasons.contains reason
      if !normalization.isEmpty then .normalizationError normalization
      else if !profileErrors.isEmpty then .profileError profileErrors
      else if !undefined.isEmpty then .undefinedEncoding undefined
      else .architecturalInvalid architectural
  else
    .undetermined (form.openObligations ++ ["semantic-form-review-incomplete"])

def validate (form : FormConstraint) (decoded : DecodedInstruction)
    (profile : ArchitectureProfile) : ValidationResult :=
  validateArchitectural (architecturalForm form) decoded profile

def implementationDisposition (form : FormConstraint) : ImplementationStatus :=
  form.implementationStatus

theorem unreviewed_is_undetermined (form : FormConstraint)
    (decoded : DecodedInstruction) (profile : ArchitectureProfile)
    (h : form.reviewLevel ≠ .semanticReviewed) :
    validate form decoded profile =
      .undetermined (form.openObligations ++ ["semantic-form-review-incomplete"]) := by
  simp [validate, validateArchitectural, architecturalForm, readyForLegality, h]

theorem validated_implies_review_ready (form : FormConstraint)
    (decoded : DecodedInstruction) (profile : ArchitectureProfile)
    (h : validate form decoded profile = .validated) : readyForLegality form = true := by
  unfold validate at h
  unfold validateArchitectural at h
  split at h
  next ready => exact ready
  next => contradiction

theorem implementation_status_independent (form : FormConstraint)
    (status : ImplementationStatus) (decoded : DecodedInstruction)
    (profile : ArchitectureProfile) :
    validate { form with implementationStatus := status } decoded profile =
      validate form decoded profile := by
  unfold validate architecturalForm
  congr 1

namespace Fixture

def operand (kind : OperandKind) (identity : String) (access : AccessIntent)
    (order : Nat) : DecodedOperand := {
  kind := kind, widthBits := some 64,
  encodedWidth := 64, semanticWidth := 64, extension := .none,
  identity := identity,
  sourceText := "fixture",
  accessIntent := access, evaluationOrder := order
}

def completeForm (status : ImplementationStatus) : FormConstraint := {
  formId := "fixture-add-r64-rm64",
  reviewLevel := .semanticReviewed,
  constraintsKnown := true,
  openObligations := [],
  allowedModes := [.long64],
  requiredFeatures := [],
  allowedOperandSizes := [64],
  allowedAddressSizes := [64],
  allowedPrefixes := [.fs, .gs, .addressSize, .rex, .rexW],
  requiredPrefixes := [.rexW],
  encodingFamilies := [.legacy],
  operands := [
    { allowedKinds := [.gpr], allowedWidths := [64], allowedEncodedWidths := [64],
      allowedSemanticWidths := [64], allowedExtensions := [.none],
      allowedIdentities := ["gpr:0:full64"],
      allowedAccessIntents := [.write], evaluationOrder := 2 },
    { allowedKinds := [.gpr, .memory], allowedWidths := [64], allowedEncodedWidths := [64],
      allowedSemanticWidths := [64], allowedExtensions := [.none], allowedIdentities := ["*"],
      allowedAccessIntents := [.read], evaluationOrder := 1 }
  ],
  lockMemoryDestinationIndices := [],
  implementationStatus := status
}

def pendingForm : FormConstraint := {
  completeForm .missing with
  reviewLevel := .tableReconciled,
  constraintsKnown := false,
  openObligations := ["review-mode-and-size-rules"]
}

def profile : ArchitectureProfile := {
  modes := [.long64], features := [], operandSizes := [64], addressSizes := [32, 64]
}

def goodDecoded : DecodedInstruction := {
  formId := "fixture-add-r64-rm64",
  mode := .long64,
  operandSize := 64,
  addressSize := 64,
  prefixes := [.rexW],
  operands := [operand .gpr "gpr:0:full64" .write 2,
    operand .gpr "gpr:1:full64" .read 1],
  encodingFamily := .legacy,
  rexPresent := true,
  highByteRegister := false,
  prefixConflict := false
}

example : validate pendingForm goodDecoded profile =
    .undetermined ["review-mode-and-size-rules", "semantic-form-review-incomplete"] := by
  decide

example : validate { completeForm .missing with allowedModes := [] } goodDecoded profile =
    .undetermined ["semantic-form-review-incomplete"] := by
  decide

example : validate (completeForm .missing) goodDecoded profile = .validated := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with mode := .protectedMode, addressSize := 32 } profile =
    .normalizationError [.incoherentDecoderEvidence] := by
  decide

example : validate (completeForm .missing) goodDecoded { profile with modes := [] } =
    .profileError [.modeNotImplementedByProfile] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with prefixes := [.rexW, .rep] } profile =
    .architecturalInvalid [.prefixIllegalForForm] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with prefixes := [.rexW, .lock] } profile =
    .architecturalInvalid [.prefixIllegalForForm, .lockRequiresMemoryDestination] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with encodingFamily := .xop } profile =
    .normalizationError [.incoherentDecoderEvidence, .encodingFamilyMismatch] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with highByteRegister := true } profile =
    .normalizationError [.incoherentDecoderEvidence, .rexHighByteConflict] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with prefixes := [.rexW, .lock], operands := [] } profile =
    .normalizationError [.operandShapeMismatch] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with rexPresent := false } profile =
    .normalizationError [.incoherentDecoderEvidence] := by
  decide

example : validate (completeForm .missing)
    { goodDecoded with operands := [
        { operand .gpr "gpr:0:full64" .write 2 with identity := "gpr:3:full64" },
        operand .gpr "gpr:1:full64" .read 1] } profile =
    .normalizationError [.operandShapeMismatch] := by
  decide

end Fixture

namespace Source

/-! Reviewed transcription of the TLA+ validation operator. The shared types
make record encoding/decoding identities; the trust boundary is the manual
comparison between this definition and the TLA+ source. -/

def validate (form : FormConstraint) (decoded : DecodedInstruction)
    (profile : ArchitectureProfile) : ValidationResult :=
  validateArchitectural (architecturalForm form) decoded profile

theorem validation_correspondence (form : FormConstraint)
    (decoded : DecodedInstruction) (profile : ArchitectureProfile) :
    AMD64.Forms.validate form decoded profile = validate form decoded profile := by
  rfl

end Source
end AMD64.Forms
