import AMD64.IntegerExecution

namespace AMD64.IntegerExecution.Checks

open AMD64.Arch
open AMD64.Operands
open AMD64.IntegerSemantics

def capabilities : Capabilities := {
  longMode := true, x87 := true, mmx := true, sse := true,
  avx := true, avx512 := true, mxcsrMisalignedMask := true
}

def architecture : ArchitectureProfile :=
  { capabilities, physicalAddressBits := 52, linearAddressBits := 48 }

def selector : SegmentSelector := { raw := Bits.zero }

def cache (longMode : Bool) : SegmentCache := {
  base := Bits.zero, limit := fun _ => true, present := true, dpl := 0,
  readable := true, writable := true, executable := true, conforming := false,
  expandDown := false, defaultBig := false, longMode
}

def segment (longMode : Bool) : SegmentRegister :=
  { selector, cache := cache longMode, unusable := false }

def segments : SegmentContext := {
  cs := segment true, ss := segment false, ds := segment false,
  es := segment false, fs := segment false, gs := segment false
}

def flags : RFlags := {
  cf := false, fixed1 := true, pf := false, reserved3 := false,
  af := false, reserved5 := false, zf := false, sf := false,
  tf := false, interruptEnable := true, df := false, of := false,
  iopl := Bits.zero, nestedTask := false, reserved15 := false,
  resume := false, virtual8086 := false, ac := false,
  virtualInterrupt := false, virtualInterruptPending := false,
  id := false, reservedHigh := Bits.zero
}

def x87Status : X87Status := {
  invalid := false, denormal := false, zeroDivide := false,
  overflow := false, underflow := false, precision := false,
  stackFault := false, errorSummary := false, c0 := false, c1 := false,
  c2 := false, top := 0, c3 := false, busy := false
}

def x87 : X87State := {
  physical := fun _ _ => false, tags := fun _ => .empty,
  status := x87Status, control := X87Control.init,
  lastInstruction := .offset64 Bits.zero, lastData := .offset64 Bits.zero,
  lastOpcode := Bits.zero
}

def mxcsr : MXCSR := {
  invalid := false, denormal := false, zeroDivide := false,
  overflow := false, underflow := false, precision := false,
  denormalsAreZero := false, invalidMask := true, denormalMask := true,
  zeroDivideMask := true, overflowMask := true, underflowMask := true,
  precisionMask := true, roundingControl := .nearest, flushToZero := false,
  reserved16 := false, misalignedMask := false, reservedHigh := Bits.zero
}

def context64 : ExecutionContext := {
  mode := .long64, cpl := 0, x87Enabled := true, sseEnabled := true,
  avxEnabled := true, avx512Enabled := true
}

def stateWithRax (rax : AMD64.Word) : CPUState := {
  gpr := fun register => if register.val = 0 then rax else zero,
  rip := Bits.zero, rflags := flags, segments, x87,
  vectors := fun _ _ => false, kMask := fun _ _ => false, mxcsr,
  execution := context64
}

theorem stateWithRax_valid (rax : AMD64.Word) :
    ValidCPUState architecture (stateWithRax rax) := by
  simp [ValidCPUState, ValidProfile, ModeSupported, architecture, capabilities,
    stateWithRax, context64, flags, RFlags.Valid, x87, X87Control.Valid,
    X87Control.init, mxcsr, MXCSR.Valid, segments, SegmentContext.Valid, segment, cache,
    SegmentCache.Valid]

def formProfile : AMD64.Forms.ArchitectureProfile := {
  modes := [.long64], features := [], operandSizes := [8, 16, 32, 64], addressSizes := [64]
}

def al (access : AMD64.Forms.AccessIntent) : ExecutableOperand :=
  { ref := .gpr ⟨0, .low8⟩, sourceText := "AL", accessIntent := access,
    evaluationOrder := 1, registerExtension := false, byteCode4To7 := false }

def byteRegister (index : Fin 16) : ExecutableOperand :=
  { ref := .gpr ⟨index, .low8⟩, sourceText := "r8b", accessIntent := .write,
    evaluationOrder := 1, registerExtension := decide (8 ≤ index.val),
    byteCode4To7 := decide (4 ≤ index.val % 8) }

