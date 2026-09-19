----------------------- MODULE AriadneMachineState -----------------------
EXTENDS AriadneMachineCommon

\* Post-recovery abstract machine-state analysis
\* =============================================
\* This module consumes a frozen, instruction-level LOCAL CFG recovered by
\* Ariadne.tla. It never discovers instructions, changes structural edges, or
\* follows call edges. Call summaries, when present, arrive as ordinary local
\* "summary" edges with semantics supplied by the adapter.
\*
\* statesAt[a] is a set of possible abstract states BEFORE instruction a.
\* StateSteps relates one before-state to a running after-state and one existing
\* structural edge. TerminalTransitions records fault, return and stop outcomes.
\* The relation may be nondeterministic and is a trusted finite abstraction of
\* ISA semantics. The model verifies propagation and classification relative to
\* that relation; it does not prove the relation faithfully implements an ISA.
\*
\* Separate state identifiers can preserve correlations between locations.
\* Valuation exposes each state's register/flag/memory abstraction for reporting.
\* An adapter may use constants, ranges, symbolic origins or other finite values
\* as strings.
\* Different concrete states can map to the same abstract state identifier.

CONSTANT
  \* @type: $snapshotId;
  SnapshotId
CONSTANT
  \* @type: Set($address);
  Nodes
CONSTANT
  \* @type: Set($address);
  EntryPoints
CONSTANT
  \* @type: Set($location);
  Locations
CONSTANT
  \* @type: $location -> Set($abstractValue);
  ValueDomain
CONSTANT
  \* @type: Set($abstractStateId);
  StateIds
CONSTANT
  \* @type: $abstractStateId -> ($location -> Set($abstractValue));
  Valuation
CONSTANT
  \* @type: $abstractStateId -> $machineStatus;
  StateStatus
CONSTANT
  \* @type: $address -> Set($abstractStateId);
  InitialStates
CONSTANT
  \* @type: Set({src: $address, dst: $address, kind: $edgeKind});
  StructuralEdges
CONSTANT
  \* @type: $address -> Set($location);
  Uses
CONSTANT
  \* @type: $address -> Set($location);
  MustDefs
CONSTANT
  \* @type: $address -> Set($location);
  MayDefs
CONSTANT
  \* @type: Set({src: $address, before: $abstractStateId,
  \*             dst: $address, after: $abstractStateId, kind: $edgeKind});
  StateSteps
CONSTANT
  \* @type: Set({site: $address, before: $abstractStateId,
  \*             after: $abstractStateId, outcome: $terminalOutcome});
  TerminalTransitions
CONSTANT
  \* @type: Set($address);
  CompleteSites
CONSTANT
  \* @type: Set({site: $address, reason: $obligationReason});
  AdapterObligations

Statuses == {"running", "faulted", "returned", "stopped"}
TerminalOutcomes == {"faulted", "returned", "stopped"}
ObligationReasons ==
  {"incomplete-semantics", "unknown-memory", "unmodeled-exception",
   "unmodeled-system-call", "unmodeled-concurrency"}
Phases == {"stateflow", "done"}

\* @type: $abstractStateId
\*          => {snapshot: $snapshotId, state: $abstractStateId};
StateIdentity(state) == [snapshot |-> SnapshotId, state |-> state]
\* @type: $address => {snapshot: $snapshotId, va: $address};
AddressIdentity(address) == MachineAddressIdentity(SnapshotId, address)
\* @type: ($address, $address, $edgeKind)
\*          => {src: $address, dst: $address, kind: $edgeKind};
Edge(src, dst, kind) == MachineEdge(src, dst, kind)
StructuralGraph == StructuralEdges
\* @type: $address => {site: $address, reason: $obligationReason};
SemanticObligation(a) == [site |-> a, reason |-> "incomplete-semantics"]
SemanticObligations ==
  {SemanticObligation(a) : a \in Nodes \ CompleteSites}
Obligations == AdapterObligations \cup SemanticObligations

\* The transition relation must respect the instruction's may-write frame.
\* A must-write can produce the same abstract value as its input, so equality of
\* before/after values does not by itself violate definite-write semantics.
\* @type: ($address, $abstractStateId, $abstractStateId) => Bool;
PreservesFrame(site, before, after) ==
  \A location \in Locations \ MayDefs[site] :
    Valuation[before][location] = Valuation[after][location]

\* @type: {src: $address, before: $abstractStateId, dst: $address,
\*          after: $abstractStateId, kind: $edgeKind}
\*          => {src: $address, dst: $address, kind: $edgeKind};
StepEdge(step) == Edge(step.src, step.dst, step.kind)

