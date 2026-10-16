------------------- MODULE AriadneAlignmentHypothesis -------------------
EXTENDS Integers, FiniteSets, Sequences

\* Additive authority for explicitly conditional MOVAPS aligned16 selection.
\* Existing AriadnePredicateAdmission/GuardedTargetResolution authorities and
\* their proof identities remain unchanged. This finite companion preserves
\* original candidate edges, roots and baseline verdicts, and computes a second
\* root-driven least product closure with instruction-local hypothesis filters.
\* Hypotheses apply on EVERY visit in one physical activation, never as roots.
\* Exact captured bytes/BIL/decoder identity, reviewed predicate recognition,
\* original target/composition replay and final projection are trusted concrete
\* binding premises here. Mathematical residues do not prove ISA semantics,
\* canonical addresses, memory readability, exception absence or execution.
\* An open/exhausted computation cannot select a normal effect or establish
\* contradiction. A closed empty intersection blocks only the conditional
\* normal branch. The original unknown/exception alternative is retained.
\* @typeAlias: hypothesisState = {activation: Int, site: Int, residue: Int};
\* @typeAlias: hypothesisEdge = {src: Int, dst: Int};
AlignmentHypothesis_typedefs == TRUE
CONSTANTS
  \* @type: Str;
  Scenario,
  \* @type: Int;
  WorkBudget,
  \* @type: Int;
  ClosureLimit
Scenarios == {"Unknown", "Aligned", "Misaligned", "Unreached", "Open", "Zero",
  "Mixed", "SignedDisplacement", "TwoHypotheses", "Bypass", "Clobber", "Loop",
  "RecursiveActivation", "NoHypotheses", "SelfSupport", "BadSource", "BadScope",
  "BadProfile", "BadEpoch", "BadPredicate", "BadDecoder", "ChangedFinal"}
ASSUME /\ Scenario \in Scenarios /\ WorkBudget \in Nat /\ ClosureLimit \in Nat
Nodes == 1..5
Residues == 0..15
Activations == IF Scenario = "RecursiveActivation" THEN {1,2} ELSE {1}
SourceValid == Scenario \notin {"BadSource","BadDecoder","BadPredicate"}
ScopeValid == Scenario \notin {"BadScope","BadProfile","BadEpoch"}
FinalProjectionValid == Scenario # "ChangedFinal"
Closed == Scenario # "Open"
CandidateEpoch == 3
WithinEpochLimit == CandidateEpoch < ClosureLimit
Valid == SourceValid /\ ScopeValid /\ FinalProjectionValid
Roots == IF Scenario = "SelfSupport" THEN {5} ELSE {1}
HypothesisSites == IF Scenario = "NoHypotheses" THEN {}
                   ELSE IF Scenario = "TwoHypotheses" THEN {2,4} ELSE {2}
Guards == {2} \cup (IF Scenario \in {"TwoHypotheses","Clobber","Bypass"} THEN {4} ELSE {})
\* @type: (Int, Int) => $hypothesisEdge;
Edge(a,b) == [src |-> a, dst |-> b]
CandidateEdges ==
  (IF Scenario = "Unreached" THEN {Edge(2,3),Edge(3,4)}
   ELSE IF Scenario = "SelfSupport" THEN {Edge(2,3),Edge(3,2)}
   ELSE {Edge(1,2),Edge(2,3),Edge(3,4)})
  \cup (IF 4 \in Guards THEN {Edge(4,5)} ELSE {})
  \cup (IF Scenario = "Bypass" THEN {Edge(1,3)} ELSE {})
  \cup (IF Scenario = "Loop" THEN {Edge(3,2)} ELSE {})
InitialResidues == IF Scenario = "Aligned" THEN {0}
                   ELSE IF Scenario = "Misaligned" THEN {4}
                   ELSE IF Scenario = "Mixed" THEN {0,4} ELSE Residues
\* @type: Int => Int;
Displacement(n) == IF Scenario = "SignedDisplacement" /\ n = 2 THEN -8
                   ELSE IF Scenario = "TwoHypotheses" /\ n = 4 THEN 8 ELSE 0
\* @type: (Int, Int) => Set(Int);
Transfer(n,r) ==
  IF Scenario = "Clobber" /\ n = 3 THEN Residues
  ELSE IF Scenario = "TwoHypotheses" /\ n = 3 THEN {(r+8)%16}
  ELSE IF Scenario = "Loop" /\ n = 3 THEN {(r+8)%16}
  ELSE {r}
\* @type: (Int, Int, Int) => $hypothesisState;
State(a,n,r) == [activation |-> a, site |-> n, residue |-> r]
Initial == {State(a,n,r): a \in Activations, n \in Roots, r \in InitialResidues}
\* @type: ($hypothesisState, Bool) => Bool;
Allowed(s,conditional) == ~conditional \/ s.activation # 1 \/ s.site \notin HypothesisSites
                          \/ (s.residue+Displacement(s.site))%16 = 0
