---------------- MODULE AMD64IntegerShiftExecution ----------------
EXTENDS AMD64IntegerExecution, AMD64IntegerShiftBit

\* Register execution for all reviewed legacy and BMI2 shift/rotate rows.
\* The original reg/mem form IDs are retained. A validated memory instance is
\* modeling-unavailable until MachineAccess supplies resolved bytes/events.

\* @typeAlias: shiftWidthCount = {width: Int, countKind: Str};
\* @typeAlias: shiftBinding = {formId: Str, operation: Str, width: Int,
\*   countKind: Str, bmi2: Bool};
\* @typeAlias: shiftEncodingEvidence = {vexL: Bool, vexW: Bool};

\* @type: Seq($shiftWidthCount);
LegacyWidthsCounts == <<
  [width |-> 8, countKind |-> "one"], [width |-> 8, countKind |-> "cl"],
  [width |-> 8, countKind |-> "immediate"],
  [width |-> 16, countKind |-> "one"], [width |-> 16, countKind |-> "cl"],
  [width |-> 16, countKind |-> "immediate"],
  [width |-> 32, countKind |-> "one"], [width |-> 32, countKind |-> "cl"],
  [width |-> 32, countKind |-> "immediate"],
  [width |-> 64, countKind |-> "one"], [width |-> 64, countKind |-> "cl"],
  [width |-> 64, countKind |-> "immediate"]>>

\* @type: Seq(Str);
RclIds == <<"AMD64-F-0645","AMD64-F-0646","AMD64-F-0647","AMD64-F-0648",
  "AMD64-F-0649","AMD64-F-0650","AMD64-F-0651","AMD64-F-0652",
  "AMD64-F-0653","AMD64-F-0654","AMD64-F-0655","AMD64-F-0656">>
\* @type: Seq(Str);
RcrIds == <<"AMD64-F-0657","AMD64-F-0658","AMD64-F-0659","AMD64-F-0660",
  "AMD64-F-0661","AMD64-F-0662","AMD64-F-0663","AMD64-F-0664",
  "AMD64-F-0665","AMD64-F-0666","AMD64-F-0667","AMD64-F-0668">>
\* @type: Seq(Str);
RolIds == <<"AMD64-F-0685","AMD64-F-0686","AMD64-F-0687","AMD64-F-0688",
  "AMD64-F-0689","AMD64-F-0690","AMD64-F-0691","AMD64-F-0692",
  "AMD64-F-0693","AMD64-F-0694","AMD64-F-0695","AMD64-F-0696">>
\* @type: Seq(Str);
RorIds == <<"AMD64-F-0697","AMD64-F-0698","AMD64-F-0699","AMD64-F-0700",
  "AMD64-F-0701","AMD64-F-0702","AMD64-F-0703","AMD64-F-0704",
  "AMD64-F-0705","AMD64-F-0706","AMD64-F-0707","AMD64-F-0708">>
\* @type: Seq(Str);
SalIds == <<"AMD64-F-0712","AMD64-F-0713","AMD64-F-0714","AMD64-F-0715",
  "AMD64-F-0716","AMD64-F-0717","AMD64-F-0718","AMD64-F-0719",
  "AMD64-F-0720","AMD64-F-0721","AMD64-F-0722","AMD64-F-0723">>
\* @type: Seq(Str);
ShlIds == <<"AMD64-F-0724","AMD64-F-0725","AMD64-F-0726","AMD64-F-0727",
  "AMD64-F-0728","AMD64-F-0729","AMD64-F-0730","AMD64-F-0731",
  "AMD64-F-0732","AMD64-F-0733","AMD64-F-0734","AMD64-F-0735">>
\* @type: Seq(Str);
SarIds == <<"AMD64-F-0736","AMD64-F-0737","AMD64-F-0738","AMD64-F-0739",
  "AMD64-F-0740","AMD64-F-0741","AMD64-F-0742","AMD64-F-0743",
  "AMD64-F-0744","AMD64-F-0745","AMD64-F-0746","AMD64-F-0747">>
