------------------------- MODULE AriadnePipeline -------------------------
EXTENDS AriadneMachineCommon

\* Small end-to-end instance: VA 4096 defines x, VA 4100 uses x.
\* Sparse VAs check that discovery uses explicit successors, not node indices.
\* Unlike the larger recovery fixtures, all phases fit within eight steps.
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
Instructions == [a \in {4096, 4100} |->
  [kind |-> IF a = 4096 THEN "ordinary" ELSE "return",
   fall |-> IF a = 4096 THEN {4100} ELSE {},
   targets |-> {}, complete |-> TRUE,
   uses |-> IF a = 4100 THEN {"x"} ELSE {},
   mustDefs |-> IF a = 4096 THEN {"x"} ELSE {},
   mayDefs |-> IF a = 4096 THEN {"x"} ELSE {}]]

Engine == INSTANCE Ariadne WITH
  SnapshotId <- "pipeline-snapshot",
  Addresses <- {4096, 4100}, Locations <- {"x"},
  EntryPoints <- {4096}, SliceSeeds <- {4100},
  InputKind <- "binary", Captured <- NoAddresses, FileBacked <- {4096, 4100},
  TrustedFallback <- NoAddresses, Decodable <- {4096, 4100}, Insn <- Instructions

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates
AddressContract ==
  /\ Engine!AddressIdentity(4096) = [snapshot |-> "pipeline-snapshot", va |-> 4096]
  /\ DOMAIN reaching = {4096, 4100}

FixtureResult == phase = "done" =>
  /\ decoded = {4096, 4100}
  /\ slice = {4096, 4100}
  /\ obligations = {}
  /\ reaching[4100] = {[loc |-> "x", site |-> 4096, origin |-> "instruction"]}
Safety == Engine!TypeOK /\ Engine!RecoveryInvariant /\ Engine!DefinitionInvariant
          /\ Engine!ResultInvariant /\ AddressContract /\ FixtureResult

\* Reachability witness: checking this deliberately false invariant should
\* yield a counterexample ending in done. It is not a safety requirement.
NotDone == phase # "done"

=============================================================================
