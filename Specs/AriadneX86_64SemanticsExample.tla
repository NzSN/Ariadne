----------------- MODULE AriadneX86_64SemanticsExample -----------------
EXTENDS AriadneX86_64Semantics

CONSTANT
  \* @type: $scenarioId;
  Scenario
ASSUME Scenario \in {"complete", "unsupported", "missing-state", "missing-edge"}
VARIABLES
  \* @type: $analysisPhase;
  phase,
  \* @type: $address -> Set($abstractStateId);
  statesAt

\* Normalized instructions corresponding to:
\* 1000: mov eax,5; 1005: cmp eax,5; 1008: je 100C;
\* 100A: ud2; 100C: ud2. These are supplied decoded records, not decoded bytes.
Nodes == {4096, 4101, 4104, 4106, 4108}
Five == WordFromBytes([byte \in 1..8 |-> IF byte = 1 THEN 5 ELSE 0])
\* @type: $x86Opcode => $x86Instruction;
DataInstruction(op) ==
  [op |-> op, width |-> 32, dst |-> "rax", source |-> "imm", sourceReg |-> "",
   immediate |-> Five, next |-> 4104, target |-> 0, condition |-> ""]
\* @type: $x86Instruction;
FaultInstruction ==
  [op |-> "ud2", width |-> 0, dst |-> "", source |-> "none", sourceReg |-> "",
   immediate |-> ZeroWord, next |-> 0, target |-> 0, condition |-> ""]
\* @type: $address -> $x86Instruction;
Instructions == [a \in Nodes |->
  CASE a = 4096 -> [DataInstruction("mov") EXCEPT !.next = 4101]
    [] a = 4101 -> IF Scenario = "unsupported"
                  THEN [DataInstruction("inc") EXCEPT !.source = "none"]
                  ELSE DataInstruction("cmp")
    [] a = 4104 -> [FaultInstruction EXCEPT !.op = "jcc", !.condition = "e",
                                          !.next = 4106, !.target = 4108]
    [] OTHER -> FaultInstruction]

RunningIds == {"zero-clear", "zero-equal", "zero-below", "five-clear", "five-equal", "five-below"}
FaultIds == {"fault-zero-clear", "fault-zero-equal", "fault-zero-below",
             "fault-five-clear", "fault-five-equal", "fault-five-below"}
StateIds == (RunningIds \cup FaultIds) \ (IF Scenario = "missing-state" THEN {"five-clear"} ELSE {})
FiveIds == {"five-clear", "five-equal", "five-below", "fault-five-clear", "fault-five-equal", "fault-five-below"}
EqualIds == {"zero-equal", "five-equal", "fault-zero-equal", "fault-five-equal"}
BelowIds == {"zero-below", "five-below", "fault-zero-below", "fault-five-below"}
\* @type: $abstractStateId -> $x86State;
Catalogue == [id \in StateIds |->
  [gpr |-> [reg \in GPRs |-> IF reg = "rax" /\ id \in FiveIds THEN Five ELSE ZeroWord],
   flags |-> [flag \in Flags |->
                IF id \in EqualIds THEN flag \in {"zf", "pf"}
                ELSE IF id \in BelowIds THEN flag \in {"cf", "af", "sf"}
                ELSE FALSE]]]
\* @type: $abstractStateId -> $machineStatus;
Statuses == [id \in StateIds |-> IF id \in RunningIds THEN "running" ELSE "faulted"]
\* @type: $abstractValue -> $x86Word;
Names == [name \in {"zero", "five"} |-> IF name = "five" THEN Five ELSE ZeroWord]
Values == ValuationFor(Catalogue, Names)
\* @type: $location -> Set($abstractValue);
Domains == [location \in X86Locations |->
              IF location \in GPRs THEN {"zero", "five"} ELSE {"false", "true"}]
