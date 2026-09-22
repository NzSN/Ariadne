import AMD64.IntegerExecution

/-!
Long-mode CPL3 register execution for common integer forms. Source reg/mem
rows retain their memory alternative, which is reported as unavailable.
-/
namespace AMD64.IntegerCommonExecution

open AMD64.Arch
open AMD64.Forms
open AMD64.Operands
open AMD64.IntegerExecution

inductive SourceShape where | immediate | registerOrMemory | none
  deriving DecidableEq, Repr

structure Binding where
  operation : Operation
  width : Nat
  sourceShape : SourceShape
  encodedWidth : Nat := 0
  extension : ImmediateExtension := .none
  accumulator : Bool := false
  destinationAccess : AccessIntent := .readWrite
  deriving DecidableEq, Repr

def arithmeticShapes : List (Nat × SourceShape × Nat × ImmediateExtension × Bool) := [
  (8,.immediate,8,.none,true),(16,.immediate,16,.none,true),
  (32,.immediate,32,.none,true),(64,.immediate,32,.sign,true),
  (8,.immediate,8,.none,false),(16,.immediate,16,.none,false),
  (32,.immediate,32,.none,false),(64,.immediate,32,.sign,false),
  (16,.immediate,8,.sign,false),(32,.immediate,8,.sign,false),
  (64,.immediate,8,.sign,false),
  (8,.registerOrMemory,0,.none,false),(16,.registerOrMemory,0,.none,false),
  (32,.registerOrMemory,0,.none,false),(64,.registerOrMemory,0,.none,false),
  (8,.registerOrMemory,0,.none,false),(16,.registerOrMemory,0,.none,false),
  (32,.registerOrMemory,0,.none,false),(64,.registerOrMemory,0,.none,false)]

def adcIds := ["AMD64-F-0005","AMD64-F-0006","AMD64-F-0007","AMD64-F-0008",
  "AMD64-F-0009","AMD64-F-0010","AMD64-F-0011","AMD64-F-0012","AMD64-F-0013",
  "AMD64-F-0014","AMD64-F-0015","AMD64-F-0016","AMD64-F-0017","AMD64-F-0018",
  "AMD64-F-0019","AMD64-F-0020","AMD64-F-0021","AMD64-F-0022","AMD64-F-0023"]
def addIds := ["AMD64-F-0026","AMD64-F-0027","AMD64-F-0028","AMD64-F-0029",
  "AMD64-F-0030","AMD64-F-0031","AMD64-F-0032","AMD64-F-0033","AMD64-F-0034",
  "AMD64-F-0035","AMD64-F-0036","AMD64-F-0037","AMD64-F-0038","AMD64-F-0039",
  "AMD64-F-0040","AMD64-F-0041","AMD64-F-0042","AMD64-F-0043","AMD64-F-0044"]
def andIds := ["AMD64-F-0047","AMD64-F-0048","AMD64-F-0049","AMD64-F-0050",
  "AMD64-F-0051","AMD64-F-0052","AMD64-F-0053","AMD64-F-0054","AMD64-F-0055",
  "AMD64-F-0056","AMD64-F-0057","AMD64-F-0058","AMD64-F-0059","AMD64-F-0060",
  "AMD64-F-0061","AMD64-F-0062","AMD64-F-0063","AMD64-F-0064","AMD64-F-0065"]
def cmpIds := ["AMD64-F-0240","AMD64-F-0241","AMD64-F-0242","AMD64-F-0243",
  "AMD64-F-0244","AMD64-F-0245","AMD64-F-0246","AMD64-F-0247","AMD64-F-0248",
  "AMD64-F-0249","AMD64-F-0250","AMD64-F-0251","AMD64-F-0252","AMD64-F-0253",
  "AMD64-F-0254","AMD64-F-0255","AMD64-F-0256","AMD64-F-0257","AMD64-F-0258"]
def orIds := ["AMD64-F-0561","AMD64-F-0562","AMD64-F-0563","AMD64-F-0564",
  "AMD64-F-0565","AMD64-F-0566","AMD64-F-0567","AMD64-F-0568","AMD64-F-0569",
  "AMD64-F-0570","AMD64-F-0571","AMD64-F-0572","AMD64-F-0573","AMD64-F-0574",
  "AMD64-F-0575","AMD64-F-0576","AMD64-F-0577","AMD64-F-0578","AMD64-F-0579"]
