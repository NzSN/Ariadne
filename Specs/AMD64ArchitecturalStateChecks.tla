--------------- MODULE AMD64ArchitecturalStateChecks ---------------
EXTENDS AMD64ArchitecturalState

Zeros(width) == [bit \in 1..width |-> FALSE]
Ones(width) == [bit \in 1..width |-> TRUE]

Capabilities == [
  longMode |-> TRUE, x87 |-> TRUE, mmx |-> TRUE, sse |-> TRUE,
  avx |-> TRUE, avx512 |-> TRUE, mxcsrMisalignedMask |-> TRUE]
Profile == [capabilities |-> Capabilities, physicalAddressBits |-> 52,
            linearAddressBits |-> 48]

Segment(long, big) == [
  selector |-> Zeros(16), base |-> Zeros(64), limit |-> Ones(32),
  present |-> TRUE, dpl |-> 0, readable |-> TRUE, writable |-> TRUE,
  executable |-> TRUE, conforming |-> FALSE, expandDown |-> FALSE, defaultBig |-> big,
  longMode |-> long, unusable |-> FALSE]
Segments == [
  cs |-> Segment(TRUE, FALSE), ss |-> Segment(FALSE, FALSE),
  ds |-> Segment(FALSE, FALSE), es |-> Segment(FALSE, FALSE),
  fs |-> Segment(FALSE, FALSE), gs |-> Segment(FALSE, FALSE)]

Flags == [
  cf |-> FALSE, fixed1 |-> TRUE, pf |-> FALSE, reserved3 |-> FALSE,
  af |-> FALSE, reserved5 |-> FALSE, zf |-> FALSE, sf |-> FALSE,
  tf |-> FALSE, interruptEnable |-> TRUE, df |-> FALSE, of |-> FALSE,
  iopl |-> Zeros(2), nestedTask |-> FALSE, reserved15 |-> FALSE,
  resume |-> FALSE, virtual8086 |-> FALSE, ac |-> FALSE,
  virtualInterrupt |-> FALSE, virtualInterruptPending |-> FALSE,
  id |-> FALSE, reservedHigh |-> Zeros(42)]

Status == [
  invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  stackFault |-> FALSE, errorSummary |-> FALSE, c0 |-> FALSE,
  c1 |-> FALSE, c2 |-> FALSE, top |-> 3, c3 |-> FALSE, busy |-> FALSE]
Control == [
  invalidMask |-> TRUE, denormalMask |-> TRUE, zeroDivideMask |-> TRUE,
  overflowMask |-> TRUE, underflowMask |-> TRUE, precisionMask |-> TRUE,
  reserved6 |-> TRUE, reserved7 |-> FALSE, precisionControl |-> "bits64",
  roundingControl |-> "nearest", infinityControl |-> FALSE,
  reservedHigh |-> Zeros(3)]
Pointer == [kind |-> "offset64", selector |-> Zeros(16),
            offset64 |-> Zeros(64), offset32 |-> Zeros(32),
            linear32 |-> Zeros(32)]
X87 == [physical |-> [r \in 0..7 |-> [bit \in 1..80 |-> r = 3 /\ bit <= 64]],
        tags |-> [r \in 0..7 |-> "empty"], status |-> Status,
        control |-> Control, lastInstruction |-> Pointer, lastData |-> Pointer,
        lastOpcode |-> Zeros(11)]
MXCSR == [
  invalid |-> FALSE, denormal |-> FALSE, zeroDivide |-> FALSE,
  overflow |-> FALSE, underflow |-> FALSE, precision |-> FALSE,
  denormalsAreZero |-> FALSE, invalidMask |-> TRUE, denormalMask |-> TRUE,
  zeroDivideMask |-> TRUE, overflowMask |-> TRUE, underflowMask |-> TRUE,
  precisionMask |-> TRUE, roundingControl |-> "nearest", flushToZero |-> FALSE,
  reserved16 |-> FALSE, misalignedMask |-> FALSE, reservedHigh |-> Zeros(14)]
State == [
  gpr |-> [r \in 0..15 |-> Zeros(64)], rip |-> Zeros(64), rflags |-> Flags,
  segments |-> Segments, x87 |-> X87,
  vectors |-> [r \in 0..31 |-> [bit \in 1..512 |-> r = 31 /\ bit = 512]],
  kMask |-> [r \in 0..7 |-> Zeros(64)], mxcsr |-> MXCSR,
  execution |-> [mode |-> "long64", cpl |-> 0,
    features |-> [x87Enabled |-> TRUE, sseEnabled |-> TRUE,
      avxEnabled |-> TRUE, avx512Enabled |-> TRUE]]]

AliasChecks ==
  /\ GPRIndex("rax") = 0 /\ GPRIndex("rcx") = 1
  /\ GPRIndex("rdx") = 2 /\ GPRIndex("rsi") = 6 /\ GPRIndex("rdi") = 7
  /\ RCX(State) = State.gpr[1] /\ RSI(State) = State.gpr[6]
  /\ RDI(State) = State.gpr[7]
  /\ ReadST(X87, 0) = X87.physical[3]
  /\ ReadMMX(X87, 3) = Ones(64)
  /\ ReadXMM(State.vectors, 31) = Zeros(128)
  /\ ReadYMM(State.vectors, 31) = Zeros(256)
  /\ VectorRegisterAvailable(Profile, State.execution, 31)
  /\ DefaultAddressWidth(Segments, "long64") = 64
  /\ DefaultInstructionPointerWidth(Segments, "long64") = 64
  /\ X87ControlInit = Control

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ CPUStateWellFormed(Profile, State) /\ AliasChecks
=====================================================================
