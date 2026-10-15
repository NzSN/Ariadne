---------------- MODULE AriadneGuardedTargetResolution ----------------
EXTENDS Integers, FiniteSets, Sequences

\* C0 analysis-level authority for joint target/guard preparation. Nodes denote
\* semantic instruction points in one immutable snapshot and activation. Exact
\* captured bytes, typed BIL, pending MOVAPS recognition and source digests are
\* adapter premises. Neither candidate reachability nor captured memory proves
\* an executed history. This model does not reinstate the retired ISA track.
\*
\* The digest below is a structural identity, not a cryptographic model. Its
\* inputs contain no receipts or final request: source/scope -> candidate seal
\* -> target and guard receipts -> final request is deliberately acyclic.
\* @typeAlias: compositionEdge = {src: Int, dst: Int};
\* @typeAlias: compositionScope = {snapshot: Int, intent: Int, activation: Int, roots: Set(Int), seeds: Set(Int), premises: Set(Str)};
\* @typeAlias: compositionGraph = {scope: $compositionScope, epoch: Int, sites: Set(Int), original: Set($compositionEdge), pending: Set($compositionEdge), augmentation: Set($compositionEdge), barriers: Set(Int), opaque: Set(Int), covered: Bool, complete: Bool, frontier: Set(Int), frontierCovered: Bool, infeasibleContexts: Set(Int)};
Composition_typedefs == TRUE

CONSTANTS
  \* @type: Str;
  Scenario,
  \* @type: Int;
  ReadBudget,
  \* @type: Int;
  UpdateBudget

\* @type: Set(Str);
Scenarios == {"Complete", "PartialRead", "PartialBudget", "MissingCode",
              "Bypass", "Backedge", "CompletenessOnly", "BarrierOnly",
              "TransferOnly", "PendingHavoc", "OpaqueCall", "Untrusted",
              "WrongScope", "Zero", "BoundedFrontier", "UncoveredFrontier",
              "InfeasibleFrontier", "ChangedFrontier"}
ASSUME /\ Scenario \in Scenarios /\ ReadBudget \in Nat /\ UpdateBudget \in Nat

\* @type: Set(Int);
Nodes == 1..6
\* @type: Set(Int);
Indices == 0..2
\* @type: Set(Int);
Residues == 0..15
Guard == 2
Dispatch == 3
\* @type: Str;
ModelVersion == "ariadne.guarded-target-resolution/v1"
\* @type: (Int, Int) => $compositionEdge;
Edge(a,b) == [src |-> a, dst |-> b]
\* Roots and premises never grow when table destinations are discovered. Slice
\* seeds are output selectors, even when a backedge makes their node reachable.
\* @type: $compositionScope;
Scope == [snapshot |-> 1, intent |-> 1, activation |-> 1,
          roots |-> {1}, seeds |-> {6},
          premises |-> {"checked-windows-call-entry", "frozen-captured-control-data"}]
\* @type: Set($compositionEdge);
Original == {Edge(1,2), Edge(4,6), Edge(5,6)}
\* @type: Set($compositionEdge);
Pending == {Edge(2,3)}
\* Separate source-bound pending transfer: identity in the scalar bank commits
\* no ordinary memory effect, and is not derived from an alignment verdict.
PendingChecked == Scenario # "PendingHavoc"
MemoryPremise == Scenario # "Untrusted"
ScopeValid == Scenario # "WrongScope"
\* A reverse symbolic cut is a proof frontier, never an entry point. Its local
\* BIL/table form must bound the index for arbitrary scalar-register inputs.
\* The finite index set here abstracts that independently checked entailment;
\* every reverse-prefix context must be covered before completeness is true.
\* @type: Set(Int);
Frontier == IF Scenario \in {"BoundedFrontier", "UncoveredFrontier",
                              "InfeasibleFrontier", "ChangedFrontier"}
            THEN {Dispatch} ELSE {}
