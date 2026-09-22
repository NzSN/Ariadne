------------------- MODULE AMD64ControlExecution -------------------
EXTENDS Integers, Sequences, FiniteSets

Control == INSTANCE AMD64Control
MachineAccess == INSTANCE AMD64MachineAccess

\* Authoritative pure CPU/order layer for stack-family execution. Concrete
\* address resolution and byte effects are composed through AMD64MachineAccess;
\* this module does not invent a competing memory-access abstraction.
\*
\* Authority: AMD APM Volume 3 revision 3.38 pages 224-225, 262, 327-329,
\* 332-334, and 339-343. Fault-boundary policy additionally depends on Volume 2
\* revision 3.45 sections 8.1.1-8.1.4, pages 306-308.

\* @typeAlias: controlExecutionProjection = {rip: $amd64Bits,
\*   rcx: $amd64Bits, rsp: $amd64Bits, flags: $integerFlags, mode: Str,
\*   ssDefaultBig: Bool, csLimit: $amd64Bits};
\* @typeAlias: stackMicroOp = {kind: Str, index: Int, register: Str};
\* @typeAlias: integerFlags = Str -> Bool;
\* @typeAlias: amd64Bits = Int -> Bool;
\* @typeAlias: amd64RFlags = {cf: Bool, fixed1: Bool, pf: Bool,
\*   reserved3: Bool, af: Bool, reserved5: Bool, zf: Bool, sf: Bool,
\*   tf: Bool, interruptEnable: Bool, df: Bool, of: Bool, iopl: $amd64Bits,
\*   nestedTask: Bool, reserved15: Bool, resume: Bool, virtual8086: Bool,
\*   ac: Bool, virtualInterrupt: Bool, virtualInterruptPending: Bool,
\*   id: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: controlFeatures = {x87Enabled: Bool, sseEnabled: Bool,
\*   avxEnabled: Bool, avx512Enabled: Bool};
\* @typeAlias: controlContext = {mode: Str, cpl: Int,
\*   features: $controlFeatures};
\* @typeAlias: controlSegment = {selector: $amd64Bits, base: $amd64Bits,
\*   limit: $amd64Bits, present: Bool, dpl: Int, readable: Bool,
\*   writable: Bool, executable: Bool, conforming: Bool, expandDown: Bool,
\*   defaultBig: Bool, longMode: Bool, unusable: Bool};
\* @typeAlias: controlSegments = {cs: $controlSegment, ss: $controlSegment,
\*   ds: $controlSegment, es: $controlSegment, fs: $controlSegment,
\*   gs: $controlSegment};
\* @typeAlias: controlX87Status = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   stackFault: Bool, errorSummary: Bool, c0: Bool, c1: Bool, c2: Bool,
\*   top: Int, c3: Bool, busy: Bool};
\* @typeAlias: controlX87Control = {invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, reserved6: Bool, reserved7: Bool,
\*   precisionControl: Str, roundingControl: Str, infinityControl: Bool,
\*   reservedHigh: $amd64Bits};
\* @typeAlias: controlX87Pointer = {kind: Str, selector: $amd64Bits,
\*   offset64: $amd64Bits, offset32: $amd64Bits, linear32: $amd64Bits};
\* @typeAlias: controlX87 = {physical: Int -> $amd64Bits,
\*   tags: Int -> Str, status: $controlX87Status, control: $controlX87Control,
\*   lastInstruction: $controlX87Pointer, lastData: $controlX87Pointer,
\*   lastOpcode: $amd64Bits};
\* @typeAlias: controlMXCSR = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   denormalsAreZero: Bool, invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, roundingControl: Str, flushToZero: Bool,
\*   reserved16: Bool, misalignedMask: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: controlCPUState = {gpr: Int -> $amd64Bits,
\*   rip: $amd64Bits, rflags: $amd64RFlags, segments: $controlSegments,
\*   x87: $controlX87, vectors: Int -> $amd64Bits,
\*   kMask: Int -> $amd64Bits, mxcsr: $controlMXCSR,
\*   execution: $controlContext};
\* @typeAlias: amd64Byte = Int -> Bool;
\* @typeAlias: amd64Carry = Int -> Bool;
\* @typeAlias: controlCapabilities = {longMode: Bool, x87: Bool, mmx: Bool,
\*   sse: Bool, avx: Bool, avx512: Bool, mxcsrMisalignedMask: Bool};
\* @typeAlias: controlProfile = {capabilities: $controlCapabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};
\* @typeAlias: controlAccess = {kind: Str, stack: Bool,
\*   implicitSupervisor: Bool, shadow: Bool};
\* @typeAlias: controlSystemConfig = {virtualBits: Int, paging: Bool,
\*   a20Enabled: Bool, cr0AM: Bool, cr0WP: Bool, cr4PAE: Bool,
\*   cr4SMEP: Bool, cr4SMAP: Bool, cr4PKE: Bool, cr4CET: Bool,
\*   eferNXE: Bool, iopl: Int, pkruAD: Int -> Bool, pkruWD: Int -> Bool};
\* @typeAlias: controlPage = {linearTag: $amd64Bits,
\*   physicalTag: $amd64Bits, offsetBits: Int, present: Bool,
\*   writable: Bool, user: Bool, executable: Bool, reserved: Bool,
\*   shadowStack: Bool, protectionKey: Int};
\* @typeAlias: controlByteCell = {physical: $amd64Bits, value: $amd64Byte};
\* @typeAlias: controlConcreteMemory = {physicalBits: Int,
\*   defaultByte: $amd64Byte, overrides: Set($controlByteCell)};
\* @typeAlias: controlMachineState = {cpu: $controlCPUState,
\*   memory: $controlConcreteMemory};
\* @typeAlias: controlMemoryTypeResolution = {kind: Str,
\*   memoryType: Str, reason: Str};
\* @typeAlias: amd64StackRequest = {rawEffective: $amd64Bits,
\*   addressSize: Int, segment: Str, access: Str, byteCount: Int};
\* @typeAlias: controlStackPushPlan = {width: Int, oldRSP: $amd64Bits,
\*   newRSP: $amd64Bits, value: $amd64Bits, request: $amd64StackRequest};
\* @typeAlias: controlStackPopPlan = {width: Int, oldRSP: $amd64Bits,
\*   newRSP: $amd64Bits, request: $amd64StackRequest};
\* @typeAlias: controlMachineRequest = {rawEffective: $amd64Bits,
\*   addressSize: Int, segmentName: Str, access: $controlAccess,
\*   byteCount: Int, alignmentBits: Int,
\*   memoryType: $controlMemoryTypeResolution};
\* @typeAlias: controlSpanWitness = {effectiveBytes: Seq($amd64Bits),
\*   effectiveCarries: Seq($amd64Carry), segmentRawBytes: Seq($amd64Bits),
\*   segmentCarries: Seq($amd64Carry), linearBytes: Seq($amd64Bits)};
\* @typeAlias: controlResolvedSpan = {request: $controlMachineRequest,
\*   effectiveBytes: Seq($amd64Bits), linearBytes: Seq($amd64Bits),
\*   physicalBytes: Seq($amd64Bits),
\*   memoryType: $controlMemoryTypeResolution};
\* @typeAlias: controlByteEffect = {index: Int, physical: $amd64Bits,
\*   before: $amd64Byte, after: $amd64Byte};
\* @typeAlias: controlPushCertificate = {negativeSize: $amd64Bits,
\*   negateCarry: $amd64Carry, subtractCarry: $amd64Carry,
\*   controlPlan: $controlStackPushPlan, spanWitness: $controlSpanWitness,
\*   resolved: $controlResolvedSpan, writes: Set($controlByteEffect),
\*   memoryType: $controlMemoryTypeResolution, afterCPU: $controlCPUState};
\* @typeAlias: controlPopCertificate = {fullSum: $amd64Bits,
\*   carry: $amd64Carry, controlPlan: $controlStackPopPlan,
\*   spanWitness: $controlSpanWitness, resolved: $controlResolvedSpan,
\*   bytes: Seq($amd64Byte), value: $amd64Bits,
\*   memoryType: $controlMemoryTypeResolution, afterCPU: $controlCPUState};
\* @typeAlias: controlPopGPRCertificate = {pop: $controlPopCertificate,
\*   afterPop: $controlMachineState, afterCPU: $controlCPUState};
\* @typeAlias: controlReadCertificate = {negativeSize: $amd64Bits,
\*   negateCarry: $amd64Carry, subtractCarry: $amd64Carry,
\*   rawAddress: $amd64Bits, spanWitness: $controlSpanWitness,
\*   resolved: $controlResolvedSpan, bytes: Seq($amd64Byte),
\*   value: $amd64Bits, memoryType: $controlMemoryTypeResolution};
\* @typeAlias: controlEnterCertificate = {
\*   initialPush: $controlPushCertificate,
\*   afterInitial: $controlMachineState, framePointer: $amd64Bits,
\*   readCertificates: Seq($controlReadCertificate),
\*   pushCertificates: Seq($controlPushCertificate),
\*   copyMachines: Seq($controlMachineState),
\*   afterCopies: $controlMachineState,
\*   framePush: $controlPushCertificate,
\*   afterNested: $controlMachineState,
\*   allocationNegative: $amd64Bits,
\*   allocationNegateCarry: $amd64Carry,
\*   allocationSubtractCarry: $amd64Carry,
\*   allocationFullSum: $amd64Bits, finalRSP: $amd64Bits,
\*   finalWitness: $controlSpanWitness,
\*   finalResolved: $controlResolvedSpan,
\*   finalMemoryType: $controlMemoryTypeResolution,
\*   afterSPCPU: $controlCPUState, afterCPU: $controlCPUState};

