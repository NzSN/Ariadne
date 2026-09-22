------------------------- MODULE AMD64Monitor -------------------------
EXTENDS AMD64MachineAccess

\* MONITORX/MWAITX with concrete one-byte MachineAccess resolution.
\* Authority: AMD APM Volume 3 rev. 3.38 PDF pages 280-281, 310-311,
\* and CPUID function 5 on PDF page 675.

MonitorDispositions == {"armed", "UD", "GP", "memoryFault",
  "sourceUnspecified", "modelingUnavailable"}
WakeKinds == {"matchingStore", "timerExpired", "interrupt", "nmi", "smi",
  "init", "reset", "farTransfer"}

\* @typeAlias: monitorProfile = {monitorx: Bool, interruptBreak: Bool,
\*   minimumLineBytes: Int, maximumLineBytes: Int};
\* @typeAlias: monitorRange = {bytes: Set($amd64Address)};
\* @typeAlias: monitorState = {range: Set($amd64Address), pending: Bool};
\* @typeAlias: monitorWake = {kind: Str,
\*   committedLinearBytes: Set($amd64Address), elapsedP0: $amd64Address,
\*   unmasked: Bool};
\* Transitive Snowcat aliases are not re-exported through EXTENDS.
\* @typeAlias: amd64Capabilities = {longMode: Bool, x87: Bool, mmx: Bool,
\*   sse: Bool, avx: Bool, avx512: Bool, mxcsrMisalignedMask: Bool};
\* @typeAlias: amd64Profile = {capabilities: $amd64Capabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};
\* @typeAlias: amd64Bits = Int -> Bool;
\* @typeAlias: monitorEnabledFeatures = {x87Enabled: Bool, sseEnabled: Bool,
\*   avxEnabled: Bool, avx512Enabled: Bool};
\* @typeAlias: monitorContext = {mode: Str, cpl: Int,
\*   features: $monitorEnabledFeatures};
\* @typeAlias: monitorSegment = {selector: $amd64Bits, base: $amd64Bits,
\*   limit: $amd64Bits, present: Bool, dpl: Int, readable: Bool,
\*   writable: Bool, executable: Bool, conforming: Bool, expandDown: Bool,
\*   defaultBig: Bool, longMode: Bool, unusable: Bool};
\* @typeAlias: monitorSegments = {cs: $monitorSegment, ss: $monitorSegment,
\*   ds: $monitorSegment, es: $monitorSegment, fs: $monitorSegment,
\*   gs: $monitorSegment};
\* @typeAlias: monitorRFlags = {cf: Bool, fixed1: Bool, pf: Bool,
\*   reserved3: Bool, af: Bool, reserved5: Bool, zf: Bool, sf: Bool,
\*   tf: Bool, interruptEnable: Bool, df: Bool, of: Bool, iopl: $amd64Bits,
\*   nestedTask: Bool, reserved15: Bool, resume: Bool, virtual8086: Bool,
\*   ac: Bool, virtualInterrupt: Bool, virtualInterruptPending: Bool,
\*   id: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: monitorX87Status = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   stackFault: Bool, errorSummary: Bool, c0: Bool, c1: Bool, c2: Bool,
\*   top: Int, c3: Bool, busy: Bool};
\* @typeAlias: monitorX87Control = {invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, reserved6: Bool, reserved7: Bool,
\*   precisionControl: Str, roundingControl: Str, infinityControl: Bool,
\*   reservedHigh: $amd64Bits};
\* @typeAlias: monitorX87Pointer = {kind: Str, selector: $amd64Bits,
\*   offset64: $amd64Bits, offset32: $amd64Bits, linear32: $amd64Bits};
\* @typeAlias: monitorX87 = {physical: Int -> $amd64Bits, tags: Int -> Str,
\*   status: $monitorX87Status, control: $monitorX87Control,
\*   lastInstruction: $monitorX87Pointer, lastData: $monitorX87Pointer,
\*   lastOpcode: $amd64Bits};
\* @typeAlias: monitorMXCSR = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   denormalsAreZero: Bool, invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, roundingControl: Str, flushToZero: Bool,
\*   reserved16: Bool, misalignedMask: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: monitorCPUState = {gpr: Int -> $amd64Bits, rip: $amd64Bits,
\*   rflags: $monitorRFlags, segments: $monitorSegments, x87: $monitorX87,
\*   vectors: Int -> $amd64Bits, kMask: Int -> $amd64Bits,
\*   mxcsr: $monitorMXCSR, execution: $monitorContext};

\* @type: ($monitorProfile, $monitorRange, $amd64Address) => Bool;
MonitorRangeWellFormed(profile, range, target) ==
  /\ profile.minimumLineBytes > 0
  /\ Cardinality(range.bytes) \in
       profile.minimumLineBytes..profile.maximumLineBytes
  /\ target \in range.bytes

