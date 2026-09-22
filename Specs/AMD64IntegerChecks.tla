--------------------- MODULE AMD64IntegerChecks ---------------------
EXTENDS AMD64IntegerArithmetic, AMD64IntegerShiftBit, AMD64IntegerMulDiv

\* Directed full-width-container vectors. They target width/count/undefined
\* boundaries from the pinned manual rather than shrinking architectural words.
VARIABLE
  \* @type: Bool;
  ok

Word(bits) == [bit \in 1..64 |-> bit \in bits]
Ones(width) == Word(1..width)
FalseFlags == [flag \in Flags |-> FALSE]
TrueFlags == [flag \in Flags |-> TRUE]

W0 == ZeroWord
W1 == Word({1})
W2 == Word({2})
W3 == Word({1, 2})
W7F == Word(1..7)
W80 == Word({8})
WFE == Word(2..8)
WFF == Word(1..8)
WFD == Word({1} \cup 3..8)

ArithmeticChecks ==
  /\ AddResult(WFF, W1, FALSE, 8).value = W0
  /\ AddResult(WFF, W1, FALSE, 8).flags.cf
  /\ AddResult(WFF, W1, FALSE, 8).flags.zf
  /\ SubResult(W0, W1, FALSE, 8).value = WFF
  /\ SubResult(W0, W1, FALSE, 8).flags.cf
  /\ NegResult(W80, 8).value = W80
  /\ NegResult(W80, 8).flags.of
  /\ IncResult(WFF, 8, TRUE).flags.cf
  /\ ~DecResult(W0, 8, FALSE).flags.cf
  /\ ZeroExtend(WFF, 8, 16) = WFF
  /\ SignExtend(W80, 8, 16) = Word(8..16)
  /\ LogicFlagDomains("andn", W0, 8)["pf"] = BOOLEAN
  /\ LogicFlagDomains("and", W0, 8)["pf"] = {TRUE}
  /\ ByteSwap(Word({1}), 32) = Word({25})
  /\ ByteSwap(ByteSwap(Word({1, 9, 32}), 32), 32) = Word({1, 9, 32})

DerivedBitChecks ==
  /\ DerivedBitValue("blcfill", Word({1, 2, 3}), 32) = W0
  /\ DerivedBitValue("blcic", Word({1, 2, 3}), 32) = Word({4})
  /\ DerivedBitValue("blcmsk", Word({1, 2, 3}), 32) = Word(1..4)
  /\ DerivedBitValue("blcs", Word({1, 2, 3}), 32) = Word(1..4)
  /\ DerivedBitValue("blsfill", Word({4}), 32) = Word(1..4)
  /\ DerivedBitValue("blsi", Word({4}), 32) = Word({4})
  /\ DerivedBitValue("blsmsk", Word({4}), 32) = Word(1..4)
  /\ DerivedBitValue("blsr", Word({4}), 32) = W0
  /\ DerivedBitValue("tzmsk", Word({4}), 32) = Word({1, 2, 3})
  /\ DerivedBitFlagDomains("blsr", W0, 32)["cf"] = {TRUE}

FlagChecks ==
  /\ LahfValue(FalseFlags) = Word({2})
  /\ SahfFlags(FalseFlags, Word({1, 3, 5, 7, 8})) =
       [FalseFlags EXCEPT !["cf"] = TRUE, !["pf"] = TRUE,
                          !["af"] = TRUE, !["zf"] = TRUE, !["sf"] = TRUE]
  /\ SetStatusFlag(FalseFlags, "cf", TRUE)["cf"]
  /\ ~ComplementStatusFlag(TrueFlags, "cf")["cf"]
  /\ ConditionHolds("be", [FalseFlags EXCEPT !["zf"] = TRUE])
  /\ ~ConditionHolds("g", [FalseFlags EXCEPT !["zf"] = TRUE])
  /\ SetConditionValue(TRUE) = W1
  /\ SetConditionValue(FALSE) = W0

AdxChecks ==
  /\ AdxResultAllowed("cf", WFF, W0, TrueFlags, 8, W0, TrueFlags)
  /\ AdxResultAllowed("of", WFF, W0,
         [FalseFlags EXCEPT !["of"] = TRUE], 8, W0,
         [FalseFlags EXCEPT !["of"] = TRUE])

CountFlagChecks ==
  /\ BitScanFlagDomains(TRUE)["zf"] = {TRUE}
  /\ BitScanFlagDomains(TRUE)["cf"] = BOOLEAN
  /\ BitTestFlagDomains(TRUE)["cf"] = {TRUE}
  /\ BextrFlagDomains(W0, 32)["zf"] = {TRUE}
  /\ BextrFlagDomains(W0, 32)["sf"] = BOOLEAN
  /\ BzhiFlagDomains(W0, 32, 32)["cf"] = {TRUE}
  /\ BzhiFlagDomains(W0, 32, 32)["of"] = {FALSE}
  /\ CountFlagDomains("lzcnt", W0, SmallNatWord(32), 32)["cf"] = {TRUE}
  /\ CountFlagDomains("lzcnt", Word({32}), W0, 32)["zf"] = {TRUE}
  /\ CountFlagDomains("tzcnt", W1, W0, 32)["zf"] = {TRUE}
  /\ CountFlagDomains("popcnt", W0, W0, 32) =
       [flag \in Flags |-> IF flag = "zf" THEN {TRUE} ELSE {FALSE}]

