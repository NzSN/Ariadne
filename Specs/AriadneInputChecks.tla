----------------------- MODULE AriadneInputChecks -----------------------
EXTENDS AriadneInput
CONSTANT
  \* @type: Int;
  Budget
VARIABLES
  \* @type: Set(Int);
  pending,
  \* @type: Set(Int);
  attempted,
  \* @type: Str;
  status
Roots == {1}
Edges == {[src |-> 1, dst |-> 2, kind |-> "summary"],
          [src |-> 1, dst |-> 9, kind |-> "call"],
          [src |-> 2, dst |-> 3, kind |-> "next"],
          [src |-> 3, dst |-> 2, kind |-> "jump"]}
\* @type: Set({start: Int, data: Seq(Int), fileOffset: Int});
Captures == {[start |-> 100, data |-> <<144,72>>, fileOffset |-> 0],
             [start |-> 101, data |-> <<72,137>>, fileOffset |-> 2],
             [start |-> 102, data |-> <<0>>, fileOffset |-> 4]}
\* @type: Seq(Int);
Artifact == <<144,72,72,137,0>>
BytesOK ==
  /\ WellMapped(Artifact,Captures)
  /\ PrefixEvidence(Captures,100,<<144,72>>)
  /\ ~Readable(Captures,102)
  /\ ~Readable(Captures,103)
  /\ ~PrefixEvidence(Captures,100,<<144,72,0>>)
Init == /\ pending = Roots /\ attempted = {} /\ status = "building"
Visit(a) ==
  /\ status = "building" /\ a \in pending /\ Cardinality(attempted) < Budget
  /\ attempted' = attempted \cup {a}
  /\ pending' = (pending \cup LocalSuccessors(Edges,a)) \ attempted'
  /\ UNCHANGED status
Publish == /\ status = "building" /\ pending = {}
           /\ status' = "ready" /\ UNCHANGED <<pending,attempted>>
Exhaust == /\ status = "building" /\ pending # {} /\ Cardinality(attempted) >= Budget
          /\ status' = "limited" /\ UNCHANGED <<pending,attempted>>
Next == (\E a \in pending: Visit(a)) \/ Publish \/ Exhaust
vars == <<pending,attempted,status>>
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety ==
  /\ BytesOK
  /\ attempted \subseteq {1,2,3}
  /\ pending \cap attempted = {}
  /\ Cardinality(attempted) <= Budget
  /\ (status = "ready" => Closed(Roots,attempted,Edges) /\ pending = {})
  /\ (Budget = 2 => status # "ready")
Terminates == <> (status \in {"ready","limited"})
=============================================================================
