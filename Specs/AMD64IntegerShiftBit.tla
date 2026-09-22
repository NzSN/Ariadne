-------------------- MODULE AMD64IntegerShiftBit --------------------
EXTENDS AMD64IntegerCore

\* @type: Int => Int;
CountMask(width) == IF width = 64 THEN 64 ELSE 32
\* @type: (Int, Int) => Int;
MaskedCount(count, width) == count % CountMask(width)
\* @type: (Int, Int) => Int;
RotateCount(count, width) == MaskedCount(count, width) % width
\* @type: (Int, Int) => Int;
CarryRotateCount(count, width) == MaskedCount(count, width) % (width + 1)

\* @type: (Str, $integerWord, Int, Int) => $integerWord;
ShiftValue(kind, value, width, count) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE CASE kind = "shl" -> IF bit > count THEN value[bit - count] ELSE FALSE
           [] kind = "shr" -> IF bit + count <= width THEN value[bit + count] ELSE FALSE
           [] OTHER -> IF bit + count <= width THEN value[bit + count]
                       ELSE value[width]]

\* @type: (Str, $integerWord, $integerWord, Int, Int, $integerFlags)
\*   => $integerFlagDomains;
ShiftFlagDomains(kind, before, result, width, count, oldFlags) ==
  IF count = 0 THEN ExactFlagDomains(oldFlags)
  ELSE [flag \in Flags |->
    CASE flag = "cf" ->
           IF count <= width
           THEN {IF kind = "shl" THEN before[width - count + 1]
                 ELSE before[count]}
           ELSE {IF kind = "sar" THEN before[width] ELSE FALSE}
      [] flag = "of" ->
           IF count = 1
           THEN {IF kind = "shl" THEN result[width] # before[width]
                 ELSE IF kind = "shr" THEN before[width] ELSE FALSE}
           ELSE BOOLEAN
      [] flag = "af" -> BOOLEAN
      [] flag = "pf" -> {ParityEven(result)}
      [] flag = "zf" -> {IsZero(result, width)}
      [] OTHER -> {result[width]}]

\* @type: (Str, $integerWord, Int, Int, $integerFlags,
\*   $integerWord, $integerFlags) => Bool;
ShiftAllowed(kind, before, rawCount, width, oldFlags, result, flags) ==
  LET count == MaskedCount(rawCount, width)
      exact == IF count = 0 THEN Truncate(before, width)
               ELSE ShiftValue(kind, before, width, count)
  IN /\ kind \in {"shl", "shr", "sar"}
     /\ result = exact
     /\ FlagsAllowed(flags,
          ShiftFlagDomains(kind, before, result, width, count, oldFlags))

\* @type: (Str, $integerWord, Int, Int) => $integerWord;
RotateValue(kind, value, width, count) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE LET source ==
      IF kind = "rol" THEN ((bit - count - 1) % width) + 1
      ELSE ((bit + count - 1) % width) + 1
    IN value[source]]

\* @type: (Str, $integerWord, Int, Int, $integerFlags) => $integerFlagDomains;
RotateFlagDomains(kind, result, width, masked, oldFlags) ==
  IF masked = 0 THEN ExactFlagDomains(oldFlags)
  ELSE LET cf == IF kind = "rol" THEN result[1] ELSE result[width]
       IN [flag \in Flags |->
         IF flag = "cf" THEN {cf}
         ELSE IF flag = "of" THEN
           IF masked = 1
           THEN {IF kind = "rol" THEN result[width] # cf
                 ELSE result[width] # result[width - 1]}
           ELSE BOOLEAN
         ELSE {oldFlags[flag]}]

\* @type: (Str, $integerWord, Int, Int, $integerFlags,
\*   $integerWord, $integerFlags) => Bool;
RotateAllowed(kind, before, rawCount, width, oldFlags, result, flags) ==
  LET masked == MaskedCount(rawCount, width)
      effective == masked % width
      exact == IF effective = 0 THEN Truncate(before, width)
               ELSE RotateValue(kind, before, width, effective)
  IN /\ kind \in {"rol", "ror"}
     /\ result = exact
     /\ FlagsAllowed(flags,
          RotateFlagDomains(kind, result, width, masked, oldFlags))

\* @type: ($integerWord, Bool, Int, Int) => Bool;
RingBit(value, carry, width, position) ==
  IF position = width + 1 THEN carry ELSE value[position]

\* @type: (Str, $integerWord, Bool, Int, Int) => $integerWord;
CarryRotateValue(kind, value, carry, width, count) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE LET ringWidth == width + 1
             source == IF kind = "rcl"
                       THEN ((bit - count - 1) % ringWidth) + 1
                       ELSE ((bit + count - 1) % ringWidth) + 1
         IN RingBit(value, carry, width, source)]

