--------------------- MODULE AMD64IntegerMulDiv ---------------------
EXTENDS AMD64IntegerCore

\* Double-width values are Boolean maps; multiplication uses bounded column
\* carries, never conversion of a 64-bit word to a host integer.
\* @typeAlias: integerDoubleWord = Int -> Bool;

\* @type: $integerDoubleWord => Bool;
DoubleWordWellFormed(word) == DOMAIN word = 1..128 /\
                              \A bit \in 1..128 : word[bit] \in BOOLEAN

\* @type: $integerDoubleWord;
DoubleZero == [bit \in 1..128 |-> FALSE]

\* @type: ($integerWord, $integerWord, Int) => $integerDoubleWord;
WideFromHalves(low, high, width) ==
  [bit \in 1..128 |->
    IF bit <= width THEN low[bit]
    ELSE IF bit <= 2 * width THEN high[bit - width] ELSE FALSE]

\* @type: ($integerDoubleWord, Int) => $integerWord;
LowHalf(wide, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN wide[bit] ELSE FALSE]

\* @type: ($integerDoubleWord, Int) => $integerWord;
HighHalf(wide, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN wide[bit + width] ELSE FALSE]

\* @type: ($integerWord, $integerWord, Int, Int) => Set(Int);
ProductTerms(left, right, width, column) ==
  {leftBit \in 1..width :
    column - leftBit + 1 \in 1..width /\
    left[leftBit] /\ right[column - leftBit + 1]}

RECURSIVE ProductCarry(_, _, _, _)
\* @type: ($integerWord, $integerWord, Int, Int) => Int;
ProductCarry(left, right, width, column) ==
  IF column = 1 THEN 0
  ELSE (ProductCarry(left, right, width, column - 1) +
        Cardinality(ProductTerms(left, right, width, column - 1))) \div 2

\* @type: ($integerWord, $integerWord, Int) => $integerDoubleWord;
UnsignedProduct(left, right, width) ==
  [bit \in 1..128 |->
    IF bit <= 2 * width
    THEN (ProductCarry(left, right, width, bit) +
          Cardinality(ProductTerms(left, right, width, bit))) % 2 = 1
    ELSE FALSE]

\* @type: ($integerDoubleWord, Int) => $integerDoubleWord;
WideNot(word, width) ==
  [bit \in 1..128 |-> IF bit <= 2 * width THEN ~word[bit] ELSE FALSE]

RECURSIVE WideCarryInto(_, _, _, _)
\* @type: ($integerDoubleWord, $integerDoubleWord, Bool, Int) => Bool;
WideCarryInto(left, right, carry, position) ==
  IF position = 1 THEN carry
  ELSE (left[position - 1] /\ right[position - 1]) \/
       ((left[position - 1] \/ right[position - 1]) /\
        WideCarryInto(left, right, carry, position - 1))

