------------------- MODULE AMD64LegacyProjectionChecks -------------------
EXTENDS AMD64LegacyProjection

KernelCorrespondence ==
  \A width \in {32, 64} : \A op \in Old!DataOps : \A left, right \in Words :
    LET before == Before(left, right)
    IN Old!DataResults(Instruction(op, width), before) = KernelProjection(op, width, before)

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ KernelCorrespondence
=============================================================================
