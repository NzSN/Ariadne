----------------------- MODULE AriadneFrameStructure -----------------------
EXTENDS AriadneMachineCommon, Sequences

\* Stage 5.1 authority: a finite recovery-prefix and frame-link contract.
\* The machine analyzes immutable final requests, not the captured CPU. It
\* preserves attempted/decoded starts, semantic VAs, exact typed local/call
\* edges, provenance, obligations, pending work and activation identity.
\* Deterministic Visit is Ariadne.tla's action restricted to the least pending
\* VA; no FinishRecovery, reaching-definition or slicing action exists here.
\* Mathematical graph records abstract concrete bytes, instruction effects,
\* hashes, decoder/proof parsing and allocation. ValidEvidence is the PREMISE
\* that successful final preparation and concrete source/guard/target/paired
\* proof checks agree. Rejected scenarios are negative premise controls, not a
\* claim that TLA proves those concrete validators. Budget/deadline checkpoints
\* abstract cooperative producer receipts; ReplayBudget is a separate trusted
\* host cap. HostCapacity abstracts a checked finite source/proof/graph/output
\* envelope. These units do not qualify real byte sizing or elapsed time.
\* A fair finite check is not universal Rust/native refinement or path proof.
\* @typeAlias: structureEdge = {src: Int, dst: Int, kind: Str};
\* @typeAlias: structureObligation = {site: Int, reason: Str};
FrameStructure_typedefs == TRUE
CONSTANTS
  \* @type: Str;
  Scenario,
  \* @type: Int;
  Budget,
  \* @type: Int;
  DeadlineAt,
  \* @type: Int;
  HostCapacity,
  \* @type: Int;
  ReplayBudget

Scenarios == {"Straight", "Diamond", "Cycle", "UnreachableSeed", "Call",
  "Failed", "MissingBytes", "Boundary", "Indirect", "UnknownGuard",
  "Recursion", "WorkStopped", "ZeroWork", "Deadline", "PrepareUnavailable",
  "ChildUnavailable", "ParentUnavailable", "UnreachedCall", "UncapturedCall",
  "WrongContinuation", "WrongTarget", "AmbiguousCall", "InvalidCapture",
  "InvalidProof", "MissingProof", "WrongSnapshot", "WrongActivation",
  "WrongProducer", "WrongEpoch", "CandidatePromotion", "HostLimit",
  "HostExact", "HostAbove", "ReplayLimit", "ReplayExact", "PendingChild", "FailedChild"}
ASSUME /\ Scenario \in Scenarios
       /\ Budget \in Nat /\ DeadlineAt \in Nat
       /\ HostCapacity \in Nat /\ ReplayBudget \in Nat
Frames == {0,1}
Addresses == {10,20,30,40,100}
ValidEvidence == Scenario \notin {"InvalidCapture", "InvalidProof", "MissingProof",
  "WrongSnapshot", "WrongActivation", "WrongProducer", "WrongEpoch",
  "CandidatePromotion"}
HostRequired == 5
Admitted == ValidEvidence /\ HostCapacity >= HostRequired
PreparedFrames ==
  IF Scenario = "PrepareUnavailable" THEN {}
  ELSE IF Scenario = "ChildUnavailable" THEN {1}
  ELSE IF Scenario = "ParentUnavailable" THEN {0}
  ELSE Frames
ActiveFrames == IF Admitted THEN PreparedFrames ELSE {}
IsCallScenario == Scenario \in {"Call", "Recursion", "ChildUnavailable",
  "ParentUnavailable", "UnreachedCall", "UncapturedCall", "WrongContinuation",
  "WrongTarget", "AmbiguousCall", "PendingChild", "FailedChild"}
\* @type: Int => Int;
Root(f) == IF f = 0 THEN IF Scenario = "Recursion" THEN 10 ELSE 100
           ELSE IF Scenario = "UnreachedCall" THEN 20 ELSE 10
