------------------------ MODULE AMD64External ------------------------
EXTENDS Integers, Sequences, FiniteSets, AMD64ArchitecturalState

\* D2 execution semantics whose results depend on processor/environment data.
\* Authority: AMD APM Volume 3 rev. 3.38 entries V3-GP-001/2/3/4,
\* 048/49/50/51, 071/74/75/79/82/85/86/94/96/101,
\* 115/116/117/118/119/139/149; Volume 1 rev. 3.25 section 5.12;
\* and the referenced Volume 2 system dependencies.

DecimalKinds == {"aaa", "aad", "aam", "aas", "daa", "das"}
EntropyKinds == {"rdrand", "rdseed"}
WakeCauses == {"matchingStore", "timerExpired", "interrupt", "nmi", "smi",
                "init", "reset", "farTransfer"}
StatusFlagNames == {"cf", "pf", "af", "zf", "sf", "of"}

RECURSIVE NatBit(_, _)
\* @type: (Int, Int) => Bool;
NatBit(value, bit) ==
  IF bit = 1 THEN value % 2 = 1 ELSE NatBit(value \div 2, bit - 1)

\* @type: Int => $amd64Bits;
NatWord(value) == [bit \in 1..64 |-> NatBit(value, bit)]

RECURSIVE BitsToNat(_, _)
\* Bounded unsigned decoding. Callers use at most 32 bits in checked rules.
\* @type: ($amd64Bits, Int) => Int;
BitsToNat(value, width) ==
  IF width = 0 THEN 0
  ELSE BitsToNat(value, width - 1) + IF value[width] THEN 2 ^ (width - 1) ELSE 0

\* @type: ($amd64Bits, Int, $amd64Bits) => $amd64Bits;
WriteGPRWord(before, width, value) == [bit \in 1..64 |->
  IF bit <= width THEN value[bit]
  ELSE IF width = 32 THEN FALSE ELSE before[bit]]

\* @type: ($amd64CPUState, Int, Int, $amd64Bits, $amd64CPUState) => Bool;
WriteLowGPRAllowed(before, register, width, value, after) ==
  /\ register \in 0..15 /\ width \in {8, 16, 32, 64}
  /\ IF before.execution.mode # "long64" /\ width = 32
     THEN \E stored \in [1..64 -> BOOLEAN] :
          /\ \A bit \in 1..32 : stored[bit] = value[bit]
          /\ after = [before EXCEPT !.gpr[register] = stored]
     ELSE after = [before EXCEPT !.gpr[register] =
                       WriteGPRWord(@, width, value)]

\* @type: ($amd64CPUState, Str, $amd64Bits, $amd64CPUState) => Bool;
WriteSegmentBase(before, segment, value, after) ==
  CASE segment = "fs" -> after = [before EXCEPT !.segments.fs.base = value]
    [] OTHER -> after = [before EXCEPT !.segments.gs.base = value]

\* @type: ($amd64Bits, Int) => Bool;
CanonicalWord(value, linearBits) ==
  /\ linearBits \in 1..64
  /\ \A bit \in (linearBits + 1)..64 : value[bit] = value[linearBits]

\* @type: Int => Bool;
ParityEven8(value) ==
  Cardinality({bit \in 1..8 : ((value \div (2 ^ (bit - 1))) % 2) = 1}) % 2 = 0

\* @type: (Int, Int) => Int;
AXValue(ah, al) == ((ah % 256) * 256) + (al % 256)

