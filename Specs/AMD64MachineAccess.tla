--------------------- MODULE AMD64MachineAccess ---------------------
EXTENDS AMD64ConcreteMemory, AMD64MemoryTypes

\* Shared architectural CPU + concrete-memory access boundary.
\*
\* The address witness contains only full-width addition results and carries;
\* every result is checked below. Page selection is derived from the unique
\* explicit PageMap match. It is not an environment-selected translation.
\* Captured MemoryState is deliberately absent from amd64MachineState.

\* @typeAlias: machineAccessRequest = {rawEffective: $amd64Address,
\*   addressSize: Int, segmentName: Str, access: $amd64Access,
\*   byteCount: Int, alignmentBits: Int,
\*   memoryType: $amd64MemoryTypeResolution};
\* @typeAlias: machineSpanWitness = {effectiveBytes: Seq($amd64Address),
\*   effectiveCarries: Seq($amd64Carry), segmentRawBytes: Seq($amd64Address),
\*   segmentCarries: Seq($amd64Carry), linearBytes: Seq($amd64Address)};
\* @typeAlias: machineResolvedSpan = {request: $machineAccessRequest,
\*   effectiveBytes: Seq($amd64Address), linearBytes: Seq($amd64Address),
\*   physicalBytes: Seq($amd64Address),
\*   memoryType: $amd64MemoryTypeResolution};
\* @typeAlias: machineIndexedFault = {index: Int, fault: $amd64Fault};
\* @typeAlias: machineByteEffect = {index: Int, physical: $amd64Address,
\*   before: $amd64Byte, after: $amd64Byte};
\* @typeAlias: machineEffectPlan = {writes: Set($machineByteEffect),
\*   commitPolicy: Str, committed: Int};
\* @typeAlias: machineCPUSegment = {selector: (Int -> Bool),
\*   base: (Int -> Bool), limit: (Int -> Bool), present: Bool, dpl: Int,
\*   readable: Bool, writable: Bool, executable: Bool, conforming: Bool,
\*   expandDown: Bool, defaultBig: Bool, longMode: Bool, unusable: Bool};
\* @typeAlias: machineMemorySegment = {base: $amd64Address,
\*   limit: $amd64Address, present: Bool, readable: Bool, writable: Bool,
\*   executable: Bool, conforming: Bool, expandDown: Bool, defaultBig: Bool,
\*   unusable: Bool, dpl: Int, rpl: Int};
\* @typeAlias: machineCapabilities = {longMode: Bool, x87: Bool, mmx: Bool,
\*   sse: Bool, avx: Bool, avx512: Bool, mxcsrMisalignedMask: Bool};
\* @typeAlias: machineProfile = {capabilities: $machineCapabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};
\* @typeAlias: machineEnabledFeatures = {x87Enabled: Bool, sseEnabled: Bool,
\*   avxEnabled: Bool, avx512Enabled: Bool};
\* @typeAlias: machineContext = {mode: Str, cpl: Int,
\*   features: $machineEnabledFeatures};
\* @typeAlias: machineSegments = {cs: $machineCPUSegment,
\*   ss: $machineCPUSegment, ds: $machineCPUSegment, es: $machineCPUSegment,
\*   fs: $machineCPUSegment, gs: $machineCPUSegment};
\* @typeAlias: machineRFlags = {cf: Bool, fixed1: Bool, pf: Bool,
\*   reserved3: Bool, af: Bool, reserved5: Bool, zf: Bool, sf: Bool,
\*   tf: Bool, interruptEnable: Bool, df: Bool, of: Bool,
\*   iopl: (Int -> Bool), nestedTask: Bool, reserved15: Bool, resume: Bool,
\*   virtual8086: Bool, ac: Bool, virtualInterrupt: Bool,
\*   virtualInterruptPending: Bool, id: Bool, reservedHigh: (Int -> Bool)};
\* @typeAlias: machineX87Status = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   stackFault: Bool, errorSummary: Bool, c0: Bool, c1: Bool, c2: Bool,
\*   top: Int, c3: Bool, busy: Bool};
\* @typeAlias: machineX87Control = {invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, reserved6: Bool, reserved7: Bool,
\*   precisionControl: Str, roundingControl: Str, infinityControl: Bool,
\*   reservedHigh: (Int -> Bool)};
\* @typeAlias: machineX87Pointer = {kind: Str, selector: (Int -> Bool),
\*   offset64: (Int -> Bool), offset32: (Int -> Bool),
\*   linear32: (Int -> Bool)};
\* @typeAlias: machineX87 = {physical: Int -> (Int -> Bool),
\*   tags: Int -> Str, status: $machineX87Status, control: $machineX87Control,
\*   lastInstruction: $machineX87Pointer, lastData: $machineX87Pointer,
\*   lastOpcode: (Int -> Bool)};
\* @typeAlias: machineMXCSR = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   denormalsAreZero: Bool, invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, roundingControl: Str, flushToZero: Bool,
\*   reserved16: Bool, misalignedMask: Bool, reservedHigh: (Int -> Bool)};
\* @typeAlias: machineCPUState = {gpr: Int -> (Int -> Bool),
\*   rip: (Int -> Bool), rflags: $machineRFlags, segments: $machineSegments,
\*   x87: $machineX87, vectors: Int -> (Int -> Bool),
\*   kMask: Int -> (Int -> Bool), mxcsr: $machineMXCSR,
\*   execution: $machineContext};
\* @typeAlias: machineState = {cpu: $machineCPUState,
\*   memory: $amd64ConcreteMemory};

