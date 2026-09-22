----------------------- MODULE AMD64MemoryTypes -----------------------
EXTENDS AMD64Memory

\* Partial, profile-bound effective memory-type resolution.
\* Authority: AMD APM Volume 2 revision 3.45 sections 7.4, 7.7 and 7.8.

MemoryTypes == {"UC", "UC-", "CD", "WC", "WC+", "WP", "WT", "WB"}
ResolutionKinds == {"resolved", "undefined", "unsupported", "unknown"}

\* @typeAlias: amd64MemoryTypeResolution = {kind: Str, memoryType: Str,
\*   reason: Str};
\* @typeAlias: amd64MTRRRegion = {base: $amd64Address,
\*   limit: $amd64Address, memoryType: Str};
\* @typeAlias: amd64MemoryTypeConfig = {cacheDisabled: Bool,
\*   mtrrsEnabled: Bool, defaultMTRR: Str, mtrrRegions: Set($amd64MTRRRegion),
\*   patFields: Int -> Str};

\* @type: Str => $amd64MemoryTypeResolution;
Resolved(memoryType) == [kind |-> "resolved", memoryType |-> memoryType,
  reason |-> ""]
\* @type: (Str, Str) => $amd64MemoryTypeResolution;
Unresolved(kind, reason) == [kind |-> kind, memoryType |-> "UC", reason |-> reason]

\* Supported subset of Volume 2 Table 7-11. Undefined combinations remain
\* explicit rather than being coerced to WB or UC.
\* @type: (Str, Str) => $amd64MemoryTypeResolution;
CombinePATMTRR(pat, mtrr) ==
  IF pat \notin MemoryTypes \/ mtrr \notin MemoryTypes
  THEN Unresolved("unknown", "unrecognized-type")
  ELSE IF pat = "UC" \/ mtrr = "UC" THEN Resolved("UC")
  ELSE IF pat = "UC-" THEN IF mtrr = "WC" THEN Resolved("WC") ELSE Resolved("UC")
  ELSE IF pat = mtrr THEN Resolved(pat)
  ELSE IF mtrr = "WB" THEN Resolved(pat)
  ELSE IF pat = "WB" THEN Resolved(mtrr)
  ELSE Unresolved("unsupported", "unimplemented-table-7-11-combination")

\* @type: (Bool, Bool, Str, Str) => $amd64MemoryTypeResolution;
EffectiveMemoryType(cacheDisabled, mtrrsEnabled, pat, mtrr) ==
  IF cacheDisabled THEN Resolved("CD")
  ELSE IF ~mtrrsEnabled THEN Resolved("UC")
  ELSE CombinePATMTRR(pat, mtrr)

\* @type: (Bool, Bool, Bool) => Int;
PATIndex(patBit, pcd, pwt) ==
  (IF patBit THEN 4 ELSE 0) + (IF pcd THEN 2 ELSE 0) +
  (IF pwt THEN 1 ELSE 0)

\* @type: ($amd64MemoryTypeConfig, $amd64Address) => $amd64MemoryTypeResolution;
MTRRTypeAt(config, physical) ==
  LET matches == {region \in config.mtrrRegions :
                    UnsignedLE(region.base, physical) /\
                    UnsignedLE(physical, region.limit)}
  IN IF ~config.mtrrsEnabled THEN Resolved("UC")
     ELSE IF matches = {} THEN Resolved(config.defaultMTRR)
     ELSE IF Cardinality(matches) = 1
          THEN Resolved((CHOOSE region \in matches : TRUE).memoryType)
          ELSE Unresolved("unsupported", "overlapping-mtrr-ranges")

\* @type: ($amd64MemoryTypeConfig, $amd64Address, Bool, Bool, Bool)
\*   => $amd64MemoryTypeResolution;
ResolveMemoryType(config, physical, patBit, pcd, pwt) ==
  LET mtrr == MTRRTypeAt(config, physical)
      pat == config.patFields[PATIndex(patBit, pcd, pwt)]
  IN IF config.cacheDisabled THEN Resolved("CD")
     ELSE IF mtrr.kind /= "resolved" THEN mtrr
     ELSE CombinePATMTRR(pat, mtrr.memoryType)

=======================================================================