def imm8 (value : Nat) : ExecutableOperand :=
  { ref := .immediate {
      encoded := wordOfNat value, encodedWidth := 8,
      semanticWidth := 8, extension := .none },
    sourceText := "imm8", accessIntent := .read, evaluationOrder := 2,
    registerExtension := false, byteCode4To7 := false }

def instruction (formId : String) (destination source : ExecutableOperand) :
    ExecutableInstruction := {
  formId, operandSize := 8, addressSize := 64, prefixes := [],
  operands := [destination, source], implicitResources := [], encodingFamily := .legacy
}

def gprOperand (index : Fin 16) (view : GPRView)
    (access : AMD64.Forms.AccessIntent) (order : Nat) : ExecutableOperand :=
  { ref := .gpr ⟨index, view⟩, sourceText := "gpr", accessIntent := access,
    evaluationOrder := order, registerExtension := decide (8 ≤ index.val),
    byteCode4To7 := decide (view = .high8 ∨ 4 ≤ index.val % 8) }

def immediateRef (value encodedWidth semanticWidth : Nat)
    (extension : ImmediateExtension) : ImmediateRef := {
  encoded := wordOfNat value
  encodedWidth := encodedWidth
  semanticWidth := semanticWidth
  extension := extension
}

def lowOnes (width : Nat) : AMD64.Word := fun bit => bit.val < width

def immediateBitsRef (encoded : AMD64.Word) (encodedWidth semanticWidth : Nat)
    (extension : ImmediateExtension) : ImmediateRef := {
  encoded, encodedWidth, semanticWidth, extension
}

def immediateOperand (value encodedWidth semanticWidth : Nat)
    (extension : ImmediateExtension) : ExecutableOperand :=
  { ref := .immediate (immediateRef value encodedWidth semanticWidth extension)
    sourceText := "imm", accessIntent := .read,
    evaluationOrder := 2, registerExtension := false, byteCode4To7 := false }

def sizedInstruction (formId : String) (width : Nat) (destination source : ExecutableOperand)
    (prefixes : List AMD64.Forms.Prefix := []) : ExecutableInstruction := {
  formId, operandSize := width, addressSize := 64, prefixes,
  operands := [destination, source], implicitResources := [], encodingFamily := .legacy
}

def unaryInstruction (formId : String) (width : Nat) (destination : ExecutableOperand)
    (prefixes : List AMD64.Forms.Prefix := []) : ExecutableInstruction := {
  formId, operandSize := width, addressSize := 64, prefixes,
  operands := [destination], implicitResources := [], encodingFamily := .legacy
}

def add255 : ExecutableInstruction :=
  instruction "AMD64-F-0026" (al .readWrite) (imm8 1)

@[simp] theorem wordOfNat_one_high (bit : Fin 64) (high : 8 ≤ bit.val) :
    wordOfNat 1 bit = false := by
  apply Nat.testBit_lt_two_pow
  apply Nat.one_lt_pow
  · omega
  · decide

def movHigh : ExecutableInstruction :=
  instruction "AMD64-F-0496"
    { ref := .gpr ⟨0, .high8⟩, sourceText := "AH", accessIntent := .write,
      evaluationOrder := 1, registerExtension := false, byteCode4To7 := true }
    (imm8 18)

example : writeViewForMode .long64 (fun _ => true) zero .low32 = zero := by
  funext bit
  by_cases lower : bit.val < 32
  · simp [writeViewForMode, AMD64.writeView64, GPRView.offset, GPRView.width, lower, zero]
  · simp [writeViewForMode, AMD64.writeView64, GPRView.offset, GPRView.width, lower, zero]

example (before : AMD64.Word) (value : AMD64.Word) (bit : Fin 64)
    (upper : 32 ≤ bit.val) :
    writeViewForMode .protectedMode before value .low32 bit = before bit := by
  simp [writeViewForMode, GPRView.offset, GPRView.width, show ¬bit.val < 32 by omega]

