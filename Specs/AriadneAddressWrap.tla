------------------------- MODULE AriadneAddressWrap -------------------------
EXTENDS Integers, FiniteSets, Sequences, AriadneAddressWrapCases

\* Draft W0 question-level contract. No ISA, decoder, unwind or history proof.
\* Every address has FOUR 16-bit limbs, least-significant first: exactly 64 bits.
\* The signed displacement is TWO 16-bit limbs, sign-extended to 64 bits.
\* The exact wide integer T is represented losslessly by (quotient,effective):
\*   T = quotient * 2^64 + Sum_i(effective[i] * 2^(16*(i-1))).
\* This representation keeps every concrete boundary without giant scalar
\* literals or reducing the architectural width to a toy modulus.
\* Hashes, raw byte parsing and trusted BAP/decoded admission are source premises.
\* Conditional arithmetic and final fault admission remain separate.
\* ordinaryAV, contextSupported and receiptMatches abstract previously checked
\* admission facts: this model does not prove parsing, context validity or ISA
\* semantics. Admitted number_parameters is 0..15; >15 is a binding error.
\* Qualification is Apalache typechecking plus finite TLC safety/liveness.
\* The recursive sequence constructor earns no Apalache bounded-SMT claim.

CONSTANT
  \* @type: Set(Int);
  CaseIds
ASSUME CaseIds # {} /\ CaseIds \subseteq 1..Len(CaseTable)

\* @type: Int;
Radix == 65536
\* @type: Seq(Int);
Zero == <<0,0,0,0>>
\* @type: Seq(Int);
Cutoff == <<0,0,32768,0>>

\* @type: (Int, Int) => Int;
Min(a,b) == IF a < b THEN a ELSE b
RECURSIVE Repeat(_, _)
\* @type: (Int, Str) => Seq(Str);
Repeat(n,tag) == IF n=0 THEN <<>> ELSE Append(Repeat(n-1,tag),tag)
\* All modeled evidence lengths use0..42. Include64 as an uncapped control.
\* @type: Bool;
RepeatContract == \A n \in ((0..42) \cup {64}), tag \in {"field","control"}:
  Len(Repeat(n,tag))=n /\ \A i \in 1..n: Repeat(n,tag)[i]=tag
\* @type: Seq(Int) => Bool;
Word64(a) == Len(a)=4 /\ \A i \in 1..4: a[i] \in 0..65535
\* @type: (Seq(Int), Seq(Int)) => Bool;
Less(a,b) == a[4] < b[4]
  \/ (a[4]=b[4] /\ a[3]<b[3])
  \/ (a[4]=b[4] /\ a[3]=b[3] /\ a[2]<b[2])
  \/ (a[4]=b[4] /\ a[3]=b[3] /\ a[2]=b[2] /\ a[1]<b[1])
\* @type: (Seq(Int), Seq(Int)) => Bool;
AtMost(a,b) == a=b \/ Less(a,b)
\* @type: (Seq(Int), Seq(Int)) => {digits: Seq(Int), carry: Int};
Add64(a,b) ==
  LET s1 == a[1]+b[1]
      s2 == a[2]+b[2]+(s1 \div Radix)
      s3 == a[3]+b[3]+(s2 \div Radix)
      s4 == a[4]+b[4]+(s3 \div Radix)
  IN [digits |-> <<s1 % Radix,s2 % Radix,s3 % Radix,s4 % Radix>>,
      carry |-> s4 \div Radix]
\* @type: $wrapCase => Bool;
Negative(c) == c.displacement[2] >= 32768
\* @type: $wrapCase => Seq(Int);
Displacement64(c) == <<c.displacement[1],c.displacement[2],
                       IF Negative(c) THEN 65535 ELSE 0,
                       IF Negative(c) THEN 65535 ELSE 0>>
\* @type: $wrapCase => Seq(Int);
Effective(c) == Add64(c.base,Displacement64(c)).digits
\* @type: $wrapCase => Int;
Quotient(c) == Add64(c.base,Displacement64(c)).carry - (IF Negative(c) THEN 1 ELSE 0)
\* @type: $wrapCase => {digits: Seq(Int), carry: Int};
AccessEnd(c) == Add64(Effective(c),<<c.accessBytes,0,0,0>>)
\* @type: $wrapCase => Bool;
RangeAdmitted(c) == AccessEnd(c).carry=0 /\ AtMost(AccessEnd(c).digits,Cutoff)
\* @type: $wrapCase => Bool;
ReportedByteAdmitted(c) == AccessEnd(c).carry=0
  /\ AtMost(Effective(c),c.reported) /\ Less(c.reported,AccessEnd(c).digits)

