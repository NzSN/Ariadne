import AMD64.ArchitecturalState
import AMD64.Memory
import AMD64.InstructionForms
import Std

/-!
Executable operand payloads and their checked erasure to instruction-form shapes.

This module owns operand identity and encoding payload only. Register storage is
owned by `AMD64.Arch`; address translation, protection, and faults are owned by
`AMD64.MemoryModel`. `AddressExpr` retains the inputs needed to construct a
future `MemoryModel.AddressRequest`; it does not duplicate effective-address or
access resolution.
-/

namespace AMD64.Operands

open AMD64.Arch
open AMD64.MemoryModel

structure GPRRef where
  /-- Canonical order: RAX, RCX, RDX, RBX, RSP, RBP, RSI, RDI, R8..R15. -/
  index : Fin 16
  view : AMD64.GPRView
  deriving DecidableEq, Repr

def GPRRef.identity (register : GPRRef) : String :=
  s!"gpr:{register.index.val}:{match register.view with
    | .low8 => "low8" | .high8 => "high8" | .low16 => "low16"
    | .low32 => "low32" | .full64 => "full64"}"

def GPRRef.width : GPRRef -> Nat
  | ⟨_, .low8⟩ | ⟨_, .high8⟩ => 8
  | ⟨_, .low16⟩ => 16
  | ⟨_, .low32⟩ => 32
  | ⟨_, .full64⟩ => 64

def GPRRef.Valid (context : ExecutionContext) (register : GPRRef) : Prop :=
  GPRRegisterAvailable context register.index ∧
  (register.view = .high8 -> register.index.val < 4) ∧
  (register.view = .full64 -> context.mode = .long64)

inductive ImmediateExtension where
  | none | zero | sign
  deriving DecidableEq, Repr

structure ImmediateRef where
  encoded : Bits 64
  encodedWidth : Nat
  semanticWidth : Nat
  extension : ImmediateExtension

def ImmediateRef.Valid (immediate : ImmediateRef) : Prop :=
  immediate.encodedWidth ∈ [8, 16, 32, 64] ∧
  immediate.semanticWidth ∈ [8, 16, 32, 64] ∧
  immediate.encodedWidth ≤ immediate.semanticWidth ∧
  (immediate.extension = .none -> immediate.encodedWidth = immediate.semanticWidth) ∧
  (∀ bit : Fin 64, immediate.encodedWidth ≤ bit.val -> immediate.encoded bit = false)

def ImmediateRef.value (immediate : ImmediateRef) : Bits 64 := fun bit =>
  if bit.val < immediate.encodedWidth then immediate.encoded bit
  else match immediate.extension with
    | .sign => if h : 0 < immediate.encodedWidth then
        if upper : immediate.encodedWidth ≤ 64 then
          immediate.encoded ⟨immediate.encodedWidth - 1, by omega⟩ else false
        else false
    | .none | .zero => false

structure RelativeRef where
  displacement : Int
  encodedWidth : Nat
  targetWidth : Nat
  deriving DecidableEq, Repr

structure AddressExpr where
  base : Option (Fin 16)
  baseExtended : Bool
  index : Option (Fin 16)
  indexExtended : Bool
  scale : Nat
  displacement : Int
  displacementWidth : Nat
  segment : Option SegmentReg
  addressSize : AddressSize
  ripRelative : Bool
  deriving DecidableEq, Repr

def AddressExpr.Valid (context : ExecutionContext) (segments : SegmentContext)
    (address : AddressExpr) : Prop :=
  address.scale ∈ [1, 2, 4, 8] ∧
  address.displacementWidth ∈ [0, 8, 16, 32] ∧
  (∀ register ∈ address.base, GPRRegisterAvailable context register) ∧
  (∀ register ∈ address.index, GPRRegisterAvailable context register) ∧
  (address.base.map (fun register => 8 ≤ register.val) |>.getD false) = address.baseExtended ∧
  (address.index.map (fun register => 8 ≤ register.val) |>.getD false) = address.indexExtended ∧
  (address.index.isNone -> address.scale = 1) ∧
  (address.ripRelative -> address.base.isNone ∧ address.index.isNone ∧ context.mode = .long64) ∧
  addressSizePermitted context.mode (defaultAddressWidth segments context.mode) address.addressSize

inductive VectorView where
  | xmm | ymm | zmm
  deriving DecidableEq, Repr

def VectorView.width : VectorView -> Nat
  | .xmm => 128 | .ymm => 256 | .zmm => 512