example (state : CPUState) (register : GPRRef) (value : AMD64.Word)
    (other : Fin 16) (different : other ≠ register.index) :
    (writeGPR state register value).gpr other = state.gpr other :=
  writeGPR_other state register value other different

def legacyState : CPUState :=
  { stateWithRax (fun _ => true) with
    execution := { context64 with mode := .protectedMode } }

def legacyLow32ZeroUpper : CPUState :=
  { legacyState with gpr := fun index bit =>
      if index = 0 then wordOfNat 1 bit else legacyState.gpr index bit }

def legacyLow32OneUpper : CPUState :=
  { legacyState with gpr := fun index bit =>
      if index = 0 then (wordOfNat 1 bit || decide (32 ≤ bit.val))
      else legacyState.gpr index bit }

example : WriteGPRAllowed legacyState ⟨0, .low32⟩ (wordOfNat 1)
    legacyLow32ZeroUpper := by
  refine ⟨wordOfNat 1, ?_, ?_⟩
  · intro bit low
    rfl
  · simp only [legacyLow32ZeroUpper]
    congr 1
    funext index bit
    by_cases same : index = 0 <;> simp [same]

example : WriteGPRAllowed legacyState ⟨0, .low32⟩ (wordOfNat 1)
    legacyLow32OneUpper := by
  refine ⟨fun bit => wordOfNat 1 bit || decide (32 ≤ bit.val), ?_, ?_⟩
  · intro bit low
    simp [show ¬32 ≤ bit.val by omega]
  · simp only [legacyLow32OneUpper]
    congr 1
    funext index bit
    by_cases same : index = 0 <;> simp [same]

example : reviewedBinding "AMD64-F-0026" = some (.add, AMD64.Forms.Core.addALImm8) := by
  rfl

example : reviewedBinding "unknown" = none := by rfl

theorem add255_validated : validateExecutable architecture (stateWithRax (wordOfNat 255)) formProfile
    AMD64.Forms.Core.addALImm8 add255 = .formResult .validated := by
  classical
  simp [validateExecutable, invalidPayloadIndices, invalidEncodingIndices,
    invalidImplicitIndices, add255, instruction, al, imm8, architecture,
    stateWithRax, context64, segments, segment, cache, selector, formProfile,
    ExecutableOperand.encodingCoherent, OperandRef.Valid, GPRRef.Valid,
    ImmediateRef.Valid, GPRRegisterAvailable,
    AMD64.Forms.Core.addALImm8,
    AMD64.Forms.Core.registerImmediateForm, AMD64.Forms.Core.accumulator,
    AMD64.Forms.Core.immediate, AMD64.Forms.validate]
  split
  · decide
  · rename_i missing
    exact (missing wordOfNat_one_high).elim

def inc255 : ExecutableInstruction :=
  unaryInstruction "AMD64-F-0318" 8 (al .readWrite)

def inc255Payload : UnaryPayload := ⟨⟨0, .low8⟩⟩
def inc255After : CPUState :=
  let value := readGPR (stateWithRax (wordOfNat 255)) inc255Payload.destination
  let result := exactUnary .inc value
    (projectStatusFlags (stateWithRax (wordOfNat 255)).rflags) 8
  writeStatus (writeGPR (stateWithRax (wordOfNat 255)) inc255Payload.destination
    result.value) result.flags

example : AMD64.Forms.IntegerSupplement.binding inc255.formId =
    some (.inc, AMD64.Forms.IntegerSupplement.inc8) := by rfl

example : BodyStep .inc inc255 (stateWithRax (wordOfNat 255)) inc255After := by
  simp [BodyStep, unaryPayload, inc255, unaryInstruction, al, inc255After,
    inc255Payload, GPRRef.width]
  exact ⟨_, writeGPR_is_allowed _ _ _, rfl⟩

def addPayload : BinaryPayload :=
  ⟨⟨0, .low8⟩, .immediate {
    encoded := wordOfNat 1, encodedWidth := 8,
    semanticWidth := 8, extension := .none }⟩

def addAfter : CPUState :=
  commitExactBinary .add addPayload (stateWithRax (wordOfNat 255))