StackMicroKinds == {"push-register", "pop-register", "discard-pop",
  "push-old-rbp", "read-frame", "push-frame", "push-frame-pointer",
  "final-access-check"}

RECURSIVE WordBytes(_, _)

\* @type: Str => Int;
GPRIndex(name) ==
  CASE name = "rax" -> 0 [] name = "rcx" -> 1
    [] name = "rdx" -> 2 [] name = "rbx" -> 3
    [] name = "rsp" -> 4 [] name = "rbp" -> 5
    [] name = "rsi" -> 6 [] OTHER -> 7

\* @type: $controlCPUState => $controlExecutionProjection;
ControlProjection(cpu) == [
  rip |-> cpu.rip,
  rcx |-> cpu.gpr[GPRIndex("rcx")],
  rsp |-> cpu.gpr[GPRIndex("rsp")],
  flags |-> [name \in Control!Integer!Flags |->
    CASE name = "cf" -> cpu.rflags.cf
      [] name = "pf" -> cpu.rflags.pf
      [] name = "af" -> cpu.rflags.af
      [] name = "zf" -> cpu.rflags.zf
      [] name = "sf" -> cpu.rflags.sf
      [] OTHER -> cpu.rflags.of],
  mode |-> cpu.execution.mode,
  ssDefaultBig |-> cpu.segments.ss.defaultBig,
  csLimit |-> [bit \in 1..64 |->
    IF bit <= 32 THEN cpu.segments.cs.limit[bit] ELSE FALSE]]

