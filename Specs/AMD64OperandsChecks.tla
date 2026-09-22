----------------------- MODULE AMD64OperandsChecks -----------------------
EXTENDS AMD64Operands

VARIABLE
  \* @type: Bool;
  done

NoAddress == [basePresent |-> FALSE, base |-> 0, baseExtended |-> FALSE,
  indexPresent |-> FALSE, index |-> 0, indexExtended |-> FALSE, scale |-> 1,
  displacement |-> 0, displacementWidth |-> 0,
  segmentPresent |-> FALSE, segment |-> "ds", addressSize |-> 64,
  ripRelative |-> FALSE]

\* @type: Seq(Bool);
NoBits == <<>>
\* @type: Seq($amd64OperandRef);
NoOperandRefs == <<>>

\* @type: (Int, Str) => $amd64OperandRef;
GPRPayload(index, view) == [kind |-> "gpr", width |-> GPRViewWidth(view),
  gprIndex |-> index, gprView |-> view, address |-> NoAddress,
  immediate |-> NoBits, encodedWidth |-> 0, semanticWidth |-> 0,
  extension |-> "none", relative |-> 0, targetWidth |-> 0,
  segment |-> "ds", vectorIndex |-> 0, vectorView |-> "xmm",
  mmxIndex |-> 0, maskIndex |-> 0, farSelector |-> NoBits,
  farOffset |-> NoBits, farOffsetWidth |-> 0, constant |-> 0]

\* @type: (Int, Str) => $amd64ExecutableOperand;
ExecutableOperand(index, view) == [ref |-> GPRPayload(index, view),
  sourceText |-> "fixture", accessIntent |-> "readWrite", evaluationOrder |-> 1,
  registerExtension |-> index >= 8,
  byteCode4To7 |-> view = "high8" \/ (index % 8) >= 4]

\* @type: (Int, Str, Set(Str)) => $amd64ExecutableInstruction;
Instruction(index, view, prefixes) == [formId |-> "fixture-fixed-al",
  operandSize |-> 8, addressSize |-> 64, prefixes |-> prefixes,
  operands |-> <<ExecutableOperand(index, view)>>, implicitResources |-> NoOperandRefs,
  encodingFamily |-> "legacy"]

Context == [mode |-> "long64", cpl |-> 3, x87Enabled |-> TRUE,
  sseEnabled |-> TRUE, avxEnabled |-> TRUE, avx512Enabled |-> TRUE]
Capabilities == [longMode |-> TRUE, x87 |-> TRUE, mmx |-> TRUE,
  sse |-> TRUE, avx |-> TRUE, avx512 |-> TRUE, mxcsrMisalignedMask |-> TRUE]
Architecture == [capabilities |-> Capabilities,
  physicalAddressBits |-> 52, linearAddressBits |-> 48]
FormProfile == [modes |-> {"long64"}, features |-> {},
  operandSizes |-> {8}, addressSizes |-> {64}]

\* @type: Seq(Set(Str));
FixedKinds == <<{"gpr"}>>
\* @type: Seq(Set(Int));
FixedWidths == <<{8}>>
\* @type: Seq(Set(Int));
FixedEncodedWidths == <<{8}>>
\* @type: Seq(Set(Int));
FixedSemanticWidths == <<{8}>>
\* @type: Seq(Set(Str));
FixedExtensions == <<{"none"}>>
\* @type: Seq(Set(Str));
FixedALIdentities == <<{"gpr:0:low8"}>>
\* @type: Seq(Set(Str));
FixedAHIdentities == <<{"gpr:0:high8"}>>
\* @type: Seq(Set(Str));
FixedAccesses == <<{"readWrite"}>>
\* @type: Seq(Int);
FixedOrder == <<1>>

FixedALForm == [formId |-> "fixture-fixed-al",
  reviewLevel |-> "semantic-reviewed", constraintsKnown |-> TRUE,
  openObligations |-> {}, allowedModes |-> {"long64"},
  requiredFeatures |-> {}, allowedOperandSizes |-> {8},
  allowedAddressSizes |-> {64}, allowedPrefixes |-> {"rex"},
  requiredPrefixes |-> {}, encodingFamilies |-> {"legacy"},
  operandKinds |-> FixedKinds, operandWidths |-> FixedWidths,
  operandEncodedWidths |-> FixedEncodedWidths,
  operandSemanticWidths |-> FixedSemanticWidths,
  operandExtensions |-> FixedExtensions,
  operandIdentities |-> FixedALIdentities,
  operandAccesses |-> FixedAccesses, operandEvaluationOrder |-> FixedOrder,
  lockMemoryDestinationIndices |-> {}, implementationStatus |-> "missing"]

Init == done = FALSE
Next == done' = ~done
Spec == Init /\ [][Next]_done

ValidAL == ValidateExecutable(Architecture, Context, 64, FixedALForm, FormProfile,
  Instruction(0, "low8", {})).kind = "validated"
RejectBL == ValidateExecutable(Architecture, Context, 64, FixedALForm, FormProfile,
  Instruction(3, "low8", {})).kind = "normalization-error"
RejectWidth == ValidateExecutable(Architecture, Context, 64, FixedALForm, FormProfile,
  Instruction(0, "low32", {})).kind = "normalization-error"
RejectHigh8Rex == ValidateExecutable(Architecture, Context, 64,
  [FixedALForm EXCEPT !.operandIdentities = FixedAHIdentities],
  FormProfile, Instruction(0, "high8", {"rex"})).kind = "normalization-error"
EraseIdentity == EraseInstruction(Context,
  Instruction(0, "low8", {})).operands[1].identity = "gpr:0:low8"

VectorInstruction(index, family, prefixes) ==
  [Instruction(0, "low8", prefixes) EXCEPT
    !.encodingFamily = family,
    !.operands[1].ref.kind = "xmm",
    !.operands[1].ref.vectorIndex = index,
    !.operands[1].registerExtension = index >= 8,
    !.operands[1].byteCode4To7 = FALSE]
VectorEncodingChecks ==
  /\ OperandEncodingWellFormed(Context, VectorInstruction(8, "legacy", {"rex"}), 1)
  /\ ~OperandEncodingWellFormed(Context, VectorInstruction(8, "legacy", {}), 1)
  /\ OperandEncodingWellFormed(Context, VectorInstruction(8, "vex", {}), 1)
  /\ ~OperandEncodingWellFormed(Context, VectorInstruction(16, "vex", {}), 1)
Safety == ValidAL /\ RejectBL /\ RejectWidth /\ RejectHigh8Rex /\ EraseIdentity
  /\ VectorEncodingChecks

=============================================================================
