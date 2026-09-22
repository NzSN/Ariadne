-------------------- MODULE AMD64UnsupportedChecks --------------------
EXTENDS AMD64Unsupported

RAX == [kind |-> "register", name |-> "rax"]
ZF == [kind |-> "flag", name |-> "zf"]
MEM == [kind |-> "memory", name |-> "[rdi]"]
RIP == [kind |-> "control", name |-> "rip"]
Facts == {
  [location |-> RAX, value |-> "1"],
  [location |-> ZF, value |-> "true"],
  [location |-> MEM, value |-> "42"],
  [location |-> RIP, value |-> "4096"]}
Before == [concreteFacts |-> Facts, undefinedLocations |-> {},
  observationGaps |-> {}]
Dependent == {RAX, ZF, MEM, RIP}
Untrusted == [mayAffect |-> {}, trusted |-> FALSE, dependencyClosed |-> FALSE]
Unsupported == UnsupportedFallback(Before, Dependent, Untrusted)
EmptyCaller == UnsupportedFallback(Before, {}, Untrusted)
Unknown == UnknownInstructionFallback(Before)
SelectiveSummary == [mayAffect |-> {RAX, ZF}, trusted |-> TRUE,
  dependencyClosed |-> TRUE]
Selective == UnsupportedFallback(Before, Dependent, SelectiveSummary)
\* The trusted summary omits RIP and the caller supplies no extras.  Control
\* must still be derived from Before and invalidated.
SelectiveOmittedControl == UnsupportedFallback(Before, {}, SelectiveSummary)
Capture == MissingCaptureFallback(Before, {MEM}, "memory:[rdi]")
Undefined == ArchitecturalUndefinedProjection(Before, {ZF}, {4100}, TRUE)
Contradictory == [concreteFacts |-> {
    [location |-> RAX, value |-> "1"], [location |-> RAX, value |-> "2"]},
  undefinedLocations |-> {}, observationGaps |-> {}]

UnsupportedChecks ==
  /\ KnowledgeWellFormed(Before)
  /\ KnowledgeLE(Unsupported.knowledge, Before)
  /\ Unsupported.knowledge.concreteFacts = {}
  /\ Unknown.knowledge.concreteFacts = {}
  /\ Unknown.knowledge.undefinedLocations = {}
  /\ Unknown.dependentLocations = Dependent
  /\ KnowledgeLE(Unknown.knowledge, Before)
  /\ KnowledgeWellFormed(Unknown.knowledge)
  /\ FallbackHasNoArchitecturalOutcome(Unknown)
  /\ Unknown.kind = "semantic-gap"
  /\ Unknown.reason = "unsupported-semantics"
  /\ EmptyCaller.knowledge.concreteFacts = {}
  /\ DependentFacts(Unsupported.knowledge, Dependent) = {}
  /\ FallbackHasNoArchitecturalOutcome(Unsupported)
  /\ Unsupported.kind = "semantic-gap"
  /\ Unsupported.reason = "unsupported-semantics"
  /\ ~TrustedSummaryValid(MutableUniverse(Before, {}), Untrusted)
  /\ EffectiveDependent(Before, {}, Untrusted) = Dependent
  /\ Selective.knowledge.concreteFacts =
       {[location |-> MEM, value |-> "42"]}
  /\ [location |-> RIP, value |-> "4096"] \notin
       Selective.knowledge.concreteFacts
  /\ SelectiveOmittedControl.knowledge.concreteFacts =
       {[location |-> MEM, value |-> "42"]}
  /\ [location |-> RIP, value |-> "4096"] \notin
       SelectiveOmittedControl.knowledge.concreteFacts
  /\ KnowledgeWellFormed(Unsupported.knowledge)
  /\ ~KnowledgeWellFormed(Contradictory)
  /\ Capture.kind = "evidence-gap" /\ Capture.reason = "missing-capture"
  /\ Capture.knowledge.concreteFacts = Facts \ {[location |-> MEM, value |-> "42"]}
  /\ "memory:[rdi]" \in Capture.knowledge.observationGaps
  /\ Undefined.kind = "supported-undefined"
  /\ ZF \in Undefined.knowledge.undefinedLocations
  /\ [location |-> ZF, value |-> "true"] \notin Undefined.knowledge.concreteFacts
  /\ Undefined.successfulTransition /\ Undefined.retired
  /\ Undefined.successors = {4100} /\ Undefined.successorsComplete

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ UnsupportedChecks
=======================================================================
