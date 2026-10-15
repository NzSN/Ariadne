--------------------- MODULE AriadnePredicateAdmission ---------------------
EXTENDS Integers, FiniteSets, Sequences

\* G0/S1 authority for proof-only MOVAPS load/store normal admission and
\* explicitly scoped, control-only normal terminals. The preserved v1 model
\* lives in the frozen caller-coverage/legacy-v2 fixture; it is not edited here.
\* The finite nodes below denote snapshot/activation-qualified instruction
\* points, not file offsets or a claim that any represented path executed.
\* Captured decoding, exact reviewed BIL/byte recognition, source hashes and
\* derivation validation are trusted input checks abstracted by the bindings.
\* This is a candidate graph: pending load/store edges commit no normal effect.
\* The final normal request is published only after independent replay and
\* final incoming closure. A certified Stop ends LOCAL NORMAL completion,
\* retaining an exceptional exit and opaque effects. Handler/debugger reentry
\* is outside this scope, not assumed impossible. Exact trap bytes, pinned BAP
\* observations and UD1 extent parsing are source checks abstracted below;
\* the independent concrete oracle tests those representation-level clauses.
\* @typeAlias: guardScenario = Str;
\* @typeAlias: guardOrigin = Str;
\* @typeAlias: guardVerdict = Str;
\* @typeAlias: guardPhase = Str;
\* @typeAlias: guardDecision = Str;
\* @typeAlias: guardOperation = Str;
\* @typeAlias: guardVersion = Str;
\* @typeAlias: guardFlowScope = Str;
\* @typeAlias: guardPremise = {root: Int, point: Int, snapshot: Int, intent: Int, activation: Int, origin: $guardOrigin, residues: Set(Int)};
\* @typeAlias: candidateEdge = {src: Int, dst: Int};
PredicateAdmission_typedefs == TRUE
CONSTANTS
  \* @type: $guardScenario;
  Scenario,
  \* @type: Int;
  UpdateBudget

\* @type: Set($guardScenario);
TerminalScenarios == {"TerminalInt3", "TerminalUd2", "TerminalUd1",
  "TerminalUnknownStop", "TerminalBadBytes", "TerminalBadSpan", "TerminalBadAst",
  "TerminalBadRule", "TerminalMissingScope", "TerminalMissingExit",
  "TerminalBadSuccessor", "TerminalBadEffects", "TerminalHandlerResume",
  "TerminalWholeMachineClaim", "TerminalCompletenessOnly", "TerminalLateEdge",
  "TerminalLateEvidence", "TerminalStaleEpoch", "TerminalLegacyField"}
\* @type: Set($guardScenario);
LoadScenarios == {"LoadAligned", "LoadUnknown", "LoadMisaligned", "LoadWrongShape",
  "LoadWrongDirection", "LoadWrongBank", "LoadWrongMerge", "LoadWrongWidth",
  "LoadWrongAddress", "LoadWrongPredicate", "LoadPrematureEffect", "LoadLegacyField"}
\* @type: Set($guardScenario);
InvalidEvidenceScenarios == {"TerminalBadBytes", "TerminalBadSpan", "TerminalBadAst",
  "TerminalBadRule", "TerminalMissingScope", "TerminalMissingExit",
  "TerminalBadSuccessor", "TerminalBadEffects", "TerminalWholeMachineClaim",
  "TerminalStaleEpoch", "TerminalLegacyField", "LoadWrongShape", "LoadWrongDirection",
  "LoadWrongBank", "LoadWrongMerge", "LoadWrongWidth", "LoadWrongAddress",
  "LoadWrongPredicate", "LoadPrematureEffect", "LoadLegacyField"}
\* @type: Set($guardScenario);
Scenarios == {"Aligned", "Captured", "Unwind", "Unknown", "Misaligned",
              "Conflict", "WrongPoint", "WrongActivation", "WrongSnapshot",
              "WrongIntent", "AbiOptOut", "UnwindResume", "NonRootPremise",
              "AdditionalRoot", "LateIncoming", "LateRoot", "LateTransfer",
              "LateBarrier", "LoopIdentity", "LoopChanging", "PendingHavoc",
              "OpaqueTransfer", "OpaqueCall", "Barrier", "Unreached", "Zero"}
              \cup TerminalScenarios \cup LoadScenarios
