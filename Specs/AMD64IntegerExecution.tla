------------------- MODULE AMD64IntegerExecution -------------------
EXTENDS AMD64ArchitecturalState, Integers, Sequences, FiniteSets

RegisterViews == INSTANCE AMD64RegisterViews
Operands == INSTANCE AMD64Operands
FormsCore == INSTANCE AMD64InstructionFormsCore
FormsSupplement == INSTANCE AMD64IntegerFormSupplement
Core == INSTANCE AMD64IntegerCore
Arithmetic == INSTANCE AMD64IntegerArithmetic
Adapter == INSTANCE AMD64IntegerStateAdapter

\* Conditional normalized-payload execution. A reviewed form-to-operation
\* dispatcher must first establish Operands!ValidateExecutable(...).kind =
\* "validated". Until that source-backed dispatcher is imported, `op` is an
\* explicit conditional semantic tag. Unsupported payloads produce a modeling-
\* unavailable result, never #UD, a no-op, or an impossible transition.
\* "body-applied" excludes RIP/fallthrough, fetch, trap delivery and asynchronous
\* events; the later execution boundary composes those before retirement.

IntegerOperations == {
  "mov", "add", "adc", "sub", "sbb", "cmp", "inc", "dec", "neg",
  "and", "or", "xor", "test", "not", "clc", "stc", "cmc", "cld", "std"
}
BinaryOperations == {"mov", "add", "adc", "sub", "sbb", "cmp",
                      "and", "or", "xor", "test"}
UnaryOperations == {"inc", "dec", "neg", "not"}
FlagOperations == {"clc", "stc", "cmc", "cld", "std"}

\* Local aliases repeat the operand composition types because Snowcat aliases
\* are not re-exported through INSTANCE.
\* @typeAlias: integerWord = Int -> Bool;
\* @typeAlias: integerFlags = Str -> Bool;
\* @typeAlias: integerFlagDomains = Str -> Set(Bool);
\* @typeAlias: executionOperandAddress = {basePresent: Bool, base: Int,
\*   baseExtended: Bool, indexPresent: Bool, index: Int, indexExtended: Bool,
\*   scale: Int, displacement: Int, displacementWidth: Int,
\*   segmentPresent: Bool, segment: Str, addressSize: Int, ripRelative: Bool};
\* @typeAlias: executionOperandRef = {kind: Str, width: Int,
\*   gprIndex: Int, gprView: Str, address: $executionOperandAddress,
\*   immediate: Seq(Bool), encodedWidth: Int, semanticWidth: Int,
\*   extension: Str, relative: Int, targetWidth: Int, segment: Str,
\*   vectorIndex: Int, vectorView: Str, mmxIndex: Int, maskIndex: Int,
\*   farSelector: Seq(Bool), farOffset: Seq(Bool), farOffsetWidth: Int,
\*   constant: Int};
\* @typeAlias: executionOperand = {ref: $executionOperandRef,
\*   sourceText: Str, accessIntent: Str, evaluationOrder: Int,
\*   registerExtension: Bool, byteCode4To7: Bool};
\* @typeAlias: executionInstruction = {formId: Str, operandSize: Int,
\*   addressSize: Int, prefixes: Set(Str), operands: Seq($executionOperand),
\*   implicitResources: Seq($executionOperandRef), encodingFamily: Str};
\* @typeAlias: integerExecutionOutcome = {kind: Str, stateWritten: Bool,
\*   state: $amd64CPUState, reason: Str};
\* @typeAlias: fallthroughEvidence = {beforeIP: $integerWord,
\*   instructionLength: Int, nextIP: $integerWord,
\*   fetchAcceptedAssumption: Bool,
\*   synchronousEventsResolvedAssumption: Bool,
\*   asynchronousEventsCheckedAssumption: Bool};
\* @typeAlias: fallthroughOutcome = {kind: Str, stateWritten: Bool,
\*   state: $amd64CPUState, reason: Str};
\* @typeAlias: executionCapabilities = {longMode: Bool, x87: Bool, mmx: Bool,
\*   sse: Bool, avx: Bool, avx512: Bool, mxcsrMisalignedMask: Bool};
\* @typeAlias: executionProfile = {capabilities: $executionCapabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};
\* @typeAlias: executionContext = {mode: Str, cpl: Int,
\*   x87Enabled: Bool, sseEnabled: Bool, avxEnabled: Bool, avx512Enabled: Bool};
\* @typeAlias: executionFormProfile = {modes: Set(Str), features: Set(Str),
\*   operandSizes: Set(Int), addressSizes: Set(Int)};
\* @typeAlias: executionFormConstraint = {
\*   formId: Str, reviewLevel: Str, constraintsKnown: Bool,
\*   openObligations: Set(Str), allowedModes: Set(Str),
\*   requiredFeatures: Set(Str), allowedOperandSizes: Set(Int),
\*   allowedAddressSizes: Set(Int), allowedPrefixes: Set(Str),
\*   requiredPrefixes: Set(Str), encodingFamilies: Set(Str),
\*   operandKinds: Seq(Set(Str)), operandWidths: Seq(Set(Int)),
\*   operandEncodedWidths: Seq(Set(Int)),
\*   operandSemanticWidths: Seq(Set(Int)), operandExtensions: Seq(Set(Str)),
\*   operandIdentities: Seq(Set(Str)), operandAccesses: Seq(Set(Str)),
\*   operandEvaluationOrder: Seq(Int), lockMemoryDestinationIndices: Set(Int),
\*   implementationStatus: Str};

