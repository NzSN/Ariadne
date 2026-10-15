-------------------- MODULE AriadneLoopTargetClosure --------------------
EXTENDS Integers, FiniteSets, Sequences
\* @typeAlias: loopScalar = {b: Int, s: Int, p: Int};
\* @typeAlias: loopScenario = Str;
\* @typeAlias: loopPhase = Str;
\* @typeAlias: loopCheck = Str;
Loop_typedefs == TRUE
CONSTANTS
  \* @type: $loopScenario;
  Scenario,
  \* @type: Int;
  Budget
\* @type: Set($loopScenario);
Scenarios == {"Good", "WrongEntry", "CircularComplete", "BackedgeClobber",
              "GuardBypass", "FlagClobber", "WrongPolarity", "SelectorClobber",
              "HiddenStore", "OpaqueCall", "UnknownMemory", "OmitExit",
              "OmitTarget", "MissingEntry", "HiddenEntrance", "LateEntrance",
              "CompletenessEpoch", "StaleEpoch", "RootInside", "SharedSelector",
              "UntrustedMemory", "WrongScope"}
ASSUME /\ Scenario \in Scenarios /\ Budget \in Nat
VARIABLES
  \* @type: $loopPhase;
  phase,
  \* @type: Int;
  checked,
  \* @type: Set($loopCheck);
  passed,
  \* @type: Int;
  readIndex,
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
  complete

\* Analysis-level authority for a finite local phase, not a machine ISA proof.
\* The nine nodes are pointer load/test/branch, selector load/compare/branch,
\* captured table load, target add, dispatch. Byte/BIL admission and concrete
\* hashes are external premises; mathematical words below have four bits.
Words == 0..15
Nodes == 0..8
Indices == 0..9
Base == 12
Modulus == 16
\* @type: Seq(Int);
Offsets == <<-3, -2, -1, 4, -3, -2, -1, -3, -2, -1>>
Target(i) == (Base + Offsets[i+1]) % Modulus
AllTargets == {Target(i): i \in Indices}
OffsetWords == {Offsets[i+1] % Modulus: i \in Indices}
\* @type: Set(Seq(Int));
Internal == {<<0,1>>, <<1,2>>, <<2,3>>, <<3,4>>, <<4,5>>,
             <<5,1>>, <<5,6>>, <<6,7>>, <<7,8>>, <<8,0>>}
\* @type: Set(Seq(Int));
Exits == {<<2,9>>, <<8,9>>, <<8,10>>, <<8,11>>}
\* @type: Set(Seq(Int));
RequiredEdges == Internal \cup Exits
\* @type: Set(Seq(Int));
ClaimedEdges ==
  IF Scenario = "OmitExit" THEN RequiredEdges \ {<<2,9>>}
  ELSE IF Scenario = "OmitTarget" THEN RequiredEdges \ {<<8,0>>}
  ELSE RequiredEdges
Changes == Scenario \in {"LateEntrance", "CompletenessEpoch", "StaleEpoch"}
\* @type: Int => Set(Seq(Int));
Entrances(rev) == {<<13,3>>} \cup
  (IF Scenario = "HiddenEntrance" \/ (Scenario = "LateEntrance" /\ rev > 0)
   THEN {<<14,6>>} ELSE {})
\* @type: Set(Seq(Int));
ClaimedEntrances == {<<13,3>>}
RootInside == Scenario = "RootInside"
AllowedSelector(n) ==
  IF Scenario = "SharedSelector" /\ n = 4 THEN {3}
  ELSE IF n = 6 THEN Indices
  ELSE IF n = 7 THEN OffsetWords
  ELSE IF n = 8 THEN AllTargets
  ELSE Words
\* @type: Int => Set($loopScalar);
Assertion(n) == {[b |-> Base, s |-> a, p |-> q]:
                  a \in AllowedSelector(n), q \in Words}
\* Every entrance corridor starts with arbitrary earlier values and an
\* original base-reset assignment. A claimed invariant cannot initialize itself.
EntryStates == {[b |-> (IF Scenario \in {"WrongEntry", "CircularComplete"}
                       THEN Base+1 ELSE Base), s |-> a, p |-> q]:
                  a \in Words, q \in Words}