\* @type: ($controlCPUState, Int) => Str;
StackPointerView(cpu, width) ==
  IF width = 16 THEN "low16" ELSE IF width = 32 THEN "low32" ELSE "full64"

\* @type: ($controlCPUState, Int) => Str;
BasePointerView(cpu, width) == StackPointerView(cpu, width)

\* @type: (Str, $amd64Bits, $amd64Bits, Str, $amd64Bits) => Bool;
WriteViewAllowed(mode, before, value, view, candidate) ==
  LET width == IF view = "low16" THEN 16 ELSE IF view = "low32" THEN 32 ELSE 64
  IN IF mode # "long64" /\ view = "low32"
     THEN /\ \A bit \in 1..32 : candidate[bit] = value[bit]
          /\ \A bit \in 1..64 : candidate[bit] \in BOOLEAN
     ELSE candidate = [bit \in 1..64 |->
       IF bit <= width THEN value[bit]
       ELSE IF view = "low32" THEN FALSE ELSE before[bit]]

\* @type: (Str, Int) => Str;
NamedGPRView(name, width) ==
  IF width = 16 THEN "low16" ELSE IF width = 32 THEN "low32" ELSE "full64"

\* @type: ($controlCPUState, Str, Int, $amd64Bits, $controlCPUState) => Bool;
WriteNamedGPRAllowed(before, name, width, value, after) ==
  LET index == GPRIndex(name)
      view == NamedGPRView(name, width)
  IN /\ name \in {"rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"}
     /\ width \in {16, 32, 64}
     /\ WriteViewAllowed(before.execution.mode, before.gpr[index], value,
                         view, after.gpr[index])
     /\ after = [before EXCEPT !.gpr[index] = after.gpr[index]]

\* @type: ($controlCPUState, Str, Int) => $amd64Bits;
ReadNamedGPRValue(cpu, name, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN cpu.gpr[GPRIndex(name)][bit]
                         ELSE FALSE]

\* These relations preserve legacy dword upper-bit nondeterminism by reusing
\* IntegerExecution.WriteViewAllowed rather than selecting one witness.
\* @type: ($controlCPUState, $amd64Bits, $controlCPUState) => Bool;
WriteStackPointerAllowed(before, value, after) ==
  LET width == Control!StackAddressSize(ControlProjection(before))
      view == StackPointerView(before, width)
      index == GPRIndex("rsp")
  IN /\ WriteViewAllowed(before.execution.mode,
         before.gpr[index], value, view, after.gpr[index])
     /\ after = [before EXCEPT !.gpr[index] = after.gpr[index]]

