------------------------- MODULE AriadneExample -------------------------
EXTENDS Naturals, FiniteSets

CONSTANT
  \* @type: Str;
  Mode
CONSTANT
  \* @type: Str;
  Scenario
VARIABLE
  \* @type: Str;
  phase
VARIABLE
  \* @type: Set(Int);
  pending
VARIABLE
  \* @type: Set(Int);
  visited
VARIABLE
  \* @type: Set(Int);
  decoded
VARIABLE
  \* @type: Int -> Str;
  provenance
VARIABLE
  \* @type: Set({src: Int, dst: Int, kind: Str});
  edges
VARIABLE
  \* @type: Set({site: Int, reason: Str});
  obligations
VARIABLE
  \* @type: Int -> Set({loc: Str, site: Int, origin: Str});
  reaching
VARIABLE
  \* @type: Set(Int);
  slice
ASSUME Mode \in {"binary", "dump"} /\ Scenario \in {"partial", "loop", "closed"}

Addr == 1..7
Loc == {"x", "target"}
I(k, f, t, c, u, must, may) ==
  [kind |-> k, fall |-> f, targets |-> t, complete |-> c,
   uses |-> u, mustDefs |-> must, mayDefs |-> may]

\* Diamond with a loop back to a definition. Both definitions must reach 5.
LoopInstructions == [a \in Addr |->
  CASE a = 1 -> I("conditional", {2}, {3}, TRUE, {}, {}, {})
    [] a = 2 -> I("ordinary", {4}, {}, TRUE, {}, {"x"}, {"x"})
    [] a = 3 -> I("ordinary", {4}, {}, TRUE, {}, {"x"}, {"x"})
    [] a = 4 -> I("conditional", {5}, {2}, TRUE, {"x"}, {}, {})
    [] OTHER -> I("return", {}, {}, TRUE, {"x"}, {}, {})]

\* Partial fixture: 6 has unavailable bytes; 7 has bytes but cannot decode.
\* The call's opaque summary may change every tracked location, killing none.
OtherInstructions == [a \in Addr |->
  CASE a = 1 -> I("conditional", {2}, {3}, TRUE, {}, {}, {})
    [] a = 2 -> I("ordinary", {4}, {}, TRUE, {}, {"x"}, {"x"})
    [] a = 3 -> I("indirect", {},
                  IF Scenario = "closed" THEN {4} ELSE {4, 6, 7},
                  Scenario = "closed", {"target"}, {}, {})
    [] a = 4 -> I("call", {5}, {6}, Scenario = "closed", {"x"}, {}, Loc)
    [] OTHER -> I("return", {}, {}, TRUE, {"x"}, {}, {})]

Instructions == IF Scenario = "loop" THEN LoopInstructions ELSE OtherInstructions
Files == {1, 2, 3, 4, 5, 7}
Capture == IF Scenario = "partial" THEN {1, 3, 4} ELSE {1, 3, 4, 5}
Fallback == {2, 7}
Seeds == IF Scenario = "loop" THEN {5} ELSE {4, 5}

Engine == INSTANCE Ariadne WITH
  SnapshotId <- "example-snapshot",
  Addresses <- Addr, Locations <- Loc, EntryPoints <- {1}, SliceSeeds <- Seeds,
  InputKind <- Mode, Captured <- Capture, FileBacked <- Files,
  TrustedFallback <- Fallback, Decodable <- 1..6, Insn <- Instructions

Spec == Engine!Spec
\* Explicit action interface for Apalache's bounded safety checks. The fair
\* temporal Spec above remains the TLC interface for termination checking.
Init == Engine!Init
Next == Engine!Next
BinaryConstants == Mode = "binary" /\ Scenario = "partial"
DumpConstants == Mode = "dump" /\ Scenario = "partial"
LoopConstants == Mode = "binary" /\ Scenario = "loop"
ClosedConstants == Mode = "dump" /\ Scenario = "closed"
TypeOK == Engine!TypeOK
RecoveryInvariant == Engine!RecoveryInvariant
DefinitionInvariant == Engine!DefinitionInvariant
ResultInvariant == Engine!ResultInvariant
Terminates == Engine!Terminates

ExpectedDecoded == IF Mode = "dump" /\ Scenario = "partial" THEN 1..4 ELSE 1..5
ExpectedSlice == IF Scenario = "loop" THEN {2, 3, 5}
                 ELSE IF Mode = "dump" /\ Scenario = "partial" THEN {2, 4}
                 ELSE {2, 4, 5}
ExpectedObligations ==
  IF Scenario # "partial" THEN {}
  ELSE {Engine!Obligation(3, "indirect-targets"),
        Engine!Obligation(4, "call-targets"),
        Engine!Obligation(6, "unavailable"),
        Engine!Obligation(7, "decode-failed")}
       \cup IF Mode = "dump" THEN {Engine!Obligation(5, "unavailable")} ELSE {}

\* Exact independent fixture expectations catch dropped branches, dropped
\* obligations, accidental call-target traversal and an under-approximated slice.
FixtureResult == phase = "done" =>
  /\ decoded = ExpectedDecoded
  /\ slice = ExpectedSlice
  /\ obligations = ExpectedObligations
  /\ Engine!CallGraph =
       IF Scenario = "loop" THEN {} ELSE {Engine!Edge(4, 6, "call")}
  /\ (Scenario # "loop" => Engine!Edge(4, 5, "summary") \in Engine!LocalGraph)
  /\ (Scenario = "closed" => 6 \notin visited)
  /\ (Engine!ScopeClosed <=> Scenario # "partial")
  /\ (Scenario = "loop" =>
        {d.site : d \in {v \in reaching[5] : v.loc = "x"}} = {2, 3})
  /\ (Mode = "dump" => provenance[1] = "captured"
                        /\ provenance[2] = "file")

Safety == TypeOK /\ RecoveryInvariant /\ DefinitionInvariant
          /\ ResultInvariant /\ FixtureResult

=============================================================================
