---------------- MODULE AMD64MachineAccessChecks ----------------
EXTENDS AMD64MachineAccess

ZeroBits(width) == [bit \in 1..width |-> FALSE]
OneBits(width) == [bit \in 1..width |-> TRUE]
Word(bits) == [bit \in 1..64 |-> bit \in bits]
Zero64 == ZeroBits(64)
ZeroCarry == ZeroBits(65)
CarryTo13 == [bit \in 1..65 |-> bit \in 2..13]
ZeroByte == ZeroBits(8)
OneByte == [bit \in 1..8 |-> bit = 1]
Addr4095 == Word(1..12)
Addr4096 == Word({13})
FarPhysical == Word({21})

Segment(long, base) == [selector |-> ZeroBits(16), base |-> base,
  limit |-> OneBits(32), present |-> TRUE, dpl |-> 0, readable |-> TRUE,
  writable |-> TRUE, executable |-> TRUE, conforming |-> FALSE,
  expandDown |-> FALSE, defaultBig |-> FALSE, longMode |-> long,
  unusable |-> FALSE]
Segments == [cs |-> Segment(TRUE, Zero64), ss |-> Segment(FALSE, Zero64),
  ds |-> Segment(FALSE, Zero64), es |-> Segment(FALSE, Zero64),
  fs |-> Segment(FALSE, Zero64), gs |-> Segment(FALSE, Zero64)]
Flags == [cf |-> FALSE, fixed1 |-> TRUE, pf |-> FALSE,
  reserved3 |-> FALSE, af |-> FALSE, reserved5 |-> FALSE,
  zf |-> FALSE, sf |-> FALSE, tf |-> FALSE, interruptEnable |-> TRUE,
  df |-> FALSE, of |-> FALSE, iopl |-> ZeroBits(2), nestedTask |-> FALSE,
  reserved15 |-> FALSE, resume |-> FALSE, virtual8086 |-> FALSE,
  ac |-> FALSE, virtualInterrupt |-> FALSE,
  virtualInterruptPending |-> FALSE, id |-> FALSE,
  reservedHigh |-> ZeroBits(42)]
XStatus == [invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  stackFault |-> FALSE, errorSummary |-> FALSE, c0 |-> FALSE,
  c1 |-> FALSE, c2 |-> FALSE, top |-> 0, c3 |-> FALSE, busy |-> FALSE]
XControl == [invalidMask |-> TRUE, denormalMask |-> TRUE,
  zeroDivideMask |-> TRUE, overflowMask |-> TRUE, underflowMask |-> TRUE,
  precisionMask |-> TRUE, reserved6 |-> TRUE, reserved7 |-> FALSE,
  precisionControl |-> "bits64", roundingControl |-> "nearest",
  infinityControl |-> FALSE, reservedHigh |-> ZeroBits(3)]
XPointer == [kind |-> "offset64", selector |-> ZeroBits(16),
  offset64 |-> Zero64, offset32 |-> ZeroBits(32), linear32 |-> ZeroBits(32)]
X87 == [physical |-> [r \in 0..7 |-> ZeroBits(80)],
  tags |-> [r \in 0..7 |-> "empty"], status |-> XStatus,
  control |-> XControl, lastInstruction |-> XPointer,
  lastData |-> XPointer, lastOpcode |-> ZeroBits(11)]
MXCSR == [invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  denormalsAreZero |-> FALSE, invalidMask |-> TRUE, denormalMask |-> TRUE,
  zeroDivideMask |-> TRUE, overflowMask |-> TRUE, underflowMask |-> TRUE,
  precisionMask |-> TRUE, roundingControl |-> "nearest", flushToZero |-> FALSE,
  reserved16 |-> FALSE, misalignedMask |-> FALSE,
  reservedHigh |-> ZeroBits(14)]
CPU == [gpr |-> [r \in 0..15 |-> Zero64], rip |-> Zero64,
  rflags |-> Flags, segments |-> Segments, x87 |-> X87,
  vectors |-> [r \in 0..31 |-> ZeroBits(512)],
  kMask |-> [r \in 0..7 |-> Zero64], mxcsr |-> MXCSR,
  execution |-> [mode |-> "long64", cpl |-> 3,
    features |-> [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
      avxEnabled |-> TRUE, avx512Enabled |-> TRUE]]]
Capabilities == [longMode |-> TRUE, x87 |-> TRUE, mmx |-> TRUE,
  sse |-> TRUE, avx |-> TRUE, avx512 |-> TRUE,
  mxcsrMisalignedMask |-> FALSE]
Profile == [capabilities |-> Capabilities,
  physicalAddressBits |-> 52, linearAddressBits |-> 48]
