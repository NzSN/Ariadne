---------------------- MODULE AriadneMemoryRefinement ----------------------
EXTENDS Integers, FiniteSets, Sequences
\* Finite assessment contract. Instruction relations and scoped alias witnesses
\* are admitted premises; this model does not establish instruction-step truth.
\* Synchronized with backward_values.rs and memory_refinement.rs, 2026-10-11.
\* Four-bit words and a two-operation constraint cap are representative finite
\* instances of the implementation's 1..64-bit words and 64-operation cap.
\* A missing represented predecessor is distinct from a conflicting preimage.
\* Capture/query binding, worklist traversal and serialized byte costs are outside
\* these scalar/alias decisions. Unavailable assessment never excludes a writer.
\* @typeAlias: memoryTransfer = {kind: Str, value: Int};
\* @typeAlias: memoryFact = {kind: Str, mask: Int, value: Int, operations: Seq($memoryTransfer)};
\* @typeAlias: memoryStep = {after: $memoryFact, represented: Bool, before: Set(Int), boundary: Str, conflict: Bool};
Modulus == 16
Values == 0..15
Kinds == {"copy", "add", "sub", "and", "constant"}
\* @type: (Int, Int) => Int;
Bit(n, p) == (n \div (2^p)) % 2
\* @type: (Int, Int) => Int;
And(x, m) == Bit(x,0)*Bit(m,0) + 2*Bit(x,1)*Bit(m,1)
             + 4*Bit(x,2)*Bit(m,2) + 8*Bit(x,3)*Bit(m,3)
\* @type: (Str, Int, Int) => Int;
Forward(kind, x, c) ==
  CASE kind = "copy" -> x
    [] kind = "add" -> (x+c) % Modulus
    [] kind = "sub" -> (x-c) % Modulus
    [] kind = "and" -> And(x,c)
    [] OTHER -> c
\* @type: (Str, Int, Int) => Set(Int);
Before(kind, after, c) == {x \in Values : Forward(kind,x,c) = after}
\* @type: Set(Int) => Str;
Precision(s) == IF s = {} THEN "conflict"
                ELSE IF Cardinality(s) = 1 THEN "exact"
                ELSE IF s = Values THEN "unknown" ELSE "constrained"
\* @type: (Int, Int) => Set(Int);
Range(a,n) == {(a+i) % Modulus : i \in 0..(n-1)}
\* @type: (Int, Int, Int, Int) => Bool;
Disjoint(a,n,b,m) == Range(a,n) \cap Range(b,m) = {}
\* @type: (Bool, Bool, Bool, Bool, Bool) => Bool;
Exclude(entry, footprintComplete, scopeComplete, disjoint, budgetFits) ==
  ~entry /\ footprintComplete /\ scopeComplete /\ disjoint /\ budgetFits
