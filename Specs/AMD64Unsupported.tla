----------------------- MODULE AMD64Unsupported -----------------------
EXTENDS Integers, FiniteSets

\* Conservative analysis fallback for semantics outside the verified subset.
\* This module does not define an architectural instruction transition.

LocationKinds == {"register", "flag", "memory", "control"}
ProjectionKinds == {"semantic-gap", "evidence-gap", "supported-undefined"}
GapReasons == {"unsupported-semantics", "missing-capture"}

\* @typeAlias: unsupportedLocation = {kind: Str, name: Str};
\* @typeAlias: unsupportedFact = {location: $unsupportedLocation, value: Str};
\* @typeAlias: unsupportedKnowledge = {concreteFacts: Set($unsupportedFact),
\*   undefinedLocations: Set($unsupportedLocation), observationGaps: Set(Str)};
\* @typeAlias: unsupportedEffectSummary = {
\*   mayAffect: Set($unsupportedLocation), trusted: Bool,
\*   dependencyClosed: Bool};
\* @typeAlias: unsupportedProjection = {kind: Str, reason: Str,
\*   knowledge: $unsupportedKnowledge,
\*   dependentLocations: Set($unsupportedLocation), retired: Bool,
\*   faultKnown: Bool, faultVector: Int, successfulTransition: Bool,
\*   successors: Set(Int), successorsComplete: Bool};

\* @type: $unsupportedLocation => Bool;
LocationWellFormed(location) ==
  location.kind \in LocationKinds /\ location.name # ""

\* @type: $unsupportedKnowledge => Bool;
KnowledgeWellFormed(knowledge) ==
  /\ \A fact \in knowledge.concreteFacts :
       LocationWellFormed(fact.location) /\ fact.value # ""
  /\ \A left, right \in knowledge.concreteFacts :
       left.location = right.location => left = right
  /\ \A location \in knowledge.undefinedLocations : LocationWellFormed(location)
  /\ {fact.location : fact \in knowledge.concreteFacts}
       \cap knowledge.undefinedLocations = {}

\* Information order: every positive fact in `less` already exists in `more`.
\* Undefined/gap markers are obligations rather than positive concrete facts.
\* @type: ($unsupportedKnowledge, $unsupportedKnowledge) => Bool;
KnowledgeLE(less, more) == less.concreteFacts \subseteq more.concreteFacts

\* @type: ($unsupportedKnowledge, Set($unsupportedLocation))
\*   => Set($unsupportedFact);
DependentFacts(before, dependent) ==
  {fact \in before.concreteFacts : fact.location \in dependent}

\* @type: ($unsupportedKnowledge, Set($unsupportedLocation))
\*   => $unsupportedKnowledge;
RemoveDependent(before, dependent) ==
  [concreteFacts |-> before.concreteFacts \ DependentFacts(before, dependent),
   undefinedLocations |-> before.undefinedLocations \ dependent,
   observationGaps |-> before.observationGaps]

\* @type: (Set($unsupportedLocation), $unsupportedEffectSummary) => Bool;
TrustedSummaryValid(mutableLocations, summary) ==
  /\ summary.trusted /\ summary.dependencyClosed
  /\ summary.mayAffect \subseteq mutableLocations

\* @type: Set($unsupportedLocation) => Set($unsupportedLocation);
ControlLocations(mutableLocations) ==
  {location \in mutableLocations : location.kind = "control"}

\* @type: $unsupportedKnowledge => Set($unsupportedLocation);
ObservedLocations(before) ==
  {fact.location : fact \in before.concreteFacts} \cup before.undefinedLocations

\* @type: ($unsupportedKnowledge, Set($unsupportedLocation))
\*   => Set($unsupportedLocation);
MutableUniverse(before, callerExtra) == ObservedLocations(before) \cup callerExtra

