----------------------- MODULE AMD64ControlChecks -----------------------
EXTENDS AMD64Control

VARIABLE
  \* @type: Bool;
  done

\* @type: (Bool, Bool, Bool, Bool, Bool) => $integerFlags;
Flags(cf, pf, zf, sf, of) == [name \in Integer!Flags |->
  CASE name = "cf" -> cf [] name = "pf" -> pf [] name = "af" -> FALSE
    [] name = "zf" -> zf [] name = "sf" -> sf [] OTHER -> of]

ZeroCarry == [bit \in 1..65 |-> FALSE]
AllOnesAddress == [bit \in AddressBits |-> TRUE]
ZeroState == [rip |-> ZeroAddress, rcx |-> ZeroAddress, rsp |-> ZeroAddress,
  flags |-> Flags(FALSE, FALSE, FALSE, FALSE, FALSE), mode |-> "long64",
  ssDefaultBig |-> TRUE, csLimit |-> ZeroAddress]
ZeroFallthrough == [instructionLength |-> 1, nextRIP |-> OneAddress]
ZeroRelative == [value |-> ZeroAddress, encodedWidth |-> 8,
  semanticWidth |-> 64, extension |-> "sign"]
TakenPlan == [taken |-> TRUE, fallthrough |-> ZeroAddress,
  target |-> OneAddress, nextRIP |-> OneAddress]

Init == done = FALSE
Next == done' = ~done
Spec == Init /\ [][Next]_done

ConditionsChecked ==
  /\ ConditionHolds("o", Flags(FALSE, FALSE, FALSE, FALSE, TRUE))
  /\ ConditionHolds("no", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("b", Flags(TRUE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("ae", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("e", Flags(FALSE, FALSE, TRUE, FALSE, FALSE))
  /\ ConditionHolds("ne", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("be", Flags(TRUE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("a", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("s", Flags(FALSE, FALSE, FALSE, TRUE, FALSE))
  /\ ConditionHolds("ns", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("p", Flags(FALSE, TRUE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("np", Flags(FALSE, FALSE, FALSE, FALSE, FALSE))
  /\ ConditionHolds("l", Flags(FALSE, FALSE, FALSE, TRUE, FALSE))
  /\ ConditionHolds("ge", Flags(FALSE, FALSE, FALSE, TRUE, TRUE))
  /\ ConditionHolds("le", Flags(FALSE, FALSE, TRUE, FALSE, FALSE))
  /\ ConditionHolds("g", Flags(FALSE, FALSE, FALSE, TRUE, TRUE))

CountChecked == CountIsZero(ZeroAddress, 16) /\ ~CountIsZero(OneAddress, 16)
RetireChecked == RetireTo(ZeroState, OneAddress,
  [ZeroState EXCEPT !.rip = OneAddress])
StackWidthsChecked == StackAddressSize(ZeroState) = 64 /\
  StackAddressSize([ZeroState EXCEPT !.mode = "protected", !.ssDefaultBig = TRUE]) = 32 /\
  StackAddressSize([ZeroState EXCEPT !.mode = "real", !.ssDefaultBig = FALSE]) = 16
TargetsChecked ==
  /\ TargetWithinCurrentCode("long64", ZeroAddress, 48, ZeroAddress)
  /\ TargetWithinCurrentCode("protected", ZeroAddress, 32, ZeroAddress)
  /\ ~TargetWithinCurrentCode("protected", OneAddress, 32, ZeroAddress)

StackOperandRulesChecked ==
  /\ StackOperandReady("long64", 16)
  /\ StackOperandReady("long64", 64)
  /\ ~StackOperandReady("long64", 32)
  /\ StackOperandReady("protected", 16)
  /\ StackOperandReady("protected", 32)
  /\ ~StackOperandReady("protected", 64)
  /\ AllRegisterStackReady("real", 16)
  /\ AllRegisterStackReady("protected", 32)
  /\ ~AllRegisterStackReady("long64", 32)

StackOrdersChecked ==
  /\ Len(PushaOrder) = 8 /\ PushaOrder[5] = "original-rsp"
  /\ Len(PopaOrder) = 8 /\ PopaOrder[4] = "discard-rsp"

FlagRulesChecked ==
  /\ FlagWritePermitted("real", 0, 0, "iopl")
  /\ FlagWritePermitted("protected", 0, 0, "iopl")
  /\ ~FlagWritePermitted("protected", 3, 3, "iopl")
  /\ FlagWritePermitted("protected", 2, 2, "if")
  /\ ~FlagWritePermitted("protected", 3, 2, "if")
  /\ ~FlagWritePermitted("protected", 0, 0, "vip")
  /\ PushFlagImage("real", AllOnesAddress)[17] = FALSE
  /\ PushFlagImage("real", AllOnesAddress)[18] = FALSE
  /\ PushFlagImage("protected", AllOnesAddress)[18] = TRUE
  /\ PopFlagImage(AllOnesAddress, ZeroAddress, 64, "protected", 3, 3)[17] = FALSE
  /\ PopFlagImage(AllOnesAddress, ZeroAddress, 64, "protected", 3, 3)[18] = TRUE
  /\ PopFlagImage(AllOnesAddress, ZeroAddress, 64, "protected", 3, 3)[13] = TRUE

UndefinedOpcodesChecked ==
  \A opcode \in UndefinedOpcodes : UndefinedOpcodeOutcome(opcode, "invalid-opcode-fault")

TentativeFaultChecked ==
  TentativeStackFault(ZeroState, [ZeroState EXCEPT !.rsp = OneAddress],
    [entry |-> ZeroState, tentative |-> [ZeroState EXCEPT !.rsp = OneAddress],
     visibility |-> "uncommitted-until-delivery-contract"])

Safety == ConditionsChecked /\ CountChecked /\ RetireChecked /\ StackWidthsChecked /\ TargetsChecked /\
  StackOperandRulesChecked /\ StackOrdersChecked /\ FlagRulesChecked /\
  UndefinedOpcodesChecked /\ TentativeFaultChecked

=============================================================================
