---------------------- MODULE FiniteLookupEquality ----------------------
EXTENDS AriadneMemoryRefinementLookup
Authority == INSTANCE AriadneMemoryRefinementAlgebra WITH checked <- checked

PointwiseEquality ==
  /\ Modulus = Authority!Modulus
  /\ Values = Authority!Values
  /\ Kinds = Authority!Kinds
  /\ ChainLimit = Authority!ChainLimit
  /\ \A x,c \in Values:
       /\ And(x,c) = Authority!And(x,c)
       /\ \A kind \in Kinds:
            /\ Forward(kind,x,c) = Authority!Forward(kind,x,c)
            /\ Forward(kind,x,c) \in Values

DomainEquality ==
  /\ PointwiseEquality
  /\ ExactFacts = Authority!ExactFacts
  /\ PlainConstraints = Authority!PlainConstraints
  /\ ComposedConstraints = Authority!ComposedConstraints
  /\ Facts = Authority!Facts
  /\ Transfers = Authority!Transfers
  /\ Cardinality(ExactFacts) = 16
  /\ Cardinality(PlainConstraints) = 64
  /\ Cardinality(ComposedConstraints) = 42
  /\ Cardinality(Facts) = 123
  /\ Cardinality(Transfers) = 80

\* No unadmitted argument is hidden in a table lookup. In particular, the
\* direct And calls in fact construction and Permits have carrier arguments,
\* and every prefix of each admitted operation chain stays in the carrier.
CallClosure ==
  /\ \A f \in Facts:
       /\ f.mask \in Values /\ f.value \in Values
       /\ Len(f.operations) <= ChainLimit
       /\ \A i \in 1..Len(f.operations):
            /\ f.operations[i].kind \in Kinds
            /\ f.operations[i].value \in Values
       /\ \A x \in Values, i \in 0..Len(f.operations):
            ApplyChain(x,SubSeq(f.operations,1,i)) \in Values

ExtensionalEquality ==
  /\ \A kind \in Kinds, after,c \in Values:
       Before(kind,after,c) = Authority!Before(kind,after,c)
  /\ \A f \in Facts, x \in Values:
       /\ ApplyChain(x,f.operations) = Authority!ApplyChain(x,f.operations)
       /\ Permits(f,x) = Authority!Permits(f,x)
  /\ \A f \in Facts: Meaning(f) = Authority!Meaning(f)
  /\ \A f \in Facts, t \in Transfers:
       /\ Preimage(f,t) = Authority!Preimage(f,t)
       /\ Inverse(f,t) = Authority!Inverse(f,t)

\* @type: ($memoryFact, $memoryStep, Set(Int)) => Seq(Bool);
SixClauses(f,r,predecessors) ==
  <<r.after = f,
    (r.represented => r.before = predecessors /\ r.before # {} /\ ~r.conflict),
    (r.conflict => ~r.represented /\ predecessors = {}),
    (~r.represented /\ ~r.conflict => r.boundary \in
       {"constraint-expression-budget","unsupported-constraint-composition"}),
    (r.boundary = "information-erasure" => r.represented /\ r.before = Values),
    (f.kind = "unknown" => r.boundary = "no-useful-numerical-constraint")>>

SixClauseEquality == \A f \in Facts, t \in Transfers:
  SixClauses(f,Inverse(f,t),Preimage(f,t)) =
    SixClauses(f,Authority!Inverse(f,t),Authority!Preimage(f,t))

WholeEquality ==
  /\ DomainEquality
  /\ CallClosure
  /\ ExtensionalEquality
  /\ SixClauseEquality
  /\ IdealSafety = Authority!IdealSafety
  /\ RepresentationSafety = Authority!RepresentationSafety
  /\ CandidateSafety = Authority!CandidateSafety
  /\ Safety = Authority!Safety
  \* Equality of two false predicates is not theorem acceptance.
  /\ Authority!Safety
  /\ Safety
=============================================================================
