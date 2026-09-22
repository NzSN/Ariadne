---------------------- MODULE AMD64StringsMemory ----------------------
EXTENDS AMD64Strings, AMD64Memory

\* Actual resolved/captured byte binding for CMPS, LODS, MOVS, SCAS, STOS.
\* Resolved physical spans are produced by AMD64Memory's constrained address
\* pipeline. Missing captured bytes are unavailable, not zero and not a fault.
\* INS/OUTS remain outside this module until a device executor exists.

\* @typeAlias: stringByteSeq = Seq($amd64Byte);
\* @typeAlias: stringAddressSeq = Seq($amd64Address);

\* @type: (Set($amd64Address), $stringAddressSeq) => Bool;
SpanAvailable(captured, physicalSpan) ==
  \A index \in 1..Len(physicalSpan) : physicalSpan[index] \in captured

\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $stringByteSeq) => Bool;
ReadResolvedBytes(memory, captured, physicalSpan, values) ==
  /\ Len(values) = Len(physicalSpan)
  /\ SpanAvailable(captured, physicalSpan)
  /\ \A index \in 1..Len(physicalSpan) :
       ReadByte(memory, physicalSpan[index], values[index])

\* Values are least-significant byte first.
\* @type: $stringByteSeq => $integerWord;
BytesToWord(values) ==
  [bit \in 1..64 |->
    IF bit <= 8 * Len(values)
    THEN LET byteIndex == ((bit - 1) \div 8) + 1
             within == ((bit - 1) % 8) + 1
         IN values[byteIndex][within]
    ELSE FALSE]

\* @type: ($integerWord, Int) => $amd64Byte;
WordByte(word, index) ==
  [bit \in 1..8 |-> word[(index - 1) * 8 + bit]]

\* Architectural element sizes are exactly 1,2,4,8 bytes. Explicit sequence
\* constructors keep Snowcat's Seq type rather than an arbitrary Int function.
\* @type: ($integerWord, Int) => $stringByteSeq;
WordToBytes(word, byteCount) ==
  CASE byteCount = 1 -> <<WordByte(word, 1)>>
    [] byteCount = 2 -> <<WordByte(word, 1), WordByte(word, 2)>>
    [] byteCount = 4 -> <<WordByte(word, 1), WordByte(word, 2),
                         WordByte(word, 3), WordByte(word, 4)>>
    [] OTHER -> <<WordByte(word, 1), WordByte(word, 2),
                  WordByte(word, 3), WordByte(word, 4),
                  WordByte(word, 5), WordByte(word, 6),
                  WordByte(word, 7), WordByte(word, 8)>>

\* Resolved spans contain one address per byte. Uniqueness prevents ambiguous
\* simultaneous replacement and is supplied by the address resolver.
\* @type: $stringAddressSeq => Bool;
SpanUnique(physicalSpan) ==
  \A left, right \in 1..Len(physicalSpan) :
    physicalSpan[left] = physicalSpan[right] => left = right

\* @type: (Set($amd64ByteCell), $stringAddressSeq, $stringByteSeq)
\*   => Set($amd64ByteCell);
WriteResolvedBytesResult(memory, physicalSpan, values) ==
  {cell \in memory :
    \A index \in 1..Len(physicalSpan) : cell.physical # physicalSpan[index]} \cup
  {[physical |-> physicalSpan[index], value |-> values[index]] :
    index \in 1..Len(physicalSpan)}

\* @type: (Set($amd64ByteCell), $stringAddressSeq, $stringByteSeq,
\*   Set($amd64Address), Set($amd64ByteCell), Set($amd64Address)) => Bool;
WriteResolvedBytes(memory, physicalSpan, values, captured, after, afterCaptured) ==
  /\ Len(values) = Len(physicalSpan)
  /\ SpanUnique(physicalSpan)
  /\ after = WriteResolvedBytesResult(memory, physicalSpan, values)
  /\ afterCaptured = captured \cup {physicalSpan[index] : index \in 1..Len(physicalSpan)}

\* Source values are read from `before` before any destination replacement.
\* This gives the required overlap behavior across successive committed calls.
\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $stringAddressSeq, $stringByteSeq, Set($amd64ByteCell),
\*   Set($amd64Address)) => Bool;
MoveIterationMemory(before, captured, sourceSpan, destinationSpan, values,
                    after, afterCaptured) ==
  /\ ReadResolvedBytes(before, captured, sourceSpan, values)
  /\ WriteResolvedBytes(before, destinationSpan, values, captured,
                         after, afterCaptured)

\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $integerWord, Int, Set($amd64ByteCell), Set($amd64Address)) => Bool;
StoreIterationMemory(before, captured, destinationSpan, accumulator, byteCount,
                     after, afterCaptured) ==
  WriteResolvedBytes(before, destinationSpan, WordToBytes(accumulator, byteCount),
                     captured, after, afterCaptured)

\* @type: (Set($amd64ByteCell), Set($amd64Address), $stringAddressSeq,
\*   $stringByteSeq, $integerWord) => Bool;
LoadIterationValue(memory, captured, sourceSpan, values, accumulatorValue) ==
  /\ ReadResolvedBytes(memory, captured, sourceSpan, values)
  /\ accumulatorValue = BytesToWord(values)

\* CMPS passes source as left and destination as right. SCAS passes the
\* accumulator as left. `SubResult` supplies all six status flags.
\* @type: ($stringByteSeq, $stringByteSeq, Int) => $integerFlags;
CompareByteSequences(left, right, width) ==
  SubResult(BytesToWord(left), BytesToWord(right), FALSE, width).flags

\* General accumulator write relation with legacy upper bits unconstrained.
\* @type: (Str, Int, $integerWord, $integerWord, $integerWord) => Bool;
GPRWriteAllowed(mode, width, before, value, after) ==
  \A bit \in 1..64 :
    IF bit <= width THEN after[bit] = value[bit]
    ELSE IF mode = "long64" /\ width = 32 THEN ~after[bit]
    ELSE IF mode = "long64" \/ bit <= 32 THEN after[bit] = before[bit]
    ELSE TRUE

\* A fault or modeling-unavailable boundary cannot commit the current
\* iteration's CPU control or memory mutation.
\* @type: ($stringControl, Set($amd64ByteCell), $stringControl,
\*   Set($amd64ByteCell)) => Bool;
CurrentIterationFrames(beforeControl, beforeMemory, afterControl, afterMemory) ==
  afterControl = beforeControl /\ afterMemory = beforeMemory

=============================================================================
