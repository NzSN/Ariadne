-------------------- MODULE AMD64InstructionFormsCore --------------------
EXTENDS Integers, Sequences

Forms == INSTANCE AMD64InstructionForms

CommonPrefixes == {"rep", "repne", "operand-size", "address-size",
  "cs", "ss", "ds", "es", "fs", "gs", "rex"}
AllModes == {"real", "virtual8086", "protected", "compatibility", "long64"}

\* @type: Int => Set(Str);
PrefixesForWidth(width) == IF width \in {8, 64} THEN CommonPrefixes \cup {"rex-w"}
                           ELSE CommonPrefixes
\* @type: Int => Str;
AccumulatorIdentity(width) == CASE width = 8 -> "gpr:0:low8"
  [] width = 16 -> "gpr:0:low16" [] width = 32 -> "gpr:0:low32"
  [] OTHER -> "gpr:0:full64"
\* @type: Set(Str) => Seq(Set(Str));
Kinds(destinationKinds) == <<destinationKinds, {"immediate"}>>
\* @type: (Int, Int) => Seq(Set(Int));
Widths(width, encodedWidth) == <<{width}, {encodedWidth}>>
\* @type: (Int, Int) => Seq(Set(Int));
SemanticWidths(width, encodedWidth) == <<{width}, {width}>>
\* @type: Str => Seq(Set(Str));
Extensions(extension) == <<{"none"}, {extension}>>
\* @type: Str => Seq(Set(Str));
Identities(destination) == <<{destination}, {""}>>
\* @type: Str => Seq(Set(Str));
Accesses(destinationAccess) == <<{destinationAccess}, {"read"}>>
\* @type: Seq(Int);
OperandOrder == <<1, 2>>

\* @type: (Str, Int, Int, Str, Set(Str), Str, Str) => $amd64FormConstraint;
RegisterImmediateForm(formId, width, encodedWidth, extension,
                      destinationKinds, destinationIdentity, destinationAccess) == [
  formId |-> formId, reviewLevel |-> "semantic-reviewed",
  constraintsKnown |-> TRUE, openObligations |-> {},
  allowedModes |-> IF width = 64 THEN {"long64"} ELSE AllModes,
  requiredFeatures |-> {}, allowedOperandSizes |-> {width},
  allowedAddressSizes |-> {16, 32, 64},
  allowedPrefixes |-> PrefixesForWidth(width),
  requiredPrefixes |-> IF width = 64 THEN {"rex-w"} ELSE {},
  encodingFamilies |-> {"legacy"},
  operandKinds |-> Kinds(destinationKinds),
  operandWidths |-> Widths(width, encodedWidth),
  operandEncodedWidths |-> Widths(width, encodedWidth),
  operandSemanticWidths |-> SemanticWidths(width, encodedWidth),
  operandExtensions |-> Extensions(extension),
  operandIdentities |-> Identities(destinationIdentity),
  operandAccesses |-> Accesses(destinationAccess),
  operandEvaluationOrder |-> OperandOrder,
  lockMemoryDestinationIndices |-> {}, implementationStatus |-> "missing"]

AccumulatorForm(id, width, encodedWidth, extension, access) ==
  RegisterImmediateForm(id, width, encodedWidth, extension, {"gpr"},
    AccumulatorIdentity(width), access)
AnyGPRForm(id, width, encodedWidth, extension) ==
  RegisterImmediateForm(id, width, encodedWidth, extension, {"gpr"}, "*", "write")

