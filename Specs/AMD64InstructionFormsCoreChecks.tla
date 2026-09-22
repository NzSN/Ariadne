----------------- MODULE AMD64InstructionFormsCoreChecks -----------------
EXTENDS AMD64InstructionFormsCore

VARIABLE
  \* @type: Bool;
  done

\* @type: Str => Seq({kind: Str, width: Int, encodedWidth: Int,
\*   semanticWidth: Int, extension: Str, identity: Str, sourceText: Str,
\*   accessIntent: Str, evaluationOrder: Int});
Operands(destinationIdentity) == <<
  [kind |-> "gpr", width |-> 8, encodedWidth |-> 8, semanticWidth |-> 8,
   extension |-> "none", identity |-> destinationIdentity,
   sourceText |-> "AL", accessIntent |-> "readWrite", evaluationOrder |-> 1],
  [kind |-> "immediate", width |-> 8, encodedWidth |-> 8, semanticWidth |-> 8,
   extension |-> "none", identity |-> "",
   sourceText |-> "imm8", accessIntent |-> "read", evaluationOrder |-> 2]
>>

Decoded(destinationIdentity, prefixes) == [formId |-> "AMD64-F-0026",
  mode |-> "long64", operandSize |-> 8, addressSize |-> 64,
  prefixes |-> prefixes, operands |-> Operands(destinationIdentity),
  encodingFamily |-> "legacy",
  rexPresent |-> "rex" \in prefixes \/ "rex-w" \in prefixes,
  highByteRegister |-> destinationIdentity = "gpr:0:high8",
  prefixConflict |-> FALSE]

Profile == [modes |-> {"long64"}, features |-> {},
  operandSizes |-> {8}, addressSizes |-> {64}]

Init == done = FALSE
Next == done' = ~done
Spec == Init /\ [][Next]_done

\* @type: (Str, Int, Int, Str, Str) => Seq({kind: Str, width: Int,
\*   encodedWidth: Int, semanticWidth: Int, extension: Str, identity: Str,
\*   sourceText: Str, accessIntent: Str, evaluationOrder: Int});
WideOperands(identity, encodedWidth, semanticWidth, extension, access) == <<
  [kind |-> "gpr", width |-> 64, encodedWidth |-> 64, semanticWidth |-> 64,
   extension |-> "none", identity |-> identity, sourceText |-> "RAX",
   accessIntent |-> access, evaluationOrder |-> 1],
  [kind |-> "immediate", width |-> encodedWidth, encodedWidth |-> encodedWidth,
   semanticWidth |-> semanticWidth, extension |-> extension, identity |-> "",
   sourceText |-> "imm", accessIntent |-> "read", evaluationOrder |-> 2]
>>

WideDecoded(formId, encodedWidth, semanticWidth, extension, access) == [
  formId |-> formId, mode |-> "long64", operandSize |-> 64, addressSize |-> 64,
  prefixes |-> {"rex-w"},
  operands |-> WideOperands("gpr:0:full64", encodedWidth, semanticWidth, extension, access),
  encodingFamily |-> "legacy", rexPresent |-> TRUE,
  highByteRegister |-> FALSE, prefixConflict |-> FALSE]

Profile64 == [modes |-> {"long64"}, features |-> {},
  operandSizes |-> {64}, addressSizes |-> {64}]

Reviewed == \A form \in CoreForms : Forms!ReadyForLegality(form)
ValidAL == Forms!ValidateDecoded(AddALImm8, Decoded("gpr:0:low8", {}), Profile).kind =
  "validated"
RejectAH == Forms!ValidateDecoded(AddALImm8, Decoded("gpr:0:high8", {}), Profile).kind =
  "normalization-error"
RejectBL == Forms!ValidateDecoded(AddALImm8, Decoded("gpr:3:low8", {}), Profile).kind =
  "normalization-error"
RejectLock == Forms!ValidateDecoded(AddALImm8, Decoded("gpr:0:low8", {"lock"}), Profile).kind =
  "architectural-invalid"
ValidAdd64Sign == Forms!ValidateDecoded(AddRAXImm32,
  WideDecoded("AMD64-F-0029", 32, 64, "sign", "readWrite"), Profile64).kind = "validated"
RejectAdd64Zero == Forms!ValidateDecoded(AddRAXImm32,
  WideDecoded("AMD64-F-0029", 32, 64, "zero", "readWrite"), Profile64).kind =
  "normalization-error"
ValidMov64Imm64 == Forms!ValidateDecoded(MovReg64Imm64,
  WideDecoded("AMD64-F-0499", 64, 64, "none", "write"), Profile64).kind = "validated"
ValidMov64Imm32Sign == Forms!ValidateDecoded(MovReg64Imm32Sign,
  WideDecoded("AMD64-F-0503-R", 32, 64, "sign", "write"), Profile64).kind = "validated"

Safety == Reviewed /\ ValidAL /\ RejectAH /\ RejectBL /\ RejectLock /\
  ValidAdd64Sign /\ RejectAdd64Zero /\ ValidMov64Imm64 /\ ValidMov64Imm32Sign

=============================================================================
