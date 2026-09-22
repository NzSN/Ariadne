--------------- MODULE AMD64AtomicExecutionChecks ---------------
EXTENDS AMD64AtomicExecution, AMD64MachineAccessChecks

Request1 == [Request EXCEPT !.rawEffective = Zero64, !.byteCount = 1]
\* @type: $machineSpanWitness;
Witness1 == [effectiveBytes |-> <<Zero64>>,
  effectiveCarries |-> <<ZeroCarry>>,
  segmentRawBytes |-> <<Zero64>>, segmentCarries |-> <<ZeroCarry>>,
  linearBytes |-> <<Zero64>>]
\* @type: $machineResolvedSpan;
Resolved1 == [request |-> Request1, effectiveBytes |-> <<Zero64>>,
  linearBytes |-> <<Zero64>>, physicalBytes |-> <<Zero64>>,
  memoryType |-> WBType]
ZeroMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte, overrides |-> {}]
High8CPU == [CPU EXCEPT !.gpr[0] = Word({9})]
High8Machine == [cpu |-> High8CPU, memory |-> ZeroMemory]
XchgHigh8 == [kind |-> "xchg", width |-> 8, sourceIndex |-> 0,
  sourceView |-> "high8", lockPrefix |-> FALSE,
  cmpxchg8b |-> TRUE, cmpxchg16b |-> TRUE]

XAddCPU == [CPU EXCEPT !.gpr[3] = Word({1})]
XAddMachine == [cpu |-> XAddCPU, memory |-> Memory]
XAdd16 == [kind |-> "xadd", width |-> 16, sourceIndex |-> 3,
  sourceView |-> "low16", lockPrefix |-> FALSE,
  cmpxchg8b |-> TRUE, cmpxchg16b |-> TRUE]

\* @type: Seq($amd64Address);
Addresses8 == <<OffsetWord(0, 64), OffsetWord(1, 64),
  OffsetWord(2, 64), OffsetWord(3, 64), OffsetWord(4, 64),
  OffsetWord(5, 64), OffsetWord(6, 64), OffsetWord(7, 64)>>
\* @type: Seq($amd64Carry);
Carries8 == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry,
  ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>
Request8 == [Request EXCEPT !.rawEffective = Zero64, !.byteCount = 8]
\* @type: $machineSpanWitness;
Witness8 == [effectiveBytes |-> Addresses8, effectiveCarries |-> Carries8,
  segmentRawBytes |-> Addresses8, segmentCarries |-> Carries8,
  linearBytes |-> Addresses8]
\* @type: $machineResolvedSpan;
Resolved8 == [request |-> Request8, effectiveBytes |-> Addresses8,
  linearBytes |-> Addresses8, physicalBytes |-> Addresses8,
  memoryType |-> WBType]
BlockCPU == [CPU EXCEPT !.gpr[3] = Word({1})]
BlockMachine == [cpu |-> BlockCPU, memory |-> ZeroMemory]
CMPXCHG8B == [kind |-> "cmpxchg8b", width |-> 64,
  sourceIndex |-> 0, sourceView |-> "low32", lockPrefix |-> FALSE,
  cmpxchg8b |-> TRUE, cmpxchg16b |-> TRUE]
FailureMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> Zero64, value |-> OneByte]}]
FailureMachine == [cpu |-> CPU, memory |-> FailureMemory]

CMPXCHG16B == [kind |-> "cmpxchg16b", width |-> 128,
  sourceIndex |-> 0, sourceView |-> "full64", lockPrefix |-> FALSE,
  cmpxchg8b |-> TRUE, cmpxchg16b |-> TRUE]
NoCX16 == [CMPXCHG16B EXCEPT !.cmpxchg16b = FALSE]
UnknownGroup7 == [known |-> FALSE, gpRank |-> 0, pfRank |-> 1, acRank |-> 2]
GPFirst == [known |-> TRUE, gpRank |-> 0, pfRank |-> 1, acRank |-> 2]
PFFirst == [known |-> TRUE, gpRank |-> 1, pfRank |-> 0, acRank |-> 2]