AddALImm8 == AccumulatorForm("AMD64-F-0026", 8, 8, "none", "readWrite")
AddAXImm16 == AccumulatorForm("AMD64-F-0027", 16, 16, "none", "readWrite")
AddEAXImm32 == AccumulatorForm("AMD64-F-0028", 32, 32, "none", "readWrite")
AddRAXImm32 == AccumulatorForm("AMD64-F-0029", 64, 32, "sign", "readWrite")
AndALImm8 == AccumulatorForm("AMD64-F-0047", 8, 8, "none", "readWrite")
AndAXImm16 == AccumulatorForm("AMD64-F-0048", 16, 16, "none", "readWrite")
AndEAXImm32 == AccumulatorForm("AMD64-F-0049", 32, 32, "none", "readWrite")
AndRAXImm32 == AccumulatorForm("AMD64-F-0050", 64, 32, "sign", "readWrite")
CmpALImm8 == AccumulatorForm("AMD64-F-0240", 8, 8, "none", "read")
CmpAXImm16 == AccumulatorForm("AMD64-F-0241", 16, 16, "none", "read")
CmpEAXImm32 == AccumulatorForm("AMD64-F-0242", 32, 32, "none", "read")
CmpRAXImm32 == AccumulatorForm("AMD64-F-0243", 64, 32, "sign", "read")
OrALImm8 == AccumulatorForm("AMD64-F-0561", 8, 8, "none", "readWrite")
OrAXImm16 == AccumulatorForm("AMD64-F-0562", 16, 16, "none", "readWrite")
OrEAXImm32 == AccumulatorForm("AMD64-F-0563", 32, 32, "none", "readWrite")
OrRAXImm32 == AccumulatorForm("AMD64-F-0564", 64, 32, "sign", "readWrite")
SubALImm8 == AccumulatorForm("AMD64-F-0848", 8, 8, "none", "readWrite")
SubAXImm16 == AccumulatorForm("AMD64-F-0849", 16, 16, "none", "readWrite")
SubEAXImm32 == AccumulatorForm("AMD64-F-0850", 32, 32, "none", "readWrite")
SubRAXImm32 == AccumulatorForm("AMD64-F-0851", 64, 32, "sign", "readWrite")
TestALImm8 == AccumulatorForm("AMD64-F-0869", 8, 8, "none", "read")
TestAXImm16 == AccumulatorForm("AMD64-F-0870", 16, 16, "none", "read")
TestEAXImm32 == AccumulatorForm("AMD64-F-0871", 32, 32, "none", "read")
TestRAXImm32 == AccumulatorForm("AMD64-F-0872", 64, 32, "sign", "read")
XorALImm8 == AccumulatorForm("AMD64-F-0913", 8, 8, "none", "readWrite")
XorAXImm16 == AccumulatorForm("AMD64-F-0914", 16, 16, "none", "readWrite")
XorEAXImm32 == AccumulatorForm("AMD64-F-0915", 32, 32, "none", "readWrite")
XorRAXImm32 == AccumulatorForm("AMD64-F-0916", 64, 32, "sign", "readWrite")
MovReg8Imm8 == AnyGPRForm("AMD64-F-0496", 8, 8, "none")
MovReg16Imm16 == AnyGPRForm("AMD64-F-0497", 16, 16, "none")
MovReg32Imm32 == AnyGPRForm("AMD64-F-0498", 32, 32, "none")
MovReg64Imm64 == AnyGPRForm("AMD64-F-0499", 64, 64, "none")
MovReg64Imm32Sign == AnyGPRForm("AMD64-F-0503-R", 64, 32, "sign")

CoreForms == {AddALImm8, AddAXImm16, AddEAXImm32, AddRAXImm32,
  AndALImm8, AndAXImm16, AndEAXImm32, AndRAXImm32,
  CmpALImm8, CmpAXImm16, CmpEAXImm32, CmpRAXImm32,
  OrALImm8, OrAXImm16, OrEAXImm32, OrRAXImm32,
  SubALImm8, SubAXImm16, SubEAXImm32, SubRAXImm32,
  TestALImm8, TestAXImm16, TestEAXImm32, TestRAXImm32,
  XorALImm8, XorAXImm16, XorEAXImm32, XorRAXImm32,
  MovReg8Imm8, MovReg16Imm16, MovReg32Imm32, MovReg64Imm64,
  MovReg64Imm32Sign}

CoreByteForms == {AddALImm8, AndALImm8, CmpALImm8, MovReg8Imm8,
  OrALImm8, SubALImm8, TestALImm8, XorALImm8}

=============================================================================
