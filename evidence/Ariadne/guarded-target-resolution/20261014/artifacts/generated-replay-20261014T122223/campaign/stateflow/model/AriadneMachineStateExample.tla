-------------------- MODULE AriadneMachineStateExample --------------------
EXTENDS AriadneMachineCommon

\* A finite abstract execution:
\*   1 sets RAX to 5; 2 establishes ZF=true; 3 branches to 4, not 5.
\* The structural CFG retains both branch edges. State analysis classifies the
\* taken edge as feasible and the fallthrough edge as provably infeasible under
\* the supplied entry state. Both exits have terminal return semantics.
VARIABLES
  \* @type: $analysisPhase;
  phase,
  \* @type: $address -> Set($abstractStateId);
  statesAt

Nodes == 1..5
Locations == {"rax", "zf"}
States == {"entry", "rax-five", "zf-true", "returned"}

\* @type: $location -> Set($abstractValue);
Domains == [location \in Locations |->
  IF location = "rax" THEN {"zero", "five", "other"}
  ELSE {"false", "true"}]

\* @type: $abstractStateId -> ($location -> Set($abstractValue));
Values == [state \in States |->
  IF state = "entry"
  THEN [location \in Locations |-> Domains[location]]
  ELSE [location \in Locations |->
          IF location = "rax" THEN {"five"}
          ELSE IF state = "rax-five" THEN {"false", "true"} ELSE {"true"}]]

\* @type: $abstractStateId -> $machineStatus;
Statuses == [state \in States |->
  IF state = "returned" THEN "returned" ELSE "running"]

\* @type: $address -> Set($abstractStateId);
EntryStates == [a \in Nodes |-> IF a = 1 THEN {"entry"} ELSE {}]

\* @type: ($address, $address, $edgeKind)
\*          => {src: $address, dst: $address, kind: $edgeKind};
E(src, dst, kind) == [src |-> src, dst |-> dst, kind |-> kind]
Edges ==
  {E(1, 2, "next"), E(2, 3, "next"), E(3, 4, "taken"),
   E(3, 5, "fallthrough")}

\* @type: $address -> Set($location);
InstructionUses == [a \in Nodes |->
  CASE a = 2 -> {"rax"}
    [] a = 3 -> {"zf"}
    [] OTHER -> {}]
\* @type: $address -> Set($location);
InstructionMustDefs == [a \in Nodes |->
  CASE a = 1 -> {"rax"}
    [] a = 2 -> {"zf"}
    [] OTHER -> {}]
\* @type: $address -> Set($location);
InstructionMayDefs == InstructionMustDefs

\* @type: ($address, $abstractStateId, $address, $abstractStateId, $edgeKind)
\*          => {src: $address, before: $abstractStateId, dst: $address,
\*              after: $abstractStateId, kind: $edgeKind};
S(src, before, dst, after, kind) ==
  [src |-> src, before |-> before, dst |-> dst, after |-> after, kind |-> kind]
Steps ==
  {S(1, "entry", 2, "rax-five", "next"),
   S(2, "rax-five", 3, "zf-true", "next"),
   S(3, "zf-true", 4, "zf-true", "taken")}

\* @type: ($address, $abstractStateId, $abstractStateId, $terminalOutcome)
\*          => {site: $address, before: $abstractStateId,
\*              after: $abstractStateId, outcome: $terminalOutcome};
T(site, before, after, outcome) ==
  [site |-> site, before |-> before, after |-> after, outcome |-> outcome]
Terminals ==
  {T(4, "zf-true", "returned", "returned"),
   T(5, "zf-true", "returned", "returned")}

\* @type: Set({site: $address, reason: $obligationReason});
NoAdapterObligations == {}

Engine == INSTANCE AriadneMachineState WITH
  SnapshotId <- "machine-state-snapshot",
  Nodes <- Nodes,
  EntryPoints <- {1},
  Locations <- Locations,
  ValueDomain <- Domains,
  StateIds <- States,
  Valuation <- Values,
  StateStatus <- Statuses,
  InitialStates <- EntryStates,
  StructuralEdges <- Edges,
  Uses <- InstructionUses,
  MustDefs <- InstructionMustDefs,
  MayDefs <- InstructionMayDefs,
  StateSteps <- Steps,
  TerminalTransitions <- Terminals,
  CompleteSites <- Nodes,
  AdapterObligations <- NoAdapterObligations

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates

ExpectedStates ==
  [a \in Nodes |->
    CASE a = 1 -> {"entry"}
      [] a = 2 -> {"rax-five"}
      [] a \in {3, 4} -> {"zf-true"}
      [] OTHER -> {}]

FixtureInvariant ==
  /\ Engine!AddressIdentity(3) =
       [snapshot |-> "machine-state-snapshot", va |-> 3]
  /\ Engine!StateIdentity("zf-true") =
       [snapshot |-> "machine-state-snapshot", state |-> "zf-true"]
  /\ Engine!Obligations = {}
  /\ Engine!StructuralGraph = Edges
  /\ (phase = "done" =>
       /\ statesAt = ExpectedStates
       /\ Engine!FeasibleEdges =
            {E(1, 2, "next"), E(2, 3, "next"), E(3, 4, "taken")}
       /\ Engine!ProvablyInfeasibleEdges = {E(3, 5, "fallthrough")}
       /\ Engine!UnknownFeasibilityEdges = {}
       /\ Engine!UnreachableNodes = {5}
       /\ Engine!ReachedTerminalTransitions =
            {T(4, "zf-true", "returned", "returned")})

Safety == Engine!TypeOK /\ Engine!StateflowInvariant
          /\ Engine!ResultInvariant /\ FixtureInvariant

NotDone == phase # "done"

=============================================================================