\* @type: Seq(Str);
ShrIds == <<"AMD64-F-0816","AMD64-F-0817","AMD64-F-0818","AMD64-F-0819",
  "AMD64-F-0820","AMD64-F-0821","AMD64-F-0822","AMD64-F-0823",
  "AMD64-F-0824","AMD64-F-0825","AMD64-F-0826","AMD64-F-0827">>

\* @type: (Seq(Str), Str) => Set({formId: Str, operation: Str, width: Int,
\*   countKind: Str, bmi2: Bool});
LegacyBindings(ids, operation) ==
  {[formId |-> ids[index], operation |-> operation,
    width |-> LegacyWidthsCounts[index].width,
    countKind |-> LegacyWidthsCounts[index].countKind, bmi2 |-> FALSE] :
    index \in 1..12}

\* @type: Set($shiftBinding);
DoubleBindings == {
  [formId |-> "AMD64-F-0808",operation |-> "shld",width |-> 16,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0809",operation |-> "shld",width |-> 16,countKind |-> "cl",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0810",operation |-> "shld",width |-> 32,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0811",operation |-> "shld",width |-> 32,countKind |-> "cl",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0812",operation |-> "shld",width |-> 64,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0813",operation |-> "shld",width |-> 64,countKind |-> "cl",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0828",operation |-> "shrd",width |-> 16,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0829",operation |-> "shrd",width |-> 16,countKind |-> "cl",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0830",operation |-> "shrd",width |-> 32,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0831",operation |-> "shrd",width |-> 32,countKind |-> "cl",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0832",operation |-> "shrd",width |-> 64,countKind |-> "immediate",bmi2 |-> FALSE],
  [formId |-> "AMD64-F-0833",operation |-> "shrd",width |-> 64,countKind |-> "cl",bmi2 |-> FALSE]}

\* @type: Set($shiftBinding);
BmiBindings == {
  [formId |-> "AMD64-F-0748",operation |-> "sarx",width |-> 32,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0749",operation |-> "sarx",width |-> 64,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0814",operation |-> "shlx",width |-> 32,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0815",operation |-> "shlx",width |-> 64,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0834",operation |-> "shrx",width |-> 32,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0835",operation |-> "shrx",width |-> 64,countKind |-> "register",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0709",operation |-> "rorx",width |-> 32,countKind |-> "immediate",bmi2 |-> TRUE],
  [formId |-> "AMD64-F-0710",operation |-> "rorx",width |-> 64,countKind |-> "immediate",bmi2 |-> TRUE]}

\* @type: Set($shiftBinding);
Bindings == LegacyBindings(RclIds,"rcl") \cup LegacyBindings(RcrIds,"rcr")
  \cup LegacyBindings(RolIds,"rol") \cup LegacyBindings(RorIds,"ror")
  \cup LegacyBindings(SalIds,"shl") \cup LegacyBindings(ShlIds,"shl")
  \cup LegacyBindings(SarIds,"sar") \cup LegacyBindings(ShrIds,"shr")
  \cup DoubleBindings \cup BmiBindings
\* @type: Set(Str);
ShiftReviewedFormIds == {binding.formId : binding \in Bindings}

\* @type: Str => $shiftBinding;
BindingFor(formId) == CHOOSE binding \in Bindings : binding.formId = formId

RECURSIVE LowNat(_, _)
\* @type: ($integerWord, Int) => Int;
LowNat(word, bits) == IF bits = 0 THEN 0
  ELSE LowNat(word, bits - 1) + IF word[bits] THEN 2 ^ (bits - 1) ELSE 0

\* @type: ($amd64CPUState, Str, $executionOperandRef) => Int;
CountValue(before, kind, ref) ==
  CASE kind = "one" -> 1
    [] kind = "cl" -> LowNat(ReadGPR(before, ref), 8)
    [] kind = "immediate" -> LowNat(ImmediateValue(ref), 8)
    [] OTHER -> LowNat(ReadGPR(before, ref), IF ref.width = 64 THEN 6 ELSE 5)