\* One reverse-prefix loop context needs no known table base when its source-
\* bound branch conjunction is universally false. Equality of the two symbolic
\* loads requires unchanged address/index definitions, no unknown write, and
\* the frozen-control-data premise. Those source checks are adapter premises;
\* changed or mutable contexts require independent input values. Structural
\* CFG edges remain represented, and an infeasible context is never a root.
HasLoopContext == Scenario \in {"InfeasibleFrontier", "ChangedFrontier"}
StableLoopLoad == Scenario # "ChangedFrontier"
\* @type: Set(Int);
LoopWords == 0..15
\* @type: Set({older: Int, newer: Int});
LoopAssignments == {p \in [older: LoopWords, newer: LoopWords]:
                     /\ (~StableLoopLoad \/ p.older = p.newer)
                     /\ p.older > 9 /\ p.newer <= 9}
\* @type: Set(Int);
InfeasibleContexts == IF HasLoopContext /\ LoopAssignments = {} THEN {1} ELSE {}
FrontierCovered == /\ Scenario # "UncoveredFrontier"
                   /\ (~HasLoopContext \/ LoopAssignments = {})
Readable == IF Scenario = "PartialRead" THEN {0,1} ELSE Indices
\* Decoded signed entries are supplied producer facts. Duplicate destinations
\* stay valid; an unavailable destination never makes its table entry disappear.
\* @type: Seq(Int);
Offsets == <<2,3,3>>
\* @type: Int => Int;
Target(i) == (2 + Offsets[i+1]) % 16
\* @type: Set(Int);
AllTargets == {Target(i): i \in Indices}
\* @type: Set(Str);
LateScenarios == {"Bypass", "Backedge", "CompletenessOnly", "BarrierOnly", "TransferOnly"}

VARIABLES
  \* @type: $compositionScope;
  scope,
  \* @type: Set(Int);
  remaining,
  \* @type: Set(Int);
  inspected,
  \* @type: Set(Int);
  targets,
  \* @type: Set(Int);
  sites,
  \* @type: Set(Int);
  pendingSites,
  \* @type: Set($compositionEdge);
  extraEdges,
  \* @type: Set(Int);
  barriers,
  \* @type: Set(Int);
  opaque,
  \* @type: Bool;
  covered,
  \* @type: Bool;
  complete,
  \* @type: Int;
  spent,
  \* @type: Int;
  updates,
  \* @type: Int;
  epoch,
  \* @type: Bool;
  lateChecked,
  \* @type: Int -> Set(Int);
  facts,
  \* @type: Bool;
  sealed,
  \* @type: Bool;
  guardExhausted,
  \* @type: $compositionGraph;
  receiptGraph,
  \* @type: Int;
  targetReceiptEpoch,
  \* @type: Int;
  guardReceiptEpoch,
  \* @type: Bool;
  targetReceiptComplete,
  \* @type: Str;
  guardVerdict,
  \* @type: Set($compositionEdge);
  finalEdges,
  \* @type: Bool;
  normalStore,
  \* @type: Str;
  phase,
  \* @type: Str;
  decision

vars == <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
          barriers,opaque,covered,complete,spent,updates,epoch,lateChecked,
          facts,sealed,guardExhausted,receiptGraph,targetReceiptEpoch,guardReceiptEpoch,
          targetReceiptComplete,guardVerdict,finalEdges,normalStore,phase,decision>>
\* @type: Set($compositionEdge);
SourceControl == {e \in Original: e.src \in sites}
\* @type: Set($compositionEdge);
Augmentation == {Edge(Dispatch,t): t \in targets} \cup extraEdges
\* @type: Set($compositionEdge);
CandidateEdges == SourceControl \cup Pending \cup Augmentation
\* @type: $compositionGraph;
CandidateGraph == [scope |-> scope, epoch |-> epoch, sites |-> sites,
                   original |-> SourceControl, pending |-> Pending,
                   augmentation |-> Augmentation, barriers |-> barriers,
                   opaque |-> opaque, covered |-> covered, complete |-> complete,
                   frontier |-> Frontier, frontierCovered |-> FrontierCovered,
                   infeasibleContexts |-> InfeasibleContexts]
