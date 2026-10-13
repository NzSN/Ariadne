---------------------- MODULE AriadneTargetResolution ----------------------
EXTENDS Integers, FiniteSets, Sequences
CONSTANTS
  \* @type: Int;
  Budget,
  \* @type: Bool;
  MemoryPremise,
  \* @type: Bool;
  MissingEntry,
  \* @type: Bool;
  NewIncoming
VARIABLES
  \* @type: Set(Int);
  remaining,
  \* @type: Set(Int);
  inspected,
  \* @type: Set(Int);
  targets,
  \* @type: Int;
  spent,
  \* @type: Int;
  revision,
  \* @type: Int;
  certificateRevision,
  \* @type: Bool;
  incomingCovered,
  \* @type: Bool;
  complete,
  \* @type: Str;
  phase
\* The finite abstraction retains a bounded index domain, decoded signed
\* offsets, immutable captured read availability, coverage and stale receipts.
\* Byte mapping, BIL admission and width-correct entry decoding are producer
\* premises; this model does not assert earlier runtime memory stability.
Indices == 0..3
Modulus == 16
Base == 2
\* @type: Seq(Int);
Offsets == <<-3, 1, 1, 7>>
\* @type: Int => Int;
Target(i) == (Base + Offsets[i+1]) % Modulus
Readable == IF MissingEntry THEN Indices \ {2} ELSE Indices
AllTargets == {Target(i) : i \in Indices}
vars == <<remaining, inspected, targets, spent, revision,
          certificateRevision, incomingCovered, complete, phase>>
Init ==
 /\ remaining = Indices /\ inspected = {} /\ targets = {} /\ spent = 0
 /\ revision = 0 /\ certificateRevision = -1
 /\ incomingCovered = TRUE /\ complete = FALSE /\ phase = "enumerate"
Read(i) ==
 /\ phase = "enumerate" /\ i \in remaining /\ spent < Budget
 /\ remaining' = remaining \ {i} /\ inspected' = inspected \cup {i}
 /\ targets' = IF i \in Readable THEN targets \cup {Target(i)} ELSE targets
 /\ spent' = spent + 1
 /\ UNCHANGED <<revision, certificateRevision, incomingCovered, complete, phase>>
FinishReads ==
 /\ phase = "enumerate" /\ (remaining = {} \/ spent = Budget)
 /\ phase' = "revalidate"
 /\ UNCHANGED <<remaining, inspected, targets, spent, revision,
                certificateRevision, incomingCovered, complete>>
\* Discovery can expose a guard-bypassing route after enumeration. It must
\* invalidate coverage before publication, even if every table byte was read.
Discover ==
 /\ phase = "revalidate" /\ NewIncoming /\ revision = 0
 /\ revision' = 1 /\ incomingCovered' = FALSE /\ complete' = FALSE
 /\ UNCHANGED <<remaining, inspected, targets, spent, certificateRevision, phase>>
Validate ==
 /\ phase = "revalidate" /\ (~NewIncoming \/ revision = 1)
 /\ certificateRevision' = revision
 /\ complete' = (MemoryPremise /\ incomingCovered /\ remaining = {}
                  /\ Indices \subseteq Readable)
 /\ phase' = "done"
 /\ UNCHANGED <<remaining, inspected, targets, spent, revision, incomingCovered>>
Next == (\E i \in remaining: Read(i)) \/ FinishReads \/ Discover \/ Validate
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety ==
 /\ remaining \subseteq Indices /\ inspected = Indices \ remaining
 /\ spent = Cardinality(inspected) /\ spent <= Budget
 /\ targets = {Target(i) : i \in inspected \cap Readable}
 /\ (complete => /\ phase = "done" /\ certificateRevision = revision
                  /\ MemoryPremise /\ incomingCovered
                  /\ AllTargets \subseteq targets)
 /\ (~MemoryPremise \/ MissingEntry \/ NewIncoming \/ Budget < 4 => ~complete)
Terminates == <> (phase = "done")
=============================================================================
