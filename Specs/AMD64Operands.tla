-------------------------- MODULE AMD64Operands --------------------------
EXTENDS Integers, FiniteSets, Sequences

Forms == INSTANCE AMD64InstructionForms

\* Executable operand payloads and erasure to the legality shape in
\* AMD64InstructionForms. Register storage and state validity remain owned by
\* AMD64ArchitecturalState. Effective-address arithmetic, segment bases,
\* translation and faults remain owned by AMD64Memory.

GPRViews == {"low8", "high8", "low16", "low32", "full64"}
OperandKinds == {
  "gpr", "memory", "immediate", "relative-offset", "segment-register",
  "xmm", "vector", "mmx", "mask", "far-pointer-immediate",
  "far-pointer-memory", "constant"
}
Extensions == {"none", "zero", "sign"}
VectorViews == {"xmm", "ymm", "zmm"}
SegmentNames == {"cs", "ss", "ds", "es", "fs", "gs"}

\* @typeAlias: amd64OperandAddress = {basePresent: Bool, base: Int,
\*   baseExtended: Bool, indexPresent: Bool, index: Int, indexExtended: Bool,
\*   scale: Int, displacement: Int,
\*   displacementWidth: Int, segmentPresent: Bool, segment: Str,
\*   addressSize: Int, ripRelative: Bool};
\* @typeAlias: amd64OperandRef = {kind: Str, width: Int,
\*   gprIndex: Int, gprView: Str, address: $amd64OperandAddress,
\*   immediate: Seq(Bool), encodedWidth: Int, semanticWidth: Int,
\*   extension: Str, relative: Int, targetWidth: Int, segment: Str,
\*   vectorIndex: Int, vectorView: Str, mmxIndex: Int, maskIndex: Int,
\*   farSelector: Seq(Bool), farOffset: Seq(Bool), farOffsetWidth: Int,
\*   constant: Int};
\* @typeAlias: amd64ExecutableOperand = {ref: $amd64OperandRef,
\*   sourceText: Str, accessIntent: Str, evaluationOrder: Int,
\*   registerExtension: Bool, byteCode4To7: Bool};
\* @typeAlias: amd64ExecutableInstruction = {formId: Str,
\*   operandSize: Int, addressSize: Int, prefixes: Set(Str),
\*   operands: Seq($amd64ExecutableOperand), implicitResources: Seq($amd64OperandRef),
\*   encodingFamily: Str};
\* @typeAlias: amd64OperandContext = {mode: Str, cpl: Int,
\*   x87Enabled: Bool, sseEnabled: Bool, avxEnabled: Bool,
\*   avx512Enabled: Bool};
\* @typeAlias: amd64OperandCapabilities = {longMode: Bool, x87: Bool,
\*   mmx: Bool, sse: Bool, avx: Bool, avx512: Bool,
\*   mxcsrMisalignedMask: Bool};
\* @typeAlias: amd64OperandProfile = {capabilities: $amd64OperandCapabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};

\* @type: Seq(Str);
Low8Identities == <<
  "gpr:0:low8", "gpr:1:low8", "gpr:2:low8", "gpr:3:low8",
  "gpr:4:low8", "gpr:5:low8", "gpr:6:low8", "gpr:7:low8",
  "gpr:8:low8", "gpr:9:low8", "gpr:10:low8", "gpr:11:low8",
  "gpr:12:low8", "gpr:13:low8", "gpr:14:low8", "gpr:15:low8">>
\* @type: Seq(Str);
High8Identities == <<"gpr:0:high8", "gpr:1:high8", "gpr:2:high8", "gpr:3:high8">>
\* @type: Seq(Str);
Low16Identities == <<
  "gpr:0:low16", "gpr:1:low16", "gpr:2:low16", "gpr:3:low16",
  "gpr:4:low16", "gpr:5:low16", "gpr:6:low16", "gpr:7:low16",
  "gpr:8:low16", "gpr:9:low16", "gpr:10:low16", "gpr:11:low16",
  "gpr:12:low16", "gpr:13:low16", "gpr:14:low16", "gpr:15:low16">>
\* @type: Seq(Str);
Low32Identities == <<
  "gpr:0:low32", "gpr:1:low32", "gpr:2:low32", "gpr:3:low32",
  "gpr:4:low32", "gpr:5:low32", "gpr:6:low32", "gpr:7:low32",
  "gpr:8:low32", "gpr:9:low32", "gpr:10:low32", "gpr:11:low32",
  "gpr:12:low32", "gpr:13:low32", "gpr:14:low32", "gpr:15:low32">>
