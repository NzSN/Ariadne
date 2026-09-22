------------------ MODULE AMD64ConcreteMemoryChecks ------------------
EXTENDS AMD64ConcreteMemory

Zeros == [bit \in AddressBits |-> FALSE]
One == [bit \in AddressBits |-> bit = 1]
ZeroByte == [bit \in ByteBits |-> FALSE]
OneByte == [bit \in ByteBits |-> bit = 1]
ZeroCarry == [bit \in 1..65 |-> FALSE]

EmptyConcrete == [physicalBits |-> 52, defaultByte |-> ZeroByte, overrides |-> {}]
OneConcrete == ConcreteWrite(EmptyConcrete, Zeros, OneByte)
CapturedOne == {[physical |-> Zeros, value |-> OneByte]}

ConcreteContracts ==
  /\ ConcreteMemoryWellFormed(EmptyConcrete)
  /\ ConcreteMemoryWellFormed(OneConcrete)
  /\ ConcreteRead(EmptyConcrete, Zeros) = ZeroByte
  /\ ConcreteRead(OneConcrete, Zeros) = OneByte
  /\ ConcreteRead(OneConcrete, One) = ZeroByte
  /\ ConcreteRead(ConcreteWrite(OneConcrete, Zeros, ZeroByte), Zeros) = ZeroByte

KnowledgeContracts ==
  /\ ConcreteRefinesCaptured(OneConcrete, CapturedOne, {Zeros})
  /\ ~ConcreteRefinesCaptured(EmptyConcrete, CapturedOne, {Zeros})
  /\ ConcreteRefinesCaptured(EmptyConcrete, {}, {})
  /\ SnapshotWrite(EmptyConcrete, Zeros, OneByte, {}, {}, CapturedOne, {Zeros})
  /\ ReadByteResult({}, {}, Zeros,
       [kind |-> "unavailable", value |-> ZeroByte])

EntryByteContracts ==
  /\ SmallOffset(0) = Zeros
  /\ SmallOffset(1) = One
  /\ ConcreteBytesAt(OneConcrete, Zeros, <<OneByte>>, <<Zeros>>, <<ZeroCarry>>)

VARIABLE
  \* @type: Bool;
  checked

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ ConcreteContracts /\ KnowledgeContracts /\
          EntryByteContracts

========================================================================