CommitPolicies == {"rollback", "committedPrefix", "bodyAll", "instructionSpecific"}
MachineModes == {"real", "protected", "virtual8086", "compatibility", "long64"}
MachineSegmentNames == {"cs", "ss", "ds", "es", "fs", "gs"}

\* @type: ($machineSegments, Str) => Int;
MachineDefaultAddressWidth(segments, mode) ==
  IF mode = "long64" THEN 64
  ELSE IF mode \in {"protected", "compatibility"} /\ segments.cs.defaultBig
       THEN 32 ELSE 16

\* @type: (Int, Int) => $amd64Address;
OffsetWord(offset, width) ==
  [bit \in AddressBits |->
    IF bit <= width /\ bit <= 4
    THEN ((offset \div (2 ^ (bit - 1))) % 2) = 1
    ELSE FALSE]

\* @type: ((Int -> Bool), Int) => Int;
LowBitsNat(bits, width) ==
  (IF width >= 1 /\ bits[1] THEN 1 ELSE 0) +
  (IF width >= 2 /\ bits[2] THEN 2 ELSE 0)

\* @type: ($machineSegments, Str) => $machineCPUSegment;
CPUSelectSegment(segments, name) ==
  CASE name = "cs" -> segments.cs [] name = "ss" -> segments.ss
    [] name = "ds" -> segments.ds [] name = "es" -> segments.es
    [] name = "fs" -> segments.fs [] OTHER -> segments.gs

\* Convert the canonical CPU segment cache to AMD64Memory's access view.
\* @type: $machineCPUSegment => $machineMemorySegment;
MemorySegment(segment) ==
  [base |-> segment.base,
   limit |-> [bit \in AddressBits |-> IF bit <= 32 THEN segment.limit[bit]
                                      ELSE FALSE],
   present |-> segment.present, readable |-> segment.readable,
   writable |-> segment.writable, executable |-> segment.executable,
   conforming |-> segment.conforming, expandDown |-> segment.expandDown,
   defaultBig |-> segment.defaultBig, unusable |-> segment.unusable,
   dpl |-> segment.dpl, rpl |-> LowBitsNat(segment.selector, 2)]

\* @type: ($machineProfile, $machineState) => Bool;
MachineStateWellFormed(profile, state) ==
  /\ state.cpu.execution.mode \in MachineModes
  /\ state.cpu.execution.cpl \in 0..3
  /\ (state.cpu.execution.features.avx512Enabled =>
        state.cpu.execution.features.avxEnabled /\ profile.capabilities.avx512)
  /\ (state.cpu.execution.features.avxEnabled =>
        state.cpu.execution.features.sseEnabled /\ profile.capabilities.avx)
  /\ (state.cpu.execution.features.sseEnabled => profile.capabilities.sse)
  /\ (state.cpu.execution.features.x87Enabled => profile.capabilities.x87)
  /\ ConcreteMemoryWellFormed(state.memory)
  /\ state.memory.physicalBits = profile.physicalAddressBits

\* @type: (Set($amd64Page), $amd64Address) => Set($amd64Page);
MatchingPages(pageMap, linear) ==
  {page \in pageMap : MappingMatches(linear, page)}

\* @type: (Set($amd64Page), $amd64Address) => $amd64Page;
UniquePage(pageMap, linear) ==
  CHOOSE page \in MatchingPages(pageMap, linear) : TRUE

\* @type: ($amd64SystemConfig, Str, Set($amd64Page), $amd64Address)
\*   => $amd64Address;
ResolvedPhysical(config, mode, pageMap, linear) ==
  IF config.paging
  THEN [bit \in AddressBits |->
         IF bit <= UniquePage(pageMap, linear).offsetBits THEN linear[bit]
         ELSE UniquePage(pageMap, linear).physicalTag[bit]]
  ELSE ApplyA20(config, mode, linear)