\* @type: (Str, $integerWord, Bool, Int, Int) => Bool;
CarryRotateCF(kind, value, carry, width, count) ==
  LET ringWidth == width + 1
      source == IF kind = "rcl"
                THEN ((width - count) % ringWidth) + 1
                ELSE ((width + count) % ringWidth) + 1
  IN RingBit(value, carry, width, source)

\* @type: (Str, $integerWord, Int, Int, $integerFlags,
\*   $integerWord, $integerFlags) => Bool;
CarryRotateAllowed(kind, before, rawCount, width, oldFlags, result, flags) ==
  LET masked == MaskedCount(rawCount, width)
      effective == masked % (width + 1)
      exact == IF effective = 0 THEN Truncate(before, width)
               ELSE CarryRotateValue(kind, before, oldFlags["cf"], width, effective)
      cf == IF effective = 0 THEN oldFlags["cf"]
            ELSE CarryRotateCF(kind, before, oldFlags["cf"], width, effective)
      domains == IF masked = 0 THEN ExactFlagDomains(oldFlags)
                 ELSE [flag \in Flags |->
                   IF flag = "cf" THEN {cf}
                   ELSE IF flag = "of" THEN
                     IF masked = 1
                     THEN {IF kind = "rcl" THEN exact[width] # cf
                           ELSE exact[width] # exact[width - 1]}
                     ELSE BOOLEAN
                   ELSE {oldFlags[flag]}]
  IN /\ kind \in {"rcl", "rcr"}
     /\ result = exact
     /\ FlagsAllowed(flags, domains)

\* @type: (Str, $integerWord, $integerWord, Int, Int) => $integerWord;
DoubleShiftValue(kind, destination, source, width, count) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE IF kind = "shld"
      THEN IF bit > count THEN destination[bit - count]
           ELSE source[width - count + bit]
      ELSE IF bit + count <= width THEN destination[bit + count]
           ELSE source[bit + count - width]]

