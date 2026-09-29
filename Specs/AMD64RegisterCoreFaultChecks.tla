------------------ MODULE AMD64RegisterCoreFaultChecks ------------------
EXTENDS AMD64Exceptions

\* Bounded Stage D witness for the source-backed LOCK-invalid MOV register
\* alternative. The form validator and this architectural #UD rollback are
\* checked separately until a case-specific dispatcher composes them.
ZeroIP == [bit \in AddressBits |-> FALSE]
Restart == [savedIP |-> ZeroIP, resumeIP |-> ZeroIP,
  completedIterations |-> 0, remainingIterations |-> 0]
UDTemplate == [vector |-> "UD", class |-> "fault", errorCode |-> 0,
  hasErrorCode |-> FALSE, cr2 |-> ZeroIP, hasCR2 |-> FALSE,
  restart |-> Restart]
\* @type: Seq({kind: Str, index: Int});
RegisterEffect == <<[kind |-> "registerWrite", index |-> 0]>>
LockFault == RollbackFault(ZeroIP, UDTemplate, RegisterEffect)

FaultWitness ==
  /\ LockFault.kind = "faulted"
  /\ LockFault.commitPolicy = "rollback"
  /\ LockFault.committed = 0
  /\ LockFault.exception.vector = "UD"
  /\ ~LockFault.exception.hasErrorCode
  /\ LockFault.exception.restart.savedIP = ZeroIP
  /\ LockFault.exception.restart.resumeIP = ZeroIP
  /\ OutcomeWellFormed(LockFault)
  /\ RestartContract(LockFault)

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ FaultWitness

========================================================================
