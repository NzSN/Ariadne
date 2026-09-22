--------------- MODULE AMD64IntegerExecutionChecks ---------------
EXTENDS AMD64IntegerExecution

VARIABLE
  \* @type: Bool;
  checked

ZeroBits(width) == [bit \in 1..width |-> FALSE]
OneBits(width) == [bit \in 1..width |-> TRUE]
Word(bits) == [bit \in 1..64 |-> bit \in bits]

Capabilities == [longMode |-> TRUE, x87 |-> TRUE, mmx |-> TRUE,
  sse |-> TRUE, avx |-> TRUE, avx512 |-> TRUE, mxcsrMisalignedMask |-> TRUE]
Architecture == [capabilities |-> Capabilities, physicalAddressBits |-> 52,
  linearAddressBits |-> 48]
OperandContext == [mode |-> "long64", cpl |-> 0, x87Enabled |-> TRUE,
  sseEnabled |-> TRUE, avxEnabled |-> TRUE, avx512Enabled |-> TRUE]
FormProfile == [modes |-> {"long64"}, features |-> {},
  operandSizes |-> {8, 16, 32, 64}, addressSizes |-> {64}]

Segment(long) == [selector |-> ZeroBits(16), base |-> ZeroBits(64),
  limit |-> OneBits(32), present |-> TRUE, dpl |-> 0, readable |-> TRUE,
  writable |-> TRUE, executable |-> TRUE, conforming |-> FALSE,
  expandDown |-> FALSE, defaultBig |-> FALSE, longMode |-> long,
  unusable |-> FALSE]
Segments == [cs |-> Segment(TRUE), ss |-> Segment(FALSE),
  ds |-> Segment(FALSE), es |-> Segment(FALSE),
  fs |-> Segment(FALSE), gs |-> Segment(FALSE)]
RFlags == [cf |-> FALSE, fixed1 |-> TRUE, pf |-> FALSE,
  reserved3 |-> FALSE, af |-> FALSE, reserved5 |-> FALSE,
  zf |-> FALSE, sf |-> FALSE, tf |-> FALSE, interruptEnable |-> TRUE,
  df |-> FALSE, of |-> FALSE, iopl |-> ZeroBits(2), nestedTask |-> FALSE,
  reserved15 |-> FALSE, resume |-> FALSE, virtual8086 |-> FALSE,
  ac |-> FALSE, virtualInterrupt |-> FALSE,
  virtualInterruptPending |-> FALSE, id |-> FALSE,
  reservedHigh |-> ZeroBits(42)]
X87Status == [invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  stackFault |-> FALSE, errorSummary |-> FALSE, c0 |-> FALSE,
  c1 |-> FALSE, c2 |-> FALSE, top |-> 0, c3 |-> FALSE, busy |-> FALSE]
X87Control == [invalidMask |-> TRUE, denormalMask |-> TRUE,
  zeroDivideMask |-> TRUE, overflowMask |-> TRUE, underflowMask |-> TRUE,
  precisionMask |-> TRUE, reserved6 |-> TRUE, reserved7 |-> FALSE,
  precisionControl |-> "bits64", roundingControl |-> "nearest",
  infinityControl |-> FALSE, reservedHigh |-> ZeroBits(3)]
X87Pointer == [kind |-> "offset64", selector |-> ZeroBits(16),
  offset64 |-> ZeroBits(64), offset32 |-> ZeroBits(32),
  linear32 |-> ZeroBits(32)]
X87 == [physical |-> [r \in 0..7 |-> ZeroBits(80)],
  tags |-> [r \in 0..7 |-> "empty"], status |-> X87Status,
  control |-> X87Control, lastInstruction |-> X87Pointer,
  lastData |-> X87Pointer, lastOpcode |-> ZeroBits(11)]
MXCSR == [invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  denormalsAreZero |-> FALSE, invalidMask |-> TRUE, denormalMask |-> TRUE,
  zeroDivideMask |-> TRUE, overflowMask |-> TRUE, underflowMask |-> TRUE,
  precisionMask |-> TRUE, roundingControl |-> "nearest", flushToZero |-> FALSE,
  reserved16 |-> FALSE, misalignedMask |-> FALSE,
  reservedHigh |-> ZeroBits(14)]

