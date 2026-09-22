import AMD64.IntegerExecution

/-!
CPU/register execution for the Volume 3 shift and rotate rows.  Memory
alternatives remain explicit `memoryOperand` outcomes until MachineAccess is
available.  All operands are read from the pre-state before any destination or
flag write, including CL and overlapping BMI sources.
-/

namespace AMD64.IntegerShiftExecution

open AMD64.Arch
open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerSemantics
open AMD64.IntegerExecution

inductive Operation where
  | rcl | rcr | rol | ror | shl | shr | sar | shld | shrd
  | sarx | shlx | shrx | rorx
  deriving DecidableEq, Repr

inductive CountSource where | one | cl | immediate | register
  deriving DecidableEq, Repr

structure Binding where
  operation : Operation
  width : Nat
  countSource : CountSource
  bmi2 : Bool := false
  deriving DecidableEq, Repr

structure EncodingEvidence where
  /-- Reserved VEX.L for BMI2 forms. It must be zero. -/
  vexL : Bool := false
  /-- VEX.W must agree with the reviewed 32/64-bit row. -/
  vexW : Bool := false
  deriving DecidableEq, Repr

def widthsAndCounts : List (Nat × CountSource) :=
  [(8,.one),(8,.cl),(8,.immediate),(16,.one),(16,.cl),(16,.immediate),
   (32,.one),(32,.cl),(32,.immediate),(64,.one),(64,.cl),(64,.immediate)]

def rclIds := ["AMD64-F-0645","AMD64-F-0646","AMD64-F-0647","AMD64-F-0648",
  "AMD64-F-0649","AMD64-F-0650","AMD64-F-0651","AMD64-F-0652",
  "AMD64-F-0653","AMD64-F-0654","AMD64-F-0655","AMD64-F-0656"]
def rcrIds := ["AMD64-F-0657","AMD64-F-0658","AMD64-F-0659","AMD64-F-0660",
  "AMD64-F-0661","AMD64-F-0662","AMD64-F-0663","AMD64-F-0664",
  "AMD64-F-0665","AMD64-F-0666","AMD64-F-0667","AMD64-F-0668"]
def rolIds := ["AMD64-F-0685","AMD64-F-0686","AMD64-F-0687","AMD64-F-0688",
  "AMD64-F-0689","AMD64-F-0690","AMD64-F-0691","AMD64-F-0692",
  "AMD64-F-0693","AMD64-F-0694","AMD64-F-0695","AMD64-F-0696"]
def rorIds := ["AMD64-F-0697","AMD64-F-0698","AMD64-F-0699","AMD64-F-0700",
  "AMD64-F-0701","AMD64-F-0702","AMD64-F-0703","AMD64-F-0704",
  "AMD64-F-0705","AMD64-F-0706","AMD64-F-0707","AMD64-F-0708"]
def salIds := ["AMD64-F-0712","AMD64-F-0713","AMD64-F-0714","AMD64-F-0715",
  "AMD64-F-0716","AMD64-F-0717","AMD64-F-0718","AMD64-F-0719",
  "AMD64-F-0720","AMD64-F-0721","AMD64-F-0722","AMD64-F-0723"]
def shlIds := ["AMD64-F-0724","AMD64-F-0725","AMD64-F-0726","AMD64-F-0727",
  "AMD64-F-0728","AMD64-F-0729","AMD64-F-0730","AMD64-F-0731",
  "AMD64-F-0732","AMD64-F-0733","AMD64-F-0734","AMD64-F-0735"]
def sarIds := ["AMD64-F-0736","AMD64-F-0737","AMD64-F-0738","AMD64-F-0739",
  "AMD64-F-0740","AMD64-F-0741","AMD64-F-0742","AMD64-F-0743",
  "AMD64-F-0744","AMD64-F-0745","AMD64-F-0746","AMD64-F-0747"]
def shrIds := ["AMD64-F-0816","AMD64-F-0817","AMD64-F-0818","AMD64-F-0819",
  "AMD64-F-0820","AMD64-F-0821","AMD64-F-0822","AMD64-F-0823",
  "AMD64-F-0824","AMD64-F-0825","AMD64-F-0826","AMD64-F-0827"]

def bindingFrom12 (operation : Operation) (ids : List String)
    (formId : String) : Option Binding :=
  (ids.zip widthsAndCounts).find? (fun pair => pair.1 = formId) |>.map fun pair =>
    { operation, width := pair.2.1, countSource := pair.2.2 }

def doubleBindings : List (String × Binding) := [
  ("AMD64-F-0808",⟨.shld,16,.immediate,false⟩),("AMD64-F-0809",⟨.shld,16,.cl,false⟩),
  ("AMD64-F-0810",⟨.shld,32,.immediate,false⟩),("AMD64-F-0811",⟨.shld,32,.cl,false⟩),
  ("AMD64-F-0812",⟨.shld,64,.immediate,false⟩),("AMD64-F-0813",⟨.shld,64,.cl,false⟩),
  ("AMD64-F-0828",⟨.shrd,16,.immediate,false⟩),("AMD64-F-0829",⟨.shrd,16,.cl,false⟩),
  ("AMD64-F-0830",⟨.shrd,32,.immediate,false⟩),("AMD64-F-0831",⟨.shrd,32,.cl,false⟩),
  ("AMD64-F-0832",⟨.shrd,64,.immediate,false⟩),("AMD64-F-0833",⟨.shrd,64,.cl,false⟩)]

