-------------------- MODULE AMD64AtomicChecks --------------------
EXTENDS AMD64Atomic

ZeroWord == [bit \in 1..64 |-> FALSE]
OneWord == [bit \in 1..64 |-> bit = 1]
TwoWord == [bit \in 1..64 |-> bit = 2]
ZeroByte == [bit \in ByteBits |-> FALSE]
OneByte == [bit \in ByteBits |-> bit = 1]
Zeros == [bit \in AddressBits |-> FALSE]
Misaligned16 == [bit \in AddressBits |-> bit = 1]
ZeroCarry == [bit \in 1..65 |-> FALSE]
BeforeMemory == [physicalBits |-> 52, defaultByte |-> ZeroByte, overrides |-> {}]
AfterMemory == ConcreteWrite(BeforeMemory, Zeros, OneByte)

KernelContracts ==
  LET xadd == XAddKernel(OneWord, OneWord, 8)
      equal == CompareExchangeKernel(OneWord, OneWord, TwoWord, 8)
      unequal == CompareExchangeKernel(ZeroWord, OneWord, TwoWord, 8)
  IN /\ xadd.destination = TwoWord /\ xadd.source = OneWord
     /\ equal.equal /\ equal.destination = TwoWord
     /\ ~unequal.equal /\ unequal.accumulator = OneWord

BlockContracts ==
  /\ CompareExchangeBlock(<<ZeroByte>>, <<ZeroByte>>, <<OneByte>>).zf
  /\ CompareExchangeBlock(<<ZeroByte>>, <<ZeroByte>>, <<OneByte>>).memory = <<OneByte>>
  /\ ~CompareExchangeBlock(<<ZeroByte>>, <<OneByte>>, <<ZeroByte>>).zf
  /\ CompareExchangeBlock(<<ZeroByte>>, <<OneByte>>, <<ZeroByte>>).expected = <<OneByte>>
  /\ AlignedForBytes(Zeros, 16)
  /\ ~AlignedForBytes(Misaligned16, 16)
  /\ BlockLegality(FALSE, Zeros, 16) = "feature-unavailable"
  /\ BlockLegality(TRUE, Misaligned16, 16) = "GP0"
  /\ BlockLegality(TRUE, Zeros, 16) = "allowed"

MemoryEventContracts ==
  /\ AtomicWriteOnDomain({Zeros}, <<Zeros>>, <<OneByte>>,
                         BeforeMemory, AfterMemory)
  /\ AtomicEvent("xchg", Zeros, 8, <<ZeroByte>>, <<OneByte>>,
                 FALSE, "WB").locked
  /\ AtomicEvent("xchg", Zeros, 8, <<ZeroByte>>, <<OneByte>>,
                 FALSE, "WB").atomic
  /\ ~AtomicEvent("xadd", Zeros, 8, <<ZeroByte>>, <<OneByte>>,
                  FALSE, "WB").locked
  /\ ~AtomicEvent("cmpxchg", Zeros, 8, <<ZeroByte>>, <<OneByte>>,
                  FALSE, "WB").atomic
  /\ AtomicEvent("xadd", Zeros, 8, <<ZeroByte>>, <<OneByte>>,
                 TRUE, "WB").atomic
  /\ AtomicAccessPermitted(
       [kind |-> "readWrite", stack |-> FALSE,
        implicitSupervisor |-> FALSE, shadow |-> FALSE],
       8, <<Zeros>>, {})
  /\ AtomicPreAccessLegality("cmpxchg16b", 128, TRUE, FALSE, "long64") =
       "UD-feature"
  /\ AtomicPreAccessLegality("cmpxchg16b", 128, TRUE, TRUE, "protected") =
       "UD-mode"
  /\ AtomicPreAccessLegality("cmpxchg16b", 128, TRUE, TRUE, "long64") =
       "allowed"
  /\ AtomicPreAccessLegality("xadd", 128, TRUE, TRUE, "long64") =
       "invalid-width"

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ KernelContracts /\ BlockContracts /\
          MemoryEventContracts
==================================================================