\* @type: ($integerDoubleWord, $integerDoubleWord, Bool, Int)
\*   => $integerDoubleWord;
WideAdd(left, right, carry, width) ==
  [bit \in 1..128 |->
    IF bit <= 2 * width
    THEN (left[bit] # right[bit]) # WideCarryInto(left, right, carry, bit)
    ELSE FALSE]

\* @type: ($integerDoubleWord, Int) => $integerDoubleWord;
WideNegate(word, width) == WideAdd(WideNot(word, width), DoubleZero, TRUE, width)

\* @type: ($integerWord, Int) => $integerDoubleWord;
SignExtendedWide(word, width) ==
  [bit \in 1..128 |->
    IF bit <= width THEN word[bit]
    ELSE IF bit <= 2 * width THEN word[width] ELSE FALSE]

\* @type: ($integerWord, Int) => $integerWord;
SignedMagnitude(word, width) ==
  IF word[width] THEN LowHalf(WideNegate(SignExtendedWide(word, width), width), width)
  ELSE Truncate(word, width)

\* @type: ($integerWord, $integerWord, Int) => $integerDoubleWord;
SignedProduct(left, right, width) ==
  LET magnitude == UnsignedProduct(SignedMagnitude(left, width),
                                   SignedMagnitude(right, width), width)
  IN IF left[width] # right[width] THEN WideNegate(magnitude, width) ELSE magnitude

\* @type: ($integerDoubleWord, Int, Bool) => $integerFlagDomains;
MulFlagDomains(product, width, signed) ==
  LET low == LowHalf(product, width)
      high == HighHalf(product, width)
      overflow == IF signed
                  THEN ~ActiveEqual(high,
                         [bit \in 1..64 |-> IF bit <= width THEN low[width] ELSE FALSE],
                         width)
                  ELSE ~IsZero(high, width)
  IN [flag \in Flags |->
       IF flag \in {"cf", "of"} THEN {overflow} ELSE BOOLEAN]

\* @type: ($integerWord, $integerWord, Int, Bool, $integerWord,
\*   $integerWord, $integerFlags) => Bool;
MulResultAllowed(left, right, width, signed, low, high, flags) ==
  LET product == IF signed THEN SignedProduct(left, right, width)
                 ELSE UnsignedProduct(left, right, width)
  IN /\ low = LowHalf(product, width)
     /\ high = HighHalf(product, width)
     /\ FlagsAllowed(flags, MulFlagDomains(product, width, signed))

\* Exact unsigned division is a relation between candidate quotient/remainder
\* and the 2*width dividend.  This avoids enumerating or converting 128-bit
\* arithmetic.  The unique successful pair is characterized by q*d+r=n and
\* r<d.  A divide-error outcome has no architectural quotient/remainder write.
\* @type: ($integerDoubleWord, $integerWord, Int, $integerWord,
\*   $integerWord) => Bool;
UnsignedDivisionOK(dividend, divisor, width, quotient, remainder) ==
  LET product == UnsignedProduct(quotient, divisor, width)
      remainderWide == WideFromHalves(remainder, ZeroWord, width)
  IN /\ ~IsZero(divisor, width)
     /\ WordWellFormed(quotient) /\ WordWellFormed(remainder)
     /\ \A bit \in (width + 1)..64 : ~quotient[bit] /\ ~remainder[bit]
     /\ WideAdd(product, remainderWide, FALSE, width) = dividend
     /\ UnsignedLess(remainder, divisor, width)

\* @type: ($integerDoubleWord, $integerWord, Int,
\*   {kind: Str, quotient: $integerWord, remainder: $integerWord}) => Bool;
UnsignedDivisionOutcome(dividend, divisor, width, outcome) ==
  \/ /\ outcome.kind = "ok"
     /\ UnsignedDivisionOK(dividend, divisor, width,
                           outcome.quotient, outcome.remainder)
  \/ /\ outcome.kind = "divideError"
     /\ (IsZero(divisor, width) \/
         ~UnsignedLess(HighHalf(dividend, width), divisor, width))

\* Signed division is characterized through magnitudes. Quotient sign is the
\* xor of operand signs; remainder sign follows the dividend. This also makes
\* the most-negative / -1 overflow a divide error because no width-bit signed
\* quotient candidate satisfies the relation.
\* @type: ($integerWord, $integerWord, Int, Bool) => Bool;
SignedValueMatchesMagnitude(value, magnitude, width, negative) ==
  /\ SignedMagnitude(value, width) = magnitude
  /\ IF IsZero(magnitude, width) THEN IsZero(value, width)
     ELSE value[width] = negative

\* @type: ($integerDoubleWord, Int) => Bool;
WideIsZero(word, width) == \A bit \in 1..(2 * width) : ~word[bit]

\* @type: ($integerDoubleWord, $integerDoubleWord, Int) => Bool;
WideUnsignedLess(left, right, width) ==
  \E pivot \in 1..(2 * width) :
    /\ ~left[pivot] /\ right[pivot]
    /\ \A bit \in (pivot + 1)..(2 * width) : left[bit] = right[bit]

\* @type: ($integerDoubleWord, Int) => $integerDoubleWord;
SignedWideMagnitude(word, width) ==
  IF word[2 * width] THEN WideNegate(word, width) ELSE word

\* The word encodes one past the largest allowed quotient magnitude. Positive
\* quotients overflow at 2^(w-1); negative quotients overflow at 2^(w-1)+1.
\* @type: (Int, Bool) => $integerWord;
SignedQuotientThreshold(width, negative) ==
  [bit \in 1..64 |-> bit = width \/ (negative /\ bit = 1)]

\* @type: ($integerDoubleWord, $integerWord, Int) => Bool;
SignedDivisionOverflow(dividend, divisor, width) ==
  LET dividendNegative == dividend[2 * width]
      divisorNegative == divisor[width]
      quotientNegative == dividendNegative # divisorNegative
      magnitude == SignedWideMagnitude(dividend, width)
      divisorMagnitude == SignedMagnitude(divisor, width)
      threshold == UnsignedProduct(divisorMagnitude,
                     SignedQuotientThreshold(width, quotientNegative), width)
  IN ~WideUnsignedLess(magnitude, threshold, width)

\* @type: ($integerDoubleWord, $integerWord, Int, $integerWord,
\*   $integerWord) => Bool;
SignedDivisionOK(dividend, divisor, width, quotient, remainder) ==
  LET divisorMagnitude == SignedMagnitude(divisor, width)
      quotientMagnitude == SignedMagnitude(quotient, width)
      remainderMagnitude == SignedMagnitude(remainder, width)
      dividendNegative == dividend[2 * width]
      unsignedDividend == SignedWideMagnitude(dividend, width)
  IN /\ ~IsZero(divisor, width)
     /\ SignedValueMatchesMagnitude(quotient, quotientMagnitude, width,
                                    dividendNegative # divisor[width])
     /\ SignedValueMatchesMagnitude(remainder, remainderMagnitude, width,
                                    dividendNegative)
     /\ UnsignedDivisionOK(unsignedDividend, divisorMagnitude, width,
                           quotientMagnitude, remainderMagnitude)

\* @type: ($integerDoubleWord, $integerWord, Int,
\*   {kind: Str, quotient: $integerWord, remainder: $integerWord}) => Bool;
SignedDivisionOutcome(dividend, divisor, width, outcome) ==
  \/ /\ outcome.kind = "ok"
     /\ SignedDivisionOK(dividend, divisor, width,
                         outcome.quotient, outcome.remainder)
  \/ /\ outcome.kind = "divideError"
     /\ (IsZero(divisor, width) \/
         SignedDivisionOverflow(dividend, divisor, width))

DivideFlagDomains == UndefinedFlagDomains

=============================================================================