\* @type: (Str, Int, Int, Bool, Bool,
\*   {ax: Int, cf: Bool, af: Bool, pf: Bool, zf: Bool, sf: Bool,
\*    undefined: Set(Str)}) => Bool;
DecimalBody(kind, base, beforeAX, beforeAF, beforeCF, result) ==
  LET al == beforeAX % 256
      ah == (beforeAX \div 256) % 256
      lowAdjust == al % 16 > 9 \/ beforeAF
      highAdjust == al > 153 \/ beforeCF
  IN CASE kind = "aaa" ->
       LET adjusted == IF lowAdjust THEN (beforeAX + 262) % 65536 ELSE beforeAX
       IN /\ result.ax = AXValue(adjusted \div 256, adjusted % 16)
       /\ result.cf = lowAdjust /\ result.af = lowAdjust
       /\ result.undefined = {"of", "sf", "zf", "pf"}
     [] kind = "aas" ->
       LET adjusted == IF lowAdjust THEN (beforeAX + 65536 - 262) % 65536 ELSE beforeAX
       IN /\ result.ax = AXValue(adjusted \div 256, adjusted % 16)
       /\ result.cf = lowAdjust /\ result.af = lowAdjust
       /\ result.undefined = {"of", "sf", "zf", "pf"}
     [] kind = "aad" ->
       LET value == (base * ah + al) % 256 IN
       /\ result.ax = AXValue(0, value)
       /\ result.pf = ParityEven8(value) /\ result.zf = (value = 0)
       /\ result.sf = (value >= 128)
       /\ result.undefined = {"of", "af", "cf"}
     [] kind = "aam" ->
       /\ base # 0
       /\ result.ax = AXValue(al \div base, al % base)
       /\ result.pf = ParityEven8(al % base) /\ result.zf = (al % base = 0)
       /\ result.sf = (al % base >= 128)
       /\ result.undefined = {"of", "af", "cf"}
     [] kind = "daa" ->
       LET low == IF lowAdjust THEN al + 6 ELSE al
           value == (low + IF highAdjust THEN 96 ELSE 0) % 256
       IN /\ result.ax = AXValue(ah, value)
          /\ result.af = (beforeAF \/ lowAdjust)
          /\ result.cf = (beforeCF \/ highAdjust)
          /\ result.pf = ParityEven8(value) /\ result.zf = (value = 0)
          /\ result.sf = (value >= 128) /\ result.undefined = {"of"}
     [] OTHER ->
       LET low == IF lowAdjust THEN al + 250 ELSE al
           value == (low + IF highAdjust THEN 160 ELSE 0) % 256
       IN /\ result.ax = AXValue(ah, value)
          /\ result.af = (beforeAF \/ lowAdjust)
          /\ result.cf = (beforeCF \/ highAdjust)
          /\ result.pf = ParityEven8(value) /\ result.zf = (value = 0)
          /\ result.sf = (value >= 128) /\ result.undefined = {"of"}

\* @type: (Str, Str, Int, Int, Bool, Bool, Str) => Bool;
DecimalDisposition(mode, kind, base, beforeAX, beforeAF, beforeCF, disposition) ==
  /\ kind \in DecimalKinds
  /\ CASE mode = "long64" -> disposition = "UD"
       [] kind = "aam" /\ base = 0 -> disposition = "DE"
       [] OTHER -> disposition = "bodyApplied"

\* @type: Str => Set(Str);
DecimalUndefined(kind) ==
  CASE kind \in {"aaa", "aas"} -> {"of", "sf", "zf", "pf"}
    [] kind \in {"aad", "aam"} -> {"of", "af", "cf"}
    [] OTHER -> {"of"}

\* Canonical CPU binding. Undefined status flags range over BOOLEAN while all
\* non-status rFLAGS fields and all unrelated CPU fields are framed.
\* @type: (Str, Int, $amd64CPUState, $amd64CPUState, Str) => Bool;
DecimalCPUTransition(kind, base, before, after, disposition) ==
  LET beforeAX == BitsToNat(before.gpr[0], 16)
  IN /\ DecimalDisposition(before.execution.mode, kind, base, beforeAX,
                            before.rflags.af, before.rflags.cf, disposition)
     /\ CASE disposition \in {"UD", "DE"} -> after = before
          [] OTHER ->
             LET result == [ax |-> BitsToNat(after.gpr[0], 16),
                  cf |-> after.rflags.cf, af |-> after.rflags.af,
                  pf |-> after.rflags.pf, zf |-> after.rflags.zf,
                  sf |-> after.rflags.sf, undefined |-> DecimalUndefined(kind)]
                 valued == [after EXCEPT !.rflags = before.rflags]
             IN /\ DecimalBody(kind, base, beforeAX, before.rflags.af,
                               before.rflags.cf, result)
                /\ WriteLowGPRAllowed(before, 0, 16, NatWord(result.ax), valued)
                /\ [after.rflags EXCEPT !.cf = before.rflags.cf,
                     !.pf = before.rflags.pf, !.af = before.rflags.af,
                     !.zf = before.rflags.zf, !.sf = before.rflags.sf,
                     !.of = before.rflags.of] = before.rflags

