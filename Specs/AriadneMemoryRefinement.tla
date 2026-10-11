---------------------- MODULE AriadneMemoryRefinement ----------------------
EXTENDS Integers, FiniteSets
\* Finite assessment contract. Instruction relations and scoped alias witnesses
\* are admitted premises; this model does not establish instruction-step truth.
Modulus == 16
Values == 0..15
Kinds == {"copy", "add", "sub", "and", "constant"}
Bit(n, p) == (n \div (2^p)) % 2
And(x, m) == Bit(x,0)*Bit(m,0) + 2*Bit(x,1)*Bit(m,1)
             + 4*Bit(x,2)*Bit(m,2) + 8*Bit(x,3)*Bit(m,3)
Forward(kind, x, c) ==
  CASE kind = "copy" -> x
    [] kind = "add" -> (x+c) % Modulus
    [] kind = "sub" -> (x-c) % Modulus
    [] kind = "and" -> And(x,c)
    [] OTHER -> c
Before(kind, after, c) == {x \in Values : Forward(kind,x,c) = after}
Precision(s) == IF s = {} THEN "conflict"
                ELSE IF Cardinality(s) = 1 THEN "exact"
                ELSE IF s = Values THEN "unknown" ELSE "constrained"
Range(a,n) == {(a+i) % Modulus : i \in 0..(n-1)}
Disjoint(a,n,b,m) == Range(a,n) \cap Range(b,m) = {}
Exclude(entry, footprintComplete, scopeComplete, disjoint, budgetFits) ==
  ~entry /\ footprintComplete /\ scopeComplete /\ disjoint /\ budgetFits
Stop(useful, supported, budgetFits) == ~useful \/ ~supported \/ ~budgetFits
Safety ==
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
VARIABLE
  \* @type: Int;
  checked
Init == checked = 0
Next == /\ checked = 0 /\ checked' = 1
Spec == Init /\ [][Next]_checked
=============================================================================