example : ExecuteReviewed architecture formProfile add255
    (stateWithRax (wordOfNat 255)) (.bodyApplied addAfter) := by
  unfold ExecuteReviewed
  rw [show reviewedBinding add255.formId =
    some (.add, AMD64.Forms.Core.addALImm8) by rfl]
  simp only
  rw [if_pos (stateWithRax_valid (wordOfNat 255))]
  rw [add255_validated]
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, add255,
    instruction, al, imm8, BodyStep, addAfter, addPayload, GPRRef.width]

example : unsignedValue (readGPR addAfter ⟨0, .low8⟩) 8 = 0 := by decide
example : addAfter.rflags.cf = true := by decide
example : addAfter.rflags.zf = true := by decide
example : addAfter.rflags.df = flags.df := by decide

def add16Instruction := sizedInstruction "AMD64-F-0027" 16
  (gprOperand 0 .low16 .readWrite 1) (immediateOperand 1 16 16 .none)
def add16Payload : BinaryPayload :=
  ⟨⟨0, .low16⟩, .immediate (immediateRef 1 16 16 .none)⟩
def add16After := commitExactBinary .add add16Payload (stateWithRax (wordOfNat 1))

theorem add16_validated : validateExecutable architecture (stateWithRax (wordOfNat 1))
    formProfile AMD64.Forms.Core.addAXImm16 add16Instruction = .formResult .validated := by
  classical
  simp [validateExecutable, invalidPayloadIndices, invalidEncodingIndices,
    invalidImplicitIndices, add16Instruction, sizedInstruction, gprOperand,
    immediateOperand, immediateRef, architecture, stateWithRax, context64,
    segments, segment, cache, selector, formProfile,
    ExecutableOperand.encodingCoherent, OperandRef.Valid, GPRRef.Valid,
    ImmediateRef.Valid, GPRRegisterAvailable, AMD64.Forms.Core.addAXImm16,
    AMD64.Forms.Core.registerImmediateForm, AMD64.Forms.Core.accumulator,
    AMD64.Forms.Core.immediate, AMD64.Forms.validate]
  split
  · decide
  · rename_i missing
    exact (missing fun bit high => wordOfNat_one_high bit (by omega)).elim

example : ExecuteConditional .add add16Instruction (stateWithRax (wordOfNat 1))
    (.bodyApplied add16After) := by
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, add16Instruction,
    sizedInstruction, gprOperand, immediateOperand, immediateRef, BodyStep,
    add16After, add16Payload, GPRRef.width]
example : ExecuteReviewed architecture formProfile add16Instruction
    (stateWithRax (wordOfNat 1)) (.bodyApplied add16After) := by
  unfold ExecuteReviewed
  rw [show reviewedBinding add16Instruction.formId =
    some (.add, AMD64.Forms.Core.addAXImm16) by rfl]
  simp only
  rw [if_pos (stateWithRax_valid (wordOfNat 1)), add16_validated]
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, add16Instruction,
    sizedInstruction, gprOperand, immediateOperand, immediateRef, BodyStep,
    add16After, add16Payload, GPRRef.width]
example : unsignedValue (readGPR add16After ⟨0, .low16⟩) 16 = 2 := by decide

def add64Instruction := sizedInstruction "AMD64-F-0029" 64
  (gprOperand 0 .full64 .readWrite 1)
  { ref := .immediate (immediateBitsRef (lowOnes 32) 32 64 .sign)
    sourceText := "imm32", accessIntent := .read, evaluationOrder := 2
    registerExtension := false, byteCode4To7 := false } [.rexW]
def add64Payload : BinaryPayload :=
  ⟨⟨0, .full64⟩, .immediate (immediateBitsRef (lowOnes 32) 32 64 .sign)⟩
def add64After := commitExactBinary .add add64Payload (stateWithRax zero)