ASSUME /\ Scenario \in Scenarios /\ UpdateBudget \in Nat

Nodes == 1..4
Residues == 0..15
\* @type: $guardVersion;
ModelVersion == "ariadne.predicate-admission/v2"
\* @type: $guardFlowScope;
NormalFlowScope == "local-normal-completion/v1"
\* @type: $guardOperation;
GuardOperation == IF Scenario \in LoadScenarios THEN "load" ELSE "store"
Terminal == 4
Guard == 2
Displacement == 576
SliceSeeds == {4}
\* @type: (Int, Int) => $candidateEdge;
Edge(a,b) == [src |-> a, dst |-> b]
\* @type: (Int, Int, $guardOrigin, Set(Int)) => $guardPremise;
Premise(root,point,origin,rs) ==
  [root |-> root, point |-> point, snapshot |-> 1, intent |-> 1,
   activation |-> 1, origin |-> origin, residues |-> rs]

InitialRoots == IF Scenario \in {"AdditionalRoot","LateIncoming"}
                THEN {1,4} ELSE {1}
InitialEdges == IF Scenario = "Unreached" THEN {Edge(2,3)}
                ELSE {Edge(1,2),Edge(2,3)} \cup
                  (IF Scenario \in TerminalScenarios THEN {Edge(3,Terminal)} ELSE {})
                  \cup (IF Scenario = "TerminalBadSuccessor"
                        THEN {Edge(Terminal,Guard)} ELSE {})
LoopEdges == IF Scenario \in {"LoopIdentity","LoopChanging","PendingHavoc"}
             THEN {Edge(3,2)} ELSE {}
AdditionalEdges == IF Scenario = "AdditionalRoot" THEN {Edge(4,2)} ELSE {}
InitialBarriers == (IF Scenario = "Barrier" THEN {Guard} ELSE {}) \cup
  (IF Scenario = "TerminalUnknownStop" THEN {Terminal} ELSE {})
LateScenarios == {"LateIncoming","LateRoot","LateTransfer","LateBarrier",
                  "TerminalCompletenessOnly","TerminalLateEdge","TerminalLateEvidence"}
\* No environment fact says a handler cannot resume. This concrete set of
\* possible handler-supplied residues is deliberately unconstrained.
ExceptionalResumeResidues == IF Scenario = "TerminalHandlerResume" THEN Residues ELSE {}
WholeMachineCoverageClaimed == Scenario = "TerminalWholeMachineClaim"
NormalEvidenceValid == Scenario \notin InvalidEvidenceScenarios
InitialTerminals == IF Scenario \in TerminalScenarios /\ NormalEvidenceValid
                       /\ Scenario # "TerminalUnknownStop" THEN {Terminal} ELSE {}
\* Full opaque exceptional effects are retained as MAY effects. Their numeric
\* identities stand for tracked architectural locations; none is a MUST write.
TrackedLocations == 0..3
TerminalUses == TrackedLocations
TerminalMayDefs == TrackedLocations
TerminalMustDefs == IF Scenario = "TerminalBadEffects" THEN {0} ELSE {}

\* A premise never creates a root. Captured observations and derived unwind
\* facts apply at their own point/activation only. ABI entry is opt-in and has
\* its own checked normal-call-entry anchor, not merely Windows metadata.
EntryPremise ==
  LET p == Premise(IF Scenario = "NonRootPremise" THEN 4 ELSE 1,
                   IF Scenario \in {"WrongPoint","UnwindResume"} THEN 3 ELSE 1,
                   IF Scenario = "Captured" THEN "captured"
                   ELSE IF Scenario \in {"Unwind","UnwindResume"} THEN "unwind"
                   ELSE "abi", {8})
  IN [p EXCEPT !.activation = IF Scenario = "WrongActivation" THEN 2 ELSE 1,
               !.snapshot = IF Scenario = "WrongSnapshot" THEN 2 ELSE 1,
               !.intent = IF Scenario = "WrongIntent" THEN 2 ELSE 1]
