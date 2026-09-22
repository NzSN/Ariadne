--------------------- MODULE AMD64ExternalChecks ---------------------
EXTENDS AMD64External

Zero64 == [bit \in 1..64 |-> FALSE]
Zero128 == [bit \in 1..128 |-> FALSE]
ZeroBits(width) == [bit \in 1..width |-> FALSE]
OneBits(width) == [bit \in 1..width |-> TRUE]
Word(bits) == [bit \in 1..64 |-> bit \in bits]

Segment(long, base) == [selector |-> ZeroBits(16), base |-> base,
  limit |-> OneBits(32), present |-> TRUE, dpl |-> 0, readable |-> TRUE,
  writable |-> TRUE, executable |-> TRUE, conforming |-> FALSE,
  expandDown |-> FALSE, defaultBig |-> FALSE, longMode |-> long,
  unusable |-> FALSE]
Segments == [cs |-> Segment(TRUE, Zero64), ss |-> Segment(FALSE, Zero64),
  ds |-> Segment(FALSE, Zero64), es |-> Segment(FALSE, Zero64),
  fs |-> Segment(FALSE, Word({1})), gs |-> Segment(FALSE, Zero64)]
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
BaseCPU == [gpr |-> [r \in 0..15 |-> Zero64], rip |-> Zero64,
  rflags |-> Flags, segments |-> Segments, x87 |-> X87,
  vectors |-> [r \in 0..31 |-> ZeroBits(512)],
  kMask |-> [r \in 0..7 |-> Zero64], mxcsr |-> MXCSR,
  execution |-> [mode |-> "long64", cpl |-> 0,
    features |-> [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
      avxEnabled |-> TRUE, avx512Enabled |-> TRUE]]]

LegacyCPU == [BaseCPU EXCEPT !.execution.mode = "protected",
  !.segments.cs.longMode = FALSE, !.segments.cs.defaultBig = TRUE]
DecimalBefore == [LegacyCPU EXCEPT !.gpr[0] = NatWord(250), !.rflags.af = TRUE]
DecimalAfter == [DecimalBefore EXCEPT !.gpr[0] = NatWord(512),
  !.rflags.cf = TRUE, !.rflags.af = TRUE]

\* @type: Seq({function: Int, subfunction: Int, eax: Int, ebx: Int,
\*   ecx: Int, edx: Int});
CPUIDRows == <<[function |-> 1, subfunction |-> 0,
  eax |-> 2, ebx |-> 3, ecx |-> 4, edx |-> 5]>>
CPUIDProfile == [supported |-> TRUE, userDisable |-> FALSE, rows |-> CPUIDRows]
CPUIDBefore == [BaseCPU EXCEPT !.gpr[0] = NatWord(1)]
CPUIDAfter == [CPUIDBefore EXCEPT !.gpr[0] = NatWord(2),
  !.gpr[3] = NatWord(3), !.gpr[1] = NatWord(4), !.gpr[2] = NatWord(5)]

EntropySample == [kind |-> "rdrand", width |-> 32, valid |-> TRUE,
  value |-> Word({1}), provenance |-> "fixture-rng"]
EntropyAfter == [BaseCPU EXCEPT !.gpr[0] = Word({1}), !.rflags.cf = TRUE]
CRCAfter == [BaseCPU EXCEPT !.gpr[0] =
  Word({1, 2, 9, 10, 16, 17, 18, 20, 22, 23, 26, 29, 30, 31, 32})]

SSEProfile == [supported |-> TRUE, emulateFP |-> FALSE,
  taskSwitched |-> FALSE, osfxsr |-> TRUE]
SSEUnsupported == [SSEProfile EXCEPT !.supported = FALSE]
SSENoOS == [SSEProfile EXCEPT !.osfxsr = FALSE]
MMXProfile == [supported |-> TRUE, emulateFP |-> FALSE,
  taskSwitched |-> FALSE, pendingX87 |-> FALSE]
XMMOneAfter == [BaseCPU EXCEPT !.vectors[0] =
  [bit \in 1..512 |-> bit = 1]]
XMMReadAfter == [XMMOneAfter EXCEPT !.gpr[0] = Word({1})]
MMXX87After == [X87 EXCEPT
  !.physical[0] = [bit \in 1..80 |-> bit = 1 \/ bit > 64],
  !.tags = [r \in 0..7 |-> "valid"], !.status.top = 0]
MMXOneAfter == [BaseCPU EXCEPT !.x87 = MMXX87After]
MMXReadAfter == [MMXOneAfter EXCEPT !.gpr[0] = Word({1})]

FSReadAfter == [BaseCPU EXCEPT !.gpr[0] = Word({1})]
GSWriteAfter == [BaseCPU EXCEPT !.segments.gs.base = Word({1})]
RDPRUAfter == [BaseCPU EXCEPT !.gpr[0] = Word({1})]
Profile == [monitorx |-> TRUE, interruptBreak |-> TRUE]
Monitor == [armed |-> TRUE, base |-> 4096, byteCount |-> 64, pending |-> TRUE]
Entropy == {[kind |-> "rdseed", width |-> 32, valid |-> FALSE,
             value |-> 0, provenance |-> "fixture-rng"]}