\* @type: $integerWord => $amd64CPUState;
StateWithRAX(value) == [gpr |-> [r \in 0..15 |-> IF r = 0 THEN value ELSE ZeroBits(64)],
  rip |-> ZeroBits(64), rflags |-> RFlags, segments |-> Segments, x87 |-> X87,
  vectors |-> [r \in 0..31 |-> ZeroBits(512)],
  kMask |-> [r \in 0..7 |-> ZeroBits(64)], mxcsr |-> MXCSR,
  execution |-> [mode |-> "long64", cpl |-> 0,
    features |-> [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
      avxEnabled |-> TRUE, avx512Enabled |-> TRUE]]]

NoAddress == [basePresent |-> FALSE, base |-> 0, baseExtended |-> FALSE,
  indexPresent |-> FALSE, index |-> 0, indexExtended |-> FALSE, scale |-> 1,
  displacement |-> 0, displacementWidth |-> 0,
  segmentPresent |-> FALSE, segment |-> "ds", addressSize |-> 64,
  ripRelative |-> FALSE]
NoBits == <<>>
NoRefs == <<>>

\* @type: (Int, Str) => $executionOperandRef;
GPRRef(index, view) == [kind |-> "gpr", width |-> ViewWidth(view),
  gprIndex |-> index, gprView |-> view, address |-> NoAddress,
  immediate |-> NoBits, encodedWidth |-> 0, semanticWidth |-> 0,
  extension |-> "none", relative |-> 0, targetWidth |-> 0,
  segment |-> "ds", vectorIndex |-> 0, vectorView |-> "xmm",
  mmxIndex |-> 0, maskIndex |-> 0, farSelector |-> NoBits,
  farOffset |-> NoBits, farOffsetWidth |-> 0, constant |-> 0]

\* @type: (Seq(Bool), Int, Int, Str) => $executionOperandRef;
ImmediateSized(bits, encodedWidth, semanticWidth, extension) == [kind |-> "immediate",
  width |-> encodedWidth,
  gprIndex |-> 0, gprView |-> "low8", address |-> NoAddress,
  immediate |-> bits, encodedWidth |-> encodedWidth, semanticWidth |-> semanticWidth,
  extension |-> extension, relative |-> 0, targetWidth |-> 0,
  segment |-> "ds", vectorIndex |-> 0, vectorView |-> "xmm",
  mmxIndex |-> 0, maskIndex |-> 0, farSelector |-> NoBits,
  farOffset |-> NoBits, farOffsetWidth |-> 0, constant |-> 0]

\* @type: Seq(Bool) => $executionOperandRef;
ImmediateRef(bits) == ImmediateSized(bits, 8, 8, "none")

MemoryRef == [GPRRef(0, "low8") EXCEPT !.kind = "memory"]

\* @type: ($executionOperandRef, Str, Int) => $executionOperand;
Operand(ref, access, order) == [ref |-> ref, sourceText |-> "fixture",
  accessIntent |-> access, evaluationOrder |-> order,
  registerExtension |-> ref.kind = "gpr" /\ ref.gprIndex >= 8,
  byteCode4To7 |-> ref.kind = "gpr" /\
    (ref.gprView = "high8" \/ (ref.gprIndex % 8) >= 4)]

\* @type: (Str, $executionOperandRef, Str, $executionOperandRef, Set(Str))
\*   => $executionInstruction;
Instruction(formId, destination, destinationAccess, source, prefixes) == [
  formId |-> formId, operandSize |-> 8, addressSize |-> 64,
  prefixes |-> prefixes,
  operands |-> <<Operand(destination, destinationAccess, 1),
                Operand(source, "read", 2)>>,
  implicitResources |-> NoRefs, encodingFamily |-> "legacy"]

\* @type: (Str, Int, $executionOperandRef, $executionOperandRef)
\*   => $executionInstruction;
RegisterInstruction(formId, width, destination, source) == [
  formId |-> formId, operandSize |-> width, addressSize |-> 64, prefixes |-> {},
  operands |-> <<Operand(destination, "readWrite", 1),
                Operand(source, "read", 2)>>,
  implicitResources |-> NoRefs, encodingFamily |-> "legacy"]

\* @type: (Str, Int, $executionOperandRef, Str, $executionOperandRef, Set(Str))
\*   => $executionInstruction;
SizedInstruction(formId, width, destination, destinationAccess, source, prefixes) == [
  formId |-> formId, operandSize |-> width, addressSize |-> 64,
  prefixes |-> prefixes,
  operands |-> <<Operand(destination, destinationAccess, 1), Operand(source, "read", 2)>>,
  implicitResources |-> NoRefs, encodingFamily |-> "legacy"]

