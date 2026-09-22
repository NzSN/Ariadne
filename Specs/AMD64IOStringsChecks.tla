--------------------- MODULE AMD64IOStringsChecks ---------------------
EXTENDS AMD64IOStrings

Address(number) == SmallNatWord(number)
Byte(number) == [bit \in 1..8 |-> NatBitSmall(number, bit)]
A0 == Address(0)
A1 == Address(1)
B1 == Byte(1)
Memory0 == {[physical |-> A0, value |-> B1],
            [physical |-> A1, value |-> Byte(2)]}
Captured == {A0, A1}
\* @type: Seq($amd64Byte);
Values == <<B1>>
FalseFlags == [flag \in Flags |-> FALSE]
\* @type: $stringControl;
Control0 == [source |-> ZeroWord, destination |-> OneWord,
             count |-> OneWord, df |-> FALSE, status |-> FalseFlags]
\* @type: $stringSpec;
OutsSpec == [kind |-> "outs", elementBytes |-> 1, addressSize |-> 64,
             repeatMode |-> "rep", mode |-> "long64"]
\* @type: $stringSpec;
InsSpec == [kind |-> "ins", elementBytes |-> 1, addressSize |-> 64,
            repeatMode |-> "rep", mode |-> "long64"]
\* @type: $stringControl;
ControlAfterOuts == [source |-> OneWord, destination |-> OneWord,
  count |-> ZeroWord, df |-> FALSE, status |-> FalseFlags]
\* @type: $stringControl;
ControlAfterIns == [source |-> ZeroWord,
  destination |-> SmallNatWord(2), count |-> ZeroWord,
  df |-> FALSE, status |-> FalseFlags]
ZeroFault == [stage |-> 0, vector |-> "GP", reason |-> "fixture",
  errorCode |-> NoPageFaultCode, linear |-> ZeroAddress]
\* @type: $ioPermissionSnapshot;
Snapshot == [status |-> "ready", covered |-> 0..65535,
  denied |-> {}, fault |-> ZeroFault]
\* @type: $ioOrdering;
Ordering == [priorWritesComplete |-> TRUE, nextSequence |-> 0]
\* @type: $ioRequest;
OutRequest == [direction |-> "output", base |-> 20, width |-> 1,
               writeData |-> Values, sequence |-> 0]
\* @type: $ioRequest;
InRequest == [direction |-> "input", base |-> 20, width |-> 1,
              writeData |-> <<>>, sequence |-> 0]
\* @type: $ioDeviceRule;
OutRule == [direction |-> "output", base |-> 20, width |-> 1,
            writeData |-> Values, readData |-> <<>>, transactionOrder |-> <<0>>]
\* @type: $ioDeviceRule;
InRule == [direction |-> "input", base |-> 20, width |-> 1,
           writeData |-> <<>>, readData |-> Values, transactionOrder |-> <<0>>]
OutEvent == RuleEvent(OutRule, OutRequest)
InEvent == RuleEvent(InRule, InRequest)
MemoryAfterIns == WriteResolvedBytesResult(Memory0, <<A1>>, Values)
CapturedAfterIns == Captured \cup {A1}

BindingChecks ==
  /\ OUTSSuccess(Memory0, Captured, <<A0>>, Values, OutsSpec, Control0,
       ControlAfterOuts, "long64", 3, 3, Snapshot, Ordering, {OutRule},
       OutRequest, OutEvent, ZeroFault)
  /\ INSSuccess(Memory0, Captured, <<A1>>, InsSpec, Control0,
       ControlAfterIns, "long64", 3, 3, Snapshot, Ordering, {InRule},
       InRequest, InEvent, ZeroFault, MemoryAfterIns, CapturedAfterIns)
  /\ IOStringEffectOrder("outs") = <<"memory-read", "io-write">>
  /\ IOStringEffectOrder("ins") = <<"io-read", "memory-write">>
  /\ MixedFailureOrderingOpen("ins") /\ MixedFailureOrderingOpen("outs")
  /\ MixedFailurePossibleEffects("ins") = <<"io-read-before-destination-fault">>

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ BindingChecks
=============================================================================