InputContract ==
  /\ MachineAddressSpaceContract(SnapshotId, Nodes)
  /\ IsFiniteSet(EntryPoints) /\ EntryPoints \subseteq Nodes
  /\ IsFiniteSet(Locations) /\ Locations # {}
  /\ DOMAIN ValueDomain = Locations
  /\ \A location \in Locations :
       /\ IsFiniteSet(ValueDomain[location])
       /\ ValueDomain[location] # {}
  /\ IsFiniteSet(StateIds) /\ StateIds # {}
  /\ DOMAIN Valuation = StateIds
  /\ \A state \in StateIds :
       /\ DOMAIN Valuation[state] = Locations
       /\ \A location \in Locations :
            /\ Valuation[state][location] \subseteq ValueDomain[location]
            /\ Valuation[state][location] # {}
  /\ DOMAIN StateStatus = StateIds
  /\ \A state \in StateIds : StateStatus[state] \in Statuses
  /\ DOMAIN InitialStates = Nodes
  /\ \A a \in Nodes : InitialStates[a] \subseteq StateIds
  /\ \A a \in Nodes \ EntryPoints : InitialStates[a] = {}
  /\ \A a \in EntryPoints :
       /\ InitialStates[a] # {}
       /\ \A state \in InitialStates[a] : StateStatus[state] = "running"
  /\ \A edge \in StructuralEdges :
       /\ DOMAIN edge = {"src", "dst", "kind"}
       /\ edge.src \in Nodes /\ edge.dst \in Nodes
       /\ edge.kind \in MachineLocalEdgeKinds
  /\ DOMAIN Uses = Nodes
  /\ DOMAIN MustDefs = Nodes
  /\ DOMAIN MayDefs = Nodes
  /\ \A a \in Nodes :
       /\ MachineEffectWellFormed(
            Locations, Uses[a], MustDefs[a], MayDefs[a])
  /\ \A step \in StateSteps :
       /\ DOMAIN step = {"src", "before", "dst", "after", "kind"}
       /\ step.src \in Nodes /\ step.dst \in Nodes
       /\ step.before \in StateIds /\ step.after \in StateIds
       /\ StateStatus[step.before] = "running"
       /\ StateStatus[step.after] = "running"
       /\ step.kind \in MachineLocalEdgeKinds
       /\ StepEdge(step) \in StructuralEdges
       /\ PreservesFrame(step.src, step.before, step.after)
  /\ \A transition \in TerminalTransitions :
       /\ DOMAIN transition = {"site", "before", "after", "outcome"}
       /\ transition.site \in Nodes
       /\ transition.before \in StateIds /\ transition.after \in StateIds
       /\ StateStatus[transition.before] = "running"
       /\ transition.outcome \in TerminalOutcomes
       /\ StateStatus[transition.after] = transition.outcome
       /\ PreservesFrame(transition.site, transition.before, transition.after)
  /\ CompleteSites \subseteq Nodes
  /\ \A obligation \in AdapterObligations :
       /\ DOMAIN obligation = {"site", "reason"}
       /\ obligation.site \in Nodes
       /\ obligation.reason \in ObligationReasons \ {"incomplete-semantics"}

ASSUME InputContract

VARIABLE
  \* @type: $analysisPhase;
  phase
VARIABLE
  \* @type: $address -> Set($abstractStateId);
  statesAt
vars == <<phase, statesAt>>

Init ==
  /\ phase = "stateflow"
  /\ statesAt = InitialStates

\* Only transitions whose before-state has reached their source contribute.
ReachedSteps ==
  {step \in StateSteps : step.before \in statesAt[step.src]}
ReachedTerminalTransitions ==
  {transition \in TerminalTransitions
    : transition.before \in statesAt[transition.site]}

Incoming(a) ==
  InitialStates[a]
  \cup {step.after : step \in {candidate \in ReachedSteps : candidate.dst = a}}

Propagate(a) ==
  /\ phase = "stateflow" /\ a \in Nodes
  /\ ~(Incoming(a) \subseteq statesAt[a])
  /\ statesAt' = [statesAt EXCEPT ![a] = @ \cup Incoming(a)]
  /\ UNCHANGED phase

StateflowFixed == \A a \in Nodes : statesAt[a] = Incoming(a)

FinishStateflow ==
  /\ phase = "stateflow" /\ StateflowFixed
  /\ phase' = "done"
  /\ UNCHANGED statesAt

Next == (\E a \in Nodes : Propagate(a)) \/ FinishStateflow
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

\* StructuralEdges is never changed or filtered. These are derived views over
\* the current analysis facts. "Infeasible" is justified only at a certified
\* complete, reached source; every other absent edge remains unknown.
FeasibleEdges == {StepEdge(step) : step \in ReachedSteps}
ReachedSources == {a \in Nodes : statesAt[a] # {}}
ProvablyInfeasibleEdges ==
  IF phase = "done"
  THEN {edge \in StructuralEdges
         : edge.src \in CompleteSites /\ edge.src \in ReachedSources
           /\ edge \notin FeasibleEdges}
  ELSE {}
UnknownFeasibilityEdges ==
  StructuralEdges \ (FeasibleEdges \cup ProvablyInfeasibleEdges)
UnreachableNodes == IF phase = "done" THEN Nodes \ ReachedSources ELSE {}

TypeOK ==
  /\ InputContract
  /\ phase \in Phases
  /\ DOMAIN statesAt = Nodes
  /\ \A a \in Nodes : statesAt[a] \subseteq StateIds
  /\ \A a \in Nodes :
       \A state \in statesAt[a] : StateStatus[state] = "running"
  /\ FeasibleEdges \subseteq StructuralEdges
  /\ ProvablyInfeasibleEdges \subseteq StructuralEdges
  /\ UnknownFeasibilityEdges \subseteq StructuralEdges
  /\ Obligations \subseteq
       [site : Nodes, reason : ObligationReasons]

StateflowInvariant ==
  /\ \A a \in Nodes : InitialStates[a] \subseteq statesAt[a]
  /\ \A a \in Nodes : statesAt[a] \subseteq Incoming(a)
  /\ FeasibleEdges \cap ProvablyInfeasibleEdges = {}
  /\ FeasibleEdges \cap UnknownFeasibilityEdges = {}
  /\ ProvablyInfeasibleEdges \cap UnknownFeasibilityEdges = {}
  /\ FeasibleEdges \cup ProvablyInfeasibleEdges
       \cup UnknownFeasibilityEdges = StructuralEdges

ResultInvariant == phase = "done" => StateflowFixed
Terminates == <> (phase = "done")

=============================================================================