\* @type: (Str, $executionOperandRef) => Bool;
CountShape(kind, ref) ==
  CASE kind = "one" -> ref.kind = "constant" /\ ref.constant = 1
    [] kind = "cl" -> ref.kind = "gpr" /\ ref.gprIndex = 1 /\ ref.gprView = "low8"
    [] kind = "immediate" -> ref.kind = "immediate" /\ ref.encodedWidth = 8
    [] OTHER -> ref.kind = "gpr"

\* @type: ($shiftBinding, Str) => Bool;
ModeAllowed(binding, mode) ==
  /\ binding.width = 64 => mode = "long64"
  /\ binding.bmi2 => mode \in {"protected","compatibility","long64"}

LegacyPrefixes == {"rep","repne","operand-size","address-size",
  "cs","ss","ds","es","fs","gs","rex","rex-w"}
VexPrefixes == {"address-size","cs","ss","ds","es","fs","gs"}

\* @type: ($shiftBinding, $executionInstruction, $shiftEncodingEvidence) => Bool;
EncodingAllowed(binding, instruction, evidence) ==
  /\ "lock" \notin instruction.prefixes
  /\ IF binding.bmi2
     THEN /\ instruction.encodingFamily = "vex"
          /\ instruction.prefixes \subseteq VexPrefixes
          /\ ~evidence.vexL
          /\ evidence.vexW = (binding.width = 64)
     ELSE /\ instruction.encodingFamily = "legacy"
          /\ instruction.prefixes \subseteq LegacyPrefixes
          /\ (binding.width = 64 => "rex-w" \in instruction.prefixes)
          /\ (binding.width /= 64 => "rex-w" \notin instruction.prefixes)

\* @type: ($shiftBinding, $executionInstruction) => Bool;
PayloadShape(binding, instruction) ==
  LET triple == binding.operation \in {"shld","shrd","sarx","shlx","shrx","rorx"}
  IN /\ Len(instruction.operands) = IF triple THEN 3 ELSE 2
     /\ instruction.operands[1].ref.kind \in {"gpr","memory"}
     /\ instruction.operands[1].ref.width = binding.width
     /\ IF triple
        THEN /\ instruction.operands[2].ref.kind \in {"gpr","memory"}
             /\ instruction.operands[2].ref.width = binding.width
             /\ CountShape(binding.countKind, instruction.operands[3].ref)
        ELSE CountShape(binding.countKind, instruction.operands[2].ref)

\* @type: ($integerFlagDomains, $amd64CPUState, $integerFlags, $amd64CPUState) => Bool;
WriteWithDomains(domains, valued, status, after) ==
  /\ Core!FlagsAllowed(status, domains)
  /\ after = WriteStatus(valued, status)