\* @type: ($controlCPUState, Int, $amd64Bits, $controlCPUState) => Bool;
WriteBasePointerAllowed(before, width, value, after) ==
  LET view == BasePointerView(before, width)
      index == GPRIndex("rbp")
  IN /\ width \in {16, 32, 64}
     /\ WriteViewAllowed(before.execution.mode,
         before.gpr[index], value, view, after.gpr[index])
     /\ after = [before EXCEPT !.gpr[index] = after.gpr[index]]

\* @type: $amd64RFlags => $amd64Bits;
RFlagsWord(flags) == [bit \in 1..64 |->
  CASE bit = 1 -> flags.cf
    [] bit = 2 -> flags.fixed1
    [] bit = 3 -> flags.pf
    [] bit = 4 -> flags.reserved3
    [] bit = 5 -> flags.af
    [] bit = 6 -> flags.reserved5
    [] bit = 7 -> flags.zf
    [] bit = 8 -> flags.sf
    [] bit = 9 -> flags.tf
    [] bit = 10 -> flags.interruptEnable
    [] bit = 11 -> flags.df
    [] bit = 12 -> flags.of
    [] bit = 13 -> flags.iopl[1]
    [] bit = 14 -> flags.iopl[2]
    [] bit = 15 -> flags.nestedTask
    [] bit = 16 -> flags.reserved15
    [] bit = 17 -> flags.resume
    [] bit = 18 -> flags.virtual8086
    [] bit = 19 -> flags.ac
    [] bit = 20 -> flags.virtualInterrupt
    [] bit = 21 -> flags.virtualInterruptPending
    [] bit = 22 -> flags.id
    [] OTHER -> flags.reservedHigh[bit - 22]]

\* @type: ($amd64RFlags, $amd64Bits) => $amd64RFlags;
RFlagsFromWord(before, word) == [before EXCEPT
  !.cf = word[1], !.fixed1 = word[2], !.pf = word[3],
  !.reserved3 = word[4], !.af = word[5], !.reserved5 = word[6],
  !.zf = word[7], !.sf = word[8], !.tf = word[9],
  !.interruptEnable = word[10], !.df = word[11], !.of = word[12],
  !.iopl = [index \in 1..2 |-> word[index + 12]],
  !.nestedTask = word[15], !.reserved15 = word[16],
  !.resume = word[17], !.virtual8086 = word[18], !.ac = word[19],
  !.virtualInterrupt = word[20], !.virtualInterruptPending = word[21],
  !.id = word[22],
  !.reservedHigh = [index \in 1..42 |-> word[index + 22]]]

\* @type: $amd64RFlags => Int;
IOPLValue(flags) == (IF flags.iopl[1] THEN 1 ELSE 0) +
                    (IF flags.iopl[2] THEN 2 ELSE 0)

\* @type: ($controlCPUState, $amd64Bits, Int) => $controlCPUState;
ApplyPoppedFlags(cpu, popped, width) ==
  LET image == Control!PopFlagImage(RFlagsWord(cpu.rflags), popped, width,
        cpu.execution.mode, cpu.execution.cpl, IOPLValue(cpu.rflags))
  IN [cpu EXCEPT !.rflags = RFlagsFromWord(@, image)]

\* @type: ($amd64Bits, Int) => $amd64Byte;
WordByte(word, index) == [bit \in 1..8 |-> word[(index - 1) * 8 + bit]]

\* @type: ($amd64Bits, Int) => Seq($amd64Byte);
WordBytes(word, count) ==
  IF count <= 0 THEN <<>> ELSE Append(WordBytes(word, count - 1),
                                      WordByte(word, count))

\* @type: Seq($amd64Byte) => $amd64Bits;
WordFromBytes(bytes) == [bit \in 1..64 |->
  LET byteIndex == ((bit - 1) \div 8) + 1
      byteBit == ((bit - 1) % 8) + 1
  IN IF byteIndex <= Len(bytes) THEN bytes[byteIndex][byteBit] ELSE FALSE]

UnknownMemoryType == [kind |-> "unknown", memoryType |-> "UC",
                      reason |-> "control-body-memory-type-unbound"]

\* @type: ($amd64StackRequest, Str, $controlMemoryTypeResolution)
\*   => $controlMachineRequest;
MachineStackRequest(request, kind, memoryType) == [
  rawEffective |-> request.rawEffective,
  addressSize |-> request.addressSize,
  segmentName |-> "ss",
  access |-> [kind |-> kind, stack |-> TRUE,
              implicitSupervisor |-> FALSE, shadow |-> FALSE],
  byteCount |-> request.byteCount,
  alignmentBits |-> 0,
  memoryType |-> memoryType]

