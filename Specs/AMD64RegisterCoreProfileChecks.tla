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

\* The first Stage D register-only candidate is checked as a complete
\* normalized payload and an explicitly assumed fallthrough boundary. These
\* fixtures do not convert the trusted fetch/event assumptions into proof of
\* retirement or architectural fault delivery.
UserMov64Before == [Base!StateWithRAX(Base!ZeroBits(64)) EXCEPT
  !.execution.cpl = 3]
UserMov64After == WriteGPR(UserMov64Before, Base!GPRRef(0, "full64"),
  ReadSource(UserMov64Before, Base!Mov64SignReviewed.operands[2].ref))
UserMov64Body == Base!BodyOutcome(UserMov64After)
UserMov64NextIP == Base!Word({1,2,3})
UserMov64Evidence == [beforeIP |-> UserMov64Before.rip,
  instructionLength |-> 7, nextIP |-> UserMov64NextIP,
  fetchAcceptedAssumption |-> TRUE,
  synchronousEventsResolvedAssumption |-> TRUE,
  asynchronousEventsCheckedAssumption |-> TRUE]
UserMov64BoundaryAfter == [UserMov64After EXCEPT !.rip = UserMov64NextIP]
UserMov64BoundaryOutcome == [kind |-> "fallthrough-applied",
  stateWritten |-> TRUE, state |-> UserMov64BoundaryAfter, reason |-> ""]
UserMov64Locked == [Base!Mov64SignReviewed EXCEPT
  !.prefixes = {"rex-w", "lock"}]
UserMov64WithoutW == [Base!Mov64SignReviewed EXCEPT !.prefixes = {}]

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

Mov64SignCandidate ==
  /\ CPUStateWellFormed(Base!Architecture, UserMov64Before)
  /\ UserMov64Before.execution.mode = "long64"
  /\ UserMov64Before.execution.cpl = 3
  /\ ExecuteReviewed(Base!Architecture, Base!FormProfile,
       Base!Mov64SignReviewed, UserMov64Before, UserMov64Body)
  /\ ApplyFallthrough(UserMov64Body, UserMov64Evidence,
       UserMov64BoundaryOutcome)
  /\ UserMov64After.gpr[0] = Base!OneBits(64)
  /\ \A r \in 1..15 : UserMov64After.gpr[r] = UserMov64Before.gpr[r]
  /\ UserMov64BoundaryAfter.rflags = UserMov64Before.rflags
  /\ UserMov64BoundaryAfter.segments = UserMov64Before.segments
  /\ UserMov64BoundaryAfter.x87 = UserMov64Before.x87
  /\ UserMov64BoundaryAfter.vectors = UserMov64Before.vectors
  /\ UserMov64BoundaryAfter.kMask = UserMov64Before.kMask
  /\ UserMov64BoundaryAfter.mxcsr = UserMov64Before.mxcsr
  /\ UserMov64BoundaryAfter.rip = UserMov64NextIP
  /\ ExecuteReviewed(Base!Architecture, Base!FormProfile,
       UserMov64Locked, UserMov64Before,
       Base!RejectedOutcome(UserMov64Before, "architectural-invalid"))
  /\ ExecuteReviewed(Base!Architecture, Base!FormProfile,
       UserMov64WithoutW, UserMov64Before,
       Base!RejectedOutcome(UserMov64Before, "normalization-error"))

UnaryAcceptance ==
  /\ ExecuteSupplementalUnary(Base!Architecture, Base!FormProfile,
       UserInc, UserBefore, Base!BodyOutcome(UserIncAfter))
  /\ UserIncAfter.rip = UserBefore.rip

Init == profileChecked = FALSE
Next == profileChecked' = ~profileChecked
Safety == profileChecked \in BOOLEAN /\ CaseAcceptance /\ MovBoundary /\
          Mov64SignCandidate /\ UnaryAcceptance

=======================================================================