\* @type: ($hypothesisState, Bool) => Set($hypothesisState);
Successors(s,conditional) ==
  IF ~Allowed(s,conditional) THEN {}
  ELSE {State(s.activation,e.dst,r): e \in {x \in CandidateEdges: x.src=s.site},
                                     r \in Transfer(s.site,s.residue)}
\* @type: $hypothesisState => Int;
Rank(s) == s.activation*256+s.site*16+s.residue
\* @type: Set($hypothesisState) => $hypothesisState;
First(states) == CHOOSE s \in states: \A other \in states: Rank(s) <= Rank(other)
VARIABLES
  \* @type: Set($hypothesisState);
  baselineSeen,
  \* @type: Set($hypothesisState);
  baselinePending,
  \* @type: Set($hypothesisState);
  conditionalSeen,
  \* @type: Set($hypothesisState);
  conditionalPending,
  \* @type: Int;
  work,
  \* @type: Str;
  phase,
  \* @type: Str;
  status
vars == <<baselineSeen,baselinePending,conditionalSeen,conditionalPending,work,phase,status>>
Init ==
  /\ baselineSeen = {} /\ conditionalSeen = {}
  /\ baselinePending = IF Valid THEN Initial ELSE {}
  /\ conditionalPending = {}
  /\ work = 0
  /\ phase = IF Valid THEN "baseline" ELSE "done"
  /\ status = IF ~Valid THEN "invalid" ELSE "pending"
VisitBaseline ==
  /\ phase="baseline" /\ baselinePending # {}
  /\ LET s == First(baselinePending) IN
       /\ baselineSeen'=baselineSeen \cup {s}
       /\ baselinePending'=(baselinePending \cup Successors(s,FALSE)) \ baselineSeen'
  /\ UNCHANGED <<conditionalSeen,conditionalPending,work,phase,status>>
StartConditional ==
  /\ phase="baseline" /\ baselinePending={}
  /\ conditionalPending'=IF Closed /\ WorkBudget>0 /\ WithinEpochLimit THEN Initial ELSE {}
  /\ phase'=IF Closed /\ WorkBudget>0 /\ WithinEpochLimit THEN "conditional" ELSE "done"
  /\ status'=IF Closed /\ WorkBudget>0 /\ WithinEpochLimit THEN "pending" ELSE "unknown"
  /\ UNCHANGED <<baselineSeen,baselinePending,conditionalSeen,work>>
VisitConditional ==
  /\ phase="conditional" /\ conditionalPending # {} /\ work<WorkBudget
  /\ LET s == First(conditionalPending) IN
       /\ conditionalSeen'=conditionalSeen \cup {s}
       /\ conditionalPending'=(conditionalPending \cup Successors(s,TRUE)) \ conditionalSeen'
  /\ work'=work+1
  /\ UNCHANGED <<baselineSeen,baselinePending,phase,status>>
Finish ==
  /\ phase="conditional" /\ conditionalPending={}
  /\ phase'="done" /\ status'="complete"
  /\ UNCHANGED <<baselineSeen,baselinePending,conditionalSeen,conditionalPending,work>>
Stop ==
  /\ phase="conditional" /\ work=WorkBudget /\ conditionalPending # {}
  /\ phase'="done" /\ status'="unknown"
  /\ UNCHANGED <<baselineSeen,baselinePending,conditionalSeen,conditionalPending,work>>
Next == VisitBaseline \/ StartConditional \/ VisitConditional \/ Finish \/ Stop
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
\* @type: (Set($hypothesisState), Int, Int) => Set(Int);
Facts(states,a,n) == {s.residue: s \in {x \in states: x.activation=a /\ x.site=n}}
\* @type: (Int, Int) => Set(Int);
Filtered(a,n) == {s.residue: s \in {x \in conditionalSeen: x.activation=a /\ x.site=n /\ Allowed(x,TRUE)}}
\* Baseline is never relabeled after conditional propagation.
\* @type: Int => Str;
BaselineVerdict(n) ==
  IF ~Valid \/ ~Closed \/ phase="baseline" THEN "unknown"
  ELSE IF Facts(baselineSeen,1,n)={} THEN "unreached"
  ELSE IF {(r+Displacement(n))%16:r \in Facts(baselineSeen,1,n)}={0} THEN "aligned"
  ELSE IF 0 \notin {(r+Displacement(n))%16:r \in Facts(baselineSeen,1,n)} THEN "misaligned"
  ELSE "unknown"
