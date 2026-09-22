import AMD64.IntegerStateAdapter
import AMD64.Operands
import AMD64.InstructionFormsCore
import AMD64.IntegerFormSupplement

/-!
Conditional execution binding for normalized register/immediate integer
payloads. A caller must first pass `Operands.validateExecutable` against a
source-reviewed form constraint. Until the reviewed form registry exports a
closed form-to-operation map, `operation` is an explicit conditional input and
this module does not claim a full instruction-form implementation.

Unsupported payloads produce `modelingUnavailable`; they are never interpreted
as #UD, a no-op, or an impossible architectural transition.

`bodyApplied` means operand and instruction-body effects have been applied.
RIP/fallthrough, fetch, trap delivery and asynchronous events are deliberately
not retirement here and must be composed by the later execution boundary.
-/

namespace AMD64.IntegerExecution

open AMD64.Arch
open AMD64.Operands
open AMD64.IntegerSemantics

inductive Operation where
  | mov | add | adc | sub | sbb | cmp | inc | dec | neg
  | and | or | xor | test | not
  | clc | stc | cmc | cld | std
  deriving DecidableEq, Repr

inductive UnavailableReason where
  | operandShape | memoryOperand | widthMismatch | formBindingPending
  | fallthroughEvidencePending | fallthroughCertificateInvalid
  deriving DecidableEq, Repr

inductive Outcome where
  | bodyApplied (state : CPUState)
  | modelingUnavailable (reason : UnavailableReason)
  | validationRejected

structure FallthroughEvidence where
  beforeIP : Bits 64
  instructionLength : Nat
  nextIP : Bits 64
  fetchAcceptedAssumption : Bool
  synchronousEventsResolvedAssumption : Bool
  asynchronousEventsCheckedAssumption : Bool

def truncateInstructionPointer (value : Bits 64) (width : Nat) : Bits 64 :=
  fun bit => if bit.val < width then value bit else false

def FallthroughEvidence.ValidFor (after : CPUState) (evidence : FallthroughEvidence) : Prop :=
  let width := defaultInstructionPointerWidth after.segments after.execution.mode
  after.rip = evidence.beforeIP ∧
  1 ≤ evidence.instructionLength ∧ evidence.instructionLength ≤ 15 ∧
  evidence.nextIP = truncateInstructionPointer
    (addWord evidence.beforeIP (wordOfNat evidence.instructionLength) false 64) width

inductive BoundaryOutcome where
  | fallthroughApplied (state : CPUState)
  | modelingUnavailable (reason : UnavailableReason)
  | validationRejected

def ApplyFallthrough (body : Outcome) (evidence : FallthroughEvidence)
    (result : BoundaryOutcome) : Prop :=
  match body with
  | .bodyApplied after =>
      (evidence.ValidFor after ∧
        evidence.fetchAcceptedAssumption = true ∧
        evidence.synchronousEventsResolvedAssumption = true ∧
        evidence.asynchronousEventsCheckedAssumption = true ∧
        result = .fallthroughApplied { after with rip := evidence.nextIP }) ∨
      (¬evidence.ValidFor after ∧
        result = .modelingUnavailable .fallthroughCertificateInvalid) ∨
      (evidence.ValidFor after ∧
        (evidence.fetchAcceptedAssumption = false ∨
         evidence.synchronousEventsResolvedAssumption = false ∨
         evidence.asynchronousEventsCheckedAssumption = false) ∧
        result = .modelingUnavailable .fallthroughEvidencePending)
  | .modelingUnavailable reason => result = .modelingUnavailable reason
  | .validationRejected => result = .validationRejected

theorem fallthrough_sets_rip (after : CPUState) (evidence : FallthroughEvidence)
    (valid : evidence.ValidFor after)
    (fetch : evidence.fetchAcceptedAssumption = true)
    (synchronous : evidence.synchronousEventsResolvedAssumption = true)
    (asynchronous : evidence.asynchronousEventsCheckedAssumption = true) :
    ApplyFallthrough (.bodyApplied after) evidence
      (.fallthroughApplied { after with rip := evidence.nextIP }) := by
  simp [ApplyFallthrough, valid, fetch, synchronous, asynchronous]

theorem fallthrough_frames_gpr (after result : CPUState) (evidence : FallthroughEvidence)
    (applied : ApplyFallthrough (.bodyApplied after) evidence (.fallthroughApplied result)) :
    result.gpr = after.gpr := by
  simp [ApplyFallthrough] at applied
  rcases applied with ⟨_, _, _, _, rfl⟩
  rfl