\* @type: (Str, Int, $executionOperandRef, Set(Str)) => $executionInstruction;
UnaryInstruction(formId, width, destination, prefixes) == [
  formId |-> formId, operandSize |-> width, addressSize |-> 64,
  prefixes |-> prefixes, operands |-> <<Operand(destination, "readWrite", 1)>>,
  implicitResources |-> NoRefs, encodingFamily |-> "legacy"]

RECURSIVE ImmediateBits(_, _)
\* @type: (Set(Int), Int) => Seq(Bool);
ImmediateBits(setBits, count) ==
  IF count = 0 THEN <<>>
  ELSE Append(ImmediateBits(setBits, count - 1), count \in setBits)

\* @type: Seq(Bool);
ByteOne == <<TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE>>
\* @type: Seq(Bool);
Byte12 == <<FALSE, TRUE, FALSE, FALSE, TRUE, FALSE, FALSE, FALSE>>
AL == GPRRef(0, "low8")
AH == GPRRef(0, "high8")
BL == GPRRef(3, "low8")
ImmOne == ImmediateRef(ByteOne)
Imm12 == ImmediateRef(Byte12)

AddInstruction == Instruction("AMD64-F-0026", AL, "readWrite", ImmOne, {})
AndInstruction == Instruction("AMD64-F-0047", AL, "readWrite", ImmOne, {})
CmpInstruction == Instruction("AMD64-F-0240", AL, "read", ImmOne, {})
MovAHInstruction == Instruction("AMD64-F-0496", AH, "write", Imm12, {})
OrInstruction == Instruction("AMD64-F-0561", AL, "readWrite", ImmOne, {})
SubInstruction == Instruction("AMD64-F-0848", AL, "readWrite", ImmOne, {})
TestInstruction == Instruction("AMD64-F-0869", AL, "read", ImmOne, {})
XorInstruction == Instruction("AMD64-F-0913", AL, "readWrite", ImmOne, {})
Add16Reviewed == SizedInstruction("AMD64-F-0027", 16, GPRRef(0, "low16"),
  "readWrite", ImmediateSized(ImmediateBits({1}, 16), 16, 16, "none"), {})
Add32Reviewed == SizedInstruction("AMD64-F-0028", 32, GPRRef(0, "low32"),
  "readWrite", ImmediateSized(ImmediateBits({1}, 32), 32, 32, "none"), {})
Add64Reviewed == SizedInstruction("AMD64-F-0029", 64, GPRRef(0, "full64"),
  "readWrite", ImmediateSized(ImmediateBits(1..32, 32), 32, 64, "sign"), {"rex-w"})
Mov32Reviewed == SizedInstruction("AMD64-F-0498", 32, GPRRef(0, "low32"),
  "write", ImmediateSized(ImmediateBits({1}, 32), 32, 32, "none"), {})
Mov64SignReviewed == SizedInstruction("AMD64-F-0503-R", 64, GPRRef(0, "full64"),
  "write", ImmediateSized(ImmediateBits(1..32, 32), 32, 64, "sign"), {"rex-w"})
Inc8Reviewed == UnaryInstruction("AMD64-F-0318", 8, AL, {})
Dec8Reviewed == UnaryInstruction("AMD64-F-0282", 8, AL, {})
Neg8Reviewed == UnaryInstruction("AMD64-F-0549", 8, AL, {})
Not8Reviewed == UnaryInstruction("AMD64-F-0557", 8, AL, {})
Inc8MemoryReviewed == UnaryInstruction("AMD64-F-0318", 8, MemoryRef, {})
SameAH == RegisterInstruction("conditional-xor-ah-ah", 8, AH, AH)
Same16 == RegisterInstruction("conditional-add-ax-ax", 16,
  GPRRef(0, "low16"), GPRRef(0, "low16"))
Same32 == RegisterInstruction("conditional-xor-eax-eax", 32,
  GPRRef(0, "low32"), GPRRef(0, "low32"))
Same64 == RegisterInstruction("conditional-sub-rax-rax", 64,
  GPRRef(0, "full64"), GPRRef(0, "full64"))

\* @type: $amd64CPUState => $integerExecutionOutcome;
BodyOutcome(state) == [kind |-> "body-applied", stateWritten |-> TRUE,
  state |-> state, reason |-> ""]
\* @type: ($amd64CPUState, Str) => $integerExecutionOutcome;
UnavailableOutcome(state, reason) == [kind |-> "modeling-unavailable",
  stateWritten |-> FALSE, state |-> state, reason |-> reason]