\* CPUID profiles contain exact (function, subfunction) rows.  An absent row is
\* modeling-unavailable rather than an invented all-zero response.
\* @type: (Seq({function: Int, subfunction: Int, eax: Int, ebx: Int,
\*   ecx: Int, edx: Int}), Int, Int,
\*   {kind: Str, eax: Int, ebx: Int, ecx: Int, edx: Int}) => Bool;
CPUIDQuery(rows, function, subfunction, result) ==
  LET matches == {row \in {rows[index] : index \in 1..Len(rows)} :
                    row.function = function /\ row.subfunction = subfunction}
  IN CASE matches = {} -> result.kind = "modelingUnavailable"
       [] OTHER -> \E row \in matches :
          /\ result.kind = "bodyApplied"
          /\ result.eax = row.eax /\ result.ebx = row.ebx
          /\ result.ecx = row.ecx /\ result.edx = row.edx

\* @type: ({supported: Bool, userDisable: Bool,
\*   rows: Seq({function: Int, subfunction: Int, eax: Int, ebx: Int,
\*              ecx: Int, edx: Int})},
\*   $amd64CPUState, $amd64CPUState, Str) => Bool;
CPUIDCPUTransition(profile, before, after, disposition) ==
  LET function == BitsToNat(before.gpr[0], 32)
      subfunction == BitsToNat(before.gpr[1], 32)
      matches == {row \in {profile.rows[index] : index \in 1..Len(profile.rows)} :
        row.function = function /\ row.subfunction = subfunction}
  IN CASE ~profile.supported -> disposition = "UD" /\ after = before
       [] profile.userDisable /\ before.execution.cpl > 0 ->
            disposition = "GP" /\ after = before
       [] matches = {} -> disposition = "modelingUnavailable" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
          \E row \in matches :
            LET eax == [before EXCEPT !.gpr[0] = WriteGPRWord(@, 32, NatWord(row.eax))]
                ebx == [eax EXCEPT !.gpr[3] = WriteGPRWord(@, 32, NatWord(row.ebx))]
                ecx == [ebx EXCEPT !.gpr[1] = WriteGPRWord(@, 32, NatWord(row.ecx))]
            IN after = [ecx EXCEPT !.gpr[2] = WriteGPRWord(@, 32, NatWord(row.edx))]

\* @type: ({kind: Str, width: Int, valid: Bool, value: Int,
\*   provenance: Str}) => Bool;
EntropySampleWellFormed(sample) ==
  /\ sample.kind \in EntropyKinds
  /\ sample.width \in {16, 32, 64}
  /\ sample.provenance # ""
  /\ (sample.kind = "rdseed" /\ ~sample.valid => sample.value = 0)

\* @type: (Str, Int, Set({kind: Str, width: Int, valid: Bool,
\*   value: Int, provenance: Str}),
\*   {kind: Str, valid: Bool, value: Int}) => Bool;
EntropyStep(kind, width, environment, result) ==
  LET matches == {sample \in environment :
                    EntropySampleWellFormed(sample) /\
                    sample.kind = kind /\ sample.width = width}
  IN CASE matches = {} -> result.kind = "modelingUnavailable"
       [] OTHER -> \E sample \in matches :
          /\ result.kind = "bodyApplied"
          /\ result.valid = sample.valid /\ result.value = sample.value