theorem fallthrough_frames_rflags (after result : CPUState) (evidence : FallthroughEvidence)
    (applied : ApplyFallthrough (.bodyApplied after) evidence (.fallthroughApplied result)) :
    result.rflags = after.rflags := by
  simp [ApplyFallthrough] at applied
  rcases applied with ⟨_, _, _, _, rfl⟩
  rfl

inductive ValueSource where
  | gpr (register : GPRRef)
  | immediate (value : ImmediateRef)

structure BinaryPayload where
  destination : GPRRef
  source : ValueSource

structure UnaryPayload where
  destination : GPRRef

def writeViewForMode (mode : OperatingMode) (before value : AMD64.Word)
    (view : AMD64.GPRView) : AMD64.Word :=
  if mode = .long64 then AMD64.writeView64 before value view
  else fun bit =>
    if h : view.offset ≤ bit.val ∧ bit.val < view.offset + view.width then
      value ⟨bit.val - view.offset, by omega⟩
    else before bit

def readGPR (state : CPUState) (register : GPRRef) : AMD64.Word :=
  AMD64.readView (state.gpr register.index) register.view

def writeGPR (state : CPUState) (register : GPRRef) (value : AMD64.Word) : CPUState :=
  { state with gpr := fun index =>
      if index = register.index then
        writeViewForMode state.execution.mode (state.gpr index) value register.view
      else state.gpr index }

/--
Architectural write relation. Volume 1 section 3.1.2.4 makes bits 63:32
undefined after a 32-bit operand in compatibility or legacy mode. `writeGPR`
remains a convenient deterministic witness, while instruction semantics use
this relation and therefore do not promise preservation or zeroing there.
-/
def WriteGPRAllowed (state : CPUState) (register : GPRRef) (value : AMD64.Word)
    (candidate : CPUState) : Prop :=
  if state.execution.mode != .long64 ∧ register.view = .low32 then
    ∃ stored : AMD64.Word,
      (∀ bit : Fin 64, bit.val < 32 → stored bit = value bit) ∧
      candidate = { state with gpr := fun index =>
        if index = register.index then stored else state.gpr index }
  else
    candidate = writeGPR state register value

@[simp] theorem writeGPR_is_allowed (state : CPUState) (register : GPRRef)
    (value : AMD64.Word) : WriteGPRAllowed state register value
      (writeGPR state register value) := by
  simp only [WriteGPRAllowed]
  split
  · rename_i h
    have modeNe : state.execution.mode ≠ .long64 := by simpa using h.1
    have viewEq : register.view = .low32 := h.2
    refine ⟨writeViewForMode state.execution.mode (state.gpr register.index)
      value register.view, ?_, ?_⟩
    · intro bit low
      simp [writeViewForMode, modeNe, viewEq, GPRView.offset, GPRView.width, low]
    · cases state
      simp only [writeGPR]
      congr 1
      funext index
      by_cases same : index = register.index
      · subst index
        simp
      · simp [same]
  · trivial

def writeStatus (state : CPUState) (status : ArithmeticFlags) : CPUState :=
  { state with rflags := applyStatusFlags state.rflags status }

def readSource (state : CPUState) : ValueSource → AMD64.Word
  | .gpr register => readGPR state register
  | .immediate value => value.value

def ValueSource.width : ValueSource → Nat
  | .gpr register => register.width
  | .immediate value => value.semanticWidth

def binaryPayload (instruction : ExecutableInstruction) :
    BinaryPayload ⊕ UnavailableReason :=
  match instruction.operands with
  | [destination, source] =>
      match destination.ref, source.ref with
      | .gpr dst, .gpr src =>
          if dst.width = instruction.operandSize ∧ src.width = dst.width then
            .inl ⟨dst, .gpr src⟩ else .inr .widthMismatch
      | .gpr dst, .immediate src =>
          if dst.width = instruction.operandSize ∧ src.semanticWidth = dst.width then
            .inl ⟨dst, .immediate src⟩ else .inr .widthMismatch
      | .gpr _, .memory .. => .inr .memoryOperand
      | .memory .., _ => .inr .memoryOperand
      | _, _ => .inr .operandShape
  | _ => .inr .operandShape

def unaryPayload (instruction : ExecutableInstruction) :
    UnaryPayload ⊕ UnavailableReason :=
  match instruction.operands with
  | [destination] =>
      match destination.ref with
      | .gpr dst => if dst.width = instruction.operandSize then .inl ⟨dst⟩
                    else .inr .widthMismatch
      | .memory .. => .inr .memoryOperand
      | _ => .inr .operandShape
  | _ => .inr .operandShape