theorem add64_validated : validateExecutable architecture (stateWithRax zero)
    formProfile AMD64.Forms.Core.addRAXImm32 add64Instruction = .formResult .validated := by
  classical
  simp [validateExecutable, invalidPayloadIndices, invalidEncodingIndices,
    invalidImplicitIndices, add64Instruction, sizedInstruction, gprOperand,
    immediateBitsRef, lowOnes, architecture, stateWithRax, context64,
    segments, segment, cache, selector, formProfile,
    ExecutableOperand.encodingCoherent, OperandRef.Valid, GPRRef.Valid,
    ImmediateRef.Valid, GPRRegisterAvailable, AMD64.Forms.Core.addRAXImm32,
    AMD64.Forms.Core.registerImmediateForm, AMD64.Forms.Core.accumulator,
    AMD64.Forms.Core.immediate, AMD64.Forms.Core.prefixesForWidth,
    AMD64.Forms.Core.commonPrefixes, AMD64.Forms.Core.viewName,
    AMD64.Forms.validate]
  decide

example : ExecuteReviewed architecture formProfile add64Instruction
    (stateWithRax zero) (.bodyApplied add64After) := by
  unfold ExecuteReviewed
  rw [show reviewedBinding add64Instruction.formId =
    some (.add, AMD64.Forms.Core.addRAXImm32) by rfl]
  simp only
  rw [if_pos (stateWithRax_valid zero), add64_validated]
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, add64Instruction,
    sizedInstruction, gprOperand, immediateBitsRef, BodyStep, add64After,
    add64Payload, GPRRef.width]

def mov32Instruction := sizedInstruction "AMD64-F-0498" 32
  (gprOperand 0 .low32 .write 1) (immediateOperand 1 32 32 .none)
def mov32After := writeGPR (stateWithRax (fun _ => true)) ⟨0, .low32⟩
  (readSource (stateWithRax (fun _ => true)) (.immediate (immediateRef 1 32 32 .none)))

theorem mov32_validated : validateExecutable architecture (stateWithRax (fun _ => true))
    formProfile AMD64.Forms.Core.movReg32Imm32 mov32Instruction = .formResult .validated := by
  classical
  simp [validateExecutable, invalidPayloadIndices, invalidEncodingIndices,
    invalidImplicitIndices, mov32Instruction, sizedInstruction, gprOperand,
    immediateOperand, immediateRef, architecture, stateWithRax, context64,
    segments, segment, cache, selector, formProfile,
    ExecutableOperand.encodingCoherent, OperandRef.Valid, GPRRef.Valid,
    ImmediateRef.Valid, GPRRegisterAvailable, AMD64.Forms.Core.movReg32Imm32,
    AMD64.Forms.Core.registerImmediateForm, AMD64.Forms.Core.anyGPR,
    AMD64.Forms.Core.immediate, AMD64.Forms.validate]
  split
  · decide
  · rename_i missing
    exact (missing fun bit high => wordOfNat_one_high bit (by omega)).elim

example : ExecuteConditional .mov mov32Instruction (stateWithRax (fun _ => true))
    (.bodyApplied mov32After) := by
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, mov32Instruction,
    sizedInstruction, gprOperand, immediateOperand, immediateRef, BodyStep,
    mov32After, GPRRef.width]
example : ExecuteReviewed architecture formProfile mov32Instruction
    (stateWithRax (fun _ => true)) (.bodyApplied mov32After) := by
  unfold ExecuteReviewed
  rw [show reviewedBinding mov32Instruction.formId =
    some (.mov, AMD64.Forms.Core.movReg32Imm32) by rfl]
  simp only
  rw [if_pos (stateWithRax_valid (fun _ => true)), mov32_validated]
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, mov32Instruction,
    sizedInstruction, gprOperand, immediateOperand, immediateRef, BodyStep,
    mov32After, GPRRef.width]
example (bit : Fin 64) (upper : 32 ≤ bit.val) : mov32After.gpr 0 bit = false := by
  simp [mov32After, writeGPR, writeViewForMode, AMD64.writeView64,
    GPRView.offset, GPRView.width, stateWithRax, context64,
    show ¬bit.val < 32 by omega]

def sub64SameInstruction := sizedInstruction "conditional-sub64-same" 64
  (gprOperand 0 .full64 .readWrite 1) (gprOperand 0 .full64 .read 2) [.rexW]
