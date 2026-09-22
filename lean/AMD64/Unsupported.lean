import Std

/-!
Conservative analysis projection for instructions whose architectural
semantics are not implemented by the current verified subset.

This is an analysis contract, not an instruction semantics and not an
architectural outcome. It cannot retire, fault, execute a no-op, or create a
successor. Architectural undefined values and missing capture are represented
by separate constructors.
-/

namespace AMD64.Unsupported

inductive LocationKind where
  | register | flag | memory | control
  deriving DecidableEq, Repr

structure Location where
  kind : LocationKind
  name : String
  deriving DecidableEq, Repr

structure ConcreteFact where
  location : Location
  value : String
  deriving DecidableEq, Repr

inductive ObservationGap where
  | missingInstructionBytes
  | missingMemoryBytes (location : Location)
  | missingRegisterCapture (location : Location)
  | missingSystemState (location : Location)
  deriving DecidableEq, Repr

structure Knowledge where
  concreteFacts : List ConcreteFact
  undefinedLocations : List Location
  observationGaps : List ObservationGap

def Knowledge.Valid (knowledge : Knowledge) : Prop :=
  knowledge.concreteFacts.Pairwise (fun left right => left.location ≠ right.location) ∧
  knowledge.undefinedLocations.Pairwise (· ≠ ·) ∧
  knowledge.observationGaps.Pairwise (· ≠ ·) ∧
  ∀ fact ∈ knowledge.concreteFacts, fact.location ∉ knowledge.undefinedLocations

/-- Information order: `less ≤ more` when every positive fact in `less` is
already present in `more`. Gap/undefined markers are obligations, not concrete
facts and do not make a projection more concrete. -/
def KnowledgeLE (less more : Knowledge) : Prop :=
  ∀ fact ∈ less.concreteFacts, fact ∈ more.concreteFacts

def locationDependent (dependent : List Location) (location : Location) : Bool :=
  dependent.contains location

def removeDependent (before : Knowledge) (dependent : List Location) : Knowledge := {
  concreteFacts := before.concreteFacts.filter
    (fun fact => !locationDependent dependent fact.location)
  undefinedLocations := before.undefinedLocations.filter
    (fun location => !locationDependent dependent location)
  observationGaps := before.observationGaps
}

structure EffectSummary where
  mayAffect : List Location
  trusted : Bool
  dependencyClosed : Bool
  deriving DecidableEq, Repr

def trustedSummaryValid (mutableLocations : List Location)
    (summary : EffectSummary) : Bool :=
  summary.trusted && summary.dependencyClosed &&
  summary.mayAffect.all mutableLocations.contains

def addUnique (locations : List Location) (location : Location) : List Location :=
  if location ∈ locations then locations else location :: locations

def observedLocations (before : Knowledge) : List Location :=
  let concrete := before.concreteFacts.foldl
    (fun current fact => addUnique current fact.location) []
  before.undefinedLocations.foldl addUnique concrete

/-- The caller may add locations absent from current knowledge, but cannot omit
locations already observed in concrete or undefined knowledge. -/
def mutableUniverse (before : Knowledge) (callerExtra : List Location) : List Location :=
  callerExtra.foldl addUnique (observedLocations before)

def controlLocations (mutableLocations : List Location) : List Location :=
  mutableLocations.filter (·.kind = .control)

/-- Without a trusted dependency-closed summary every mutable location is
invalidated. Even a trusted selective summary always includes control
locations, because this fallback cannot certify a successor or fallthrough. -/
def effectiveDependent (before : Knowledge) (callerExtra : List Location)
    (summary : EffectSummary) : List Location :=
  let mutableLocations := mutableUniverse before callerExtra
  if trustedSummaryValid mutableLocations summary then
    (controlLocations mutableLocations).foldl addUnique summary.mayAffect
  else mutableLocations

inductive GapReason where
  | unsupportedSemantics
  | missingCapture (gap : ObservationGap)
  deriving DecidableEq, Repr

inductive ProjectionKind where
  | semanticGap
  | evidenceGap
  | supportedArchitecturalUndefined
  deriving DecidableEq, Repr

structure Projection where
  kind : ProjectionKind
  reason : Option GapReason
  knowledge : Knowledge
  dependentLocations : List Location
  retired : Bool
  faultVector : Option Nat
  successfulTransition : Bool
  successors : List Nat
  successorsComplete : Bool

/-- Expert-only selective helper. The selective branch is meaningful only
when an external source has established that the summary is trusted and
dependency-closed. These Boolean fields alone do not establish profile
acceptance. Use `UnknownInstructionFallback` for the accepted safe default. -/
def UnsupportedFallback (before : Knowledge) (callerExtra : List Location)
    (summary : EffectSummary) : Projection :=
  let dependent := effectiveDependent before callerExtra summary
  {
  kind := .semanticGap
  reason := some .unsupportedSemantics
  knowledge := removeDependent before dependent
  dependentLocations := dependent
  retired := false
  faultVector := none
  successfulTransition := false
  successors := []
  successorsComplete := false
  }

/-- Safe default for a decoded instruction outside the verified profile.
It accepts no caller-supplied trust or effect claims. All observed locations
are mutable, so all concrete and undefined facts are discarded; existing
evidence-gap obligations remain visible. -/
def UnknownInstructionFallback (before : Knowledge) : Projection := {
  kind := .semanticGap
  reason := some .unsupportedSemantics
  knowledge := {
    concreteFacts := []
    undefinedLocations := []
    observationGaps := before.observationGaps }
  dependentLocations := observedLocations before
  retired := false
  faultVector := none
  successfulTransition := false
  successors := []
  successorsComplete := false
}