\* @type: Str => Int;
ViewWidth(view) == Operands!GPRViewWidth(view)

\* @type: Str => {offset: Int, width: Int};
StorageView(view) ==
  CASE view = "low8" -> RegisterViews!Low8
    [] view = "high8" -> RegisterViews!High8
    [] view = "low16" -> RegisterViews!Low16
    [] view = "low32" -> RegisterViews!Low32
    [] OTHER -> RegisterViews!Full64

\* @type: (Str, $integerWord, $integerWord, Str) => $integerWord;
WriteViewForMode(mode, before, value, viewName) ==
  LET view == StorageView(viewName)
  IN IF mode = "long64" THEN RegisterViews!WriteView64(before, value, view)
     ELSE [bit \in 1..64 |->
       IF view.offset < bit /\ bit <= view.offset + view.width
       THEN value[bit - view.offset] ELSE before[bit]]

\* @type: ($amd64CPUState, $executionOperandRef) => $integerWord;
ReadGPR(state, ref) == RegisterViews!ReadView(state.gpr[ref.gprIndex], StorageView(ref.gprView))

\* @type: ($amd64CPUState, $executionOperandRef, $integerWord) => $amd64CPUState;
WriteGPR(state, ref, value) ==
  [state EXCEPT !.gpr[ref.gprIndex] =
    WriteViewForMode(state.execution.mode, @, value, ref.gprView)]

\* Volume 1 section 3.1.2.4 says the high 32 bits are architecturally
\* undefined after a 32-bit operand in compatibility or legacy mode.  Keep
\* WriteGPR as a deterministic witness for fixtures, but use this relation at
\* the instruction boundary so the witness is never mistaken for a guarantee.
\* @type: (Str, $integerWord, $integerWord, Str, $integerWord) => Bool;
WriteViewAllowed(mode, before, value, viewName, candidate) ==
  IF mode # "long64" /\ viewName = "low32"
  THEN /\ Core!WordWellFormed(candidate)
       /\ \A bit \in 1..32 : candidate[bit] = value[bit]
       \* candidate[33..64] is deliberately unconstrained.
  ELSE candidate = WriteViewForMode(mode, before, value, viewName)

\* @type: ($amd64CPUState, $executionOperandRef, $integerWord,
\*   $amd64CPUState) => Bool;
WriteGPRAllowed(state, ref, value, candidate) ==
  /\ WriteViewAllowed(state.execution.mode, state.gpr[ref.gprIndex], value,
                      ref.gprView, candidate.gpr[ref.gprIndex])
  /\ candidate = [state EXCEPT
       !.gpr[ref.gprIndex] = candidate.gpr[ref.gprIndex]]

\* @type: ($amd64CPUState, $integerFlags) => $amd64CPUState;
WriteStatus(state, status) ==
  [state EXCEPT !.rflags = Adapter!ApplyStatusFlags(@, status)]

\* @type: $executionOperandRef => $integerWord;
ImmediateValue(ref) ==
  [bit \in 1..64 |->
    IF bit <= ref.encodedWidth THEN ref.immediate[bit]
    ELSE IF bit <= ref.semanticWidth /\ ref.extension = "sign"
         THEN ref.immediate[ref.encodedWidth] ELSE FALSE]