\* @type: ($amd64CPUState, Str) => $integerExecutionOutcome;
RejectedOutcome(state, reason) == [kind |-> "validation-rejected",
  stateWritten |-> FALSE, state |-> state, reason |-> reason]

\* @type: (Str, $executionInstruction, $amd64CPUState) => $amd64CPUState;
ExactAfter(op, instruction, before) ==
  LET destination == instruction.operands[1].ref
      source == instruction.operands[2].ref
      width == ViewWidth(destination.gprView)
      left == ReadGPR(before, destination)
      right == ReadSource(before, source)
      result == ExactBinary(op, left, right,
                  Adapter!ProjectStatusFlags(before.rflags), width)
      valued == IF op = "cmp" THEN before
                ELSE WriteGPR(before, destination, result.value)
  IN WriteStatus(valued, result.flags)

\* @type: (Str, $executionInstruction, $amd64CPUState, Bool) => $amd64CPUState;
LogicAfter(op, instruction, before, af) ==
  LET destination == instruction.operands[1].ref
      source == instruction.operands[2].ref
      width == ViewWidth(destination.gprView)
      value == Core!LogicWord(LogicOperation(op), ReadGPR(before, destination),
                              ReadSource(before, source), width)
      valued == IF op = "test" THEN before ELSE WriteGPR(before, destination, value)
      status == [flag \in Core!Flags |->
        CASE flag = "cf" \/ flag = "of" -> FALSE
          [] flag = "pf" -> Core!ParityEven(value)
          [] flag = "af" -> af
          [] flag = "zf" -> Core!IsZero(value, width)
          [] OTHER -> value[width]]
  IN WriteStatus(valued, status)

\* @type: (Str, $executionInstruction, $amd64CPUState) => $amd64CPUState;
UnaryAfter(op, instruction, before) ==
  LET destination == instruction.operands[1].ref
      width == ViewWidth(destination.gprView)
      oldFlags == Adapter!ProjectStatusFlags(before.rflags)
  IN IF op = "not"
     THEN WriteGPR(before, destination,
                   Core!NotWord(ReadGPR(before, destination), width))
     ELSE LET result == ExactUnary(op, ReadGPR(before, destination),
                                   oldFlags, width)
          IN WriteStatus(WriteGPR(before, destination, result.value), result.flags)

BeforeFF == StateWithRAX(Word(1..8))
BadModeState == [BeforeFF EXCEPT !.execution.mode = "real"]
Before12CD == StateWithRAX(Word({1,3,4,7,8,10,13}))
AddAfter == ExactAfter("add", AddInstruction, BeforeFF)
SubAfter == ExactAfter("sub", SubInstruction, StateWithRAX(Word({2})))
CmpAfter == ExactAfter("cmp", CmpInstruction, BeforeFF)
MovAHAfter == WriteGPR(Before12CD, AH, ReadSource(Before12CD, Imm12))
Add16ReviewedAfter == ExactAfter("add", Add16Reviewed, StateWithRAX(Word({1})))
Add32ReviewedAfter == ExactAfter("add", Add32Reviewed, StateWithRAX(Word({1})))
Add64ReviewedAfter == ExactAfter("add", Add64Reviewed, StateWithRAX(ZeroBits(64)))
Mov32ReviewedAfter == WriteGPR(StateWithRAX(OneBits(64)), GPRRef(0, "low32"),
  ReadSource(StateWithRAX(OneBits(64)), Mov32Reviewed.operands[2].ref))
Mov64SignAfter == WriteGPR(StateWithRAX(ZeroBits(64)), GPRRef(0, "full64"),
  ReadSource(StateWithRAX(ZeroBits(64)), Mov64SignReviewed.operands[2].ref))

