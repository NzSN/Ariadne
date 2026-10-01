---------------------- MODULE MachineStateReplay ----------------------
EXTENDS AriadneMachineCommon
CONSTANT
  \* @type: Str;
  Case
VARIABLES
  \* @type: Str;
  case_id,
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

Inputs == INSTANCE MachineStateCases
Engine == INSTANCE AriadneMachineState WITH
  SnapshotId <- Inputs!Snapshot, Nodes <- Inputs!Nodes, EntryPoints <- Inputs!Roots,
  Locations <- Inputs!Locations, ValueDomain <- Inputs!Domains, StateIds <- Inputs!States,
  Valuation <- Inputs!Valuations, StateStatus <- Inputs!Statuses, InitialStates <- Inputs!Entries,
  StructuralEdges <- Inputs!Edges, Uses <- Inputs!Uses, MustDefs <- Inputs!MustDefs,
  MayDefs <- Inputs!MayDefs, StateSteps <- Inputs!Steps, TerminalTransitions <- Inputs!Terminals,
  CompleteSites <- Inputs!Complete, AdapterObligations <- Inputs!Obligations
Ready == {a \in Inputs!Nodes : ~(Engine!Incoming(a) \subseteq statesAt[a])}
Least(addresses) == CHOOSE a \in addresses : \A b \in addresses : a <= b

Views ==
  /\ snapshot_id = Inputs!Snapshot
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
Init == Case \in Inputs!Cases /\ Engine!Init /\ case_id = Case /\ Views /\ action_taken = "init" /\ parameters = [fixture |-> Case]
Propagate ==
  /\ Ready # {}
  /\ Engine!Propagate(Least(Ready))
  /\ UpdateViews
  /\ action_taken' = "propagate"
  /\ UNCHANGED <<parameters, case_id>>
FinishStateflow ==
  /\ Engine!FinishStateflow
  /\ UpdateViews
  /\ action_taken' = "finishStateflow"
  /\ UNCHANGED <<parameters, case_id>>
Next == Propagate \/ FinishStateflow
vars == <<case_id, phase, statesAt, snapshot_id, structural_edges, feasible_edges,
          infeasible_edges, unknown_edges, terminals, not_reached, obligations,
          action_taken, parameters>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == Engine!TypeOK /\ Engine!StateflowInvariant /\ Engine!ResultInvariant /\ Views
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
TypeWitness == FALSE
TypeCase == Case = "MachineStateReplay"
HighCase == Case = "MSHighVA"
=============================================================================
