--------------------------- MODULE AriadneCalls ---------------------------
EXTENDS AriadneMachineCommon

\* Instruction 1 calls either 3 or 4 and may return to continuation 2.
\* Root 3 is independently analyzed; readable callee 4 is not a root.
\* This distinguishes graph visibility, local discovery and data-flow policy:
\*   1 --summary--> 2     1 --call--> 3     1 --call--> 4
\* Caller definitions must reach 2, never 3 via the call edge; 4 stays unvisited.
VARIABLES
  \* @type: $analysisPhase;
  phase,
  \* @type: Set($address);
  pending,
  \* @type: Set($address);
  visited,
  \* @type: Set($address);
  decoded,
  \* @type: $address -> $byteSource;
  provenance,
  \* @type: Set({src: $address, dst: $address, kind: $edgeKind});
  edges,
  \* @type: Set({site: $address, reason: $obligationReason});
  obligations,
  \* @type: $address -> Set({loc: $location, site: $address,
  \*                         origin: $definitionOrigin});
  reaching,
  \* @type: Set($address);
  slice

\* @type: Set($address);
NoAddresses == {}

\* @type: $address -> {kind: $instructionKind,
\*               fall: Set($address), targets: Set($address), complete: Bool,
\*               uses: Set($location), mustDefs: Set($location),
\*               mayDefs: Set($location)};
Instructions == [a \in 1..4 |->
  [kind |-> IF a = 1 THEN "call" ELSE "return",
   fall |-> IF a = 1 THEN {2} ELSE {},
   targets |-> IF a = 1 THEN {3, 4} ELSE {}, complete |-> TRUE,
   uses |-> IF a = 1 THEN {} ELSE {"x"},
   mustDefs |-> {}, mayDefs |-> IF a = 1 THEN {"x"} ELSE {}]]

Engine == INSTANCE Ariadne WITH
  SnapshotId <- "calls-snapshot",
  Addresses <- 1..4, Locations <- {"x"}, EntryPoints <- {1, 3}, SliceSeeds <- {2, 3},
  InputKind <- "binary", Captured <- NoAddresses, FileBacked <- 1..4,
  TrustedFallback <- NoAddresses, Decodable <- 1..4, Insn <- Instructions

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates

\* Assert the policy throughout recovery/propagation, not just at completion.
\* These expectations are independent of the implementation's edge filtering.
CallPolicy ==
  /\ 4 \notin (pending \cup visited)
  /\ Engine!Preds(3) = {}
  /\ reaching[3] \subseteq {[loc |-> "x", site |-> 3, origin |-> "entry"]}
  /\ (1 \in decoded =>
       {[src |-> 1, dst |-> 2, kind |-> "summary"],
        [src |-> 1, dst |-> 3, kind |-> "call"],
        [src |-> 1, dst |-> 4, kind |-> "call"]} \subseteq edges)

FixtureResult == phase = "done" =>
  /\ decoded = {1, 2, 3}
  /\ slice = {1, 2, 3}
  /\ obligations = {}
  /\ edges = {[src |-> 1, dst |-> 2, kind |-> "summary"],
               [src |-> 1, dst |-> 3, kind |-> "call"],
               [src |-> 1, dst |-> 4, kind |-> "call"]}
  /\ reaching[2] = {[loc |-> "x", site |-> 1, origin |-> "entry"],
                     [loc |-> "x", site |-> 1, origin |-> "instruction"]}
  /\ reaching[3] = {[loc |-> "x", site |-> 3, origin |-> "entry"]}

Safety == Engine!TypeOK /\ Engine!RecoveryInvariant /\ Engine!DefinitionInvariant
          /\ Engine!ResultInvariant /\ CallPolicy /\ FixtureResult

=============================================================================
