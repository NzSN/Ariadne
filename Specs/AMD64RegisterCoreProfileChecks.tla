---------------- MODULE AMD64RegisterCoreProfileChecks ----------------
EXTENDS AMD64IntegerExecution

VARIABLE
  \* @type: Bool;
  profileChecked

Base == INSTANCE AMD64IntegerExecutionChecks WITH checked <- profileChecked

UserUnaryFormIds == {
  "AMD64-F-0282","AMD64-F-0283","AMD64-F-0284","AMD64-F-0285",
  "AMD64-F-0318","AMD64-F-0319","AMD64-F-0320","AMD64-F-0321",
  "AMD64-F-0549","AMD64-F-0550","AMD64-F-0551","AMD64-F-0552",
  "AMD64-F-0557","AMD64-F-0558","AMD64-F-0559","AMD64-F-0560"}
RegisterCore49 == ReviewedFormIds \cup UserUnaryFormIds

UserBefore == [Base!Before12CD EXCEPT !.execution.cpl = 3]
UserMovAfter == WriteGPR(UserBefore, Base!AH,
  ReadSource(UserBefore, Base!Imm12))
UserMovBody == Base!BodyOutcome(UserMovAfter)
UserNextIP == Base!Word({2})
UserBoundaryEvidence == [beforeIP |-> UserBefore.rip,
  instructionLength |-> 2, nextIP |-> UserNextIP,
  fetchAcceptedAssumption |-> TRUE,
  synchronousEventsResolvedAssumption |-> TRUE,
  asynchronousEventsCheckedAssumption |-> TRUE]
UserBoundaryAfter == [UserMovAfter EXCEPT !.rip = UserNextIP]
UserBoundaryOutcome == [kind |-> "fallthrough-applied", stateWritten |-> TRUE,
  state |-> UserBoundaryAfter, reason |-> ""]

UserInc == Base!UnaryInstruction("AMD64-F-0318", 8, Base!AL, {})
UserIncAfter == Base!UnaryAfter("inc", UserInc, UserBefore)

CaseAcceptance ==
  /\ Cardinality(RegisterCore49) = 49
  /\ UserUnaryFormIds \subseteq FormsSupplement!SupplementalUnaryFormIds
  /\ \A formId \in ReviewedFormIds : ReviewedOperation(formId) \in IntegerOperations
  /\ \A formId \in UserUnaryFormIds :
       FormsSupplement!SupplementalUnaryOperation(formId) \in UnaryOperations

MovBoundary ==
  /\ CPUStateWellFormed(Base!Architecture, UserBefore)
  /\ UserBefore.execution.mode = "long64" /\ UserBefore.execution.cpl = 3
  /\ ExecuteReviewed(Base!Architecture, Base!FormProfile,
       Base!MovAHInstruction, UserBefore, UserMovBody)
  /\ ApplyFallthrough(UserMovBody, UserBoundaryEvidence, UserBoundaryOutcome)
  /\ UserBoundaryAfter.rip = UserNextIP
  /\ UserBoundaryAfter.gpr = UserMovAfter.gpr
  /\ UserBoundaryAfter.rflags = UserMovAfter.rflags

UnaryAcceptance ==
  /\ ExecuteSupplementalUnary(Base!Architecture, Base!FormProfile,
       UserInc, UserBefore, Base!BodyOutcome(UserIncAfter))
  /\ UserIncAfter.rip = UserBefore.rip

Init == profileChecked = FALSE
Next == profileChecked' = ~profileChecked
Safety == profileChecked \in BOOLEAN /\ CaseAcceptance /\ MovBoundary /\ UnaryAcceptance

=======================================================================