\* @type: Int -> Set(Int);
EmptyFacts == [n \in Nodes |-> {}]
\* @type: Int -> Set(Int);
SeedFacts == [n \in Nodes |-> IF n = 1 THEN {8}
                           ELSE IF n \in barriers THEN Residues ELSE {}]
\* @type: (Int, Set(Int)) => Set(Int);
Transfer(n,rs) ==
  IF rs = {} THEN {}
  ELSE IF n \in opaque \/ (n = Guard /\ ~PendingChecked) THEN Residues
  ELSE IF n = 1 THEN {(r-8) % 16: r \in rs}
  ELSE IF n = 6 /\ Scenario = "Bypass" THEN {(r+8) % 16: r \in rs}
  ELSE rs
\* @type: (Int, Int -> Set(Int)) => Set(Int);
Incoming(n,fs) == SeedFacts[n] \cup
  UNION {Transfer(e.src,fs[e.src]): e \in {x \in CandidateEdges: x.dst = n}}
\* @type: (Int -> Set(Int)) => Bool;
Replay(fs) == /\ DOMAIN fs = Nodes
             /\ \A n \in Nodes: /\ fs[n] \subseteq Residues
                                   /\ Incoming(n,fs) \subseteq fs[n]
Fixed == Replay(facts)
Verdict == IF ~complete \/ barriers # {} \/ ~covered THEN "unknown"
           ELSE IF facts[Guard] = {} THEN "unreached"
           ELSE IF facts[Guard] = {0} THEN "aligned"
           ELSE IF 0 \notin facts[Guard] THEN "misaligned"
           ELSE "unknown"

Init ==
  /\ scope = Scope /\ remaining = Indices /\ inspected = {} /\ targets = {}
  /\ sites = {1,2,3,6} /\ pendingSites = {}
  /\ extraEdges = IF Scenario = "PendingHavoc" THEN {Edge(5,Guard)}
                  ELSE IF HasLoopContext THEN {Edge(6,Dispatch)} ELSE {}
  /\ barriers = {}
  /\ opaque = IF Scenario = "OpaqueCall" THEN {1} ELSE {}
  /\ covered = FrontierCovered /\ complete = FALSE /\ spent = 0 /\ updates = 0 /\ epoch = 0
  /\ lateChecked = (Scenario \notin LateScenarios) /\ facts = SeedFacts
  /\ sealed = FALSE /\ guardExhausted = FALSE /\ receiptGraph = CandidateGraph
  /\ targetReceiptEpoch = -1 /\ guardReceiptEpoch = -1
  /\ targetReceiptComplete = FALSE /\ guardVerdict = "none"
  /\ finalEdges = {} /\ normalStore = FALSE
  /\ phase = IF ~ScopeValid \/ ~MemoryPremise THEN "done" ELSE "discover"
  /\ decision = IF ~ScopeValid \/ ~MemoryPremise THEN "invalid-scope"
                ELSE "pending"

\* Every proof-relevant read/discovery observation advances the epoch. Receipt
\* invalidation is atomic, including observations that add no distinct edge.
Read(i) ==
  /\ phase = "discover" /\ i \in remaining /\ spent < ReadBudget
  /\ remaining' = remaining \ {i} /\ inspected' = inspected \cup {i}
  /\ targets' = IF i \in Readable THEN targets \cup {Target(i)} ELSE targets
  /\ pendingSites' = pendingSites \cup (targets' \ sites)
  /\ spent' = spent+1 /\ epoch' = epoch+1 /\ sealed' = FALSE
  /\ targetReceiptEpoch' = -1 /\ guardReceiptEpoch' = -1
  /\ targetReceiptComplete' = FALSE /\ guardVerdict' = "none"
  /\ UNCHANGED <<scope,sites,extraEdges,barriers,opaque,covered,complete,
                  updates,lateChecked,facts,guardExhausted,receiptGraph,finalEdges,normalStore,phase,decision>>
