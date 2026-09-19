----------------- MODULE AriadneX86_64SemanticsChecks -----------------
EXTENDS AriadneX86_64Semantics

\* Interface-level regression vectors. Expected arithmetic uses bounded integer
\* calculations or explicit bit patterns, not the semantic arithmetic helpers.
\* @type: Int => $x86Word;
Small(n) == WordFromBytes([byte \in 1..8 |-> IF byte = 1 THEN n ELSE 0])
\* @type: Int => $x86Word;
Ones(width) == [bit \in 1..64 |-> bit <= width]
\* @type: Int => $x86Word;
SignedMin(width) == [bit \in 1..64 |-> bit = width]
\* @type: Int => $x86Word;
SignedMax(width) == [bit \in 1..64 |-> bit < width]

\* @type: ($x86Word, $x86Word) => $x86State;
TestState(left, right) ==
  [gpr |-> [reg \in GPRs |->
             CASE reg = "rax" -> left [] reg = "rbx" -> right [] OTHER -> Small(19)],
   flags |-> [flag \in Flags |-> TRUE]]

\* @type: ($x86Opcode, Int) => $x86Instruction;
RegInstruction(op, width) ==
  [op |-> op, width |-> width, dst |-> "rax", source |-> "reg", sourceReg |-> "rbx",
   immediate |-> ZeroWord, next |-> 100, target |-> 200, condition |-> ""]

\* @type: $x86Opcode => $x86Instruction;
ControlInstruction(op) ==
  [op |-> op, width |-> 0, dst |-> "", source |-> "none", sourceReg |-> "",
   immediate |-> ZeroWord, next |-> 100, target |-> 200, condition |-> ""]

\* @type: (Bool, Bool, Bool, Bool, Bool, Bool) => ($location -> Bool);
ExpectedFlags(cf, pf, af, zf, sf, of) ==
  [flag \in Flags |-> CASE flag = "cf" -> cf [] flag = "pf" -> pf
    [] flag = "af" -> af [] flag = "zf" -> zf [] flag = "sf" -> sf [] OTHER -> of]

\* @type: ($x86Opcode, Int, $x86Word, $x86Word, $x86Word, $location -> Bool) => Bool;
ArithmeticCase(op, width, left, right, result, flags) ==
  LET before == TestState(left, right)
      after == [gpr |-> [before.gpr EXCEPT !["rax"] = result], flags |-> flags]
  IN Execute(RegInstruction(op, width), before) = {Outcome(after, 100, "next", "running")}

ArithmeticBoundaries ==
  \A width \in {32, 64} :
    /\ ArithmeticCase("add", width, Ones(width), Small(1), ZeroWord,
         ExpectedFlags(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE))
    /\ ArithmeticCase("add", width, SignedMax(width), Small(1), SignedMin(width),
         ExpectedFlags(FALSE, TRUE, TRUE, FALSE, TRUE, TRUE))
    /\ ArithmeticCase("add", width, SignedMin(width), SignedMin(width), ZeroWord,
         ExpectedFlags(TRUE, TRUE, FALSE, TRUE, FALSE, TRUE))
    /\ ArithmeticCase("sub", width, ZeroWord, Small(1), Ones(width),
         ExpectedFlags(TRUE, TRUE, TRUE, FALSE, TRUE, FALSE))
    /\ ArithmeticCase("sub", width, SignedMin(width), Small(1), SignedMax(width),
         ExpectedFlags(FALSE, TRUE, TRUE, FALSE, FALSE, TRUE))
    /\ ArithmeticCase("sub", width, SignedMax(width), Ones(width), SignedMin(width),
         ExpectedFlags(TRUE, TRUE, FALSE, FALSE, TRUE, TRUE))

\* Low-nibble exhaustive inputs exercise every carry/borrow and auxiliary flag
\* combination without enumerating the architectural 64-bit state space.
SmallArithmetic ==
  \A x, y \in 0..15 : \A op \in {"add", "sub"} :
    LET subtract == op = "sub"
        byte == IF subtract THEN (256 + x - y) % 256 ELSE x + y
        borrow == subtract /\ x < y
        result == WordFromBytes([b \in 1..8 |->
                    IF b = 1 THEN byte ELSE IF b <= 4 /\ borrow THEN 255 ELSE 0])
        parity == Cardinality({b \in 0..7 : (byte \div (2 ^ b)) % 2 = 1}) % 2 = 0
    IN ArithmeticCase(op, 32, Small(x), Small(y), result,
         ExpectedFlags(borrow, parity, IF subtract THEN x < y ELSE x + y >= 16,
                       IF subtract THEN x = y ELSE x + y = 0, borrow, FALSE))