\* @type: $address -> Set($abstractStateId);
EntryStates == [a \in Nodes |-> IF a = 4096 THEN {"zero-clear"} ELSE {}]
AllEdges == {MachineEdge(4096, 4101, "next"), MachineEdge(4101, 4104, "next"),
             MachineEdge(4104, 4108, "taken"), MachineEdge(4104, 4106, "fallthrough")}
Edges == AllEdges \ (IF Scenario = "missing-edge" THEN {MachineEdge(4104, 4108, "taken")} ELSE {})
Steps == RunningSteps(Instructions, Catalogue, Statuses, Edges)
Terminals == TerminalSteps(Instructions, Catalogue, Statuses)
CompleteSites == CompleteSitesFor(Instructions, Catalogue, Statuses, Edges)
\* @type: Set({site: $address, reason: $obligationReason});
NoAdapterObligations == {}

Engine == INSTANCE AriadneMachineState WITH
  SnapshotId <- "x86-64-example", Nodes <- Nodes, EntryPoints <- {4096},
  Locations <- X86Locations, ValueDomain <- Domains, StateIds <- StateIds,
  Valuation <- Values, StateStatus <- Statuses, InitialStates <- EntryStates,
  StructuralEdges <- Edges,
  Uses <- [a \in Nodes |-> UsesOf(Instructions[a])],
  MustDefs <- [a \in Nodes |-> MustDefsOf(Instructions[a])],
  MayDefs <- [a \in Nodes |-> MayDefsOf(Instructions[a])],
  StateSteps <- Steps, TerminalTransitions <- Terminals,
  CompleteSites <- CompleteSites, AdapterObligations <- NoAdapterObligations

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates

\* @type: $address -> Set($abstractStateId);
ExpectedStates == [a \in Nodes |->
  CASE a = 4096 -> {"zero-clear"}
    [] a = 4101 /\ Scenario # "missing-state" -> {"five-clear"}
    [] a = 4104 /\ Scenario \in {"complete", "missing-edge"} -> {"five-equal"}
    [] a = 4108 /\ Scenario = "complete" -> {"five-equal"}
    [] OTHER -> {}]

FixtureInvariant ==
  /\ CatalogueWellFormed(Catalogue, Statuses, Names)
  /\ \A a \in Nodes : InstructionWellFormed(Instructions[a])
  /\ Engine!StructuralGraph = Edges
  /\ CASE Scenario = "complete" -> CompleteSites = Nodes
       [] Scenario = "unsupported" -> 4101 \notin CompleteSites
       [] Scenario = "missing-state" -> 4096 \notin CompleteSites
       [] Scenario = "missing-edge" -> 4104 \notin CompleteSites
  /\ phase = "done" =>
       /\ statesAt = ExpectedStates
       /\ IF Scenario = "complete" THEN
            /\ Engine!FeasibleEdges = AllEdges \ {MachineEdge(4104, 4106, "fallthrough")}
            /\ Engine!ProvablyInfeasibleEdges = {MachineEdge(4104, 4106, "fallthrough")}
            /\ Engine!UnknownFeasibilityEdges = {}
            /\ Engine!Obligations = {}
            /\ Engine!ReachedTerminalTransitions =
                 {[site |-> 4108, before |-> "five-equal",
                   after |-> "fault-five-equal", outcome |-> "faulted"]}
          ELSE
            /\ Engine!ProvablyInfeasibleEdges = {}
            /\ Engine!Obligations # {}
            /\ Engine!ReachedTerminalTransitions = {}
            /\ CASE Scenario = "unsupported" ->
                      MachineEdge(4101, 4104, "next") \in Engine!UnknownFeasibilityEdges
                 [] Scenario = "missing-state" ->
                      MachineEdge(4096, 4101, "next") \in Engine!UnknownFeasibilityEdges
                 [] Scenario = "missing-edge" ->
                      MachineEdge(4104, 4106, "fallthrough") \in Engine!UnknownFeasibilityEdges

Safety == Engine!TypeOK /\ Engine!StateflowInvariant /\ Engine!ResultInvariant /\ FixtureInvariant

=============================================================================