\* @type: ($amd64CPUState, $executionOperandRef) => $integerWord;
ReadSource(state, ref) ==
  IF ref.kind = "gpr" THEN ReadGPR(state, ref) ELSE ImmediateValue(ref)

\* @type: ($executionInstruction, Int) => Bool;
BinaryPayloadSupported(instruction, width) ==
  /\ Len(instruction.operands) = 2
  /\ instruction.operands[1].ref.kind = "gpr"
  /\ instruction.operands[1].ref.gprView \in Operands!GPRViews
  /\ width = ViewWidth(instruction.operands[1].ref.gprView)
  /\ instruction.operandSize = width
  /\ instruction.operands[2].ref.kind \in {"gpr", "immediate"}
  /\ IF instruction.operands[2].ref.kind = "gpr"
     THEN ViewWidth(instruction.operands[2].ref.gprView) = width
     ELSE instruction.operands[2].ref.semanticWidth = width

\* @type: ($executionInstruction, Int) => Bool;
UnaryPayloadSupported(instruction, width) ==
  /\ Len(instruction.operands) = 1
  /\ instruction.operands[1].ref.kind = "gpr"
  /\ instruction.operands[1].ref.gprView \in Operands!GPRViews
  /\ width = ViewWidth(instruction.operands[1].ref.gprView)
  /\ instruction.operandSize = width

\* @type: (Str, $executionInstruction) => Bool;
PayloadSupported(op, instruction) ==
  IF op \in BinaryOperations THEN
    \E width \in Core!Widths : BinaryPayloadSupported(instruction, width)
  ELSE IF op \in UnaryOperations THEN
    \E width \in Core!Widths : UnaryPayloadSupported(instruction, width)
  ELSE op \in FlagOperations /\ Len(instruction.operands) = 0

\* @type: (Str, $executionInstruction) => Str;
UnavailableReason(op, instruction) ==
  IF \E index \in 1..Len(instruction.operands) :
       instruction.operands[index].ref.kind = "memory"
  THEN "memory-operand"
  ELSE IF instruction.operandSize \notin Core!Widths THEN "width-mismatch"
  ELSE "operand-shape"

\* @type: (Str, $integerWord, $integerWord, $integerFlags, Int)
\*   => {value: $integerWord, flags: $integerFlags};
ExactBinary(op, left, right, oldFlags, width) ==
  CASE op = "add" -> Arithmetic!AddResult(left, right, FALSE, width)
    [] op = "adc" -> Arithmetic!AddResult(left, right, oldFlags["cf"], width)
    [] op \in {"sub", "cmp"} -> Arithmetic!SubResult(left, right, FALSE, width)
    [] OTHER -> Arithmetic!SubResult(left, right, oldFlags["cf"], width)

\* @type: (Str, $integerWord, $integerFlags, Int)
\*   => {value: $integerWord, flags: $integerFlags};
ExactUnary(op, value, oldFlags, width) ==
  CASE op = "inc" -> Arithmetic!IncResult(value, width, oldFlags["cf"])
    [] op = "dec" -> Arithmetic!DecResult(value, width, oldFlags["cf"])
    [] OTHER -> Arithmetic!NegResult(value, width)

\* @type: Str => Str;
LogicOperation(op) == IF op \in {"and", "test"} THEN "and" ELSE op

