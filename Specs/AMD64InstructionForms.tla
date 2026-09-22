---------------------- MODULE AMD64InstructionForms ----------------------
EXTENDS Integers, Sequences, FiniteSets

\* Normalized decoded-form and architectural-legality boundary.
\*
\* This module does not decode bytes and does not execute an instruction.  A
\* decoder supplies the encoding facts below; a reviewed form supplies the
\* architectural constraints.  Validation has three outcomes:
\*
\*   validated       the encoding is an architecturally admitted form;
\*   invalid         a reviewed architectural constraint is violated;
\*   undetermined    prose/encoding review is incomplete.
\*
\* An implementation missing an execution rule is independent of all three.
\* A valid-but-unimplemented instruction remains architecturally valid and
\* creates an implementation obligation at dispatch.
\*
\* Operand order is retained.  Later operand evaluation must use the ordered
\* operand records, not only the shape comparison performed here.  This is
\* required for cases such as a memory-source CMOV, whose memory access can
\* fault even when its condition is false.

Modes == {"real", "virtual8086", "protected", "compatibility", "long64"}
ReviewLevels == {"table-extracted", "table-reconciled", "semantic-reviewed"}
ImplementationStatuses == {"missing", "partial", "implemented"}
ResultKinds == {
  "validated", "architectural-invalid", "undefined-encoding",
  "normalization-error", "profile-error", "undetermined"
}

KnownPrefixes == {
  "lock", "rep", "repne", "operand-size", "address-size",
  "cs", "ss", "ds", "es", "fs", "gs", "rex", "rex-w"
}

\* @typeAlias: amd64FormConstraint = {
\*   formId: Str, reviewLevel: Str, constraintsKnown: Bool,
\*   openObligations: Set(Str), allowedModes: Set(Str),
\*   requiredFeatures: Set(Str), allowedOperandSizes: Set(Int),
\*   allowedAddressSizes: Set(Int), allowedPrefixes: Set(Str),
\*   requiredPrefixes: Set(Str), encodingFamilies: Set(Str),
\*   operandKinds: Seq(Set(Str)), operandWidths: Seq(Set(Int)),
\*   operandEncodedWidths: Seq(Set(Int)), operandSemanticWidths: Seq(Set(Int)),
\*   operandExtensions: Seq(Set(Str)),
\*   operandIdentities: Seq(Set(Str)),
\*   operandAccesses: Seq(Set(Str)), operandEvaluationOrder: Seq(Int),
\*   lockMemoryDestinationIndices: Set(Int),
\*   implementationStatus: Str};
\* `amd64DecodedOperandShape` is a legality projection. It retains canonical
\* identity but no immediate value or effective-address expression and therefore
\* is not an executable operand AST. The execution lane must define OperandRef
\* payloads and prove/project shape agreement before dispatch.
\* @typeAlias: amd64DecodedOperandShape = {
\*   kind: Str, width: Int, encodedWidth: Int, semanticWidth: Int,
\*   extension: Str, identity: Str, sourceText: Str, accessIntent: Str,
\*   evaluationOrder: Int};
\* @typeAlias: amd64DecodedFormShape = {
\*   formId: Str, mode: Str, operandSize: Int, addressSize: Int,
\*   prefixes: Set(Str), operands: Seq($amd64DecodedOperandShape), encodingFamily: Str,
\*   rexPresent: Bool, highByteRegister: Bool, prefixConflict: Bool};
\* @typeAlias: amd64FormProfile = {
\*   modes: Set(Str), features: Set(Str), operandSizes: Set(Int),
\*   addressSizes: Set(Int)};
\* @typeAlias: amd64LegalityResult = {
\*   kind: Str, reasons: Set(Str), obligations: Set(Str)};

\* @type: $amd64FormConstraint => Bool;
FormConstraintWellFormed(form) ==
  form.formId # "" /\
  form.reviewLevel \in ReviewLevels /\
  form.constraintsKnown \in BOOLEAN /\
  form.openObligations \subseteq STRING /\
  form.allowedModes \subseteq Modes /\
  form.requiredFeatures \subseteq STRING /\
  form.allowedOperandSizes \subseteq {8, 16, 32, 64} /\
  form.allowedAddressSizes \subseteq {16, 32, 64} /\
  form.allowedPrefixes \subseteq KnownPrefixes /\
  form.requiredPrefixes \subseteq KnownPrefixes /\
  form.requiredPrefixes \subseteq form.allowedPrefixes /\
  form.encodingFamilies \subseteq {"legacy", "vex", "xop"} /\
  Len(form.operandKinds) = Len(form.operandWidths) /\
  Len(form.operandKinds) = Len(form.operandEncodedWidths) /\
  Len(form.operandKinds) = Len(form.operandSemanticWidths) /\
  Len(form.operandKinds) = Len(form.operandExtensions) /\
  Len(form.operandKinds) = Len(form.operandIdentities) /\
  Len(form.operandKinds) = Len(form.operandAccesses) /\
  Len(form.operandKinds) = Len(form.operandEvaluationOrder) /\
  form.lockMemoryDestinationIndices \subseteq 1..Len(form.operandKinds) /\
  form.implementationStatus \in ImplementationStatuses