def MissingCaptureFallback (before : Knowledge) (dependent : List Location)
    (gap : ObservationGap) : Projection :=
  let reduced := removeDependent before dependent
  { kind := .evidenceGap
    reason := some (.missingCapture gap)
    knowledge := { reduced with observationGaps := gap :: reduced.observationGaps }
    dependentLocations := dependent
    retired := false
    faultVector := none
    successfulTransition := false
    successors := []
    successorsComplete := false }

/-- A source-specified undefined result is a supported semantic conclusion.
It removes concrete values at exactly the undefined locations and records those
locations as architecturally undefined. It is deliberately not a fallback. -/
def ArchitecturalUndefinedProjection (before : Knowledge)
    (undefined : List Location) (successors : List Nat)
    (successorsComplete : Bool) : Projection := {
  kind := .supportedArchitecturalUndefined
  reason := none
  knowledge := {
    concreteFacts := before.concreteFacts.filter
      (fun fact => !undefined.contains fact.location)
    undefinedLocations := undefined.foldl
      (fun current location => if location ∈ current then current else location :: current)
      before.undefinedLocations
    observationGaps := before.observationGaps }
  dependentLocations := undefined
  retired := true
  faultVector := none
  successfulTransition := true
  successors
  successorsComplete
}

theorem fallback_adds_no_concrete_facts (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary) :
    KnowledgeLE (UnsupportedFallback before mutableLocations summary).knowledge before := by
  intro fact member
  simp [UnsupportedFallback, removeDependent] at member
  exact member.1

theorem fallback_loses_dependent_facts (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary)
    (fact : ConcreteFact)
    (required : fact.location ∈ effectiveDependent before mutableLocations summary) :
    fact ∉ (UnsupportedFallback before mutableLocations summary).knowledge.concreteFacts := by
  simp [UnsupportedFallback, removeDependent, locationDependent, required]

theorem untrusted_fallback_loses_all_mutable_facts (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary)
    (untrusted : trustedSummaryValid (mutableUniverse before mutableLocations) summary = false)
    (fact : ConcreteFact)
    (mutable : fact.location ∈ mutableUniverse before mutableLocations) :
    fact ∉ (UnsupportedFallback before mutableLocations summary).knowledge.concreteFacts := by
  apply fallback_loses_dependent_facts
  simp [effectiveDependent, untrusted, mutable]

theorem fallback_preserves_validity (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary)
    (valid : before.Valid) :
    (UnsupportedFallback before mutableLocations summary).knowledge.Valid := by
  rcases valid with ⟨uniqueFacts, uniqueUndefined, uniqueGaps, disjoint⟩
  constructor
  · exact uniqueFacts.filter _
  constructor
  · exact uniqueUndefined.filter _
  constructor
  · exact uniqueGaps
  · intro fact factMember undefinedMember
    simp [UnsupportedFallback, removeDependent] at factMember undefinedMember
    exact disjoint fact factMember.1 undefinedMember.1

theorem fallback_has_no_architectural_outcome (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary) :
    (UnsupportedFallback before mutableLocations summary).retired = false ∧
    (UnsupportedFallback before mutableLocations summary).faultVector = none ∧
    (UnsupportedFallback before mutableLocations summary).successfulTransition = false := by
  exact ⟨rfl, rfl, rfl⟩

theorem fallback_control_is_unresolved (before : Knowledge)
    (mutableLocations : List Location) (summary : EffectSummary) :
    (UnsupportedFallback before mutableLocations summary).successors = [] ∧
    (UnsupportedFallback before mutableLocations summary).successorsComplete = false := by
  exact ⟨rfl, rfl⟩

theorem unknown_fallback_discards_all_concrete_facts (before : Knowledge) :
    (UnknownInstructionFallback before).knowledge.concreteFacts = [] := by
  rfl

theorem unknown_fallback_discards_all_undefined_locations (before : Knowledge) :
    (UnknownInstructionFallback before).knowledge.undefinedLocations = [] := by
  rfl

theorem unknown_fallback_tracks_all_observed_locations (before : Knowledge) :
    (UnknownInstructionFallback before).dependentLocations = observedLocations before := by
  rfl

theorem unknown_fallback_adds_no_concrete_facts (before : Knowledge) :
    KnowledgeLE (UnknownInstructionFallback before).knowledge before := by
  intro fact member
  simp [UnknownInstructionFallback] at member

theorem unknown_fallback_preserves_validity (before : Knowledge)
    (valid : before.Valid) :
    (UnknownInstructionFallback before).knowledge.Valid := by
  rcases valid with ⟨_, _, uniqueGaps, _⟩
  simpa [Knowledge.Valid, UnknownInstructionFallback] using uniqueGaps

theorem unknown_fallback_has_no_architectural_outcome (before : Knowledge) :
    (UnknownInstructionFallback before).retired = false ∧
    (UnknownInstructionFallback before).faultVector = none ∧
    (UnknownInstructionFallback before).successfulTransition = false := by
  exact ⟨rfl, rfl, rfl⟩

theorem unknown_fallback_control_is_unresolved (before : Knowledge) :
    (UnknownInstructionFallback before).successors = [] ∧
    (UnknownInstructionFallback before).successorsComplete = false := by
  exact ⟨rfl, rfl⟩

theorem undefined_is_not_unsupported (before : Knowledge)
    (undefined : List Location) (successors : List Nat) (complete : Bool) :
    (ArchitecturalUndefinedProjection before undefined successors complete).kind ≠
      .semanticGap := by
  intro contradiction
  cases contradiction

end AMD64.Unsupported