\* Reads both operands from `before` before writing, so aliases and identical
\* source/destination registers use the architectural pre-state snapshot.
\* @type: (Str, $executionInstruction, $amd64CPUState, $amd64CPUState) => Bool;
BodyStep(op, instruction, before, after) ==
  IF op \in BinaryOperations THEN
    LET destination == instruction.operands[1].ref
        source == instruction.operands[2].ref
        width == ViewWidth(destination.gprView)
        left == ReadGPR(before, destination)
        right == ReadSource(before, source)
        oldFlags == Adapter!ProjectStatusFlags(before.rflags)
    IN CASE op = "mov" -> WriteGPRAllowed(before, destination, right, after)
         [] op \in {"add", "adc", "sub", "sbb", "cmp"} ->
              LET result == ExactBinary(op, left, right, oldFlags, width)
                  valued == [after EXCEPT !.rflags = before.rflags]
              IN /\ IF op = "cmp" THEN valued = before
                     ELSE WriteGPRAllowed(before, destination,
                                          result.value, valued)
                 /\ after = WriteStatus(valued, result.flags)
         [] OTHER ->
              LET logicOp == LogicOperation(op)
                  value == Core!LogicWord(logicOp, left, right, width)
                  valued == [after EXCEPT !.rflags = before.rflags]
              IN \E status \in [Core!Flags -> BOOLEAN] :
                   /\ IF op = "test" THEN valued = before
                      ELSE WriteGPRAllowed(before, destination, value, valued)
                   /\ Core!FlagsAllowed(status,
                        Arithmetic!LogicFlagDomains(logicOp, value, width))
                   /\ after = WriteStatus(valued, status)
  ELSE IF op \in UnaryOperations THEN
    LET destination == instruction.operands[1].ref
        width == ViewWidth(destination.gprView)
        value == ReadGPR(before, destination)
        oldFlags == Adapter!ProjectStatusFlags(before.rflags)
    IN IF op = "not" THEN
         WriteGPRAllowed(before, destination, Core!NotWord(value, width), after)
       ELSE LET result == ExactUnary(op, value, oldFlags, width)
                valued == [after EXCEPT !.rflags = before.rflags]
            IN /\ WriteGPRAllowed(before, destination, result.value, valued)
               /\ after = WriteStatus(valued, result.flags)
  ELSE CASE op = "clc" -> after = [before EXCEPT !.rflags.cf = FALSE]
         [] op = "stc" -> after = [before EXCEPT !.rflags.cf = TRUE]
         [] op = "cmc" -> after = [before EXCEPT !.rflags.cf = ~@]
         [] op = "cld" -> after = [before EXCEPT !.rflags.df = FALSE]
         [] OTHER -> after = [before EXCEPT !.rflags.df = TRUE]

\* @type: (Str, $executionInstruction, $amd64CPUState,
\*   $integerExecutionOutcome) => Bool;
ExecuteConditional(op, instruction, before, outcome) ==
  /\ op \in IntegerOperations
  /\ IF PayloadSupported(op, instruction)
     THEN /\ outcome.kind = "body-applied"
          /\ outcome.stateWritten
          /\ outcome.reason = ""
          /\ BodyStep(op, instruction, before, outcome.state)
     ELSE /\ outcome.kind = "modeling-unavailable"
          /\ ~outcome.stateWritten
          /\ outcome.reason = UnavailableReason(op, instruction)
          \* Placeholder is explicitly not an architectural transition.
          /\ outcome.state = before

AddFormIds == {"AMD64-F-0026", "AMD64-F-0027", "AMD64-F-0028", "AMD64-F-0029"}
AndFormIds == {"AMD64-F-0047", "AMD64-F-0048", "AMD64-F-0049", "AMD64-F-0050"}
CmpFormIds == {"AMD64-F-0240", "AMD64-F-0241", "AMD64-F-0242", "AMD64-F-0243"}
MovFormIds == {"AMD64-F-0496", "AMD64-F-0497", "AMD64-F-0498", "AMD64-F-0499",
              "AMD64-F-0503-R"}
OrFormIds == {"AMD64-F-0561", "AMD64-F-0562", "AMD64-F-0563", "AMD64-F-0564"}
SubFormIds == {"AMD64-F-0848", "AMD64-F-0849", "AMD64-F-0850", "AMD64-F-0851"}
TestFormIds == {"AMD64-F-0869", "AMD64-F-0870", "AMD64-F-0871", "AMD64-F-0872"}
XorFormIds == {"AMD64-F-0913", "AMD64-F-0914", "AMD64-F-0915", "AMD64-F-0916"}
ReviewedFormIds == AddFormIds \cup AndFormIds \cup CmpFormIds \cup MovFormIds
                   \cup OrFormIds \cup SubFormIds \cup TestFormIds \cup XorFormIds

\* @type: Str => Str;
ReviewedOperation(formId) ==
  CASE formId \in AddFormIds -> "add"
    [] formId \in AndFormIds -> "and"
    [] formId \in CmpFormIds -> "cmp"
    [] formId \in MovFormIds -> "mov"
    [] formId \in OrFormIds -> "or"
    [] formId \in SubFormIds -> "sub"
    [] formId \in TestFormIds -> "test"
    [] OTHER -> "xor"

