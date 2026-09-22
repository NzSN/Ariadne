-------------------- MODULE AMD64LWPLayoutChecks --------------------
EXTENDS AMD64LWPLayout

Byte(value) == [bit \in 1..8 |-> ((value \div (2 ^ (bit - 1))) % 2) = 1]
ZeroByte == Byte(0)
Address(value) == [bit \in 1..64 |-> bit <= 8 /\
  ((value \div (2 ^ (bit - 1))) % 2) = 1]

Profile == [controlBlockQuadwords |-> 16, eventSize |-> 32,
  maxEvents |-> 5, eventOffset |-> 88, minimumBufferUnits |-> 1,
  availableFlags |-> 0..6,
  minimumInterval |-> [event \in 1..5 |-> IF event = 1 THEN 0 ELSE 10]]

RECURSIVE ZeroByteSeq(_)
\* @type: Int => Seq($amd64Byte);
ZeroByteSeq(count) == IF count = 0 THEN <<>>
  ELSE Append(ZeroByteSeq(count - 1), ZeroByte)
\* @type: Seq($amd64Byte);
ZeroBytes == ZeroByteSeq(128)
\* BufferSize=1024, Head=33, Threshold=65, Tail=32, requested flags=3,
\* and EventInterval1=-33554432 in signed low-26 representation.
\* @type: Seq($amd64Byte);
Bytes == [ZeroBytes EXCEPT ![1] = Byte(3), ![6] = Byte(4),
  ![17] = Byte(33), ![33] = Byte(65), ![65] = Byte(32), ![92] = Byte(2)]

Event1 == DecodeEvent(Profile, Bytes, 1)
Event2 == DecodeEvent(Profile, Bytes, 2)
Block == [requestedFlags |-> 3, bufferSize |-> 1024, randomBits |-> 0,
  bufferBase |-> ZeroAddress, bufferHeadOffset |-> 33, missedEvents |-> ZeroAddress,
  threshold |-> 65, filters |-> 0, baseIP |-> ZeroAddress,
  limitIP |-> ZeroAddress, bufferTailOffset |-> 32,
  fixedReservedClear |-> TRUE, softwareReservedClear |-> TRUE,
  events |-> [event \in 1..5 |-> DecodeEvent(Profile, Bytes, event)]]
Normalized == [enabledFlags |-> {0, 1}, bufferSize |-> 1024,
  randomBits |-> 0, bufferBase |-> ZeroAddress, bufferHeadOffset |-> 32,
  missedEvents |-> ZeroAddress, threshold |-> 64, filters |-> 0,
  baseIP |-> ZeroAddress, limitIP |-> ZeroAddress, bufferTailOffset |-> 32,
  tailProtocolValid |-> TRUE, reservedProtocolValid |-> TRUE,
  events |-> [event \in 1..5 |-> NormalizeEvent(Profile, Block.events[event])]]

RECURSIVE AddressSeq(_)
\* @type: Int => Seq($amd64Address);
AddressSeq(count) == IF count = 0 THEN <<>>
  ELSE Append(AddressSeq(count - 1), Address(count - 1))
\* @type: Seq($amd64Address);
Addresses == AddressSeq(128)
Overrides == {
  [physical |-> Address(0), value |-> Byte(3)],
  [physical |-> Address(5), value |-> Byte(4)],
  [physical |-> Address(16), value |-> Byte(33)],
  [physical |-> Address(32), value |-> Byte(65)],
  [physical |-> Address(64), value |-> Byte(32)],
  [physical |-> Address(91), value |-> Byte(2)]}
Memory == [physicalBits |-> 52, defaultByte |-> ZeroByte, overrides |-> Overrides]
CapturedDomain == {Addresses[index] : index \in 1..Len(Addresses)}
CapturedCells == {[physical |-> Addresses[index], value |-> Bytes[index]] :
  index \in 1..Len(Addresses)}
CaptureAvailable == [kind |-> "available", bytes |-> Bytes]
CaptureUnavailable == [kind |-> "unavailable", bytes |-> <<>>]

LayoutChecks ==
  /\ LayoutProfileWellFormed(Profile)
  /\ DecodeControlBlock(Profile, Bytes, Block)
  /\ NormalizeControlBlock(Profile, Block, Normalized)
  /\ Event1.interval = -33554432
  /\ Normalized.events[1].interval = 0
  /\ Event2.interval = 0 /\ Normalized.events[2].interval = 10
  /\ ConcreteMemoryWellFormed(Memory)
  /\ ConcreteLayoutBytes(Memory, Addresses) = Bytes
  /\ DecodeConcrete(Profile, Memory, Addresses, Block)
  /\ ConcreteRefinesCaptured(Memory, CapturedCells, CapturedDomain)
  /\ CaptureLayoutBytes(CapturedCells, CapturedDomain, Addresses, CaptureAvailable)
  /\ CaptureLayoutBytes(CapturedCells, CapturedDomain \ {Address(91)},
                        Addresses, CaptureUnavailable)

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ LayoutChecks
=======================================================================
