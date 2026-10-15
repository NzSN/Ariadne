# Caller semantic coverage qualification — 2026-10-15

## Context and follow-up

**Status.** The caller semantic-coverage correction is implemented and its S5 finite regression gates pass. All 30 original caller barriers are removed. S6 remains partial because the expanded caller dataflow does not complete within one million actions; full caller native/Rust parity is unqualified.

**Why this document exists.** Item 2 follows the [completed loop-target work](../../loop-aware-target-resolution/20261015/README.md). The [canonical design](../../../../docs/Ariadne/caller-semantic-coverage-design.md) specifies scoped exception exits and guarded MOVAPS loads.

**What this document establishes.** Exact sources, source-bound model evidence, native controls and mutations, retained failures, original-dump coverage closure and the separate completion limit.

**Where to go next.** Read the [active execution plan](../../../../Plans/caller-semantic-coverage.md), [guard contract](../../../../docs/Ariadne/justified-branch-pruning-design.md) and [frame-path ledger](../../../../Plans/frame-path-enumeration.md). [Qualification metadata](qualification.json) separates the passed coverage/regression gates from unmet original-caller completion.

**What remains unresolved.** Later MOVAPS alignment, caller dataflow completion, two callee indirect jumps and frame paths remain open. Exception-handler/debugger resumption is outside the local normal-flow scope. This evidence establishes neither executed history nor a root cause.

## Implementation and review

A source-bound terminal receipt admits exact INT3, UD2 and reviewed UD1 encodings as complete normal-flow Stops. It retains conservative uses/may-defs, no must-defs, original BAP observations and explicit exception-exit/resumption limits. The UD1 rule checks the full ModR/M/SIB/displacement span while retaining the pinned BAP opcode-only span disagreement. LLVM supplies no effects.

The MOVAPS load recognizer binds the original load, YMM high-half preservation, RSP address and alignment guard. Pending discovery commits no load/vector effects; only a proved aligned verdict selects the original normal BAP effects. New versioned report/profile identities preserve the old store-only contract.

Review corrections require complete current candidate control, reject removed guard proofs under every known frame-report generation, and route frozen legacy guard validation through frozen capture validation. The last correction has a full-admission v7-positive/v8-negative control and a behavioral dependency-reversion mutant. Current capture, guard, composition, target/loop and Rust analysis sources were unchanged by that final native legacy-dependency correction.

## Sources and exercised validation

Final source capsule: `c35459a19b1e2f5f139730bea6c119cfceff603207254b52d42effac68654a5f`, 937 files. Final native helper: `d39df81c64c1fd832b88dd48652572234422d8d8840d277cbb83fb88e783e725`. The base commit is `3176d44850626707a490da75f3732abd8b450afd`; the capsule identifies the uncommitted implementation precisely.

All compilation, native execution, model checks, replay, mutations and dump execution ran in remote Windows WSL. Local work was source review, formatting, document/layout checks and artifact verification.

| Gate | Result |
| --- | --- |
| Root checks | 242 default tests, 46 core-only tests, format, all-feature/all-target Clippy, release build and layout pass. |
| Predicate authority | 58 configurations pass, with 71 declared oracle cases, 12,752 generated complete UD1 extents and 8,944 truncation controls. The final refresh verifies their exercised source hashes; it does not claim another model execution. |
| Unchanged target/composition/loop authority | Retained 5/19/25 configurations are verified against unchanged model/config/oracle sources. |
| Current native checker | 88 direct cases and 24 production protocol cases pass; nine behavioral mutants receive credit. |
| Frozen legacy dependency | Two full-admission controls pass; one dependency-reversion mutant receives credit. |
| Capture and reports | Nine native capture tests, six frame tests including both actual legacy combined generations, kernels, producer protocol and paired composition regressions pass. Actual guard-v1 replay passes. |
| Additional native capture mutations | Three intended behavioral failures pass, with an unchanged positive observer. |
| Generated core/stateflow replay | 168 + 162 observations pass; wrong-digest controls dispatch zero observations. |
| Old-helper capability | Both new input profiles reject before helper launch against the actual manifest-bound loop-generation helper. |

The final root/current/legacy control run is [final checks `074922`](artifacts/final-checks-20261015T074922/gates.json). The [final helper qualification `075232`](artifacts/qualification-20261015T075232Z-139849/qualification.json) binds fresh native regression/replay and exact-source retained gates. Finite checks are separate from universal refinement or whole-ISA qualification.

## Original dump result

Dump `dump_03958DA4FCA844A786262A1053`, SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`; thread 23668; frame pair 1 → 0; NP10. Roots and premises are unchanged. Expected table destinations remain test expectations, never additional roots.

| Observation | Result |
| --- | --- |
| Original caller barriers | **30 → 0**, with no replacement caller barriers. All 27 INT3 sites, UD2 and UD1 have checked terminal receipts; the load has a checked guard. |
| Initial MOVAPS store `0x00007ff7744033b3` | Aligned under the existing Windows normal-call-entry premises. |
| Later MOVAPS load `0x00007ff7744035c9` | Alignment unknown; normal load effects remain withheld. |
| Indirect targets | All nine original sets, 64 destinations and 51 formerly absent starts retained; DA09/DADD remain complete. Caller has 10 complete target sites. |
| Caller recovery | 9,600 attempted starts; 9,589 decoded instructions and 11,321 edges. |
| Callee | 778 decoded instructions, 895 edges and full native/Rust parity; two indirect barriers remain at `0x00007ff77443da0e` and `0x00007ff77443e200`. |
| Frame paths | The bounded full run returns zero with `unavailable` / `missing-frame-query`; enumeration is not exhausted. |

The [bounded full retry `073143`](artifacts/dump-20261015T073143/probe-summary.json) verifies coverage closure and native proof admission. Both caller engines reach the one-million-action limit. Rust remains in Dataflow after 554,409 ms with 105,570,377 represented reaching-definition links; native completion returns `action budget`. The 600-second Rust time limit was not the stopping condition. Peak recorded process RSS is approximately 33.6 GiB. No caller full-state parity is claimed.

The [final-helper refresh `075602`](artifacts/final-dump-admission-20261015T075602/probe-summary.json) compares both frames' normalized requests and guard/target/composition reports with the bounded run. It exercises caller structural recovery and final-helper initialization, plus full callee parity. Caller completion and fresh path enumeration are explicitly unexercised in that refresh; it does not replace or relabel the bounded full-run failure.

The existing 8,192-node frame-binding ceiling is also below the recovered caller's 9,589 decoded nodes. It is a subsequent boundary; the current `missing-frame-query` result occurs earlier because the caller has no completed query.

## Evidence boundaries

The original four-shape public-API feedback is RED at `060803` and GREEN at `072748`, without an alignment premise. Earlier model parser, build/interface and test-runner failures are retained without pass credit. Two old-version assertions in ignored capture tests were corrected together with their direct-wire scope/hash domains, then all nine tests passed. Historical evidence remains byte-identical.

[The export manifest](manifest.json), [sealed archive](evidence.tar.gz), [collection inventory](artifacts/delivery/collection.json) and [import verification](import-verification.json) bind source/tool identities, original and stored artifact hashes, lossless gzip originals and reproduction drivers. Documentation reconciliation is recorded separately from behavioral qualification. No commit or push is part of this delivery.