def sub64SamePayload : BinaryPayload := ⟨⟨0, .full64⟩, .gpr ⟨0, .full64⟩⟩
def sub64SameAfter := commitExactBinary .sub sub64SamePayload (stateWithRax (fun _ => true))

example : ExecuteConditional .sub sub64SameInstruction (stateWithRax (fun _ => true))
    (.bodyApplied sub64SameAfter) := by
  simp [ExecuteConditional, shapeUnavailable, binaryPayload, sub64SameInstruction,
    sizedInstruction, gprOperand, BodyStep, sub64SameAfter, sub64SamePayload,
    GPRRef.width]

def readyFallthrough : FallthroughEvidence := {
  beforeIP := addAfter.rip
  instructionLength := 5
  nextIP := truncateInstructionPointer
    (addWord addAfter.rip (wordOfNat 5) false 64) 64
  fetchAcceptedAssumption := true
  synchronousEventsResolvedAssumption := true
  asynchronousEventsCheckedAssumption := true
}

theorem readyFallthrough_valid : readyFallthrough.ValidFor addAfter := by
  exact ⟨rfl, by decide, by decide, rfl⟩

def fallthroughAfter : CPUState := { addAfter with rip := readyFallthrough.nextIP }

example : ApplyFallthrough (.bodyApplied addAfter) readyFallthrough
    (.fallthroughApplied fallthroughAfter) :=
  fallthrough_sets_rip _ _ readyFallthrough_valid rfl rfl rfl
example : fallthroughAfter.rip = readyFallthrough.nextIP := by rfl
example : fallthroughAfter.gpr = addAfter.gpr := by rfl
example : fallthroughAfter.rflags = addAfter.rflags := by rfl

def pendingFallthrough : FallthroughEvidence :=
  { readyFallthrough with asynchronousEventsCheckedAssumption := false }

example : ApplyFallthrough (.bodyApplied addAfter) pendingFallthrough
    (.modelingUnavailable .fallthroughEvidencePending) := by
  right; right
  exact ⟨readyFallthrough_valid, Or.inr (Or.inr rfl), rfl⟩

def forgedFallthrough : FallthroughEvidence :=
  { readyFallthrough with beforeIP := wordOfNat 1 }

theorem forgedFallthrough_invalid : ¬forgedFallthrough.ValidFor addAfter := by
  intro valid
  have same := valid.1
  have atZero := congrFun same ⟨0, by decide⟩
  contradiction

example : ApplyFallthrough (.bodyApplied addAfter) forgedFallthrough
    (.modelingUnavailable .fallthroughCertificateInvalid) := by
  right; left
  exact ⟨forgedFallthrough_invalid, rfl⟩

def legacyWrapState : CPUState :=
  { legacyState with rip := wordOfNat 65535 }

def legacyWrapEvidence : FallthroughEvidence := {
  beforeIP := legacyWrapState.rip
  instructionLength := 1
  nextIP := truncateInstructionPointer
    (addWord legacyWrapState.rip (wordOfNat 1) false 64) 16
  fetchAcceptedAssumption := true
  synchronousEventsResolvedAssumption := true
  asynchronousEventsCheckedAssumption := true
}

example : legacyWrapEvidence.ValidFor legacyWrapState := by
  exact ⟨rfl, by decide, by decide, rfl⟩

example : unsignedValue legacyWrapEvidence.nextIP 16 = 0 := by decide
example : legacyWrapEvidence.nextIP ⟨16, by decide⟩ = false := by decide

def zeroLengthEvidence : FallthroughEvidence :=
  { readyFallthrough with instructionLength := 0 }
def longLengthEvidence : FallthroughEvidence :=
  { readyFallthrough with instructionLength := 16 }

example : ¬zeroLengthEvidence.ValidFor addAfter := by
  simp [FallthroughEvidence.ValidFor, zeroLengthEvidence]
example : ¬longLengthEvidence.ValidFor addAfter := by
  simp [FallthroughEvidence.ValidFor, longLengthEvidence]

end AMD64.IntegerExecution.Checks
