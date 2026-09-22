----------------------- MODULE AMD64StringsChecks -----------------------
EXTENDS AMD64Strings

FalseFlags == [flag \in Flags |-> FALSE]
ZeroControl == [source |-> ZeroWord, destination |-> ZeroWord,
                count |-> ZeroWord, df |-> FALSE, status |-> FalseFlags]
OneControl == [ZeroControl EXCEPT !.count = OneWord]
MovsRep == [kind |-> "movs", elementBytes |-> 1, addressSize |-> 16,
            repeatMode |-> "rep", mode |-> "protected"]
CmpsRepe == [kind |-> "cmps", elementBytes |-> 4, addressSize |-> 64,
             repeatMode |-> "repe", mode |-> "long64"]
InsRep == [kind |-> "ins", elementBytes |-> 4, addressSize |-> 32,
           repeatMode |-> "rep", mode |-> "long64"]
OutsRep == [kind |-> "outs", elementBytes |-> 2, addressSize |-> 16,
            repeatMode |-> "rep", mode |-> "protected"]

MovsReady == [spec |-> MovsRep, control |-> OneControl,
              stage |-> "commitReady", completedIterations |-> 0]
\* A concrete fixture witness; the architectural relation does not require
\* this upper-half choice in legacy modes.
\* @type: (Str, Int, $integerWord, $integerWord) => $integerWord;
WriteWitness(mode, addressSize, before, value) ==
  [bit \in 1..64 |->
    IF bit <= addressSize THEN value[bit]
    ELSE IF addressSize = 32 /\ mode = "long64" THEN FALSE ELSE before[bit]]
\* @type: (Str, Int, Int, Bool, $integerWord) => $integerWord;
AdvanceWitness(mode, addressSize, elementBytes, df, before) ==
  LET delta == SmallNatWord(elementBytes)
      low == IF df THEN SubWord(before, delta, FALSE, addressSize)
              ELSE AddWord(before, delta, FALSE, addressSize)
  IN WriteWitness(mode, addressSize, before, low)
MovsAfterControl == [
  source |-> AdvanceWitness(MovsRep.mode, MovsRep.addressSize,
                            MovsRep.elementBytes, OneControl.df, OneControl.source),
  destination |-> AdvanceWitness(MovsRep.mode, MovsRep.addressSize,
                                 MovsRep.elementBytes, OneControl.df,
                                 OneControl.destination),
  count |-> WriteWitness(MovsRep.mode, MovsRep.addressSize, OneControl.count,
                         SubWord(OneControl.count, OneWord, FALSE,
                                 MovsRep.addressSize)),
  df |-> OneControl.df, status |-> OneControl.status]
MovsAfter == [kind |-> "body-applied",
              control |-> MovsAfterControl,
              stage |-> "none", completedIterations |-> 1]

KernelChecks ==
  /\ SpecWellFormed(MovsRep) /\ SpecWellFormed(CmpsRepe)
  /\ SpecWellFormed(InsRep) /\ SpecWellFormed(OutsRep)
  /\ Begin(MovsRep, ZeroControl).kind = "body-applied"
  /\ Begin(MovsRep, OneControl).stage = "sourceRead"
  /\ NextStage("movs", "sourceRead") = "destinationWrite"
  /\ NextStage("movs", "destinationWrite") = "commitReady"
  /\ NextStage("ins", "ioRead") = "destinationWrite"
  /\ NextStage("outs", "sourceRead") = "ioWrite"
  /\ ~ShouldContinue("repe", OneWord, 64, FALSE)
  /\ ~ShouldContinue("repne", OneWord, 64, TRUE)
  /\ ComparisonFlags(OneWord, OneWord, 8)["zf"]
  /\ CommitIteration(MovsReady, FalseFlags, MovsAfterControl, MovsAfter)
  /\ IsZero(MovsAfter.control.count, 16)
  /\ AdvancePointerAllowed("protected", 16, 1, FALSE, ZeroWord,
                           AdvanceWitness("protected", 16, 1, FALSE, ZeroWord))
  /\ AddressWriteAllowed("long64", 32, ZeroWord,
                         [b \in 1..64 |-> TRUE],
                         WriteWitness("long64", 32, ZeroWord,
                                      [b \in 1..64 |-> TRUE]))
  /\ \A bit \in 33..64 : ~WriteWitness("long64", 32, ZeroWord,
                                        [b \in 1..64 |-> TRUE])[bit]

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ KernelChecks
=============================================================================