Discover(n) ==
  /\ phase = "discover" /\ n \in pendingSites
  /\ sites' = sites \cup {n} /\ pendingSites' = pendingSites \ {n}
  /\ barriers' = IF Scenario = "MissingCode" /\ n = 5 THEN barriers \cup {5}
                 ELSE barriers
  /\ epoch' = epoch+1 /\ sealed' = FALSE
  /\ targetReceiptEpoch' = -1 /\ guardReceiptEpoch' = -1
  /\ targetReceiptComplete' = FALSE /\ guardVerdict' = "none"
  /\ UNCHANGED <<scope,remaining,inspected,targets,extraEdges,opaque,covered,complete,
                  spent,updates,lateChecked,facts,guardExhausted,receiptGraph,finalEdges,normalStore,phase,decision>>
FinishDiscovery ==
  /\ phase = "discover" /\ pendingSites = {}
  /\ (remaining = {} \/ spent = ReadBudget)
  /\ complete' = (MemoryPremise /\ covered /\ remaining = {} /\ Indices \subseteq Readable)
  /\ epoch' = epoch+1 /\ facts' = SeedFacts /\ phase' = "propagate"
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,covered,spent,updates,lateChecked,sealed,guardExhausted,
                  receiptGraph,targetReceiptEpoch,guardReceiptEpoch,targetReceiptComplete,
                  guardVerdict,finalEdges,normalStore,decision>>
Propagate(n) ==
  /\ phase = "propagate" /\ n \in Nodes /\ updates < UpdateBudget
  /\ ~(Incoming(n,facts) \subseteq facts[n])
  /\ facts' = [facts EXCEPT ![n] = @ \cup Incoming(n,facts)]
  /\ updates' = updates+1
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,covered,complete,spent,epoch,lateChecked,sealed,guardExhausted,
                  receiptGraph,targetReceiptEpoch,guardReceiptEpoch,targetReceiptComplete,
                  guardVerdict,finalEdges,normalStore,phase,decision>>
Seal ==
  /\ phase = "propagate" /\ Fixed /\ pendingSites = {}
  /\ sealed' = TRUE /\ receiptGraph' = CandidateGraph /\ phase' = "certify"
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,covered,complete,spent,updates,epoch,lateChecked,
                  facts,guardExhausted,targetReceiptEpoch,guardReceiptEpoch,targetReceiptComplete,
                  guardVerdict,finalEdges,normalStore,decision>>
Certify ==
  /\ phase = "certify" /\ sealed /\ Fixed /\ receiptGraph = CandidateGraph
  /\ targetReceiptEpoch' = epoch /\ guardReceiptEpoch' = epoch
  /\ targetReceiptComplete' = complete /\ guardVerdict' = Verdict
  /\ phase' = "revalidate"
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,covered,complete,spent,updates,epoch,lateChecked,
                  facts,sealed,guardExhausted,receiptGraph,finalEdges,normalStore,decision>>
