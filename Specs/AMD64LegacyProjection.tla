------------------- MODULE AMD64LegacyProjection -------------------
EXTENDS Integers, FiniteSets

\* Private regression oracle for the pre-expansion, register-only evaluator.
\* This compares the new integer value/flag kernels after projecting into the
\* old six-flag/GPR state. It does NOT certify memory, faults, mode legality,
\* the new machine-state dispatcher or complete AMD64 instruction coverage.
Old == INSTANCE AriadneX86_64Semantics
New == INSTANCE AMD64IntegerArithmetic

\* @type: Int => (Int -> Bool);
Ones(width) == [bit \in 1..64 |-> bit <= width]
\* @type: Int => (Int -> Bool);
Minimum(width) == [bit \in 1..64 |-> bit = width]
\* @type: Int => (Int -> Bool);
Maximum(width) == [bit \in 1..64 |-> bit < width]

Words == {Old!ZeroWord, [bit \in 1..64 |-> bit = 1],
          Ones(32), Ones(64), Minimum(32), Minimum(64),
          Maximum(32), Maximum(64), [bit \in 1..64 |-> bit % 2 = 0]}

\* @type: ((Int -> Bool), (Int -> Bool)) => $x86State;
Before(left, right) ==
  [gpr |-> [reg \in Old!GPRs |->
     IF reg = "rax" THEN left ELSE IF reg = "rbx" THEN right ELSE Ones(64)],
   flags |-> [flag \in Old!Flags |-> flag \in {"cf", "af", "of"}]]

\* @type: (Str, Int) => $x86Instruction;
Instruction(op, width) ==
  [op |-> op, width |-> width, dst |-> "rax", source |-> "reg",
   sourceReg |-> "rbx", immediate |-> Old!ZeroWord,
   next |-> 100, target |-> 200, condition |-> ""]

\* @type: (Str, Int, $x86State, (Int -> Bool), (Str -> Bool)) => $x86State;
Projected(op, width, before, value, flags) ==
  [gpr |-> IF op \in {"cmp", "test"} THEN before.gpr
           ELSE [before.gpr EXCEPT !["rax"] = value],
   flags |-> flags]

\* @type: (Str, Int, $x86State) => Set($x86State);
KernelProjection(op, width, before) ==
  LET left == before.gpr["rax"]
      right == before.gpr["rbx"]
  IN IF op = "mov"
     THEN {Projected(op, width, before, New!Truncate(right, width), before.flags)}
     ELSE IF op \in {"add", "sub", "cmp"}
     THEN LET result == IF op = "add" THEN New!AddResult(left, right, FALSE, width)
                        ELSE New!SubResult(left, right, FALSE, width)
          IN {Projected(op, width, before, result.value, result.flags)}
     ELSE LET logicOp == IF op = "test" THEN "and" ELSE op
              value == New!LogicWord(logicOp, left, right, width)
              candidates == {flags \in [Old!Flags -> BOOLEAN] :
                New!LogicResultAllowed(logicOp, left, right, width, value, flags)}
          IN {Projected(op, width, before, value, flags) : flags \in candidates}

=============================================================================