MoveAndCompare ==
  LET before == TestState(Ones(64), Ones(64))
      move32 == [before EXCEPT !.gpr["rax"] = Ones(32)]
      cmp32 == [before EXCEPT !.flags = ExpectedFlags(FALSE, TRUE, FALSE, TRUE, FALSE, FALSE)]
      imm5 == [RegInstruction("mov", 64) EXCEPT !.source = "imm", !.immediate = Small(5)]
      imm7 == [imm5 EXCEPT !.immediate = Small(7)]
  IN /\ Execute(RegInstruction("mov", 32), before) = {Outcome(move32, 100, "next", "running")}
     /\ Execute(RegInstruction("mov", 64), before) = {Outcome(before, 100, "next", "running")}
     /\ Execute(RegInstruction("cmp", 32), before) = {Outcome(cmp32, 100, "next", "running")}
     /\ Execute(imm5, before) =
          {Outcome([before EXCEPT !.gpr["rax"] = Small(5)], 100, "next", "running")}
     /\ Execute(imm7, before) =
          {Outcome([before EXCEPT !.gpr["rax"] = Small(7)], 100, "next", "running")}
     /\ Execute(imm5, before) # Execute(imm7, before)
     /\ Execute([RegInstruction("add", 64) EXCEPT
                   !.source = "imm", !.immediate = Ones(64)], TestState(Small(1), ZeroWord)) =
          {Outcome([TestState(Small(1), ZeroWord) EXCEPT !.gpr["rax"] = ZeroWord,
                      !.flags = ExpectedFlags(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE)],
                   100, "next", "running")}

LogicalChecks ==
  /\ \A width \in {32, 64} : \A op \in LogicalOps :
       LET before == TestState(Small(165), Small(15))
           value == CASE op \in {"and", "test"} -> 5 [] op = "or" -> 175 [] OTHER -> 170
           written == IF op = "test" THEN before.gpr
                      ELSE [before.gpr EXCEPT !["rax"] = Small(value)]
       IN Execute(RegInstruction(op, width), before) =
            {Outcome([gpr |-> written, flags |-> ExpectedFlags(FALSE, TRUE, af, FALSE, FALSE, FALSE)],
                     100, "next", "running") : af \in BOOLEAN}
  /\ \A width \in {32, 64} :
       LET before == TestState(Ones(64), ZeroWord)
           i == [RegInstruction("xor", width) EXCEPT !.sourceReg = "rax"]
       IN Execute(i, before) =
            {Outcome([gpr |-> [before.gpr EXCEPT !["rax"] = ZeroWord],
                      flags |-> ExpectedFlags(FALSE, TRUE, af, TRUE, FALSE, FALSE)],
                     100, "next", "running") : af \in BOOLEAN}
  /\ LET before == TestState(Ones(64), ZeroWord)
     IN \A outcome \in Execute(RegInstruction("test", 32), before) :
          outcome.state.gpr = before.gpr /\ outcome.state.flags["zf"]

\* Independent truth sets, checked for all 64 combinations of the six flags.
\* Both labels are checked even when target and fallthrough addresses coincide.
\* @type: ($location -> Bool) => Set($x86Condition);
TrueConditions(f) ==
  (IF f["of"] THEN {"o"} ELSE {"no"})
  \cup (IF f["cf"] THEN {"b"} ELSE {"ae"})
  \cup (IF f["zf"] THEN {"e"} ELSE {"ne"})
  \cup (IF ~f["cf"] /\ ~f["zf"] THEN {"a"} ELSE {"be"})
  \cup (IF f["sf"] THEN {"s"} ELSE {"ns"})
  \cup (IF f["pf"] THEN {"p"} ELSE {"np"})
  \cup (IF f["sf"] = f["of"] THEN {"ge"} ELSE {"l"})
  \cup (IF ~f["zf"] /\ f["sf"] = f["of"] THEN {"g"} ELSE {"le"})

BranchChecks ==
  \A flags \in [Flags -> BOOLEAN] : \A cc \in Conditions :
    LET state == [TestState(ZeroWord, ZeroWord) EXCEPT !.flags = flags]
        i == [ControlInstruction("jcc") EXCEPT !.condition = cc]
        taken == cc \in TrueConditions(flags)
    IN /\ Execute(i, state) =
            {Outcome(state, IF taken THEN 200 ELSE 100,
                     IF taken THEN "taken" ELSE "fallthrough", "running")}
       /\ Execute([i EXCEPT !.target = 100], state) =
            {Outcome(state, 100, IF taken THEN "taken" ELSE "fallthrough", "running")}

