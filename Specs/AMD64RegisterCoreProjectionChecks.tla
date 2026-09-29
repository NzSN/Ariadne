--------------- MODULE AMD64RegisterCoreProjectionChecks ---------------
EXTENDS Integers, FiniteSets

\* Finite projection fixture for the Stage D MOV reg64, imm32 candidate. The
\* RAX byte cells are the analyzer's disjoint locations. A normal continuation
\* can definitely replace them; a mixture including a rollback fault cannot.
VARIABLE
  \* @type: Bool;
  checked
Core == INSTANCE AMD64RegisterCoreProfileChecks WITH profileChecked <- checked
Effects == INSTANCE AriadneEffects

RaxCells == {"gpr:rax:0", "gpr:rax:1", "gpr:rax:2", "gpr:rax:3",
  "gpr:rax:4", "gpr:rax:5", "gpr:rax:6", "gpr:rax:7"}
Locations == RaxCells \cup {"flag:zf", "memory:any"}
Cells == [l \in Locations |->
  CASE l = "gpr:rax:0" -> 1..8
    [] l = "gpr:rax:1" -> 9..16
    [] l = "gpr:rax:2" -> 17..24
    [] l = "gpr:rax:3" -> 25..32
    [] l = "gpr:rax:4" -> 33..40
    [] l = "gpr:rax:5" -> 41..48
    [] l = "gpr:rax:6" -> 49..56
    [] l = "gpr:rax:7" -> 57..64
    [] l = "flag:zf" -> {65}
    [] OTHER -> 66..81]
NormalWrite == [reads |-> {}, writes |-> RaxCells,
  replaced |-> RaxCells]
RollbackFault == [reads |-> {}, writes |-> {}, replaced |-> {}]

ProjectionSafety ==
  /\ Core!Mov64SignCandidate
  /\ Effects!Catalogue(Cells)
  /\ Effects!Touched(Cells, 1..64) = RaxCells
  /\ Effects!Replaced(Cells, 1..64) = RaxCells
  /\ Effects!Sound(Locations, {NormalWrite}, {}, RaxCells, RaxCells)
  /\ Effects!Sound(Locations, {NormalWrite, RollbackFault},
       {}, RaxCells, {})
  /\ ~Effects!Sound(Locations, {NormalWrite, RollbackFault},
       {}, RaxCells, RaxCells)
  /\ Core!UserMov64BoundaryAfter.rflags = Core!UserMov64Before.rflags

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ ProjectionSafety

========================================================================
