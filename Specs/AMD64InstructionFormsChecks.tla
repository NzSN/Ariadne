------------------- MODULE AMD64InstructionFormsChecks -------------------
EXTENDS AMD64InstructionForms

VARIABLE
  \* @type: Bool;
  done

\* @type: Seq(Set(Str));
FixtureOperandKinds == <<{"gpr"}, {"gpr", "memory"}>>
\* @type: Seq(Set(Int));
FixtureOperandWidths == <<{64}, {64}>>
\* @type: Seq(Set(Int));
FixtureEncodedWidths == <<{64}, {64}>>
\* @type: Seq(Set(Int));
FixtureSemanticWidths == <<{64}, {64}>>
\* @type: Seq(Set(Str));
FixtureExtensions == <<{"none"}, {"none"}>>
\* @type: Seq(Set(Str));
FixtureOperandIdentities == <<{"gpr:0:full64"}, {"*"}>>
\* @type: Seq(Set(Str));
FixtureOperandAccesses == <<{"write"}, {"read"}>>
\* @type: Seq(Int);
FixtureOperandOrder == <<2, 1>>

CompleteForm(status) == [
  formId |-> "fixture-add-r64-rm64",
  reviewLevel |-> "semantic-reviewed",
  constraintsKnown |-> TRUE,
  openObligations |-> {},
  allowedModes |-> {"long64"},
  requiredFeatures |-> {},
  allowedOperandSizes |-> {64},
  allowedAddressSizes |-> {64},
  allowedPrefixes |-> {"fs", "gs", "address-size", "rex", "rex-w", "lock"},
  requiredPrefixes |-> {"rex-w"},
  encodingFamilies |-> {"legacy"},
  operandKinds |-> FixtureOperandKinds,
  operandWidths |-> FixtureOperandWidths,
  operandEncodedWidths |-> FixtureEncodedWidths,
  operandSemanticWidths |-> FixtureSemanticWidths,
  operandExtensions |-> FixtureExtensions,
  operandIdentities |-> FixtureOperandIdentities,
  operandAccesses |-> FixtureOperandAccesses,
  operandEvaluationOrder |-> FixtureOperandOrder,
  lockMemoryDestinationIndices |-> {},
  implementationStatus |-> status
]

PendingForm == [CompleteForm("missing") EXCEPT
  !.reviewLevel = "table-reconciled",
  !.constraintsKnown = FALSE,
  !.openObligations = {"review-mode-and-size-rules"}
]

Profile == [
  modes |-> {"long64"},
  features |-> {},
  operandSizes |-> {64},
  addressSizes |-> {32, 64}
]

\* @type: Seq({kind: Str, width: Int, encodedWidth: Int, semanticWidth: Int,
\*   extension: Str, identity: Str, sourceText: Str,
\*   accessIntent: Str, evaluationOrder: Int});
GoodOperands == <<
  [kind |-> "gpr", width |-> 64, encodedWidth |-> 64, semanticWidth |-> 64,
   extension |-> "none", identity |-> "gpr:0:full64", sourceText |-> "r64",
   accessIntent |-> "write", evaluationOrder |-> 2],
  [kind |-> "gpr", width |-> 64, encodedWidth |-> 64, semanticWidth |-> 64,
   extension |-> "none", identity |-> "gpr:1:full64", sourceText |-> "r64",
   accessIntent |-> "read", evaluationOrder |-> 1]
>>

GoodDecoded == [
  formId |-> "fixture-add-r64-rm64",
  mode |-> "long64",
  operandSize |-> 64,
  addressSize |-> 64,
  prefixes |-> {"rex-w"},
  operands |-> GoodOperands,
  encodingFamily |-> "legacy",
  rexPresent |-> TRUE,
  highByteRegister |-> FALSE,
  prefixConflict |-> FALSE
]

Init == done = FALSE
Next == done' = ~done
Spec == Init /\ [][Next]_done

Safety ==
  /\ FormConstraintWellFormed(CompleteForm("missing"))
  /\ DecodedFormWellFormed(GoodDecoded)
  /\ ProfileWellFormed(Profile)
  /\ ValidateDecoded(PendingForm, GoodDecoded, Profile).kind = "undetermined"
  /\ ValidateDecoded([CompleteForm("missing") EXCEPT !.allowedModes = {}],
       GoodDecoded, Profile).kind = "undetermined"
  /\ ValidateDecoded(CompleteForm("missing"), GoodDecoded, Profile).kind = "validated"
  /\ ValidateDecoded(CompleteForm("implemented"), GoodDecoded, Profile) =
       ValidateDecoded(CompleteForm("missing"), GoodDecoded, Profile)
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.mode = "protected", !.addressSize = 32], Profile).kind = "normalization-error"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.prefixes = {"rex-w", "rep"}], Profile).kind = "architectural-invalid"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.prefixes = {"rex-w", "lock"}], Profile).kind = "architectural-invalid"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.highByteRegister = TRUE], Profile).kind = "normalization-error"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT
         !.prefixes = {"rex-w", "lock"},
         !.operands = <<>>], Profile).kind = "normalization-error"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.rexPresent = FALSE], Profile).kind = "normalization-error"
  /\ ValidateDecoded(CompleteForm("missing"),
       [GoodDecoded EXCEPT !.operands[1].identity = "gpr:3:full64"],
       Profile).kind = "normalization-error"

=============================================================================