def EffectsPermit (effects : FlagEffects) (old candidate : ArithmeticFlags) : Prop :=
  effects.cf.permits old.cf candidate.cf ∧
  effects.pf.permits old.pf candidate.pf ∧
  effects.af.permits old.af candidate.af ∧
  effects.zf.permits old.zf candidate.zf ∧
  effects.sf.permits old.sf candidate.sf ∧
  effects.of.permits old.of candidate.of

def exactArithmetic (operation : Operation) (left right : AMD64.Word)
    (old : ArithmeticFlags) (width : Nat) : ArithmeticResult :=
  match operation with
  | .add => addResult left right false width
  | .adc => addResult left right old.cf width
  | .sub | .cmp => subResult left right false width
  | .sbb => subResult left right old.cf width
  | _ => addResult left right false width

def exactUnary (operation : Operation) (value : AMD64.Word)
    (old : ArithmeticFlags) (width : Nat) : ArithmeticResult :=
  match operation with
  | .inc => incResult value width old.cf
  | .dec => decResult value width old.cf
  | .neg => negResult value width
  | _ => addResult value zero false width

def commitExactBinary (operation : Operation) (payload : BinaryPayload)
    (before : CPUState) : CPUState :=
  let width := payload.destination.width
  let left := readGPR before payload.destination
  let right := readSource before payload.source
  let result := exactArithmetic operation left right (projectStatusFlags before.rflags) width
  let valued := if operation = .cmp then before else writeGPR before payload.destination result.value
  writeStatus valued result.flags

def CommitExactBinaryAllowed (operation : Operation) (payload : BinaryPayload)
    (before after : CPUState) : Prop :=
  let width := payload.destination.width
  let left := readGPR before payload.destination
  let right := readSource before payload.source
  let result := exactArithmetic operation left right (projectStatusFlags before.rflags) width
  ∃ valued,
    (if operation = .cmp then valued = before
     else WriteGPRAllowed before payload.destination result.value valued) ∧
    after = writeStatus valued result.flags

@[simp] theorem commitExactBinary_is_allowed (operation : Operation) (payload : BinaryPayload)
    (before : CPUState) :
    CommitExactBinaryAllowed operation payload before
      (commitExactBinary operation payload before) := by
  simp only [CommitExactBinaryAllowed, commitExactBinary]
  split
  · exact ⟨before, rfl, rfl⟩
  · exact ⟨writeGPR before payload.destination
      (exactArithmetic operation (readGPR before payload.destination)
        (readSource before payload.source) (projectStatusFlags before.rflags)
        payload.destination.width).value,
      writeGPR_is_allowed _ _ _, rfl⟩

def logicOp : Operation → LogicOp
  | .and | .test => .and
  | .or => .or
  | .xor => .xor
  | _ => .and

def commitLogicBase (operation : Operation) (payload : BinaryPayload)
    (before : CPUState) : CPUState × FlagEffects :=
  let width := payload.destination.width
  let value := logicWord (logicOp operation) (readGPR before payload.destination)
    (readSource before payload.source) width
  let valued := if operation = .test then before else writeGPR before payload.destination value
  (valued, logicEffects (logicOp operation) value width)

def CommitLogicAllowed (operation : Operation) (payload : BinaryPayload)
    (before after : CPUState) : Prop :=
  let width := payload.destination.width
  let value := logicWord (logicOp operation) (readGPR before payload.destination)
    (readSource before payload.source) width
  ∃ valued status,
    (if operation = .test then valued = before
     else WriteGPRAllowed before payload.destination value valued) ∧
    EffectsPermit (logicEffects (logicOp operation) value width)
      (projectStatusFlags before.rflags) status ∧
    after = writeStatus valued status

