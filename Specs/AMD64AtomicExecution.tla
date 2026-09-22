-------------------- MODULE AMD64AtomicExecution --------------------
EXTENDS AMD64MachineAccess, AMD64Atomic

RegisterViews == INSTANCE AMD64RegisterViews

\* Authoritative CPU + concrete-memory bodies for memory XCHG, XADD,
\* CMPXCHG, CMPXCHG8B and CMPXCHG16B. These relations consume only a span
\* produced by MachineAccess.ResolveSpan. `bodyApplied` is not retirement.

\* @typeAlias: atomicExecutionInstruction = {kind: Str, width: Int,
\*   sourceIndex: Int, sourceView: Str, lockPrefix: Bool,
\*   cmpxchg8b: Bool, cmpxchg16b: Bool};
\* @typeAlias: atomicExecutionEvent = {kind: Str,
\*   physicalBytes: Seq($amd64Address), width: Int,
\*   before: Seq($amd64Byte), after: Seq($amd64Byte),
\*   locked: Bool, atomic: Bool,
\*   memoryType: $amd64MemoryTypeResolution};
\* @typeAlias: atomicExecutionResult = {disposition: Str,
\*   state: $machineState, plan: $machineEffectPlan,
\*   event: $atomicExecutionEvent};
\* @typeAlias: atomicGroup7Profile = {known: Bool, gpRank: Int,
\*   pfRank: Int, acRank: Int};

ScalarKinds == {"xchg", "xadd", "cmpxchg"}
BlockKinds == {"cmpxchg8b", "cmpxchg16b"}
GPRViews == {"low8", "high8", "low16", "low32", "full64"}

\* @type: Str => Int;
ViewWidth(view) ==
  CASE view \in {"low8", "high8"} -> 8 [] view = "low16" -> 16
    [] view = "low32" -> 32 [] OTHER -> 64

\* @type: Str => $amd64View;
StorageView(view) ==
  CASE view = "low8" -> RegisterViews!Low8
    [] view = "high8" -> RegisterViews!High8
    [] view = "low16" -> RegisterViews!Low16
    [] view = "low32" -> RegisterViews!Low32
    [] OTHER -> RegisterViews!Full64

\* @type: ($machineCPUState, Int, Str) => $integerWord;
ReadGPR(cpu, index, view) ==
  RegisterViews!ReadView(cpu.gpr[index], StorageView(view))

\* Same storage rule as IntegerExecution.WriteGPRAllowed. Legacy upper dword
\* bits remain relational; long64 low32 writes zero-extend.
\* @type: ($machineCPUState, Int, Str, $integerWord,
\*   $machineCPUState) => Bool;
WriteGPRAllowed(before, index, view, value, after) ==
  /\ index \in 0..15 /\ view \in GPRViews
  /\ [after EXCEPT !.gpr = before.gpr] = before
  /\ \A bit \in 1..64 :
       LET offset == StorageView(view).offset
           width == StorageView(view).width
       IN IF offset < bit /\ bit <= offset + width
          THEN after.gpr[index][bit] = value[bit - offset]
          ELSE IF view = "low32" /\ before.execution.mode = "long64"
               THEN ~after.gpr[index][bit]
               ELSE IF before.execution.mode = "long64" \/ bit <= 32
                    THEN after.gpr[index][bit] = before.gpr[index][bit]
                    ELSE TRUE

\* @type: ($machineCPUState, Int, Str, $integerWord)
\*   => Set($machineCPUState);
WriteGPRCandidates(before, index, view, value) ==
  IF before.execution.mode = "long64"
  THEN {[before EXCEPT !.gpr[index] =
          RegisterViews!WriteView64(@, value, StorageView(view))]}
  ELSE {[before EXCEPT !.gpr[index] = word] :
    word \in {candidate \in [1..64 -> BOOLEAN] :
      \A bit \in 1..64 :
        LET offset == StorageView(view).offset
            width == StorageView(view).width
        IN IF offset < bit /\ bit <= offset + width
           THEN candidate[bit] = value[bit - offset]
           ELSE IF view = "low32" /\ before.execution.mode = "long64"
                THEN ~candidate[bit]
                ELSE IF before.execution.mode = "long64" \/ bit <= 32
                     THEN candidate[bit] = before.gpr[index][bit]
                     ELSE TRUE}}

