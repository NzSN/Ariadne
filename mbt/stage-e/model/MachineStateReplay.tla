---------------------- MODULE MachineStateReplay ----------------------
EXTENDS AriadneMachineCommon
VARIABLES
  \* @type: Str;
  phase,
  \* @type: Int -> Set(Str);
  statesAt,
  \* @type: Str;
  snapshot_id,
  \* @type: Set({src: Int, dst: Int, kind: Str});
  structural_edges,
  \* @type: Set({src: Int, dst: Int, kind: Str});
  feasible_edges,
  \* @type: Set({src: Int, dst: Int, kind: Str});
  infeasible_edges,
  \* @type: Set({src: Int, dst: Int, kind: Str});
  unknown_edges,
  \* @type: Set({site: Int, before: Str, after: Str, outcome: Str});
  terminals,
  \* @type: Set(Int);
  not_reached,
  \* @type: Set({site: Int, reason: Str});
  obligations,
  \* @type: Str;
  action_taken,
  \* @type: {fixture: Str};
  parameters

Example == INSTANCE AriadneMachineStateExample
Engine == INSTANCE AriadneMachineState WITH
  SnapshotId <- "machine-state-snapshot",
  Nodes <- Example!Nodes,
  EntryPoints <- {1},
  Locations <- Example!Locations,
  ValueDomain <- Example!Domains,
  StateIds <- Example!States,
  Valuation <- Example!Values,
  StateStatus <- Example!Statuses,
  InitialStates <- Example!EntryStates,
  StructuralEdges <- Example!Edges,
  Uses <- Example!InstructionUses,
  MustDefs <- Example!InstructionMustDefs,
  MayDefs <- Example!InstructionMayDefs,
  StateSteps <- Example!Steps,
  TerminalTransitions <- Example!Terminals,
  CompleteSites <- Example!Nodes,
  AdapterObligations <- Example!NoAdapterObligations
Ready == {a \in Example!Nodes : ~(Engine!Incoming(a) \subseteq statesAt[a])}
Least(addresses) == CHOOSE a \in addresses : \A b \in addresses : a <= b

Views ==
  /\ snapshot_id = "machine-state-snapshot"
  /\ structural_edges = Engine!StructuralGraph
  /\ feasible_edges = Engine!FeasibleEdges
  /\ infeasible_edges = Engine!ProvablyInfeasibleEdges
  /\ unknown_edges = Engine!UnknownFeasibilityEdges
  /\ terminals = Engine!ReachedTerminalTransitions
  /\ not_reached = Engine!UnreachableNodes
  /\ obligations = Engine!Obligations

UpdateViews ==
  /\ feasible_edges' = Engine!FeasibleEdges'
  /\ infeasible_edges' = Engine!ProvablyInfeasibleEdges'
  /\ unknown_edges' = Engine!UnknownFeasibilityEdges'
  /\ terminals' = Engine!ReachedTerminalTransitions'
  /\ not_reached' = Engine!UnreachableNodes'
  /\ UNCHANGED <<snapshot_id, structural_edges, obligations>>
Init == Example!Init /\ Views /\ action_taken = "init" /\ parameters = [fixture |-> "MachineStateReplay"]
Propagate ==
  /\ Ready # {}
  /\ Engine!Propagate(Least(Ready))
  /\ UpdateViews
  /\ action_taken' = "propagate"
  /\ UNCHANGED parameters
FinishStateflow ==
  /\ Engine!FinishStateflow
  /\ UpdateViews
  /\ action_taken' = "finishStateflow"
  /\ UNCHANGED parameters
Next == Propagate \/ FinishStateflow
vars == <<phase, statesAt, snapshot_id, structural_edges, feasible_edges,
          infeasible_edges, unknown_edges, terminals, not_reached, obligations,
          action_taken, parameters>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == Example!Safety /\ Views
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
TypeWitness == FALSE
=============================================================================
