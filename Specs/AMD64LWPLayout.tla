----------------------- MODULE AMD64LWPLayout -----------------------
EXTENDS AMD64ConcreteMemory, Integers, Sequences, FiniteSets

\* Concrete LWPCB decoding and normalization.
\* Authority: AMD APM Volume 2 rev. 3.45 PDF pages 535-539, 545-554.

\* @typeAlias: lwpLayoutProfile = {controlBlockQuadwords: Int,
\*   eventSize: Int, maxEvents: Int, eventOffset: Int,
\*   minimumBufferUnits: Int, availableFlags: Set(Int),
\*   minimumInterval: Int -> Int};
\* @typeAlias: lwpEventConfig = {eventId: Int, intervalRaw: Int,
\*   counterRaw: Int, interval: Int, counter: Int, reservedClear: Bool};
\* @typeAlias: lwpControlBlock = {requestedFlags: Int, bufferSize: Int,
\*   randomBits: Int, bufferBase: $amd64Address, bufferHeadOffset: Int,
\*   missedEvents: $amd64Address, threshold: Int, filters: Int,
\*   baseIP: $amd64Address, limitIP: $amd64Address,
\*   bufferTailOffset: Int, fixedReservedClear: Bool,
\*   softwareReservedClear: Bool, events: Int -> $lwpEventConfig};
\* @typeAlias: lwpNormalizedEvent = {eventId: Int, interval: Int,
\*   counter: Int};
\* @typeAlias: lwpNormalized = {enabledFlags: Set(Int), bufferSize: Int,
\*   randomBits: Int, bufferBase: $amd64Address, bufferHeadOffset: Int,
\*   missedEvents: $amd64Address, threshold: Int, filters: Int,
\*   baseIP: $amd64Address, limitIP: $amd64Address,
\*   bufferTailOffset: Int, tailProtocolValid: Bool,
\*   reservedProtocolValid: Bool, events: Int -> $lwpNormalizedEvent};
\* @typeAlias: lwpCaptureResult = {kind: Str, bytes: Seq($amd64Byte)};

\* @type: $lwpLayoutProfile => Int;
ControlBlockBytes(profile) == profile.controlBlockQuadwords * 8

\* @type: $lwpLayoutProfile => Bool;
LayoutProfileWellFormed(profile) ==
  /\ profile.eventSize > 0 /\ profile.maxEvents > 0
  /\ profile.eventOffset >= 88 /\ profile.eventOffset % 8 = 0
  /\ profile.eventOffset + profile.maxEvents * 8 <= ControlBlockBytes(profile)

RECURSIVE NatBit(_, _)
\* @type: (Int, Int) => Bool;
NatBit(value, bit) ==
  IF bit = 0 THEN value % 2 = 1 ELSE NatBit(value \div 2, bit - 1)

\* @type: $amd64Byte => Int;
ByteNat(byte) ==
  (IF byte[1] THEN 1 ELSE 0) + (IF byte[2] THEN 2 ELSE 0) +
  (IF byte[3] THEN 4 ELSE 0) + (IF byte[4] THEN 8 ELSE 0) +
  (IF byte[5] THEN 16 ELSE 0) + (IF byte[6] THEN 32 ELSE 0) +
  (IF byte[7] THEN 64 ELSE 0) + (IF byte[8] THEN 128 ELSE 0)

\* @type: (Seq($amd64Byte), Int, Int) => Int;
ReadLE(bytes, offset, count) ==
  (IF count >= 1 THEN ByteNat(bytes[offset + 1]) ELSE 0) +
  (IF count >= 2 THEN 256 * ByteNat(bytes[offset + 2]) ELSE 0) +
  (IF count >= 3 THEN 65536 * ByteNat(bytes[offset + 3]) ELSE 0) +
  (IF count >= 4 THEN 16777216 * ByteNat(bytes[offset + 4]) ELSE 0)

\* @type: Int => Int;
Signed26(raw) == IF raw % 67108864 >= 33554432
  THEN (raw % 67108864) - 67108864 ELSE raw % 67108864

\* @type: (Seq($amd64Byte), Int) => $amd64Address;
AddressAt(bytes, offset) == [bit \in 1..64 |->
  bytes[offset + ((bit - 1) \div 8) + 1][((bit - 1) % 8) + 1]]

\* @type: (Seq($amd64Byte), Int, Int) => Bool;
BytesZero(bytes, start, count) ==
  \A index \in 1..count : ByteNat(bytes[start + index]) = 0

\* @type: ($lwpLayoutProfile, Seq($amd64Byte), Int) => $lwpEventConfig;
DecodeEvent(profile, bytes, index) ==
  LET offset == profile.eventOffset + (index - 1) * 8
      intervalRaw == ReadLE(bytes, offset, 4)
      counterRaw == ReadLE(bytes, offset + 4, 4)
  IN [eventId |-> index, intervalRaw |-> intervalRaw,
      counterRaw |-> counterRaw, interval |-> Signed26(intervalRaw),
      counter |-> Signed26(counterRaw),
      reservedClear |-> intervalRaw \div 67108864 = 0 /\
                        counterRaw \div 67108864 = 0]

