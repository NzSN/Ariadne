------------------------- MODULE AriadneFramePaths -------------------------
EXTENDS Naturals, FiniteSets, Sequences, TLC
CONSTANTS Nodes, Edges, Start, Finish, NP, MaxSteps, MaxVisits, MaxWork, Writers
DemoEdges == {<<1,2>>,<<1,3>>,<<2,4>>,<<3,4>>,<<2,2>>}
ASSUME /\ Start \in Nodes /\ Finish \in Nodes /\ NP > 0
       /\ Edges \subseteq Nodes \X Nodes
VARIABLES frontier, listed, work, truncated, done, writers
vars == <<frontier, listed, work, truncated, done, writers>>
Visits(p,n) == Cardinality({i \in 1..Len(p): p[i] = n})
Valid(p) == /\ Len(p) > 0 /\ p[1] = Start /\ p[Len(p)] = Finish
            /\ \A i \in 1..(Len(p)-1): <<p[i],p[i+1]>> \in Edges
Init == /\ frontier = {<<Start>>} /\ listed = {} /\ work = 0
        /\ truncated = FALSE /\ done = FALSE /\ writers = Writers
Stop == /\ ~done
        /\ (frontier = {} \/ Cardinality(listed) = NP-1 \/ work = MaxWork)
        /\ done' = TRUE
        /\ truncated' = truncated \/ frontier # {}
        /\ UNCHANGED <<frontier, listed, work, writers>>
Expand == /\ ~done /\ frontier # {} /\ Cardinality(listed) < NP-1 /\ work < MaxWork
          /\ \E p \in frontier:
              LET successors == {n \in Nodes: <<p[Len(p)],n>> \in Edges}
                  admitted == {n \in successors: Len(p) < MaxSteps /\ Visits(p,n) < MaxVisits}
              IN /\ work' = work+1
                 /\ IF p[Len(p)] = Finish
                       THEN /\ listed' = listed \cup {p}
                            /\ frontier' = frontier \ {p}
                            /\ truncated' = truncated
                       ELSE /\ listed' = listed
                            /\ frontier' = (frontier \ {p}) \cup {Append(p,n): n \in admitted}
                            /\ truncated' = truncated \/ successors # admitted
          /\ UNCHANGED <<done, writers>>
Next == Stop \/ Expand
Spec == Init /\ [][Next]_vars
StrictCount == Cardinality(listed) < NP
SoundPaths == \A p \in listed: Valid(p)
BoundedWork == work <= MaxWork
PreserveWriters == writers = Writers
=============================================================================
