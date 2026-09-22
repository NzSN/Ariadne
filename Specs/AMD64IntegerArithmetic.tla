-------------------- MODULE AMD64IntegerArithmetic --------------------
EXTENDS AMD64IntegerCore

\* Value/flag kernels for MOV extensions, ADD/ADC/ADCX/ADOX, SUB/SBB/CMP,
\* INC/DEC/NEG, AND/OR/XOR/TEST/ANDN, and the value part of XADD/CMPXCHG.
\* Manual source pages are recorded in integer-coverage.json.

\* @typeAlias: arithmeticResult = {value: $integerWord, flags: $integerFlags};
\* @typeAlias: compareExchangeResult = {accumulator: $integerWord,
\*   destination: $integerWord, flags: $integerFlags, equal: Bool};
\* @typeAlias: xaddResult = {destination: $integerWord, source: $integerWord,
\*   flags: $integerFlags};

\* @type: ($integerWord, $integerWord, Bool, Int) => $arithmeticResult;
AddResult(left, right, carry, width) ==
  LET value == AddWord(left, right, carry, width)
  IN [value |-> value,
      flags |-> StatusFlags(value, width,
                  AddCarry(left, right, carry, width),
                  AddAux(left, right, carry),
                  AddOverflow(left, right, value, width))]

\* @type: ($integerWord, $integerWord, Bool, Int) => $arithmeticResult;
SubResult(left, right, borrow, width) ==
  LET value == SubWord(left, right, borrow, width)
  IN [value |-> value,
      flags |-> StatusFlags(value, width,
                  SubBorrow(left, right, borrow, width),
                  SubAux(left, right, borrow),
                  SubOverflow(left, right, value, width))]

\* INC and DEC modify the arithmetic flags but preserve the old carry.
\* @type: ($integerWord, Int, Bool) => $arithmeticResult;
IncResult(value, width, oldCF) ==
  LET added == AddResult(value, OneWord, FALSE, width)
  IN [value |-> added.value,
      flags |-> [added.flags EXCEPT !["cf"] = oldCF]]

\* @type: ($integerWord, Int, Bool) => $arithmeticResult;
DecResult(value, width, oldCF) ==
  LET subtracted == SubResult(value, OneWord, FALSE, width)
  IN [value |-> subtracted.value,
      flags |-> [subtracted.flags EXCEPT !["cf"] = oldCF]]

\* @type: ($integerWord, Int) => $arithmeticResult;
NegResult(value, width) == SubResult(ZeroWord, value, FALSE, width)

\* Logical instructions clear CF/OF and define PF/ZF/SF; AF is undefined.
\* @type: (Str, $integerWord, Int) => $integerFlagDomains;
LogicFlagDomains(op, value, width) ==
  [flag \in Flags |->
    CASE flag = "cf" \/ flag = "of" -> {FALSE}
      [] flag = "pf" -> IF op = "andn" THEN BOOLEAN ELSE {ParityEven(value)}
      [] flag = "zf" -> {IsZero(value, width)}
      [] flag = "sf" -> {value[width]}
      [] OTHER -> BOOLEAN]

\* @type: (Str, $integerWord, $integerWord, Int, $integerWord, $integerFlags) => Bool;
LogicResultAllowed(op, left, right, width, value, flags) ==
  /\ value = LogicWord(op, left, right, width)
  /\ FlagsAllowed(flags, LogicFlagDomains(op, value, width))

\* TBM/BMI derived-bit operations are specified by the manual as short
\* ADD/SUB/NEG plus logical pseudo-operation sequences. Only 32/64-bit forms
\* are legal; that feature/form restriction remains at the form layer.
\* @type: (Str, $integerWord, Int) => $integerWord;
DerivedBitValue(op, source, width) ==
  LET incremented == AddWord(source, OneWord, FALSE, width)
      decremented == SubWord(source, OneWord, FALSE, width)
      negated == SubWord(ZeroWord, source, FALSE, width)
  IN CASE op = "blcfill" -> LogicWord("and", source, incremented, width)
       [] op = "blci" -> LogicWord("or", source, NotWord(incremented, width), width)
       [] op = "blcic" -> LogicWord("and", NotWord(source, width), incremented, width)
       [] op = "blcmsk" -> LogicWord("xor", source, incremented, width)
       [] op = "blcs" -> LogicWord("or", source, incremented, width)
       [] op = "blsfill" -> LogicWord("or", source, decremented, width)
       [] op = "blsi" -> LogicWord("and", negated, source, width)
       [] op = "blsic" -> LogicWord("or", NotWord(source, width), decremented, width)
       [] op = "blsmsk" -> LogicWord("xor", source, decremented, width)
       [] op = "blsr" -> LogicWord("and", source, decremented, width)
       [] op = "t1mskc" -> LogicWord("or", NotWord(source, width), incremented, width)
       [] op = "tzmsk" -> LogicWord("and", NotWord(source, width), decremented, width)

\* @type: (Str, $integerWord, Int) => $integerFlagDomains;
DerivedBitFlagDomains(op, source, width) ==
  LET value == DerivedBitValue(op, source, width)
      incremented == op \in {"blcfill", "blci", "blcic", "blcmsk", "blcs", "t1mskc"}
      negated == op = "blsi"
      cf == IF incremented THEN AddCarry(source, OneWord, FALSE, width)
            ELSE IF negated THEN SubBorrow(ZeroWord, source, FALSE, width)
            ELSE SubBorrow(source, OneWord, FALSE, width)
      logical == LogicFlagDomains("and", value, width)
  IN [flag \in Flags |-> IF flag = "cf" THEN {cf} ELSE logical[flag]]

\* ADX instructions update one carry chain and preserve every other flag.
\* @type: (Str, Bool, $integerFlags) => $integerFlagDomains;
AdxFlagDomains(chainFlag, exact, oldFlags) ==
  [flag \in Flags |-> IF flag = chainFlag THEN {exact} ELSE {oldFlags[flag]}]

\* @type: (Str, $integerWord, $integerWord, $integerFlags, Int,
\*   $integerWord, $integerFlags) => Bool;
AdxResultAllowed(chainFlag, left, right, oldFlags, width, value, flags) ==
  LET carryIn == oldFlags[chainFlag]
      result == AddWord(left, right, carryIn, width)
      carryOut == AddCarry(left, right, carryIn, width)
  IN /\ chainFlag \in {"cf", "of"}
     /\ value = result
     /\ FlagsAllowed(flags, AdxFlagDomains(chainFlag, carryOut, oldFlags))

\* Conditional selection returns the selected pure value. Condition decoding
\* is owned by the form/state layer.
\* @type: (Bool, $integerWord, $integerWord) => $integerWord;
ConditionalMove(condition, source, destination) ==
  IF condition THEN source ELSE destination

\* @type: ($integerWord, $integerWord, $integerWord, Int) => $compareExchangeResult;
CompareExchange(accumulator, destination, source, width) ==
  LET comparison == SubResult(accumulator, destination, FALSE, width)
  IN IF ActiveEqual(accumulator, destination, width)
     THEN [accumulator |-> Truncate(accumulator, width),
           destination |-> Truncate(source, width),
           flags |-> comparison.flags, equal |-> TRUE]
     ELSE [accumulator |-> Truncate(destination, width),
           destination |-> Truncate(destination, width),
           flags |-> comparison.flags, equal |-> FALSE]

\* @type: ($integerWord, $integerWord, Int) => $xaddResult;
XAdd(left, right, width) ==
  LET sum == AddResult(left, right, FALSE, width)
  IN [destination |-> sum.value, source |-> Truncate(left, width),
      flags |-> sum.flags]

=============================================================================
