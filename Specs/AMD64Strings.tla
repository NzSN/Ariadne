-------------------------- MODULE AMD64Strings --------------------------
EXTENDS AMD64IntegerArithmetic

\* Control and staging foundation for CMPS, INS, LODS, MOVS, OUTS, SCAS,
\* and STOS. Authority: AMD APM Volume 3 revision 3.38, section 1.2.6 and
\* reference entries V3-GP-045, 059, 072, 088, 100, 130, and 142.
\*
\* The architectural GPR identities are fixed by AMD64ArchitecturalState:
\* RCX=1 (count), RDX=2 (I/O port), RSI=6 (source), RDI=7 (destination),
\* and RAX=0 (accumulator). Address size selects their 16/32/64-bit views.
\*
\* Stages name required operations; they are not unconstrained callbacks.
\* This module does not claim a memory or I/O operation succeeded. The memory
\* layer must discharge each stage before CommitIteration is used. Completed
\* iteration count is intentionally absent from generic effect-prefix count.

StringKinds == {"cmps", "ins", "lods", "movs", "outs", "scas", "stos"}
RepeatModes == {"none", "rep", "repe", "repne"}
ElementBytes == {1, 2, 4, 8}
StringAddressSizes == {16, 32, 64}
StringModes == {"real", "protected", "virtual8086", "compatibility", "long64"}
StringStages == {"sourceRead", "destinationRead", "ioRead", "accumulatorWrite",
                 "destinationWrite", "ioWrite", "flagsWrite", "commitReady"}

\* @typeAlias: stringSpec = {kind: Str, elementBytes: Int,
\*   addressSize: Int, repeatMode: Str, mode: Str};
\* @typeAlias: stringControl = {source: $integerWord,
\*   destination: $integerWord, count: $integerWord, df: Bool,
\*   status: $integerFlags};
\* @typeAlias: stringContinuation = {spec: $stringSpec,
\*   control: $stringControl, stage: Str, completedIterations: Int};
\* @typeAlias: stringBoundary = {kind: Str, control: $stringControl,
\*   stage: Str, completedIterations: Int};
\* @typeAlias: stringRestart = {faultingIP: $integerWord,
\*   control: $stringControl, completedIterations: Int};

\* @type: Str => Bool;
UsesSourcePointer(kind) == kind \in {"cmps", "lods", "movs", "outs"}
\* @type: Str => Bool;
UsesDestinationPointer(kind) == kind \in {"cmps", "ins", "movs", "scas", "stos"}
\* @type: Str => Bool;
UpdatesStatusFlags(kind) == kind \in {"cmps", "scas"}
\* @type: Str => Bool;
UsesIO(kind) == kind \in {"ins", "outs"}

\* @type: (Str, Str) => Bool;
RepeatValidFor(repeatMode, kind) ==
  \/ repeatMode = "none" /\ kind \in StringKinds
  \/ repeatMode = "rep" /\ kind \in {"ins", "lods", "movs", "outs", "stos"}
  \/ repeatMode \in {"repe", "repne"} /\ kind \in {"cmps", "scas"}