Premises ==
  (IF Scenario \in {"Unknown","LoadUnknown"} THEN {} ELSE {EntryPremise})
  \cup (IF Scenario = "Conflict" THEN {Premise(1,1,"captured",{0})} ELSE {})
  \cup (IF Scenario = "LateIncoming" THEN {Premise(4,4,"captured",{4})} ELSE {})
\* @type: $guardPremise => Bool;
Eligible(p) ==
  /\ p.root \in InitialRoots /\ p.point = p.root
  /\ p.snapshot = 1 /\ p.intent = 1 /\ p.activation = 1
  /\ p.residues # {} /\ p.residues \subseteq Residues
  /\ p.origin \in {"captured","unwind","abi"}
  /\ (p.origin = "abi" => Scenario # "AbiOptOut" /\ p.residues = {8})
\* @type: Int => Set(Int);
Constraints(n) == {r \in Residues:
                    \A p \in Premises: p.root = n => r \in p.residues}
PremisesValid == /\ \A p \in Premises: Eligible(p)
                 /\ \A n \in InitialRoots: Constraints(n) # {}
\* @type: (Int, Set(Int)) => Set(Int);
Seed(n,rs) == IF n \in rs THEN Constraints(n) ELSE {}
\* @type: (Set(Int), Set(Int)) => (Int -> Set(Int));
Seeds(rs,bs) == [n \in Nodes |-> Seed(n,rs) \cup
                                  (IF n \in bs THEN Residues ELSE {})]
\* @type: (Set(Int), Int) => Set(Int);
Shift(values,d) == {(r+d) % 16 : r \in values}

\* Only the separately source-bound pending load/store relation permits identity
\* here. It is fixed before any verdict; the guard proof cannot certify itself.
PendingTransferChecked == Scenario # "PendingHavoc"
InitialOpaque == (IF Scenario \in {"OpaqueTransfer","OpaqueCall"} THEN {1} ELSE {})
                 \cup InitialTerminals
InitialDeltas == [n \in Nodes |-> IF n = 1
                  THEN IF Scenario \in {"Misaligned","LoadMisaligned"} THEN 0 ELSE -8
                  ELSE IF n = 3 /\ Scenario = "LoopChanging" THEN 8 ELSE 0]

VARIABLES
  \* @type: Set(Int);
  roots,
  \* @type: Set($candidateEdge);
  edges,
  \* @type: Set(Int);
  barriers,
  \* @type: Int -> Int;
  deltas,
  \* @type: Set(Int);
  opaque,
  \* @type: Int -> Set(Int);
  facts,
  \* @type: Int;
  updates,
  \* @type: Int;
  epoch,
  \* @type: Bool;
  lateChecked,
  \* @type: Bool;
  graphClosed,
  \* @type: Int;
  receiptEpoch,
  \* @type: Int -> Set(Int);
  receiptFacts,
  \* @type: $guardVerdict;
  receiptVerdict,
  \* @type: $guardPhase;
  phase,
  \* @type: $guardDecision;
  decision,
  \* @type: Bool;
  normalStoreEffect,
  \* @type: Bool;
  normalLoadEffect,
  \* @type: Set(Int);
  normalTerminals,
  \* @type: Bool;
  terminalControlComplete
vars == <<roots,edges,barriers,deltas,opaque,facts,updates,epoch,lateChecked,
          graphClosed,receiptEpoch,receiptFacts,receiptVerdict,phase,decision,
          normalStoreEffect,normalLoadEffect,normalTerminals,terminalControlComplete>>

\* Empty means unreached. Havoc on an unreached input remains empty, rather
\* than manufacturing a reached state. Unknown writes and opaque call summaries
\* havoc; ordinary branch alternatives remain in the candidate graph.
\* @type: (Int, Set(Int)) => Set(Int);
Transfer(n,values) ==
  IF values = {} THEN {}
  ELSE IF n \in opaque \/ (n = Guard /\ ~PendingTransferChecked) THEN Residues
  ELSE Shift(values,deltas[n])
\* @type: (Int, Int -> Set(Int)) => Set(Int);
Incoming(n,fs) ==
  Seed(n,roots) \cup (IF n \in barriers THEN Residues ELSE {})
  \cup UNION {Transfer(e.src,fs[e.src]): e \in {x \in edges: x.dst = n}}
\* Replay includes every candidate-only predecessor and every incoming barrier.
\* A conservative supplied fact map may overapproximate the least fixed point.
\* @type: (Int -> Set(Int)) => Bool;
Replay(fs) == /\ DOMAIN fs = Nodes
              /\ \A n \in Nodes: /\ fs[n] \subseteq Residues
                                    /\ Incoming(n,fs) \subseteq fs[n]
Fixed == Replay(facts)
\* @type: (Int -> Set(Int)) => $guardVerdict;
Verdict(fs) ==
  IF ~graphClosed \/ barriers # {} THEN "unknown"
  ELSE IF fs[Guard] = {} THEN "unreached"
  ELSE IF Shift(fs[Guard],Displacement) = {0} THEN "aligned"
  ELSE IF 0 \notin Shift(fs[Guard],Displacement) THEN "misaligned"
  ELSE "unknown"

Init ==
  /\ roots = InitialRoots /\ edges = InitialEdges \cup LoopEdges \cup AdditionalEdges
  /\ barriers = InitialBarriers /\ deltas = InitialDeltas /\ opaque = InitialOpaque
  /\ facts = Seeds(InitialRoots,InitialBarriers) /\ updates = 0 /\ epoch = 0
  /\ lateChecked = (Scenario \notin LateScenarios) /\ graphClosed = FALSE
  /\ receiptEpoch = -1 /\ receiptFacts = [n \in Nodes |-> {}]
  /\ receiptVerdict = "none" /\ normalStoreEffect = FALSE /\ normalLoadEffect = FALSE
  /\ normalTerminals = InitialTerminals /\ terminalControlComplete = TRUE
  /\ phase = IF ~PremisesValid \/ ~NormalEvidenceValid \/ UpdateBudget = 0
              THEN "done" ELSE "propagate"
  /\ decision = IF ~PremisesValid THEN "invalid-premise"
                 ELSE IF ~NormalEvidenceValid THEN "invalid-evidence"
                 ELSE IF UpdateBudget = 0 THEN "budget-stop" ELSE "pending"
Propagate(n) ==
  /\ phase = "propagate" /\ n \in Nodes /\ updates < UpdateBudget
  /\ ~(Incoming(n,facts) \subseteq facts[n])
  /\ facts' = [facts EXCEPT ![n] = @ \cup Incoming(n,facts)]
  /\ updates' = updates+1
  /\ UNCHANGED <<roots,edges,barriers,deltas,opaque,epoch,lateChecked,graphClosed,
                  receiptEpoch,receiptFacts,receiptVerdict,phase,decision,
                  normalStoreEffect,normalLoadEffect,normalTerminals,terminalControlComplete>>
CloseCandidate ==
  /\ phase = "propagate" /\ Fixed
  /\ graphClosed' = TRUE /\ phase' = "certify"
  /\ UNCHANGED <<roots,edges,barriers,deltas,opaque,facts,updates,epoch,lateChecked,
                  receiptEpoch,receiptFacts,receiptVerdict,decision,normalStoreEffect,
                  normalLoadEffect,normalTerminals,terminalControlComplete>>
BudgetStop ==
  /\ phase = "propagate" /\ ~Fixed /\ updates = UpdateBudget
  /\ phase' = "done" /\ decision' = "budget-stop" /\ graphClosed' = FALSE
  /\ receiptEpoch' = -1 /\ receiptVerdict' = "none"
  /\ UNCHANGED <<roots,edges,barriers,deltas,opaque,facts,updates,epoch,lateChecked,
                  receiptFacts,normalStoreEffect,normalLoadEffect,normalTerminals,
                  terminalControlComplete>>
Certify ==
  /\ phase = "certify" /\ graphClosed /\ Fixed
  /\ receiptEpoch' = epoch /\ receiptFacts' = facts
  /\ receiptVerdict' = Verdict(facts) /\ phase' = "revalidate"
  /\ UNCHANGED <<roots,edges,barriers,deltas,opaque,facts,updates,epoch,lateChecked,
                  graphClosed,decision,normalStoreEffect,normalLoadEffect,
                  normalTerminals,terminalControlComplete>>
\* One representative closure round exposes a new root, incoming edge, barrier
\* or changed source-bound transfer. Receipts and closure are invalidated
\* atomically; neither a stale aligned verdict nor its store may be published.
DiscoverLate ==
  /\ phase = "revalidate" /\ ~lateChecked
  /\ roots' = IF Scenario = "LateRoot" THEN roots \cup {4} ELSE roots
  /\ edges' = IF Scenario \in {"LateIncoming","LateRoot","TerminalLateEdge"}
              THEN edges \cup {Edge(4,Guard)} ELSE edges
  /\ barriers' = IF Scenario = "LateBarrier" THEN barriers \cup {Guard}
                 ELSE IF Scenario \in {"TerminalCompletenessOnly","TerminalLateEdge",
                                         "TerminalLateEvidence"}
                      THEN barriers \cup {Terminal} ELSE barriers
  /\ normalTerminals' = IF Scenario \in {"TerminalCompletenessOnly","TerminalLateEdge",
                                          "TerminalLateEvidence"}
                          THEN {} ELSE normalTerminals
  /\ terminalControlComplete' = (Scenario # "TerminalCompletenessOnly")
  /\ deltas' = IF Scenario = "LateTransfer" THEN [deltas EXCEPT ![1] = 0] ELSE deltas
  /\ epoch' = epoch+1 /\ lateChecked' = TRUE /\ graphClosed' = FALSE
  /\ facts' = Seeds(roots',barriers') /\ receiptEpoch' = -1
  /\ receiptFacts' = [n \in Nodes |-> {}] /\ receiptVerdict' = "none"
  /\ phase' = "propagate"
  /\ UNCHANGED <<opaque,updates,decision,normalStoreEffect,normalLoadEffect>>
