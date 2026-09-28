---------------------- MODULE AriadneEffectsChecks ----------------------
EXTENDS AriadneEffects
VARIABLE
  \* @type: Bool;
  tick

Cells == [l \in {"a", "b", "memory"} |->
  CASE l = "a" -> {0} [] l = "b" -> {1} [] OTHER -> {2,3}]
L == DOMAIN Cells
OpaqueCheck == \A reads,writes \in SUBSET L:
  Sound(L, {[reads |-> reads, writes |-> writes, replaced |-> {}]},
        Opaque(L).uses, Opaque(L).mayDefs, Opaque(L).mustDefs)
ProjectionCheck == \A reads,writes \in SUBSET (0..3):
  /\ Replaced(Cells,writes) \subseteq Touched(Cells,writes)
  /\ Sound(L, {[reads |-> Touched(Cells,reads),
                writes |-> Touched(Cells,writes),
                replaced |-> Replaced(Cells,writes)]},
           Touched(Cells,reads), Touched(Cells,writes), Replaced(Cells,writes))
PartialRegister ==
  /\ Replaced(Cells,{0}) = {"a"}
  /\ ~Sound(L, {[reads |-> {}, writes |-> {"a"}, replaced |-> {"a"}]},
            {}, {"a","b"}, {"a","b"})
MemoryNoKill ==
  /\ Touched(Cells,{2}) = {"memory"}
  /\ Replaced(Cells,{2}) = {}
  /\ ~Sound(L, {[reads |-> {}, writes |-> {"memory"}, replaced |-> {}]},
            {}, {"memory"}, {"memory"})
\* An immediate store updates four/eight bytes within one abstract memory
\* location covering a larger unknown alias universe. Address cells are reads;
\* no read of prior memory or whole-cell replacement follows from the store.
MemoryCells == [l \in {"base", "index", "memory"} |->
  CASE l = "base" -> {0} [] l = "index" -> {1} [] OTHER -> 2..17]
MemoryLocations == DOMAIN MemoryCells
Store32 == 2..5
Store64 == 2..9
MemoryImmediateProjection ==
  /\ Catalogue(MemoryCells)
  /\ Touched(MemoryCells,Store32) = {"memory"}
  /\ Touched(MemoryCells,Store64) = {"memory"}
  /\ Replaced(MemoryCells,Store32) = {}
  /\ Replaced(MemoryCells,Store64) = {}
  /\ Sound(MemoryLocations,
       {[reads |-> {"base","index"}, writes |-> {"memory"}, replaced |-> {}]},
       {"base","index"}, {"memory"}, {})
  /\ ~Sound(MemoryLocations,
       {[reads |-> {"base","index"}, writes |-> {"memory"}, replaced |-> {}]},
       {"base","index"}, {"memory"}, {"memory"})
  /\ ~Sound(MemoryLocations,
       {[reads |-> {"base","index"}, writes |-> {"memory"}, replaced |-> {}]},
       {"base"}, {"memory"}, {})
  /\ ~Sound(MemoryLocations,
       {[reads |-> {"base","index"}, writes |-> {"memory"}, replaced |-> {}]},
       {"index"}, {"memory"}, {})
Nonvacuity == ~Sound(L, {}, {}, L, L)
ConditionalWrite == ~Sound(L,
  {[reads |-> {}, writes |-> {}, replaced |-> {}],
   [reads |-> {}, writes |-> {"a"}, replaced |-> {"a"}]}, {}, {"a"}, {"a"})
Safety == Catalogue(Cells) /\ OpaqueCheck /\ ProjectionCheck
          /\ PartialRegister /\ MemoryNoKill /\ MemoryImmediateProjection
          /\ Nonvacuity /\ ConditionalWrite
Init == tick = FALSE
Next == tick' = ~tick
Spec == Init /\ [][Next]_tick
=============================================================================
