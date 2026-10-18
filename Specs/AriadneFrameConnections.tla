--------------------- MODULE AriadneFrameConnections ---------------------
EXTENDS Naturals, FiniteSets, Sequences

\* Stage 5.2 finite graph contract. Node IDs are activation-qualified; source
\* admission, captured bytes, active-call matching and hashing are premises.
\* Closure rounds abstract the implementation's bounded traversals/SCC work.
\* Exactness is relative to Edges, never to unknown continuations. BFS models
\* a first shortest loop-free example. Further detours must satisfy ValidPath,
\* strict NP and writer/premise preservation; they are not an enumeration.
\* Samples abstract bounded detours by selecting valid node paths; typed edge
\* identities remain in Edges and are tested by the independent Rust oracle.
\* Parallel sample IDs and concrete independent-layer scheduling are erased.
\* Concrete allocation sizes, clocks, codecs and Rust refinement are separate.
\* @typeAlias: connectionEdge = {src: Int, dst: Int, kind: Str};
Connection_typedefs == TRUE
CONSTANTS
  \* @type: Str;
  Scenario,
  \* @type: Int;
  NP,
  \* @type: Int;
  MaxWork,
  \* @type: Int;
  MaxSearch
Nodes == {1,2,3,4}
Start == 1
Finish == IF Scenario = "Equal" THEN 1 ELSE 4
\* @type: (Int, Int, Str) => $connectionEdge;
Edge(a,b,k) == [src |-> a, dst |-> b, kind |-> k]
\* @type: Seq($connectionEdge);
EdgeOrder ==
  IF Scenario = "Disconnected" THEN <<Edge(1,2,"next"),Edge(3,4,"next")>>
  ELSE IF Scenario = "Cycle" THEN
    <<Edge(1,2,"next"),Edge(2,3,"next"),Edge(3,2,"jump"),Edge(3,4,"next")>>
  ELSE IF Scenario = "Self" THEN
    <<Edge(1,1,"jump"),Edge(1,2,"next"),Edge(2,4,"next")>>
  ELSE IF Scenario = "Parallel" THEN
    <<Edge(1,2,"taken"),Edge(1,2,"fallthrough"),Edge(2,4,"next")>>
  ELSE IF Scenario = "UnknownReconnect" THEN
    <<Edge(1,2,"taken"),Edge(1,3,"fallthrough"),Edge(2,4,"next")>>
  ELSE <<Edge(1,2,"taken"),Edge(1,3,"fallthrough"),Edge(2,4,"next"),Edge(3,4,"next")>>
Edges == {EdgeOrder[i] : i \in DOMAIN EdgeOrder}
Frontiers == IF Scenario = "UnknownReconnect" THEN {3} ELSE {}
Hypotheses == IF Scenario = "Conditional" THEN {7} ELSE {}
AnchorsAvailable == Scenario # "MissingAnchors"
Writers == Nodes
ASSUME /\ Scenario \in {"Diamond","Cycle","Self","Parallel","Disconnected",
                         "UnknownReconnect","Equal","Conditional","MissingAnchors"}
       /\ NP \in 1..10 /\ MaxWork \in Nat /\ MaxSearch \in Nat
\* @type: (Set(<<Int, Int>>), Int, Int) => Bool;
Has(r,a,b) == <<a,b>> \in r
\* TLC accepts the bounded existential formulation without enumerating paths.
\* @type: Set(<<Int, Int>>) => Set(<<Int, Int>>);
ClosureStep(r) == r \cup {p \in Nodes \X Nodes :
    \E b \in Nodes: Has(r,p[1],b) /\ Has(r,b,p[2])}
\* @type: Set(<<Int, Int>>);
InitialRelation == {<<n,n>> : n \in Nodes} \cup {<<e.src,e.dst>> : e \in Edges}
\* @type: Seq(Int) => Bool;
ValidPath(p) == /\ Len(p)>0 /\ p[1]=Start /\ p[Len(p)]=Finish
                /\ Cardinality({p[i]:i \in DOMAIN p})=Len(p)
                /\ \A i \in 1..(Len(p)-1):
                     \E e \in Edges:e.src=p[i] /\ e.dst=p[i+1]
\* @type: Set(Seq(Int));
Paths1 == {<<a>> : a \in Nodes}
\* @type: Set(Seq(Int));
Paths2 == {<<a,b>> : a,b \in Nodes}
\* @type: Set(Seq(Int));
Paths3 == {<<a,b,c>> : a,b,c \in Nodes}
\* @type: Set(Seq(Int));
Paths4 == {<<a,b,c,d>> : a,b,c,d \in Nodes}
PathUniverse == Paths1 \cup Paths2 \cup Paths3 \cup Paths4
AllSimplePaths == {p \in Paths1 \cup Paths2 \cup Paths3 \cup Paths4 : ValidPath(p)}
\* @type: (Int, Int) => Bool;
HasPath(a,b) == \E p \in PathUniverse:
  /\ p[1]=a /\ p[Len(p)]=b
  /\ \A i \in 1..(Len(p)-1): \E e \in Edges: e.src=p[i] /\ e.dst=p[i+1]
ExactRelation == {p \in Nodes \X Nodes: HasPath(p[1],p[2])}
\* @type: Seq(Seq(Int)) => Seq(Int);
First(q) == q[1]
VARIABLE
  \* @type: Set(<<Int, Int>>);
  relation
VARIABLE
  \* @type: Int;
  work
VARIABLE
  \* @type: Str;
  phase
VARIABLE
  \* @type: Seq(Seq(Int));
  queue