\* Completeness-only, barrier-only and transfer-only changes are not hidden by
\* equality of target sets. Both receipt families become stale. The known
\* destination set is monotone even if incoming coverage must be downgraded.
DiscoverLate ==
  /\ phase = "revalidate" /\ ~lateChecked
  /\ extraEdges' = CASE Scenario = "Bypass" -> extraEdges \cup {Edge(6,Guard)}
                       [] Scenario = "Backedge" -> extraEdges \cup {Edge(5,Dispatch)}
                       [] OTHER -> extraEdges
  /\ barriers' = IF Scenario = "BarrierOnly" THEN barriers \cup {6} ELSE barriers
  /\ opaque' = IF Scenario = "TransferOnly" THEN opaque \cup {1} ELSE opaque
  /\ covered' = IF Scenario \in {"Bypass","Backedge","CompletenessOnly"}
                THEN FALSE ELSE covered
  /\ complete' = IF Scenario \in {"Bypass","Backedge","CompletenessOnly"}
                 THEN FALSE ELSE complete
  /\ epoch' = epoch+1 /\ lateChecked' = TRUE /\ sealed' = FALSE
  /\ guardExhausted' = FALSE
  /\ targetReceiptEpoch' = -1 /\ guardReceiptEpoch' = -1
  /\ targetReceiptComplete' = FALSE /\ guardVerdict' = "none"
  /\ facts' = SeedFacts /\ phase' = "propagate"
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,spent,updates,
                  receiptGraph,finalEdges,normalStore,decision>>
\* Once candidate discovery can be frozen, exhausted guard work can still
\* publish paired, sealed partial evidence and a stopped final request. No
\* alignment verdict is manufactured from the unfinished residue map. A
\* materialization failure before candidate freeze has no such publication.
BudgetStop ==
  /\ phase = "propagate" /\ ~Fixed /\ updates = UpdateBudget
  /\ phase' = "done" /\ decision' = "budget-stop" /\ sealed' = TRUE
  /\ guardExhausted' = TRUE
  /\ covered' = (covered /\ lateChecked)
  /\ complete' = (complete /\ lateChecked)
  /\ epoch' = IF covered /\ ~lateChecked THEN epoch+1 ELSE epoch
  /\ receiptGraph' = [CandidateGraph EXCEPT !.epoch = epoch',
                        !.covered = covered', !.complete = complete']
  /\ targetReceiptEpoch' = epoch' /\ guardReceiptEpoch' = epoch'
  /\ targetReceiptComplete' = complete' /\ guardVerdict' = "budget-stop"
  /\ finalEdges' = CandidateEdges \ Pending /\ normalStore' = FALSE
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,spent,updates,lateChecked,facts>>
Publish ==
  /\ phase = "revalidate" /\ lateChecked /\ sealed /\ Fixed
  /\ targetReceiptEpoch = epoch /\ guardReceiptEpoch = epoch
  /\ receiptGraph = CandidateGraph /\ targetReceiptComplete = complete
  /\ guardVerdict = Verdict /\ scope = Scope /\ ScopeValid /\ MemoryPremise
  /\ normalStore' = (guardVerdict = "aligned")
  /\ finalEdges' = IF normalStore' THEN CandidateEdges ELSE CandidateEdges \ Pending
  /\ decision' = IF normalStore' THEN "admit-normal" ELSE "guard-unknown-stop"
  /\ phase' = "done"
  /\ UNCHANGED <<scope,remaining,inspected,targets,sites,pendingSites,extraEdges,
                  barriers,opaque,covered,complete,spent,updates,epoch,lateChecked,
                  facts,sealed,guardExhausted,receiptGraph,targetReceiptEpoch,guardReceiptEpoch,
                  targetReceiptComplete,guardVerdict>>

Next == (\E i \in remaining: Read(i)) \/ (\E n \in pendingSites: Discover(n))
        \/ FinishDiscovery \/ (\E n \in Nodes: Propagate(n)) \/ Seal \/ Certify
        \/ DiscoverLate \/ BudgetStop \/ Publish
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