\* @type: $wrapCase => Bool;
Control(c) == c.contextFlags % 2 = 1
\* @type: $wrapCase => Bool;
Integer(c) == (c.contextFlags \div 2) % 2 = 1
\* @type: $wrapCase => Bool;
FormAdmitted(c) ==
  (c.form \in {"MOV32mi","MOV32mr"} /\ c.accessBytes=4 /\ c.operation=1)
  \/ (c.form="MOV32rm" /\ c.accessBytes=4 /\ c.operation=0)
  \/ (c.form \in {"MOV64mi32","MOV64mr"} /\ c.accessBytes=8 /\ c.operation=1)
  \/ (c.form="MOV64rm" /\ c.accessBytes=8 /\ c.operation=0)
\* @type: $wrapCase => Bool;
ArithmeticInputReady(c) ==
  /\ c.windows /\ c.exception /\ c.context /\ c.contextSupported
  /\ c.ordinaryAV /\ c.siteMatches /\ Control(c) /\ c.parameters >= 2
  /\ c.captured /\ c.reached /\ c.semantics /\ c.prefix /\ c.oneAccess
  /\ FormAdmitted(c)
  /\ c.receipt /\ c.receiptMatches /\ c.baseOnly
  /\ (IF c.baseGroup=1 THEN Control(c) ELSE Integer(c))
  /\ c.bapAddress = Effective(c)

\* Full source bundle: instruction, record, optional context, fields, receipt.
\* Raw identities and field names are erased; atom ordering/count is preserved.
\* @type: $wrapCase => Int;
Registers(c) == IF c.contextSupported
  THEN (IF Control(c) THEN 3 ELSE 0)+(IF Integer(c) THEN 15 ELSE 0) ELSE 0
\* @type: $wrapCase => Seq(Str);
Evidence(c) == <<"instruction">>
  \o (IF c.exception THEN <<"record">>
      \o (IF c.context THEN <<"context">> ELSE <<>>)
      \o Repeat(8+c.parameters+(IF c.context THEN 1+Registers(c) ELSE 0),"field")
      ELSE <<>>)
  \o (IF c.receipt THEN <<"receipt">> ELSE <<>>)
\* @type: $wrapCase => Seq(Str);
KeptEvidence(c) == SubSeq(Evidence(c),1,Min(Len(Evidence(c)),c.evidenceLimit))
\* @type: $wrapCase => Bool;
EvidenceFits(c) == Len(Evidence(c)) <= c.evidenceLimit
\* @type: $wrapCase => Int;
ObservedClaims(c) == Cardinality({i \in 1..Len(KeptEvidence(c)):
  KeptEvidence(c)[i]="field" \/ (KeptEvidence(c)[i]="instruction" /\ c.captured)})
\* @type: $wrapCase => Int;
NeededClaims(c) == ObservedClaims(c)
  +(IF ArithmeticInputReady(c) /\ EvidenceFits(c) THEN 5 ELSE 0)+1
\* @type: $wrapCase => Bool;
ClaimsFit(c) == NeededClaims(c) <= c.claimLimit
\* @type: $wrapCase => Bool;
KeepArithmetic(c) == ArithmeticInputReady(c) /\ EvidenceFits(c) /\ ClaimsFit(c)
\* @type: $wrapCase => Bool;
FaultReady(c) == KeepArithmetic(c) /\ RangeAdmitted(c) /\ ReportedByteAdmitted(c)
\* @type: $wrapCase => Str;
Outcome(c) == IF ~FaultReady(c) THEN "unknown"
  ELSE IF Quotient(c)=0 THEN "refuted_under_premises" ELSE "consistent_with_evidence"
\* @type: $wrapCase => Int;
ClaimCount(c) == IF ClaimsFit(c) THEN NeededClaims(c)
  ELSE Min(ObservedClaims(c),c.claimLimit)+(IF c.claimLimit>ObservedClaims(c) THEN 1 ELSE 0)

VARIABLE
  \* @type: $wrapCase;
  current
VARIABLE
  \* @type: Str;
  phase
VARIABLE
  \* @type: Bool;
  arithmeticReady
VARIABLE
  \* @type: Bool;
  factsRetained
VARIABLE
  \* @type: Int;
  quotient
VARIABLE
  \* @type: Seq(Int);
  effective
VARIABLE
  \* @type: Str;
  conclusion
VARIABLE
  \* @type: Bool;
  truncated
VARIABLE
  \* @type: Int;
  evidenceCount
VARIABLE
  \* @type: Int;
  claimCount
vars == <<current,phase,arithmeticReady,factsRetained,quotient,effective,conclusion,
          truncated,evidenceCount,claimCount>>