\* @type: Str => $executionFormConstraint;
ReviewedForm(formId) ==
  CASE formId = "AMD64-F-0026" -> FormsCore!AddALImm8
    [] formId = "AMD64-F-0027" -> FormsCore!AddAXImm16
    [] formId = "AMD64-F-0028" -> FormsCore!AddEAXImm32
    [] formId = "AMD64-F-0029" -> FormsCore!AddRAXImm32
    [] formId = "AMD64-F-0047" -> FormsCore!AndALImm8
    [] formId = "AMD64-F-0048" -> FormsCore!AndAXImm16
    [] formId = "AMD64-F-0049" -> FormsCore!AndEAXImm32
    [] formId = "AMD64-F-0050" -> FormsCore!AndRAXImm32
    [] formId = "AMD64-F-0240" -> FormsCore!CmpALImm8
    [] formId = "AMD64-F-0241" -> FormsCore!CmpAXImm16
    [] formId = "AMD64-F-0242" -> FormsCore!CmpEAXImm32
    [] formId = "AMD64-F-0243" -> FormsCore!CmpRAXImm32
    [] formId = "AMD64-F-0496" -> FormsCore!MovReg8Imm8
    [] formId = "AMD64-F-0497" -> FormsCore!MovReg16Imm16
    [] formId = "AMD64-F-0498" -> FormsCore!MovReg32Imm32
    [] formId = "AMD64-F-0499" -> FormsCore!MovReg64Imm64
    [] formId = "AMD64-F-0503-R" -> FormsCore!MovReg64Imm32Sign
    [] formId = "AMD64-F-0561" -> FormsCore!OrALImm8
    [] formId = "AMD64-F-0562" -> FormsCore!OrAXImm16
    [] formId = "AMD64-F-0563" -> FormsCore!OrEAXImm32
    [] formId = "AMD64-F-0564" -> FormsCore!OrRAXImm32
    [] formId = "AMD64-F-0848" -> FormsCore!SubALImm8
    [] formId = "AMD64-F-0849" -> FormsCore!SubAXImm16
    [] formId = "AMD64-F-0850" -> FormsCore!SubEAXImm32
    [] formId = "AMD64-F-0851" -> FormsCore!SubRAXImm32
    [] formId = "AMD64-F-0869" -> FormsCore!TestALImm8
    [] formId = "AMD64-F-0870" -> FormsCore!TestAXImm16
    [] formId = "AMD64-F-0871" -> FormsCore!TestEAXImm32
    [] formId = "AMD64-F-0872" -> FormsCore!TestRAXImm32
    [] formId = "AMD64-F-0913" -> FormsCore!XorALImm8
    [] formId = "AMD64-F-0914" -> FormsCore!XorAXImm16
    [] formId = "AMD64-F-0915" -> FormsCore!XorEAXImm32
    [] OTHER -> FormsCore!XorRAXImm32

\* This is the first non-conditional dispatcher: form ID, reviewed constraint,
\* executable payload erasure, legality validation, and kernel step are one path.
\* A rejected validation is reported at the boundary and is not reclassified as
\* an architectural exception before the exception layer binds it.
\* @type: $amd64CPUState => $executionContext;
OperandContextFromState(state) == [
  mode |-> state.execution.mode,
  cpl |-> state.execution.cpl,
  x87Enabled |-> state.execution.features.x87Enabled,
  sseEnabled |-> state.execution.features.sseEnabled,
  avxEnabled |-> state.execution.features.avxEnabled,
  avx512Enabled |-> state.execution.features.avx512Enabled]

\* @type: ($executionProfile, $executionFormProfile, $executionInstruction,
\*   $amd64CPUState, $integerExecutionOutcome) => Bool;
ExecuteReviewed(architecture, formProfile, instruction, before, outcome) ==
  IF ~CPUStateWellFormed(architecture, before) THEN
    /\ outcome.kind = "validation-rejected"
    /\ ~outcome.stateWritten
    /\ outcome.reason = "invalid-before-state"
    /\ outcome.state = before
  ELSE IF instruction.formId \notin ReviewedFormIds THEN
    /\ outcome.kind = "modeling-unavailable"
    /\ ~outcome.stateWritten
    /\ outcome.reason = "form-binding-pending"
    /\ outcome.state = before
  ELSE LET legality == Operands!ValidateExecutable(
         architecture, OperandContextFromState(before),
         DefaultAddressWidth(before.segments, before.execution.mode),
         ReviewedForm(instruction.formId), formProfile, instruction)
       IN IF legality.kind = "validated"
          THEN ExecuteConditional(ReviewedOperation(instruction.formId),
                                 instruction, before, outcome)
          ELSE /\ outcome.kind = "validation-rejected"
               /\ ~outcome.stateWritten
               /\ outcome.reason = legality.kind
               /\ outcome.state = before

