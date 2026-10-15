# Loop-aware target closure qualification — 2026-10-15

## Context and follow-up

**Status.** The L0–L6 stable-base loop extension is implemented and accepted for its declared finite/source-bound scope. Original-dump probe `051409` closes DA09 and DADD through independently validated induction receipts. The parent ninth incoming-coverage clause is closed.

**Why this document exists.** The [canonical design](../../../../docs/Ariadne/guarded-target-resolution-design.md#proposed-stable-base-invariant-follow-up) and [execution plan](../../../../Plans/completed/loop-aware-target-resolution.md) extend the existing resolver beyond the earlier cyclic incoming-state residuals.

**What this document establishes.** Exact qualified sources/tools, finite controls, legacy semantic replay, retained failures, both original-dump loop proofs, all-nine candidate reconciliation and native/Rust full-state parity.

**Where to go next.** Read the canonical design for contracts and current usage, the [parent composition plan](../../../../Plans/completed/guarded-target-resolution.md) for its closed C5 clause, and the [frame-path ledger](../../../../Plans/frame-path-enumeration.md) for the still-unavailable listing.

**What remains unresolved.** Caller guard coverage retains 30 barriers and its initial MOVAPS is unknown. Callee coverage retains 12 barriers. NP10 frame paths remain unavailable with `missing-or-ambiguous-active-call-anchor`. General loop synthesis, new loop-only target discovery, heap traversal and universal Rust/inter-model refinement remain outside this delivery.

The [qualification summary](qualification.json) gives the accepted scope and links every gate.

## Qualified implementation and source identity

The existing local resolver now supports `InductiveDispatch` whole-dispatch coverage alongside ordinary prefix-tree receipts. It checks every entrance, original transfer, internal edge and exit of a bounded local phase region. Pointer values and selector loads may change each iteration. Captured relative32 table entries remain independently justified by ordinary path receipts; the loop strategy supplies coverage, and declines when a required witness is missing.

Local target v3/local-v2, combined native v2, composition v2 and outer minidump/explanation/frame v5/v4/v4 carry the new contract. Dedicated frozen v1 replay preserves actual retained legacy reports. Rooted target-only v1 remains supported. A [supplemental public-API control](artifacts/legacy-capability-20261015T052319/result.json), linked against the same qualified release library, rejects a genuine old helper lacking v2 before process launch; the old runtime is not exercised.

The qualified source archive is SHA-256 `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee`, with 877 verified files, retained in [the source capsule](reproduce/source-current.tar.gz) and [source manifest](artifacts/delivery/source-manifest.json). The working-tree base is `da7308aecda19b45c9257a5414b7d405fcd8a7dd`; the source capsule, rather than that base commit alone, identifies this implementation. Later documentation/evidence reconciliation is recorded separately from runtime qualification.

Native helper SHA-256 is `7f8030820b486dc5a7ec055433d5a7540496c3aaa85fb04c3d91cbdc9e6ec1dd`. The [native manifest](artifacts/final-native/manifest.json) and [tool identities](artifacts/delivery/tool-identities.json) bind the pinned lifter, LLVM reference, SDK, Rust, model tools and Mirrors replay toolchain. Loop model/engine and composition identities are carried in the dump [source binding](artifacts/dump-20261015T051409/source-binding.json).

## Fresh validation

All compilation, models, mutation, replay and original-dump execution ran in remote Windows WSL. Documentation links ran against the complete local checkout; its source-bound result is retained separately because the compact remote source package omits historical linked evidence.

| Gate | Fresh result |
| --- | --- |
| Applicable root checks | Format, 227 default tests, 46 core-only tests, all-feature/all-target Clippy with warnings denied, Rust layout and documentation links pass. Ordinary tests' ignored cases are not implicitly qualified. |
| Focused Rust | Seven loop tests plus the caller-publication regression pass; includes both captured shapes and two independently initialized entrances. |
| Models and oracle | Apalache typechecks; 5 target + 19 composition + 25 loop configurations pass. Independent loop oracle: 29 induction controls and 4 arithmetic controls. |
| Native proof checker | 41 controls, including 3 valid proofs; all pass. |
| Behavioral mutations | 8/8 credited: inventory, source references, entrance inclusion, base preservation, branch provenance, successor coverage, selector freshness and graph/epoch binding. Every credited variant preserves its positive and admits its named negative. |
| Native regression | Four target cases, 17 kernel cases, 9 capture cases, paired composition/admission controls and 5 frame/report cases pass. |
| Legacy compatibility | Actual retained 2026-10-14 combined minidump/frame reports pass semantic replay with original identities; new proof stripping/downgrade controls reject. The supplemental old-capability control rejects v2 before launch. |
| Generated core/stateflow replay | 168 + 162 observations pass; both wrong-digest controls reject with zero observations dispatched. |
| Release and original dump | Qualified release build passes; original-dump scope below passes. |

Exact commands, elapsed times and gate results are in [validation `050857`](artifacts/validation-20261015T050857/complete.json), [native checker controls](artifacts/native-checkers/loop-aware-native-controls-validation-20261015T050857/result.json) and [replay `050942Z`](artifacts/generated-replay-20261015T050942Z/qualification.json). The loop component discharges documented coverage premises; these finite checks do not establish a machine-checked inter-model coupling or universal implementation theorem.

## Original dump acceptance

Dump `dump_03958DA4FCA844A786262A1053`, SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`; thread 23668; frame pair 1 → 0; NP10. The declared premises remain `FrozenCapturedControlData` and Windows normal-call entry. No expected destination becomes a discovery root.

| Dispatch | Complete target set |
| --- | --- |
| `0x00007ff77440da09` | `0x00007ff77440a451`, `0x00007ff77440d9eb`, `0x00007ff77440da0c`, `0x00007ff77440da19` |
| `0x00007ff77440dadd` | `0x00007ff77440a5df`, `0x00007ff77440dabf`, `0x00007ff77440dae0`, `0x00007ff77440daed` |

Both accepted receipts bind the final snapshot/artifact/graph and have 9 region instructions, 10 internal edges, 1 entrance, 4 exits, 9 assertions, 1 initialization corridor and 11 source references. Each table covers selectors 0..9. The new proofs retain fresh loads across iterations; no runtime termination or historical path is inferred.

All nine original tables match 370 entries and 64 distinct destinations; all 51 formerly absent starts were attempted. All nine original sites are complete, and the newly exposed DADD makes 10/10 complete caller target sites. Caller materialization contains 9,590 attempted sites at epoch 609; the resolver's represented graph also includes explicit unattempted Stop endpoints. Callee materialization contains 778 sites at epoch 129.

Both native initializations accept the paired proof report. Completed native requests and full states equal Rust for both frames: caller 9 decoded/9 edges/1,269 reported definitions, callee 768 decoded/895 edges/1,289,259 reported definitions. Probe elapsed time is 202,410 ms. [The final summary](artifacts/dump-20261015T051409/probe-summary.json) and [loop audit](artifacts/dump-20261015T051409/loop-closure-audit.json) retain exact identities, premises, budgets, target receipts and comparisons.

The listing returns zero paths with coverage `unavailable` and `missing-or-ambiguous-active-call-anchor`. This establishes neither an executed path nor the absence of a possible path. Full frame-path acceptance remains open.

## Review correction and retained failures

Initial source `39e902…` passed finite qualification, but full-dump attempt `050210` rejected caller publication with `loop coverage graph changed before publication`; its callee passed parity. The resolver had omitted represented Stop endpoints for non-followed call targets and unattempted slice seeds. Final publication added them and correctly rejected the stale global graph binding.

The prior [fully qualified source capsule](reproduce/source-history/39e902c8a34c7fd6efa4e948788d9a611f07014ceea33c5e4b4aac56c6d7d31d.tar.gz) retains that original failed-dump implementation.

The correction includes those endpoints before proof production, without decoding them or adding roots. The final stale-proof rejection remains unchanged. The regression checks complete-only epoch advancement, exact resolver/receipt/final-request graph identity and unchanged Stop/non-root status. Corrected source `5cd406…` then passed fresh qualification, replay and original-dump acceptance. Earlier format/model/test-harness and source-packaging failures remain historical diagnostics with no pass or mutation credit.

## Evidence and reproduction

[The export manifest](manifest.json), [sealed archive](evidence.tar.gz), [collection inventory](artifacts/delivery/collection.json) and [import verification](import-verification.json) bind retained artifacts and verify lossless compression. Large JSON is gzip; standalone Rust reproduction source is retained as `.rs.txt`. Compiled executables/objects are omitted with identities recorded. The later capability control and historical source capsule are bound separately by [the delivery supplement](delivery-supplement.json); they do not alter the sealed main archive. Raw original 2026-10-14 evidence retains its original bytes and scope.

Use the retained orchestration with the exact source capsule, pinned SDK/runtime/toolchain, original dump identity and explicit budgets in the probe summary. Replay and source-mutant build directories are isolated. The final documentation/link check does not replace any runtime or release qualification.
