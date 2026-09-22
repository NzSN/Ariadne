------------------------ MODULE AMD64Exceptions ------------------------
EXTENDS AMD64Memory

\* Exception, commit and restart vocabulary shared by later instruction
\* families. It intentionally does not perform IDT/gate delivery. The outcome
\* records what architectural execution exposes at the instruction boundary;
\* delivery is a distinct Volume 2 state transition still owed by C3/F1.
\*
\* Authority: AMD APM Volume 2 revision 3.45 sections 8.1, 8.2 and 8.5.

\* @typeAlias: amd64Effect = {kind: Str, index: Int};
\* @typeAlias: amd64Restart = {savedIP: $amd64Address,
\*   resumeIP: $amd64Address, completedIterations: Int,
\*   remainingIterations: Int};
\* @typeAlias: amd64Exception = {vector: Str, class: Str, errorCode: Int,
\*   hasErrorCode: Bool, cr2: $amd64Address, hasCR2: Bool,
\*   restart: $amd64Restart};
\* @typeAlias: amd64Outcome = {kind: Str, commitPolicy: Str,
\*   effects: Seq($amd64Effect), committed: Int,
\*   exception: $amd64Exception, hasException: Bool,
\*   progress: $amd64Restart, hasProgress: Bool};

ExceptionVectors == {"DE", "DB", "BP", "OF", "BR", "UD", "NM", "DF",
  "TS", "NP", "SS", "GP", "PF", "MF", "AC", "MC", "XF", "CP",
  "HV", "VC", "SX"}
ExceptionClasses == {"fault", "trap", "abort", "interrupt"}
OutcomeKinds == {"retired", "faulted", "trapped", "aborted", "inProgress"}
CommitPolicies == {"rollback", "committedPrefix", "afterInstruction"}

\* Volume 2 section 8.2.17 says #AC returns an error code whose value is
\* zero. `hasErrorCode` distinguishes that pushed zero from exceptions whose
\* "Error Code Returned" field is None.
\* @type: $amd64Exception => Bool;
AlignmentExceptionWellFormed(exception) ==
  /\ exception.vector = "AC"
  /\ exception.class = "fault"
  /\ exception.hasErrorCode
  /\ exception.errorCode = 0
  /\ ~exception.hasCR2

\* @type: (Seq($amd64Effect), Int) => Seq($amd64Effect);
CommittedPrefix(effects, committed) ==
  SubSeq(effects, 1, committed)

\* Ordinary fault: no instruction effects commit, saved and resume IP both
\* identify the faulting instruction. A later per-form rule may use an
\* explicit committedPrefix policy only when the manual permits progress.
\* @type: ($amd64Address, $amd64Exception, Seq($amd64Effect)) => $amd64Outcome;
RollbackFault(faultingIP, exception, effects) ==
  [kind |-> "faulted", commitPolicy |-> "rollback", effects |-> effects,
   committed |-> 0,
   hasException |-> TRUE, hasProgress |-> FALSE,
   progress |-> exception.restart,
   exception |-> [exception EXCEPT
     !.restart.savedIP = faultingIP,
     !.restart.resumeIP = faultingIP,
     !.restart.completedIterations = 0]]

\* @type: ($amd64Address, $amd64Exception, Seq($amd64Effect), Int, Int, Int) => $amd64Outcome;
PrefixFault(faultingIP, exception, effects, committedEffects,
            completedIterations, remainingIterations) ==
  [kind |-> "faulted", commitPolicy |-> "committedPrefix", effects |-> effects,
   committed |-> committedEffects,
   hasException |-> TRUE, hasProgress |-> TRUE,
   progress |-> [savedIP |-> faultingIP, resumeIP |-> faultingIP,
     completedIterations |-> completedIterations,
     remainingIterations |-> remainingIterations],
   exception |-> [exception EXCEPT
     !.restart.savedIP = faultingIP,
     !.restart.resumeIP = faultingIP,
     !.restart.completedIterations = completedIterations,
     !.restart.remainingIterations = remainingIterations]]

\* @type: ($amd64Address, $amd64Exception, Seq($amd64Effect)) => $amd64Outcome;
Trap(nextIP, exception, effects) ==
  [kind |-> "trapped", commitPolicy |-> "afterInstruction", effects |-> effects,
   committed |-> Len(effects),
   hasException |-> TRUE, hasProgress |-> FALSE,
   progress |-> exception.restart,
   exception |-> [exception EXCEPT
     !.restart.savedIP = nextIP,
     !.restart.resumeIP = nextIP,
     \* A trap commits all effects, but that count is not a REP/string
     \* iteration count. Ordinary traps carry no iteration progress.
     !.restart.completedIterations = 0,
     !.restart.remainingIterations = 0]]

\* A restartable instruction may expose an architectural prefix before either
\* retirement or a fault. The template exception keeps the record type fixed;
\* hasException=FALSE makes it semantically absent.
\* @type: ($amd64Restart, $amd64Exception, Seq($amd64Effect), Int) => $amd64Outcome;
InProgressOutcome(progress, exceptionTemplate, effects, committed) ==
  [kind |-> "inProgress", commitPolicy |-> "committedPrefix",
   effects |-> effects, committed |-> committed,
   exception |-> exceptionTemplate, hasException |-> FALSE,
   progress |-> progress, hasProgress |-> TRUE]

\* @type: $amd64Fault => Str;
MemoryFaultClass(fault) == "fault"

\* The common access pipeline constructs at most one stage of candidates.
\* The form layer must ensure uniqueness if it adds same-stage alternatives.
\* @type: Set($amd64Fault) => Bool;
UniqueFaultCandidate(candidates) == Cardinality(candidates) <= 1

\* @type: Set($amd64Fault) => Bool;
CommonFaultPriority(candidates) ==
  \A fault \in candidates :
    /\ fault.stage \in 1..3
    /\ (fault.stage = 1 => fault.vector \in {"SS", "GP"})
    /\ (fault.stage = 2 => fault.vector = "PF")
    /\ (fault.stage = 3 => fault.vector = "AC")

\* @type: $amd64Outcome => Bool;
OutcomeWellFormed(outcome) ==
  /\ outcome.kind \in OutcomeKinds
  /\ outcome.commitPolicy \in CommitPolicies
  /\ outcome.committed \in 0..Len(outcome.effects)
  /\ outcome.exception.vector \in ExceptionVectors
  /\ outcome.exception.class \in ExceptionClasses
  /\ outcome.exception.restart.completedIterations >= 0
  /\ outcome.exception.restart.remainingIterations >= 0
  /\ outcome.progress.completedIterations >= 0
  /\ outcome.progress.remainingIterations >= 0
  /\ (outcome.kind \in {"faulted", "trapped", "aborted"} => outcome.hasException)
  /\ (outcome.kind = "inProgress" => ~outcome.hasException /\ outcome.hasProgress)
  /\ (outcome.hasException /\ outcome.exception.vector = "AC" =>
        AlignmentExceptionWellFormed(outcome.exception))
  /\ (outcome.commitPolicy = "rollback" => outcome.committed = 0)
  /\ (outcome.commitPolicy = "afterInstruction" =>
        outcome.committed = Len(outcome.effects))

\* @type: $amd64Outcome => Bool;
RestartContract(outcome) ==
  /\ (outcome.exception.class = "fault" /\
       outcome.commitPolicy = "rollback" =>
       outcome.exception.restart.savedIP = outcome.exception.restart.resumeIP)
  /\ (outcome.exception.class = "trap" =>
       outcome.commitPolicy = "afterInstruction")
  /\ (outcome.exception.class = "abort" => outcome.kind = "aborted")

==========================================================================
