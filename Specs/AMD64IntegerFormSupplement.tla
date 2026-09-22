---------------- MODULE AMD64IntegerFormSupplement ----------------
EXTENDS Integers, Sequences

Forms == INSTANCE AMD64InstructionForms

\* Source-reviewed register projections of reg/mem rows.  The original form
\* ID is retained because register selection is the ModRM.mod=3 instance of
\* that row.  Memory instances remain pending the memory/atomic composition.
CommonPrefixes == {"rep", "repne", "operand-size", "address-size",
  "cs", "ss", "ds", "es", "fs", "gs", "rex"}
AllModes == {"real", "virtual8086", "protected", "compatibility", "long64"}
LegacyModes == {"real", "virtual8086", "protected", "compatibility"}

\* @type: Int => Set(Str);
PrefixesForWidth(width) == IF width \in {8, 64}
  THEN CommonPrefixes \cup {"rex-w"} ELSE CommonPrefixes
\* @type: Int => Str;
ViewName(width) == CASE width = 8 -> "low8" [] width = 16 -> "low16"
  [] width = 32 -> "low32" [] OTHER -> "full64"

\* @type: (Str, Int, Set(Str)) => $amd64FormConstraint;
UnaryRegisterForm(id, width, modes) == [
  formId |-> id, reviewLevel |-> "semantic-reviewed",
  constraintsKnown |-> TRUE, openObligations |-> {},
  allowedModes |-> modes, requiredFeatures |-> {},
  allowedOperandSizes |-> {width}, allowedAddressSizes |-> {16, 32, 64},
  allowedPrefixes |-> PrefixesForWidth(width) \cup {"lock"},
  requiredPrefixes |-> IF width = 64 THEN {"rex-w"} ELSE {},
  encodingFamilies |-> {"legacy"},
  operandKinds |-> <<{"gpr", "memory"}>>, operandWidths |-> <<{width}>>,
  operandEncodedWidths |-> <<{width}>>,
  operandSemanticWidths |-> <<{width}>>,
  operandExtensions |-> <<{"none"}>>,
  operandIdentities |-> <<{"*"}>>,
  operandAccesses |-> <<{"readWrite"}>>,
  operandEvaluationOrder |-> <<1>>,
  lockMemoryDestinationIndices |-> {1}, implementationStatus |-> "partial"]

\* The opcode-embedded 40+r/48+r rows are register-only and are unavailable
\* in long mode because those bytes are REX prefixes there.
\* @type: (Str, Int) => $amd64FormConstraint;
EmbeddedRegisterForm(id, width) ==
  [UnaryRegisterForm(id, width, LegacyModes) EXCEPT
    !.allowedPrefixes = PrefixesForWidth(width),
    !.operandKinds = <<{"gpr"}>>,
    !.lockMemoryDestinationIndices = {}]

UnaryWidthModes(width) == IF width = 64 THEN {"long64"} ELSE AllModes

Dec8 == UnaryRegisterForm("AMD64-F-0282", 8, UnaryWidthModes(8))
Dec16 == UnaryRegisterForm("AMD64-F-0283", 16, UnaryWidthModes(16))
Dec32 == UnaryRegisterForm("AMD64-F-0284", 32, UnaryWidthModes(32))
Dec64 == UnaryRegisterForm("AMD64-F-0285", 64, UnaryWidthModes(64))
Dec16Embedded == EmbeddedRegisterForm("AMD64-F-0286", 16)
Dec32Embedded == EmbeddedRegisterForm("AMD64-F-0287", 32)
Inc8 == UnaryRegisterForm("AMD64-F-0318", 8, UnaryWidthModes(8))
Inc16 == UnaryRegisterForm("AMD64-F-0319", 16, UnaryWidthModes(16))
Inc32 == UnaryRegisterForm("AMD64-F-0320", 32, UnaryWidthModes(32))
Inc64 == UnaryRegisterForm("AMD64-F-0321", 64, UnaryWidthModes(64))
Inc16Embedded == EmbeddedRegisterForm("AMD64-F-0322", 16)
Inc32Embedded == EmbeddedRegisterForm("AMD64-F-0323", 32)
Neg8 == UnaryRegisterForm("AMD64-F-0549", 8, UnaryWidthModes(8))
Neg16 == UnaryRegisterForm("AMD64-F-0550", 16, UnaryWidthModes(16))
Neg32 == UnaryRegisterForm("AMD64-F-0551", 32, UnaryWidthModes(32))
Neg64 == UnaryRegisterForm("AMD64-F-0552", 64, UnaryWidthModes(64))
Not8 == UnaryRegisterForm("AMD64-F-0557", 8, UnaryWidthModes(8))
Not16 == UnaryRegisterForm("AMD64-F-0558", 16, UnaryWidthModes(16))
Not32 == UnaryRegisterForm("AMD64-F-0559", 32, UnaryWidthModes(32))
Not64 == UnaryRegisterForm("AMD64-F-0560", 64, UnaryWidthModes(64))

SupplementalUnaryForms == {Dec8, Dec16, Dec32, Dec64, Dec16Embedded,
  Dec32Embedded, Inc8, Inc16, Inc32, Inc64, Inc16Embedded, Inc32Embedded,
  Neg8, Neg16, Neg32, Neg64, Not8, Not16, Not32, Not64}

SupplementalUnaryFormIds == {form.formId : form \in SupplementalUnaryForms}

\* @type: Str => $amd64FormConstraint;
SupplementalUnaryForm(formId) ==
  CHOOSE form \in SupplementalUnaryForms : form.formId = formId

DecFormIds == {"AMD64-F-0282", "AMD64-F-0283", "AMD64-F-0284",
  "AMD64-F-0285", "AMD64-F-0286", "AMD64-F-0287"}
IncFormIds == {"AMD64-F-0318", "AMD64-F-0319", "AMD64-F-0320",
  "AMD64-F-0321", "AMD64-F-0322", "AMD64-F-0323"}
NegFormIds == {"AMD64-F-0549", "AMD64-F-0550", "AMD64-F-0551",
  "AMD64-F-0552"}
NotFormIds == {"AMD64-F-0557", "AMD64-F-0558", "AMD64-F-0559",
  "AMD64-F-0560"}

\* @type: Str => Str;
SupplementalUnaryOperation(formId) ==
  CASE formId \in DecFormIds -> "dec"
    [] formId \in IncFormIds -> "inc"
    [] formId \in NegFormIds -> "neg"
    [] OTHER -> "not"

====================================================================