AddressNat(value) == [bit \in AddressBits |->
  IF bit <= 16 THEN ((value \div (2 ^ (bit - 1))) % 2) = 1 ELSE FALSE]
CarryNat(left, right) == [bit \in 1..65 |->
  IF bit = 1 THEN FALSE
  ELSE IF bit <= 17
       THEN (left % (2 ^ (bit - 1))) + (right % (2 ^ (bit - 1))) >=
              (2 ^ (bit - 1))
       ELSE FALSE]
\* @type: Seq($amd64Address);
Addresses16 == <<AddressNat(4095), AddressNat(4096), AddressNat(4097),
  AddressNat(4098), AddressNat(4099), AddressNat(4100), AddressNat(4101),
  AddressNat(4102), AddressNat(4103), AddressNat(4104), AddressNat(4105),
  AddressNat(4106), AddressNat(4107), AddressNat(4108), AddressNat(4109),
  AddressNat(4110)>>
\* @type: Seq($amd64Carry);
Carries16 == <<CarryNat(4095, 0), CarryNat(4095, 1),
  CarryNat(4095, 2), CarryNat(4095, 3), CarryNat(4095, 4),
  CarryNat(4095, 5), CarryNat(4095, 6), CarryNat(4095, 7),
  CarryNat(4095, 8), CarryNat(4095, 9), CarryNat(4095, 10),
  CarryNat(4095, 11), CarryNat(4095, 12), CarryNat(4095, 13),
  CarryNat(4095, 14), CarryNat(4095, 15)>>
\* @type: Seq($amd64Carry);
ZeroCarries16 == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry,
  ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry,
  ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>
Request16 == [Request EXCEPT !.byteCount = 16]
\* @type: $machineSpanWitness;
Witness16 == [effectiveBytes |-> Addresses16,
  effectiveCarries |-> Carries16, segmentRawBytes |-> Addresses16,
  segmentCarries |-> ZeroCarries16, linearBytes |-> Addresses16]

\* @type: ($machineState, $machineCPUState, $amd64ConcreteMemory,
\*   $machineResolvedSpan, $atomicExecutionInstruction, Seq($amd64Byte),
\*   Seq($amd64Byte)) => $atomicExecutionResult;
ResultRecord(before, afterCPU, afterMemory, span, instruction, oldBytes,
             newBytes) ==
  LET writes == PlannedWrites(before.memory, span, newBytes)
      plan == [writes |-> writes, commitPolicy |-> "bodyAll",
               committed |-> Len(newBytes)]
  IN [disposition |-> "bodyApplied",
      state |-> [cpu |-> afterCPU, memory |-> afterMemory],
      plan |-> plan,
      event |-> ExecutionEvent(instruction, span, oldBytes, newBytes)]

XchgAfterCPU == [High8CPU EXCEPT !.gpr[0] = Zero64]
XchgAfterMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> Zero64, value |-> OneByte]}]
XchgResult == ResultRecord(High8Machine, XchgAfterCPU, XchgAfterMemory,
  Resolved1, XchgHigh8, <<ZeroByte>>, <<OneByte>>)

XAddKernelFixture == XAddKernel(Word({1}), Word({1}), 16)
XAddAfterCPU == [XAddCPU EXCEPT !.rflags =
  ApplyStatus(@, XAddKernelFixture.flags)]
TwoByte == [bit \in 1..8 |-> bit = 2]
XAddAfterMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> Addr4095, value |-> TwoByte]}]
XAddResult == ResultRecord(XAddMachine, XAddAfterCPU, XAddAfterMemory,
  ResolvedFixture, XAdd16, <<OneByte, ZeroByte>>, <<TwoByte, ZeroByte>>)

\* @type: Seq($amd64Byte);
Zeros8 == <<ZeroByte, ZeroByte, ZeroByte, ZeroByte,
            ZeroByte, ZeroByte, ZeroByte, ZeroByte>>