\* @type: Int => Str;
ConditionalVerdict(n) ==
  IF status # "complete" THEN "unknown"
  ELSE IF Filtered(1,n)={} THEN "unreached"
  ELSE IF {(r+Displacement(n))%16:r \in Filtered(1,n)}={0} THEN "aligned"
  ELSE IF 0 \notin {(r+Displacement(n))%16:r \in Filtered(1,n)} THEN "misaligned"
  ELSE "unknown"
\* @type: Int => Str;
Basis(n) == IF status # "complete" THEN "unknown"
             ELSE IF Filtered(1,n)={} THEN "unreachable"
             ELSE IF ConditionalVerdict(n)#"aligned" THEN "unknown"
             ELSE IF BaselineVerdict(n)="aligned" THEN "proved"
             ELSE "assumed"
Selected == {n \in Guards: Basis(n) \in {"proved","assumed"}}
\* Record the full hypothesis context even for independent participants.
ConditionalContext == HypothesisSites
ProjectedNormalEdges == {e \in CandidateEdges:e.src \in Selected}
TypeOK ==
  /\ baselineSeen \subseteq [activation:Activations,site:Nodes,residue:Residues]
  /\ baselinePending \subseteq [activation:Activations,site:Nodes,residue:Residues]
  /\ conditionalSeen \subseteq [activation:Activations,site:Nodes,residue:Residues]
  /\ conditionalPending \subseteq [activation:Activations,site:Nodes,residue:Residues]
  /\ work \in 0..WorkBudget /\ phase \in {"baseline","conditional","done"}
  /\ status \in {"pending","complete","unknown","invalid"}
NoNewRoot ==
  (phase="done" /\ status="invalid") \/
  baselineSeen \cup baselinePending = Initial \cup UNION {Successors(s,FALSE):s \in baselineSeen}
ConditionalClosure == status="complete" =>
  /\ baselinePending={} /\ conditionalPending={}
  /\ conditionalSeen = Initial \cup UNION {Successors(s,TRUE):s \in conditionalSeen}
  /\ baselineSeen = Initial \cup UNION {Successors(s,FALSE):s \in baselineSeen}
  /\ conditionalSeen \subseteq baselineSeen
SelectionPolicy ==
  /\ (~Valid \/ ~Closed \/ ~WithinEpochLimit \/ status # "complete" => Selected={})
  /\ \A n \in Selected:
       /\ Valid /\ Closed /\ WithinEpochLimit /\ Filtered(1,n)#{}
       /\ {(r+Displacement(n))%16:r \in Filtered(1,n)}={0}
       /\ (Basis(n)="proved" => BaselineVerdict(n)="aligned")
       /\ (Basis(n)="assumed" => BaselineVerdict(n)#"aligned")
  /\ ProjectedNormalEdges \subseteq CandidateEdges
  /\ ConditionalContext=HypothesisSites
ScenarioOutcome == status="complete" =>
  /\ (Scenario="Unknown" => BaselineVerdict(2)="unknown" /\ Basis(2)="assumed")
  /\ (Scenario="Aligned" => BaselineVerdict(2)="aligned" /\ Basis(2)="proved")
  /\ (Scenario="Misaligned" => BaselineVerdict(2)="misaligned" /\ Basis(2)="unreachable" /\ 3 \notin {s.site:s \in conditionalSeen})
  /\ (Scenario \in {"Unreached","SelfSupport"} => Facts(conditionalSeen,1,2)={} /\ Basis(2)="unreachable")
  /\ (Scenario="Clobber" => Facts(conditionalSeen,1,4)=Residues /\ Basis(4)="unknown")
  /\ (Scenario="Bypass" => Facts(conditionalSeen,1,3)=Residues /\ Basis(4)="unknown")
  /\ (Scenario="Loop" => Filtered(1,2)={0} /\ Facts(conditionalSeen,1,3)={0} /\ Facts(conditionalSeen,1,4)={8})
  /\ (Scenario="SignedDisplacement" => Filtered(1,2)={8})
  /\ (Scenario="TwoHypotheses" => Filtered(1,2)={0} /\ Filtered(1,4)={8} /\ Selected={2,4})
  /\ (Scenario="RecursiveActivation" => Facts(conditionalSeen,2,2)=Residues /\ Filtered(2,2)=Residues /\
       Facts(conditionalSeen,2,3)=Residues /\ Filtered(1,2)={0})
  /\ (Scenario="NoHypotheses" => conditionalSeen=baselineSeen /\ Selected={})
BaselinePreservation ==
  /\ (phase="done" /\ Valid /\ Closed /\ Scenario="Aligned" => BaselineVerdict(2)="aligned")
  /\ (phase="done" /\ Valid /\ Closed /\ Scenario="Unknown" => BaselineVerdict(2)="unknown")
Safety == BaselinePreservation /\ TypeOK /\ NoNewRoot /\ ConditionalClosure /\ SelectionPolicy /\ ScenarioOutcome
Terminates == <> (phase="done")
=============================================================================
