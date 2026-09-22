---------------------- MODULE AMD64MonitorChecks ----------------------
EXTENDS AMD64Monitor

ZeroBits(width) == [bit \in 1..width |-> FALSE]
OneBits(width) == [bit \in 1..width |-> TRUE]
Word(bits) == [bit \in 1..64 |-> bit \in bits]
Zero64 == ZeroBits(64)
ZeroCarry == ZeroBits(65)
Addr4095 == Word(1..12)

Segment(long) == [selector |-> ZeroBits(16), base |-> Zero64,
  limit |-> OneBits(32), present |-> TRUE, dpl |-> 0, readable |-> TRUE,
  writable |-> TRUE, executable |-> TRUE, conforming |-> FALSE,
  expandDown |-> FALSE, defaultBig |-> FALSE, longMode |-> long,
  unusable |-> FALSE]
Segments == [cs |-> Segment(TRUE), ss |-> Segment(FALSE),
  ds |-> Segment(FALSE), es |-> Segment(FALSE),
  fs |-> Segment(FALSE), gs |-> Segment(FALSE)]
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
CPU == [gpr |-> [r \in 0..15 |-> IF r = 0 THEN Addr4095 ELSE Zero64],
  rip |-> Zero64, rflags |-> Flags, segments |-> Segments, x87 |-> X87,
  vectors |-> [r \in 0..31 |-> ZeroBits(512)],
  kMask |-> [r \in 0..7 |-> Zero64], mxcsr |-> MXCSR,
  execution |-> [mode |-> "long64", cpl |-> 0,
    features |-> [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
      avxEnabled |-> TRUE, avx512Enabled |-> TRUE]]]
Capabilities == [longMode |-> TRUE, x87 |-> TRUE, mmx |-> TRUE,
  sse |-> TRUE, avx |-> TRUE, avx512 |-> TRUE,
  mxcsrMisalignedMask |-> FALSE]
Architecture == [capabilities |-> Capabilities,
  physicalAddressBits |-> 52, linearAddressBits |-> 48]
Config == [virtualBits |-> 48, paging |-> TRUE, a20Enabled |-> TRUE,
  cr0AM |-> FALSE, cr0WP |-> TRUE, cr4PAE |-> TRUE,
  cr4SMEP |-> FALSE, cr4SMAP |-> FALSE, cr4PKE |-> FALSE,
  cr4CET |-> FALSE, eferNXE |-> TRUE, iopl |-> 0,
  pkruAD |-> [key \in 0..15 |-> FALSE],
  pkruWD |-> [key \in 0..15 |-> FALSE]]
Page0 == [linearTag |-> Zero64, physicalTag |-> Zero64, offsetBits |-> 12,
  present |-> TRUE, writable |-> TRUE, user |-> FALSE,
  executable |-> TRUE, reserved |-> FALSE, shadowStack |-> FALSE,
  protectionKey |-> 0]
Pages == {Page0}

Profile == [monitorx |-> TRUE, interruptBreak |-> TRUE,
  minimumLineBytes |-> 1, maximumLineBytes |-> 1]
WB == Resolved("WB")
UC == Resolved("UC")
Request == MonitorRequest(CPU, 64, "ds", WB)
\* @type: {effectiveBytes: Seq($amd64Bits), effectiveCarries: Seq($amd64Bits),
\*   segmentRawBytes: Seq($amd64Bits), segmentCarries: Seq($amd64Bits),
\*   linearBytes: Seq($amd64Bits)};
Witness == [effectiveBytes |-> <<Addr4095>>,
  effectiveCarries |-> <<ZeroCarry>>,
  segmentRawBytes |-> <<Addr4095>>,
  segmentCarries |-> <<ZeroCarry>>,
  linearBytes |-> <<Addr4095>>]
\* @type: {request: {rawEffective: $amd64Bits, addressSize: Int,
\*   segmentName: Str, access: {kind: Str, stack: Bool,
\*     implicitSupervisor: Bool, shadow: Bool}, byteCount: Int,
\*   alignmentBits: Int,
\*   memoryType: {kind: Str, memoryType: Str, reason: Str}},
\*   effectiveBytes: Seq($amd64Bits), linearBytes: Seq($amd64Bits),
\*   physicalBytes: Seq($amd64Bits),
\*   memoryType: {kind: Str, memoryType: Str, reason: Str}};
ResolvedWB == [request |-> Request,
  effectiveBytes |-> <<Addr4095>>, linearBytes |-> <<Addr4095>>,
  physicalBytes |-> <<Addr4095>>, memoryType |-> WB]
ResolvedUC == [ResolvedWB EXCEPT !.request.memoryType = UC, !.memoryType = UC]
Range == [bytes |-> {Addr4095}]
Idle == [range |-> {}, pending |-> FALSE]
Armed == [range |-> {Addr4095}, pending |-> TRUE]
NMI == [kind |-> "nmi", committedLinearBytes |-> {},
  elapsedP0 |-> Zero64, unmasked |-> FALSE]

MonitorChecks ==
  /\ Request.byteCount = 1 /\ Request.access.kind = "read"
  /\ ExecuteMONITORX(Profile, Architecture, Config, CPU, Pages,
       64, "ds", WB, Witness, ResolvedWB, Range, Idle,
       CPU, Armed, "armed")
  /\ BindResolvedMonitor(Profile, CPU, Idle, Range, ResolvedUC,
       CPU, Idle, "sourceUnspecified")
  /\ ExecuteMWAITX(Profile, CPU, Armed, NMI, CPU, Idle, "woke")
  /\ ExecuteMWAITX([Profile EXCEPT !.monitorx = FALSE], CPU, Armed,
       NMI, CPU, Armed, "UD")
  /\ ObserveCommittedStore(Armed, {Addr4095}, Idle)

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ MonitorChecks
=======================================================================
