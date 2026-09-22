----------------- MODULE AMD64MemoryTypesChecks -----------------
EXTENDS AMD64MemoryTypes

Contracts ==
  /\ EffectiveMemoryType(FALSE, FALSE, "WB", "WB") = Resolved("UC")
  /\ EffectiveMemoryType(TRUE, TRUE, "WB", "WB") = Resolved("CD")
  /\ CombinePATMTRR("WB", "WT") = Resolved("WT")
  /\ CombinePATMTRR("WC", "WB") = Resolved("WC")
  /\ CombinePATMTRR("WC", "WT").kind = "unsupported"
  /\ CombinePATMTRR("bogus", "WB").kind = "unknown"
  /\ PATIndex(FALSE, FALSE, FALSE) = 0
  /\ PATIndex(TRUE, TRUE, TRUE) = 7

VARIABLE
  \* @type: Bool;
  checked
Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ Contracts
=================================================================