\* No trusted summary means every mutable fact is dependent. Selective
\* summaries must be explicit and dependency-closed; control remains dependent
\* because fallback cannot certify a successor.
\* @type: ($unsupportedKnowledge, Set($unsupportedLocation),
\*   $unsupportedEffectSummary)
\*   => Set($unsupportedLocation);
EffectiveDependent(before, callerExtra, summary) ==
  LET mutableLocations == MutableUniverse(before, callerExtra)
  IN
  IF TrustedSummaryValid(mutableLocations, summary)
  THEN summary.mayAffect \cup ControlLocations(mutableLocations)
  ELSE mutableLocations

\* Expert-only selective helper.  A caller may use the selective branch only
\* when the effect summary comes from an external, trusted, dependency-closed
\* source.  Merely setting the Boolean fields is not profile acceptance.
\*
\* No successful no-op, retirement, fault, or successor is manufactured.
\* @type: ($unsupportedKnowledge, Set($unsupportedLocation),
\*   $unsupportedEffectSummary)
\*   => $unsupportedProjection;
UnsupportedFallback(before, callerExtra, summary) ==
  LET dependent == EffectiveDependent(before, callerExtra, summary)
  IN
  [kind |-> "semantic-gap", reason |-> "unsupported-semantics",
   knowledge |-> RemoveDependent(before, dependent),
   dependentLocations |-> dependent, retired |-> FALSE,
   faultKnown |-> FALSE, faultVector |-> 0,
   successfulTransition |-> FALSE,
   successors |-> {}, successorsComplete |-> FALSE]

\* Safe default for every decoded instruction outside the verified profile.
\* It deliberately accepts no caller-provided effect or trust claims.  Every
\* observed location is mutable, so all concrete and undefined facts are
\* discarded while prior evidence-gap obligations remain visible.
\* @type: $unsupportedKnowledge => $unsupportedProjection;
UnknownInstructionFallback(before) ==
  [kind |-> "semantic-gap", reason |-> "unsupported-semantics",
   knowledge |->
     [concreteFacts |-> {}, undefinedLocations |-> {},
      observationGaps |-> before.observationGaps],
   dependentLocations |-> ObservedLocations(before), retired |-> FALSE,
   faultKnown |-> FALSE, faultVector |-> 0,
   successfulTransition |-> FALSE,
   successors |-> {}, successorsComplete |-> FALSE]

\* Missing bytes/registers/system state are observed evidence gaps, not
\* unsupported instruction semantics and not architectural undefined values.
\* @type: ($unsupportedKnowledge, Set($unsupportedLocation), Str)
\*   => $unsupportedProjection;
MissingCaptureFallback(before, dependent, gap) ==
  LET reduced == RemoveDependent(before, dependent)
  IN [kind |-> "evidence-gap", reason |-> "missing-capture",
      knowledge |-> [reduced EXCEPT !.observationGaps = @ \cup {gap}],
      dependentLocations |-> dependent, retired |-> FALSE,
      faultKnown |-> FALSE, faultVector |-> 0,
      successfulTransition |-> FALSE,
      successors |-> {}, successorsComplete |-> FALSE]

\* Source-specified architectural undefined results are supported semantics.
\* They remove concrete values only at the named outputs and record those
\* locations as undefined. Supplied control facts remain explicit inputs.
\* @type: ($unsupportedKnowledge, Set($unsupportedLocation), Set(Int), Bool)
\*   => $unsupportedProjection;
ArchitecturalUndefinedProjection(before, undefined, successors, complete) ==
  [kind |-> "supported-undefined", reason |-> "",
   knowledge |->
     [concreteFacts |-> before.concreteFacts \ DependentFacts(before, undefined),
      undefinedLocations |-> before.undefinedLocations \cup undefined,
      observationGaps |-> before.observationGaps],
   dependentLocations |-> undefined, retired |-> TRUE,
   faultKnown |-> FALSE, faultVector |-> 0,
   successfulTransition |-> TRUE,
   successors |-> successors, successorsComplete |-> complete]

\* @type: $unsupportedProjection => Bool;
FallbackHasNoArchitecturalOutcome(projection) ==
  /\ ~projection.retired /\ ~projection.faultKnown
  /\ ~projection.successfulTransition
  /\ projection.successors = {} /\ ~projection.successorsComplete

=======================================================================