\* AMD states that the destination is undefined when count exceeds width.
\* The candidate predicate constrains only its shape in that case.
\* @type: (Str, $integerWord, $integerWord, Int, Int, $integerFlags,
\*   $integerWord, $integerFlags) => Bool;
DoubleShiftAllowed(kind, destination, source, rawCount, width, oldFlags,
                   result, flags) ==
  LET count == MaskedCount(rawCount, width)
      valueDefined == count <= width
      exact == IF count = 0 THEN Truncate(destination, width)
               ELSE DoubleShiftValue(kind, destination, source, width, count)
      domains == IF count = 0 THEN ExactFlagDomains(oldFlags)
                 ELSE [flag \in Flags |->
                   CASE flag = "cf" ->
                          IF valueDefined
                          THEN {IF kind = "shld"
                                THEN destination[width - count + 1]
                                ELSE destination[count]}
                          ELSE BOOLEAN
                     [] flag = "of" ->
                          IF count = 1 /\ valueDefined
                          THEN {IF kind = "shld"
                                THEN exact[width] # destination[width]
                                ELSE destination[width] # exact[width]}
                          ELSE BOOLEAN
                     [] flag = "af" -> BOOLEAN
                     [] flag = "pf" -> IF valueDefined THEN {ParityEven(exact)} ELSE BOOLEAN
                     [] flag = "zf" -> IF valueDefined THEN {IsZero(exact, width)} ELSE BOOLEAN
                     [] OTHER -> IF valueDefined THEN {exact[width]} ELSE BOOLEAN]
  IN /\ kind \in {"shld", "shrd"}
     /\ WordWellFormed(result)
     /\ (valueDefined => result = exact)
     /\ (~valueDefined => \A bit \in (width + 1)..64 : ~result[bit])
     /\ FlagsAllowed(flags, domains)

\* @type: ($integerWord, Int, Int) => Bool;
BitTest(word, width, index) == word[(index % width) + 1]

\* @type: ($integerWord, Int) => Int;
LeastSetIndex(word, width) ==
  CHOOSE index \in 0..(width - 1) :
    word[index + 1] /\ \A lower \in 0..(index - 1) : ~word[lower + 1]

\* @type: ($integerWord, Int) => Int;
GreatestSetIndex(word, width) ==
  CHOOSE index \in 0..(width - 1) :
    word[index + 1] /\ \A higher \in (index + 1)..(width - 1) : ~word[higher + 1]

\* AMD Volume 3 pages 165-166 require BSF/BSR to preserve the destination
\* when the source is zero. The old destination is therefore explicit.
\* @type: (Str, $integerWord, $integerWord, Int, $integerWord, Bool) => Bool;
BitScanAllowed(direction, source, oldDestination, width, result, zf) ==
  /\ direction \in {"forward", "reverse"}
  /\ WordWellFormed(result)
  /\ zf = IsZero(source, width)
  /\ IF zf THEN result = oldDestination
     ELSE result = SmallNatWord(IF direction = "forward"
                                THEN LeastSetIndex(source, width)
                                ELSE GreatestSetIndex(source, width))

\* BSF/BSR define ZF and leave the other five status flags undefined.
\* @type: Bool => $integerFlagDomains;
BitScanFlagDomains(zf) ==
  [flag \in Flags |-> IF flag = "zf" THEN {zf} ELSE BOOLEAN]

\* BT/BTC/BTR/BTS define CF and leave the other five status flags undefined.
\* @type: Bool => $integerFlagDomains;
BitTestFlagDomains(cf) ==
  [flag \in Flags |-> IF flag = "cf" THEN {cf} ELSE BOOLEAN]

\* @type: ($integerWord, Int) => Int;
CountOnes(word, width) == Cardinality({bit \in 1..width : word[bit]})
\* @type: ($integerWord, Int) => $integerWord;
PopCount(word, width) == SmallNatWord(CountOnes(word, width))
\* @type: ($integerWord, Int) => $integerWord;
TrailingZeroCount(word, width) ==
  SmallNatWord(IF IsZero(word, width) THEN width ELSE LeastSetIndex(word, width))
\* @type: ($integerWord, Int) => $integerWord;
LeadingZeroCount(word, width) ==
  SmallNatWord(IF IsZero(word, width) THEN width
               ELSE width - 1 - GreatestSetIndex(word, width))

\* BEXTR clears CF/OF, defines ZF, and leaves SF/AF/PF undefined.
\* @type: ($integerWord, Int) => $integerFlagDomains;
BextrFlagDomains(result, width) ==
  [flag \in Flags |->
    CASE flag \in {"cf", "of"} -> {FALSE}
      [] flag = "zf" -> {IsZero(result, width)}
      [] OTHER -> BOOLEAN]

\* BZHI clears OF, defines SF/ZF, sets CF when the index is out of range,
\* and leaves AF/PF undefined.
\* @type: ($integerWord, Int, Int) => $integerFlagDomains;
BzhiFlagDomains(result, width, index) ==
  [flag \in Flags |->
    CASE flag = "cf" -> {index >= width}
      [] flag = "of" -> {FALSE}
      [] flag = "zf" -> {IsZero(result, width)}
      [] flag = "sf" -> {result[width]}
      [] OTHER -> BOOLEAN]

\* LZCNT/TZCNT define CF/ZF and leave OF/SF/AF/PF undefined. POPCNT
\* clears every arithmetic flag except ZF, which reports a zero source.
\* @type: (Str, $integerWord, $integerWord, Int) => $integerFlagDomains;
CountFlagDomains(kind, source, result, width) ==
  IF kind = "popcnt" THEN
    [flag \in Flags |-> IF flag = "zf" THEN {IsZero(source, width)} ELSE {FALSE}]
  ELSE [flag \in Flags |->
    CASE flag = "cf" -> {IsZero(source, width)}
      [] flag = "zf" -> {IsZero(result, width)}
      [] OTHER -> BOOLEAN]

\* @type: ($integerWord, Int, Int, Int) => $integerWord;
ExtractBits(source, width, start, length) ==
  [bit \in 1..64 |->
    IF bit <= length /\ start + bit <= width THEN source[start + bit]
    ELSE FALSE]

\* @type: ($integerWord, Int, Int) => $integerWord;
ZeroHighBits(source, width, index) ==
  [bit \in 1..64 |-> IF bit <= width /\ bit <= index THEN source[bit] ELSE FALSE]

\* @type: ($integerWord, Int) => Int;
MaskRank(mask, position) ==
  Cardinality({bit \in 1..(position - 1) : mask[bit]})

\* @type: ($integerWord, $integerWord, Int) => $integerWord;
ParallelDeposit(source, mask, width) ==
  [bit \in 1..64 |->
    IF bit <= width /\ mask[bit] THEN source[MaskRank(mask, bit) + 1] ELSE FALSE]

\* @type: ($integerWord, $integerWord, Int) => $integerWord;
ParallelExtract(source, mask, width) ==
  [bit \in 1..64 |->
    IF bit <= CountOnes(mask, width)
    THEN LET selected == CHOOSE sourceBit \in 1..width :
           mask[sourceBit] /\ MaskRank(mask, sourceBit) + 1 = bit
         IN source[selected]
    ELSE FALSE]

=============================================================================
