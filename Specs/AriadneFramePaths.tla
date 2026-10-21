------------------------- MODULE AriadneFramePaths -------------------------
EXTENDS Naturals, FiniteSets, Sequences, Apalache

\* Search contract for src/investigation/frame_paths.rs, synchronized 2026-10-11.
\* Nodes are activation-qualified IDs: equal VAs in different frames stay
\* distinct. Input binding, unwind evidence and active-call anchors are premises.
\* Typed edges distinguish parallel paths. A stack and reversed edge scans model
\* DFS over caller-supplied canonical edge order; zero budgets stay partial.
\* DeadlineAt is an admitted outer-loop work-count receipt, not wall-clock time.
\* External stops abstract graph/byte limits; their guard placement, JSON sizing,
\* hash validation and process RSS are outside this search abstraction.
\* @typeAlias: frameEdge = {src: Int, dst: Int, kind: Str};
\* @typeAlias: framePath = {nodes: Seq(Int), edges: Seq($frameEdge)};
FramePaths_typedefs == TRUE
CONSTANT
  \* @type: Set(Int);
  Nodes
CONSTANT
  \* @type: Seq($frameEdge);
  EdgeOrder
CONSTANT
  \* @type: Int;
  Start
CONSTANT
  \* @type: Int;
  Finish
CONSTANT
  \* @type: Int;
  NP
CONSTANT
  \* @type: Int;
  MaxSteps
CONSTANT
  \* @type: Int;
  MaxVisits
CONSTANT
  \* @type: Int;
  MaxWork
CONSTANT
  \* @type: Int;
  MaxScans
CONSTANT
  \* @type: Int;
  DeadlineAt
CONSTANT
  \* @type: Bool;
  GraphComplete
CONSTANT
  \* @type: Bool;
  AllowExternalStops
CONSTANT
  \* @type: Set(Int);
  Writers
\* @type: (Int, Int, Str) => $frameEdge;
Edge(a,b,kind) == [src |-> a, dst |-> b, kind |-> kind]
\* @type: ($frameEdge, Int) => Bool;
EdgeFrom(e,n) == e.src = n
\* @type: Seq($frameEdge);
DemoEdges == <<Edge(1,2,"taken"), Edge(1,2,"fallthrough"),
               Edge(1,3,"next"), Edge(2,2,"jump"),
               Edge(2,4,"next"), Edge(3,4,"next")>>
\* @type: $frameEdge => Bool;
NonLoopEdge(e) == e.src # e.dst
\* @type: Seq($frameEdge);
DemoAcyclicEdges == SelectSeq(DemoEdges, LAMBDA e: NonLoopEdge(e))
\* @type: Bool;
DemoConstants ==
  /\ Nodes = {1,2,3,4} /\ EdgeOrder = DemoEdges /\ Start = 1 /\ Finish = 4
  /\ NP = 3 /\ MaxSteps = 6 /\ MaxVisits = 2 /\ MaxWork = 20
  /\ MaxScans = 40 /\ DeadlineAt = 21
  /\ GraphComplete = TRUE /\ AllowExternalStops = FALSE /\ Writers = {1,2,3}
\* @type: Set($frameEdge);
Edges == {EdgeOrder[i] : i \in DOMAIN EdgeOrder}
\* @type: Bool;
InputContract ==
  /\ IsFiniteSet(Nodes) /\ Start \in Nodes /\ Finish \in Nodes
  /\ NP \in 1..4097
  /\ MaxSteps \in Nat /\ MaxVisits \in Nat /\ MaxWork \in Nat
  /\ MaxScans \in Nat /\ DeadlineAt \in Nat /\ IsFiniteSet(Writers)
  /\ GraphComplete \in BOOLEAN /\ AllowExternalStops \in BOOLEAN
  /\ Cardinality(Edges) = Len(EdgeOrder)
  /\ \A e \in Edges:
       /\ e.src \in Nodes /\ e.dst \in Nodes
       /\ e.kind \in {"next","taken","fallthrough","jump","indirect","summary","call"}
