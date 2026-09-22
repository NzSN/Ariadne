import AMD64.IntegerExecution

/-! CPU/register binding for MUL, IMUL, DIV, IDIV and MULX. -/
namespace AMD64.IntegerMulDivExecution

open AMD64.Arch
open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution

inductive Operation where
  | mul | imulOne | imulTwo | imulThree | div | idiv | mulx
  deriving DecidableEq, Repr

inductive ImmediateKind where | none | imm8Sign | operandSign
  deriving DecidableEq, Repr

structure Binding where
  operation : Operation
  width : Nat
  immediate : ImmediateKind := .none
  bmi2 : Bool := false
  deriving DecidableEq, Repr

structure EncodingEvidence where
  vexL : Bool := false
  vexW : Bool := false
  deriving DecidableEq, Repr

def bindings : List (String × Binding) := [
  ("AMD64-F-0288",⟨.div,8,.none,false⟩),("AMD64-F-0289",⟨.div,16,.none,false⟩),
  ("AMD64-F-0290",⟨.div,32,.none,false⟩),("AMD64-F-0291",⟨.div,64,.none,false⟩),
  ("AMD64-F-0295",⟨.idiv,8,.none,false⟩),("AMD64-F-0296",⟨.idiv,16,.none,false⟩),
  ("AMD64-F-0297",⟨.idiv,32,.none,false⟩),("AMD64-F-0298",⟨.idiv,64,.none,false⟩),
  ("AMD64-F-0299",⟨.imulOne,8,.none,false⟩),("AMD64-F-0300",⟨.imulOne,16,.none,false⟩),
  ("AMD64-F-0301",⟨.imulOne,32,.none,false⟩),("AMD64-F-0302",⟨.imulOne,64,.none,false⟩),
  ("AMD64-F-0303",⟨.imulTwo,16,.none,false⟩),("AMD64-F-0304",⟨.imulTwo,32,.none,false⟩),
  ("AMD64-F-0305",⟨.imulTwo,64,.none,false⟩),
  ("AMD64-F-0306",⟨.imulThree,16,.imm8Sign,false⟩),
  ("AMD64-F-0307",⟨.imulThree,32,.imm8Sign,false⟩),
  ("AMD64-F-0308",⟨.imulThree,64,.imm8Sign,false⟩),
  ("AMD64-F-0309",⟨.imulThree,16,.operandSign,false⟩),
  ("AMD64-F-0310",⟨.imulThree,32,.operandSign,false⟩),
  ("AMD64-F-0311",⟨.imulThree,64,.operandSign,false⟩),
  ("AMD64-F-0542",⟨.mul,8,.none,false⟩),("AMD64-F-0543",⟨.mul,16,.none,false⟩),
  ("AMD64-F-0544",⟨.mul,32,.none,false⟩),("AMD64-F-0545",⟨.mul,64,.none,false⟩),
  ("AMD64-F-0546",⟨.mulx,32,.none,true⟩),("AMD64-F-0547",⟨.mulx,64,.none,true⟩)]

def reviewedFormIds := bindings.map (·.1)
def BindingFor (formId : String) : Option Binding :=
  bindings.find? (fun pair => pair.1 = formId) |>.map (·.2)

inductive Outcome where
  | bodyApplied (state : CPUState)
  | divideError (unchanged : CPUState)
  | modelingUnavailable (reason : UnavailableReason)
  | validationRejected

def gpr (index : Nat) (view : GPRView) : Option GPRRef := do
  if h : index < 16 then some ⟨⟨index,h⟩,view⟩ else none

def accumulatorLow (width : Nat) : Option GPRRef :=
  match width with
  | 8 => gpr 0 .low8 | 16 => gpr 0 .low16 | 32 => gpr 0 .low32
  | 64 => gpr 0 .full64 | _ => none

def accumulatorHigh (width : Nat) : Option GPRRef :=
  match width with
  | 8 => gpr 0 .high8 | 16 => gpr 2 .low16 | 32 => gpr 2 .low32
  | 64 => gpr 2 .full64 | _ => none