\* @type: $amd64DecodedFormShape => Bool;
DecodedFormWellFormed(decoded) ==
  decoded.formId # "" /\
  decoded.mode \in Modes /\
  decoded.operandSize \in {8, 16, 32, 64} /\
  decoded.addressSize \in {16, 32, 64} /\
  decoded.prefixes \subseteq KnownPrefixes /\
  decoded.encodingFamily \in {"legacy", "vex", "xop"} /\
  decoded.rexPresent \in BOOLEAN /\
  decoded.highByteRegister \in BOOLEAN /\
  decoded.prefixConflict \in BOOLEAN

\* @type: $amd64FormProfile => Bool;
ProfileWellFormed(profile) ==
  profile.modes \subseteq Modes /\
  profile.features \subseteq STRING /\
  profile.operandSizes \subseteq {8, 16, 32, 64} /\
  profile.addressSizes \subseteq {16, 32, 64}

\* Review readiness is semantic, not a synonym for finding a table row.
\* @type: $amd64FormConstraint => Bool;
ConstraintDataComplete(form) ==
  /\ form.allowedModes # {}
  /\ form.allowedOperandSizes # {}
  /\ form.allowedAddressSizes # {}
  /\ form.encodingFamilies # {}
  /\ \A index \in 1..Len(form.operandKinds) :
       form.operandKinds[index] # {} /\ form.operandWidths[index] # {} /\
       form.operandEncodedWidths[index] # {} /\
       form.operandSemanticWidths[index] # {} /\ form.operandExtensions[index] # {} /\
       form.operandIdentities[index] # {} /\ form.operandAccesses[index] # {}

\* @type: $amd64FormConstraint => Bool;
ReadyForLegality(form) ==
  form.reviewLevel = "semantic-reviewed" /\
  form.constraintsKnown /\
  form.openObligations = {} /\
  ConstraintDataComplete(form)

\* @type: (Str, Set(Str)) => $amd64LegalityResult;
Rejected(kind, reasons) == [kind |-> kind, reasons |-> reasons, obligations |-> {}]

\* @type: Set(Str) => $amd64LegalityResult;
Undetermined(obligations) ==
  [kind |-> "undetermined", reasons |-> {}, obligations |-> obligations]

Validated == [kind |-> "validated", reasons |-> {}, obligations |-> {}]

\* @type: ($amd64FormConstraint, $amd64DecodedFormShape) => Bool;
OperandShapesMatch(form, decoded) ==
  Len(form.operandKinds) = Len(decoded.operands) /\
  \A index \in 1..Len(decoded.operands) :
    decoded.operands[index].kind \in form.operandKinds[index] /\
    decoded.operands[index].width \in form.operandWidths[index] /\
    decoded.operands[index].encodedWidth \in form.operandEncodedWidths[index] /\
    decoded.operands[index].semanticWidth \in form.operandSemanticWidths[index] /\
    decoded.operands[index].extension \in form.operandExtensions[index] /\
    ("*" \in form.operandIdentities[index] \/
      decoded.operands[index].identity \in form.operandIdentities[index]) /\
    decoded.operands[index].accessIntent \in form.operandAccesses[index] /\
    decoded.operands[index].evaluationOrder = form.operandEvaluationOrder[index]

\* LOCK is admitted only when a reviewed form identifies a writable memory
\* destination and this particular decode resolves that union operand to
\* memory. A reg/mem table spelling alone never establishes LOCK legality.
\* @type: ($amd64FormConstraint, $amd64DecodedFormShape) => Bool;
LockUseLegal(form, decoded) ==
  "lock" \notin decoded.prefixes \/
  \E index \in form.lockMemoryDestinationIndices \cap 1..Len(decoded.operands) :
    decoded.operands[index].kind = "memory"

\* Redundant decoder facts are retained because each changes architectural
\* register selection. They must agree rather than being trusted piecemeal.
\* @type: $amd64DecodedFormShape => Bool;
DecoderEvidenceCoherent(decoded) ==
  /\ (("rex" \in decoded.prefixes \/ "rex-w" \in decoded.prefixes) =>
       decoded.mode = "long64")
  /\ IF decoded.encodingFamily = "legacy"
     THEN decoded.rexPresent =
       ("rex" \in decoded.prefixes \/ "rex-w" \in decoded.prefixes)
     ELSE ~decoded.rexPresent /\
       "rex" \notin decoded.prefixes /\ "rex-w" \notin decoded.prefixes
  /\ (decoded.highByteRegister =>
       decoded.encodingFamily = "legacy" /\ ~decoded.rexPresent)