\* A successful push commits all planned bytes as the instruction body. This
\* says nothing about retirement. Fault paths do not use this relation and do
\* not infer a committed prefix.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, $amd64Bits, Int, $controlPushCertificate,
\*   $controlMachineState) => Bool;
PushBodyApplied(architecture, config, pageMap, before, value, width,
                certificate, after) ==
  /\ Control!StackPushPlan(ControlProjection(before.cpu), value, width,
       certificate.negativeSize, certificate.negateCarry,
       certificate.subtractCarry, certificate.controlPlan)
  /\ LET request == MachineStackRequest(certificate.controlPlan.request, "write",
                                        certificate.memoryType)
      bytes == WordBytes(certificate.controlPlan.value, width \div 8)
      effectPlan == [writes |-> certificate.writes,
        commitPolicy |-> "bodyAll", committed |-> Cardinality(certificate.writes)]
     IN /\ certificate.controlPlan.width = width
     /\ MachineAccess!ResolveSpan(architecture, config, before.cpu, pageMap,
           request, certificate.spanWitness, certificate.resolved)
     /\ MachineAccess!PlanWrites(before.memory, certificate.resolved, bytes,
                                 certificate.writes)
     /\ WriteStackPointerAllowed(before.cpu,
           certificate.controlPlan.newRSP, certificate.afterCPU)
     /\ MachineAccess!BodyApplied(before, certificate.afterCPU, effectPlan, after)

\* Successful pop: exact bytes are read before the address-sized SP update.
\* There are no memory writes in the body effect plan.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, $controlPopCertificate,
\*   $controlMachineState) => Bool;
PopStackBodyApplied(architecture, config, pageMap, before, width,
                    certificate, after) ==
  /\ Control!StackPopPlan(ControlProjection(before.cpu), width,
       certificate.fullSum, certificate.carry, certificate.controlPlan)
  /\ LET request == MachineStackRequest(certificate.controlPlan.request, "read",
                                        certificate.memoryType)
      emptyPlan == [writes |-> {}, commitPolicy |-> "bodyAll", committed |-> 0]
     IN /\ MachineAccess!ResolveSpan(architecture, config, before.cpu, pageMap,
           request, certificate.spanWitness, certificate.resolved)
     /\ MachineAccess!MachineRead(before.memory, certificate.resolved,
                                  certificate.bytes)
     /\ certificate.value = WordFromBytes(certificate.bytes)
     /\ WriteStackPointerAllowed(before.cpu,
           certificate.controlPlan.newRSP, certificate.afterCPU)
     /\ MachineAccess!BodyApplied(before, certificate.afterCPU, emptyPlan, after)

\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Str, Int, $controlPopGPRCertificate,
\*   $controlMachineState) => Bool;
PopGPRBodyApplied(architecture, config, pageMap, before, destination, width,
                  certificate, after) ==
  /\ PopStackBodyApplied(architecture, config, pageMap, before, width,
                         certificate.pop, certificate.afterPop)
  /\ WriteNamedGPRAllowed(certificate.afterPop.cpu, destination, width,
       certificate.pop.value, certificate.afterCPU)
  /\ after = [certificate.afterPop EXCEPT !.cpu = certificate.afterCPU]

\* @type: ($controlCPUState, Int, Bool) => Str;
VirtualFlagGuard(cpu, width, cr4VME) ==
  IF cpu.execution.mode = "virtual8086" /\ IOPLValue(cpu.rflags) < 3
  THEN IF width = 16 /\ cr4VME THEN "allowed" ELSE "GP"
  ELSE "allowed"

\* @type: ($controlCPUState, Int, Bool) => $amd64Bits;
PushedFlagsWord(cpu, width, cr4VME) ==
  LET ordinary == Control!PushFlagImage(cpu.execution.mode,
                                        RFlagsWord(cpu.rflags))
  IN IF cpu.execution.mode = "virtual8086" /\ IOPLValue(cpu.rflags) < 3 /\
           width = 16 /\ cr4VME
     THEN [ordinary EXCEPT ![10] = cpu.rflags.virtualInterrupt,
                            ![13] = TRUE, ![14] = TRUE]
     ELSE ordinary

\* @type: ($controlCPUState, $amd64Bits, Int, Bool) => Bool;
VirtualPopFlagsFault(cpu, popped, width, cr4VME) ==
  /\ cpu.execution.mode = "virtual8086"
  /\ IOPLValue(cpu.rflags) < 3
  /\ width = 16 /\ cr4VME
  /\ (popped[9] \/ (popped[10] /\ cpu.rflags.virtualInterruptPending))

