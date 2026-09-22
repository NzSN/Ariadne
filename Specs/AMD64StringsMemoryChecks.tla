------------------- MODULE AMD64StringsMemoryChecks -------------------
EXTENDS AMD64StringsMemory

Address(number) == SmallNatWord(number)
Byte(number) == [bit \in 1..8 |-> NatBitSmall(number, bit)]
A0 == Address(0)
A1 == Address(1)
A2 == Address(2)
B1 == Byte(1)
B2 == Byte(2)
B3 == Byte(3)

Memory0 == {
  [physical |-> A0, value |-> B1],
  [physical |-> A1, value |-> B2],
  [physical |-> A2, value |-> B3]}
Captured == {A0, A1, A2}
\* @type: Seq($amd64Byte);
Bytes1 == <<B1>>
Memory1 == WriteResolvedBytesResult(Memory0, <<A0>>, Bytes1)
MemoryOverlap1 == WriteResolvedBytesResult(Memory0, <<A1>>, Bytes1)
MemoryOverlap2 == WriteResolvedBytesResult(MemoryOverlap1, <<A2>>, Bytes1)
Captured1 == Captured \cup {A1}
Captured2 == Captured1 \cup {A2}

FalseFlags == [flag \in Flags |-> FALSE]
Control0 == [source |-> ZeroWord, destination |-> ZeroWord,
             count |-> OneWord, df |-> FALSE, status |-> FalseFlags]

MemoryChecks ==
  /\ CapturedMemoryWellFormed(Memory0, Captured)
  /\ ReadResolvedBytes(Memory0, Captured, <<A0>>, Bytes1)
  /\ ~SpanAvailable({A0}, <<A0, A1>>)
  /\ MoveIterationMemory(Memory0, Captured, <<A0>>, <<A1>>, Bytes1,
                          MemoryOverlap1, Captured1)
  /\ MoveIterationMemory(MemoryOverlap1, Captured1, <<A1>>, <<A2>>, Bytes1,
                          MemoryOverlap2, Captured2)
  /\ ReadByte(MemoryOverlap2, A2, B1)
  /\ LoadIterationValue(Memory0, Captured, <<A0>>, Bytes1,
                         BytesToWord(Bytes1))
  /\ StoreIterationMemory(Memory0, Captured, <<A1>>, BytesToWord(Bytes1), 1,
                           MemoryOverlap1, Captured1)
  /\ CompareByteSequences(Bytes1, Bytes1, 8)["zf"]
  /\ CurrentIterationFrames(Control0, Memory0, Control0, Memory0)
  /\ GPRWriteAllowed("long64", 32, ZeroWord,
                     [bit \in 1..64 |-> TRUE],
                     [bit \in 1..64 |-> bit <= 32])

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ MemoryChecks
=============================================================================