\* @type: ($monitorCPUState, Int, Str, $amd64MemoryTypeResolution)
\*   => $machineAccessRequest;
MonitorRequest(cpu, addressSize, segmentName, memoryType) ==
  [rawEffective |-> cpu.gpr[0], addressSize |-> addressSize,
   segmentName |-> segmentName,
   access |-> [kind |-> "read", stack |-> segmentName = "ss",
               implicitSupervisor |-> FALSE, shadow |-> FALSE],
   byteCount |-> 1, alignmentBits |-> 0, memoryType |-> memoryType]

\* @type: ($monitorProfile, $monitorCPUState, $monitorState,
\*   $monitorRange, $machineResolvedSpan, $monitorCPUState,
\*   $monitorState, Str) => Bool;
BindResolvedMonitor(profile, beforeCPU, beforeMonitor, range, resolved,
                    afterCPU, afterMonitor, disposition) ==
  /\ MonitorRangeWellFormed(profile, range, resolved.linearBytes[1])
  /\ afterCPU = beforeCPU
  /\ CASE resolved.memoryType.kind # "resolved" ->
       disposition = "modelingUnavailable" /\ afterMonitor = beforeMonitor
     [] resolved.memoryType.memoryType = "WB" ->
       /\ disposition = "armed"
       /\ afterMonitor = [range |-> range.bytes, pending |-> TRUE]
     [] OTHER ->
       /\ disposition = "sourceUnspecified"
       /\ afterMonitor = beforeMonitor

\* Complete resolution and entry ordering. The explicit range is processor-
\* profile data and cannot replace CPU, memory, or fault state.
\* @type: ($monitorProfile, $amd64Profile, $amd64SystemConfig,
\*   $monitorCPUState, Set($amd64Page), Int, Str,
\*   $amd64MemoryTypeResolution, $machineSpanWitness,
\*   $machineResolvedSpan, $monitorRange, $monitorState,
\*   $monitorCPUState, $monitorState, Str) => Bool;
ExecuteMONITORX(profile, architecture, config, beforeCPU, pageMap,
                addressSize, segmentName, memoryType, witness, resolved,
                range, beforeMonitor, afterCPU, afterMonitor, disposition) ==
  LET request == MonitorRequest(beforeCPU, addressSize, segmentName, memoryType)
      faults == SpanFaultCandidates(config, beforeCPU, pageMap, request, witness)
      ecxNonzero == \E bit \in 1..32 : beforeCPU.gpr[1][bit]
  IN CASE ~profile.monitorx ->
       disposition = "UD" /\ afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] ecxNonzero ->
       disposition = "GP" /\ afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] faults # {} ->
       disposition = "memoryFault" /\ afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] OTHER ->
       /\ ResolveSpan(architecture, config, beforeCPU, pageMap, request,
                      witness, resolved)
       /\ BindResolvedMonitor(profile, beforeCPU, beforeMonitor, range,
                              resolved, afterCPU, afterMonitor, disposition)

\* @type: ($monitorState, Set($amd64Address), $monitorState) => Bool;
ObserveCommittedStore(before, committedLinearBytes, after) ==
  IF before.pending /\ before.range \cap committedLinearBytes # {}
  THEN after = [range |-> {}, pending |-> FALSE]
  ELSE after = before

\* @type: ($monitorProfile, $monitorCPUState, $monitorState,
\*   $monitorWake) => Bool;
WakeAllowed(profile, cpu, monitor, observation) ==
  LET interruptExtension == cpu.gpr[1][1]
      timerExtension == cpu.gpr[1][2]
      timeoutNonzero == \E bit \in 1..32 : cpu.gpr[3][bit]
  IN /\ observation.kind \in WakeKinds
     /\ CASE observation.kind = "matchingStore" ->
          monitor.pending /\ monitor.range \cap observation.committedLinearBytes # {}
       [] observation.kind = "timerExpired" ->
          timerExtension /\ timeoutNonzero /\
          UnsignedLE(cpu.gpr[3], observation.elapsedP0)
       [] observation.kind = "interrupt" ->
          observation.unmasked \/ (interruptExtension /\ profile.interruptBreak)
       [] OTHER -> TRUE

\* @type: ($monitorProfile, $monitorCPUState, $monitorState,
\*   $monitorWake, $monitorCPUState, $monitorState, Str) => Bool;
ExecuteMWAITX(profile, beforeCPU, beforeMonitor, observation,
              afterCPU, afterMonitor, disposition) ==
  LET reservedSet == \E bit \in 3..32 : beforeCPU.gpr[1][bit]
      unsupportedIBE == beforeCPU.gpr[1][1] /\ ~profile.interruptBreak
  IN CASE ~profile.monitorx -> disposition = "UD" /\
       afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] reservedSet \/ unsupportedIBE -> disposition = "GP" /\
       afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] ~WakeAllowed(profile, beforeCPU, beforeMonitor, observation) ->
       disposition = "modelingUnavailable" /\
       afterCPU = beforeCPU /\ afterMonitor = beforeMonitor
     [] OTHER -> disposition = "woke" /\ afterCPU = beforeCPU /\
       afterMonitor = [range |-> {}, pending |-> FALSE]

=======================================================================