def protectedFamily : OperatingMode → Bool
  | .protectedMode | .compatibility | .long64 => true
  | _ => false

def modeAllowed (binding : Binding) (mode : OperatingMode) : Bool :=
  (binding.width != 64 || mode == .long64) &&
  (!binding.bmi2 || protectedFamily mode)

def encodingAllowed (binding : Binding) (instruction : ExecutableInstruction)
    (evidence : EncodingEvidence) : Bool :=
  !instruction.prefixes.contains .lock &&
  if binding.bmi2 then
    instruction.encodingFamily == .vex && !evidence.vexL &&
      evidence.vexW == (binding.width == 64) &&
      !instruction.prefixes.contains .rex && !instruction.prefixes.contains .rexW
  else
    instruction.encodingFamily == .legacy &&
      (if binding.width = 64 then instruction.prefixes.contains .rexW
       else !instruction.prefixes.contains .rexW)

def sourceWord (before : CPUState) (ref : OperandRef) (width : Nat) :
    IWord ⊕ UnavailableReason :=
  match ref with
  | .gpr register => if register.width = width then .inl (readGPR before register)
                     else .inr .widthMismatch
  | .memory _ memoryWidth => if memoryWidth = width then .inr .memoryOperand
                             else .inr .widthMismatch
  | _ => .inr .operandShape

def signedImmediate (ref : OperandRef) (binding : Binding) :
    IWord ⊕ UnavailableReason :=
  match ref with
  | .immediate immediate =>
      let encoded := match binding.immediate with
        | .imm8Sign => 8 | .operandSign => if binding.width = 64 then 32 else binding.width
        | .none => 0
      if immediate.encodedWidth = encoded ∧ immediate.semanticWidth = binding.width ∧
          immediate.extension = .sign then .inl immediate.value else .inr .widthMismatch
  | _ => .inr .operandShape

def mulEffects (overflow : Bool) : FlagEffects := {
  cf := .exact overflow, of := .exact overflow,
  pf := .undefined, af := .undefined, zf := .undefined, sf := .undefined }

def divideEffects : FlagEffects := {
  cf := .undefined, pf := .undefined, af := .undefined,
  zf := .undefined, sf := .undefined, of := .undefined }

def writeWithEffects (before : CPUState) (register : GPRRef) (value : IWord)
    (effects : FlagEffects) (after : CPUState) : Prop :=
  ∃ valued status, WriteGPRAllowed before register value valued ∧
    EffectsPermit effects (projectStatusFlags before.rflags) status ∧
    after = writeStatus valued status

def writePairWithEffects (before : CPUState) (lowRef highRef : GPRRef)
    (low high : IWord) (effects : FlagEffects) (after : CPUState) : Prop :=
  ∃ lowWritten pairWritten status,
    WriteGPRAllowed before lowRef low lowWritten ∧
    WriteGPRAllowed lowWritten highRef high pairWritten ∧
    EffectsPermit effects (projectStatusFlags before.rflags) status ∧
    after = writeStatus pairWritten status

def implicitDividend (before : CPUState) (width : Nat) : Option (IWord × IWord) := do
  let lowRef ← accumulatorLow width
  let highRef ← accumulatorHigh width
  pure (readGPR before highRef, readGPR before lowRef)