def VectorView.archWidth : VectorView -> VectorWidth
  | .xmm => .bits128 | .ymm => .bits256 | .zmm => .bits512

structure VectorRef where
  index : Fin 32
  view : VectorView
  deriving DecidableEq, Repr

def VectorRef.Valid (profile : AMD64.Arch.ArchitectureProfile)
    (context : ExecutionContext) (register : VectorRef) : Prop :=
  VectorRegisterAvailable profile context register.index ∧
  VectorWidthAvailable profile register.view.archWidth

structure FarPointerRef where
  selector : Bits 16
  offset : Bits 64
  offsetWidth : Nat

def FarPointerRef.Valid (pointer : FarPointerRef) : Prop :=
  pointer.offsetWidth ∈ [16, 32, 64] ∧
  ∀ bit : Fin 64, pointer.offsetWidth ≤ bit.val -> pointer.offset bit = false

inductive OperandRef where
  | gpr (register : GPRRef)
  | memory (address : AddressExpr) (width : Nat)
  | immediate (value : ImmediateRef)
  | relative (value : RelativeRef)
  | segment (register : SegmentReg)
  | vector (register : VectorRef)
  | mmx (register : Fin 8)
  | mask (register : Fin 8)
  | farImmediate (pointer : FarPointerRef)
  | farMemory (address : AddressExpr) (offsetWidth : Nat)
  | constant (value : Int) (width : Nat)

def OperandRef.Valid (profile : AMD64.Arch.ArchitectureProfile)
    (context : ExecutionContext) (segments : SegmentContext) : OperandRef -> Prop
  | .gpr register => register.Valid context
  | .memory address width => address.Valid context segments ∧ width ∈ [8, 16, 32, 64, 128, 512]
  | .immediate value => value.Valid
  | .relative value => value.encodedWidth ∈ [8, 16, 32] ∧ value.targetWidth ∈ [16, 32, 64]
  | .segment _ => True
  | .vector register => register.Valid profile context
  | .mmx _ => profile.capabilities.mmx ∧ context.x87Enabled
  | .mask _ => MaskRegisterAvailable profile ∧ context.avx512Enabled
  | .farImmediate pointer => pointer.Valid
  | .farMemory address offsetWidth => address.Valid context segments ∧ offsetWidth ∈ [16, 32, 64]
  | .constant _ width => width ∈ [1, 8, 16, 32, 64]

def OperandRef.kind : OperandRef -> AMD64.Forms.OperandKind
  | .gpr _ => .gpr
  | .memory .. => .memory
  | .immediate _ => .immediate
  | .relative _ => .relativeOffset
  | .segment _ => .segmentRegister
  | .vector ⟨_, .xmm⟩ => .xmm
  | .vector _ => .vector
  | .mmx _ => .mmx
  | .mask _ => .mask
  | .farImmediate _ => .farPointerImmediate
  | .farMemory .. => .farPointerMemory
  | .constant .. => .constant

def OperandRef.width : OperandRef -> Nat
  | .gpr register => register.width
  | .memory _ width => width
  | .immediate value => value.encodedWidth
  | .relative value => value.encodedWidth
  | .segment _ => 16
  | .vector register => register.view.width
  | .mmx _ => 64
  | .mask _ => 64
  | .farImmediate pointer => pointer.offsetWidth
  | .farMemory _ width => width
  | .constant _ width => width

def ImmediateExtension.form : ImmediateExtension -> AMD64.Forms.ValueExtension
  | .none => .none | .zero => .zero | .sign => .sign

def OperandRef.encodingWidths : OperandRef -> Nat × Nat × AMD64.Forms.ValueExtension
  | .immediate value => (value.encodedWidth, value.semanticWidth, value.extension.form)
  | .relative value => (value.encodedWidth, value.targetWidth, .sign)
  | operand => (operand.width, operand.width, .none)

def OperandRef.identity : OperandRef -> String
  | .gpr register => register.identity
  | .segment register => s!"segment:{repr register}"
  | .vector register => s!"vector:{register.index.val}:{repr register.view}"
  | .mmx register => s!"mmx:{register.val}"
  | .mask register => s!"mask:{register.val}"
  | .memory .. => "memory"
  | .farMemory .. => "far-memory"
  | .immediate _ | .relative _ | .farImmediate _ | .constant .. => ""

structure ExecutableOperand where
  ref : OperandRef
  sourceText : String
  accessIntent : AMD64.Forms.AccessIntent
  evaluationOrder : Nat
  registerExtension : Bool
  byteCode4To7 : Bool