\* Verified ascending byte-address construction. Carry witnesses prove every
\* effective offset and segment-base addition at full 64-bit precision.
\* @type: ($machineProfile, $amd64SystemConfig, $machineCPUState,
\*   $machineAccessRequest, $machineSpanWitness) => Bool;
SpanWitnessWellFormed(profile, config, cpu, request, witness) ==
  LET count == request.byteCount
      mode == cpu.execution.mode
      segment == CPUSelectSegment(cpu.segments, request.segmentName)
      memorySegment == MemorySegment(segment)
      effectiveBase == EffectiveOffset(request.rawEffective, request.addressSize)
      segmentBase == EffectiveSegmentBase(mode, request.segmentName, memorySegment)
  IN /\ count \in 1..16
     /\ request.segmentName \in MachineSegmentNames
     /\ request.alignmentBits \in 0..6
     /\ AddressSizePermitted(mode, MachineDefaultAddressWidth(cpu.segments, mode),
                              request.addressSize)
     /\ ~(mode \in {"real", "virtual8086"} /\ config.paging /\
           ~config.a20Enabled)
     /\ Len(witness.effectiveBytes) = count
     /\ Len(witness.effectiveCarries) = count
     /\ Len(witness.segmentRawBytes) = count
     /\ Len(witness.segmentCarries) = count
     /\ Len(witness.linearBytes) = count
     /\ \A index \in 1..count :
          /\ WordAddWithCarry(effectiveBase,
               OffsetWord(index - 1, request.addressSize),
               witness.effectiveBytes[index], witness.effectiveCarries[index])
          /\ SegmentLinearWithCarry(mode, segmentBase,
               witness.effectiveBytes[index], witness.segmentRawBytes[index],
               witness.segmentCarries[index], witness.linearBytes[index])

\* @type: ($amd64SystemConfig, $machineCPUState, Set($amd64Page),
\*   $machineAccessRequest, $machineSpanWitness)
\*   => Set($machineIndexedFault);
SpanFaultCandidates(config, cpu, pageMap, request, witness) ==
  LET count == request.byteCount
      segment == MemorySegment(CPUSelectSegment(cpu.segments,
                                                request.segmentName))
      rawAddressFaults ==
        IF ~SegmentPermits(cpu.execution.mode, cpu.execution.cpl,
             request.segmentName, segment, request.access,
             witness.effectiveBytes[1], witness.effectiveBytes[count])
        THEN {[index |-> 1,
               fault |-> [stage |-> 1,
                 vector |-> IF request.access.stack THEN "SS" ELSE "GP",
                 reason |-> "segment", errorCode |-> NoPageFaultCode,
                 linear |-> witness.linearBytes[1]]]}
        ELSE { [index |-> index,
                fault |-> [stage |-> 1,
                  vector |-> IF request.access.stack THEN "SS" ELSE "GP",
                  reason |-> "non-canonical", errorCode |-> NoPageFaultCode,
                  linear |-> witness.linearBytes[index]]] :
               index \in {candidate \in 1..count :
                 cpu.execution.mode = "long64" /\
                 ~Canonical(witness.linearBytes[candidate],
                            config.virtualBits)} }
      addressFaults == {candidate \in rawAddressFaults :
        ~\E earlier \in rawAddressFaults : earlier.index < candidate.index}
      rawPageFaults == IF addressFaults /= {} THEN {} ELSE UNION {
        { [index |-> index,
           fault |-> [stage |-> 2, vector |-> "PF",
             reason |-> IF MatchingPages(pageMap, witness.linearBytes[index]) = {}
                        THEN "not-present" ELSE "page-protection",
             errorCode |-> IF MatchingPages(pageMap, witness.linearBytes[index]) = {}
                           THEN MissingPageFaultError(config, cpu.execution.cpl,
                                  request.access)
                           ELSE PageFaultError(config, cpu.execution.cpl,
                                  cpu.rflags.ac,
                                  UniquePage(pageMap, witness.linearBytes[index]),
                                  request.access),
             linear |-> witness.linearBytes[index]]] } :
          index \in {candidate \in 1..count :
            config.paging /\
              (MatchingPages(pageMap, witness.linearBytes[candidate]) = {} \/
               ~PagePermits(config, cpu.execution.cpl, cpu.rflags.ac,
                 UniquePage(pageMap, witness.linearBytes[candidate]),
                 request.access))}}
      pageFaults == {candidate \in rawPageFaults :
        ~\E earlier \in rawPageFaults : earlier.index < candidate.index}
      alignmentFaults ==
        IF pageFaults = {} /\ AlignmentFault(config, cpu.execution.cpl,
             cpu.rflags.ac, witness.linearBytes[1], request.alignmentBits)
        THEN {[index |-> 1,
               fault |-> [stage |-> 3, vector |-> "AC",
                 reason |-> "unaligned", errorCode |-> NoPageFaultCode,
                 linear |-> witness.linearBytes[1]]]}
        ELSE {}
  IN addressFaults \cup pageFaults \cup alignmentFaults