\* Each reason below denotes a constraint backed by a semantic-reviewed form.
\* Multiple violations are returned together so a caller does not accidentally
\* depend on an arbitrary validator ordering.
\* @type: ($amd64FormConstraint, $amd64DecodedFormShape, $amd64FormProfile) => Set(Str);
InvalidReasons(form, decoded, profile) ==
  {reason \in {
    "form-id-mismatch", "incoherent-decoder-evidence",
    "mode-address-size-incompatible",
    "mode-not-implemented-by-profile",
    "mode-illegal-for-form", "missing-required-feature",
    "operand-size-not-implemented-by-profile", "operand-size-illegal-for-form",
    "address-size-not-implemented-by-profile", "address-size-illegal-for-form",
    "conflicting-prefixes", "prefix-illegal-for-form", "required-prefix-missing",
    "encoding-family-mismatch", "operand-shape-mismatch",
    "lock-requires-memory-destination", "rex-high-byte-conflict"
  } :
    CASE reason = "form-id-mismatch" -> decoded.formId # form.formId
      [] reason = "incoherent-decoder-evidence" -> ~DecoderEvidenceCoherent(decoded)
      [] reason = "mode-address-size-incompatible" ->
           (decoded.mode = "long64" /\ decoded.addressSize = 16) \/
           (decoded.mode # "long64" /\ decoded.addressSize = 64)
      [] reason = "mode-not-implemented-by-profile" -> decoded.mode \notin profile.modes
      [] reason = "mode-illegal-for-form" -> decoded.mode \notin form.allowedModes
      [] reason = "missing-required-feature" ->
           ~(form.requiredFeatures \subseteq profile.features)
      [] reason = "operand-size-not-implemented-by-profile" ->
           decoded.operandSize \notin profile.operandSizes
      [] reason = "operand-size-illegal-for-form" ->
           decoded.operandSize \notin form.allowedOperandSizes
      [] reason = "address-size-not-implemented-by-profile" ->
           decoded.addressSize \notin profile.addressSizes
      [] reason = "address-size-illegal-for-form" ->
           decoded.addressSize \notin form.allowedAddressSizes
      [] reason = "conflicting-prefixes" -> decoded.prefixConflict
      [] reason = "prefix-illegal-for-form" ->
           ~(decoded.prefixes \subseteq form.allowedPrefixes)
      [] reason = "required-prefix-missing" ->
           ~(form.requiredPrefixes \subseteq decoded.prefixes)
      [] reason = "encoding-family-mismatch" ->
           decoded.encodingFamily \notin form.encodingFamilies
      [] reason = "operand-shape-mismatch" -> ~OperandShapesMatch(form, decoded)
      [] reason = "lock-requires-memory-destination" -> ~LockUseLegal(form, decoded)
      [] reason = "rex-high-byte-conflict" ->
           decoded.rexPresent /\ decoded.highByteRegister
  }

NormalizationReasonNames == {
  "form-id-mismatch", "incoherent-decoder-evidence", "mode-address-size-incompatible",
  "required-prefix-missing", "encoding-family-mismatch",
  "operand-shape-mismatch", "rex-high-byte-conflict"
}
ProfileReasonNames == {
  "mode-not-implemented-by-profile", "operand-size-not-implemented-by-profile",
  "address-size-not-implemented-by-profile"
}
UndefinedReasonNames == {"conflicting-prefixes"}

\* Result kind is part of the API. In particular, downstream exception
\* delivery must never translate normalization/profile errors wholesale to
\* #UD. Only reviewed instruction semantics maps architectural-invalid reasons
\* to a specified fault.

\* @type: ($amd64FormConstraint, $amd64DecodedFormShape, $amd64FormProfile) => $amd64LegalityResult;
ValidateDecoded(form, decoded, profile) ==
  IF ~ReadyForLegality(form)
  THEN Undetermined(form.openObligations \cup {"semantic-form-review-incomplete"})
  ELSE LET reasons == InvalidReasons(form, decoded, profile)
           normalization == reasons \cap NormalizationReasonNames
           profileErrors == reasons \cap ProfileReasonNames
           undefined == reasons \cap UndefinedReasonNames
           architectural == reasons \ (NormalizationReasonNames \cup
             ProfileReasonNames \cup UndefinedReasonNames)
       IN CASE normalization # {} -> Rejected("normalization-error", normalization)
            [] profileErrors # {} -> Rejected("profile-error", profileErrors)
            [] undefined # {} -> Rejected("undefined-encoding", undefined)
            [] architectural # {} -> Rejected("architectural-invalid", architectural)
            [] OTHER -> Validated

\* This operator is intentionally separate from ValidateDecoded.  Dispatch may
\* use it only after architectural validation; changing it cannot change
\* whether an encoding is legal.
\* @type: $amd64FormConstraint => Str;
ImplementationDisposition(form) == form.implementationStatus

=============================================================================
