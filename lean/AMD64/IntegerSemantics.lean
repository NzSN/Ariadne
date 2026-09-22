import AMD64.RegisterViews

/-!
Pure value and flag kernels for AMD64 general-purpose integer instructions.

Authority: AMD APM Volume 1 revision 3.25, sections 3.1.4 and 3.2, and
Volume 3 revision 3.38, chapter 3. Operand decoding, register/memory writes,
mode and feature legality, exceptions, and atomicity are separate layers.

The `Source` namespace is a reviewed transcription of the corresponding TLA+
operators. The correspondence theorems relate that transcription to the typed
Lean functions. They do not prove that a TLA+ parser produced this Lean text;
review plus source hashes is the explicit trust boundary.
-/

namespace AMD64.IntegerSemantics

abbrev IWord := AMD64.Word

def validWidth (width : Nat) : Prop := width = 8 ∨ width = 16 ∨ width = 32 ∨ width = 64

def zero : IWord := fun _ => false
def one : IWord := fun bit => bit.val = 0

def getBit (word : IWord) (bit : Nat) : Bool :=
  if h : bit < 64 then word ⟨bit, h⟩ else false

def truncate (word : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then word bit else false

def zeroExtend (word : IWord) (sourceWidth targetWidth : Nat) : IWord := fun bit =>
  if bit.val < sourceWidth ∧ bit.val < targetWidth then word bit else false

def signExtend (word : IWord) (sourceWidth targetWidth : Nat) : IWord := fun bit =>
  if hs : bit.val < sourceWidth then word bit
  else if bit.val < targetWidth then word ⟨sourceWidth - 1, by omega⟩ else false

def notWord (word : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then !(word bit) else false

inductive LogicOp where | and | or | xor | andn
  deriving DecidableEq, Repr

def logicWord (op : LogicOp) (left right : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then
    match op with
    | .and => left bit && right bit
    | .or => left bit || right bit
    | .xor => Bool.xor (left bit) (right bit)
    | .andn => !(left bit) && right bit
  else false

def isZero (word : IWord) (width : Nat) : Bool :=
  !(List.range width).any (getBit word)

def parityEven (word : IWord) : Bool :=
  (List.range 8).countP (getBit word) % 2 = 0

def carryInto (left right : IWord) (carry : Bool) : Nat → Bool
  | 0 => carry
  | n + 1 =>
      (getBit left n && getBit right n) ||
        ((getBit left n || getBit right n) && carryInto left right carry n)

def addWord (left right : IWord) (carry : Bool) (width : Nat) : IWord := fun bit =>
  if bit.val < width then
    Bool.xor (Bool.xor (left bit) (right bit)) (carryInto left right carry bit.val)
  else false

def subWord (left right : IWord) (borrow : Bool) (width : Nat) : IWord :=
  addWord left (notWord right width) (!borrow) width

structure ArithmeticFlags where
  cf : Bool
  pf : Bool
  af : Bool
  zf : Bool
  sf : Bool
  of : Bool
  deriving DecidableEq, Repr

structure ArithmeticResult where
  value : IWord
  flags : ArithmeticFlags

def clearCarry (flags : ArithmeticFlags) : ArithmeticFlags := { flags with cf := false }
def setCarry (flags : ArithmeticFlags) : ArithmeticFlags := { flags with cf := true }
def complementCarry (flags : ArithmeticFlags) : ArithmeticFlags := { flags with cf := !flags.cf }

def lahfValue (flags : ArithmeticFlags) : IWord := fun bit =>
  match bit.val with
  | 0 => flags.cf
  | 1 => true
  | 2 => flags.pf
  | 4 => flags.af
  | 6 => flags.zf
  | 7 => flags.sf
  | _ => false

def sahfFlags (old : ArithmeticFlags) (value : IWord) : ArithmeticFlags :=
  { old with cf := getBit value 0, pf := getBit value 2, af := getBit value 4
             zf := getBit value 6, sf := getBit value 7 }

inductive Condition where
  | o | no | b | ae | e | ne | be | a | s | ns | p | np | l | ge | le | g
  deriving DecidableEq, Repr

def conditionHolds (condition : Condition) (flags : ArithmeticFlags) : Bool :=
  match condition with
  | .o => flags.of
  | .no => !flags.of
  | .b => flags.cf
  | .ae => !flags.cf
  | .e => flags.zf
  | .ne => !flags.zf
  | .be => flags.cf || flags.zf
  | .a => !flags.cf && !flags.zf
  | .s => flags.sf
  | .ns => !flags.sf
  | .p => flags.pf
  | .np => !flags.pf
  | .l => Bool.xor flags.sf flags.of
  | .ge => flags.sf == flags.of
  | .le => flags.zf || Bool.xor flags.sf flags.of
  | .g => !flags.zf && flags.sf == flags.of

def setConditionValue (condition : Bool) : IWord := fun bit => bit.val = 0 && condition

def resultFlags (result : IWord) (width : Nat) (cf af of : Bool) : ArithmeticFlags :=
  { cf := cf
    pf := parityEven result
    af := af
    zf := isZero result width
    sf := getBit result (width - 1)
    of := of }

def addResult (left right : IWord) (carry : Bool) (width : Nat) : ArithmeticResult :=
  let value := addWord left right carry width
  let cf := carryInto left right carry width
  let af := carryInto left right carry 4
  let sign (word : IWord) := getBit word (width - 1)
  let of := (sign left == sign right) && Bool.xor (sign value) (sign left)
  { value, flags := resultFlags value width cf af of }

def subResult (left right : IWord) (borrow : Bool) (width : Nat) : ArithmeticResult :=
  let value := subWord left right borrow width
  let cf := !(carryInto left (notWord right width) (!borrow) width)
  let af := !(carryInto left (notWord right width) (!borrow) 4)
  let sign (word : IWord) := getBit word (width - 1)
  let of := Bool.xor (sign left) (sign right) && Bool.xor (sign value) (sign left)
  { value, flags := resultFlags value width cf af of }

def incResult (value : IWord) (width : Nat) (oldCF : Bool) : ArithmeticResult :=
  let result := addResult value one false width
  { result with flags.cf := oldCF }

def decResult (value : IWord) (width : Nat) (oldCF : Bool) : ArithmeticResult :=
  let result := subResult value one false width
  { result with flags.cf := oldCF }

def negResult (value : IWord) (width : Nat) : ArithmeticResult :=
  subResult zero value false width

inductive ADXChain where | carry | overflow
  deriving DecidableEq, Repr

def adxResult (chain : ADXChain) (left right : IWord) (old : ArithmeticFlags)
    (width : Nat) : ArithmeticResult :=
  let carryIn := match chain with | .carry => old.cf | .overflow => old.of
  let value := addWord left right carryIn width
  let carryOut := carryInto left right carryIn width
  let flags := match chain with
    | .carry => { old with cf := carryOut }
    | .overflow => { old with of := carryOut }
  { value, flags }

theorem adcx_preserves_overflow (left right : IWord) (old : ArithmeticFlags)
    (width : Nat) : (adxResult .carry left right old width).flags.of = old.of := by
  rfl

theorem adox_preserves_carry (left right : IWord) (old : ArithmeticFlags)
    (width : Nat) : (adxResult .overflow left right old width).flags.cf = old.cf := by
  rfl

theorem adx_value (chain : ADXChain) (left right : IWord) (old : ArithmeticFlags)
    (width : Nat) :
    (adxResult chain left right old width).value =
      addWord left right (match chain with | .carry => old.cf | .overflow => old.of) width := by
  cases chain <;> rfl

inductive FlagChoice where
  | preserve
  | exact (value : Bool)
  | undefined
  deriving DecidableEq, Repr

def FlagChoice.permits (choice : FlagChoice) (old candidate : Bool) : Prop :=
  match choice with
  | .preserve => candidate = old
  | .exact value => candidate = value
  | .undefined => True

structure FlagEffects where
  cf : FlagChoice
  pf : FlagChoice
  af : FlagChoice
  zf : FlagChoice
  sf : FlagChoice
  of : FlagChoice
  deriving DecidableEq, Repr

def logicEffects (op : LogicOp) (value : IWord) (width : Nat) : FlagEffects :=
  { cf := .exact false
    pf := if op = .andn then .undefined else .exact (parityEven value)
    af := .undefined
    zf := .exact (isZero value width)
    sf := .exact (getBit value (width - 1))
    of := .exact false }

inductive DerivedBitOp where
  | blcfill | blci | blcic | blcmsk | blcs | blsfill
  | blsi | blsic | blsmsk | blsr | t1mskc | tzmsk
  deriving DecidableEq, Repr

def derivedBitValue (op : DerivedBitOp) (source : IWord) (width : Nat) : IWord :=
  let incremented := addWord source one false width
  let decremented := subWord source one false width
  let negated := subWord zero source false width
  match op with
  | .blcfill => logicWord .and source incremented width
  | .blci => logicWord .or source (notWord incremented width) width
  | .blcic => logicWord .and (notWord source width) incremented width
  | .blcmsk => logicWord .xor source incremented width
  | .blcs => logicWord .or source incremented width
  | .blsfill => logicWord .or source decremented width
  | .blsi => logicWord .and negated source width
  | .blsic => logicWord .or (notWord source width) decremented width
  | .blsmsk => logicWord .xor source decremented width
  | .blsr => logicWord .and source decremented width
  | .t1mskc => logicWord .or (notWord source width) incremented width
  | .tzmsk => logicWord .and (notWord source width) decremented width

def derivedBitEffects (op : DerivedBitOp) (source : IWord) (width : Nat) : FlagEffects :=
  let value := derivedBitValue op source width
  let cf := match op with
    | .blcfill | .blci | .blcic | .blcmsk | .blcs | .t1mskc =>
        carryInto source one false width
    | .blsi => !(carryInto zero (notWord source width) true width)
    | _ => !(carryInto source (notWord one width) true width)
  { (logicEffects .and value width) with cf := .exact cf }

def byteSwap (word : IWord) (width : Nat) : IWord := fun bit =>
  if _h : bit.val < width then
    let byte := bit.val / 8
    let within := bit.val % 8
    getBit word (width - 8 * byte - 8 + within)
  else false

inductive BitAction where | complement | reset | set
  deriving DecidableEq, Repr

def bitModify (word : IWord) (width index : Nat) (action : BitAction) : IWord := fun bit =>
  if bit.val ≥ width then false
  else if bit.val = index % width then
    match action with
    | .complement => !(word bit)
    | .reset => false
    | .set => true
  else word bit

def bitTest (word : IWord) (width index : Nat) : Bool :=
  if 0 < width then getBit word (index % width) else false

def wordOfNat (value : Nat) : IWord := fun bit => value.testBit bit.val

def unsignedValue (word : IWord) (width : Nat) : Nat :=
  (List.range width).foldl
    (fun total bit => if getBit word bit then total + 2 ^ bit else total) 0

def leastSetIndex (word : IWord) (width : Nat) : Nat :=
  (List.range width).findIdx (getBit word)

def greatestSetIndex (word : IWord) (width : Nat) : Nat :=
  let reversed := (List.range width).reverse
  match reversed.find? (getBit word) with
  | some bit => bit
  | none => 0

/-- BSF/BSR value relation. A zero source preserves the supplied destination
word exactly. The CPU binding must implement that case as no destination write,
so a 32-bit form does not accidentally zero the canonical register's high half. -/
def bitScanAllowed (reverse : Bool) (source oldDestination : IWord)
    (width : Nat) (candidate : IWord) : Prop :=
  if isZero source width then candidate = oldDestination
  else candidate = wordOfNat (if reverse then greatestSetIndex source width else leastSetIndex source width)

def bitScanEffects (zeroSource : Bool) : FlagEffects :=
  { cf := .undefined, pf := .undefined, af := .undefined
    zf := .exact zeroSource, sf := .undefined, of := .undefined }

def bitTestEffects (selected : Bool) : FlagEffects :=
  { cf := .exact selected, pf := .undefined, af := .undefined
    zf := .undefined, sf := .undefined, of := .undefined }

def popCount (word : IWord) (width : Nat) : IWord :=
  wordOfNat ((List.range width).countP (getBit word))

def trailingZeroCount (word : IWord) (width : Nat) : IWord :=
  if isZero word width then wordOfNat width else wordOfNat (leastSetIndex word width)

def leadingZeroCount (word : IWord) (width : Nat) : IWord :=
  if isZero word width then wordOfNat width else wordOfNat (width - 1 - greatestSetIndex word width)

def bextrEffects (result : IWord) (width : Nat) : FlagEffects :=
  { cf := .exact false, pf := .undefined, af := .undefined
    zf := .exact (isZero result width), sf := .undefined, of := .exact false }

def bzhiEffects (result : IWord) (width index : Nat) : FlagEffects :=
  { cf := .exact (decide (index ≥ width)), pf := .undefined, af := .undefined
    zf := .exact (isZero result width), sf := .exact (getBit result (width - 1))
    of := .exact false }

inductive CountKind where | lzcnt | tzcnt | popcnt
  deriving DecidableEq, Repr

def countEffects (kind : CountKind) (source result : IWord) (width : Nat) : FlagEffects :=
  match kind with
  | .popcnt =>
      { cf := .exact false, pf := .exact false, af := .exact false
        zf := .exact (isZero source width), sf := .exact false, of := .exact false }
  | .lzcnt | .tzcnt =>
      { cf := .exact (isZero source width), pf := .undefined, af := .undefined
        zf := .exact (isZero result width), sf := .undefined, of := .undefined }

def extractBits (source : IWord) (width start length : Nat) : IWord := fun bit =>
  if h : bit.val < length ∧ start + bit.val < width ∧ start + bit.val < 64 then
    source ⟨start + bit.val, h.2.2⟩
  else false

def zeroHighBits (source : IWord) (width index : Nat) : IWord := fun bit =>
  if bit.val < width ∧ bit.val < index then source bit else false

def maskRank (mask : IWord) (position : Nat) : Nat :=
  (List.range position).countP (getBit mask)

def parallelDeposit (source mask : IWord) (width : Nat) : IWord := fun bit =>
  if _h : bit.val < width ∧ mask bit then
    getBit source (maskRank mask bit.val)
  else false

def parallelExtract (source mask : IWord) (width : Nat) : IWord :=
  wordOfNat ((List.range width).foldl (fun out bit =>
    if getBit mask bit then
      if getBit source bit then out + 2 ^ maskRank mask bit else out
    else out) 0)

inductive ShiftKind where | shl | shr | sar
  deriving DecidableEq, Repr

def maskedCount (count width : Nat) : Nat := count % (if width = 64 then 64 else 32)

def shiftValue (kind : ShiftKind) (value : IWord) (width count : Nat) : IWord := fun bit =>
  if bit.val ≥ width then false else
  match kind with
  | .shl => if count ≤ bit.val then getBit value (bit.val - count) else false
  | .shr => if bit.val + count < width then getBit value (bit.val + count) else false
  | .sar => if bit.val + count < width then getBit value (bit.val + count)
            else getBit value (width - 1)

def shiftEffects (kind : ShiftKind) (before result : IWord) (width rawCount : Nat) : FlagEffects :=
  let count := maskedCount rawCount width
  if count = 0 then
    { cf := .preserve, pf := .preserve, af := .preserve
      zf := .preserve, sf := .preserve, of := .preserve }
  else
    let cf := if count ≤ width then
        match kind with
        | .shl => getBit before (width - count)
        | .shr | .sar => getBit before (count - 1)
      else match kind with | .sar => getBit before (width - 1) | _ => false
    let overflow := if count = 1 then .exact <| match kind with
      | .shl => Bool.xor (getBit result (width - 1)) (getBit before (width - 1))
      | .shr => getBit before (width - 1)
      | .sar => false
      else .undefined
    { cf := .exact cf, pf := .exact (parityEven result), af := .undefined
      zf := .exact (isZero result width), sf := .exact (getBit result (width - 1))
      of := overflow }

inductive RotateKind where | rol | ror
  deriving DecidableEq, Repr

def rotateValue (kind : RotateKind) (value : IWord) (width count : Nat) : IWord := fun bit =>
  if _hw : 0 < width ∧ width ≤ 64 ∧ bit.val < width then
    let source := match kind with
      | .rol => (bit.val + width - count % width) % width
      | .ror => (bit.val + count % width) % width
    getBit value source
  else false

def rotateEffects (kind : RotateKind) (result : IWord) (width rawCount : Nat) : FlagEffects :=
  let masked := maskedCount rawCount width
  if masked = 0 then
    { cf := .preserve, pf := .preserve, af := .preserve
      zf := .preserve, sf := .preserve, of := .preserve }
  else
    let cf := match kind with | .rol => getBit result 0 | .ror => getBit result (width - 1)
    let overflow := if masked = 1 then .exact <| match kind with
      | .rol => Bool.xor (getBit result (width - 1)) cf
      | .ror => Bool.xor (getBit result (width - 1)) (getBit result (width - 2))
      else .undefined
    { cf := .exact cf, pf := .preserve, af := .preserve
      zf := .preserve, sf := .preserve, of := overflow }

inductive CarryRotateKind where | rcl | rcr
  deriving DecidableEq, Repr

def ringBit (value : IWord) (carry : Bool) (width position : Nat) : Bool :=
  if position = width then carry else getBit value position

def carryRotateValue (kind : CarryRotateKind) (value : IWord) (carry : Bool)
    (width count : Nat) : IWord := fun bit =>
  if _hw : 0 < width ∧ width ≤ 64 ∧ bit.val < width then
    let ringWidth := width + 1
    let source := match kind with
      | .rcl => (bit.val + ringWidth - count % ringWidth) % ringWidth
      | .rcr => (bit.val + count % ringWidth) % ringWidth
    ringBit value carry width source
  else false

def carryRotateCF (kind : CarryRotateKind) (value : IWord) (carry : Bool)
    (width count : Nat) : Bool :=
  let ringWidth := width + 1
  let source := match kind with
    | .rcl => (width + ringWidth - count % ringWidth) % ringWidth
    | .rcr => (width + count % ringWidth) % ringWidth
  ringBit value carry width source

def carryRotateEffects (kind : CarryRotateKind) (result : IWord) (newCF : Bool)
    (width rawCount : Nat) : FlagEffects :=
  let masked := maskedCount rawCount width
  if masked = 0 then
    { cf := .preserve, pf := .preserve, af := .preserve
      zf := .preserve, sf := .preserve, of := .preserve }
  else
    let overflow := if masked = 1 then .exact <| match kind with
      | .rcl => Bool.xor (getBit result (width - 1)) newCF
      | .rcr => Bool.xor (getBit result (width - 1)) (getBit result (width - 2))
      else .undefined
    { cf := .exact newCF, pf := .preserve, af := .preserve
      zf := .preserve, sf := .preserve, of := overflow }

inductive DoubleShiftKind where | shld | shrd
  deriving DecidableEq, Repr

def doubleShiftExact (kind : DoubleShiftKind) (destination source : IWord)
    (width count : Nat) : IWord := fun bit =>
  if bit.val ≥ width then false else
  match kind with
  | .shld => if count ≤ bit.val then getBit destination (bit.val - count)
             else getBit source (width - count + bit.val)
  | .shrd => if bit.val + count < width then getBit destination (bit.val + count)
             else getBit source (bit.val + count - width)

def doubleShiftAllowed (kind : DoubleShiftKind) (destination source : IWord)
    (width rawCount : Nat) (candidate : IWord) : Prop :=
  let count := maskedCount rawCount width
  if count ≤ width then candidate = doubleShiftExact kind destination source width count
  else ∀ bit : Fin 64, width ≤ bit.val → candidate bit = false

structure MulResult where
  low : IWord
  high : IWord
  overflow : Bool

def unsignedMul (left right : IWord) (width : Nat) : MulResult :=
  let product := unsignedValue left width * unsignedValue right width
  let modulus := 2 ^ width
  let low := wordOfNat (product % modulus)
  let high := wordOfNat ((product / modulus) % modulus)
  { low, high, overflow := decide (product ≥ modulus) }

def signedValue (word : IWord) (width : Nat) : Int :=
  let unsigned := unsignedValue word width
  if 0 < width ∧ width ≤ 64 ∧ getBit word (width - 1)
  then Int.ofNat unsigned - Int.ofNat (2 ^ width)
  else Int.ofNat unsigned

def signedMul (left right : IWord) (width : Nat) : MulResult :=
  let product := signedValue left width * signedValue right width
  let modulus : Int := Int.ofNat (2 ^ width)
  let encoded := product.emod (modulus * modulus)
  let lowNat := (encoded.emod modulus).toNat
  let highNat := (encoded.ediv modulus).toNat
  let min : Int := -(Int.ofNat (2 ^ (width - 1)))
  let max : Int := Int.ofNat (2 ^ (width - 1)) - 1
  { low := wordOfNat lowNat, high := wordOfNat highNat
    overflow := decide (product < min ∨ product > max) }

inductive DivideResult where
  | divideError
  | ok (quotient remainder : IWord)

def unsignedDivide (high low divisor : IWord) (width : Nat) : DivideResult :=
  let dividend := unsignedValue high width * 2 ^ width + unsignedValue low width
  let d := unsignedValue divisor width
  if d = 0 then .divideError
  else let quotient := dividend / d
       if quotient ≥ 2 ^ width then .divideError
       else .ok (wordOfNat quotient) (wordOfNat (dividend % d))

def signedDivide (high low divisor : IWord) (width : Nat) : DivideResult :=
  let unsignedDividend := unsignedValue high width * 2 ^ width + unsignedValue low width
  let signedDividend := if 0 < width ∧ width ≤ 64 ∧ getBit high (width - 1)
    then Int.ofNat unsignedDividend - Int.ofNat (2 ^ (2 * width))
    else Int.ofNat unsignedDividend
  let d := signedValue divisor width
  if d = 0 then .divideError
  else let quotient := signedDividend.tdiv d
       let remainder := signedDividend.tmod d
       let min : Int := -(Int.ofNat (2 ^ (width - 1)))
       let max : Int := Int.ofNat (2 ^ (width - 1)) - 1
       if quotient < min ∨ quotient > max then .divideError
       else .ok (wordOfNat (quotient.emod (Int.ofNat (2 ^ width))).toNat)
                (wordOfNat (remainder.emod (Int.ofNat (2 ^ width))).toNat)

theorem truncate_inside (word : IWord) (width : Nat) (bit : Fin 64)
    (inside : bit.val < width) : truncate word width bit = word bit := by
  simp [truncate, inside]

theorem truncate_outside (word : IWord) (width : Nat) (bit : Fin 64)
    (outside : width ≤ bit.val) : truncate word width bit = false := by
  simp [truncate, show ¬ bit.val < width by omega]

theorem zeroExtend_source (word : IWord) (sourceWidth targetWidth : Nat) (bit : Fin 64)
    (source : bit.val < sourceWidth) (target : bit.val < targetWidth) :
    zeroExtend word sourceWidth targetWidth bit = word bit := by
  simp [zeroExtend, source, target]

theorem bitModify_selected (word : IWord) (width index : Nat) (action : BitAction)
    (bit : Fin 64) (inside : bit.val < width) (selected : bit.val = index % width) :
    bitModify word width index action bit =
      match action with | .complement => !(word bit)
                        | .reset => false | .set => true := by
  unfold bitModify
  rw [if_neg (by omega), if_pos selected]

theorem unsignedDivide_by_zero (high low divisor : IWord) (width : Nat)
    (zeroDivisor : unsignedValue divisor width = 0) :
    unsignedDivide high low divisor width = .divideError := by
  simp [unsignedDivide, zeroDivisor]

namespace Source

/- Reviewed zero-based transcription of the TLA+ operators. This namespace is
   the explicit source-transcription trust boundary described at file top. -/
def truncate (word : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then word bit else false

def zeroExtend (word : IWord) (sourceWidth targetWidth : Nat) : IWord := fun bit =>
  if bit.val < sourceWidth ∧ bit.val < targetWidth then word bit else false

def signExtend (word : IWord) (sourceWidth targetWidth : Nat) : IWord := fun bit =>
  if hs : bit.val < sourceWidth then word bit
  else if bit.val < targetWidth then word ⟨sourceWidth - 1, by omega⟩ else false

def notWord (word : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then !(word bit) else false

def logicWord (op : LogicOp) (left right : IWord) (width : Nat) : IWord := fun bit =>
  if bit.val < width then
    match op with
    | .and => left bit && right bit
    | .or => left bit || right bit
    | .xor => Bool.xor (left bit) (right bit)
    | .andn => !(left bit) && right bit
  else false

def addWord (left right : IWord) (carry : Bool) (width : Nat) : IWord := fun bit =>
  if bit.val < width then
    Bool.xor (Bool.xor (left bit) (right bit))
      (IntegerSemantics.carryInto left right carry bit.val)
  else false

def bitModify (word : IWord) (width index : Nat) (action : BitAction) : IWord := fun bit =>
  if bit.val ≥ width then false
  else if bit.val = index % width then
    match action with
    | .complement => !(word bit)
    | .reset => false
    | .set => true
  else word bit

def maskedCount (count width : Nat) : Nat := count % (if width = 64 then 64 else 32)

def shiftValue (kind : ShiftKind) (value : IWord) (width count : Nat) : IWord := fun bit =>
  if bit.val ≥ width then false else
  match kind with
  | .shl => if count ≤ bit.val then getBit value (bit.val - count) else false
  | .shr => if bit.val + count < width then getBit value (bit.val + count) else false
  | .sar => if bit.val + count < width then getBit value (bit.val + count)
            else getBit value (width - 1)

def rotateValue (kind : RotateKind) (value : IWord) (width count : Nat) : IWord := fun bit =>
  if _hw : 0 < width ∧ width ≤ 64 ∧ bit.val < width then
    let source := match kind with
      | .rol => (bit.val + width - count % width) % width
      | .ror => (bit.val + count % width) % width
    getBit value source
  else false

def adxResult (chain : ADXChain) (left right : IWord) (old : ArithmeticFlags)
    (width : Nat) : ArithmeticResult :=
  let carryIn := match chain with | .carry => old.cf | .overflow => old.of
  let value := addWord left right carryIn width
  let carryOut := IntegerSemantics.carryInto left right carryIn width
  let flags := match chain with
    | .carry => { old with cf := carryOut }
    | .overflow => { old with of := carryOut }
  { value, flags }

def bitScanEffects (zeroSource : Bool) : FlagEffects :=
  { cf := .undefined, pf := .undefined, af := .undefined
    zf := .exact zeroSource, sf := .undefined, of := .undefined }

def bitTestEffects (selected : Bool) : FlagEffects :=
  { cf := .exact selected, pf := .undefined, af := .undefined
    zf := .undefined, sf := .undefined, of := .undefined }

def bextrEffects (result : IWord) (width : Nat) : FlagEffects :=
  { cf := .exact false, pf := .undefined, af := .undefined
    zf := .exact (IntegerSemantics.isZero result width), sf := .undefined
    of := .exact false }

def bzhiEffects (result : IWord) (width index : Nat) : FlagEffects :=
  { cf := .exact (decide (index ≥ width)), pf := .undefined, af := .undefined
    zf := .exact (IntegerSemantics.isZero result width)
    sf := .exact (IntegerSemantics.getBit result (width - 1)), of := .exact false }

def countEffects (kind : CountKind) (source result : IWord) (width : Nat) : FlagEffects :=
  match kind with
  | .popcnt =>
      { cf := .exact false, pf := .exact false, af := .exact false
        zf := .exact (IntegerSemantics.isZero source width), sf := .exact false
        of := .exact false }
  | .lzcnt | .tzcnt =>
      { cf := .exact (IntegerSemantics.isZero source width), pf := .undefined
        af := .undefined, zf := .exact (IntegerSemantics.isZero result width)
        sf := .undefined, of := .undefined }

theorem truncate_correspondence (word : IWord) (width : Nat) :
    IntegerSemantics.truncate word width = truncate word width := rfl

theorem addWord_correspondence (left right : IWord) (carry : Bool) (width : Nat) :
    IntegerSemantics.addWord left right carry width = addWord left right carry width := rfl

theorem zeroExtend_correspondence (word : IWord) (sourceWidth targetWidth : Nat) :
    IntegerSemantics.zeroExtend word sourceWidth targetWidth =
      zeroExtend word sourceWidth targetWidth := rfl

theorem signExtend_correspondence (word : IWord) (sourceWidth targetWidth : Nat) :
    IntegerSemantics.signExtend word sourceWidth targetWidth =
      signExtend word sourceWidth targetWidth := rfl

theorem notWord_correspondence (word : IWord) (width : Nat) :
    IntegerSemantics.notWord word width = notWord word width := rfl

theorem logicWord_correspondence (op : LogicOp) (left right : IWord) (width : Nat) :
    IntegerSemantics.logicWord op left right width = logicWord op left right width := rfl

theorem bitModify_correspondence (word : IWord) (width index : Nat) (action : BitAction) :
    IntegerSemantics.bitModify word width index action = bitModify word width index action := rfl

theorem maskedCount_correspondence (count width : Nat) :
    IntegerSemantics.maskedCount count width = maskedCount count width := rfl

theorem shiftValue_correspondence (kind : ShiftKind) (word : IWord)
    (width count : Nat) :
    IntegerSemantics.shiftValue kind word width count = shiftValue kind word width count := rfl

theorem rotateValue_correspondence (kind : RotateKind) (word : IWord)
    (width count : Nat) :
    IntegerSemantics.rotateValue kind word width count = rotateValue kind word width count := rfl

theorem adxResult_correspondence (chain : ADXChain) (left right : IWord)
    (old : ArithmeticFlags) (width : Nat) :
    IntegerSemantics.adxResult chain left right old width =
      adxResult chain left right old width := rfl

theorem bitScanEffects_correspondence (zeroSource : Bool) :
    IntegerSemantics.bitScanEffects zeroSource = bitScanEffects zeroSource := rfl

theorem bitTestEffects_correspondence (selected : Bool) :
    IntegerSemantics.bitTestEffects selected = bitTestEffects selected := rfl

theorem bextrEffects_correspondence (result : IWord) (width : Nat) :
    IntegerSemantics.bextrEffects result width = bextrEffects result width := rfl

theorem bzhiEffects_correspondence (result : IWord) (width index : Nat) :
    IntegerSemantics.bzhiEffects result width index = bzhiEffects result width index := rfl

theorem countEffects_correspondence (kind : CountKind) (source result : IWord)
    (width : Nat) : IntegerSemantics.countEffects kind source result width =
      countEffects kind source result width := rfl

end Source
end AMD64.IntegerSemantics