def sbbIds := ["AMD64-F-0750","AMD64-F-0751","AMD64-F-0752","AMD64-F-0753",
  "AMD64-F-0754","AMD64-F-0755","AMD64-F-0756","AMD64-F-0757","AMD64-F-0758",
  "AMD64-F-0759","AMD64-F-0760","AMD64-F-0761","AMD64-F-0762","AMD64-F-0763",
  "AMD64-F-0764","AMD64-F-0765","AMD64-F-0766","AMD64-F-0767","AMD64-F-0768"]
def subIds := ["AMD64-F-0848","AMD64-F-0849","AMD64-F-0850","AMD64-F-0851",
  "AMD64-F-0852","AMD64-F-0853","AMD64-F-0854","AMD64-F-0855","AMD64-F-0856",
  "AMD64-F-0857","AMD64-F-0858","AMD64-F-0859","AMD64-F-0860","AMD64-F-0861",
  "AMD64-F-0862","AMD64-F-0863","AMD64-F-0864","AMD64-F-0865","AMD64-F-0866"]
def xorIds := ["AMD64-F-0913","AMD64-F-0914","AMD64-F-0915","AMD64-F-0916",
  "AMD64-F-0917","AMD64-F-0918","AMD64-F-0919","AMD64-F-0920","AMD64-F-0921",
  "AMD64-F-0922","AMD64-F-0923","AMD64-F-0924","AMD64-F-0925","AMD64-F-0926",
  "AMD64-F-0927","AMD64-F-0928","AMD64-F-0929","AMD64-F-0930","AMD64-F-0931"]

def accessFor (operation : Operation) : AccessIntent :=
  if operation ∈ [.cmp,.test] then .read else if operation = .mov then .write else .readWrite

def bindings19 (operation : Operation) (ids : List String) : List (String × Binding) :=
  (ids.zip arithmeticShapes).map fun pair => (pair.1, {
    operation, width := pair.2.1, sourceShape := pair.2.2.1,
    encodedWidth := pair.2.2.2.1, extension := pair.2.2.2.2.1,
    accumulator := pair.2.2.2.2.2, destinationAccess := accessFor operation })

def testBindings : List (String × Binding) :=
  let ids := ["AMD64-F-0869","AMD64-F-0870","AMD64-F-0871","AMD64-F-0872",
    "AMD64-F-0873","AMD64-F-0874","AMD64-F-0875","AMD64-F-0876",
    "AMD64-F-0877","AMD64-F-0878","AMD64-F-0879","AMD64-F-0880"]
  let shapes := arithmeticShapes.take 8 ++ (arithmeticShapes.drop 11 |>.take 4)
  (ids.zip shapes).map fun pair => (pair.1, {
    operation := .test, width := pair.2.1, sourceShape := pair.2.2.1,
    encodedWidth := pair.2.2.2.1, extension := pair.2.2.2.2.1,
    accumulator := pair.2.2.2.2.2, destinationAccess := .read })