def ExecutableOperand.encodingCoherent (context : ExecutionContext)
    (family : AMD64.Forms.EncodingFamily) (rexPresent : Bool)
    (operand : ExecutableOperand) : Bool :=
  match operand.ref with
  | .gpr register =>
      let extendedSyntax := rexPresent || family != .legacy
      let expectedExtension := 8 ≤ register.index.val
      let expectedHighCode := match register.view with
        | .high8 => true
        | _ => 4 ≤ register.index.val % 8
      operand.registerExtension == expectedExtension &&
      operand.byteCode4To7 == expectedHighCode &&
      (!operand.registerExtension || (context.mode == .long64 && extendedSyntax)) &&
      (match register.view with
       | .high8 => !extendedSyntax && register.index.val < 4
       | .low8 => register.index.val < 4 || extendedSyntax
       | _ => true)
  | .memory address _ | .farMemory address _ =>
      let extendedSyntax := rexPresent || family != .legacy
      (!address.baseExtended && !address.indexExtended) ||
        (context.mode == .long64 && extendedSyntax)
  | .vector register =>
      register.index.val < 16 && !operand.byteCode4To7 &&
      operand.registerExtension == (8 ≤ register.index.val) &&
        (!operand.registerExtension ||
          (context.mode == .long64 && (rexPresent || family != .legacy)))
  | _ => !operand.registerExtension && !operand.byteCode4To7

def ExecutableOperand.erase (operand : ExecutableOperand) : AMD64.Forms.DecodedOperandShape := {
  kind := operand.ref.kind
  widthBits := some operand.ref.width
  encodedWidth := operand.ref.encodingWidths.1
  semanticWidth := operand.ref.encodingWidths.2.1
  extension := operand.ref.encodingWidths.2.2
  identity := operand.ref.identity
  sourceText := operand.sourceText
  accessIntent := operand.accessIntent
  evaluationOrder := operand.evaluationOrder
}

structure ExecutableInstruction where
  formId : AMD64.Forms.FormId
  operandSize : Nat
  addressSize : Nat
  prefixes : List AMD64.Forms.Prefix
  operands : List ExecutableOperand
  /-- Architectural reads/writes such as implicit AH; never interpreted as encoded fields. -/
  implicitResources : List OperandRef
  encodingFamily : AMD64.Forms.EncodingFamily

def modeShape : OperatingMode -> AMD64.Forms.Mode
  | .real => .real | .virtual8086 => .virtual8086
  | .protectedMode => .protectedMode | .compatibility => .compatibility
  | .long64 => .long64

def ExecutableInstruction.erase (context : ExecutionContext)
    (instruction : ExecutableInstruction) : AMD64.Forms.DecodedInstructionShape := {
  formId := instruction.formId
  mode := modeShape context.mode
  operandSize := instruction.operandSize
  addressSize := instruction.addressSize
  prefixes := instruction.prefixes
  operands := instruction.operands.map ExecutableOperand.erase
  encodingFamily := instruction.encodingFamily
  rexPresent := instruction.prefixes.contains .rex || instruction.prefixes.contains .rexW
  highByteRegister := instruction.operands.any fun operand =>
    match operand.ref with | .gpr ⟨_, .high8⟩ => true | _ => false
  prefixConflict := false
}

inductive CoupledValidationResult where
  | invalidPayload (operandIndices : List Nat)
  | formResult (result : AMD64.Forms.ValidationResult)
  deriving DecidableEq, Repr

noncomputable def invalidPayloadIndices (profile : AMD64.Arch.ArchitectureProfile)
    (context : ExecutionContext) (segments : SegmentContext)
    (operands : List ExecutableOperand) : List Nat := by
  classical
  exact operands.zipIdx.filterMap fun pair =>
    if OperandRef.Valid profile context segments pair.1.ref then none else some pair.2

def invalidEncodingIndices (context : ExecutionContext)
    (instruction : ExecutableInstruction) : List Nat :=
  let rexPresent := instruction.prefixes.contains .rex || instruction.prefixes.contains .rexW
  instruction.operands.zipIdx.filterMap fun pair =>
    if pair.1.encodingCoherent context instruction.encodingFamily rexPresent
    then none else some pair.2

noncomputable def invalidImplicitIndices (profile : AMD64.Arch.ArchitectureProfile)
    (context : ExecutionContext) (segments : SegmentContext)
    (operands : List OperandRef) : List Nat := by
  classical
  exact operands.zipIdx.filterMap fun pair =>
    if OperandRef.Valid profile context segments pair.1 then none else some pair.2