\* @type: Seq(Str);
Full64Identities == <<
  "gpr:0:full64", "gpr:1:full64", "gpr:2:full64", "gpr:3:full64",
  "gpr:4:full64", "gpr:5:full64", "gpr:6:full64", "gpr:7:full64",
  "gpr:8:full64", "gpr:9:full64", "gpr:10:full64", "gpr:11:full64",
  "gpr:12:full64", "gpr:13:full64", "gpr:14:full64", "gpr:15:full64">>

\* @type: (Int, Str) => Str;
GPRIdentity(register, view) ==
  CASE view = "low8" -> Low8Identities[register + 1]
    [] view = "high8" -> High8Identities[register + 1]
    [] view = "low16" -> Low16Identities[register + 1]
    [] view = "low32" -> Low32Identities[register + 1]
    [] OTHER -> Full64Identities[register + 1]

\* @type: Str => Int;
GPRViewWidth(view) ==
  CASE view \in {"low8", "high8"} -> 8
    [] view = "low16" -> 16
    [] view = "low32" -> 32
    [] OTHER -> 64

\* @type: ($amd64OperandContext, Int, Str) => Bool;
GPRRefWellFormed(context, register, view) ==
  /\ register \in 0..15 /\ (register < 8 \/ context.mode = "long64")
  /\ view \in GPRViews
  /\ (view = "high8" => register \in 0..3)
  /\ (view = "full64" => context.mode = "long64")

\* RIP-relative addressing remains possible in long64 with address size 32;
\* Memory!EffectiveOffset owns the subsequent truncation/zero extension.
\* Reviewed transcription of AMD64Memory!AddressSizePermitted. It is kept here
\* only because Snowcat cannot currently compose the state and memory modules'
\* intentionally different `amd64Segment` aliases in one INSTANCE graph. The
\* parent integration gate owns the cross-module equality fixture.
\* @type: (Str, Int, Int) => Bool;
OperandAddressSizePermitted(mode, defaultAddressSize, addressSize) ==
  CASE mode = "long64" -> defaultAddressSize = 64 /\ addressSize \in {32, 64}
    [] mode \in {"compatibility", "protected"} ->
         defaultAddressSize \in {16, 32} /\ addressSize \in {16, 32}
    [] mode \in {"real", "virtual8086"} ->
         defaultAddressSize = 16 /\ addressSize \in {16, 32}
    [] OTHER -> FALSE

\* @type: ($amd64OperandContext, Int, $amd64OperandAddress) => Bool;
AddressExprWellFormed(context, defaultAddressSize, address) ==
  /\ address.scale \in {1, 2, 4, 8}
  /\ address.displacementWidth \in {0, 8, 16, 32}
  /\ (~address.basePresent \/
        (address.base \in 0..15 /\ (address.base < 8 \/ context.mode = "long64")))
  /\ (~address.indexPresent \/
        (address.index \in 0..15 /\ (address.index < 8 \/ context.mode = "long64")))
  /\ address.baseExtended = (address.basePresent /\ address.base >= 8)
  /\ address.indexExtended = (address.indexPresent /\ address.index >= 8)
  /\ (address.indexPresent \/ address.scale = 1)
  /\ (~address.ripRelative \/
        (~address.basePresent /\ ~address.indexPresent /\ context.mode = "long64"))
  /\ (~address.segmentPresent \/ address.segment \in SegmentNames)
  /\ OperandAddressSizePermitted(context.mode, defaultAddressSize, address.addressSize)

