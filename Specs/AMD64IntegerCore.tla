----------------------- MODULE AMD64IntegerCore -----------------------
EXTENDS Integers, FiniteSets

\* Pure bit-vector support for the integer instruction kernels.  A word is a
\* 64-bit Boolean map even when an operation has a narrower architectural
\* width.  Bits above that width are zero in value results.  This module never
\* represents a 64-bit value as a TLC host integer.
\*
\* Authority: AMD APM Volume 1 rev. 3.25, sections 3.1.4 and 3.2; Volume 3
\* rev. 3.38, chapter 3.  Form legality, storage writes, memory, and exceptions
\* are deliberately outside this pure kernel.

Widths == {8, 16, 32, 64}
Flags == {"cf", "pf", "af", "zf", "sf", "of"}
Conditions == {"o", "no", "b", "ae", "e", "ne", "be", "a",
               "s", "ns", "p", "np", "l", "ge", "le", "g"}

\* @typeAlias: integerWord = Int -> Bool;
\* @typeAlias: integerFlags = Str -> Bool;
\* @typeAlias: integerFlagDomains = Str -> Set(Bool);

\* @type: $integerWord => Bool;
WordWellFormed(word) == DOMAIN word = 1..64 /\
                        \A bit \in 1..64 : word[bit] \in BOOLEAN

\* @type: $integerFlags => Bool;
FlagsWellFormed(flags) == DOMAIN flags = Flags /\
                          \A flag \in Flags : flags[flag] \in BOOLEAN

\* @type: $integerWord;
ZeroWord == [bit \in 1..64 |-> FALSE]
\* @type: $integerWord;
OneWord == [bit \in 1..64 |-> bit = 1]

\* @type: ($integerWord, Int) => $integerWord;
Truncate(word, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN word[bit] ELSE FALSE]

\* @type: ($integerWord, Int, Int) => $integerWord;
ZeroExtend(word, sourceWidth, targetWidth) ==
  [bit \in 1..64 |-> IF bit <= sourceWidth /\ bit <= targetWidth
                     THEN word[bit] ELSE FALSE]

\* @type: ($integerWord, Int, Int) => $integerWord;
SignExtend(word, sourceWidth, targetWidth) ==
  [bit \in 1..64 |->
    IF bit <= sourceWidth THEN word[bit]
    ELSE IF bit <= targetWidth THEN word[sourceWidth] ELSE FALSE]

\* @type: ($integerWord, Int) => $integerWord;
NotWord(word, width) ==
  [bit \in 1..64 |-> IF bit <= width THEN ~word[bit] ELSE FALSE]

\* @type: (Str, $integerWord, $integerWord, Int) => $integerWord;
LogicWord(op, left, right, width) ==
  [bit \in 1..64 |->
    IF bit > width THEN FALSE
    ELSE CASE op = "and" -> left[bit] /\ right[bit]
           [] op = "or" -> left[bit] \/ right[bit]
           [] op = "xor" -> left[bit] # right[bit]
           [] op = "andn" -> ~left[bit] /\ right[bit]]

\* @type: ($integerWord, Int) => Bool;
IsZero(word, width) == \A bit \in 1..width : ~word[bit]
\* @type: ($integerWord, $integerWord, Int) => Bool;
ActiveEqual(left, right, width) ==
  \A bit \in 1..width : left[bit] = right[bit]

\* Unsigned ordering without conversion to an unbounded host integer.
\* @type: ($integerWord, $integerWord, Int) => Bool;
UnsignedLess(left, right, width) ==
  \E pivot \in 1..width :
    /\ ~left[pivot] /\ right[pivot]
    /\ \A bit \in (pivot + 1)..width : left[bit] = right[bit]

\* @type: $integerWord => Bool;
ParityEven(word) == Cardinality({bit \in 1..8 : word[bit]}) % 2 = 0

\* Carry into one-based bit position. position=width+1 is carry out.
\* @type: ($integerWord, $integerWord, Bool, Int) => Bool;
CarryInto(left, right, carry, position) ==
  \/ carry /\ (\A bit \in 1..(position - 1) : left[bit] \/ right[bit])
  \/ \E generated \in 1..(position - 1) :
       /\ left[generated] /\ right[generated]
       /\ \A bit \in (generated + 1)..(position - 1) :
            left[bit] \/ right[bit]