\* @type: Seq($amd64Byte);
OneThenZeros8 == <<OneByte, ZeroByte, ZeroByte, ZeroByte,
                   ZeroByte, ZeroByte, ZeroByte, ZeroByte>>
BlockAfterCPU == [BlockCPU EXCEPT !.rflags.zf = TRUE]
BlockAfterMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> Zero64, value |-> OneByte]}]
BlockResult == ResultRecord(BlockMachine, BlockAfterCPU, BlockAfterMemory,
  Resolved8, CMPXCHG8B, Zeros8, OneThenZeros8)
FailureAfterCPU == [CPU EXCEPT !.gpr[0] = Word({1}), !.rflags.zf = FALSE]
FailureResult == ResultRecord(FailureMachine, FailureAfterCPU, FailureMemory,
  Resolved8, CMPXCHG8B, OneThenZeros8, OneThenZeros8)

AccessContracts ==
  /\ ResolveSpan(Profile, Config, High8CPU, Pages, Request1, Witness1, Resolved1)
  /\ ResolveSpan(Profile, Config, BlockCPU, Pages, Request8, Witness8, Resolved8)
  /\ AtomicPreflight(NoCX16, CPU) = "UD-feature"
  /\ SpanWitnessWellFormed(Profile, Config, CPU, Request16, Witness16)
  /\ MandatoryAtomicFaults(CMPXCHG16B, Witness16) /= {}
  /\ Cardinality(AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
       Request16, Witness16, CMPXCHG16B)) = 2
  /\ \A candidate \in AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
       Request16, Witness16, CMPXCHG16B) :
       AtomicFaultSelected(UnknownGroup7,
         AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
           Request16, Witness16, CMPXCHG16B), candidate)
  /\ \A selected \in AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
       Request16, Witness16, CMPXCHG16B) :
       AtomicFaultSelected(GPFirst,
         AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
           Request16, Witness16, CMPXCHG16B), selected) =>
         selected.fault.vector = "GP"
  /\ \A selected \in AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
       Request16, Witness16, CMPXCHG16B) :
       AtomicFaultSelected(PFFirst,
         AtomicFaultCandidates(Config, CPU, ReadOnlyPages,
           Request16, Witness16, CMPXCHG16B), selected) =>
         selected.fault.vector = "PF"

BodyContracts ==
  /\ AtomicBody(High8Machine, Resolved1, XchgHigh8, XchgResult)
  /\ XchgResult.state.memory.overrides =
            {[physical |-> Zero64, value |-> OneByte]}
  /\ ~XchgResult.state.cpu.gpr[0][9]
  /\ XchgResult.event.locked /\ XchgResult.event.atomic
  /\ AtomicBody(XAddMachine, ResolvedFixture, XAdd16, XAddResult)
  /\ ~XAddResult.event.atomic
  /\ XAddResult.event.physicalBytes = <<Addr4095, FarPhysical>>
  /\ ConcreteRead(XAddResult.state.memory, Addr4095) = TwoByte
  /\ ReadGPR(XAddResult.state.cpu, 3, "low16") = Word({1})
  /\ AtomicBody(BlockMachine, Resolved8, CMPXCHG8B, BlockResult)
  /\ BlockResult.state.cpu.rflags.zf
  /\ ConcreteRead(BlockResult.state.memory, Zero64) = OneByte
  /\ ~BlockResult.event.atomic
  /\ AtomicBody(FailureMachine, Resolved8, CMPXCHG8B, FailureResult)
  /\ ~FailureResult.state.cpu.rflags.zf
  /\ FailureResult.state.cpu.gpr[0][1]
  /\ \A bit \in 33..64 : ~FailureResult.state.cpu.gpr[0][bit]
  /\ FailureResult.state.memory = FailureMemory

VARIABLE
  \* @type: Bool;
  aeChecked

AEInit == checked = FALSE /\ aeChecked = FALSE
AENext == checked' = ~checked /\ aeChecked' = ~aeChecked
AESafety == checked \in BOOLEAN /\ aeChecked \in BOOLEAN /\
            AccessContracts /\ BodyContracts

==================================================================
