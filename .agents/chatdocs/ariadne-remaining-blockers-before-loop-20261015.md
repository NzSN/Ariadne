# Ariadne blockers before loop closure — historical reconstruction

**Historical scope:** this reconstructs the deleted pre-loop inventory from retained run `dump-20261014T121127`. Its original temporary-file bytes are unavailable. It is not the current implementation status.

Regenerated on 2026-10-16. Later work resolves items recorded here; see the [updated inventory](ariadne-remaining-blockers-20261015.html).

| Historical item | Result in the retained pre-loop run |
| --- | --- |
| 1. Caller cyclic target certificates | DA09 and DADD remained incomplete. The caller had 8 complete target sites out of 10. |
| 2. Caller semantic coverage | **32 barriers:** two cyclic indirect jumps plus 27 INT3 sites, UD2, UD1 and a MOVAPS load. |
| 3. Initial MOVAPS store | Unknown alignment while candidate coverage remained incomplete. |
| 4. Callee coverage | **12 barriers**, including two indirect jumps and ten terminal-instruction barriers. |
| 5. Frame paths | Coverage `unavailable`, 0 paths, stop `missing-or-ambiguous-active-call-anchor`. |

The original caller query attempted 9,590 starts. The callee attempted 778. These counts are recovery/preparation observations, not an executed instruction history.

## What later changed

Loop closure completed DA09/DADD, reducing caller barriers from 32 to 30. Caller terminal/load support then removed those remaining 30 coverage barriers, admitted the initial MOVAPS normal outcome under recorded premises, and exposed the much larger caller dataflow action-budget limit.

The callee terminal correction reduced its barriers from 12 to two. The two remaining callee jumps have captured image tables; the [later case-4 analysis](ariadne-case4-analysis-20261015.html) explains the unresolved search/coverage work.

## Context and follow-up

**Status.** Historical reconstruction only. **Origin.** Retained source-bound 2026-10-14 dump retry. **Next reading.** [Current retained blocker inventory](ariadne-remaining-blockers-20261015.html). **Limit.** Restoring this document does not rerun the old analysis or undo later qualification.