\* @type: ($integerWord, $integerWord, Bool, Int) => $integerWord;
AddWord(left, right, carry, width) ==
  [bit \in 1..64 |->
    IF bit <= width
    THEN (left[bit] # right[bit]) # CarryInto(left, right, carry, bit)
    ELSE FALSE]

\* @type: ($integerWord, $integerWord, Bool, Int) => $integerWord;
SubWord(left, right, borrow, width) ==
  AddWord(left, NotWord(right, width), ~borrow, width)

\* @type: ($integerWord, $integerWord, Bool, Int) => Bool;
AddCarry(left, right, carry, width) ==
  CarryInto(left, right, carry, width + 1)

\* @type: ($integerWord, $integerWord, Bool, Int) => Bool;
SubBorrow(left, right, borrow, width) ==
  ~CarryInto(left, NotWord(right, width), ~borrow, width + 1)

\* @type: ($integerWord, $integerWord, Bool) => Bool;
AddAux(left, right, carry) == CarryInto(left, right, carry, 5)
\* @type: ($integerWord, $integerWord, Bool) => Bool;
SubAux(left, right, borrow) ==
  ~CarryInto(left, NotWord(right, 64), ~borrow, 5)

\* @type: ($integerWord, $integerWord, $integerWord, Int) => Bool;
AddOverflow(left, right, result, width) ==
  (left[width] = right[width]) /\ (result[width] # left[width])

\* @type: ($integerWord, $integerWord, $integerWord, Int) => Bool;
SubOverflow(left, right, result, width) ==
  (left[width] # right[width]) /\ (result[width] # left[width])

\* @type: ($integerWord, Int, Bool, Bool, Bool) => $integerFlags;
StatusFlags(result, width, cf, af, of) ==
  [flag \in Flags |->
    CASE flag = "cf" -> cf
      [] flag = "pf" -> ParityEven(result)
      [] flag = "af" -> af
      [] flag = "zf" -> IsZero(result, width)
      [] flag = "sf" -> result[width]
      [] OTHER -> of]

\* A per-flag set is the compact relational representation of flag effects.
\* BOOLEAN means architecturally undefined, not a chosen constant.
\* @type: $integerFlags => $integerFlagDomains;
ExactFlagDomains(flags) == [flag \in Flags |-> {flags[flag]}]
\* @type: $integerFlagDomains;
UndefinedFlagDomains == [flag \in Flags |-> BOOLEAN]

\* @type: ($integerFlags, $integerFlagDomains) => Bool;
FlagsAllowed(candidate, domains) ==
  FlagsWellFormed(candidate) /\
  \A flag \in Flags : candidate[flag] \in domains[flag]

\* @type: (Int, Int) => Bool;
NatBitSmall(number, bit) ==
  IF bit <= 7 THEN (number \div (2 ^ (bit - 1))) % 2 = 1 ELSE FALSE

\* @type: Int => $integerWord;
SmallNatWord(number) == [bit \in 1..64 |-> NatBitSmall(number, bit)]

\* @type: ($integerWord, Int) => $integerWord;
ByteSwap(word, width) ==
  [bit \in 1..64 |->
    IF bit <= width
    THEN LET byte == (bit - 1) \div 8
             within == (bit - 1) % 8
         IN word[width - (8 * byte) - 7 + within]
    ELSE FALSE]

\* @type: ($integerWord, Int, Int, Str) => $integerWord;
BitModify(word, width, index, action) ==
  LET selected == (index % width) + 1
  IN [bit \in 1..64 |->
       IF bit > width THEN FALSE
       ELSE IF bit # selected THEN word[bit]
       ELSE CASE action = "set" -> TRUE
              [] action = "reset" -> FALSE
              [] OTHER -> ~word[bit]]

\* Source and target are values, independent of register aliasing and writes.
\* @type: ($integerWord, $integerWord) => {left: $integerWord, right: $integerWord};
Exchange(left, right) == [left |-> right, right |-> left]

\* These predicates are the preconditions of the executable operators. Invalid
\* widths are rejected here rather than silently normalized by a kernel.
\* @type: ($integerWord, Int) => Bool;
ValidUnaryInputs(word, width) == WordWellFormed(word) /\ width \in Widths

\* @type: ($integerWord, $integerWord, Int) => Bool;
ValidBinaryInputs(left, right, width) ==
  WordWellFormed(left) /\ WordWellFormed(right) /\ width \in Widths

\* @type: ($integerFlags, Str, Bool) => $integerFlags;
SetStatusFlag(oldFlags, flag, value) == [oldFlags EXCEPT ![flag] = value]

\* @type: ($integerFlags, Str) => $integerFlags;
ComplementStatusFlag(oldFlags, flag) ==
  [oldFlags EXCEPT ![flag] = ~oldFlags[flag]]

\* LAHF stores SF:ZF:0:AF:0:PF:1:CF in the low byte.
\* @type: $integerFlags => $integerWord;
LahfValue(flags) ==
  [bit \in 1..64 |->
    CASE bit = 1 -> flags["cf"]
      [] bit = 2 -> TRUE
      [] bit = 3 -> flags["pf"]
      [] bit = 5 -> flags["af"]
      [] bit = 7 -> flags["zf"]
      [] bit = 8 -> flags["sf"]
      [] OTHER -> FALSE]

\* SAHF loads five status flags and preserves OF.
\* @type: ($integerFlags, $integerWord) => $integerFlags;
SahfFlags(oldFlags, value) ==
  [flag \in Flags |->
    CASE flag = "cf" -> value[1]
      [] flag = "pf" -> value[3]
      [] flag = "af" -> value[5]
      [] flag = "zf" -> value[7]
      [] flag = "sf" -> value[8]
      [] OTHER -> oldFlags[flag]]

\* @type: (Str, $integerFlags) => Bool;
ConditionHolds(condition, flags) ==
  CASE condition = "o" -> flags["of"]
    [] condition = "no" -> ~flags["of"]
    [] condition = "b" -> flags["cf"]
    [] condition = "ae" -> ~flags["cf"]
    [] condition = "e" -> flags["zf"]
    [] condition = "ne" -> ~flags["zf"]
    [] condition = "be" -> flags["cf"] \/ flags["zf"]
    [] condition = "a" -> ~flags["cf"] /\ ~flags["zf"]
    [] condition = "s" -> flags["sf"]
    [] condition = "ns" -> ~flags["sf"]
    [] condition = "p" -> flags["pf"]
    [] condition = "np" -> ~flags["pf"]
    [] condition = "l" -> flags["sf"] # flags["of"]
    [] condition = "ge" -> flags["sf"] = flags["of"]
    [] condition = "le" -> flags["zf"] \/ (flags["sf"] # flags["of"])
    [] OTHER -> ~flags["zf"] /\ (flags["sf"] = flags["of"])

\* @type: Bool => $integerWord;
SetConditionValue(condition) == [bit \in 1..64 |-> bit = 1 /\ condition]

=============================================================================