\* @type: Int => Set(Int);
Roots(f) == IF f \in ActiveFrames THEN {Root(f)} ELSE {}
\* Slice seed 30 in UnreachableSeed is deliberately absent from Roots.
SliceSeeds == IF Scenario = "UnreachableSeed" THEN {30} ELSE {}
\* @type: (Int, Int) => Str;
Kind(f,a) ==
  IF f = 0 THEN "return"
  ELSE IF a = 10 /\ IsCallScenario THEN "call"
  ELSE IF a = 10 /\ Scenario = "Diamond" THEN "conditional"
  ELSE IF a = 10 /\ Scenario = "Indirect" THEN "indirect"
  ELSE IF a = 20 /\ Scenario = "Cycle" THEN "jump"
  ELSE IF a = 20 /\ Scenario = "UnknownGuard" THEN "stop"
  ELSE IF a = 10 \/ (a \in {20,30} /\ Scenario = "Diamond") THEN "ordinary"
  ELSE "return"
\* @type: (Int, Int) => Set(Int);
Fall(f,a) ==
  IF f = 1 /\ a = 10 /\ Kind(f,a) \in {"ordinary","call","conditional"}
  THEN {IF Scenario = "Boundary" THEN 40 ELSE 20}
  ELSE IF f = 1 /\ a \in {20,30} /\ Scenario = "Diamond" THEN {40}
  ELSE {}
\* @type: (Int, Int) => Set(Int);
Target(f,a) ==
  IF f = 1 /\ a = 10 /\ IsCallScenario THEN
    {IF Scenario = "Recursion" THEN 10
     ELSE IF Scenario = "WrongTarget" THEN 30 ELSE 100}
  ELSE IF f = 1 /\ a = 10 /\ Scenario = "Diamond" THEN {30}
  ELSE IF f = 1 /\ a = 10 /\ Scenario = "Indirect" THEN {20}
  ELSE IF f = 1 /\ a = 20 /\ Scenario = "Cycle" THEN {10}
  ELSE {}
\* @type: (Int, Int) => Str;
Source(f,a) ==
  IF f = 1 /\ ((a = 20 /\ Scenario = "MissingBytes") \/
     (a = 40 /\ Scenario = "Boundary")) THEN "unavailable" ELSE "captured"
\* @type: (Int, Int) => Bool;
CanDecode(f,a) == Source(f,a) # "unavailable" /\
  ~(f = 1 /\ a = 20 /\ Scenario \in {"Failed","UnknownGuard"}) /\
  ~(f = 0 /\ a = Root(0) /\ Scenario = "FailedChild")
\* PendingChild spends no child Visit work while the caller can still recover.
\* An independently known root is insufficient for an admitted frame CALL.
\* @type: Int => Int;
FrameBudget(f) == IF f = 0 /\ Scenario = "PendingChild" THEN 0 ELSE Budget
\* @type: (Int, Int, Str) => $structureEdge;
Edge(a,b,k) == MachineEdge(a,b,k)
\* @type: (Int, Int) => Set($structureEdge);
InstructionEdges(f,a) ==
  (CASE Kind(f,a) = "ordinary" -> {Edge(a,b,"next"): b \in Fall(f,a)}
     [] Kind(f,a) = "conditional" ->
        {Edge(a,b,"fallthrough"): b \in Fall(f,a)} \cup
        {Edge(a,b,"taken"): b \in Target(f,a)}
     [] Kind(f,a) = "jump" -> {Edge(a,b,"jump"): b \in Target(f,a)}
     [] Kind(f,a) = "indirect" -> {Edge(a,b,"indirect"): b \in Target(f,a)}
     [] Kind(f,a) = "call" ->
        {Edge(a,b,"summary"): b \in Fall(f,a)} \cup
        {Edge(a,b,"call"): b \in Target(f,a)}
     [] OTHER -> {})
\* @type: $structureEdge => Bool;
Local(e) == e.kind \in MachineLocalEdgeKinds
\* Scope classification is additional frame evidence, never a deletion of a
\* structural edge or a new root. Boundary 40 is still attempted once.
\* @type: Int => Set(Int);
DeclaredFunction(f) == IF f = 0 THEN {Root(0)}
                       ELSE IF Scenario = "Boundary" THEN {10,20,30}
                       ELSE Addresses
\* @type: (Int, Int) => Set(Int);
LocalSuccessors(f,a) ==
  {e.dst: e \in {x \in InstructionEdges(f,a): Local(x)}}
