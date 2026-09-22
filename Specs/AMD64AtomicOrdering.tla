---------------------- MODULE AMD64AtomicOrdering ----------------------
EXTENDS Integers, FiniteSets

\* Bounded serialization fixture for one declared coherent-WB profile.
\* It checks that two atomic increments occupy distinct positions in a single
\* RMW order. This is not a general AMD memory-ordering model and says nothing
\* about surrounding ordinary loads/stores, WC/UC/MMIO, or cache protocol.

Threads == {0, 1}

VARIABLE
  \* @type: Int;
  value
VARIABLE
  \* @type: Set(Int);
  done
VARIABLE
  \* @type: Int -> Int;
  observed

Init == value = 0 /\ done = {} /\ observed = [thread \in Threads |-> -1]

AtomicIncrement(thread) ==
  /\ thread \in Threads \ done
  /\ observed' = [observed EXCEPT ![thread] = value]
  /\ value' = value + 1
  /\ done' = done \cup {thread}

Next == \E thread \in Threads : AtomicIncrement(thread)

TypeOK == value \in 0..2 /\ done \subseteq Threads /\
  observed \in [Threads -> {-1, 0, 1}]

NoLostAtomicUpdate == done = Threads => value = 2 /\
  {observed[thread] : thread \in Threads} = {0, 1}

Safety == TypeOK /\ NoLostAtomicUpdate

==========================================================================