ControlAndUnsupported ==
  LET state == TestState(Ones(64), Small(5))
  IN /\ Execute(ControlInstruction("nop"), state) = {Outcome(state, 100, "next", "running")}
     /\ Execute(ControlInstruction("jmp"), state) = {Outcome(state, 200, "jump", "running")}
     /\ Execute(ControlInstruction("ud2"), state) = {Outcome(state, 0, "", "faulted")}
     /\ \A i \in {ControlInstruction("ret"), ControlInstruction("call"),
                    ControlInstruction("hlt"), RegInstruction("adc", 64),
                    RegInstruction("mov", 8), RegInstruction("mov", 16),
                    [RegInstruction("mov", 64) EXCEPT !.source = "memory"],
                    [RegInstruction("add", 64) EXCEPT
                      !.source = "imm", !.immediate = SignedMin(64)]} :
          /\ InstructionWellFormed(i)
          /\ ~Supported(i) /\ Execute(i, state) = {}
          /\ MustDefsOf(i) = {} /\ MayDefsOf(i) = X86Locations
     /\ UsesOf(RegInstruction("mov", 32)) = {"rbx"}
     /\ MustDefsOf(RegInstruction("mov", 32)) = {"rax"}
     /\ UsesOf(RegInstruction("cmp", 64)) = {"rax", "rbx"}
     /\ MustDefsOf(RegInstruction("cmp", 64)) = Flags
     /\ UsesOf([ControlInstruction("jcc") EXCEPT !.condition = "le"]) = {"zf", "sf", "of"}

FrameChecks ==
  \A op \in DataOps : \A width \in {32, 64} :
    LET i == RegInstruction(op, width)
        before == TestState(Ones(64), Small(5))
    IN \A outcome \in Execute(i, before) :
         /\ StateWellFormed(outcome.state)
         /\ \A reg \in GPRs \ MayDefsOf(i) : outcome.state.gpr[reg] = before.gpr[reg]
         /\ \A flag \in Flags \ MayDefsOf(i) : outcome.state.flags[flag] = before.flags[flag]

ExtendedRegisters ==
  LET before == [TestState(Ones(64), ZeroWord) EXCEPT !.gpr["r8"] = Ones(64)]
      i == [RegInstruction("mov", 32) EXCEPT !.dst = "r15", !.sourceReg = "r8"]
      self == [RegInstruction("mov", 32) EXCEPT !.sourceReg = "rax"]
  IN /\ Execute(i, before) =
          {Outcome([before EXCEPT !.gpr["r15"] = Ones(32)], 100, "next", "running")}
     /\ Execute(self, before) =
          {Outcome([before EXCEPT !.gpr["rax"] = Ones(32)], 100, "next", "running")}

BridgeChecks ==
  LET before == TestState(Small(5), Small(1))
      af0 == [before EXCEPT !.gpr["rax"] = ZeroWord,
                 !.flags = ExpectedFlags(FALSE, TRUE, FALSE, TRUE, FALSE, FALSE)]
      af1 == [af0 EXCEPT !.flags["af"] = TRUE]
      catalogue == [id \in {"in", "af0", "af1", "duplicate"} |->
                      CASE id = "in" -> before [] id = "af1" -> af1 [] OTHER -> af0]
      statuses == [id \in DOMAIN catalogue |-> "running"]
      program == [site \in {1, 100} |-> IF site = 1
                    THEN [RegInstruction("xor", 32) EXCEPT !.sourceReg = "rax"]
                    ELSE ControlInstruction("ret")]
      edges == {MachineEdge(1, 100, "next")}
      steps == RunningSteps(program, catalogue, statuses, edges)
      cut == [id \in DOMAIN catalogue \ {"af1"} |-> catalogue[id]]
      cutStatuses == [id \in DOMAIN cut |-> "running"]
      terminalCatalogue == [id \in {"live", "dead"} |-> before]
      terminalStatuses == [id \in {"live", "dead"} |-> IF id = "live" THEN "running" ELSE "faulted"]
      terminalProgram == [site \in {1} |-> ControlInstruction("ud2")]
  IN /\ CompleteSitesFor(program, catalogue, statuses, edges) = {1}
     /\ {s.after : s \in {t \in steps : t.src = 1 /\ t.before = "in"}} = {"af0", "af1", "duplicate"}
     /\ CompleteSitesFor(program, cut, cutStatuses, edges) = {}
     /\ CompleteSitesFor(program, catalogue, statuses, {MachineEdge(1, 100, "jump")}) = {}
     /\ RunningSteps(program, catalogue, statuses, {MachineEdge(1, 100, "jump")}) = {}
     /\ CompleteSitesFor(terminalProgram, terminalCatalogue, terminalStatuses, {}) = {1}
     /\ TerminalSteps(terminalProgram, terminalCatalogue, terminalStatuses) =
          {[site |-> 1, before |-> "live", after |-> "dead", outcome |-> "faulted"]}
     /\ CompleteSitesFor(terminalProgram, catalogue, statuses, {}) = {}

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == ~checked /\ checked' = TRUE
Safety == checked \in BOOLEAN /\ ArithmeticBoundaries /\ SmallArithmetic /\ MoveAndCompare
          /\ LogicalChecks /\ BranchChecks /\ ControlAndUnsupported /\ FrameChecks
          /\ ExtendedRegisters /\ BridgeChecks

=============================================================================
