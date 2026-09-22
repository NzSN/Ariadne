import AMD64.IntegerSemantics

/-! Directed executable checks for the pure integer kernels. These are finite
vectors at architectural widths; the general laws live in IntegerSemantics. -/

namespace AMD64.IntegerSemantics.Checks

def falseFlags : ArithmeticFlags :=
  { cf := false
    pf := false
    af := false
    zf := false
    sf := false
    of := false }

def zeroSetFlags : ArithmeticFlags := { falseFlags with zf := true }
def allSetFlags : ArithmeticFlags :=
  { cf := true, pf := true, af := true, zf := true, sf := true, of := true }

example : unsignedValue (wordOfNat 255) 8 = 255 := by decide
example : unsignedValue (addResult (wordOfNat 255) (wordOfNat 1) false 8).value 8 = 0 := by decide
example : (addResult (wordOfNat 255) (wordOfNat 1) false 8).flags.cf = true := by decide
example : unsignedValue (subResult zero (wordOfNat 1) false 8).value 8 = 255 := by decide
example : (negResult (wordOfNat 128) 8).flags.of = true := by decide
example : (incResult (wordOfNat 255) 8 true).flags.cf = true := by decide
example : (logicEffects .andn zero 8).pf = .undefined := by decide
example : (logicEffects .and zero 8).pf = .exact true := by decide
example : unsignedValue (derivedBitValue .blcmsk (wordOfNat 7) 32) 32 = 15 := by decide
example : unsignedValue (derivedBitValue .blsi (wordOfNat 8) 32) 32 = 8 := by decide
example : unsignedValue (derivedBitValue .tzmsk (wordOfNat 8) 32) 32 = 7 := by decide
example : unsignedValue (lahfValue falseFlags) 8 = 2 := by decide
example : conditionHolds .be zeroSetFlags = true := by decide
example : unsignedValue (setConditionValue true) 8 = 1 := by decide
example : (adxResult .carry (wordOfNat 255) zero allSetFlags 8).flags.of = true := by decide
example : (adxResult .overflow (wordOfNat 255) zero allSetFlags 8).flags.cf = true := by decide
example : (bextrEffects zero 32).zf = .exact true := by decide
example : (bzhiEffects zero 32 32).cf = .exact true := by decide
example : (countEffects .lzcnt zero (wordOfNat 32) 32).cf = .exact true := by decide
example : (countEffects .tzcnt (wordOfNat 1) zero 32).zf = .exact true := by decide
example : (countEffects .popcnt zero zero 32).pf = .exact false := by decide

example : maskedCount 32 32 = 0 := by decide
example : maskedCount 64 64 = 0 := by decide
example : unsignedValue (shiftValue .shl (wordOfNat 255) 8 9) 8 = 0 := by decide
example : unsignedValue (shiftValue .sar (wordOfNat 128) 8 9) 8 = 255 := by decide
example : (shiftEffects .sar (wordOfNat 128) (wordOfNat 255) 8 9).cf = .exact true := by decide
example : (rotateEffects .rol (wordOfNat 128) 8 8).of = .undefined := by decide
example : (rotateEffects .rol (wordOfNat 1) 8 9).of = .undefined := by decide
example : carryRotateCF .rcl (wordOfNat 128) true 8 0 = true := by decide
example : (carryRotateEffects .rcl (wordOfNat 128) true 8 9).of = .undefined := by decide

example : bitScanAllowed false zero (wordOfNat 255) 8 (wordOfNat 255) := by
  simp [bitScanAllowed, isZero, zero, getBit]
example : ¬bitScanAllowed false zero (wordOfNat 255) 8 (wordOfNat 0) := by
  simp only [bitScanAllowed, isZero, Bool.false_eq_true, ↓reduceIte]
  intro equal
  have bitZero := congrFun equal ⟨0, by decide⟩
  contradiction
example : bitScanAllowed true zero (fun bit => bit.val = 63) 32
    (fun bit => bit.val = 63) := by simp [bitScanAllowed, isZero, zero, getBit]
example : (bitScanEffects true).zf = .exact true := by rfl
example : (bitScanEffects true).cf = .undefined := by rfl
example : unsignedValue (popCount (wordOfNat 137) 8) 8 = 3 := by decide
example : unsignedValue (trailingZeroCount (wordOfNat 128) 8) 8 = 7 := by decide
example : unsignedValue (leadingZeroCount (wordOfNat 1) 8) 8 = 7 := by decide
example : unsignedValue (parallelDeposit (wordOfNat 3) (wordOfNat 42) 8) 8 = 10 := by decide
example : unsignedValue (parallelExtract (wordOfNat 34) (wordOfNat 42) 8) 8 = 5 := by decide

example : unsignedValue (unsignedMul (wordOfNat 255) (wordOfNat 2) 8).low 8 = 254 := by decide
example : unsignedValue (unsignedMul (wordOfNat 255) (wordOfNat 2) 8).high 8 = 1 := by decide

def divideMatches (result : DivideResult) (width : Nat) (expectError : Bool)
    (expectedQuotient expectedRemainder : Nat) : Bool :=
  match result with
  | .divideError => expectError
  | .ok quotient remainder =>
      !expectError && unsignedValue quotient width == expectedQuotient &&
        unsignedValue remainder width == expectedRemainder

example : divideMatches
    (unsignedDivide (wordOfNat 1) zero (wordOfNat 2) 8) 8 false 128 0 = true := by decide
example : divideMatches
    (unsignedDivide (wordOfNat 1) zero (wordOfNat 1) 8) 8 true 0 0 = true := by decide
example : divideMatches
    (unsignedDivide zero (wordOfNat 42) zero 8) 8 true 0 0 = true := by decide
example : divideMatches
    (signedDivide (wordOfNat 255) (wordOfNat 254) (wordOfNat 2) 8) 8 false 255 0 = true := by decide
example : divideMatches
    (signedDivide (wordOfNat 255) (wordOfNat 128) (wordOfNat 255) 8) 8 true 0 0 = true := by decide

end AMD64.IntegerSemantics.Checks