\* @type: ($lwpLayoutProfile, Seq($amd64Byte), $lwpControlBlock) => Bool;
DecodeControlBlock(profile, bytes, block) ==
  /\ LayoutProfileWellFormed(profile)
  /\ Len(bytes) = ControlBlockBytes(profile)
  /\ block = [requestedFlags |-> ReadLE(bytes, 0, 4),
       bufferSize |-> ReadLE(bytes, 4, 4) % 268435456,
       randomBits |-> ReadLE(bytes, 4, 4) \div 268435456,
       bufferBase |-> AddressAt(bytes, 8),
       bufferHeadOffset |-> ReadLE(bytes, 16, 4),
       missedEvents |-> AddressAt(bytes, 24),
       threshold |-> ReadLE(bytes, 32, 4),
       filters |-> ReadLE(bytes, 36, 4),
       baseIP |-> AddressAt(bytes, 40), limitIP |-> AddressAt(bytes, 48),
       bufferTailOffset |-> ReadLE(bytes, 64, 4),
       fixedReservedClear |-> BytesZero(bytes, 20, 4) /\
         BytesZero(bytes, 56, 8) /\ BytesZero(bytes, 68, 4),
       softwareReservedClear |-> BytesZero(bytes, 72, profile.eventOffset - 72),
       events |-> [event \in 1..profile.maxEvents |->
                    DecodeEvent(profile, bytes, event)]]

\* @type: ($lwpLayoutProfile, $lwpEventConfig) => $lwpNormalizedEvent;
NormalizeEvent(profile, event) ==
  LET minimum == IF event.eventId = 1 THEN 0
                 ELSE profile.minimumInterval[event.eventId]
      interval == IF event.interval < 0 THEN minimum
                  ELSE IF event.interval < minimum THEN minimum ELSE event.interval
      counter == IF event.counter < 0 THEN 0 ELSE event.counter
  IN [eventId |-> event.eventId, interval |-> interval, counter |-> counter]

\* Tail/reserved violations are protocol facts, not architectural faults.
\* @type: ($lwpLayoutProfile, $lwpControlBlock, $lwpNormalized) => Bool;
NormalizeControlBlock(profile, block, normalized) ==
  LET size == block.bufferSize - (block.bufferSize % profile.eventSize)
      minimum == 32 * profile.minimumBufferUnits * profile.eventSize
  IN /\ LayoutProfileWellFormed(profile)
     /\ size >= minimum /\ size > 0
     /\ normalized = [enabledFlags |->
          {bit \in 0..31 : bit \in profile.availableFlags /\
                            NatBit(block.requestedFlags, bit)},
        bufferSize |-> size, randomBits |-> block.randomBits,
        bufferBase |-> block.bufferBase,
        bufferHeadOffset |-> IF block.bufferHeadOffset >= size THEN 0
          ELSE block.bufferHeadOffset - (block.bufferHeadOffset % profile.eventSize),
        missedEvents |-> block.missedEvents,
        threshold |-> block.threshold - (block.threshold % profile.eventSize),
        filters |-> block.filters, baseIP |-> block.baseIP, limitIP |-> block.limitIP,
        bufferTailOffset |-> block.bufferTailOffset,
        tailProtocolValid |-> block.bufferTailOffset < size /\
          block.bufferTailOffset % profile.eventSize = 0,
        reservedProtocolValid |-> block.fixedReservedClear /\
          block.softwareReservedClear /\
          (\A event \in 1..profile.maxEvents : block.events[event].reservedClear),
        events |-> [event \in 1..profile.maxEvents |->
          NormalizeEvent(profile, block.events[event])]]

RECURSIVE ConcreteBytesAux(_, _, _)
\* @type: ($amd64ConcreteMemory, Seq($amd64Address), Int) => Seq($amd64Byte);
ConcreteBytesAux(memory, addresses, count) ==
  IF count = 0 THEN <<>>
  ELSE Append(ConcreteBytesAux(memory, addresses, count - 1),
              ConcreteRead(memory, addresses[count]))

\* @type: ($amd64ConcreteMemory, Seq($amd64Address)) => Seq($amd64Byte);
ConcreteLayoutBytes(memory, addresses) ==
  ConcreteBytesAux(memory, addresses, Len(addresses))

\* @type: ($lwpLayoutProfile, $amd64ConcreteMemory, Seq($amd64Address),
\*   $lwpControlBlock) => Bool;
DecodeConcrete(profile, memory, addresses, block) ==
  DecodeControlBlock(profile, ConcreteLayoutBytes(memory, addresses), block)

\* Analysis-only adapter. Unavailable capture has an empty byte sequence and
\* never supplies architectural zero bytes or a fault.
\* @type: (Set($amd64ByteCell), Set($amd64Address), Seq($amd64Address),
\*   $lwpCaptureResult) => Bool;
CaptureLayoutBytes(cells, domain, addresses, result) ==
  IF \A index \in 1..Len(addresses) : addresses[index] \in domain
  THEN /\ result.kind = "available"
       /\ Len(result.bytes) = Len(addresses)
       /\ \A index \in 1..Len(addresses) :
            ReadByte(cells, addresses[index], result.bytes[index])
  ELSE result = [kind |-> "unavailable", bytes |-> <<>>]

=======================================================================