\* @type: ($controlCPUState, $amd64Bits, Int, Bool) => $controlCPUState;
ApplyPoppedFlagsWithVME(cpu, popped, width, cr4VME) ==
  IF cpu.execution.mode = "virtual8086" /\ IOPLValue(cpu.rflags) < 3 /\
       width = 16 /\ cr4VME
  THEN LET ordinary == Control!PopFlagImage(RFlagsWord(cpu.rflags), popped,
             width, cpu.execution.mode, cpu.execution.cpl, IOPLValue(cpu.rflags))
           image == [ordinary EXCEPT
             ![10] = cpu.rflags.interruptEnable,
             ![13] = cpu.rflags.iopl[1], ![14] = cpu.rflags.iopl[2],
             ![20] = popped[10]]
       IN [cpu EXCEPT !.rflags = RFlagsFromWord(@, image)]
  ELSE ApplyPoppedFlags(cpu, popped, width)

\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, Bool, $controlPushCertificate,
\*   $controlMachineState) => Bool;
PushFlagsBodyApplied(architecture, config, pageMap, before, width, cr4VME,
                     certificate, after) ==
  /\ VirtualFlagGuard(before.cpu, width, cr4VME) = "allowed"
  /\ PushBodyApplied(architecture, config, pageMap, before,
       PushedFlagsWord(before.cpu, width, cr4VME),
       width, certificate, after)

\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, Bool, $controlPopGPRCertificate,
\*   $controlMachineState) => Bool;
PopFlagsBodyApplied(architecture, config, pageMap, before, width, cr4VME,
                    certificate, after) ==
  /\ VirtualFlagGuard(before.cpu, width, cr4VME) = "allowed"
  /\ PopStackBodyApplied(architecture, config, pageMap, before, width,
                         certificate.pop, certificate.afterPop)
  /\ ~VirtualPopFlagsFault(before.cpu, certificate.pop.value, width, cr4VME)
  /\ certificate.afterCPU = ApplyPoppedFlagsWithVME(
       certificate.afterPop.cpu, certificate.pop.value, width, cr4VME)
  /\ after = [certificate.afterPop EXCEPT !.cpu = certificate.afterCPU]

\* Fault candidates carry an exact failed access and its program-order index,
\* but deliberately select no memory commit policy.
StackFaultTentative(config, cpu, pageMap, request, witness, faults) ==
  /\ faults = MachineAccess!SpanFaultCandidates(config, cpu, pageMap,
                                                 request, witness)
  /\ faults # {}

\* @type: Int => $amd64Bits;
SmallNatWord(value) == [bit \in 1..64 |->
  IF bit <= 16 THEN ((value \div (2 ^ (bit - 1))) % 2) = 1 ELSE FALSE]

\* Read SS:[old-rBP-index*V] from the current tentative memory. Earlier ENTER
\* pushes are therefore observable to a later aliased frame read.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, $amd64Bits, Int, Int, $controlReadCertificate) => Bool;
EnterFrameRead(architecture, config, pageMap, current, oldRBP, width, index,
               certificate) ==
  LET byteCount == width \div 8
      amount == SmallNatWord(index * byteCount)
      addressSize == Control!StackAddressSize(ControlProjection(current.cpu))
      request == [rawEffective |-> certificate.rawAddress,
        addressSize |-> addressSize, segmentName |-> "ss",
        access |-> [kind |-> "read", stack |-> TRUE,
          implicitSupervisor |-> FALSE, shadow |-> FALSE],
        byteCount |-> byteCount, alignmentBits |-> 0,
        memoryType |-> certificate.memoryType]
  IN /\ index \in 1..30
     /\ width \in {16, 32, 64}
     /\ Control!NegateAddress(amount, certificate.negativeSize,
                              certificate.negateCarry)
     /\ MachineAccess!WordAddWithCarry(oldRBP, certificate.negativeSize,
          certificate.rawAddress, certificate.subtractCarry)
     /\ MachineAccess!ResolveSpan(architecture, config, current.cpu, pageMap,
          request, certificate.spanWitness, certificate.resolved)
     /\ MachineAccess!MachineRead(current.memory, certificate.resolved,
                                  certificate.bytes)
     /\ certificate.value = WordFromBytes(certificate.bytes)

\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, $amd64Bits, Int, Int,
\*   Seq($controlReadCertificate), Seq($controlPushCertificate),
\*   Seq($controlMachineState)) => Bool;
EnterCopiesTrace(architecture, config, pageMap, afterInitial, oldRBP, width,
                 level, reads, pushes, machines) ==
  LET copies == IF level = 0 THEN 0 ELSE level - 1
  IN /\ level \in 0..31
     /\ Len(reads) = copies
     /\ Len(pushes) = copies
     /\ Len(machines) = copies + 1
     /\ machines[1] = afterInitial
     /\ \A copy \in 1..copies :
          /\ EnterFrameRead(architecture, config, pageMap, machines[copy],
               oldRBP, width, copy, reads[copy])
          /\ PushBodyApplied(architecture, config, pageMap, machines[copy],
               reads[copy].value, width, pushes[copy], machines[copy + 1])