\* @type: (Int, Str) => $structureObligation;
Obligation(a,r) == [site |-> a, reason |-> r]
\* @type: (Int, Int) => Set($structureObligation);
DecodeObligations(f,a) ==
  IF Kind(f,a) = "indirect" THEN {Obligation(a,"indirect-targets")} ELSE {}
\* @type: (Int, Int) => Str;
Failure(f,a) == IF Source(f,a) = "unavailable" THEN "unavailable" ELSE "decode-failed"
\* @type: Set(Int) => Int;
Min(s) == CHOOSE a \in s: \A b \in s: a <= b
VARIABLES
  \* @type: Int -> Set(Int);
  pending,
  \* @type: Int -> Set(Int);
  visited,
  \* @type: Int -> Set(Int);
  decoded,
  \* @type: Int -> Set($structureEdge);
  edges,
  \* @type: Int -> Set($structureObligation);
  obligations,
  \* @type: Int -> (Int -> Str);
  provenance,
  \* @type: Int -> Int;
  visits,
  \* @type: Set(Int);
  sealed,
  \* @type: Int -> Str;
  stop,
  \* @type: Str;
  phase,
  \* @type: Str;
  result,
  \* @type: Int;
  replayRemaining,
  \* @type: Int;
  replayWork,
  \* @type: Int;
  finishRecoveryActions,
  \* @type: Int;
  dataflowActions,
  \* @type: Int;
  sliceActions,
  \* @type: Bool;
  linked
vars == <<pending,visited,decoded,edges,obligations,provenance,visits,sealed,
  stop,phase,result,replayRemaining,replayWork,finishRecoveryActions,
  dataflowActions,sliceActions,linked>>
Init ==
  /\ pending = [f \in Frames |-> Roots(f)]
  /\ visited = [f \in Frames |-> {}] /\ decoded = [f \in Frames |-> {}]
  /\ edges = [f \in Frames |-> {}] /\ obligations = [f \in Frames |-> {}]
  /\ provenance = [f \in Frames |-> [a \in Addresses |-> "unavailable"]]
  /\ visits = [f \in Frames |-> 0] /\ sealed = Frames \ ActiveFrames
  /\ stop = [f \in Frames |-> IF f \in ActiveFrames THEN "" ELSE "unavailable"]
  /\ phase = IF ~Admitted THEN "done" ELSE "recover"
  /\ result = IF ~ValidEvidence THEN "invalid"
               ELSE IF ~Admitted THEN "verification_stopped" ELSE ""
  /\ replayRemaining = 0 /\ replayWork = 0 /\ linked = FALSE
  /\ finishRecoveryActions = 0 /\ dataflowActions = 0 /\ sliceActions = 0
\* @type: (Int, Int) => Bool;
Visit(f,a) ==
  /\ phase = "recover" /\ f \in ActiveFrames \ sealed
  /\ f = Min(ActiveFrames \ sealed) /\ a \in pending[f] /\ a = Min(pending[f])
  /\ visits[f] < FrameBudget(f) /\ visits[f] < DeadlineAt
  /\ visited' = [visited EXCEPT ![f] = @ \cup {a}]
  /\ visits' = [visits EXCEPT ![f] = @ + 1]
  /\ IF CanDecode(f,a)
     THEN /\ decoded' = [decoded EXCEPT ![f] = @ \cup {a}]
          /\ provenance' = [provenance EXCEPT ![f][a] = Source(f,a)]
          /\ edges' = [edges EXCEPT ![f] = @ \cup InstructionEdges(f,a)]
          /\ obligations' = [obligations EXCEPT ![f] = @ \cup DecodeObligations(f,a)]
          /\ pending' = [pending EXCEPT ![f] =
               (@ \cup LocalSuccessors(f,a)) \ visited'[f]]
     ELSE /\ pending' = [pending EXCEPT ![f] = @ \ {a}]
          /\ obligations' = [obligations EXCEPT ![f] = @ \cup {Obligation(a,Failure(f,a))}]
          /\ UNCHANGED <<decoded,provenance,edges>>
  /\ UNCHANGED <<sealed,stop,phase,result,replayRemaining,replayWork,
       finishRecoveryActions,dataflowActions,sliceActions,linked>>