def BodyStep (operation : Operation) (instruction : ExecutableInstruction)
    (before after : CPUState) : Prop :=
  match operation with
  | .mov =>
      match binaryPayload instruction with
      | .inl payload => WriteGPRAllowed before payload.destination
          (readSource before payload.source) after
      | .inr _ => False
  | .add | .adc | .sub | .sbb | .cmp =>
      match binaryPayload instruction with
      | .inl payload => CommitExactBinaryAllowed operation payload before after
      | .inr _ => False
  | .and | .or | .xor | .test =>
      match binaryPayload instruction with
      | .inl payload => CommitLogicAllowed operation payload before after
      | .inr _ => False
  | .inc | .dec | .neg =>
      match unaryPayload instruction with
      | .inl payload =>
          let value := readGPR before payload.destination
          let result := exactUnary operation value (projectStatusFlags before.rflags)
            payload.destination.width
          ∃ valued, WriteGPRAllowed before payload.destination result.value valued ∧
            after = writeStatus valued result.flags
      | .inr _ => False
  | .not =>
      match unaryPayload instruction with
      | .inl payload =>
          WriteGPRAllowed before payload.destination
            (notWord (readGPR before payload.destination) payload.destination.width) after
      | .inr _ => False
  | .clc => after = { before with rflags := { before.rflags with cf := false } }
  | .stc => after = { before with rflags := { before.rflags with cf := true } }
  | .cmc => after = { before with rflags := { before.rflags with cf := !before.rflags.cf } }
  | .cld => after = { before with rflags := { before.rflags with df := false } }
  | .std => after = { before with rflags := { before.rflags with df := true } }

def shapeUnavailable (operation : Operation) (instruction : ExecutableInstruction) :
    Option UnavailableReason :=
  match operation with
  | .mov | .add | .adc | .sub | .sbb | .cmp | .and | .or | .xor | .test =>
      match binaryPayload instruction with | .inl _ => none | .inr reason => some reason
  | .inc | .dec | .neg | .not =>
      match unaryPayload instruction with | .inl _ => none | .inr reason => some reason
  | _ => if instruction.operands.isEmpty then none else some .operandShape

def ExecuteConditional (operation : Operation) (instruction : ExecutableInstruction)
    (before : CPUState) (outcome : Outcome) : Prop :=
  match shapeUnavailable operation instruction with
  | some reason => outcome = .modelingUnavailable reason
  | none => match outcome with
    | .bodyApplied after => BodyStep operation instruction before after
    | .modelingUnavailable _ => False
    | .validationRejected => False

def reviewedBinding (formId : AMD64.Forms.FormId) :
    Option (Operation × AMD64.Forms.FormConstraint) :=
  match formId with
  | "AMD64-F-0026" => some (.add, AMD64.Forms.Core.addALImm8)
  | "AMD64-F-0027" => some (.add, AMD64.Forms.Core.addAXImm16)
  | "AMD64-F-0028" => some (.add, AMD64.Forms.Core.addEAXImm32)
  | "AMD64-F-0029" => some (.add, AMD64.Forms.Core.addRAXImm32)
  | "AMD64-F-0047" => some (.and, AMD64.Forms.Core.andALImm8)
  | "AMD64-F-0048" => some (.and, AMD64.Forms.Core.andAXImm16)
  | "AMD64-F-0049" => some (.and, AMD64.Forms.Core.andEAXImm32)
  | "AMD64-F-0050" => some (.and, AMD64.Forms.Core.andRAXImm32)
  | "AMD64-F-0240" => some (.cmp, AMD64.Forms.Core.cmpALImm8)
  | "AMD64-F-0241" => some (.cmp, AMD64.Forms.Core.cmpAXImm16)
  | "AMD64-F-0242" => some (.cmp, AMD64.Forms.Core.cmpEAXImm32)
  | "AMD64-F-0243" => some (.cmp, AMD64.Forms.Core.cmpRAXImm32)
  | "AMD64-F-0496" => some (.mov, AMD64.Forms.Core.movReg8Imm8)
  | "AMD64-F-0497" => some (.mov, AMD64.Forms.Core.movReg16Imm16)
  | "AMD64-F-0498" => some (.mov, AMD64.Forms.Core.movReg32Imm32)
  | "AMD64-F-0499" => some (.mov, AMD64.Forms.Core.movReg64Imm64)
  | "AMD64-F-0503-R" => some (.mov, AMD64.Forms.Core.movReg64Imm32Sign)
  | "AMD64-F-0561" => some (.or, AMD64.Forms.Core.orALImm8)
  | "AMD64-F-0562" => some (.or, AMD64.Forms.Core.orAXImm16)
  | "AMD64-F-0563" => some (.or, AMD64.Forms.Core.orEAXImm32)
  | "AMD64-F-0564" => some (.or, AMD64.Forms.Core.orRAXImm32)
  | "AMD64-F-0848" => some (.sub, AMD64.Forms.Core.subALImm8)
  | "AMD64-F-0849" => some (.sub, AMD64.Forms.Core.subAXImm16)
  | "AMD64-F-0850" => some (.sub, AMD64.Forms.Core.subEAXImm32)
  | "AMD64-F-0851" => some (.sub, AMD64.Forms.Core.subRAXImm32)
  | "AMD64-F-0869" => some (.test, AMD64.Forms.Core.testALImm8)
  | "AMD64-F-0870" => some (.test, AMD64.Forms.Core.testAXImm16)
  | "AMD64-F-0871" => some (.test, AMD64.Forms.Core.testEAXImm32)
  | "AMD64-F-0872" => some (.test, AMD64.Forms.Core.testRAXImm32)
  | "AMD64-F-0913" => some (.xor, AMD64.Forms.Core.xorALImm8)
  | "AMD64-F-0914" => some (.xor, AMD64.Forms.Core.xorAXImm16)
  | "AMD64-F-0915" => some (.xor, AMD64.Forms.Core.xorEAXImm32)
  | "AMD64-F-0916" => some (.xor, AMD64.Forms.Core.xorRAXImm32)
  | _ => none