ASSUME InputContract
\* @type: $framePath => Int;
Last(p) == p.nodes[Len(p.nodes)]
\* @type: ($framePath, Int) => Int;
Visits(p,n) == Cardinality({i \in DOMAIN p.nodes : p.nodes[i] = n})
\* @type: $framePath => Bool;
Prefix(p) ==
  /\ Len(p.nodes) > 0 /\ p.nodes[1] = Start
  /\ Len(p.edges)+1 = Len(p.nodes)
  /\ \A n \in {p.nodes[i] : i \in DOMAIN p.nodes}: n \in Nodes
  /\ \A i \in DOMAIN p.edges:
       /\ p.edges[i] \in Edges
       /\ p.edges[i].src = p.nodes[i] /\ p.edges[i].dst = p.nodes[i+1]
\* @type: $framePath => Bool;
Valid(p) == Prefix(p) /\ Last(p) = Finish
\* @type: ($framePath, $frameEdge) => $framePath;
Extend(p,e) == [nodes |-> Append(p.nodes,e.dst), edges |-> Append(p.edges,e)]
\* @type: Int => Seq($frameEdge);
Outgoing(n) == SelectSeq(EdgeOrder, LAMBDA e: EdgeFrom(e,n))
\* @type: (Seq($frameEdge), $frameEdge) => Seq($frameEdge);
PrependEdge(s,e) == <<e>> \o s
\* @type: Seq($frameEdge) => Seq($frameEdge);
Reverse(s) == ApaFoldSeqLeft(PrependEdge,<<>>,s)
\* @type: Seq($framePath) => Seq($framePath);
DropLast(s) == SubSeq(s,1,Len(s)-1)
\* @type: $framePath;
Seed == [nodes |-> <<Start>>, edges |-> <<>>]
VARIABLE
  \* @type: Seq($framePath);
  frontier
VARIABLE
  \* @type: Seq($framePath);
  listed
VARIABLE
  \* @type: $framePath;
  active
VARIABLE
  \* @type: Seq($frameEdge);
  remaining
VARIABLE
  \* @type: Int;
  work
VARIABLE
  \* @type: Int;
  scans
VARIABLE
  \* @type: Bool;
  blocked
VARIABLE
  \* @type: Str;
  phase
VARIABLE
  \* @type: Str;
  stop
VARIABLE
  \* @type: Set(Int);
  writers
vars == <<frontier,listed,active,remaining,work,scans,blocked,phase,stop,writers>>
Init ==
  /\ frontier = IF MaxSteps = 0 \/ MaxVisits = 0 THEN <<>> ELSE <<Seed>>
  /\ listed = <<>> /\ active = Seed /\ remaining = <<>>
  /\ work = 0 /\ scans = 0 /\ writers = Writers
  /\ blocked = (MaxSteps = 0 \/ MaxVisits = 0)
  /\ phase = IF blocked THEN "done" ELSE "select"
  /\ stop = IF blocked THEN "path-or-visit-budget" ELSE ""
OuterStop ==
  /\ phase = "select"
  /\ (frontier = <<>> \/ Len(listed) = NP-1 \/ work = MaxWork \/ work >= DeadlineAt)
  /\ phase' = "done"
  /\ stop' = IF frontier = <<>>
             THEN IF blocked THEN "search-restriction" ELSE "frontier-exhausted"
             ELSE IF Len(listed) = NP-1 THEN "path-count-budget"
             ELSE IF work = MaxWork THEN "search-state-budget" ELSE "deadline-budget"
  /\ UNCHANGED <<frontier,listed,active,remaining,work,scans,blocked,writers>>
SelectPath ==
  /\ phase = "select" /\ frontier # <<>>
  /\ Len(listed) < NP-1 /\ work < MaxWork /\ work < DeadlineAt
  /\ active' = frontier[Len(frontier)] /\ frontier' = DropLast(frontier)
  /\ work' = work+1 /\ phase' = "process"
  /\ UNCHANGED <<listed,remaining,scans,blocked,stop,writers>>