TypeOK ==
  /\ scope = Scope /\ remaining \subseteq Indices /\ inspected \subseteq Indices
  /\ targets \subseteq AllTargets /\ sites \subseteq Nodes /\ pendingSites \subseteq Nodes
  /\ barriers \subseteq Nodes /\ opaque \subseteq Nodes
  /\ \A e \in extraEdges \cup finalEdges: e.src \in Nodes /\ e.dst \in Nodes
  /\ spent \in 0..ReadBudget /\ updates \in 0..UpdateBudget
  /\ epoch \in 0..7 /\ targetReceiptEpoch \in -1..7 /\ guardReceiptEpoch \in -1..7
  /\ covered \in BOOLEAN /\ complete \in BOOLEAN /\ lateChecked \in BOOLEAN
  /\ sealed \in BOOLEAN /\ guardExhausted \in BOOLEAN /\ normalStore \in BOOLEAN
  /\ facts \in [Nodes -> SUBSET Residues]
  /\ phase \in {"discover","propagate","certify","revalidate","done"}
  /\ decision \in {"pending","invalid-scope","budget-stop","admit-normal","guard-unknown-stop"}
  /\ guardVerdict \in {"none","aligned","misaligned","unreached","unknown","budget-stop"}
SourcePolicy ==
  /\ SourceControl = {e \in Original: e.src \in sites}
  /\ scope.roots = {1} /\ scope.seeds = {6}
  /\ targets = {Target(i): i \in inspected \cap Readable}
  /\ inspected = Indices \ remaining /\ spent = Cardinality(inspected)
  /\ (complete => /\ MemoryPremise /\ covered /\ remaining = {}
                   /\ Indices \subseteq Readable /\ AllTargets \subseteq targets)
ReceiptPolicy ==
  /\ (sealed => Fixed \/ guardExhausted)
  /\ (targetReceiptEpoch >= 0 => /\ targetReceiptEpoch = epoch
        /\ guardReceiptEpoch = epoch /\ sealed /\ receiptGraph = CandidateGraph
        /\ targetReceiptComplete = complete
        /\ guardVerdict = IF guardExhausted THEN "budget-stop" ELSE Verdict)
  /\ (guardReceiptEpoch >= 0 => targetReceiptEpoch = epoch)
FinalPolicy ==
  /\ finalEdges \subseteq CandidateEdges
  /\ normalStore = (decision = "admit-normal")
  /\ (phase # "done" => ~normalStore /\ finalEdges = {})
  /\ (finalEdges # {} => /\ sealed /\ targetReceiptEpoch = epoch
        /\ guardReceiptEpoch = epoch /\ receiptGraph = CandidateGraph)
  /\ (normalStore => /\ ScopeValid /\ MemoryPremise /\ sealed /\ lateChecked
        /\ targetReceiptEpoch = epoch /\ guardReceiptEpoch = epoch
        /\ receiptGraph = CandidateGraph /\ Replay(facts)
        /\ guardVerdict = "aligned" /\ facts[Guard] = {0}
        /\ complete /\ covered /\ ~guardExhausted
        /\ barriers = {} /\ finalEdges = CandidateEdges)
  /\ (~normalStore => finalEdges \cap Pending = {})
FrontierPolicy ==
  /\ (InfeasibleContexts # {} => /\ HasLoopContext /\ StableLoopLoad
        /\ MemoryPremise /\ LoopAssignments = {} /\ Frontier = {Dispatch})
  /\ (HasLoopContext => Edge(6,Dispatch) \in CandidateEdges)
  /\ (Scenario = "ChangedFrontier" => /\ LoopAssignments # {}
        /\ InfeasibleContexts = {} /\ ~FrontierCovered /\ ~complete)
  /\ scope.roots = {1} /\ Dispatch \notin scope.roots
ExpectedOutcome ==
  phase = "done" =>
    IF ~ScopeValid \/ ~MemoryPremise THEN decision = "invalid-scope"
    ELSE IF UpdateBudget = 0 THEN decision = "budget-stop"
    ELSE IF UpdateBudget >= 64 THEN
      IF Scenario \in {"Complete","BoundedFrontier","InfeasibleFrontier"}
      THEN decision = "admit-normal"
      ELSE decision = "guard-unknown-stop"
    ELSE TRUE
Safety == TypeOK /\ SourcePolicy /\ ReceiptPolicy /\ FinalPolicy /\ FrontierPolicy /\ ExpectedOutcome
Terminates == <> (phase = "done")
=============================================================================