EntranceHolds(rev) ==
  /\ Entrances(rev) = ClaimedEntrances
  /\ EntryStates \subseteq Assertion(3)
  /\ ~RootInside
\* Conditional guards use the original selector/flags from this transition.
\* Flag havoc means either structural successor may be taken.
\* @type: (Seq(Int), $loopScalar) => Bool;
Enabled(e, st) ==
  IF e[1] = 2 THEN IF e[2] = 3 THEN st.p # 0 ELSE st.p = 0
  ELSE IF e[1] = 5 THEN
    IF Scenario \in {"GuardBypass", "FlagClobber"} THEN TRUE
    ELSE IF Scenario = "WrongPolarity" THEN
      IF e[2] = 6 THEN st.s > 9 ELSE st.s <= 9
    ELSE IF e[2] = 6 THEN st.s <= 9 ELSE st.s > 9
  ELSE IF e[1] = 8 THEN st.s = e[2]
  ELSE TRUE
\* @type: (Seq(Int), $loopScalar) => Set($loopScalar);
Forward(e, st) ==
  IF ~Enabled(e, st) THEN {}
  ELSE IF e[1] = 0 THEN
    {[b |-> (IF Scenario = "BackedgeClobber" THEN (st.b+1)%Modulus ELSE st.b),
      s |-> st.s, p |-> fresh]: fresh \in Words}
  ELSE IF e[1] = 3 THEN
    \* Fresh universally quantified selector; never reuse an older iteration.
    {[b |-> st.b, s |-> fresh, p |-> st.p]: fresh \in Words}
  ELSE IF e[1] = 5 /\ e[2] = 6 /\ Scenario = "SelectorClobber" THEN
    {[b |-> st.b, s |-> (st.s+1)%Modulus, p |-> st.p]}
  ELSE IF e[1] = 6 THEN
    {[b |-> st.b, s |-> Offsets[st.s+1]%Modulus, p |-> st.p]}
  ELSE IF e[1] = 7 THEN
    {[b |-> st.b, s |-> (st.b+st.s)%Modulus, p |-> st.p]}
  ELSE {st}
Preservation == \A e \in Internal:
  \A st \in Assertion(e[1]): Forward(e, st) \subseteq Assertion(e[2])
DispatchDomain ==
  /\ AllowedSelector(6) = Indices
  /\ AllowedSelector(8) = AllTargets
  /\ {e[2]: e \in {x \in RequiredEdges: x[1] = 8}} = AllTargets
EffectsSafe == Scenario \notin {"HiddenStore", "OpaqueCall", "UnknownMemory"}
MemoryPremise == Scenario # "UntrustedMemory"
ScopeBound == Scenario # "WrongScope"
\* @type: Seq($loopCheck);
CheckNames == <<"entrance", "induction", "dispatch", "edges",
                "effects", "memory", "scope">>
\* @type: ($loopCheck, Int) => Bool;
CheckHolds(name, rev) ==
  CASE name = "entrance" -> EntranceHolds(rev)
    [] name = "induction" -> Preservation
    [] name = "dispatch" -> DispatchDomain
    [] name = "edges" -> ClaimedEdges = RequiredEdges
    [] name = "effects" -> EffectsSafe
    [] name = "memory" -> MemoryPremise
    [] name = "scope" -> ScopeBound
    [] OTHER -> FALSE
\* @type: Set($loopCheck);
AllChecks == {CheckNames[k]: k \in 1..Len(CheckNames)}
\* @type: Int => Set($loopCheck);
PassedAt(rev) == {name \in AllChecks: CheckHolds(name, rev)}
Readable == IF Scenario = "MissingEntry" THEN Indices \ {3} ELSE Indices
vars == <<phase, checked, passed, readIndex, inspected, targets, spent,
          revision, certificateRevision, complete>>
Init ==
  /\ phase = "check" /\ checked = 0 /\ passed = {}
  /\ readIndex = 0 /\ inspected = {} /\ targets = {} /\ spent = 0
  /\ revision = 0 /\ certificateRevision = 0 /\ complete = FALSE