\* @type: (Bool, Bool, Bool) => Bool;
Stop(useful, supported, budgetFits) == ~useful \/ ~supported \/ ~budgetFits
IdealSafety ==
 /\ \A kind \in Kinds, after,c \in Values:
       LET s == Before(kind,after,c) IN
       /\ (Precision(s) = "exact" => Cardinality(s) = 1)
       /\ (Precision(s) = "constrained" => s # {} /\ s # Values)
       /\ (Precision(s) = "unknown" => s = Values)
       /\ (Precision(s) = "conflict" => s = {})
       /\ \A x \in Values: x \in s <=> Forward(kind,x,c) = after
 /\ \A a,b \in Values, n,m \in {1,2,4,8}:
       Disjoint(a,n,b,m) <=> ~\E i \in 0..(n-1), j \in 0..(m-1):
                                   (a+i) % Modulus = (b+j) % Modulus
 /\ \A entry,footprintComplete,scopeComplete,disjoint,budgetFits \in BOOLEAN:
       Exclude(entry,footprintComplete,scopeComplete,disjoint,budgetFits) =>
         ~entry /\ footprintComplete /\ scopeComplete /\ disjoint /\ budgetFits
 /\ \A useful,supported,budgetFits \in BOOLEAN:
       Stop(useful,supported,budgetFits) <=>
          ~useful \/ ~supported \/ ~budgetFits

ChainLimit == 2
\* @type: (Str, Int) => $memoryTransfer;
Transfer(kind,value) == [kind |-> kind, value |-> value]
\* @type: (Str, Int, Int, Seq($memoryTransfer)) => $memoryFact;
Fact(kind,mask,value,operations) ==
  [kind |-> kind, mask |-> mask, value |-> value, operations |-> operations]
RECURSIVE ApplyChain(_, _)
\* @type: (Int, Seq($memoryTransfer)) => Int;
ApplyChain(x,operations) ==
  IF operations = <<>> THEN x
  ELSE ApplyChain(Forward(Head(operations).kind,x,Head(operations).value), Tail(operations))
\* @type: ($memoryFact, Int) => Bool;
Permits(f,x) ==
  CASE f.kind = "unknown" -> TRUE
    [] f.kind = "exact" -> x = f.value
    [] OTHER -> And(ApplyChain(x,f.operations),f.mask) = f.value
\* @type: $memoryFact => Set(Int);
Meaning(f) == {x \in Values: Permits(f,x)}
\* @type: ($memoryFact, $memoryTransfer) => Set(Int);
Preimage(f,t) == {x \in Values: Permits(f,Forward(t.kind,x,t.value))}
\* @type: ($memoryFact, Bool, Set(Int), Str, Bool) => $memoryStep;
Step(f,represented,before,boundary,conflict) ==
  [after |-> f, represented |-> represented, before |-> before,
   boundary |-> boundary, conflict |-> conflict]
\* @type: ($memoryFact, $memoryTransfer) => $memoryStep;
Inverse(f,t) ==
  LET predecessors == Preimage(f,t) IN
  CASE f.kind = "unknown" -> Step(f,TRUE,Values,"no-useful-numerical-constraint",FALSE)
    [] t.kind = "copy" -> Step(f,TRUE,Meaning(f),"",FALSE)
    [] t.kind = "constant" ->
         IF predecessors = {} THEN Step(f,FALSE,{},"inconsistent-predecessor-constraints",TRUE)
         ELSE Step(f,TRUE,Values,"information-erasure",FALSE)
    [] t.kind \in {"add","sub"} ->
         IF f.kind = "constrained" /\ Len(f.operations) = ChainLimit
         THEN Step(f,FALSE,{},"constraint-expression-budget",FALSE)
         ELSE Step(f,TRUE,predecessors,"",FALSE)
    [] OTHER ->
         IF t.value = Modulus-1 THEN Step(f,TRUE,Meaning(f),"",FALSE)
         ELSE IF f.kind = "constrained" /\ f.operations # <<>>
         THEN Step(f,FALSE,{},"unsupported-constraint-composition",FALSE)
         ELSE IF predecessors = {} THEN Step(f,FALSE,{},"inconsistent-predecessor-constraints",TRUE)
         ELSE IF predecessors = Values THEN Step(f,TRUE,Values,"information-erasure",FALSE)
         ELSE Step(f,TRUE,predecessors,"",FALSE)
ExactFacts == {Fact("exact",15,v,<<>>) : v \in Values}
PlainConstraints ==
  {f \in {Fact("constrained",m,v,<<>>) : m \in 1..14, v \in Values}:
    And(f.value,f.mask) = f.value}
\* Directed bijective chains exercise retained constraints and the cap boundary.
\* @type: Set(Seq($memoryTransfer));
Chains == {<<Transfer("add",1)>>, <<Transfer("sub",15)>>,
           <<Transfer("add",1),Transfer("sub",15)>>}
ComposedConstraints ==
  {f \in {Fact("constrained",m,v,ops) : m \in {1,3,7}, v \in Values, ops \in Chains}:
    And(f.value,f.mask) = f.value}
Facts == ExactFacts \cup PlainConstraints \cup ComposedConstraints
         \cup {Fact("unknown",0,0,<<>>)}
Transfers == {Transfer(kind,v) : kind \in Kinds, v \in Values}
RepresentationSafety == \A f \in Facts, t \in Transfers:
  LET r == Inverse(f,t) IN
  /\ r.after = f
  /\ (r.represented => r.before = Preimage(f,t) /\ r.before # {} /\ ~r.conflict)
  /\ (r.conflict => ~r.represented /\ Preimage(f,t) = {})
  /\ (~r.represented /\ ~r.conflict => r.boundary \in
       {"constraint-expression-budget","unsupported-constraint-composition"})
  /\ (r.boundary = "information-erasure" => r.represented /\ r.before = Values)
  /\ (f.kind = "unknown" => r.boundary = "no-useful-numerical-constraint")
\* Preserve every original candidate when admission succeeds. Budget or evidence
\* failure may make the assessment unavailable; that yields no exclusion claim.
Candidates == {"entry","proved","unknown","budget-limited"}
\* This is the original bound universe, not a claim that an unavailable wire
\* report publishes candidate rows. Unavailable rows below express no exclusion.
\* @type: (Str, Bool) => Str;
CandidateDecision(c,available) ==
  IF ~available THEN "unavailable"
  ELSE IF Exclude(c = "entry", c # "unknown", c # "unknown", c # "unknown", c # "budget-limited")
       THEN "excluded_under_premises" ELSE "retained"
\* @type: Bool => (Str -> Str);
CandidateResults(available) == [c \in Candidates |-> CandidateDecision(c,available)]
CandidateSafety == \A available \in BOOLEAN:
  /\ DOMAIN CandidateResults(available) = Candidates
  /\ (available => CandidateResults(available)["entry"] = "retained")
  /\ (~available => \A c \in Candidates: CandidateResults(available)[c] = "unavailable")
  /\ CandidateResults(available)["unknown"] # "excluded_under_premises"
  /\ CandidateResults(available)["budget-limited"] # "excluded_under_premises"
Safety == IdealSafety /\ RepresentationSafety /\ CandidateSafety
VARIABLE
  \* @type: Int;
  checked
Init == checked = 0
Next == /\ checked = 0 /\ checked' = 1
Spec == Init /\ [][Next]_checked
=============================================================================