\* @type: ($amd64OperandProfile, $amd64OperandContext, Int, $amd64OperandRef) => Bool;
OperandRefWellFormed(profile, context, defaultAddressSize, operand) ==
  operand.kind \in OperandKinds /\
  CASE operand.kind = "gpr" ->
         GPRRefWellFormed(context, operand.gprIndex, operand.gprView)
    [] operand.kind = "memory" ->
         AddressExprWellFormed(context, defaultAddressSize, operand.address) /\
         operand.width \in {8, 16, 32, 64, 128, 512}
    [] operand.kind = "immediate" ->
         operand.encodedWidth \in {8, 16, 32, 64} /\
         operand.semanticWidth \in {8, 16, 32, 64} /\
         operand.encodedWidth <= operand.semanticWidth /\
         operand.extension \in Extensions /\
         Len(operand.immediate) = operand.encodedWidth
    [] operand.kind = "relative-offset" ->
         operand.encodedWidth \in {8, 16, 32} /\ operand.targetWidth \in {16, 32, 64}
    [] operand.kind = "segment-register" -> operand.segment \in SegmentNames
    [] operand.kind \in {"xmm", "vector"} ->
         operand.vectorIndex \in 0..31 /\ operand.vectorView \in VectorViews /\
         profile.capabilities.sse /\
         (operand.vectorIndex < 8 \/ context.mode = "long64") /\
         (operand.vectorIndex < 16 \/ profile.capabilities.avx512) /\
         (operand.vectorView = "xmm" \/
           (operand.vectorView = "ymm" /\ profile.capabilities.avx) \/
           (operand.vectorView = "zmm" /\ profile.capabilities.avx512))
    [] operand.kind = "mmx" ->
         operand.mmxIndex \in 0..7 /\ profile.capabilities.mmx /\ context.x87Enabled
    [] operand.kind = "mask" ->
         operand.maskIndex \in 0..7 /\ profile.capabilities.avx512 /\ context.avx512Enabled
    [] operand.kind = "far-pointer-immediate" ->
         Len(operand.farSelector) = 16 /\ operand.farOffsetWidth \in {16, 32, 64} /\
         Len(operand.farOffset) = operand.farOffsetWidth
    [] operand.kind = "far-pointer-memory" ->
         AddressExprWellFormed(context, defaultAddressSize, operand.address) /\
         operand.farOffsetWidth \in {16, 32, 64}
    [] OTHER -> operand.width \in {1, 8, 16, 32, 64}

\* @type: $amd64OperandRef => Str;
OperandIdentity(operand) ==
  CASE operand.kind = "gpr" -> GPRIdentity(operand.gprIndex, operand.gprView)
    [] operand.kind = "segment-register" ->
         CASE operand.segment = "cs" -> "segment:cs"
           [] operand.segment = "ss" -> "segment:ss"
           [] operand.segment = "ds" -> "segment:ds"
           [] operand.segment = "es" -> "segment:es"
           [] operand.segment = "fs" -> "segment:fs"
           [] OTHER -> "segment:gs"
    [] operand.kind = "memory" -> "memory"
    [] operand.kind = "far-pointer-memory" -> "far-memory"
    [] OTHER -> ""

\* @type: $amd64ExecutableOperand => {kind: Str, width: Int,
\*   encodedWidth: Int, semanticWidth: Int, extension: Str,
\*   identity: Str, sourceText: Str, accessIntent: Str, evaluationOrder: Int};
EraseOperand(operand) ==
  [kind |-> operand.ref.kind,
   width |-> IF operand.ref.kind = "gpr"
             THEN GPRViewWidth(operand.ref.gprView) ELSE operand.ref.width,
   encodedWidth |-> IF operand.ref.kind \in {"immediate", "relative-offset"}
                    THEN operand.ref.encodedWidth
                    ELSE IF operand.ref.kind = "gpr" THEN GPRViewWidth(operand.ref.gprView)
                    ELSE operand.ref.width,
   semanticWidth |-> IF operand.ref.kind = "immediate" THEN operand.ref.semanticWidth
                     ELSE IF operand.ref.kind = "relative-offset" THEN operand.ref.targetWidth
                     ELSE IF operand.ref.kind = "gpr" THEN GPRViewWidth(operand.ref.gprView)
                     ELSE operand.ref.width,
   extension |-> IF operand.ref.kind = "relative-offset" THEN "sign"
                 ELSE IF operand.ref.kind = "immediate" THEN operand.ref.extension ELSE "none",
   identity |-> OperandIdentity(operand.ref),
   sourceText |-> operand.sourceText,
   accessIntent |-> operand.accessIntent,
   evaluationOrder |-> operand.evaluationOrder]

RECURSIVE EraseOperands(_, _)
\* @type: (Seq($amd64ExecutableOperand), Int) => Seq({kind: Str,
\*   width: Int, encodedWidth: Int, semanticWidth: Int, extension: Str,
\*   identity: Str, sourceText: Str, accessIntent: Str,
\*   evaluationOrder: Int});
EraseOperands(operands, count) ==
  IF count = 0 THEN <<>>
  ELSE Append(EraseOperands(operands, count - 1), EraseOperand(operands[count]))

\* Explicit state-mode to form-mode bridge. The current spellings coincide,
\* but this mapping prevents accidental raw-string coupling if either module's
\* representation changes.
\* @type: Str => Str;
ModeShape(mode) ==
  CASE mode = "real" -> "real"
    [] mode = "virtual8086" -> "virtual8086"
    [] mode = "protected" -> "protected"
    [] mode = "compatibility" -> "compatibility"
    [] mode = "long64" -> "long64"
    [] OTHER -> "invalid-mode"