\* @type: ($machineRFlags, $integerFlags) => $machineRFlags;
ApplyStatus(flags, status) ==
  [flags EXCEPT !.cf = status["cf"], !.pf = status["pf"],
                !.af = status["af"], !.zf = status["zf"],
                !.sf = status["sf"], !.of = status["of"]]

\* @type: ($machineCPUState, $integerFlags, $machineCPUState) => Bool;
WriteStatus(before, status, after) ==
  after = [before EXCEPT !.rflags = ApplyStatus(@, status)]

\* @type: ($machineCPUState, $integerFlags) => $machineCPUState;
ApplyStatusCPU(before, status) ==
  [before EXCEPT !.rflags = ApplyStatus(@, status)]

\* @type: ($atomicExecutionInstruction, $machineCPUState) => Str;
AtomicPreflight(instruction, cpu) ==
  IF instruction.kind \in ScalarKinds /\
       (instruction.width \notin {8, 16, 32, 64} \/
        instruction.sourceView \notin GPRViews \/
        ViewWidth(instruction.sourceView) /= instruction.width \/
        instruction.sourceIndex \notin 0..15)
  THEN "formRejected"
  ELSE AtomicPreAccessLegality(instruction.kind, instruction.width,
         instruction.cmpxchg8b, instruction.cmpxchg16b,
         cpu.execution.mode)

\* @type: ($atomicExecutionInstruction, $machineResolvedSpan) => Bool;
AtomicRequestCompatible(instruction, span) ==
  /\ span.request.access.kind = "readWrite"
  /\ span.memoryType.kind = "resolved"
  /\ span.request.byteCount = instruction.width \div 8
  /\ IF instruction.kind = "cmpxchg8b" THEN instruction.width = 64
     ELSE IF instruction.kind = "cmpxchg16b" THEN instruction.width = 128
     ELSE instruction.kind \in ScalarKinds /\
          instruction.width \in {8, 16, 32, 64}

\* @type: ($atomicExecutionInstruction, $machineSpanWitness)
\*   => Set($machineIndexedFault);
MandatoryAtomicFaults(instruction, witness) ==
  IF instruction.kind = "cmpxchg16b" /\
     ~Aligned(witness.linearBytes[1], 4)
  THEN {[index |-> 1,
         fault |-> [stage |-> 3, vector |-> "GP",
           reason |-> "cmpxchg16b-alignment",
           errorCode |-> NoPageFaultCode,
           linear |-> witness.linearBytes[1]]]}
  ELSE {}

\* Group-7 candidates remain a set. A later profile-aware selector chooses
\* among mandatory #GP, data #PF, and ordinary #AC when they coexist.
\* @type: ($amd64SystemConfig, $machineCPUState, Set($amd64Page),
\*   $machineAccessRequest, $machineSpanWitness,
\*   $atomicExecutionInstruction) => Set($machineIndexedFault);
AtomicFaultCandidates(config, cpu, pageMap, request, witness, instruction) ==
  SpanFaultCandidates(config, cpu, pageMap, request, witness) \cup
  MandatoryAtomicFaults(instruction, witness)

\* @type: ($atomicGroup7Profile, $machineIndexedFault) => Int;
Group7Rank(profile, candidate) ==
  CASE candidate.fault.vector = "GP" -> profile.gpRank
    [] candidate.fault.vector = "PF" -> profile.pfRank
    [] OTHER -> profile.acRank

\* Unknown implementation profile preserves every group-7 alternative.
\* A known profile supplies stable ranks; this module never invents a
\* universal #GP/#PF/#AC ordering.
\* @type: ($atomicGroup7Profile, Set($machineIndexedFault),
\*   $machineIndexedFault) => Bool;
AtomicFaultSelected(profile, candidates, selected) ==
  /\ selected \in candidates
  /\ IF profile.known
     THEN /\ {profile.gpRank, profile.pfRank, profile.acRank} = {0, 1, 2}
          /\ \A candidate \in candidates :
               Group7Rank(profile, selected) <= Group7Rank(profile, candidate)
     ELSE TRUE

