------------------------- MODULE LLVMIRReplay -------------------------
EXTENDS AriadneTypes, Naturals, FiniteSets
CONSTANT
  \* @type: Str;
  Case
VARIABLES
  \* @type: Str;
  case_id,
  \* @type: Str;
  phase,
  \* @type: Set(Str);
  slice,
  \* @type: Str;
  artifact_id,
  \* @type: Str;
  module_id,
  \* @type: Str;
  function_id,
  \* @type: Set({src: Str, dst: Str, kind: Str});
  control_graph,
  \* @type: Set({site: Str, callee: Str, kind: Str});
  call_graph,
  \* @type: Str -> Set(Str);
  dependency_preds,
  \* @type: Set({site: Str, reason: Str});
  obligations,
  \* @type: Str;
  action_taken,
  \* @type: {fixture: Str};
  parameters

Inputs == INSTANCE LLVMIRCases
Engine == INSTANCE AriadneLLVMIR WITH
  ArtifactId <- Inputs!Artifact, ModuleId <- Inputs!Module, FunctionId <- Inputs!Function,
  VerifiedIR <- Inputs!Verified, Blocks <- Inputs!Blocks, EntryBlock <- Inputs!Entry,
  Instructions <- Inputs!Instructions, BlockOf <- Inputs!BlockOf, InstructionIndex <- Inputs!Index,
  Terminator <- Inputs!Terminators, TermInfo <- Inputs!TermInfo, Values <- Inputs!Values,
  ValueKind <- Inputs!ValueKind, DefSite <- Inputs!DefSite, Uses <- Inputs!Uses,
  PhiNodes <- Inputs!PhiNodes, PhiIncoming <- Inputs!PhiIncoming, MemoryPreds <- Inputs!MemoryPreds,
  CallSites <- Inputs!CallSites, Callees <- Inputs!Callees, CallTargets <- Inputs!CallTargets,
  CompleteCalls <- Inputs!CompleteCalls, AdapterObligations <- Inputs!Obligations, SliceSeeds <- Inputs!Seeds
Views ==
  /\ artifact_id = Inputs!Artifact
  /\ module_id = Inputs!Module
  /\ function_id = Inputs!Function
  /\ control_graph = Engine!ControlGraph
  /\ call_graph = Engine!CallGraph
  /\ dependency_preds = [i \in Inputs!Instructions |-> Engine!DependencyPreds(i)]
  /\ obligations = Engine!Obligations
Init == Case \in Inputs!Cases /\ Engine!Init /\ case_id = Case /\ Views /\ action_taken = "init" /\ parameters = [fixture |-> Case]
ExpandSlice ==
  /\ Engine!ExpandSlice /\ UNCHANGED <<artifact_id, module_id, function_id, control_graph, call_graph, dependency_preds, obligations>>
  /\ action_taken' = "expandSlice" /\ UNCHANGED <<parameters, case_id>>
FinishSlice ==
  /\ Engine!FinishSlice /\ UNCHANGED <<artifact_id, module_id, function_id, control_graph, call_graph, dependency_preds, obligations>>
  /\ action_taken' = "finishSlice" /\ UNCHANGED <<parameters, case_id>>
Next == ExpandSlice \/ FinishSlice
vars == <<case_id, phase, slice, artifact_id, module_id, function_id, control_graph,
          call_graph, dependency_preds, obligations, action_taken, parameters>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == Engine!TypeOK /\ Engine!CFGInvariant /\ Engine!DependencyInvariant /\ Engine!ResultInvariant /\ Views
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
TypeWitness == FALSE
TypeCase == Case = "LLVMIRReplay"
=============================================================================