\* @type: (Bool, Str, Int, Int,
\*   {kind: Str, width: Int, valid: Bool, value: $amd64Bits,
\*    provenance: Str}, $amd64CPUState, $amd64CPUState, Str) => Bool;
EntropySampleCPUTransition(supported, kind, width, destination, sample,
                           before, after, disposition) ==
  CASE ~supported -> disposition = "UD" /\ after = before
    [] sample.kind # kind \/ sample.width # width \/ sample.provenance = "" ->
         disposition = "modelingUnavailable" /\ after = before
    [] kind = "rdseed" /\ ~sample.valid /\
       \E bit \in 1..width : sample.value[bit] ->
         disposition = "modelingUnavailable" /\ after = before
    [] OTHER -> disposition = "bodyApplied" /\
         /\ WriteLowGPRAllowed(before, destination, width, sample.value,
              [after EXCEPT !.rflags = before.rflags])
         /\ after.rflags = [before.rflags EXCEPT !.cf = sample.valid,
              !.of = FALSE, !.sf = FALSE, !.zf = FALSE,
              !.af = FALSE, !.pf = FALSE]

\* Reflected Castagnoli polynomial 82F63B78h, represented as set bits so TLC
\* never coerces the unsigned 32-bit pattern through a signed host integer.
CRCPolynomial == [bit \in 1..64 |->
  bit \in {4, 5, 6, 7, 9, 10, 12, 13, 14, 18, 19, 21, 22, 23, 24, 26, 32}]

\* @type: ($amd64Bits, Bool) => $amd64Bits;
CRC32CBit(crc, inputBit) ==
  LET mix == crc[1] /= inputBit
      shifted == [bit \in 1..64 |-> IF bit < 32 THEN crc[bit + 1] ELSE FALSE]
  IN [bit \in 1..64 |-> shifted[bit] /= (mix /\ CRCPolynomial[bit])]

RECURSIVE CRC32CBits(_, _, _, _)
\* @type: ($amd64Bits, Int, Int, $amd64Bits) => $amd64Bits;
CRC32CBits(source, width, index, crc) ==
  IF index > width THEN crc
  ELSE CRC32CBits(source, width, index + 1, CRC32CBit(crc, source[index]))

\* @type: (Bool, Int, Int, Int, $amd64Bits, $amd64CPUState,
\*   $amd64CPUState, Str) => Bool;
CRC32CPUTransition(supported, destination, destinationWidth, sourceWidth,
                   source, before, after, disposition) ==
  LET widthValid ==
        (destinationWidth = 32 /\ sourceWidth \in {8, 16, 32}) \/
        (destinationWidth = 64 /\ sourceWidth \in {8, 64})
      result == CRC32CBits(source, sourceWidth, 1, before.gpr[destination])
  IN CASE ~supported -> disposition = "UD" /\ after = before
       [] ~widthValid -> disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, destinationWidth,
                               result, after)

\* XMM scalar writes zero through bit 127 and preserve the canonical upper
\* vector bank.  MMX writes set bits 79:64, clear TOP, and mark every tag full.
\* @type: ($amd64Bits, Int, $amd64Bits, $amd64Bits) => Bool;
XMMScalarWrite(before, width, value, after) ==
  /\ width \in {32, 64}
  /\ \A bit \in 1..512 : after[bit] =
       IF bit <= width THEN value[bit]
       ELSE IF bit <= 128 THEN FALSE ELSE before[bit]