ReviewedChecks ==
  /\ ExecuteReviewed(Architecture, FormProfile,
       AddInstruction, BeforeFF, BodyOutcome(AddAfter))
  /\ ExecuteReviewed(Architecture, FormProfile,
       SubInstruction, StateWithRAX(Word({2})), BodyOutcome(SubAfter))
  /\ ExecuteReviewed(Architecture, FormProfile,
       CmpInstruction, BeforeFF, BodyOutcome(CmpAfter))
  /\ ExecuteReviewed(Architecture, FormProfile,
       MovAHInstruction, Before12CD, BodyOutcome(MovAHAfter))
  /\ ExecuteReviewed(Architecture, FormProfile,
       AndInstruction, BeforeFF,
       BodyOutcome(LogicAfter("and", AndInstruction, BeforeFF, FALSE)))
  /\ ExecuteReviewed(Architecture, FormProfile,
       OrInstruction, BeforeFF,
       BodyOutcome(LogicAfter("or", OrInstruction, BeforeFF, TRUE)))
  /\ ExecuteReviewed(Architecture, FormProfile,
       TestInstruction, BeforeFF,
       BodyOutcome(LogicAfter("test", TestInstruction, BeforeFF, FALSE)))
  /\ ExecuteReviewed(Architecture, FormProfile,
       XorInstruction, BeforeFF,
       BodyOutcome(LogicAfter("xor", XorInstruction, BeforeFF, TRUE)))
  /\ ExecuteReviewed(Architecture, FormProfile, Add16Reviewed,
       StateWithRAX(Word({1})), BodyOutcome(Add16ReviewedAfter))
  /\ ExecuteReviewed(Architecture, FormProfile, Add32Reviewed,
       StateWithRAX(Word({1})), BodyOutcome(Add32ReviewedAfter))
  /\ ExecuteReviewed(Architecture, FormProfile, Add64Reviewed,
       StateWithRAX(ZeroBits(64)), BodyOutcome(Add64ReviewedAfter))
  /\ ExecuteReviewed(Architecture, FormProfile, Mov32Reviewed,
       StateWithRAX(OneBits(64)), BodyOutcome(Mov32ReviewedAfter))
  /\ ExecuteReviewed(Architecture, FormProfile, Mov64SignReviewed,
       StateWithRAX(ZeroBits(64)), BodyOutcome(Mov64SignAfter))
  /\ ExecuteSupplementalUnary(Architecture, FormProfile, Inc8Reviewed,
       StateWithRAX(Word(1..8)),
       BodyOutcome(UnaryAfter("inc", Inc8Reviewed, StateWithRAX(Word(1..8)))))
  /\ ExecuteSupplementalUnary(Architecture, FormProfile, Dec8Reviewed,
       StateWithRAX(ZeroBits(64)),
       BodyOutcome(UnaryAfter("dec", Dec8Reviewed, StateWithRAX(ZeroBits(64)))))
  /\ ExecuteSupplementalUnary(Architecture, FormProfile, Neg8Reviewed,
       StateWithRAX(Word({8})),
       BodyOutcome(UnaryAfter("neg", Neg8Reviewed, StateWithRAX(Word({8})))))
  /\ ExecuteSupplementalUnary(Architecture, FormProfile, Not8Reviewed,
       StateWithRAX(Word({1})),
       BodyOutcome(UnaryAfter("not", Not8Reviewed, StateWithRAX(Word({1})))))
  /\ ExecuteSupplementalUnary(Architecture, FormProfile, Inc8MemoryReviewed,
       BeforeFF, UnavailableOutcome(BeforeFF, "memory-operand"))