\* Register execution for the source-reviewed DEC/INC/NEG/NOT supplement.
\* A memory instance of the same source row remains modeling-unavailable until
\* address translation, faults and LOCK atomicity are composed.  It is not
\* reclassified as #UD or as a register-form validation failure.
\* @type: ($executionProfile, $executionFormProfile, $executionInstruction,
\*   $amd64CPUState, $integerExecutionOutcome) => Bool;
ExecuteSupplementalUnary(architecture, formProfile, instruction, before, outcome) ==
  IF ~CPUStateWellFormed(architecture, before) THEN
    /\ outcome.kind = "validation-rejected"
    /\ ~outcome.stateWritten
    /\ outcome.reason = "invalid-before-state"
    /\ outcome.state = before
  ELSE IF instruction.formId \notin FormsSupplement!SupplementalUnaryFormIds THEN
    /\ outcome.kind = "modeling-unavailable"
    /\ ~outcome.stateWritten
    /\ outcome.reason = "form-binding-pending"
    /\ outcome.state = before
  ELSE LET legality == Operands!ValidateExecutable(
         architecture, OperandContextFromState(before),
         DefaultAddressWidth(before.segments, before.execution.mode),
         FormsSupplement!SupplementalUnaryForm(instruction.formId),
         formProfile, instruction)
       IN IF legality.kind = "validated"
          THEN IF Len(instruction.operands) = 1 /\
                  instruction.operands[1].ref.kind = "memory"
               THEN /\ outcome.kind = "modeling-unavailable"
                    /\ ~outcome.stateWritten
                    /\ outcome.reason = "memory-operand"
                    /\ outcome.state = before
               ELSE ExecuteConditional(
                      FormsSupplement!SupplementalUnaryOperation(instruction.formId),
                      instruction, before, outcome)
          ELSE /\ outcome.kind = "validation-rejected"
               /\ ~outcome.stateWritten
               /\ outcome.reason = legality.kind
               /\ outcome.state = before

\* Applies the sequential next-IP only when fetch and event evidence is
\* explicitly present. These booleans are named assumptions: this adapter does
\* not check fetch or event delivery. The next-IP certificate is independently
\* tied to the body's preserved RIP and a decoded length in 1..15.
\* `fallthrough-applied` is still not named retirement.
\* @type: Int => $integerWord;
InstructionLengthWord(length) == Core!SmallNatWord(length)

\* @type: ($integerWord, Int) => $integerWord;
TruncateInstructionPointer(value, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN value[bit] ELSE FALSE]

\* @type: ($amd64CPUState, $fallthroughEvidence) => Bool;
FallthroughCertificateValid(after, evidence) ==
  /\ evidence.instructionLength \in 1..15
  /\ after.rip = evidence.beforeIP
  /\ evidence.nextIP = TruncateInstructionPointer(
       Core!AddWord(evidence.beforeIP,
         InstructionLengthWord(evidence.instructionLength), FALSE, 64),
       DefaultInstructionPointerWidth(after.segments, after.execution.mode))

\* @type: ($integerExecutionOutcome, $fallthroughEvidence,
\*   $fallthroughOutcome) => Bool;
ApplyFallthrough(body, evidence, result) ==
  IF body.kind = "body-applied" THEN
    IF ~FallthroughCertificateValid(body.state, evidence)
    THEN /\ result.kind = "modeling-unavailable"
         /\ ~result.stateWritten
         /\ result.state = body.state
         /\ result.reason = "fallthrough-certificate-invalid"
    ELSE IF evidence.fetchAcceptedAssumption /\
       evidence.synchronousEventsResolvedAssumption /\
       evidence.asynchronousEventsCheckedAssumption
    THEN /\ result.kind = "fallthrough-applied"
         /\ result.stateWritten
         /\ result.state = [body.state EXCEPT !.rip = evidence.nextIP]
         /\ result.reason = ""
    ELSE /\ result.kind = "modeling-unavailable"
         /\ ~result.stateWritten
         /\ result.state = body.state
         /\ result.reason = "fallthrough-evidence-pending"
  ELSE /\ result.kind = body.kind
       /\ result.stateWritten = body.stateWritten
       /\ result.state = body.state
       /\ result.reason = body.reason

=====================================================================