def bmiBindings : List (String × Binding) := [
  ("AMD64-F-0748",⟨.sarx,32,.register,true⟩),
  ("AMD64-F-0749",⟨.sarx,64,.register,true⟩),
  ("AMD64-F-0814",⟨.shlx,32,.register,true⟩),
  ("AMD64-F-0815",⟨.shlx,64,.register,true⟩),
  ("AMD64-F-0834",⟨.shrx,32,.register,true⟩),
  ("AMD64-F-0835",⟨.shrx,64,.register,true⟩),
  ("AMD64-F-0709",⟨.rorx,32,.immediate,true⟩),
  ("AMD64-F-0710",⟨.rorx,64,.immediate,true⟩)]

def reviewedFormIds : List String :=
  rclIds ++ rcrIds ++ rolIds ++ rorIds ++ salIds ++ shlIds ++ sarIds ++ shrIds ++
  doubleBindings.map (·.1) ++ bmiBindings.map (·.1)

def BindingFor (formId : String) : Option Binding :=
  (bindingFrom12 .rcl rclIds formId).orElse fun _ =>
  (bindingFrom12 .rcr rcrIds formId).orElse fun _ =>
  (bindingFrom12 .rol rolIds formId).orElse fun _ =>
  (bindingFrom12 .ror rorIds formId).orElse fun _ =>
  (bindingFrom12 .shl salIds formId).orElse fun _ =>
  (bindingFrom12 .shl shlIds formId).orElse fun _ =>
  (bindingFrom12 .sar sarIds formId).orElse fun _ =>
  (bindingFrom12 .shr shrIds formId).orElse fun _ =>
  (doubleBindings.find? (fun pair => pair.1 = formId) |>.map (·.2)).orElse fun _ =>
  bmiBindings.find? (fun pair => pair.1 = formId) |>.map (·.2)

def protectedFamily : OperatingMode → Bool
  | .protectedMode | .compatibility | .long64 => true
  | .real | .virtual8086 => false

def allowedLegacyPrefixes : List Prefix :=
  [.rep,.repne,.operandSize,.addressSize,.cs,.ss,.ds,.es,.fs,.gs,.rex,.rexW]
def allowedVexPrefixes : List Prefix := [.addressSize,.cs,.ss,.ds,.es,.fs,.gs]

def prefixesAllowed (binding : Binding) (instruction : ExecutableInstruction) : Bool :=
  let allowed := if binding.bmi2 then allowedVexPrefixes else allowedLegacyPrefixes
  instruction.prefixes.all allowed.contains && !instruction.prefixes.contains .lock &&
  (if binding.width = 64 ∧ !binding.bmi2 then instruction.prefixes.contains .rexW
   else !instruction.prefixes.contains .rexW)

def modeAllowed (binding : Binding) (mode : OperatingMode) : Bool :=
  (binding.width != 64 || mode == .long64) &&
  (!binding.bmi2 || protectedFamily mode)

def encodingAllowed (binding : Binding) (instruction : ExecutableInstruction)
    (evidence : EncodingEvidence) : Bool :=
  if binding.bmi2 then
    instruction.encodingFamily == .vex && !evidence.vexL &&
      evidence.vexW == (binding.width == 64)
  else instruction.encodingFamily == .legacy

def countValue (state : CPUState) : CountSource → OperandRef → Option Nat
  | .one, .constant value _ => if value = 1 then some 1 else none
  | .cl, .gpr register =>
      if register.index.val = 1 ∧ register.view = .low8
      then some (unsignedValue (readGPR state register) 8) else none
  | .immediate, .immediate value =>
      if value.encodedWidth = 8 then some (unsignedValue value.value 8) else none
  | .register, .gpr register => some (unsignedValue (readGPR state register) register.width)
  | _, _ => none

structure Payload where
  destination : GPRRef
  source : Option GPRRef := none
  rawCount : Nat
  deriving DecidableEq, Repr

