------------- MODULE AMD64IntegerShiftExecutionChecks -------------
EXTENDS AMD64IntegerShiftExecution

VARIABLE
  \* @type: Bool;
  shiftChecked

Base == INSTANCE AMD64IntegerExecutionChecks WITH checked <- shiftChecked

W0 == Base!ZeroBits(64)
W16 == Base!Word(1..16)
Status0 == [flag \in Core!Flags |-> FALSE]
Status1 == [flag \in Core!Flags |-> TRUE]
AL == Base!GPRRef(0, "low8")
AX == Base!GPRRef(0, "low16")
CL == Base!GPRRef(1, "low8")

\* @type: (Str, Int, $executionOperandRef, $executionOperandRef,
\*   $executionOperandRef, Str) => $executionInstruction;
TripleInstruction(formId, width, destination, source, count, family) == [
  formId |-> formId, operandSize |-> width, addressSize |-> 64,
  prefixes |-> IF width = 64 /\ family = "legacy" THEN {"rex-w"} ELSE {},
  operands |-> <<Base!Operand(destination, "write", 1),
                Base!Operand(source, "read", 2),
                Base!Operand(count, "read", 3)>>,
  implicitResources |-> Base!NoRefs, encodingFamily |-> family]

Rol8By8 == Base!Instruction("AMD64-F-0687", AL, "readWrite",
  Base!ImmediateSized(Base!ImmediateBits({4}, 8), 8, 8, "none"), {})
Rol8By9 == Base!Instruction("AMD64-F-0687", AL, "readWrite",
  Base!ImmediateSized(Base!ImmediateBits({1,4}, 8), 8, 8, "none"), {})
ShlCountZero == Base!Instruction("AMD64-F-0726", AL, "readWrite",
  Base!ImmediateSized(Base!ImmediateBits({6}, 8), 8, 8, "none"), {})
ShlMemory == Base!Instruction("AMD64-F-0726", Base!MemoryRef, "readWrite",
  Base!ImmediateSized(Base!ImmediateBits({1}, 8), 8, 8, "none"), {})
AliasState == [Base!BeforeFF EXCEPT !.gpr[1] = Base!Word({1,2})]
ShlClCl == Base!Instruction("AMD64-F-0725", CL, "readWrite", CL, {})
Shld16 == TripleInstruction("AMD64-F-0808", 16, AX, AX,
  Base!ImmediateSized(Base!ImmediateBits({1,5}, 8), 8, 8, "none"), "legacy")
ShldZeroAfter == WriteStatus(WriteGPR(Base!BeforeFF, AX, W0), Status0)
ShldOnesAfter == WriteStatus(WriteGPR(Base!BeforeFF, AX, W16), Status1)
Shlx64 == TripleInstruction("AMD64-F-0815", 64, Base!GPRRef(1,"full64"),
  Base!GPRRef(1,"full64"), Base!GPRRef(1,"full64"), "vex")

BindingChecks ==
  /\ Cardinality(ShiftReviewedFormIds) = 116
  /\ BindingFor("AMD64-F-0687").operation = "rol"
  /\ BindingFor("AMD64-F-0687").width = 8
  /\ BindingFor("AMD64-F-0815").bmi2
  /\ ~ModeAllowed(BindingFor("AMD64-F-0815"), "real")
  /\ ~EncodingAllowed(BindingFor("AMD64-F-0815"), Shlx64,
                       [vexL |-> TRUE, vexW |-> TRUE])
  /\ EncodingAllowed(BindingFor("AMD64-F-0815"), Shlx64,
                      [vexL |-> FALSE, vexW |-> TRUE])
  /\ Execute(Base!Architecture, Base!FormProfile,
       [vexL |-> FALSE, vexW |-> FALSE], ShlCountZero, Base!BeforeFF,
       Base!BodyOutcome(Base!BeforeFF))
  /\ Execute(Base!Architecture, Base!FormProfile,
       [vexL |-> FALSE, vexW |-> FALSE], ShlMemory, Base!BeforeFF,
       Base!UnavailableOutcome(Base!BeforeFF, "memory-operand"))

CountAndAliasChecks ==
  /\ CountValue(AliasState, "cl", CL) = 3
  /\ ShiftValue("shl", ReadGPR(AliasState, CL), 8, 3) = Base!Word({4,5})
  /\ ShiftBodyStep(BindingFor("AMD64-F-0726"), ShlCountZero,
                   Base!BeforeFF, Base!BeforeFF)
  /\ RotateValue("rol", ReadGPR(Base!BeforeFF, AL), 8, 8 % 8) =
       ReadGPR(Base!BeforeFF, AL)
  /\ RotateFlagDomains("rol", ReadGPR(Base!BeforeFF, AL), 8, 8,
                       Status0)["of"] = BOOLEAN
  /\ RotateFlagDomains("rol",
       RotateValue("rol", ReadGPR(Base!BeforeFF, AL), 8, 1), 8, 9,
       Status0)["of"] = BOOLEAN
  /\ CarryRotateAllowed("rcl", Base!Word({8}), 9, 8, Status1,
       Base!Word({8}), [Status1 EXCEPT !["of"] = FALSE])

DoubleShiftChecks ==
  /\ ShiftBodyStep(BindingFor("AMD64-F-0808"), Shld16,
                   Base!BeforeFF, ShldZeroAfter)
  /\ ShiftBodyStep(BindingFor("AMD64-F-0808"), Shld16,
                   Base!BeforeFF, ShldOnesAfter)
  /\ ShldZeroAfter.gpr[0] /= ShldOnesAfter.gpr[0]

Init == shiftChecked = FALSE
Next == shiftChecked' = ~shiftChecked
Safety == shiftChecked \in BOOLEAN /\ BindingChecks /\ CountAndAliasChecks /\
          DoubleShiftChecks

=====================================================================
