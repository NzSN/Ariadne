------------------- MODULE AMD64RegisterViewsSymbolic -------------------
EXTENDS AMD64RegisterViews

\* Symbolic full-width input fixture for Apalache only. Never ask TLC to
\* enumerate [1..64 -> BOOLEAN]. The bound is execution depth, not word width.
VARIABLES
  \* @type: $amd64Word;
  before,
  \* @type: $amd64Word;
  value,
  \* @type: $amd64View;
  view

Init == /\ before \in [1..64 -> BOOLEAN]
        /\ value \in [1..64 -> BOOLEAN]
        /\ view \in Views
Next == UNCHANGED <<before, value, view>>

Safety ==
  LET after == WriteView64(before, value, view)
  IN /\ WordWellFormed(after)
     /\ ReadView(after, view) =
          [bit \in 1..64 |-> IF bit <= view.width THEN value[bit] ELSE FALSE]
     /\ \A bit \in 1..64 :
          (bit <= view.offset \/ bit > view.offset + view.width) =>
            after[bit] = (IF view = Low32 THEN FALSE ELSE before[bit])
=============================================================================
