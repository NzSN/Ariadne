--------------- MODULE AMD64IntegerCommonExecution ---------------
EXTENDS AMD64IntegerExecution

\* Long64/CPL3 register instances of common reg/mem rows. The same source rows
\* retain memory alternatives, returned as modeling-unavailable.

\* @typeAlias: commonBinding = {formId: Str, operation: Str, width: Int,
\*   destinationAccess: Str};

\* @type: Seq(Int);
RegWidths == <<8,16,32,64,8,16,32,64>>
\* @type: Seq(Str);
AdcRegIds == <<"AMD64-F-0016","AMD64-F-0017","AMD64-F-0018","AMD64-F-0019",
  "AMD64-F-0020","AMD64-F-0021","AMD64-F-0022","AMD64-F-0023">>
\* @type: Seq(Str);
AddRegIds == <<"AMD64-F-0037","AMD64-F-0038","AMD64-F-0039","AMD64-F-0040",
  "AMD64-F-0041","AMD64-F-0042","AMD64-F-0043","AMD64-F-0044">>
\* @type: Seq(Str);
AndRegIds == <<"AMD64-F-0058","AMD64-F-0059","AMD64-F-0060","AMD64-F-0061",
  "AMD64-F-0062","AMD64-F-0063","AMD64-F-0064","AMD64-F-0065">>
\* @type: Seq(Str);
CmpRegIds == <<"AMD64-F-0251","AMD64-F-0252","AMD64-F-0253","AMD64-F-0254",
  "AMD64-F-0255","AMD64-F-0256","AMD64-F-0257","AMD64-F-0258">>
\* @type: Seq(Str);
MovRegIds == <<"AMD64-F-0478","AMD64-F-0479","AMD64-F-0480","AMD64-F-0481",
  "AMD64-F-0482","AMD64-F-0483","AMD64-F-0484","AMD64-F-0485">>
\* @type: Seq(Str);
OrRegIds == <<"AMD64-F-0572","AMD64-F-0573","AMD64-F-0574","AMD64-F-0575",
  "AMD64-F-0576","AMD64-F-0577","AMD64-F-0578","AMD64-F-0579">>
\* @type: Seq(Str);
SbbRegIds == <<"AMD64-F-0761","AMD64-F-0762","AMD64-F-0763","AMD64-F-0764",
  "AMD64-F-0765","AMD64-F-0766","AMD64-F-0767","AMD64-F-0768">>
\* @type: Seq(Str);
SubRegIds == <<"AMD64-F-0859","AMD64-F-0860","AMD64-F-0861","AMD64-F-0862",
  "AMD64-F-0863","AMD64-F-0864","AMD64-F-0865","AMD64-F-0866">>
\* @type: Seq(Str);
XorRegIds == <<"AMD64-F-0924","AMD64-F-0925","AMD64-F-0926","AMD64-F-0927",
  "AMD64-F-0928","AMD64-F-0929","AMD64-F-0930","AMD64-F-0931">>
\* @type: Seq(Str);
TestRegIds == <<"AMD64-F-0877","AMD64-F-0878","AMD64-F-0879","AMD64-F-0880">>
\* @type: Seq(Int);
TestWidths == <<8,16,32,64>>

\* @type: (Seq(Str), Str, Str) => Set($commonBinding);
RegBindings(ids, operation, access) ==
  {[formId |-> ids[index], operation |-> operation, width |-> RegWidths[index],
    destinationAccess |-> access] : index \in 1..8}
\* @type: Set($commonBinding);
CommonBindings == RegBindings(AdcRegIds,"adc","readWrite")
  \cup RegBindings(AddRegIds,"add","readWrite")
  \cup RegBindings(AndRegIds,"and","readWrite")
  \cup RegBindings(CmpRegIds,"cmp","read")
  \cup RegBindings(MovRegIds,"mov","write")
  \cup RegBindings(OrRegIds,"or","readWrite")
  \cup RegBindings(SbbRegIds,"sbb","readWrite")
  \cup RegBindings(SubRegIds,"sub","readWrite")
  \cup RegBindings(XorRegIds,"xor","readWrite")
  \cup {[formId |-> TestRegIds[index], operation |-> "test",
          width |-> TestWidths[index], destinationAccess |-> "read"] : index \in 1..4}
\* @type: Set(Str);
CommonFormIds == {binding.formId : binding \in CommonBindings}
\* @type: Str => $commonBinding;
CommonBindingFor(id) == CHOOSE binding \in CommonBindings : binding.formId = id

CommonPrefixes == {"rep","repne","operand-size","address-size",
  "cs","ss","ds","es","fs","gs","rex","rex-w"}

\* @type: ($commonBinding, $executionInstruction) => Bool;
CommonPayloadShape(binding, instruction) ==
  /\ Len(instruction.operands) = 2
  /\ instruction.operands[1].ref.kind \in {"gpr","memory"}
  /\ instruction.operands[1].ref.width = binding.width
  /\ instruction.operands[1].accessIntent = binding.destinationAccess
  /\ instruction.operands[2].ref.kind \in {"gpr","memory"}
  /\ instruction.operands[2].ref.width = binding.width
  /\ instruction.operands[2].accessIntent = "read"

\* @type: ($executionProfile, $executionFormProfile, $executionInstruction,
\*   $amd64CPUState, $integerExecutionOutcome) => Bool;
ExecuteCommon(architecture, formProfile, instruction, before, outcome) ==
  IF instruction.formId \notin CommonFormIds THEN
    /\ outcome.kind = "modeling-unavailable" /\ ~outcome.stateWritten
    /\ outcome.reason = "form-binding-pending" /\ outcome.state = before
  ELSE LET binding == CommonBindingFor(instruction.formId)
       IN IF ~CPUStateWellFormed(architecture, before) \/
             before.execution.mode /= "long64" \/ before.execution.cpl /= 3 \/
             "long64" \notin formProfile.modes \/
             instruction.operandSize /= binding.width \/
             instruction.addressSize \notin formProfile.addressSizes \/
             instruction.encodingFamily /= "legacy" \/
             ~(instruction.prefixes \subseteq CommonPrefixes) \/
             "lock" \in instruction.prefixes \/
             (binding.width = 64 /\ "rex-w" \notin instruction.prefixes) \/
             (binding.width /= 64 /\ "rex-w" \in instruction.prefixes) \/
             ~CommonPayloadShape(binding, instruction) \/
             Operands!InvalidPayloadIndices(architecture,
               OperandContextFromState(before),
               DefaultAddressWidth(before.segments, before.execution.mode),
               instruction) /= {}
          THEN /\ outcome.kind = "validation-rejected" /\ ~outcome.stateWritten
               /\ outcome.reason = "common-form-invalid" /\ outcome.state = before
          ELSE IF instruction.operands[1].ref.kind = "memory" \/
                  instruction.operands[2].ref.kind = "memory"
          THEN /\ outcome.kind = "modeling-unavailable" /\ ~outcome.stateWritten
               /\ outcome.reason = "memory-operand" /\ outcome.state = before
          ELSE ExecuteConditional(binding.operation, instruction, before, outcome)

====================================================================