\* @type: ($atomicExecutionInstruction, $machineResolvedSpan,
\*   Seq($amd64Byte), Seq($amd64Byte)) => $atomicExecutionEvent;
ExecutionEvent(instruction, span, before, after) ==
  LET locked == AtomicityFor(instruction.kind, instruction.lockPrefix)
  IN [kind |-> instruction.kind, physicalBytes |-> span.physicalBytes,
      width |-> instruction.width, before |-> before, after |-> after,
      locked |-> locked, atomic |-> locked,
      memoryType |-> span.memoryType]

\* Explicit constructors keep Snowcat's sequence type for architectural
\* atomic widths 1,2,4,8 and 16 bytes.
\* @type: ($amd64ConcreteMemory, $machineResolvedSpan) => Seq($amd64Byte);
ReadSpanBytes(memory, span) ==
  LET address == span.physicalBytes
      read(index) == ConcreteRead(memory, address[index])
  IN CASE Len(address) = 1 -> <<read(1)>>
       [] Len(address) = 2 -> <<read(1), read(2)>>
       [] Len(address) = 4 -> <<read(1), read(2), read(3), read(4)>>
       [] Len(address) = 8 -> <<read(1), read(2), read(3), read(4),
                                read(5), read(6), read(7), read(8)>>
       [] OTHER -> <<read(1), read(2), read(3), read(4),
                     read(5), read(6), read(7), read(8),
                     read(9), read(10), read(11), read(12),
                     read(13), read(14), read(15), read(16)>>

\* @type: ($machineState, $machineResolvedSpan,
\*   $atomicExecutionInstruction, $machineCPUState,
\*   Seq($amd64Byte), Seq($amd64Byte), $atomicExecutionResult) => Bool;
FinishAtomicBody(before, span, instruction, afterCPU, oldBytes, newBytes,
                 result) ==
  LET writes == PlannedWrites(before.memory, span, newBytes)
      plan == [writes |-> writes, commitPolicy |-> "bodyAll",
                 committed |-> Len(newBytes)]
  IN /\ PlanWrites(before.memory, span, newBytes, writes)
       /\ EffectPlanWellFormed(plan)
       /\ BodyApplied(before, afterCPU, plan, result.state)
       /\ result.disposition = "bodyApplied"
       /\ result.plan = plan
       /\ result.event = ExecutionEvent(instruction, span, oldBytes, newBytes)

\* @type: ($machineState, $machineResolvedSpan,
\*   $atomicExecutionInstruction, $atomicExecutionResult) => Bool;
ScalarAtomicBody(before, span, instruction, result) ==
  LET oldBytes == ReadSpanBytes(before.memory, span)
      destination == BytesToWord(oldBytes)
      source == ReadGPR(before.cpu, instruction.sourceIndex,
                        instruction.sourceView)
      width == instruction.width
  IN /\ instruction.kind \in ScalarKinds
     /\ AtomicRequestCompatible(instruction, span)
     /\ AtomicPreflight(instruction, before.cpu) = "allowed"
     /\ CASE instruction.kind = "xchg" ->
          \E afterCPU \in WriteGPRCandidates(before.cpu,
               instruction.sourceIndex, instruction.sourceView, destination) :
            /\ WriteGPRAllowed(before.cpu, instruction.sourceIndex,
                 instruction.sourceView, destination, afterCPU)
            /\ FinishAtomicBody(before, span, instruction, afterCPU, oldBytes,
                 WordBytes(source, width), result)
        [] instruction.kind = "xadd" ->
          LET kernel == XAddKernel(destination, source, width)
              newBytes == WordBytes(kernel.destination, width)
          IN \E valued \in WriteGPRCandidates(before.cpu,
               instruction.sourceIndex, instruction.sourceView, kernel.source) :
               LET afterCPU == ApplyStatusCPU(valued, kernel.flags)
               IN
               /\ WriteGPRAllowed(before.cpu, instruction.sourceIndex,
                    instruction.sourceView, kernel.source, valued)
               /\ WriteStatus(valued, kernel.flags, afterCPU)
               /\ FinishAtomicBody(before, span, instruction, afterCPU,
                    oldBytes, newBytes, result)
        [] OTHER ->
          LET accumulatorView == CASE width = 8 -> "low8"
                [] width = 16 -> "low16" [] width = 32 -> "low32"
                [] OTHER -> "full64"
              accumulator == ReadGPR(before.cpu, 0, accumulatorView)
              kernel == CompareExchangeKernel(accumulator, destination,
                                                source, width)
              newBytes == WordBytes(kernel.destination, width)
          IN \E compared \in
               IF kernel.equal THEN {before.cpu}
               ELSE WriteGPRCandidates(before.cpu, 0, accumulatorView,
                                        kernel.accumulator) :
               LET afterCPU == ApplyStatusCPU(compared, kernel.flags)
               IN /\ IF kernel.equal THEN compared = before.cpu
                      ELSE WriteGPRAllowed(before.cpu, 0, accumulatorView,
                             kernel.accumulator, compared)
               /\ WriteStatus(compared, kernel.flags, afterCPU)
               /\ FinishAtomicBody(before, span, instruction, afterCPU,
                    oldBytes, newBytes, result)

