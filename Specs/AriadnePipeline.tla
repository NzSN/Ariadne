------------------------- MODULE AriadnePipeline -------------------------
EXTENDS Naturals

\* Small end-to-end instance: instruction 1 defines x, instruction 2 uses x.
\* Unlike the larger recovery fixtures, all phases fit within eight steps.
VARIABLES
  \* @type: Str;
  phase,
  \* @type: Set(Int);
  pending,
  \* @type: Set(Int);
  visited,
  \* @type: Set(Int);
  decoded,
  \* @type: Int -> Str;
  provenance,
  \* @type: Set({src: Int, dst: Int, kind: Str});
  edges,
  \* @type: Set({site: Int, reason: Str});
  obligations,
  \* @type: Int -> Set({loc: Str, site: Int, origin: Str});
  reaching,
  \* @type: Set(Int);
  slice

\* @type: Set(Int);
NoAddresses == {}

\* @type: Int -> {kind: Str, fall: Set(Int), targets: Set(Int), complete: Bool,
\*               uses: Set(Str), mustDefs: Set(Str), mayDefs: Set(Str)};
Instructions == [a \in 1..2 |->
  [kind |-> IF a = 1 THEN "ordinary" ELSE "return",
   fall |-> IF a = 1 THEN {2} ELSE {},
   targets |-> {}, complete |-> TRUE,
   uses |-> IF a = 2 THEN {"x"} ELSE {},
   mustDefs |-> IF a = 1 THEN {"x"} ELSE {},
   mayDefs |-> IF a = 1 THEN {"x"} ELSE {}]]

Engine == INSTANCE Ariadne WITH
  Addresses <- 1..2, Locations <- {"x"}, EntryPoints <- {1}, SliceSeeds <- {2},
  InputKind <- "binary", Captured <- NoAddresses, FileBacked <- 1..2,
  TrustedFallback <- NoAddresses, Decodable <- 1..2, Insn <- Instructions

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates
FixtureResult == phase = "done" =>
  /\ decoded = {1, 2}
  /\ slice = {1, 2}
  /\ obligations = {}
  /\ reaching[2] = {[loc |-> "x", site |-> 1, origin |-> "instruction"]}
Safety == Engine!TypeOK /\ Engine!RecoveryInvariant /\ Engine!DefinitionInvariant
          /\ Engine!ResultInvariant /\ FixtureResult

\* Reachability witness: checking this deliberately false invariant should
\* yield a counterexample ending in done. It is not a safety requirement.
NotDone == phase # "done"

=============================================================================
