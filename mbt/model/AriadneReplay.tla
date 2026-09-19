------------------------- MODULE AriadneReplay -------------------------
EXTENDS AriadneMachineCommon

\* Replay selects the deterministic schedule used by Analyzer::step().
\* Every transition invokes an action of the original Ariadne instance.
\* No engine equations or expected result states are reimplemented here.
CONSTANT
  \* @type: $scenarioId;
  Fixture
VARIABLES
  \* @type: $analysisPhase;
  phase,
  \* @type: Set($address);
  pending,
  \* @type: Set($address);
  visited,
  \* @type: Set($address);
  decoded,
  \* @type: $address -> $byteSource;
  provenance,
  \* @type: Set({src: $address, dst: $address, kind: $edgeKind});
  edges,
  \* @type: Set({site: $address, reason: $obligationReason});
  obligations,
  \* @type: $address -> Set({loc: $location, site: $address, origin: $definitionOrigin});
  reaching,
  \* @type: Set($address);
  slice,
  \* @type: $scenarioId;
  fixture_id,
  \* @type: Str;
  action_taken,
  \* @type: {fixture: $scenarioId};
  parameters

ASSUME Fixture \in {"Binary", "Dump", "Loop", "Closed", "Pipeline", "Calls"}
Mode == IF Fixture \in {"Dump", "Closed"} THEN "dump" ELSE "binary"
Scenario == CASE Fixture = "Loop" -> "loop"
             [] Fixture = "Closed" -> "closed"
             [] OTHER -> "partial"
Example == INSTANCE AriadneExample WITH Mode <- Mode, Scenario <- Scenario
Pipeline == INSTANCE AriadnePipeline
Calls == INSTANCE AriadneCalls

Addresses == CASE Fixture = "Pipeline" -> {4096, 4100}
              [] Fixture = "Calls" -> 1..4
              [] OTHER -> Example!Addr
Locations == IF Fixture \in {"Pipeline", "Calls"} THEN {"x"} ELSE Example!Loc
Roots == IF Fixture = "Pipeline" THEN {4096}
         ELSE IF Fixture = "Calls" THEN {1, 3} ELSE {1}
Seeds == CASE Fixture = "Pipeline" -> {4100}
          [] Fixture = "Calls" -> {2, 3}
          [] OTHER -> Example!Seeds
Snapshot == CASE Fixture = "Pipeline" -> "pipeline-snapshot"
             [] Fixture = "Calls" -> "calls-snapshot"
             [] OTHER -> "example-snapshot"
Small == Fixture \in {"Pipeline", "Calls"}
Instructions == CASE Fixture = "Pipeline" -> Pipeline!Instructions
                 [] Fixture = "Calls" -> Calls!Instructions
                 [] OTHER -> Example!Instructions

Core == INSTANCE Ariadne WITH
  SnapshotId <- Snapshot, Addresses <- Addresses, Locations <- Locations,
  EntryPoints <- Roots, SliceSeeds <- Seeds, InputKind <- Mode,
  Captured <- IF Small THEN {} ELSE Example!Capture,
  FileBacked <- IF Small THEN Addresses ELSE Example!Files,
  TrustedFallback <- IF Small THEN {} ELSE Example!Fallback,
  Decodable <- IF Small THEN Addresses ELSE 1..6,
  Insn <- Instructions

\* @type: Set($address) => $address;
Least(addresses) == CHOOSE a \in addresses : \A b \in addresses : a <= b
Ready == {a \in decoded : ~(Core!Incoming(a) \subseteq reaching[a])}

Init == Core!Init /\ fixture_id = Fixture
        /\ action_taken = "init" /\ parameters = [fixture |-> Fixture]
Label(name) == action_taken' = name /\ UNCHANGED <<parameters, fixture_id>>
Visit == /\ phase = "recover" /\ pending # {}
         /\ Core!Visit(Least(pending)) /\ Label("visit")
FinishRecovery == Core!FinishRecovery /\ Label("finishRecovery")
Propagate == /\ phase = "dataflow" /\ Ready # {}
             /\ Core!Propagate(Least(Ready)) /\ Label("propagate")
FinishDataflow == Core!FinishDataflow /\ Label("finishDataflow")
ExpandSlice == Core!ExpandSlice /\ Label("expandSlice")
FinishSlice == Core!FinishSlice /\ Label("finishSlice")
Next == Visit \/ FinishRecovery \/ Propagate \/ FinishDataflow \/ ExpandSlice \/ FinishSlice
vars == <<phase, pending, visited, decoded, provenance, edges, obligations,
          reaching, slice, fixture_id, action_taken, parameters>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == CASE Fixture = "Pipeline" -> Pipeline!Safety
           [] Fixture = "Calls" -> Calls!Safety
           [] OTHER -> Example!Safety
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
TypeWitness == FALSE
PipelineConstants == Fixture = "Pipeline"
=============================================================================