ProcessPath ==
  /\ phase = "process"
  /\ IF Last(active) = Finish
     THEN /\ listed' = Append(listed,active) /\ phase' = "select"
          /\ UNCHANGED <<remaining,blocked>>
     ELSE IF Len(active.nodes) >= MaxSteps
     THEN /\ blocked' = TRUE /\ phase' = "select"
          /\ UNCHANGED <<listed,remaining>>
     ELSE /\ remaining' = Reverse(Outgoing(Last(active))) /\ phase' = "scan"
          /\ UNCHANGED <<listed,blocked>>
  /\ UNCHANGED <<frontier,active,work,scans,stop,writers>>
ScanEdge ==
  /\ phase = "scan" /\ remaining # <<>> /\ scans < MaxScans
  /\ LET e == Head(remaining) IN
       IF Visits(active,e.dst) >= MaxVisits
       THEN /\ blocked' = TRUE /\ UNCHANGED frontier
       ELSE /\ frontier' = Append(frontier,Extend(active,e)) /\ UNCHANGED blocked
  /\ remaining' = Tail(remaining) /\ scans' = scans+1
  /\ UNCHANGED <<listed,active,work,phase,stop,writers>>
FinishScan ==
  /\ phase = "scan" /\ (remaining = <<>> \/ scans = MaxScans)
  /\ blocked' = (blocked \/ remaining # <<>>)
  /\ remaining' = <<>> /\ phase' = "select"
  /\ UNCHANGED <<frontier,listed,active,work,scans,stop,writers>>
\* Loss of a popped active alternative must remain partial even with no frontier.
ExternalStop ==
  /\ AllowExternalStops /\ phase # "done"
  /\ blocked' = TRUE /\ phase' = "done" /\ stop' = "external-resource-budget"
  /\ UNCHANGED <<frontier,listed,active,remaining,work,scans,writers>>
Next == OuterStop \/ SelectPath \/ ProcessPath \/ ScanEdge \/ FinishScan \/ ExternalStop
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
EnumerationExhausted == phase = "done" /\ frontier = <<>> /\ ~blocked /\ stop = "frontier-exhausted"
CompleteWithinScope == EnumerationExhausted /\ GraphComplete
NoPathWithinScope == CompleteWithinScope /\ listed = <<>>
Truncated == blocked \/ (phase = "done" /\ frontier # <<>>)
CoverageInvariant ==
  /\ (Truncated => ~EnumerationExhausted)
  /\ (CompleteWithinScope => GraphComplete /\ phase = "done" /\ ~Truncated)
  /\ (stop # "frontier-exhausted" => ~NoPathWithinScope)
StrictCount == Len(listed) < NP
SoundPaths == \A i \in DOMAIN listed:
  /\ Valid(listed[i]) /\ Len(listed[i].nodes) <= MaxSteps
  /\ \A n \in Nodes: Visits(listed[i],n) <= MaxVisits
BoundedWork == work \in 0..MaxWork
BoundedScans == scans \in 0..MaxScans
PreserveWriters == writers = Writers
TypeOK ==
  /\ phase \in {"select","process","scan","done"}
  /\ stop \in {"", "path-or-visit-budget", "search-restriction", "frontier-exhausted",
                 "path-count-budget", "search-state-budget", "deadline-budget",
                 "external-resource-budget"}
  /\ blocked \in BOOLEAN /\ Prefix(active)
  /\ \A i \in DOMAIN frontier: Prefix(frontier[i])
  /\ \A i \in DOMAIN remaining: remaining[i] \in Edges
Safety == TypeOK /\ StrictCount /\ SoundPaths /\ BoundedWork /\ BoundedScans
          /\ PreserveWriters /\ CoverageInvariant
Terminates == <> (phase = "done")
=============================================================================
