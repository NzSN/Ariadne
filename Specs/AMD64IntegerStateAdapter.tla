----------------- MODULE AMD64IntegerStateAdapter -----------------
EXTENDS AMD64ArchitecturalState

Core == INSTANCE AMD64IntegerCore
StatusFlagNames == Core!Flags

\* Narrow adapter between the pure six-status-flag kernel and the complete
\* Volume 1 rFLAGS record. It does not execute an instruction.

\* Snowcat aliases are repeated at this composition boundary because aliases
\* are not re-exported transitively through multiple EXTENDS modules.
\* @typeAlias: integerWord = Int -> Bool;
\* @typeAlias: integerFlags = Str -> Bool;
\* @typeAlias: integerFlagDomains = Str -> Set(Bool);

\* @type: $amd64RFlags => $integerFlags;
ProjectStatusFlags(rflags) ==
  [flag \in StatusFlagNames |->
    CASE flag = "cf" -> rflags.cf
      [] flag = "pf" -> rflags.pf
      [] flag = "af" -> rflags.af
      [] flag = "zf" -> rflags.zf
      [] flag = "sf" -> rflags.sf
      [] OTHER -> rflags.of]

\* @type: ($amd64RFlags, $integerFlags) => $amd64RFlags;
ApplyStatusFlags(rflags, status) ==
  [rflags EXCEPT !.cf = status["cf"], !.pf = status["pf"],
                 !.af = status["af"], !.zf = status["zf"],
                 !.sf = status["sf"], !.of = status["of"]]

\* Relational application preserves correlations between an exact input flag
\* record and each allowed output choice.
\* @type: ($amd64RFlags, $integerFlagDomains, $amd64RFlags) => Bool;
StatusDomainsAllowed(before, domains, after) ==
  /\ Core!FlagsAllowed(ProjectStatusFlags(after), domains)
  /\ after = ApplyStatusFlags(before, ProjectStatusFlags(after))

\* CLD and STD update DF in the complete rFLAGS record.
\* @type: ($amd64RFlags, Bool) => $amd64RFlags;
SetDirectionFlag(rflags, value) == [rflags EXCEPT !.df = value]

=====================================================================