ShiftChecks ==
  LET sarNine == ShiftValue("sar", W80, 8, 9)
      rolEight == RotateValue("rol", W80, 8, RotateCount(8, 8))
      rolNine == RotateValue("rol", W80, 8, RotateCount(9, 8))
      rclNine == CarryRotateValue("rcl", W80, TRUE, 8,
                    CarryRotateCount(9, 8))
  IN /\ ShiftValue("shl", WFF, 8, 9) = W0
     /\ ShiftFlagDomains("shl", WFF, W0, 8, 9, TrueFlags)["cf"] = {FALSE}
     /\ sarNine = WFF
     /\ ShiftFlagDomains("sar", W80, sarNine, 8, 9, FalseFlags)["cf"] = {TRUE}
     /\ rolEight = W80
     /\ RotateFlagDomains("rol", rolEight, 8, MaskedCount(8, 8), FalseFlags)["cf"] = {FALSE}
     /\ RotateFlagDomains("rol", rolEight, 8, MaskedCount(8, 8), FalseFlags)["of"] = BOOLEAN
     /\ rolNine = W1
     /\ RotateFlagDomains("rol", rolNine, 8, MaskedCount(9, 8), FalseFlags)["of"] = BOOLEAN
     /\ rclNine = W80
     /\ CarryRotateAllowed("rcl", W80, 9, 8, TrueFlags,
                           W80, [TrueFlags EXCEPT !["of"] = FALSE])
     /\ DoubleShiftAllowed("shld", W80, W1, 9, 8, FalseFlags,
                           W0, FalseFlags)
     /\ DoubleShiftAllowed("shld", W80, W1, 9, 8, FalseFlags,
                           WFF, TrueFlags)

BitModifyChecks ==
  /\ BitTest(W80, 8, 7)
  /\ BitModify(W0, 8, 7, "set") = W80
  /\ BitModify(WFF, 8, 7, "reset") = W7F

BitScanChecks ==
  /\ BitScanAllowed("forward", W0, WFF, 8, WFF, TRUE)
  /\ ~BitScanAllowed("forward", W0, WFF, 8, W0, TRUE)
  /\ BitScanAllowed("forward", Word({4}), WFF, 8, W3, FALSE)
  /\ BitScanAllowed("reverse", Word({2, 8}), W0, 8,
                    Word({1, 2, 3}), FALSE)
  /\ BitScanFlagDomains(TRUE)["zf"] = {TRUE}
  /\ BitScanFlagDomains(TRUE)["cf"] = BOOLEAN

CountChecks ==
  /\ PopCount(Word({1, 4, 8}), 8) = W3
  /\ TrailingZeroCount(W80, 8) = Word({1, 2, 3})
  /\ LeadingZeroCount(W1, 8) = Word({1, 2, 3})

ExtractCheck == ExtractBits(Word({3, 5}), 8, 2, 3) = Word({1, 3})
ZeroHighCheck == ZeroHighBits(WFF, 8, 3) = Word({1, 2, 3})
DepositCheck == ParallelDeposit(W3, Word({2, 4, 6}), 8) = Word({2, 4})
ExtractParallelCheck ==
  ParallelExtract(Word({2, 6}), Word({2, 4, 6}), 8) = Word({1, 3})

FeatureBitChecks == ExtractCheck /\ ZeroHighCheck /\ DepositCheck /\ ExtractParallelCheck

BitChecks == BitModifyChecks /\ BitScanChecks /\ CountChecks /\ FeatureBitChecks

MulDivChecks ==
  LET unsignedProduct == UnsignedProduct(WFF, W2, 8)
      signedProduct == SignedProduct(WFF, W2, 8)
      dividend256 == WideFromHalves(W0, W1, 8)
      zeroDivisorOutcome == [kind |-> "divideError", quotient |-> W0, remainder |-> W0]
      overflowOutcome == [kind |-> "divideError", quotient |-> W0, remainder |-> W0]
      signedMinusTwo == WideFromHalves(WFE, WFF, 8)
      signedMinusThree == WideFromHalves(WFD, WFF, 8)
      signedMinimum == WideFromHalves(W80, WFF, 8)
      signedSuccess == [kind |-> "ok", quotient |-> WFF, remainder |-> W0]
      signedRemainder == [kind |-> "ok", quotient |-> WFF, remainder |-> WFF]
      signedMinimumOK == [kind |-> "ok", quotient |-> W80, remainder |-> W0]
      signedOverflow == [kind |-> "divideError", quotient |-> W0, remainder |-> W0]
  IN /\ LowHalf(unsignedProduct, 8) = WFE
     /\ HighHalf(unsignedProduct, 8) = W1
     /\ LowHalf(signedProduct, 8) = WFE
     /\ HighHalf(signedProduct, 8) = WFF
     /\ UnsignedDivisionOK(dividend256, W2, 8, W80, W0)
     /\ UnsignedDivisionOutcome(dividend256, W0, 8, zeroDivisorOutcome)
     /\ UnsignedDivisionOutcome(dividend256, W1, 8, overflowOutcome)
     /\ SignedValueMatchesMagnitude(W0, W0, 8, TRUE)
     /\ SignedDivisionOutcome(signedMinusTwo, W2, 8, signedSuccess)
     /\ SignedDivisionOutcome(signedMinusThree, W2, 8, signedRemainder)
     /\ SignedDivisionOutcome(signedMinimum, W1, 8, signedMinimumOK)
     /\ SignedDivisionOutcome(signedMinimum, WFF, 8, signedOverflow)

AllChecks == ArithmeticChecks /\ DerivedBitChecks /\ FlagChecks /\ AdxChecks /\
             CountFlagChecks /\ ShiftChecks /\ BitChecks /\ MulDivChecks

Init == ok = TRUE
Next == UNCHANGED ok
Safety == ok /\ AllChecks

=============================================================================