Config == [virtualBits |-> 48, paging |-> TRUE, a20Enabled |-> TRUE,
  cr0AM |-> FALSE, cr0WP |-> TRUE, cr4PAE |-> TRUE,
  cr4SMEP |-> FALSE, cr4SMAP |-> FALSE, cr4PKE |-> FALSE,
  cr4CET |-> FALSE, eferNXE |-> TRUE, iopl |-> 0,
  pkruAD |-> [key \in 0..15 |-> FALSE],
  pkruWD |-> [key \in 0..15 |-> FALSE]]

Page(linear, physical, writable) ==
  [linearTag |-> linear, physicalTag |-> physical, offsetBits |-> 12,
   present |-> TRUE, writable |-> writable, user |-> TRUE,
   executable |-> TRUE, reserved |-> FALSE, shadowStack |-> FALSE,
   protectionKey |-> 0]
Page0 == Page(Zero64, Zero64, TRUE)
Page1 == Page(Addr4096, FarPhysical, TRUE)
ReadOnlyPage1 == Page(Addr4096, FarPhysical, FALSE)
Pages == {Page0, Page1}
ReadOnlyPages == {Page0, ReadOnlyPage1}
Access == [kind |-> "readWrite", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]
WBType == Resolved("WB")
Request == [rawEffective |-> Addr4095, addressSize |-> 64,
  segmentName |-> "ds", access |-> Access, byteCount |-> 2,
  alignmentBits |-> 0, memoryType |-> WBType]
\* @type: $machineSpanWitness;
Witness == [effectiveBytes |-> <<Addr4095, Addr4096>>,
  effectiveCarries |-> <<ZeroCarry, CarryTo13>>,
  segmentRawBytes |-> <<Addr4095, Addr4096>>,
  segmentCarries |-> <<ZeroCarry, ZeroCarry>>,
  linearBytes |-> <<Addr4095, Addr4096>>]
\* @type: $machineResolvedSpan;
ResolvedFixture == [request |-> Request,
  effectiveBytes |-> <<Addr4095, Addr4096>>,
  linearBytes |-> <<Addr4095, Addr4096>>,
  physicalBytes |-> <<Addr4095, FarPhysical>>,
  memoryType |-> WBType]
Memory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> Addr4095, value |-> OneByte]}]
Machine == [cpu |-> CPU, memory |-> Memory]

WriteEffects == {
  [index |-> 1, physical |-> Addr4095, before |-> OneByte, after |-> ZeroByte],
  [index |-> 2, physical |-> FarPhysical, before |-> ZeroByte, after |-> OneByte]}
AllPlan == [writes |-> WriteEffects, commitPolicy |-> "bodyAll", committed |-> 2]
RollbackPlan == [writes |-> WriteEffects, commitPolicy |-> "rollback", committed |-> 0]
PrefixPlan == [writes |-> WriteEffects, commitPolicy |-> "committedPrefix", committed |-> 1]
AllMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte,
  overrides |-> {[physical |-> FarPhysical, value |-> OneByte]}]
PrefixMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte, overrides |-> {}]

Contracts ==
  /\ MachineStateWellFormed(Profile, Machine)
  /\ SpanWitnessWellFormed(Profile, Config, CPU, Request, Witness)
  /\ ResolveSpan(Profile, Config, CPU, Pages, Request, Witness, ResolvedFixture)
  /\ ResolvedFixture.physicalBytes[1] = Addr4095
  /\ ResolvedFixture.physicalBytes[2] = FarPhysical
  /\ MachineRead(Memory, ResolvedFixture, <<OneByte, ZeroByte>>)
  /\ PlanWrites(Memory, ResolvedFixture, <<ZeroByte, OneByte>>, WriteEffects)
  /\ EffectPlanWellFormed(AllPlan)
  /\ EffectPlanWellFormed(RollbackPlan)
  /\ EffectPlanWellFormed(PrefixPlan)
  /\ ApplyCommittedPrefix(Memory, AllPlan, AllMemory)
  /\ ApplyCommittedPrefix(Memory, RollbackPlan, Memory)
  /\ ApplyCommittedPrefix(Memory, PrefixPlan, PrefixMemory)
  /\ SpanFaultCandidates(Config, CPU, ReadOnlyPages, Request, Witness) =
       {[index |-> 2,
         fault |-> [stage |-> 2, vector |-> "PF",
           reason |-> "page-protection",
           errorCode |-> PageFaultError(Config, 3, FALSE, ReadOnlyPage1, Access),
           linear |-> Addr4096]]}

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ Contracts

==================================================================