\* Complete successful ENTER body. The final access is checked but produces no
\* byte effect. Fault cases use StackFaultTentative and deliberately remain
\* outside this success relation until per-instruction commit policy is sourced.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, Int, Int, $controlEnterCertificate,
\*   $controlMachineState) => Bool;
EnterBodyApplied(architecture, config, pageMap, before, width, allocation,
                 rawLevel, certificate, after) ==
  LET level == rawLevel % 32
      oldRBP == ReadNamedGPRValue(before.cpu, "rbp", width)
      finalRequest == [rawEffective |-> certificate.finalRSP,
        addressSize |-> Control!StackAddressSize(
          ControlProjection(certificate.afterNested.cpu)),
        segmentName |-> "ss",
        access |-> [kind |-> "write", stack |-> TRUE,
          implicitSupervisor |-> FALSE, shadow |-> FALSE],
        byteCount |-> width \div 8, alignmentBits |-> 0,
        memoryType |-> certificate.finalMemoryType]
  IN /\ rawLevel \in 0..255
     /\ allocation \in 0..65535
     /\ PushBodyApplied(architecture, config, pageMap, before, oldRBP, width,
          certificate.initialPush, certificate.afterInitial)
     /\ certificate.framePointer =
          certificate.afterInitial.cpu.gpr[GPRIndex("rsp")]
     /\ EnterCopiesTrace(architecture, config, pageMap,
          certificate.afterInitial, oldRBP, width, level,
          certificate.readCertificates, certificate.pushCertificates,
          certificate.copyMachines)
     /\ certificate.afterCopies =
          certificate.copyMachines[Len(certificate.copyMachines)]
     /\ IF level = 0
          THEN certificate.afterNested = certificate.afterCopies
          ELSE PushBodyApplied(architecture, config, pageMap,
                 certificate.afterCopies, certificate.framePointer, width,
                 certificate.framePush, certificate.afterNested)
     /\ Control!NegateAddress(SmallNatWord(allocation),
          certificate.allocationNegative, certificate.allocationNegateCarry)
     /\ MachineAccess!WordAddWithCarry(
          certificate.afterNested.cpu.gpr[GPRIndex("rsp")],
          certificate.allocationNegative, certificate.allocationFullSum,
          certificate.allocationSubtractCarry)
     /\ certificate.finalRSP = MachineAccess!EffectiveOffset(
          certificate.allocationFullSum, finalRequest.addressSize)
     /\ MachineAccess!ResolveSpan(architecture, config,
          certificate.afterNested.cpu, pageMap, finalRequest,
          certificate.finalWitness, certificate.finalResolved)
     /\ WriteStackPointerAllowed(certificate.afterNested.cpu,
          certificate.finalRSP, certificate.afterSPCPU)
     /\ WriteBasePointerAllowed(certificate.afterSPCPU, width,
          certificate.framePointer, certificate.afterCPU)
     /\ after = [certificate.afterNested EXCEPT !.cpu = certificate.afterCPU]

\* @type: Int => Int;
EnterLevel(rawLevel) == rawLevel % 32

RECURSIVE NatSequence(_)
RECURSIVE EnterCopyProgramForLevel(_)

\* Ordered indices 1 through level-1.
\* @type: Int => Seq(Int);
NatSequence(count) ==
  IF count <= 0 THEN <<>> ELSE Append(NatSequence(count - 1), count)

\* @type: Int => Seq(Int);
EnterCopyIndices(rawLevel) == NatSequence(EnterLevel(rawLevel) - 1)

\* @type: Int => Seq($stackMicroOp);
EnterCopyProgramForLevel(level) ==
  IF level <= 1 THEN <<>>
  ELSE EnterCopyProgramForLevel(level - 1)
    \o <<[kind |-> "read-frame", index |-> level - 1, register |-> ""],
         [kind |-> "push-frame", index |-> level - 1, register |-> ""]>>

\* @type: Int => Seq($stackMicroOp);
EnterCopyProgram(rawLevel) == EnterCopyProgramForLevel(EnterLevel(rawLevel))

\* @type: Int => Seq($stackMicroOp);
EnterProgram(rawLevel) ==
  <<[kind |-> "push-old-rbp", index |-> 0, register |-> "rbp"]>>
  \o EnterCopyProgram(rawLevel)
  \o (IF EnterLevel(rawLevel) > 0
      THEN <<[kind |-> "push-frame-pointer", index |-> EnterLevel(rawLevel),
               register |-> "rsp"]>>
      ELSE <<>>)
  \o <<[kind |-> "final-access-check", index |-> 0, register |-> ""]>>