\* @type: ($machineCPUState, Int, Int) => Seq($amd64Byte);
RegisterPairBytes(cpu, lowIndex, highIndex) ==
  WordBytes(cpu.gpr[lowIndex], 64) \o WordBytes(cpu.gpr[highIndex], 64)

\* @type: ($machineCPUState, Bool, $machineCPUState) => Bool;
SetZF(before, value, after) == after = [before EXCEPT !.rflags.zf = value]

\* @type: ($machineState, $machineResolvedSpan,
\*   $atomicExecutionInstruction, $atomicExecutionResult) => Bool;
BlockAtomicBody(before, span, instruction, result) ==
  LET oldBytes == ReadSpanBytes(before.memory, span)
      sixteen == instruction.kind = "cmpxchg16b"
      halfWidth == IF sixteen THEN 64 ELSE 32
      halfBytes == halfWidth \div 8
      lowView == IF sixteen THEN "full64" ELSE "low32"
      expected == WordBytes(ReadGPR(before.cpu, 0, lowView), halfWidth) \o
                  WordBytes(ReadGPR(before.cpu, 2, lowView), halfWidth)
      replacement == WordBytes(ReadGPR(before.cpu, 3, lowView), halfWidth) \o
                     WordBytes(ReadGPR(before.cpu, 1, lowView), halfWidth)
      equal == expected = oldBytes
      newBytes == IF equal THEN replacement ELSE oldBytes
  IN /\ instruction.kind \in BlockKinds
     /\ AtomicRequestCompatible(instruction, span)
     /\ AtomicPreflight(instruction, before.cpu) = "allowed"
     /\ (sixteen => Aligned(span.linearBytes[1], 4))
     /\ IF equal
        THEN LET afterCPU == [before.cpu EXCEPT !.rflags.zf = TRUE]
             IN
               /\ SetZF(before.cpu, TRUE, afterCPU)
               /\ FinishAtomicBody(before, span, instruction, afterCPU,
                    oldBytes, newBytes, result)
        ELSE LET lowObserved == SubSeq(oldBytes, 1, halfBytes)
                 highObserved == SubSeq(oldBytes, halfBytes + 1,
                                        2 * halfBytes)
             IN \E lowCPU \in WriteGPRCandidates(before.cpu, 0, lowView,
                                                   BytesToWord(lowObserved)) :
                  \E pairCPU \in WriteGPRCandidates(lowCPU, 2, lowView,
                                                     BytesToWord(highObserved)) :
                  LET afterCPU == [pairCPU EXCEPT !.rflags.zf = FALSE]
                  IN
                  /\ WriteGPRAllowed(before.cpu, 0, lowView,
                       BytesToWord(lowObserved), lowCPU)
                  /\ WriteGPRAllowed(lowCPU, 2, lowView,
                       BytesToWord(highObserved), pairCPU)
                  /\ SetZF(pairCPU, FALSE, afterCPU)
                  /\ FinishAtomicBody(before, span, instruction, afterCPU,
                       oldBytes, newBytes, result)

\* @type: ($machineState, $machineResolvedSpan,
\*   $atomicExecutionInstruction, $atomicExecutionResult) => Bool;
AtomicBody(before, span, instruction, result) ==
  IF instruction.kind \in ScalarKinds
  THEN ScalarAtomicBody(before, span, instruction, result)
  ELSE BlockAtomicBody(before, span, instruction, result)

====================================================================