Publish ==
  /\ phase = "revalidate" /\ lateChecked /\ graphClosed /\ Fixed
  /\ receiptEpoch = epoch /\ receiptFacts = facts /\ Replay(receiptFacts)
  /\ receiptVerdict = Verdict(receiptFacts)
  /\ normalStoreEffect' = (receiptVerdict = "aligned" /\ GuardOperation = "store")
  /\ normalLoadEffect' = (receiptVerdict = "aligned" /\ GuardOperation = "load")
  /\ decision' = CASE receiptVerdict = "aligned" -> "admit-normal"
                      [] receiptVerdict = "misaligned" -> "refuted-normal-stop"
                      [] receiptVerdict = "unreached" -> "unreached-stop"
                      [] OTHER -> "normal-or-fault-stop"
  /\ phase' = "done"
  /\ UNCHANGED <<roots,edges,barriers,deltas,opaque,facts,updates,epoch,lateChecked,
                  graphClosed,receiptEpoch,receiptFacts,receiptVerdict,normalTerminals,
                  terminalControlComplete>>
Next == (\E n \in Nodes: Propagate(n)) \/ CloseCandidate \/ BudgetStop
        \/ Certify \/ DiscoverLate \/ Publish
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

TypeOK ==
  /\ roots \subseteq Nodes /\ barriers \subseteq Nodes /\ opaque \subseteq Nodes
  /\ \A e \in edges: e.src \in Nodes /\ e.dst \in Nodes
  /\ facts \in [Nodes -> SUBSET Residues]
  /\ receiptFacts \in [Nodes -> SUBSET Residues] /\ deltas \in [Nodes -> Int]
  /\ updates \in 0..UpdateBudget /\ epoch \in 0..1 /\ receiptEpoch \in -1..1
  /\ phase \in {"propagate","certify","revalidate","done"}
  /\ decision \in {"pending","invalid-premise","invalid-evidence","budget-stop","admit-normal",
                     "refuted-normal-stop","unreached-stop","normal-or-fault-stop"}
  /\ receiptVerdict \in {"none","aligned","misaligned","unreached","unknown"}
  /\ lateChecked \in BOOLEAN /\ graphClosed \in BOOLEAN /\ normalStoreEffect \in BOOLEAN
  /\ normalLoadEffect \in BOOLEAN /\ normalTerminals \subseteq {Terminal}
  /\ terminalControlComplete \in BOOLEAN
