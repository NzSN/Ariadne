-------------------- MODULE AMD64RegisterViewsChecks --------------------
EXTENDS AMD64RegisterViews

\* Sparse basis words plus all-zero/all-one and alternating bits expose both
\* view boundaries. These are finite full-width vectors, not all 2^64 words.
Zeros == [bit \in 1..64 |-> FALSE]
Ones == [bit \in 1..64 |-> TRUE]
Words == {Zeros, Ones, [bit \in 1..64 |-> bit % 2 = 0]} \cup
         {[bit \in 1..64 |-> bit = selected] : selected \in {1,8,9,16,17,32,33,64}}

\* Every view write recovers the low payload bits when read through that view.
ReadAfterWrite ==
  \A before, value \in Words : \A view \in Views :
    ReadView(WriteView64(before, value, view), view) =
      [bit \in 1..64 |-> IF bit <= view.width THEN value[bit] ELSE FALSE]

\* Independently stated boundary cases catch zero-extension, high-byte offset,
\* payload alignment, and accidental destruction of bits outside a short view.
Boundaries ==
  /\ WriteView64(Ones, Zeros, Low32) = Zeros
  /\ WriteView64(Ones, Zeros, Low16) = [bit \in 1..64 |-> bit > 16]
  /\ WriteView64(Ones, Zeros, High8) = [bit \in 1..64 |-> bit <= 8 \/ bit > 16]
  /\ WriteView64(Zeros, Ones, High8) = [bit \in 1..64 |-> 8 < bit /\ bit <= 16]
  /\ \A value \in Words : WriteView64(Ones, value, Full64) = value

FrameAndShape ==
  \A before, value \in Words : \A view \in Views :
    LET after == WriteView64(before, value, view)
    IN /\ WordWellFormed(after) /\ WordWellFormed(ReadView(before, view))
       /\ \A bit \in 1..64 :
            (bit <= view.offset \/ bit > view.offset + view.width) =>
              after[bit] = (IF view = Low32 THEN FALSE ELSE before[bit])

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ ReadAfterWrite /\ Boundaries /\ FrameAndShape
=============================================================================