\* @type: ($amd64X87, Int, Int, $amd64Bits, $amd64X87) => Bool;
MMXScalarWrite(before, register, width, value, after) ==
  /\ register \in 0..7 /\ width \in {32, 64}
  /\ after.status = [before.status EXCEPT !.top = 0]
  /\ \A index \in 0..7 : after.tags[index] = "valid"
  /\ \A bit \in 1..80 : after.physical[register][bit] =
       IF bit <= width THEN value[bit] ELSE IF bit <= 64 THEN FALSE ELSE TRUE
  /\ \A index \in 0..7 \ {register} : after.physical[index] = before.physical[index]
  /\ after.control = before.control
  /\ after.lastInstruction = before.lastInstruction
  /\ after.lastData = before.lastData
  /\ after.lastOpcode = before.lastOpcode

\* @type: ($amd64Bits) => $amd64Bits;
MOVMSKPD(source) == [bit \in 1..64 |->
  IF bit = 1 THEN source[64] ELSE IF bit = 2 THEN source[128] ELSE FALSE]
\* @type: ($amd64Bits) => $amd64Bits;
MOVMSKPS(source) == [bit \in 1..64 |->
  CASE bit = 1 -> source[32] [] bit = 2 -> source[64]
    [] bit = 3 -> source[96] [] bit = 4 -> source[128] [] OTHER -> FALSE]

\* @type: ({supported: Bool, emulateFP: Bool, taskSwitched: Bool,
\*   osfxsr: Bool},
\*   $amd64CPUState, Int, Int, $amd64Bits, $amd64CPUState, Str) => Bool;
MOVDToXMMCPUTransition(profile, before, destination, width, value,
                       after, disposition) ==
  LET registerLimit == IF before.execution.mode = "long64" THEN 16 ELSE 8
  IN CASE ~profile.supported \/ profile.emulateFP \/ ~profile.osfxsr ->
            disposition = "UD" /\ after = before
       [] profile.taskSwitched ->
            disposition = "NM" /\ after = before
       [] ~before.execution.features.sseEnabled ->
            disposition = "modelingUnavailable" /\ after = before
       [] destination \notin 0..(registerLimit - 1) \/ width \notin {32, 64} ->
            disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            /\ XMMScalarWrite(before.vectors[destination], width, value,
                              after.vectors[destination])
            /\ [after EXCEPT !.vectors = before.vectors] = before

\* @type: ({supported: Bool, emulateFP: Bool, taskSwitched: Bool,
\*   pendingX87: Bool}, $amd64CPUState, Int, Int, $amd64Bits,
\*   $amd64CPUState, Str) => Bool;
MOVDToMMXCPUTransition(profile, before, destination, width, value,
                       after, disposition) ==
  CASE ~profile.supported \/ profile.emulateFP ->
         disposition = "UD" /\ after = before
    [] profile.taskSwitched -> disposition = "NM" /\ after = before
    [] profile.pendingX87 -> disposition = "MF" /\ after = before
    [] destination \notin 0..7 \/ width \notin {32, 64} ->
         disposition = "formRejected" /\ after = before
    [] OTHER -> disposition = "bodyApplied" /\
         /\ MMXScalarWrite(before.x87, destination, width, value, after.x87)
         /\ [after EXCEPT !.x87 = before.x87] = before

\* @type: ({supported: Bool, emulateFP: Bool, taskSwitched: Bool,
\*   osfxsr: Bool},
\*   $amd64CPUState, Int, Int, Int, $amd64CPUState, Str) => Bool;
MOVDFromXMMCPUTransition(profile, before, destination, source, width,
                         after, disposition) ==
  LET registerLimit == IF before.execution.mode = "long64" THEN 16 ELSE 8
      value == [bit \in 1..64 |-> before.vectors[source][bit]]
  IN CASE ~profile.supported \/ profile.emulateFP \/ ~profile.osfxsr ->
            disposition = "UD" /\ after = before
       [] profile.taskSwitched ->
            disposition = "NM" /\ after = before
       [] ~before.execution.features.sseEnabled ->
            disposition = "modelingUnavailable" /\ after = before
       [] source \notin 0..(registerLimit - 1) \/ width \notin {32, 64} ->
            disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, width, value, after)