\* @type: Int => Bool;
Seal(f) ==
  /\ phase = "recover" /\ f \in ActiveFrames \ sealed
  /\ f = Min(ActiveFrames \ sealed)
  /\ (pending[f] = {} \/ visits[f] = FrameBudget(f) \/ visits[f] >= DeadlineAt)
  /\ sealed' = sealed \cup {f}
  /\ stop' = [stop EXCEPT ![f] =
       IF pending[f] = {} THEN "drained"
       ELSE IF visits[f] = FrameBudget(f) THEN "visit_limit" ELSE "deadline"]
  /\ UNCHANGED <<pending,visited,decoded,edges,obligations,provenance,visits,
       phase,result,replayRemaining,replayWork,finishRecoveryActions,
       dataflowActions,sliceActions,linked>>
ReplayCost == visits[0] + visits[1] + Cardinality(edges[0]) + Cardinality(edges[1]) + 1
BeginReplay ==
  /\ phase = "recover" /\ sealed = Frames
  /\ phase' = "verify" /\ replayRemaining' = ReplayCost
  /\ UNCHANGED <<pending,visited,decoded,edges,obligations,provenance,visits,
       sealed,stop,result,replayWork,finishRecoveryActions,dataflowActions,sliceActions,linked>>
ReplayStep ==
  /\ phase = "verify" /\ replayRemaining > 0 /\ replayWork < ReplayBudget
  /\ replayRemaining' = replayRemaining - 1 /\ replayWork' = replayWork + 1
  /\ UNCHANGED <<pending,visited,decoded,edges,obligations,provenance,visits,
       sealed,stop,phase,result,finishRecoveryActions,dataflowActions,sliceActions,linked>>
\* The E8/capture predicates are finite admitted controls. Concrete signed E8
\* arithmetic, span evidence and unwind parsing remain validator premises.
LinkPremises ==
  /\ Frames \subseteq ActiveFrames /\ IsCallScenario /\ 10 \in decoded[1]
  /\ Root(0) \in decoded[0]
  /\ Scenario \notin {"UncapturedCall","WrongContinuation","AmbiguousCall"}
  /\ Source(1,10) = "captured" /\ Kind(1,10) = "call"
  /\ 20 \in Fall(1,10) /\ Root(0) \in Target(1,10)
\* @type: Int => Set($structureEdge);
OutOfFunctionEdges(f) == {e \in edges[f]: Local(e) /\ e.dst \notin DeclaredFunction(f)}
HasGaps ==
  /\ ActiveFrames # {}
  /\ (ActiveFrames # Frames \/ \E f \in ActiveFrames:
       pending[f] # {} \/ obligations[f] # {} \/ OutOfFunctionEdges(f) # {} \/
       (IsCallScenario /\ ~LinkPremises))
EndReplay ==
  /\ phase = "verify" /\ (replayRemaining = 0 \/ replayWork = ReplayBudget)
  /\ phase' = "done"
  /\ result' = IF replayRemaining > 0 THEN "verification_stopped"
                ELSE IF ActiveFrames = {} THEN "unavailable"
                ELSE IF HasGaps THEN "partial" ELSE "available"
  /\ linked' = (replayRemaining = 0 /\ LinkPremises)
  /\ UNCHANGED <<pending,visited,decoded,edges,obligations,provenance,visits,
       sealed,stop,replayRemaining,replayWork,finishRecoveryActions,dataflowActions,sliceActions>>
Next == (\E f \in Frames: \E a \in Addresses: Visit(f,a))
        \/ (\E f \in Frames: Seal(f)) \/ BeginReplay \/ ReplayStep \/ EndReplay
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
\* @type: Int => Set($structureEdge);
ExpectedEdges(f) == UNION {InstructionEdges(f,a): a \in decoded[f]}
\* @type: Int => Set($structureObligation);
ExpectedObligations(f) ==
  UNION {DecodeObligations(f,a): a \in decoded[f]} \cup
  {Obligation(a,Failure(f,a)): a \in visited[f] \ decoded[f]}