def BodyStep (binding : Binding) (instruction : ExecutableInstruction)
    (before : CPUState) (outcome : Outcome) : Prop :=
  match binding.operation with
  | .mul | .imulOne | .div | .idiv =>
      match instruction.operands, accumulatorLow binding.width, accumulatorHigh binding.width with
      | [source], some lowRef, some highRef =>
          match sourceWord before source.ref binding.width with
          | .inr reason => outcome = .modelingUnavailable reason
          | .inl divisorOrFactor =>
              let low := readGPR before lowRef
              let high := readGPR before highRef
              match binding.operation with
              | .mul | .imulOne =>
                  let product := if binding.operation = .mul
                    then unsignedMul low divisorOrFactor binding.width
                    else signedMul low divisorOrFactor binding.width
                  match outcome with
                  | .bodyApplied after => writePairWithEffects before lowRef highRef
                      product.low product.high (mulEffects product.overflow) after
                  | _ => False
              | .div | .idiv =>
                  let divided := if binding.operation = .div
                    then unsignedDivide high low divisorOrFactor binding.width
                    else signedDivide high low divisorOrFactor binding.width
                  match divided with
                  | .divideError => outcome = .divideError before
                  | .ok quotient remainder => match outcome with
                    | .bodyApplied after => writePairWithEffects before lowRef highRef
                        quotient remainder divideEffects after
                    | _ => False
              | _ => False
      | _, _, _ => outcome = .validationRejected
  | .imulTwo =>
      match instruction.operands with
      | [destinationOperand, sourceOperand] => match destinationOperand.ref with
        | .gpr destination => match sourceWord before sourceOperand.ref binding.width with
          | .inl source =>
              let product := signedMul (readGPR before destination) source binding.width
              match outcome with
              | .bodyApplied after => writeWithEffects before destination product.low
                  (mulEffects product.overflow) after
              | _ => False
          | .inr reason => outcome = .modelingUnavailable reason
        | .memory .. => outcome = .modelingUnavailable .memoryOperand
        | _ => outcome = .validationRejected
      | _ => outcome = .validationRejected
  | .imulThree =>
      match instruction.operands with
      | [destinationOperand, sourceOperand, immediateOperand] =>
          match destinationOperand.ref, sourceWord before sourceOperand.ref binding.width,
            signedImmediate immediateOperand.ref binding with
          | .gpr destination, .inl source, .inl immediate =>
              let product := signedMul source immediate binding.width
              match outcome with
              | .bodyApplied after => writeWithEffects before destination product.low
                  (mulEffects product.overflow) after
              | _ => False
          | _, .inr reason, _ | _, _, .inr reason => outcome = .modelingUnavailable reason
          | _, _, _ => outcome = .validationRejected
      | _ => outcome = .validationRejected
  | .mulx =>
      match instruction.operands, accumulatorHigh binding.width with
      | [highOperand, lowOperand, sourceOperand], some implicitSource =>
          match highOperand.ref, lowOperand.ref, sourceWord before sourceOperand.ref binding.width with
          | .gpr highDestination, .gpr lowDestination, .inl source =>
              let product := unsignedMul (readGPR before implicitSource) source binding.width
              match outcome with
              | .bodyApplied after =>
                  ∃ lowWritten, WriteGPRAllowed before lowDestination product.low lowWritten ∧
                    WriteGPRAllowed lowWritten highDestination product.high after
              | _ => False
          | _, _, .inr reason => outcome = .modelingUnavailable reason
          | _, _, _ => outcome = .validationRejected
      | _, _ => outcome = .validationRejected

noncomputable def Execute (architecture : Arch.ArchitectureProfile)
    (formProfile : AMD64.Forms.ArchitectureProfile) (evidence : EncodingEvidence)
    (instruction : ExecutableInstruction) (before : CPUState) (outcome : Outcome) : Prop := by
  classical
  exact match BindingFor instruction.formId with
  | none => outcome = .modelingUnavailable .formBindingPending
  | some binding =>
      if ¬ValidCPUState architecture before then outcome = .validationRejected
      else if instruction.operandSize ≠ binding.width ||
          !modeAllowed binding before.execution.mode ||
          !formProfile.modes.contains (modeShape before.execution.mode) ||
          !encodingAllowed binding instruction evidence ||
          (binding.bmi2 && !formProfile.features.contains "bmi2") ||
          !formProfile.operandSizes.contains binding.width ||
          !formProfile.addressSizes.contains instruction.addressSize ||
          (before.execution.mode == .long64 && instruction.addressSize == 16) ||
          (before.execution.mode != .long64 && instruction.addressSize == 64) ||
          !(invalidPayloadIndices architecture before.execution before.segments
              instruction.operands).isEmpty ||
          !(invalidImplicitIndices architecture before.execution before.segments
              instruction.implicitResources).isEmpty ||
          !(invalidEncodingIndices before.execution instruction).isEmpty then
        outcome = .validationRejected
      else BodyStep binding instruction before outcome

end AMD64.IntegerMulDivExecution