\* @type: ($machineProfile, $amd64SystemConfig, $machineCPUState,
\*   Set($amd64Page), $machineAccessRequest, $machineSpanWitness,
\*   $machineResolvedSpan) => Bool;
ResolveSpan(profile, config, cpu, pageMap, request, witness, resolved) ==
  /\ PageMapWellFormed(pageMap)
  /\ SpanWitnessWellFormed(profile, config, cpu, request, witness)
  /\ SpanFaultCandidates(config, cpu, pageMap, request, witness) = {}
  /\ resolved.request = request
  /\ resolved.effectiveBytes = witness.effectiveBytes
  /\ resolved.linearBytes = witness.linearBytes
  /\ resolved.memoryType = request.memoryType
  /\ Len(resolved.physicalBytes) = request.byteCount
  /\ \A index \in 1..request.byteCount :
       /\ resolved.physicalBytes[index] =
            ResolvedPhysical(config, cpu.execution.mode, pageMap,
                             witness.linearBytes[index])
       /\ PhysicalAddressValid(resolved.physicalBytes[index],
                               profile.physicalAddressBits)

\* @type: ($amd64ConcreteMemory, $machineResolvedSpan, Seq($amd64Byte)) => Bool;
MachineRead(memory, span, bytes) ==
  /\ Len(bytes) = Len(span.physicalBytes)
  /\ \A index \in 1..Len(bytes) :
       bytes[index] = ConcreteRead(memory, span.physicalBytes[index])

\* @type: ($amd64ConcreteMemory, $machineResolvedSpan, Seq($amd64Byte))
\*   => Set($machineByteEffect);
PlannedWrites(memory, span, bytes) ==
  {[index |-> index, physical |-> span.physicalBytes[index],
    before |-> ConcreteRead(memory, span.physicalBytes[index]),
    after |-> bytes[index]] : index \in 1..Len(bytes)}

\* @type: ($amd64ConcreteMemory, $machineResolvedSpan, Seq($amd64Byte),
\*   Set($machineByteEffect)) => Bool;
PlanWrites(memory, span, bytes, writes) ==
  /\ Len(bytes) = Len(span.physicalBytes)
  /\ writes = PlannedWrites(memory, span, bytes)

\* @type: $machineEffectPlan => Bool;
EffectPlanWellFormed(plan) ==
  /\ plan.commitPolicy \in CommitPolicies
  /\ plan.committed \in 0..Cardinality(plan.writes)
  /\ \A left, right \in plan.writes :
       left.index = right.index => left = right
  /\ (plan.commitPolicy = "rollback" => plan.committed = 0)
  /\ (plan.commitPolicy = "bodyAll" =>
        plan.committed = Cardinality(plan.writes))

\* Simultaneous functional result for a committed prefix. Effect indices retain
\* byte order; unique physical addresses make replacement unambiguous.
\* @type: ($amd64ConcreteMemory, $machineEffectPlan,
\*   $amd64ConcreteMemory) => Bool;
ApplyCommittedPrefix(before, plan, after) ==
  LET committed == {effect \in plan.writes : effect.index <= plan.committed}
      untouched == {cell \in before.overrides :
        \A effect \in committed : cell.physical /= effect.physical}
      replacements == {
        [physical |-> effect.physical, value |-> effect.after] :
          effect \in {candidate \in committed :
            candidate.after /= before.defaultByte}}
  IN /\ EffectPlanWellFormed(plan)
     /\ \A left, right \in committed :
          left.physical = right.physical => left = right
     /\ after = [physicalBits |-> before.physicalBits,
                  defaultByte |-> before.defaultByte,
                  overrides |-> untouched \cup replacements]

\* Body application is deliberately not retirement or RIP advancement.
\* @type: ($machineState, $machineCPUState, $machineEffectPlan,
\*   $machineState) => Bool;
BodyApplied(before, afterCPU, plan, after) ==
  /\ ApplyCommittedPrefix(before.memory, plan, after.memory)
  /\ after.cpu = afterCPU

====================================================================