Init ==
  /\ \E i \in CaseIds: current=CaseTable[i]
  /\ phase="validate" /\ arithmeticReady=FALSE /\ factsRetained=FALSE
  /\ quotient=0 /\ effective=Zero /\ conclusion="unknown"
  /\ truncated=FALSE /\ evidenceCount=0 /\ claimCount=0
Validate ==
  /\ phase="validate"
  /\ phase'=IF current.bindingValid THEN "arithmetic" ELSE "error"
  /\ UNCHANGED <<current,arithmeticReady,factsRetained,quotient,effective,conclusion,
                 truncated,evidenceCount,claimCount>>
Calculate ==
  /\ phase="arithmetic" /\ phase'="publish"
  /\ arithmeticReady'=ArithmeticInputReady(current)
  /\ quotient'=IF ArithmeticInputReady(current) THEN Quotient(current) ELSE 0
  /\ effective'=IF ArithmeticInputReady(current) THEN Effective(current) ELSE Zero
  /\ UNCHANGED <<current,factsRetained,conclusion,truncated,evidenceCount,claimCount>>
Publish ==
  /\ phase="publish" /\ phase'="done"
  /\ factsRetained'=KeepArithmetic(current)
  /\ quotient'=IF KeepArithmetic(current) THEN Quotient(current) ELSE 0
  /\ effective'=IF KeepArithmetic(current) THEN Effective(current) ELSE Zero
  /\ conclusion'=Outcome(current)
  /\ truncated' = (~EvidenceFits(current) \/ ~ClaimsFit(current))
  /\ evidenceCount'=Len(KeptEvidence(current))
  /\ claimCount'=ClaimCount(current)
  /\ UNCHANGED <<current,arithmeticReady>>
Next == Validate \/ Calculate \/ Publish
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

TypeOK ==
  /\ current.id \in 1..Len(CaseTable)
  /\ (current.bindingValid => current.parameters \in 0..15)
  /\ Word64(current.base) /\ Word64(current.bapAddress) /\ Word64(current.reported)
  /\ Word64(current.payload)
  /\ Len(current.displacement)=2 /\ \A i \in 1..2: current.displacement[i] \in 0..65535
  /\ phase \in {"validate","arithmetic","publish","done","error"}
  /\ quotient \in {-1,0,1} /\ Word64(effective)
  /\ conclusion \in {"unknown","consistent_with_evidence","refuted_under_premises"}
  /\ evidenceCount >= 0 /\ claimCount >= 0
Reduction == factsRetained =>
  /\ quotient=Quotient(current) /\ effective=Effective(current)
  /\ (quotient=1 => ~Negative(current))
  /\ (quotient=-1 => Negative(current))
  /\ (quotient=0 <=> Add64(current.base,Displacement64(current)).carry=
                          (IF Negative(current) THEN 1 ELSE 0))
DefiniteRequiresAll == phase="done" /\ conclusion#"unknown" => FaultReady(current)
CorrectConclusions == phase="done" =>
  /\ (conclusion="consistent_with_evidence" => quotient=1)
  /\ (conclusion="refuted_under_premises" => quotient=0 /\ factsRetained)
  /\ (Quotient(current)=-1 => conclusion="unknown")
BudgetConservative == phase="done" =>
  /\ evidenceCount <= current.evidenceLimit /\ claimCount <= current.claimLimit
  /\ (~EvidenceFits(current) \/ ~ClaimsFit(current) =>
        conclusion="unknown" /\ truncated /\ ~factsRetained)
  /\ (factsRetained => claimCount=ObservedClaims(current)+6)
NoUnsupportedFacts == phase="done" /\ ~factsRetained => quotient=0 /\ effective=Zero
BindingBeforeBudgets ==
  /\ (phase="error" => ~current.bindingValid /\ ~factsRetained)
  /\ (phase="done" => current.bindingValid)
PayloadIndependent == Outcome([current EXCEPT !.payload=Zero])=Outcome([current EXCEPT !.payload = <<19,0,0,0>>])
IndependentExpectations ==
  /\ (phase="error" => current.expectedConclusion="error")
  /\ (phase="done" =>
       /\ conclusion=current.expectedConclusion /\ factsRetained=current.expectedFacts
       /\ quotient=current.expectedQuotient /\ effective=current.expectedEffective
       /\ truncated=current.expectedTruncated
       /\ evidenceCount=current.expectedEvidence /\ claimCount=current.expectedClaims)
Safety == TypeOK /\ Reduction /\ DefiniteRequiresAll /\ CorrectConclusions
          /\ BudgetConservative /\ NoUnsupportedFacts /\ BindingBeforeBudgets
          /\ PayloadIndependent /\ IndependentExpectations /\ RepeatContract
Terminates == <> (phase="done" \/ phase="error")
=============================================================================
