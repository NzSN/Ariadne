------------------------- MODULE AriadneEffects -------------------------
EXTENDS AriadneMachineCommon

\* Abstract projection only: architectural atoms/continuations are supplied
\* evidence. This module does not prove LLVM or AMD manual interpretation.
\* @type: (Set($location), Set({reads: Set($location), writes: Set($location), replaced: Set($location)}), Set($location), Set($location), Set($location)) => Bool;
Sound(L, outcomes, uses, mayDefs, mustDefs) ==
  /\ outcomes # {}
  /\ MachineEffectWellFormed(L, uses, mustDefs, mayDefs)
  /\ \A t \in outcomes:
       /\ t.reads \subseteq uses
       /\ t.writes \subseteq mayDefs
       /\ mustDefs \subseteq t.replaced
       /\ t.replaced \subseteq t.writes

\* Cell maps are disjoint, nonempty atom sets; an overlapping register view
\* is expanded into these cells, never stored as another independent location.
\* @type: ($location -> Set(Int)) => Bool;
Catalogue(cells) ==
  /\ \A l \in DOMAIN cells: cells[l] # {}
  /\ \A a,b \in DOMAIN cells: a # b => cells[a] \cap cells[b] = {}

\* @type: ($location -> Set(Int), Set(Int)) => Set($location);
Touched(cells, atoms) == {l \in DOMAIN cells : cells[l] \cap atoms # {}}
\* @type: ($location -> Set(Int), Set(Int)) => Set($location);
Replaced(cells, atoms) == {l \in DOMAIN cells : cells[l] # {} /\ cells[l] \subseteq atoms}

\* No-trust effects retain every possible origin, without a definite kill.
\* @type: Set($location) => {uses: Set($location), mayDefs: Set($location), mustDefs: Set($location)};
Opaque(L) == [uses |-> L, mayDefs |-> L, mustDefs |-> {}]
=============================================================================
