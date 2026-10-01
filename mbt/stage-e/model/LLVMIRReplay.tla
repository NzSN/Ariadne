------------------------- MODULE LLVMIRReplay -------------------------
EXTENDS AriadneTypes, Naturals, FiniteSets
VARIABLES
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

Example == INSTANCE AriadneLLVMIRExample
Engine == INSTANCE AriadneLLVMIR WITH
  ArtifactId <- "fixture.bc.sha256",
  ModuleId <- "fixture-module",
  FunctionId <- "fixture-function",
  VerifiedIR <- TRUE,
  Blocks <- Example!Blocks,
  EntryBlock <- "entry",
  Instructions <- Example!Instructions,
  BlockOf <- Example!InstructionBlocks,
  InstructionIndex <- Example!Indices,
  Terminator <- Example!Terminators,
  TermInfo <- Example!TerminatorsInfo,
  Values <- Example!Values,
  ValueKind <- Example!KindsOfValues,
  DefSite <- Example!DefinitionSites,
  Uses <- Example!InstructionUses,
  PhiNodes <- {"join.phi"},
  PhiIncoming <- Example!PhiInputs,
  MemoryPreds <- Example!MemoryDependencies,
  CallSites <- {"join.call"},
  Callees <- {"possible.callee"},
  CallTargets <- Example!Targets,
  CompleteCalls <- {},
  AdapterObligations <- Example!NoAdapterObligations,
  SliceSeeds <- {"join.ret"}
Views ==
  /\ artifact_id = "fixture.bc.sha256"
  /\ module_id = "fixture-module"
  /\ function_id = "fixture-function"
  /\ control_graph = Engine!ControlGraph
  /\ call_graph = Engine!CallGraph
  /\ dependency_preds = [i \in Example!Instructions |-> Engine!DependencyPreds(i)]
  /\ obligations = Engine!Obligations
Init == Example!Init /\ Views /\ action_taken = "init" /\ parameters = [fixture |-> "LLVMIRReplay"]
ExpandSlice ==
  /\ Engine!ExpandSlice /\ UNCHANGED <<artifact_id, module_id, function_id, control_graph, call_graph, dependency_preds, obligations>>
  /\ action_taken' = "expandSlice" /\ UNCHANGED parameters
FinishSlice ==
  /\ Engine!FinishSlice /\ UNCHANGED <<artifact_id, module_id, function_id, control_graph, call_graph, dependency_preds, obligations>>
  /\ action_taken' = "finishSlice" /\ UNCHANGED parameters
Next == ExpandSlice \/ FinishSlice
vars == <<phase, slice, artifact_id, module_id, function_id, control_graph,
          call_graph, dependency_preds, obligations, action_taken, parameters>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == Example!Safety /\ Views
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
TypeWitness == FALSE
=============================================================================