def movBindings : List (String × Binding) := [
  ("AMD64-F-0478",⟨.mov,8,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0479",⟨.mov,16,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0480",⟨.mov,32,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0481",⟨.mov,64,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0482",⟨.mov,8,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0483",⟨.mov,16,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0484",⟨.mov,32,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0485",⟨.mov,64,.registerOrMemory,0,.none,false,.write⟩),
  ("AMD64-F-0496",⟨.mov,8,.immediate,8,.none,false,.write⟩),
  ("AMD64-F-0497",⟨.mov,16,.immediate,16,.none,false,.write⟩),
  ("AMD64-F-0498",⟨.mov,32,.immediate,32,.none,false,.write⟩),
  ("AMD64-F-0499",⟨.mov,64,.immediate,64,.none,false,.write⟩),
  ("AMD64-F-0500",⟨.mov,8,.immediate,8,.none,false,.write⟩),
  ("AMD64-F-0501",⟨.mov,16,.immediate,16,.none,false,.write⟩),
  ("AMD64-F-0502",⟨.mov,32,.immediate,32,.none,false,.write⟩),
  ("AMD64-F-0503",⟨.mov,64,.immediate,32,.sign,false,.write⟩)]

def unaryBindings : List (String × Binding) := [
  ("AMD64-F-0282",⟨.dec,8,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0283",⟨.dec,16,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0284",⟨.dec,32,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0285",⟨.dec,64,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0318",⟨.inc,8,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0319",⟨.inc,16,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0320",⟨.inc,32,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0321",⟨.inc,64,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0549",⟨.neg,8,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0550",⟨.neg,16,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0551",⟨.neg,32,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0552",⟨.neg,64,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0557",⟨.not,8,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0558",⟨.not,16,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0559",⟨.not,32,.none,0,.none,false,.readWrite⟩),
  ("AMD64-F-0560",⟨.not,64,.none,0,.none,false,.readWrite⟩)]

def bindings : List (String × Binding) :=
  bindings19 .adc adcIds ++ bindings19 .add addIds ++ bindings19 .and andIds ++
  bindings19 .cmp cmpIds ++ bindings19 .or orIds ++ bindings19 .sbb sbbIds ++
  bindings19 .sub subIds ++ bindings19 .xor xorIds ++ testBindings ++ movBindings ++ unaryBindings

def reviewedFormIds := bindings.map (·.1)
def BindingFor (formId : String) : Option Binding :=
  bindings.find? (fun pair => pair.1 = formId) |>.map (·.2)

/-- Immediate milestone: register/register instances of reg/mem rows. Accumulator
immediates and unary rows are already paired in IntegerExecution. -/
def milestoneBindings := bindings.filter (fun pair => pair.2.sourceShape == .registerOrMemory)
def milestoneFormIds := milestoneBindings.map (·.1)
def MilestoneBindingFor (formId : String) : Option Binding :=
  milestoneBindings.find? (fun pair => pair.1 = formId) |>.map (·.2)

def viewMatchesWidth (register : GPRRef) (width : Nat) : Bool := register.width = width
def accumulatorMatches (register : GPRRef) (binding : Binding) : Bool :=
  !binding.accumulator || register.index.val = 0

def payloadValid (binding : Binding) (instruction : ExecutableInstruction) : Bool :=
  match binding.sourceShape, instruction.operands with
  | .none, [destination] => match destination.ref with
    | .gpr register => viewMatchesWidth register binding.width &&
        destination.accessIntent == binding.destinationAccess
    | .memory _ width => width = binding.width
    | _ => false
  | .immediate, [destination, source] =>
      let destinationOK := match destination.ref with
        | .gpr register => viewMatchesWidth register binding.width &&
            accumulatorMatches register binding
        | .memory _ width => width = binding.width && !binding.accumulator
        | _ => false
      let sourceOK := match source.ref with
        | .immediate immediate => immediate.encodedWidth = binding.encodedWidth &&
            immediate.semanticWidth = binding.width && immediate.extension == binding.extension
        | _ => false
      destinationOK && sourceOK && destination.accessIntent == binding.destinationAccess &&
        source.accessIntent == .read
  | .registerOrMemory, [destination, source] =>
      let destinationOK := match destination.ref with
        | .gpr register => viewMatchesWidth register binding.width
        | .memory _ width => width = binding.width
        | _ => false
      let sourceOK := match source.ref with
        | .gpr register => viewMatchesWidth register binding.width
        | .memory _ width => width = binding.width
        | _ => false
      destinationOK && sourceOK && destination.accessIntent == binding.destinationAccess &&
        source.accessIntent == .read
  | _, _ => false

def hasMemory (instruction : ExecutableInstruction) : Bool :=
  instruction.operands.any fun operand => match operand.ref with
    | .memory .. => true | _ => false

noncomputable def Execute (architecture : Arch.ArchitectureProfile)
    (formProfile : AMD64.Forms.ArchitectureProfile) (instruction : ExecutableInstruction)
    (before : CPUState) (outcome : Outcome) : Prop := by
  classical
  exact match MilestoneBindingFor instruction.formId with
  | none => outcome = .modelingUnavailable .formBindingPending
  | some binding =>
      if ¬ValidCPUState architecture before then outcome = .validationRejected
      else if before.execution.mode != .long64 || before.execution.cpl.val != 3 ||
          !formProfile.modes.contains .long64 || instruction.operandSize ≠ binding.width ||
          instruction.encodingFamily != .legacy || instruction.prefixes.contains .lock ||
          (binding.width = 64 && !instruction.prefixes.contains .rexW) ||
          (binding.width != 64 && instruction.prefixes.contains .rexW) ||
          !payloadValid binding instruction ||
          !(invalidPayloadIndices architecture before.execution before.segments
            instruction.operands).isEmpty ||
          !(invalidEncodingIndices before.execution instruction).isEmpty ||
          !instruction.implicitResources.isEmpty then outcome = .validationRejected
      else if hasMemory instruction then outcome = .modelingUnavailable .memoryOperand
      else ExecuteConditional binding.operation instruction before outcome

end AMD64.IntegerCommonExecution
