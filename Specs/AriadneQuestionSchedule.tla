------------------- MODULE AriadneQuestionSchedule -------------------
EXTENDS Naturals, Sequences, FiniteSets
CONSTANTS
  \* @type: Int;
  MaxWork,
  \* @type: Bool;
  Arrival
Tasks == 1..4
Bands == 1..3
\* @type: Seq(Int);
Slots == <<1,2,1,3>>
\* @type: Int => Int;
Band(t) == IF t=4 THEN 1 ELSE t
\* @type: Int => Int;
Cost(t) == IF t=1 THEN 12 ELSE IF t=4 THEN 3 ELSE 2
VARIABLE
  \* @type: Int -> Seq(Int);
  queues
VARIABLE
  \* @type: Int -> Int;
  remaining
VARIABLE
  \* @type: Int -> Int;
  age
VARIABLE
  \* @type: Set(Int);
  admitted
VARIABLE
  \* @type: Seq(Int);
  served
VARIABLE
  \* @type: Int;
  turn
VARIABLE
  \* @type: Int;
  work
VARIABLE
  \* @type: Bool;
  done
vars == <<queues,remaining,age,admitted,served,turn,work,done>>
Init == /\ queues=[b \in Bands |-> <<b>>]
        /\ remaining=[t \in Tasks |-> IF t=4 THEN 0 ELSE Cost(t)]
        /\ admitted={1,2,3} /\ age=[t \in Tasks |-> 0]
        /\ served= <<>> /\ turn=1 /\ work=0 /\ done=FALSE
Runnable == {b \in Bands:Len(queues[b])>0}
Chosen == IF Slots[turn] \in Runnable THEN Slots[turn]
          ELSE CHOOSE b \in Runnable: \A c \in Runnable:b<=c
Admit == /\ Arrival /\ ~done /\ 4 \notin admitted
         /\ admitted'=admitted \cup {4}
         /\ queues'=[queues EXCEPT ![1]=Append(@,4)]
         /\ remaining'=[remaining EXCEPT ![4]=Cost(4)]
         /\ UNCHANGED <<age,served,turn,work,done>>
Step == /\ ~done /\ Runnable # {} /\ work<MaxWork
        /\ LET b == Chosen t == queues[b][1] IN
           /\ remaining'=[remaining EXCEPT ![t]=@-1]
           /\ queues'=[queues EXCEPT ![b]=IF remaining[t]=1 THEN Tail(@) ELSE Append(Tail(@),t)]
           /\ age'=[j \in Tasks |-> IF j=t \/ remaining[j]=0 THEN 0 ELSE age[j]+1]
           /\ served'=Append(served,t)
        /\ work'=work+1 /\ turn'=IF turn=4 THEN 1 ELSE turn+1
        /\ UNCHANGED <<admitted,done>>
Stop == /\ ~done /\ (Runnable={} \/ work=MaxWork) /\ done'=TRUE
        /\ UNCHANGED <<queues,remaining,age,admitted,served,turn,work>>
Next == Admit \/ Step \/ Stop
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety == /\ work<=MaxWork /\ Len(served)=work
          /\ \A t \in Tasks: age[t]<=16 /\ remaining[t]>=0
          /\ \A b \in Bands: \A i \in DOMAIN queues[b]:
                queues[b][i] \in admitted /\ remaining[queues[b][i]]>0 /\ Band(queues[b][i])=b
          /\ \A t \in admitted: remaining[t]+Cardinality({i \in DOMAIN served:served[i]=t})=Cost(t)
Terminates == <>done
=============================================================================