noncomputable def ExecuteReviewed (architecture : ArchitectureProfile)
    (formProfile : AMD64.Forms.ArchitectureProfile)
    (instruction : ExecutableInstruction) (before : CPUState) (outcome : Outcome) : Prop := by
  classical
  exact match reviewedBinding instruction.formId with
    | none => outcome = .modelingUnavailable .formBindingPending
    | some (operation, form) =>
        if ValidCPUState architecture before then
          match validateExecutable architecture before formProfile form instruction with
          | .formResult .validated => ExecuteConditional operation instruction before outcome
          | _ => outcome = .validationRejected
        else outcome = .validationRejected

def supplementalOperation : AMD64.Forms.IntegerSupplement.UnaryOperation → Operation
  | .dec => .dec | .inc => .inc | .neg => .neg | .not => .not

/--
Execute the register instance of a reviewed DEC/INC/NEG/NOT source row. A
memory instance is left modeling-unavailable until translation, ordered faults
and LOCK atomicity are composed; it is never rejected merely because this
projection implements only the register instance.
-/
noncomputable def ExecuteSupplementalUnary (architecture : ArchitectureProfile)
    (formProfile : AMD64.Forms.ArchitectureProfile)
    (instruction : ExecutableInstruction) (before : CPUState) (outcome : Outcome) : Prop := by
  classical
  exact match AMD64.Forms.IntegerSupplement.binding instruction.formId with
    | none => outcome = .modelingUnavailable .formBindingPending
    | some (operation, form) =>
        if ¬ValidCPUState architecture before then outcome = .validationRejected
        else match validateExecutable architecture before formProfile form instruction with
          | .formResult .validated => match instruction.operands with
            | [operand] => match operand.ref with
              | .memory .. => outcome = .modelingUnavailable .memoryOperand
              | _ => ExecuteConditional (supplementalOperation operation) instruction before outcome
            | _ => outcome = .validationRejected
          | _ => outcome = .validationRejected

theorem writeGPR_other (state : CPUState) (register : GPRRef) (value : AMD64.Word)
    (other : Fin 16) (different : other ≠ register.index) :
    (writeGPR state register value).gpr other = state.gpr other := by
  simp [writeGPR, different]

theorem writeGPR_frames_rip (state : CPUState) (register : GPRRef) (value : AMD64.Word) :
    (writeGPR state register value).rip = state.rip := rfl

theorem writeStatus_frames_gpr (state : CPUState) (status : ArithmeticFlags) :
    (writeStatus state status).gpr = state.gpr := rfl

theorem writeStatus_frames_df (state : CPUState) (status : ArithmeticFlags) :
    (writeStatus state status).rflags.df = state.rflags.df := rfl

theorem writeGPRAllowed_frames_flags (state candidate : CPUState)
    (register : GPRRef) (value : AMD64.Word)
    (allowed : WriteGPRAllowed state register value candidate) :
    candidate.rflags = state.rflags := by
  simp only [WriteGPRAllowed] at allowed
  split at allowed
  · obtain ⟨stored, _, rfl⟩ := allowed
    rfl
  · rw [allowed]
    rfl

theorem mov_frames_flags (instruction : ExecutableInstruction) (before after : CPUState)
    (retired : BodyStep .mov instruction before after) : after.rflags = before.rflags := by
  simp only [BodyStep] at retired
  split at retired
  · exact writeGPRAllowed_frames_flags _ _ _ _ retired
  · contradiction

theorem not_frames_flags (instruction : ExecutableInstruction) (before after : CPUState)
    (retired : BodyStep .not instruction before after) : after.rflags = before.rflags := by
  simp only [BodyStep] at retired
  split at retired
  · exact writeGPRAllowed_frames_flags _ _ _ _ retired
  · contradiction

end AMD64.IntegerExecution