Check ==
  /\ phase = "check" /\ checked < Len(CheckNames) /\ spent < Budget
  /\ LET name == CheckNames[checked+1] IN
       passed' = IF CheckHolds(name, revision) THEN passed \cup {name} ELSE passed
  /\ checked' = checked+1 /\ spent' = spent+1
  /\ UNCHANGED <<phase, readIndex, inspected, targets, revision,
                  certificateRevision, complete>>
BeginReads ==
  /\ phase = "check" /\ checked = Len(CheckNames)
  /\ phase' = "read"
  /\ UNCHANGED <<checked, passed, readIndex, inspected, targets, spent,
                  revision, certificateRevision, complete>>
Read ==
  /\ phase = "read" /\ readIndex \in Indices /\ spent < Budget
  /\ inspected' = inspected \cup {readIndex}
  /\ targets' = IF readIndex \in Readable
                 THEN targets \cup {Target(readIndex)} ELSE targets
  /\ readIndex' = readIndex+1 /\ spent' = spent+1
  /\ UNCHANGED <<phase, checked, passed, revision, certificateRevision, complete>>
BeginRevalidation ==
  /\ phase = "read" /\ readIndex = 10
  /\ phase' = "revalidate"
  /\ UNCHANGED <<checked, passed, readIndex, inspected, targets, spent,
                  revision, certificateRevision, complete>>
Discover ==
  /\ phase = "revalidate" /\ Changes /\ revision = 0
  /\ revision' = revision+1 /\ complete' = FALSE
  \* CompletenessEpoch changes no edge; it still invalidates the certificate.
  /\ UNCHANGED <<phase, checked, passed, readIndex, inspected, targets,
                  spent, certificateRevision>>
Recheck ==
  /\ phase = "revalidate" /\ certificateRevision # revision
  /\ Scenario # "StaleEpoch" /\ spent < Budget
  /\ passed' = PassedAt(revision) /\ certificateRevision' = revision
  /\ spent' = spent+1
  /\ UNCHANGED <<phase, checked, readIndex, inspected, targets, revision, complete>>
Publish ==
  /\ phase = "revalidate" /\ (~Changes \/ revision > 0)
  /\ (certificateRevision = revision \/ Scenario = "StaleEpoch")
  /\ complete' = (certificateRevision = revision /\ passed = AllChecks
                   /\ inspected = Indices /\ Indices \subseteq Readable)
  /\ phase' = "done"
  /\ UNCHANGED <<checked, passed, readIndex, inspected, targets, spent,
                  revision, certificateRevision>>
Stop ==
  /\ phase # "done" /\ spent = Budget
  /\ phase' = "done" /\ complete' = FALSE
  /\ UNCHANGED <<checked, passed, readIndex, inspected, targets, spent,
                  revision, certificateRevision>>
Next == Check \/ BeginReads \/ Read \/ BeginRevalidation \/ Discover \/ Recheck \/ Publish \/ Stop
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)
Safety ==
  /\ phase \in {"check", "read", "revalidate", "done"}
  /\ checked \in 0..Len(CheckNames) /\ passed \subseteq AllChecks
  /\ readIndex \in 0..10 /\ inspected \subseteq Indices
  /\ targets = {Target(i): i \in inspected \cap Readable}
  /\ spent >= 0 /\ spent <= Budget
  /\ revision \in 0..1 /\ certificateRevision \in 0..1
  /\ (complete => /\ phase = "done" /\ certificateRevision = revision
                   /\ PassedAt(revision) = AllChecks
                   /\ inspected = Indices /\ Indices \subseteq Readable
                   /\ AllTargets \subseteq targets)
Terminates == <> (phase = "done")
\* Configurations use ample budget or deliberate stops; this is a scenario
\* expectation, distinct from the implication-based safety contract above.
ExpectedOutcome == phase = "done" =>
  complete = (Scenario \in {"Good", "CompletenessEpoch"} /\ Budget >= 19)
=============================================================================
