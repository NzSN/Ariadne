---------------- MODULE AMD64ControlExecutionChecks ----------------
EXTENDS AMD64ControlExecution

VARIABLE
  \* @type: Bool;
  done

AllOnes == [bit \in 1..64 |-> TRUE]
Zeros == [bit \in 1..64 |-> FALSE]

LevelContracts ==
  /\ EnterLevel(0) = 0
  /\ EnterLevel(1) = 1
  /\ EnterLevel(31) = 31
  /\ EnterLevel(32) = 0
  /\ EnterLevel(255) = 31
  /\ EnterCopyIndices(0) = <<>>
  /\ EnterCopyIndices(1) = <<>>
  /\ EnterCopyIndices(3) = <<1, 2>>

EnterOrderContracts ==
  /\ EnterProgram(0) =
       <<[kind |-> "push-old-rbp", index |-> 0, register |-> "rbp"],
         [kind |-> "final-access-check", index |-> 0, register |-> ""]>>
  /\ Len(EnterProgram(1)) = 3
  /\ EnterProgram(1)[2].kind = "push-frame-pointer"
  /\ Len(EnterProgram(3)) = 7
  /\ EnterProgram(3)[2].kind = "read-frame"
  /\ EnterProgram(3)[3].kind = "push-frame"
  /\ EnterProgram(3)[4].index = 2
  /\ EnterProgram(3)[6].kind = "push-frame-pointer"
  /\ OrderedStackProgram(EnterProgram(31))

AllRegisterContracts ==
  /\ Len(PushaProgram) = 8
  /\ PushaProgram[5].register = "original-rsp"
  /\ Len(PopaProgram) = 8
  /\ PopaProgram[4].kind = "discard-pop"
  /\ OrderedStackProgram(PushaProgram)
  /\ OrderedStackProgram(PopaProgram)

FlagImageContracts ==
  /\ RFlagsFromWord([cf |-> FALSE, fixed1 |-> TRUE, pf |-> FALSE,
       reserved3 |-> FALSE, af |-> FALSE, reserved5 |-> FALSE,
       zf |-> FALSE, sf |-> FALSE, tf |-> FALSE, interruptEnable |-> FALSE,
       df |-> FALSE, of |-> FALSE, iopl |-> [index \in 1..2 |-> FALSE],
       nestedTask |-> FALSE, reserved15 |-> FALSE, resume |-> FALSE,
       virtual8086 |-> FALSE, ac |-> FALSE, virtualInterrupt |-> FALSE,
       virtualInterruptPending |-> FALSE, id |-> FALSE,
       reservedHigh |-> [index \in 1..42 |-> FALSE]], AllOnes).cf
  /\ Control!PushFlagImage("real", AllOnes)[17] = FALSE
  /\ Control!PushFlagImage("real", AllOnes)[18] = FALSE

Init == done = FALSE
Next == done' = ~done
Safety == LevelContracts /\ EnterOrderContracts /\ AllRegisterContracts /\
          FlagImageContracts

====================================================================
