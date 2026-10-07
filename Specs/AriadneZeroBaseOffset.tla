---------------------- MODULE AriadneZeroBaseOffset ----------------------
EXTENDS Integers, FiniteSets
\* A question-level decision model. Decoded roles, context and semantics are
\* supplied premises; this is not instruction-step or historical-path semantics.
\* @type: (Bool, Bool, Bool, Bool, Int, Int) => Str;
Conclusion(admitted, coherent, evidenceFits, claimsFit, base, displacement) ==
  IF ~(admitted /\ coherent /\ evidenceFits /\ claimsFit) THEN "unknown"
  ELSE IF base = 0 /\ displacement # 0 THEN "consistent_with_evidence"
  ELSE "refuted_under_premises"
\* @type: Bool;
Safety ==
  \A admitted, coherent, evidenceFits, claimsFit \in BOOLEAN:
    \A base \in {0,1,2}, displacement \in {-8,0,8}:
      LET c == Conclusion(admitted,coherent,evidenceFits,claimsFit,base,displacement)
      IN /\ (c # "unknown" => admitted /\ coherent /\ evidenceFits /\ claimsFit)
         /\ (~evidenceFits \/ ~claimsFit => c = "unknown")
         /\ (~coherent => c # "refuted_under_premises")
         /\ (c = "consistent_with_evidence" => base = 0 /\ displacement # 0)
         /\ (admitted /\ coherent /\ evidenceFits /\ claimsFit =>
               (c = "refuted_under_premises" <=> base # 0 \/ displacement = 0))
VARIABLE
  \* @type: Int;
  checked
Init == checked = 0
Next == /\ checked = 0 /\ checked' = 1
Spec == Init /\ [][Next]_checked
=============================================================================