\* @type: ({supported: Bool, emulateFP: Bool, taskSwitched: Bool,
\*   pendingX87: Bool}, $amd64CPUState, Int, Int, Int,
\*   $amd64CPUState, Str) => Bool;
MOVDFromMMXCPUTransition(profile, before, destination, source, width,
                         after, disposition) ==
  LET value == ReadMMX(before.x87, source)
  IN CASE ~profile.supported \/ profile.emulateFP ->
            disposition = "UD" /\ after = before
       [] profile.taskSwitched -> disposition = "NM" /\ after = before
       [] profile.pendingX87 -> disposition = "MF" /\ after = before
       [] source \notin 0..7 \/ width \notin {32, 64} ->
            disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, width, value, after)

\* @type: ({supported: Bool, emulateFP: Bool, taskSwitched: Bool,
\*   osfxsr: Bool}, Str,
\*   $amd64CPUState, Int, Int, $amd64CPUState, Str) => Bool;
MOVMSKCPUTransition(profile, kind, before, destination, source,
                    after, disposition) ==
  LET registerLimit == IF before.execution.mode = "long64" THEN 16 ELSE 8
      mask == IF kind = "pd" THEN MOVMSKPD(ReadXMM(before.vectors, source))
              ELSE MOVMSKPS(ReadXMM(before.vectors, source))
  IN CASE ~profile.supported \/ profile.emulateFP \/ ~profile.osfxsr ->
            disposition = "UD" /\ after = before
       [] profile.taskSwitched ->
            disposition = "NM" /\ after = before
       [] ~before.execution.features.sseEnabled ->
            disposition = "modelingUnavailable" /\ after = before
       [] source \notin 0..(registerLimit - 1) ->
            disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, 32, mask, after)

\* @type: (Bool, Bool, Str, $amd64CPUState, Int, Int,
\*   $amd64CPUState, Str) => Bool;
ReadBaseCPUTransition(feature, enabled, segment, before, destination, width,
                      after, disposition) ==
  LET value == IF segment = "fs" THEN before.segments.fs.base
               ELSE before.segments.gs.base
  IN CASE before.execution.mode # "long64" \/ ~feature \/ ~enabled ->
            disposition = "UD" /\ after = before
       [] segment \notin {"fs", "gs"} \/ width \notin {32, 64} ->
            disposition = "formRejected" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, width, value, after)

\* @type: (Bool, Bool, Int, Str, $amd64CPUState, $amd64Bits, Int,
\*   $amd64CPUState, Str) => Bool;
WriteBaseCPUTransition(feature, enabled, linearBits, segment, before, source,
                       width, after, disposition) ==
  LET value == IF width = 32
               THEN WriteGPRWord([bit \in 1..64 |-> FALSE], 32, source)
               ELSE source
  IN CASE before.execution.mode # "long64" \/ ~feature \/ ~enabled ->
            disposition = "UD" /\ after = before
       [] segment \notin {"fs", "gs"} \/ width \notin {32, 64} ->
            disposition = "formRejected" /\ after = before
       [] ~CanonicalWord(value, linearBits) -> disposition = "GP" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteSegmentBase(before, segment, value, after)

\* @type: (Bool, $amd64Bits, $amd64CPUState, Int,
\*   $amd64CPUState, Str) => Bool;
RDPIDCPUTransition(supported, tscAux, before, destination, after, disposition) ==
  LET width == IF before.execution.mode = "long64" THEN 64 ELSE 32
  IN CASE ~supported -> disposition = "UD" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            WriteLowGPRAllowed(before, destination, width, tscAux, after)