\* @type: ($shiftBinding, $executionInstruction, $amd64CPUState,
\*   $amd64CPUState) => Bool;
ShiftBodyStep(binding, instruction, before, after) ==
  LET destination == instruction.operands[1].ref
      source == IF Len(instruction.operands) = 3 THEN instruction.operands[2].ref
                ELSE destination
      countRef == instruction.operands[Len(instruction.operands)].ref
      rawCount == CountValue(before, binding.countKind, countRef)
      masked == MaskedCount(rawCount, binding.width)
      oldValue == ReadGPR(before, destination)
      sourceValue == ReadGPR(before, source)
      oldFlags == Adapter!ProjectStatusFlags(before.rflags)
      result == ReadGPR(after, destination)
      status == Adapter!ProjectStatusFlags(after.rflags)
  IN IF ~binding.bmi2 /\ masked = 0 THEN after = before
     ELSE IF binding.operation \in {"shl","shr","sar"}
     THEN /\ ShiftAllowed(binding.operation, oldValue, rawCount, binding.width,
                       oldFlags, result, status)
       /\ WriteGPRAllowed(before, destination, result,
            [after EXCEPT !.rflags = before.rflags])
       /\ after = WriteStatus([after EXCEPT !.rflags = before.rflags], status)
     ELSE IF binding.operation \in {"rol","ror"}
     THEN /\ RotateAllowed(binding.operation, oldValue, rawCount, binding.width,
                        oldFlags, result, status)
       /\ WriteGPRAllowed(before, destination, result,
            [after EXCEPT !.rflags = before.rflags])
       /\ after = WriteStatus([after EXCEPT !.rflags = before.rflags], status)
     ELSE IF binding.operation \in {"rcl","rcr"}
     THEN /\ CarryRotateAllowed(binding.operation, oldValue, rawCount,
             binding.width, oldFlags, result, status)
       /\ WriteGPRAllowed(before, destination, result,
            [after EXCEPT !.rflags = before.rflags])
       /\ after = WriteStatus([after EXCEPT !.rflags = before.rflags], status)
     ELSE IF binding.operation \in {"shld","shrd"}
     THEN /\ DoubleShiftAllowed(binding.operation, oldValue, sourceValue, rawCount,
                             binding.width, oldFlags, result, status)
       /\ WriteGPRAllowed(before, destination, result,
            [after EXCEPT !.rflags = before.rflags])
       /\ after = WriteStatus([after EXCEPT !.rflags = before.rflags], status)
     ELSE LET kind == CASE binding.operation = "shlx" -> "shl"
                         [] binding.operation = "sarx" -> "sar"
                         [] binding.operation = "shrx" -> "shr"
                         [] OTHER -> "ror"
              bmiResult == IF kind = "ror"
                        THEN RotateValue("ror", sourceValue, binding.width,
                                         masked % binding.width)
                        ELSE ShiftValue(kind, sourceValue, binding.width, masked)
          IN WriteGPRAllowed(before, destination, bmiResult, after)

\* @type: ($executionProfile, $executionFormProfile, $shiftEncodingEvidence,
\*   $executionInstruction, $amd64CPUState, $integerExecutionOutcome) => Bool;
Execute(architecture, formProfile, evidence, instruction, before, outcome) ==
  IF instruction.formId \notin ShiftReviewedFormIds THEN
    /\ outcome.kind = "modeling-unavailable" /\ ~outcome.stateWritten
    /\ outcome.reason = "form-binding-pending" /\ outcome.state = before
  ELSE LET binding == BindingFor(instruction.formId)
       IN IF ~CPUStateWellFormed(architecture, before) \/
             instruction.operandSize /= binding.width \/
             ~ModeAllowed(binding, before.execution.mode) \/
             before.execution.mode \notin formProfile.modes \/
             ~EncodingAllowed(binding, instruction, evidence) \/
             (binding.bmi2 /\ "bmi2" \notin formProfile.features) \/
             binding.width \notin formProfile.operandSizes \/
             instruction.addressSize \notin formProfile.addressSizes \/
             (before.execution.mode = "long64" /\ instruction.addressSize = 16) \/
             (before.execution.mode /= "long64" /\ instruction.addressSize = 64) \/
             Operands!InvalidPayloadIndices(architecture,
               OperandContextFromState(before),
               DefaultAddressWidth(before.segments, before.execution.mode),
               instruction) /= {} \/
             ~PayloadShape(binding, instruction)
          THEN /\ outcome.kind = "validation-rejected" /\ ~outcome.stateWritten
               /\ outcome.reason = "shift-form-invalid" /\ outcome.state = before
          ELSE IF \E index \in 1..Len(instruction.operands) :
                    instruction.operands[index].ref.kind = "memory"
          THEN /\ outcome.kind = "modeling-unavailable" /\ ~outcome.stateWritten
               /\ outcome.reason = "memory-operand" /\ outcome.state = before
          ELSE /\ outcome.kind = "body-applied" /\ outcome.stateWritten
               /\ outcome.reason = ""
               /\ ShiftBodyStep(binding, instruction, before, outcome.state)

=============================================================================
