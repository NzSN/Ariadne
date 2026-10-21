-------------------------- MODULE MemoryPairChecks --------------------------
EXTENDS AriadneMemoryRefinement
VARIABLE
  \* @type: $memoryFact;
  selectedFact
VARIABLE
  \* @type: $memoryTransfer;
  selectedTransfer
PairInit ==
  /\ Init
  /\ selectedFact \in Facts
  /\ selectedTransfer \in Transfers
PairNext ==
  /\ Next
  /\ UNCHANGED <<selectedFact, selectedTransfer>>
PairRepresentationSafety ==
  LET r == Inverse(selectedFact,selectedTransfer) IN
  /\ r.after = selectedFact
  /\ (r.represented => r.before = Preimage(selectedFact,selectedTransfer) /\ r.before # {} /\ ~r.conflict)
  /\ (r.conflict => ~r.represented /\ Preimage(selectedFact,selectedTransfer) = {})
  /\ (~r.represented /\ ~r.conflict => r.boundary \in
       {"constraint-expression-budget","unsupported-constraint-composition"})
  /\ (r.boundary = "information-erasure" => r.represented /\ r.before = Values)
  /\ (selectedFact.kind = "unknown" => r.boundary = "no-useful-numerical-constraint")
PairDomainSafety == selectedFact \in Facts /\ selectedTransfer \in Transfers
PairSafety == PairDomainSafety /\ PairRepresentationSafety
=============================================================================
