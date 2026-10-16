# Ariadne remaining blockers — after caller semantic-coverage correction

**Blocker 1 is complete. Blocker 2's caller semantic coverage is fixed: 30 → 0 original barriers.** Full frame-to-frame completion has separate remaining limits.

Regenerated on **2026-10-16** from the retained 2026-10-15 records. This is a restored report, not a new dump execution. The work was published in commit `6192dee19a5b2f133177a21187952e28d603c2d9`.

Dump: `dump_03958DA4FCA844A786262A1053`; thread 23668; frames 1 → 0; NP10.

| Original item | Retained result |
| --- | --- |
| **1. Cyclic caller target certificates** | **Complete.** DA09 and DADD retain their four-target induction receipts. All nine original table sets, 64 destinations and 51 formerly missing starts remain covered. |
| **2. Caller semantic coverage** | **30 → 0 barriers**, with no replacement caller barriers. Checked normal-flow exits cover 27 INT3 sites, UD2 and UD1. The MOVAPS load is recognized and guarded. |
| **3. Initial MOVAPS alignment** | The store at `0x7ff7744033b3` is **aligned under the recorded premises**. The later load at `0x7ff7744035c9` remains unknown, so its normal effects are withheld. |
| **4. Callee coverage** | **12 → 2 barriers.** Indirect jumps `0x7ff77443da0e` and `0x7ff77443e200` remain unresolved. Callee completed native/Rust states match. |
| **5. Frame paths** | **Unavailable**, zero returned paths, `missing-frame-query`. The caller query did not complete. This does not establish that no path exists. |

## Newly exposed completion limit

Caller recovery now has **9,589 decoded instructions and 11,321 edges**, with 9,600 attempted starts. Both caller engines reach the **1,000,000-action diagnostic limit**. Rust stops in Dataflow after 554,409 ms with 105,570,377 represented reaching-definition links; native completion returns `action budget`. Peak recorded process RSS was approximately 33.6 GiB. Full caller completed-state parity remains unverified.

The current frame-binding cap is 8,192 decoded nodes. The caller alone exceeds it; the caller plus callee totals 10,367. This is a subsequent boundary: the retained result first stops because the completed caller graph is missing.

## Case 4 has been analyzed

The [case-4 report](ariadne-case4-analysis-20261015.html) verifies that both fixed image tables are fully captured. Conditional table arithmetic yields **21 mapped destinations for DA0E** and **13 for E200**, with 31 not-yet-attempted starts across their 34-destination union.

Current resolution is blocked by predecessor-search scheduling/shared work exhaustion and a narrower loop-index matcher. These independent table reads do not close the two incoming-coverage certificates.

## Validation and outcome boundaries

The qualified sources passed 242 default tests, 46 core-only tests, format/Clippy/release checks, nine native capture tests, 88 direct controls, 24 protocol controls, nine caller mutations, two legacy dependency controls with one mutation, three additional capture mutations and 330 generated core/stateflow observations. Predicate-model/oracle evidence is retained with verified source identities.

Full retry `073143` establishes caller coverage closure and the action-limit result. Final-helper refresh `075602` confirms equal normalized requests and proof reports, caller structural recovery/native admission and full callee parity. It does not repeat or claim completed caller dataflow.

## Context and follow-up

**Status.** The original semantic barriers are closed within local-normal-flow scope; the plan's S6 full-caller comparison remains open. **Contribution.** This inventory preserves the original five blocker numbers and records the completion boundary. **Next reading.** [Frame-path semantics](ariadne-frame-to-frame-semantics-20261015.html), [case-4 analysis](ariadne-case4-analysis-20261015.html) and [historical pre-loop inventory](ariadne-remaining-blockers-before-loop-20261015.html). **Limits.** No executed-history, root-cause, full caller completion or full frame-path listing is claimed.