BoundaryChecks ==
  /\ ReadGPR(AddAfter, AL) = ZeroBits(64)
  /\ AddAfter.rflags.cf /\ AddAfter.rflags.zf /\ ~AddAfter.rflags.df
  /\ CmpAfter.gpr = BeforeFF.gpr
  /\ MovAHAfter.gpr[0] = Word({1,3,4,7,8,10,13})
  /\ ExecuteConditional("xor",
       Instruction("conditional-reg-reg", AL, "readWrite", AL, {}),
       BeforeFF, BodyOutcome(LogicAfter("xor",
         Instruction("conditional-reg-reg", AL, "readWrite", AL, {}),
         BeforeFF, FALSE)))
  /\ ExecuteConditional("xor", SameAH, Before12CD,
       BodyOutcome(LogicAfter("xor", SameAH, Before12CD, FALSE)))
  /\ ExecuteConditional("add", Same16, StateWithRAX(Word({1})),
       BodyOutcome(ExactAfter("add", Same16, StateWithRAX(Word({1})))))
  /\ ExecuteConditional("xor", Same32, StateWithRAX(OneBits(64)),
       BodyOutcome(LogicAfter("xor", Same32, StateWithRAX(OneBits(64)), FALSE)))
  /\ ExecuteConditional("sub", Same64, StateWithRAX(OneBits(64)),
       BodyOutcome(ExactAfter("sub", Same64, StateWithRAX(OneBits(64)))))
  /\ ReadGPR(LogicAfter("xor", SameAH, Before12CD, FALSE), AH) = ZeroBits(64)
  /\ ReadGPR(ExactAfter("add", Same16, StateWithRAX(Word({1}))),
       GPRRef(0, "low16")) = Word({2})
  /\ ExactAfter("add", Same16, StateWithRAX(Word({1}))).gpr[0][17] = FALSE
  /\ LogicAfter("xor", Same32, StateWithRAX(OneBits(64)), FALSE).gpr[0] = ZeroBits(64)
  /\ ExactAfter("sub", Same64, StateWithRAX(OneBits(64))).gpr[0] = ZeroBits(64)
  /\ ExecuteReviewed(Architecture, FormProfile,
       Instruction("unreviewed-memory", AL, "readWrite", MemoryRef, {}),
       BeforeFF, UnavailableOutcome(BeforeFF, "form-binding-pending"))
  /\ ExecuteReviewed(Architecture, FormProfile, AddInstruction,
       BadModeState, RejectedOutcome(BadModeState, "invalid-before-state"))
  /\ OperandContextFromState(BeforeFF).mode = "long64"
  /\ Add64ReviewedAfter.gpr[0] = OneBits(64)
  /\ Mov32ReviewedAfter.gpr[0] = Word({1})
  /\ Mov64SignAfter.gpr[0] = OneBits(64)
  /\ Cardinality(ReviewedFormIds) = 33
  /\ WriteViewAllowed("protected", OneBits(64), Word({1}), "low32", Word({1}))
  /\ WriteViewAllowed("protected", OneBits(64), Word({1}), "low32",
       [bit \in 1..64 |-> bit = 1 \/ bit > 32])

NextIP == Word({1, 3})
ReadyEvidence == [beforeIP |-> AddAfter.rip, instructionLength |-> 5,
  nextIP |-> NextIP, fetchAcceptedAssumption |-> TRUE,
  synchronousEventsResolvedAssumption |-> TRUE,
  asynchronousEventsCheckedAssumption |-> TRUE]
PendingEvidence == [ReadyEvidence EXCEPT
  !.asynchronousEventsCheckedAssumption = FALSE]
FallthroughAfter == [AddAfter EXCEPT !.rip = NextIP]
FallthroughOutcome == [kind |-> "fallthrough-applied", stateWritten |-> TRUE,
  state |-> FallthroughAfter, reason |-> ""]
PendingFallthroughOutcome == [kind |-> "modeling-unavailable", stateWritten |-> FALSE,
  state |-> AddAfter, reason |-> "fallthrough-evidence-pending"]
ForgedEvidence == [ReadyEvidence EXCEPT !.nextIP = Word({1, 5})]
ForgedFallthroughOutcome == [kind |-> "modeling-unavailable", stateWritten |-> FALSE,
  state |-> AddAfter, reason |-> "fallthrough-certificate-invalid"]
LegacyWrapState == [BeforeFF EXCEPT
  !.rip = Word(1..16), !.execution.mode = "protected"]
LegacyWrapEvidence == [beforeIP |-> LegacyWrapState.rip,
  instructionLength |-> 1, nextIP |-> ZeroBits(64),
  fetchAcceptedAssumption |-> TRUE,
  synchronousEventsResolvedAssumption |-> TRUE,
  asynchronousEventsCheckedAssumption |-> TRUE]
ZeroLengthEvidence == [ReadyEvidence EXCEPT !.instructionLength = 0]
LongLengthEvidence == [ReadyEvidence EXCEPT !.instructionLength = 16]
FallthroughChecks ==
  /\ ApplyFallthrough(BodyOutcome(AddAfter), ReadyEvidence, FallthroughOutcome)
  /\ FallthroughAfter.rip = NextIP
  /\ FallthroughAfter.gpr = AddAfter.gpr
  /\ FallthroughAfter.rflags = AddAfter.rflags
  /\ ApplyFallthrough(BodyOutcome(AddAfter), PendingEvidence,
                      PendingFallthroughOutcome)
  /\ ApplyFallthrough(BodyOutcome(AddAfter), ForgedEvidence,
                      ForgedFallthroughOutcome)
  /\ FallthroughCertificateValid(LegacyWrapState, LegacyWrapEvidence)
  /\ ~FallthroughCertificateValid(AddAfter, ZeroLengthEvidence)
  /\ ~FallthroughCertificateValid(AddAfter, LongLengthEvidence)

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ ReviewedChecks /\ BoundaryChecks /\ FallthroughChecks

=====================================================================