EntropyResult == [kind |-> "bodyApplied", valid |-> FALSE, value |-> 0]
Wake == {[cause |-> "matchingStore", elapsed |-> 3, matchingStore |-> TRUE]}
WakeResult == [kind |-> "woke", cause |-> "matchingStore"]
AAAEdge == [ax |-> 512, cf |-> TRUE, af |-> TRUE, pf |-> FALSE,
            zf |-> FALSE, sf |-> FALSE,
            undefined |-> {"of", "sf", "zf", "pf"}]
AASEdge == [ax |-> 65034, cf |-> TRUE, af |-> TRUE, pf |-> FALSE,
            zf |-> FALSE, sf |-> FALSE,
            undefined |-> {"of", "sf", "zf", "pf"}]
\* @type: {operation: Str, beforeEnabled: Bool, afterEnabled: Bool,
\*   eventId: Int, memoryEffects: Seq(Str), result: Str};
LWPDisable == [operation |-> "disable", beforeEnabled |-> TRUE,
  afterEnabled |-> FALSE, eventId |-> 0, memoryEffects |-> <<"flush">>,
  result |-> "completed"]

LegacyChecks ==
  /\ DecimalDisposition("long64", "aaa", 10, 0, FALSE, FALSE, "UD")
  /\ DecimalDisposition("protected", "aam", 0, 7, FALSE, FALSE, "DE")
  /\ DecimalBody("aaa", 10, 250, TRUE, FALSE, AAAEdge)
  /\ DecimalBody("aas", 10, 0, TRUE, FALSE, AASEdge)
  /\ DecimalCPUTransition("aaa", 10, DecimalBefore, DecimalAfter, "bodyApplied")

ProfileChecks ==
  /\ CPUIDCPUTransition(CPUIDProfile, CPUIDBefore, CPUIDAfter, "bodyApplied")
  /\ EntropyStep("rdseed", 32, Entropy, EntropyResult)
  /\ EntropySampleCPUTransition(TRUE, "rdrand", 32, 0, EntropySample,
                                BaseCPU, EntropyAfter, "bodyApplied")
  /\ CRC32CPUTransition(TRUE, 0, 32, 8, Word({1}), BaseCPU,
                        CRCAfter, "bodyApplied")
  /\ CRC32CPUTransition(TRUE, 0, 32, 64, Word({1}), BaseCPU,
                        BaseCPU, "formRejected")

MediaChecks ==
  /\ MOVMSKPD(Zero128) = Zero64
  /\ MOVMSKPS(Zero128) = Zero64
  /\ MOVDToXMMCPUTransition(SSEProfile, BaseCPU, 0, 32, Word({1}),
                            XMMOneAfter, "bodyApplied")
  /\ MOVDFromXMMCPUTransition(SSEProfile, XMMOneAfter, 0, 0, 32,
                              XMMReadAfter, "bodyApplied")
  /\ MOVDToMMXCPUTransition(MMXProfile, BaseCPU, 0, 32, Word({1}),
                            MMXOneAfter, "bodyApplied")
  /\ MOVDFromMMXCPUTransition(MMXProfile, MMXOneAfter, 0, 0, 32,
                              MMXReadAfter, "bodyApplied")
  /\ MOVMSKCPUTransition(SSEProfile, "pd", BaseCPU, 0, 0,
                         BaseCPU, "bodyApplied")
  /\ MOVMSKCPUTransition(SSEUnsupported, "ps", BaseCPU, 0, 0,
                         BaseCPU, "UD")
  /\ MOVMSKCPUTransition(SSENoOS, "pd", BaseCPU, 0, 0,
                         BaseCPU, "UD")

RegisterChecks ==
  /\ ReadBaseCPUTransition(TRUE, TRUE, "fs", BaseCPU, 0, 64,
                           FSReadAfter, "bodyApplied")
  /\ ReadBaseCPUTransition(TRUE, TRUE, "fs", BaseCPU, 0, 8,
                           BaseCPU, "formRejected")
  /\ WriteBaseCPUTransition(TRUE, TRUE, 48, "gs", BaseCPU, Word({1}), 64,
                            GSWriteAfter, "bodyApplied")
  /\ WriteBaseCPUTransition(TRUE, TRUE, 48, "gs", BaseCPU, Word({1}), 8,
                            BaseCPU, "formRejected")
  /\ RDPIDCPUTransition(TRUE, Word({1}), BaseCPU, 0,
                        FSReadAfter, "bodyApplied")
  /\ RDPRUCPUTransition(TRUE, FALSE, Word({1}), Zero64, 1,
                        BaseCPU, RDPRUAfter, "bodyApplied")
  /\ NOPCPUTransition(BaseCPU, BaseCPU)
  /\ PAUSECPUTransition(TRUE, BaseCPU, BaseCPU, "bodyApplied")

EnvironmentChecks ==
  /\ MWaitXStep(Profile, Monitor, 0, 0, Wake, WakeResult)
  /\ LWPStepWellFormed(LWPDisable)

ExternalChecks == LegacyChecks /\ ProfileChecks /\ MediaChecks /\
                  RegisterChecks /\ EnvironmentChecks

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ ExternalChecks
LegacySafety == checked \in BOOLEAN /\ LegacyChecks
ProfileSafety == checked \in BOOLEAN /\ ProfileChecks
MediaSafety == checked \in BOOLEAN /\ MediaChecks
RegisterSafety == checked \in BOOLEAN /\ RegisterChecks
EnvironmentSafety == checked \in BOOLEAN /\ EnvironmentChecks
=======================================================================