VARIABLE
  \* @type: Seq(Int);
  example
VARIABLE
  \* @type: Set(Seq(Int));
  samples
VARIABLE
  \* @type: Int;
  searches
VARIABLE
  \* @type: Set(Int);
  writers
VARIABLE
  \* @type: Set(Int);
  frontiers
VARIABLE
  \* @type: Set(Int);
  hypotheses
vars == <<relation,work,phase,queue,example,samples,searches,writers,frontiers,hypotheses>>
Init == /\ relation=InitialRelation /\ work=0 /\ phase="closure"
        /\ queue= << <<Start>> >> /\ example= <<>> /\ samples={} /\ searches=0
        /\ writers=Writers /\ frontiers=Frontiers /\ hypotheses=Hypotheses
AdvanceClosure ==
  /\ phase="closure" /\ work<MaxWork
  /\ IF ClosureStep(relation)=relation
     THEN phase'="search"
     ELSE /\ relation'=ClosureStep(relation) /\ phase'="closure"
  /\ IF phase'="search" THEN UNCHANGED relation ELSE TRUE
  /\ work'=work+1
  /\ UNCHANGED <<queue,example,samples,searches,writers,frontiers,hypotheses>>
StopClosure == /\ phase="closure" /\ work=MaxWork /\ phase'="stopped"
               /\ UNCHANGED <<relation,work,queue,example,samples,searches,writers,frontiers,hypotheses>>
\* @type: (Seq(Int), $connectionEdge) => Bool;
CanExtend(p,e) == e.src=p[Len(p)] /\ e.dst \notin {p[i]:i \in DOMAIN p}
RECURSIVE ExtensionsUpTo(_,_)
\* @type: (Seq(Int), Int) => Seq(Seq(Int));
ExtensionsUpTo(p,i) == IF i=0 THEN <<>>
  ELSE IF CanExtend(p,EdgeOrder[i])
       THEN Append(ExtensionsUpTo(p,i-1),Append(p,EdgeOrder[i].dst))
       ELSE ExtensionsUpTo(p,i-1)
\* @type: Seq(Int) => Seq(Seq(Int));
Extensions(p) == ExtensionsUpTo(p,Len(EdgeOrder))

Search ==
  /\ phase="search"
  /\ IF NP=1 \/ queue= <<>> \/ ~AnchorsAvailable THEN /\ phase'="done"
                                      /\ UNCHANGED <<queue,example,samples,searches>>
     ELSE IF searches=MaxSearch THEN /\ phase'="search_stopped"
                                      /\ UNCHANGED <<queue,example,samples,searches>>
     ELSE LET p == First(queue) IN
       /\ searches'=searches+1
       /\ IF p[Len(p)]=Finish
          THEN /\ example'=p /\ samples'={p} /\ phase'="sampling" /\ queue'=Tail(queue)
          ELSE /\ queue'=Tail(queue) \o Extensions(p) /\ phase'="search"
               /\ UNCHANGED <<example,samples>>
  /\ UNCHANGED <<relation,work,writers,frontiers,hypotheses>>
Sample ==
  /\ phase="sampling"
  /\ IF Cardinality(samples)=NP-1 \/ AllSimplePaths \ samples={}
     THEN /\ phase'="done" /\ UNCHANGED <<samples,searches>>
     ELSE IF searches=MaxSearch
          THEN /\ phase'="search_stopped" /\ UNCHANGED <<samples,searches>>
          ELSE /\ \E p \in AllSimplePaths \ samples: samples'=samples \cup {p}
               /\ searches'=searches+1 /\ phase'="sampling"
  /\ UNCHANGED <<relation,work,queue,example,writers,frontiers,hypotheses>>
Next == AdvanceClosure \/ StopClosure \/ Search \/ Sample
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Complete == phase \in {"search","sampling","done","search_stopped"}
Forward == {n \in Nodes:Has(relation,Start,n)}
Backward == {n \in Nodes:Has(relation,n,Finish)}
Corridor == Forward \cap Backward
\* @type: Int => Set(Int);
Component(n) == {m \in Nodes:Has(relation,n,m) /\ Has(relation,m,n)}
Partition == {Component(n):n \in Nodes}
RepresentedAbsent == Complete /\ AnchorsAvailable /\ Finish \notin Forward
Safety ==
  /\ relation \subseteq Nodes \X Nodes /\ InitialRelation \subseteq relation
  /\ work<=MaxWork /\ searches<=MaxSearch
  /\ writers=Writers /\ frontiers=Frontiers /\ hypotheses=Hypotheses
  /\ Cardinality(samples)<NP /\ \A p \in samples:ValidPath(p)
  /\ (~AnchorsAvailable => samples={} /\ example= <<>>)
  /\ (Complete => ClosureStep(relation)=relation /\ relation=ExactRelation)
  /\ (RepresentedAbsent => ~Has(relation,Start,Finish))
  /\ (example # <<>> => ValidPath(example) /\ NP>1 /\ Complete
      /\ \A p \in AllSimplePaths: Len(example)<=Len(p))
  /\ (Complete => \A a,b \in Partition: a=b \/ a \cap b={})
  /\ (Complete => UNION Partition=Nodes)
  /\ (Complete => \A a,b \in Nodes: Component(a)#Component(b) /\ Has(relation,a,b) => ~Has(relation,b,a))
  /\ (Scenario="UnknownReconnect" => 3 \in frontiers)
Terminates == <> (phase \in {"done","stopped","search_stopped"})
=============================================================================