\* @type: ($amd64OperandContext, $amd64ExecutableInstruction) =>
\*   {formId: Str, mode: Str, operandSize: Int, addressSize: Int,
\*    prefixes: Set(Str), operands: Seq({kind: Str, width: Int,
\*      encodedWidth: Int, semanticWidth: Int, extension: Str,
\*      identity: Str, sourceText: Str, accessIntent: Str, evaluationOrder: Int}),
\*    encodingFamily: Str, rexPresent: Bool, highByteRegister: Bool,
\*    prefixConflict: Bool};
EraseInstruction(context, instruction) ==
  [formId |-> instruction.formId,
   mode |-> ModeShape(context.mode),
   operandSize |-> instruction.operandSize,
   addressSize |-> instruction.addressSize,
   prefixes |-> instruction.prefixes,
   operands |-> EraseOperands(instruction.operands, Len(instruction.operands)),
   encodingFamily |-> instruction.encodingFamily,
   rexPresent |-> "rex" \in instruction.prefixes \/ "rex-w" \in instruction.prefixes,
   highByteRegister |-> \E index \in 1..Len(instruction.operands) :
     instruction.operands[index].ref.kind = "gpr" /\
     instruction.operands[index].ref.gprView = "high8",
   prefixConflict |-> FALSE]

\* Per-operand extension/code evidence prevents impossible byte-register
\* selection from being hidden by shape erasure. VEX/XOP provide extended
\* syntax without a separate REX byte; legacy encoding needs REX.
\* @type: ($amd64OperandContext, $amd64ExecutableInstruction, Int) => Bool;
OperandEncodingWellFormed(context, instruction, index) ==
  LET operand == instruction.operands[index]
      ref == operand.ref
      rexPresent == "rex" \in instruction.prefixes \/ "rex-w" \in instruction.prefixes
      extendedSyntax == rexPresent \/ instruction.encodingFamily # "legacy"
  IN CASE ref.kind = "gpr" ->
       /\ operand.registerExtension = (ref.gprIndex >= 8)
       /\ operand.byteCode4To7 =
            (ref.gprView = "high8" \/ (ref.gprIndex % 8) >= 4)
       /\ (~operand.registerExtension \/
            (context.mode = "long64" /\ extendedSyntax))
       /\ (ref.gprView # "high8" \/ (~extendedSyntax /\ ref.gprIndex \in 0..3))
       /\ (ref.gprView # "low8" \/ ref.gprIndex < 4 \/ extendedSyntax)
     [] ref.kind \in {"memory", "far-pointer-memory"} ->
       (~ref.address.baseExtended /\ ~ref.address.indexExtended) \/
         (context.mode = "long64" /\ extendedSyntax)
     [] ref.kind \in {"xmm", "vector"} ->
       /\ ref.vectorIndex < 16
       /\ ~operand.byteCode4To7
       /\ operand.registerExtension = (ref.vectorIndex >= 8)
       /\ (~operand.registerExtension \/
            (context.mode = "long64" /\ extendedSyntax))
     [] OTHER -> ~operand.registerExtension /\ ~operand.byteCode4To7

\* @type: ($amd64OperandProfile, $amd64OperandContext, Int,
\*   $amd64ExecutableInstruction) => Set(Int);
InvalidPayloadIndices(profile, context, defaultAddressSize, instruction) ==
  {index \in 1..(Len(instruction.operands) + Len(instruction.implicitResources)) :
    IF index <= Len(instruction.operands)
    THEN ~OperandRefWellFormed(profile, context, defaultAddressSize,
           instruction.operands[index].ref) \/
         ~OperandEncodingWellFormed(context, instruction, index)
    ELSE ~OperandRefWellFormed(profile, context, defaultAddressSize,
           instruction.implicitResources[index - Len(instruction.operands)])}

\* @type: ($amd64OperandProfile, $amd64OperandContext, Int,
\*   $amd64FormConstraint, $amd64FormProfile, $amd64ExecutableInstruction) =>
\*   $amd64LegalityResult;
ValidateExecutable(architecture, context, defaultAddressSize,
                   form, formProfile, instruction) ==
  IF InvalidPayloadIndices(architecture, context, defaultAddressSize, instruction) # {}
  THEN [kind |-> "normalization-error", reasons |-> {"operand-payload-invalid"},
        obligations |-> {}]
  ELSE Forms!ValidateDecoded(form, EraseInstruction(context, instruction), formProfile)

=============================================================================