RecoveryInvariant == \A f \in Frames:
  /\ decoded[f] = {a \in visited[f]: CanDecode(f,a)}
  /\ pending[f] \cap visited[f] = {}
  /\ pending[f] \cup visited[f] = Roots(f) \cup
       {e.dst: e \in {x \in edges[f]: Local(x)}}
  /\ edges[f] = ExpectedEdges(f) /\ obligations[f] = ExpectedObligations(f)
  /\ visits[f] = Cardinality(visited[f]) /\ visits[f] <= FrameBudget(f)
  /\ \A a \in Addresses:
       provenance[f][a] = IF a \in decoded[f] THEN Source(f,a) ELSE "unavailable"
PrefixBoundary ==
  /\ finishRecoveryActions = 0 /\ dataflowActions = 0 /\ sliceActions = 0
  /\ \A f \in ActiveFrames \cap sealed:
       /\ stop[f] \in {"drained","visit_limit","deadline"}
       /\ (stop[f] = "drained" <=> pending[f] = {})
       /\ (stop[f] = "visit_limit" => visits[f] = FrameBudget(f) /\ pending[f] # {})
       /\ (stop[f] = "deadline" => visits[f] >= DeadlineAt /\ pending[f] # {})
Trusted == phase = "done" /\ result \in {"available","partial"}
TrustBoundary ==
  /\ (Trusted => Admitted /\ replayRemaining = 0 /\ replayWork <= ReplayBudget)
  /\ (linked => Trusted /\ LinkPremises)
  /\ (~ValidEvidence => result = "invalid" /\ ~linked)
  /\ (HostCapacity < HostRequired => ~Trusted)
  /\ (result = "verification_stopped" => ~Trusted /\ ~linked)
  /\ (result = "available" => ~HasGaps)
ScenarioOutcome == phase = "done" =>
  /\ (Scenario \in {"Call","Recursion"} /\ Budget >= 2 /\ DeadlineAt >= 2 /\
       ReplayBudget >= ReplayCost /\ Admitted => linked)
  /\ (Scenario \in {"UnreachedCall","UncapturedCall","WrongContinuation",
       "WrongTarget","AmbiguousCall","ParentUnavailable","ChildUnavailable",
       "PendingChild","FailedChild"} => ~linked)
  /\ (Scenario = "UnreachableSeed" => 30 \notin visited[1])
  /\ (Scenario = "UnknownGuard" => 30 \notin pending[1] \cup visited[1])
  /\ (Scenario = "Cycle" /\ Budget >= 2 /\ DeadlineAt >= 2 /\ Admitted =>
       visits[1] = 2 /\ stop[1] = "drained")
  /\ (Scenario = "Call" => 100 \notin pending[1] \cup visited[1])
  /\ (Scenario = "Boundary" /\ Budget >= 2 /\ DeadlineAt >= 2 /\ Admitted =>
       Edge(10,40,"next") \in OutOfFunctionEdges(1) /\ 40 \in visited[1] /\
       40 \notin decoded[1] /\ Obligation(40,"unavailable") \in obligations[1])
  /\ (Scenario = "ParentUnavailable" /\ Budget > 0 /\ DeadlineAt > 0 /\ Admitted =>
       decoded[0] = {100} /\ decoded[1] = {})
  /\ (Scenario = "PendingChild" /\ Budget >= 2 /\ DeadlineAt >= 2 /\ Admitted =>
       10 \in decoded[1] /\ Root(0) \in pending[0] /\ decoded[0] = {} /\
       stop[0] = "visit_limit" /\ ~linked)
  /\ (Scenario = "FailedChild" /\ Budget >= 2 /\ DeadlineAt >= 2 /\ Admitted =>
       10 \in decoded[1] /\ Root(0) \in visited[0] /\ decoded[0] = {} /\
       Obligation(Root(0),"decode-failed") \in obligations[0] /\ ~linked)
TypeOK ==
  /\ phase \in {"recover","verify","done"}
  /\ result \in {"","available","partial","unavailable","invalid","verification_stopped"}
  /\ sealed \subseteq Frames /\ linked \in BOOLEAN
  /\ replayWork \in 0..ReplayBudget /\ replayRemaining \in Nat
  /\ \A f \in Frames:
       /\ pending[f] \subseteq Addresses /\ visited[f] \subseteq Addresses
       /\ decoded[f] \subseteq Addresses
Safety == TypeOK /\ RecoveryInvariant /\ PrefixBoundary /\ TrustBoundary /\ ScenarioOutcome
Terminates == <> (phase = "done")
=============================================================================