\* @type: Seq($stackMicroOp);
PushaProgram == <<
  [kind |-> "push-register", index |-> 1, register |-> "rax"],
  [kind |-> "push-register", index |-> 2, register |-> "rcx"],
  [kind |-> "push-register", index |-> 3, register |-> "rdx"],
  [kind |-> "push-register", index |-> 4, register |-> "rbx"],
  [kind |-> "push-register", index |-> 5, register |-> "original-rsp"],
  [kind |-> "push-register", index |-> 6, register |-> "rbp"],
  [kind |-> "push-register", index |-> 7, register |-> "rsi"],
  [kind |-> "push-register", index |-> 8, register |-> "rdi"]>>

\* @type: Seq($stackMicroOp);
PopaProgram == <<
  [kind |-> "pop-register", index |-> 1, register |-> "rdi"],
  [kind |-> "pop-register", index |-> 2, register |-> "rsi"],
  [kind |-> "pop-register", index |-> 3, register |-> "rbp"],
  [kind |-> "discard-pop", index |-> 4, register |-> "discard-rsp"],
  [kind |-> "pop-register", index |-> 5, register |-> "rbx"],
  [kind |-> "pop-register", index |-> 6, register |-> "rdx"],
  [kind |-> "pop-register", index |-> 7, register |-> "rcx"],
  [kind |-> "pop-register", index |-> 8, register |-> "rax"]>>

\* Access/memory integration must preserve this order. It may attach a
\* tentative machine after any prefix, but no committed prefix is selected here.
\* @type: Seq($stackMicroOp) => Bool;
OrderedStackProgram(program) ==
  /\ \A index \in 1..Len(program) : program[index].kind \in StackMicroKinds
  /\ \A index \in 1..Len(program) : program[index].index >= 0

\* All sources, including original-rsp, are captured from the entry CPU before
\* the first push. Only successful eight-step bodies are related here.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, Seq($controlPushCertificate),
\*   Seq($controlMachineState)) => Bool;
PushaBodyTrace(architecture, config, pageMap, before, width,
               certificates, machines) ==
  /\ before.cpu.execution.mode # "long64"
  /\ width \in {16, 32}
  /\ Len(certificates) = 8
  /\ Len(machines) = 9
  /\ machines[1] = before
  /\ \A index \in 1..8 :
       LET sourceName == Control!PushaOrder[index]
           registerName == IF sourceName = "original-rsp" THEN "rsp"
                          ELSE sourceName
           value == ReadNamedGPRValue(before.cpu, registerName, width)
       IN PushBodyApplied(architecture, config, pageMap, machines[index],
                          value, width, certificates[index], machines[index + 1])

\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, Seq($controlPopGPRCertificate),
\*   Seq($controlMachineState)) => Bool;
PopaBodyTrace(architecture, config, pageMap, before, width,
              certificates, machines) ==
  /\ before.cpu.execution.mode # "long64"
  /\ width \in {16, 32}
  /\ Len(certificates) = 8
  /\ Len(machines) = 9
  /\ machines[1] = before
  /\ \A index \in 1..8 :
       LET destination == Control!PopaOrder[index]
           certificate == certificates[index]
       IN IF destination = "discard-rsp"
          THEN /\ PopStackBodyApplied(architecture, config, pageMap,
                    machines[index], width, certificate.pop,
                    certificate.afterPop)
               /\ machines[index + 1] = certificate.afterPop
          ELSE /\ PopGPRBodyApplied(architecture, config, pageMap,
                    machines[index], destination, width, certificate,
                    machines[index + 1])

\* Successful LEAVE stages rBP -> address-sized rSP, then performs the pop into
\* operand-sized rBP. A pop fault is not related here; its staged rSP remains
\* tentative until an instruction-specific fault policy is sourced.
\* @type: ($controlProfile, $controlSystemConfig, Set($controlPage),
\*   $controlMachineState, Int, $controlPopGPRCertificate,
\*   $controlCPUState, $controlMachineState, $controlMachineState) => Bool;
LeaveBodyApplied(architecture, config, pageMap, before, width, certificate,
                 stagedCPU, stagedMachine, after) ==
  LET addressSize == Control!StackAddressSize(ControlProjection(before.cpu))
      frameAddress == MachineAccess!EffectiveOffset(
        before.cpu.gpr[GPRIndex("rbp")], addressSize)
  IN /\ WriteStackPointerAllowed(before.cpu, frameAddress, stagedCPU)
     /\ stagedMachine = [before EXCEPT !.cpu = stagedCPU]
     /\ PopGPRBodyApplied(architecture, config, pageMap, stagedMachine,
          "rbp", width, certificate, after)


====================================================================