\* @type: (Bool, Bool, $amd64Bits, $amd64Bits, Int, $amd64CPUState,
\*   $amd64CPUState, Str) => Bool;
RDPRUCPUTransition(supported, tsd, mperf, aperf, maxIndex, before,
                   after, disposition) ==
  LET index == BitsToNat(before.gpr[1], 32)
      value == IF index = 0 THEN mperf ELSE IF index = 1 THEN aperf
               ELSE [bit \in 1..64 |-> FALSE]
      low == [bit \in 1..64 |-> IF bit <= 32 THEN value[bit] ELSE FALSE]
      high == [bit \in 1..64 |-> IF bit <= 32 THEN value[bit + 32] ELSE FALSE]
      eax == [before EXCEPT !.gpr[0] = WriteGPRWord(@, 32, low)]
  IN CASE ~supported \/ (tsd /\ before.execution.cpl > 0) ->
            disposition = "UD" /\ after = before
       [] OTHER -> disposition = "bodyApplied" /\
            after = [eax EXCEPT !.gpr[2] = WriteGPRWord(@, 32, high)]

\* NOP and PAUSE body effects frame the entire canonical CPU state. Decode,
\* fetch, and RIP advancement are composed outside this body relation.
\* @type: ($amd64CPUState, $amd64CPUState) => Bool;
NOPCPUTransition(before, after) == after = before
\* @type: (Bool, $amd64CPUState, $amd64CPUState, Str) => Bool;
PAUSECPUTransition(recognized, before, after, disposition) ==
  IF recognized THEN disposition = "bodyApplied" /\ after = before
  ELSE disposition = "formRejected" /\ after = before

\* @type: ({monitorx: Bool, interruptBreak: Bool},
\*   {armed: Bool, base: Int, byteCount: Int, pending: Bool},
\*   Int, Int, {kind: Str,
\*     state: {armed: Bool, base: Int, byteCount: Int, pending: Bool}}) => Bool;
MonitorXStep(profile, before, linear, ecx, result) ==
  CASE ~profile.monitorx -> result.kind = "UD"
    [] ecx # 0 -> result.kind = "GP"
    [] OTHER -> /\ result.kind = "armed"
                /\ result.state = [before EXCEPT !.armed = TRUE,
                     !.base = linear, !.pending = TRUE]

\* @type: ({monitorx: Bool, interruptBreak: Bool},
\*   {armed: Bool, base: Int, byteCount: Int, pending: Bool},
\*   Int, Int, Set({cause: Str, elapsed: Int, matchingStore: Bool}),
\*   {kind: Str, cause: Str}) => Bool;
MWaitXStep(profile, monitor, ecx, ebx, observations, result) ==
  LET allowed == {event \in observations :
       /\ event.cause \in WakeCauses
       /\ (event.cause = "timerExpired" => ecx % 4 >= 2 /\ ebx # 0 /\ event.elapsed <= ebx)
       /\ (event.cause = "matchingStore" => monitor.armed /\ event.matchingStore)
       /\ (event.cause = "interrupt" /\ ecx % 2 = 1 => profile.interruptBreak)}
  IN CASE ~profile.monitorx -> result.kind = "UD"
       [] ecx \div 4 # 0 -> result.kind = "GP"
       [] allowed = {} -> result.kind = "modelingUnavailable"
       [] OTHER -> \E event \in allowed :
            result.kind = "woke" /\ result.cause = event.cause

\* LWP steps name every external memory/ring-buffer effect.  This is an
\* executable environment protocol, while entry completeness remains open
\* until Volume 2 Chapter 13 validation and record-layout rules are bound.
\* @type: ({operation: Str, beforeEnabled: Bool, afterEnabled: Bool,
\*   eventId: Int, memoryEffects: Seq(Str), result: Str}) => Bool;
LWPStepWellFormed(step) ==
  /\ step.operation \in {"flushOld", "validateNew", "disable", "insert"}
  /\ \A index \in 1..Len(step.memoryEffects) : step.memoryEffects[index] # ""
  /\ (step.operation = "flushOld" => step.beforeEnabled)
  /\ (step.operation = "validateNew" => step.afterEnabled)
  /\ (step.operation = "disable" => ~step.afterEnabled)
  /\ (step.operation = "insert" => step.beforeEnabled /\ step.eventId \in {1, 255})

=======================================================================
