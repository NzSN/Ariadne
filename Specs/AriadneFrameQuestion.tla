--------------------- MODULE AriadneFrameQuestion ---------------------
EXTENDS Naturals, FiniteSets
\* Finite composition authority. Actual BAP/byte/activation and receipt checks
\* are concrete premises. 4-bit predicate enumeration abstracts the BV profile;
\* source closure, coherent witnesses and writer coverage are independent.
CONSTANTS
  \* @type: Str;
  Scenario,
  \* @type: Int;
  MaxWork
Values == 0..15
Writers == {0,1,2,3}
UnknownAlternatives == {0,2,3}
InitialEpoch == 1
Allowed == IF Scenario="Refuted" THEN {2,4}
           ELSE IF Scenario="Conflict" THEN {} ELSE {0,2,4}
Constraint == {0}
Closed == Scenario \notin {"Open","AbstractOnly","CyclicObserved","FaultAfter"}
AllPointFactsChecked == Scenario # "FutureMoment"
BeforeCaptureBoundary == Scenario # "FaultAfter"
WholeWordSupported == Scenario # "PartialWord"
HasWitness == Scenario \notin {"Open","AbstractOnly","Refuted","Conflict","CyclicObserved"}
              /\ AllPointFactsChecked /\ BeforeCaptureBoundary /\ WholeWordSupported
Hypotheses == IF Scenario="Conditional" THEN {7} ELSE {}
Disjoint == Scenario="Disjoint"
AllInstances == Scenario # "LoopInstance"
VARIABLE
  \* @type: Int;
  epoch
VARIABLE
  \* @type: Int;
  proofEpoch
VARIABLE
  \* @type: Str;
  verdict
VARIABLE
  \* @type: Set(Int);
  candidates
VARIABLE
  \* @type: Set(Int);
  excluded
VARIABLE
  \* @type: Set(Int);
  premises
VARIABLE
  \* @type: Int;
  work
VARIABLE
  \* @type: Str;
  phase
vars == <<epoch,proofEpoch,verdict,candidates,excluded,premises,work,phase>>
Init == /\ epoch=InitialEpoch /\ proofEpoch=0 /\ verdict="unknown"
        /\ candidates=Writers /\ excluded={} /\ premises=Hypotheses
        /\ work=0 /\ phase="assess"
Assess == /\ phase="assess" /\ work<MaxWork
          /\ verdict'=IF Allowed={} THEN "premise_conflict"
                       ELSE IF Closed /\ Allowed \cap Constraint={} THEN "refuted_under_model"
                       ELSE IF HasWitness /\ Allowed \cap Constraint # {} THEN "possible_under_model"
                       ELSE "unknown"
          /\ proofEpoch'=epoch
          /\ excluded'=IF Disjoint /\ AllInstances THEN {1} ELSE {}
          /\ phase'="revision" /\ work'=work+1
          /\ UNCHANGED <<epoch,candidates,premises>>
Revise == /\ phase="revision" /\ work<MaxWork
          /\ IF Scenario="Revision" THEN /\ epoch'=epoch+1 /\ proofEpoch'=0 /\ verdict'="unknown" /\ excluded'={}
             ELSE UNCHANGED <<epoch,proofEpoch,verdict,excluded>>
          /\ phase'="done" /\ work'=work+1
          /\ UNCHANGED <<candidates,premises>>
Stop == /\ phase # "done" /\ work=MaxWork /\ phase'="done"
        /\ UNCHANGED <<epoch,proofEpoch,verdict,candidates,excluded,premises,work>>
Next == Assess \/ Revise \/ Stop
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == /\ candidates=Writers /\ premises=Hypotheses /\ work<=MaxWork
          /\ excluded \cap UnknownAlternatives={}
          /\ (excluded # {} => Disjoint /\ AllInstances)
          /\ (verdict="refuted_under_model" => Closed /\ Allowed # {} /\ Allowed \cap Constraint={} /\ proofEpoch=epoch)
          /\ (verdict="possible_under_model" => HasWitness /\ AllPointFactsChecked /\ BeforeCaptureBoundary /\ WholeWordSupported /\ Allowed \cap Constraint # {} /\ proofEpoch=epoch)
          /\ (epoch # InitialEpoch => verdict="unknown" /\ excluded={})
Terminates == <>(phase="done")
=============================================================================