def payload (binding : Binding) (instruction : ExecutableInstruction)
    (before : CPUState) : Payload ⊕ UnavailableReason :=
  match instruction.operands with
  | [destinationOperand, countOperand] =>
      if binding.operation ∈ [.shld,.shrd,.sarx,.shlx,.shrx,.rorx]
      then .inr .operandShape else
      match destinationOperand.ref with
      | .memory _ width => if width = binding.width then .inr .memoryOperand
                           else .inr .widthMismatch
      | .gpr destination =>
          if destination.width ≠ binding.width then .inr .widthMismatch else
          match countValue before binding.countSource countOperand.ref with
          | some count => .inl ⟨destination, none, count⟩
          | none => .inr .operandShape
      | _ => .inr .operandShape
  | [destinationOperand, sourceOperand, countOperand] =>
      if binding.operation ∉ [.shld,.shrd,.sarx,.shlx,.shrx,.rorx]
      then .inr .operandShape else
      match destinationOperand.ref with
      | .memory _ width => if width = binding.width then .inr .memoryOperand
                           else .inr .widthMismatch
      | .gpr destination =>
          if destination.width ≠ binding.width then .inr .widthMismatch else
          if binding.countSource == .register &&
              !(match countOperand.ref with
                | .gpr count => count.width == binding.width | _ => false)
          then .inr .widthMismatch else
          match sourceOperand.ref,
            countValue before binding.countSource countOperand.ref with
          | .gpr source, some count =>
              if source.width = binding.width then .inl ⟨destination, some source, count⟩
              else .inr .widthMismatch
          | .memory _ width, _ => if width = binding.width then .inr .memoryOperand
                                  else .inr .widthMismatch
          | _, _ => .inr .operandShape
      | _ => .inr .operandShape
  | _ => .inr .operandShape

def doubleShiftEffects (kind : DoubleShiftKind) (destination result : IWord)
    (width rawCount : Nat) : FlagEffects :=
  let count := maskedCount rawCount width
  let defined := count ≤ width
  if count = 0 then
    { cf := .preserve, pf := .preserve, af := .preserve,
      zf := .preserve, sf := .preserve, of := .preserve }
  else
    { cf := if defined then .exact (match kind with
        | .shld => getBit destination (width-count)
        | .shrd => getBit destination (count-1)) else .undefined
      pf := if defined then .exact (parityEven result) else .undefined
      af := .undefined
      zf := if defined then .exact (isZero result width) else .undefined
      sf := if defined then .exact (getBit result (width-1)) else .undefined
      of := if count = 1 ∧ defined then .exact (match kind with
        | .shld => Bool.xor (getBit result (width-1)) (getBit destination (width-1))
        | .shrd => Bool.xor (getBit destination (width-1)) (getBit result (width-1)))
        else .undefined }

def writeWithEffects (before : CPUState) (destination : GPRRef) (value : IWord)
    (effects : FlagEffects) (after : CPUState) : Prop :=
  ∃ valued status,
    WriteGPRAllowed before destination value valued ∧
    EffectsPermit effects (projectStatusFlags before.rflags) status ∧
    after = writeStatus valued status

def BodyStep (binding : Binding) (payload : Payload) (before after : CPUState) : Prop :=
  let destinationValue := readGPR before payload.destination
  let width := binding.width
  let count := maskedCount payload.rawCount width
  if !binding.bmi2 && count = 0 then after = before else
  match binding.operation with
  | .shl | .shr | .sar =>
      let kind := match binding.operation with
        | .shl => ShiftKind.shl
        | .shr => .shr
        | _ => .sar
      let value := shiftValue kind destinationValue width count
      writeWithEffects before payload.destination value
        (shiftEffects kind destinationValue value width payload.rawCount) after
  | .rol | .ror =>
      let kind := if binding.operation = .rol then RotateKind.rol else .ror
      let value := rotateValue kind destinationValue width (count % width)
      writeWithEffects before payload.destination value
        (rotateEffects kind value width payload.rawCount) after
  | .rcl | .rcr =>
      let kind := if binding.operation = .rcl then CarryRotateKind.rcl else .rcr
      let oldCF := before.rflags.cf
      let ringCount := count % (width + 1)
      let value := carryRotateValue kind destinationValue oldCF width ringCount
      let newCF := carryRotateCF kind destinationValue oldCF width ringCount
      writeWithEffects before payload.destination value
        (carryRotateEffects kind value newCF width payload.rawCount) after
  | .shld | .shrd =>
      let kind := if binding.operation = .shld then DoubleShiftKind.shld else .shrd
      match payload.source with
      | some source =>
          let sourceValue := readGPR before source
          ∃ candidate, doubleShiftAllowed kind destinationValue sourceValue width
              payload.rawCount candidate ∧
            writeWithEffects before payload.destination candidate
              (doubleShiftEffects kind destinationValue candidate width payload.rawCount) after
      | none => False
  | .sarx | .shlx | .shrx | .rorx =>
      match payload.source with
      | some source =>
          let sourceValue := readGPR before source
          let value := match binding.operation with
            | .sarx => shiftValue .sar sourceValue width count
            | .shlx => shiftValue .shl sourceValue width count
            | .shrx => shiftValue .shr sourceValue width count
            | .rorx => rotateValue .ror sourceValue width (count % width)
            | _ => sourceValue
          WriteGPRAllowed before payload.destination value after
      | none => False

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
          !prefixesAllowed binding instruction ||
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
      else match payload binding instruction before with
        | .inr .memoryOperand => outcome = .modelingUnavailable .memoryOperand
        | .inr _ => outcome = .validationRejected
        | .inl operands => match outcome with
          | .bodyApplied after => BodyStep binding operands before after
          | _ => False

end AMD64.IntegerShiftExecution