\* @type: $stringSpec => Bool;
SpecWellFormed(spec) ==
  /\ spec.kind \in StringKinds
  /\ spec.elementBytes \in ElementBytes
  /\ spec.addressSize \in StringAddressSizes
  /\ spec.repeatMode \in RepeatModes
  /\ spec.mode \in StringModes
  /\ RepeatValidFor(spec.repeatMode, spec.kind)
  /\ (spec.addressSize = 64 => spec.mode = "long64")
  /\ (spec.mode = "long64" => spec.addressSize # 16)
  /\ (spec.elementBytes = 8 => spec.mode = "long64")
  /\ (UsesIO(spec.kind) => spec.elementBytes # 8)

\* @type: $stringControl => Bool;
ControlWellFormed(control) ==
  /\ WordWellFormed(control.source)
  /\ WordWellFormed(control.destination)
  /\ WordWellFormed(control.count)
  /\ FlagsWellFormed(control.status)

\* Volume 1 section 3.4.5 makes bits 63:32 inaccessible/undefined outside
\* 64-bit mode. This relation constrains observable bits without inventing a
\* legacy upper-half value. A 16-bit write preserves observable bits 31:16.
\* @type: (Str, Int, $integerWord, $integerWord, $integerWord) => Bool;
AddressWriteAllowed(mode, addressSize, before, value, after) ==
  \A bit \in 1..64 :
    IF bit <= addressSize THEN after[bit] = value[bit]
    ELSE IF addressSize = 32 /\ mode = "long64" THEN ~after[bit]
    ELSE IF addressSize = 16 /\ bit <= 32 THEN after[bit] = before[bit]
    ELSE TRUE

\* @type: (Str, Int, Int, Bool, $integerWord, $integerWord) => Bool;
AdvancePointerAllowed(mode, addressSize, elementBytes, df, before, after) ==
  LET delta == SmallNatWord(elementBytes)
      low == IF df THEN SubWord(before, delta, FALSE, addressSize)
              ELSE AddWord(before, delta, FALSE, addressSize)
  IN AddressWriteAllowed(mode, addressSize, before, low, after)

\* @type: (Str, Int, $integerWord, $integerWord) => Bool;
DecrementCountAllowed(mode, addressSize, before, after) ==
  AddressWriteAllowed(mode, addressSize, before,
                      SubWord(before, OneWord, FALSE, addressSize), after)

\* @type: ($stringSpec, $stringControl) => Bool;
RepeatCountZero(spec, control) == IsZero(control.count, spec.addressSize)
\* @type: ($stringSpec, $stringControl) => Bool;
ShouldExecute(spec, control) ==
  spec.repeatMode = "none" \/ ~RepeatCountZero(spec, control)

\* The ZF argument is the value produced by the completed CMPS/SCAS iteration.
\* @type: (Str, $integerWord, Int, Bool) => Bool;
ShouldContinue(repeatMode, countAfter, addressSize, zfAfter) ==
  LET nonzero == ~IsZero(countAfter, addressSize)
  IN CASE repeatMode = "none" -> FALSE
       [] repeatMode = "rep" -> nonzero
       [] repeatMode = "repe" -> nonzero /\ zfAfter
       [] OTHER -> nonzero /\ ~zfAfter

\* @type: ($stringSpec, $stringControl, $integerFlags, $stringControl) => Bool;
CommitControlAllowed(spec, before, statusAfter, after) ==
  /\ IF UsesSourcePointer(spec.kind)
     THEN AdvancePointerAllowed(spec.mode, spec.addressSize, spec.elementBytes,
                                before.df, before.source, after.source)
     ELSE after.source = before.source
  /\ IF UsesDestinationPointer(spec.kind)
     THEN AdvancePointerAllowed(spec.mode, spec.addressSize, spec.elementBytes,
                                before.df, before.destination, after.destination)
     ELSE after.destination = before.destination
  /\ IF spec.repeatMode = "none" THEN after.count = before.count
     ELSE DecrementCountAllowed(spec.mode, spec.addressSize, before.count, after.count)
  /\ after.df = before.df
  /\ after.status = IF UpdatesStatusFlags(spec.kind) THEN statusAfter ELSE before.status

\* CMPS supplies source as left and destination as right. SCAS supplies the
\* accumulator as left and destination memory as right.
\* @type: ($integerWord, $integerWord, Int) => $integerFlags;
ComparisonFlags(left, right, width) == SubResult(left, right, FALSE, width).flags

\* @type: Str => Str;
FirstStage(kind) ==
  CASE kind \in {"cmps", "lods", "movs", "outs"} -> "sourceRead"
    [] kind = "ins" -> "ioRead"
    [] kind = "scas" -> "destinationRead"
    [] OTHER -> "destinationWrite"

\* @type: (Str, Str) => Bool;
StageHasSuccessor(kind, stage) ==
  \/ stage = "sourceRead" /\ kind \in {"cmps", "lods", "movs", "outs"}
  \/ stage = "destinationRead" /\ kind \in {"cmps", "scas"}
  \/ stage = "ioRead" /\ kind = "ins"
  \/ stage = "accumulatorWrite" /\ kind = "lods"
  \/ stage = "destinationWrite" /\ kind \in {"movs", "ins", "stos"}
  \/ stage = "ioWrite" /\ kind = "outs"
  \/ stage = "flagsWrite" /\ kind \in {"cmps", "scas"}

\* Precondition: StageHasSuccessor(kind, stage).
\* @type: (Str, Str) => Str;
NextStage(kind, stage) ==
  CASE stage = "sourceRead" /\ kind = "cmps" -> "destinationRead"
    [] stage = "sourceRead" /\ kind = "lods" -> "accumulatorWrite"
    [] stage = "sourceRead" /\ kind = "movs" -> "destinationWrite"
    [] stage = "sourceRead" /\ kind = "outs" -> "ioWrite"
    [] stage = "destinationRead" -> "flagsWrite"
    [] stage = "ioRead" -> "destinationWrite"
    [] stage \in {"accumulatorWrite", "destinationWrite", "ioWrite",
                   "flagsWrite"} -> "commitReady"
    [] OTHER -> "invalid"

\* @type: ($stringContinuation, $stringContinuation) => Bool;
AdvanceStage(before, after) ==
  /\ StageHasSuccessor(before.spec.kind, before.stage)
  /\ after = [before EXCEPT !.stage = NextStage(before.spec.kind, before.stage)]

\* Common-shape boundary exposes zero-count body completion. `body-applied`
\* excludes RIP/fallthrough/trap/async handling and architectural retirement.
\* @type: ($stringSpec, $stringControl) => $stringBoundary;
Begin(spec, control) ==
  IF ShouldExecute(spec, control)
  THEN [kind |-> "inProgress", control |-> control,
        stage |-> FirstStage(spec.kind), completedIterations |-> 0]
  ELSE [kind |-> "body-applied", control |-> control,
        stage |-> "none", completedIterations |-> 0]

\* @type: ($stringContinuation, $integerFlags, $stringControl, $stringBoundary) => Bool;
CommitIteration(before, statusAfter, control, after) ==
  LET completed == before.completedIterations + 1
      continued == ShouldContinue(before.spec.repeatMode, control.count,
                                  before.spec.addressSize, control.status["zf"])
  IN /\ before.stage = "commitReady"
     /\ CommitControlAllowed(before.spec, before.control, statusAfter, control)
     /\ after = IF continued
          THEN [kind |-> "inProgress", control |-> control,
                stage |-> FirstStage(before.spec.kind),
                completedIterations |-> completed]
          ELSE [kind |-> "body-applied", control |-> control,
                stage |-> "none", completedIterations |-> completed]

\* @type: ($integerWord, $stringContinuation) => $stringRestart;
RestartAtBoundary(faultingIP, continuation) ==
  [faultingIP |-> faultingIP, control |-> continuation.control,
   completedIterations |-> continuation.completedIterations]

=============================================================================