noncomputable def validateExecutable (architecture : AMD64.Arch.ArchitectureProfile)
    (state : CPUState) (formProfile : AMD64.Forms.ArchitectureProfile)
    (form : AMD64.Forms.FormConstraint) (instruction : ExecutableInstruction) :
    CoupledValidationResult :=
  let invalid := invalidPayloadIndices architecture state.execution state.segments instruction.operands
  let invalidEncoding := invalidEncodingIndices state.execution instruction
  let invalidImplicit := invalidImplicitIndices architecture state.execution state.segments instruction.implicitResources
  if invalid.isEmpty && invalidEncoding.isEmpty && invalidImplicit.isEmpty then
    .formResult (AMD64.Forms.validate form (instruction.erase state.execution) formProfile)
  else .invalidPayload (invalid ++ invalidEncoding ++ invalidImplicit)

theorem erase_gpr_identity (register : GPRRef) (source : String)
    (access : AMD64.Forms.AccessIntent) (order : Nat) :
    (ExecutableOperand.erase ⟨.gpr register, source, access, order,
      decide (8 ≤ register.index.val),
      decide (register.view = .high8 ∨ 4 ≤ register.index.val % 8)⟩).identity =
      register.identity := by
  rfl

theorem erase_preserves_operand_count (context : ExecutionContext)
    (instruction : ExecutableInstruction) :
    (instruction.erase context).operands.length = instruction.operands.length := by
  simp [ExecutableInstruction.erase]

namespace Fixture

def context64 : ExecutionContext := {
  mode := .long64, cpl := 3, x87Enabled := true, sseEnabled := true,
  avxEnabled := true, avx512Enabled := true
}

def rax : ExecutableOperand := ⟨.gpr ⟨0, .full64⟩, "RAX", .write, 2, false, false⟩
def rbx : ExecutableOperand := ⟨.gpr ⟨3, .full64⟩, "RBX", .read, 1, false, false⟩
def eax : ExecutableOperand := ⟨.gpr ⟨0, .low32⟩, "EAX", .write, 2, false, false⟩
def ah : ExecutableOperand := ⟨.gpr ⟨0, .high8⟩, "AH", .write, 2, false, true⟩
def spl : ExecutableOperand := ⟨.gpr ⟨4, .low8⟩, "SPL", .write, 2, false, true⟩

def xmm (index : Fin 32) : ExecutableOperand :=
  ⟨.vector ⟨index, .xmm⟩, "XMM", .read, 1, decide (8 ≤ index.val), false⟩

example : (xmm 8).encodingCoherent context64 .legacy true = true := by decide
example : (xmm 8).encodingCoherent context64 .legacy false = false := by decide
example : (xmm 8).encodingCoherent context64 .vex false = true := by decide
example : (xmm 16).encodingCoherent context64 .vex false = false := by decide

def instruction (operand : ExecutableOperand)
    (prefixes : List AMD64.Forms.Prefix := [.rexW]) : ExecutableInstruction := {
  formId := "fixture-add-r64-rm64", operandSize := 64, addressSize := 64,
  prefixes := prefixes, operands := [operand, rbx], implicitResources := [],
  encodingFamily := .legacy
}

example : AMD64.Forms.validate (AMD64.Forms.Fixture.completeForm .missing)
    ((instruction rax).erase context64) AMD64.Forms.Fixture.profile = .validated := by
  decide

example : ExecutableOperand.encodingCoherent context64 .legacy false spl = false := by
  decide

example : ExecutableOperand.encodingCoherent context64 .legacy true spl = true := by
  decide

example : AMD64.Forms.validate (AMD64.Forms.Fixture.completeForm .missing)
    ((instruction rbx).erase context64) AMD64.Forms.Fixture.profile =
      .normalizationError [.operandShapeMismatch] := by
  decide

example : AMD64.Forms.validate (AMD64.Forms.Fixture.completeForm .missing)
    ((instruction eax).erase context64) AMD64.Forms.Fixture.profile =
      .normalizationError [.operandShapeMismatch] := by
  decide

example : ((instruction ah [.rex]).erase context64).highByteRegister = true := by
  decide

example : AMD64.Forms.validate (AMD64.Forms.Fixture.completeForm .missing)
    ((instruction ah [.rex]).erase context64) AMD64.Forms.Fixture.profile =
      .normalizationError [.incoherentDecoderEvidence, .requiredPrefixMissing,
        .operandShapeMismatch, .rexHighByteConflict] := by
  decide

end Fixture
end AMD64.Operands