PremisePolicy == /\ (~PremisesValid => decision = "invalid-premise")
                 /\ roots \subseteq InitialRoots \cup
                       (IF Scenario = "LateRoot" /\ epoch = 1 THEN {4} ELSE {})
                 /\ (Scenario = "NonRootPremise" => 4 \notin roots)
ClosurePolicy ==
  /\ (graphClosed => Fixed)
  /\ (receiptEpoch >= 0 => /\ receiptEpoch = epoch /\ graphClosed
                            /\ Replay(receiptFacts) /\ receiptFacts = facts
                            /\ receiptVerdict = Verdict(receiptFacts))
  /\ (normalStoreEffect \/ normalLoadEffect => /\ phase = "done" /\ lateChecked /\ graphClosed
                            /\ PremisesValid /\ UpdateBudget > 0
                            /\ receiptEpoch = epoch /\ Replay(receiptFacts)
                            /\ receiptFacts[Guard] # {}
                            /\ Shift(receiptFacts[Guard],Displacement) = {0})
EffectPolicy ==
  /\ (normalStoreEffect \/ normalLoadEffect) = (decision = "admit-normal")
  /\ ~(normalStoreEffect /\ normalLoadEffect)
  /\ (normalStoreEffect => GuardOperation = "store")
  /\ (normalLoadEffect => GuardOperation = "load")
  /\ (receiptVerdict \in {"unknown","misaligned","unreached","none"}
        => ~normalStoreEffect /\ ~normalLoadEffect)
  /\ (phase # "done" => ~normalStoreEffect /\ ~normalLoadEffect)
  /\ (decision \in {"budget-stop","invalid-premise","invalid-evidence"}
        => ~normalStoreEffect /\ ~normalLoadEffect)
NormalScopePolicy ==
  /\ (normalTerminals # {} => /\ NormalEvidenceValid /\ terminalControlComplete
       /\ normalTerminals \cap barriers = {}
       /\ ~(\E e \in edges: e.src \in normalTerminals)
       /\ TerminalUses = TrackedLocations /\ TerminalMayDefs = TrackedLocations
       /\ TerminalMustDefs = {} /\ normalTerminals \subseteq opaque)
  /\ (Scenario = "TerminalUnknownStop" => Terminal \in barriers)
  /\ (normalStoreEffect \/ normalLoadEffect =>
       /\ NormalEvidenceValid /\ ~WholeMachineCoverageClaimed
       /\ NormalFlowScope = "local-normal-completion/v1")
  /\ (Scenario = "TerminalHandlerResume" => ExceptionalResumeResidues = Residues)
\* These final witnesses ensure each finite configuration exercises its intended
\* outcome. Neither empty facts nor invalid constraints can certify alignment.
ExpectedOutcome ==
  phase = "done" =>
    IF ~PremisesValid THEN decision = "invalid-premise"
    ELSE IF ~NormalEvidenceValid THEN decision = "invalid-evidence"
    ELSE IF UpdateBudget = 0 THEN decision = "budget-stop"
    ELSE IF UpdateBudget >= 32 THEN
      CASE Scenario \in {"Aligned","Captured","Unwind","LoopIdentity",
                           "TerminalInt3","TerminalUd2","TerminalUd1",
                           "TerminalHandlerResume","LoadAligned"}
           -> decision = "admit-normal"
        [] Scenario \in {"Misaligned","LateTransfer","LoadMisaligned"}
           -> decision = "refuted-normal-stop"
        [] Scenario = "Unreached" -> decision = "unreached-stop"
        [] OTHER -> decision = "normal-or-fault-stop"
    ELSE TRUE
Safety == TypeOK /\ PremisePolicy /\ ClosurePolicy /\ EffectPolicy
          /\ NormalScopePolicy /\ ExpectedOutcome
Terminates == <> (phase = "done")
=============================================================================
