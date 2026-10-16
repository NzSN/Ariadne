# Close caller semantic-coverage barriers

## Context and follow-up

**Status.** S0–S5 implementation and scoped qualification pass, 2026-10-15. Original-dump caller coverage closes, but the full caller run hits both core action budgets and completed caller parity remains unavailable. Final-helper admission refresh `075602` passes without repeating caller completion. S6 remains partial; keep this plan active. The [canonical design](../../docs/Ariadne/caller-semantic-coverage-design.md) owns the contracts and scope.

**Why this document exists.** [Original-dump probe `051409`](../../evidence/Ariadne/loop-aware-target-resolution/20261015/artifacts/dump-20261015T051409/probe-summary.json) closes both cyclic jump certificates but leaves 30 caller barriers. Remote four-shape probe `060803` reproduces each instruction-class failure through the actual public preparation path.

**What this document establishes.** Execution order, ownership, independent negative controls and remote gates for item 2 of the blocker inventory.

**Where to go next.** Read the [qualification record](../../evidence/Ariadne/caller-semantic-coverage/20261015/README.md), dated ledger below and canonical design for passed versus incomplete gates. The [guard contract](../../docs/Ariadne/justified-branch-pruning-design.md), [BAP input interface](../../docs/Ariadne/file-reader-design.md#public-interface) and [formal guide](../../Specs/README.md) define the supporting contracts.

**What remains unresolved.** Completed caller native/Rust parity is unmet after the selected one-million-action budgets. Initial MOVAPS is aligned under recorded premises, while the later load stays unknown; the callee has two indirect barriers. Frame paths remain unavailable. Final-helper admission refresh does not repeat full caller completion. Normal-flow closure does not establish handler behavior, actual execution or whole-machine completeness.

## Stages and ownership

Workers are not alone. Preserve unrelated edits and frozen evidence; coordinate shared types and identities before touching caller-owned files. Stage dependencies are evidence gates, not additional approval questions. All compilation, native helpers, models, replay, mutations and dump execution run in remote Windows WSL.

| Stage | Owner and files | Dependency | Acceptance |
| --- | --- | --- | --- |
| S0 — diagnose and freeze | Root/evidence owner; `tests/bap/fixtures/caller-coverage/`, canonical design, this plan | Current qualified baseline | Four actual RED cases; exact BAP/LLVM span diagnosis; original source/model/guard/composition identities frozen. |
| S1 — model and oracle | Model owner; `Specs/AriadnePredicateAdmission.tla`, new configs, checker and independent fixtures | S0 | Authority distinguishes normal terminals, unknown Stops and load/store guards; positive, invalid-evidence and stale-epoch finite controls pass before runtime acceptance. |
| S2 — Rust recognition and proof | Rust owner; private terminal module, `src/bap/guard_admission.rs`, `src/bap/prepare.rs`, required module exports, `native/llvm_mc/decode.cpp`, focused tests | S1 contract | Narrow terminal rules; conservative effects; exact MOVAPS load; legacy guard policy; replay rejects malformed bytes/AST/span/scope. Default unguarded semantics preserved. |
| S3 — native admission | Native owner; `native/bap-core/` terminal module, guard/capture/composition/main/build integration and native controls | S1 + frozen S2 wire | Independent source replay, versioned capability/legacy policies and strict new/current identities; no unsupported downgrade. |
| S4 — composition and consumers | Integration owner; `src/input/materialize.rs`, `src/bap/composition.rs`, core protocol/session/adapter and input/investigation/report consumers, integration tests | S2 + S3 | One coordinator; exact full graph binding including Stop endpoints; qualified terminals excluded from barriers only after validation; complete source/proof retention; actual old reports replay unchanged. |
| S5 — qualify | Root + independent reviewers; isolated remote source/helper/replay/mutation outputs and source/tool manifests | S4 | Applicable root tests, focused/native controls, model/oracle, behavioral mutations and 330 generated regression observations pass on exact sources. |
| S6 — original dump and delivery | Root/evidence owner; byte-identical frame-pair retry, caller barrier audit, docs/checkpoints | S5 | Original 30 barriers handled under explicit normal-flow scope; all original target facts preserved; both full native/Rust requests and states match; remaining guards/path outcomes reported honestly. |

## Dated execution ledger, 2026-10-15

| Stage | Current result and limit |
| --- | --- |
| S0 | Complete: actual four-shape RED probe `060803`, raw helper/extent diagnosis and frozen guard/composition/capture contracts. Historical errors and RED evidence retain their original identities. |
| S1 | Complete: predicate v2 typecheck and 58 finite safety/termination configurations; independent oracle 71 cases, 12,752 complete UD1 extents and 8,944 truncation controls. Final qualification verifies the unchanged model/oracle source hashes. No universal ISA/refinement claim follows. |
| S2 | Implemented: narrow control-only terminals, exact MOVAPS load/store guards, no premature load/vector effects and conservative unknown outcomes. Default unguarded rules and original target/loop source contracts remain separate. |
| S3 | Implemented and qualified: independent native source/wire replay; 88 direct and 24 protocol controls, nine behavioral caller mutants. Two frozen legacy-capture controls and a dependency-reversion mutant pass. |
| S4 | Implemented: shared graph/epoch scope, checked terminal barrier exclusions and strict current/legacy report retention. Review corrections cover Rust/native completeness parity, stripped legacy-frame proof rejection and the frozen `Legacy_capture` dependency. |
| S5 | Passed: `qualification-20261015T075232Z-139849` on final source `c35459a19b1e2f5f139730bea6c119cfceff603207254b52d42effac68654a5f` (937 files), helper `d39df81c64c1fd832b88dd48652572234422d8d8840d277cbb83fb88e783e725`. Root tests 242 default/46 core-only, format/Clippy/release, nine capture tests, native kernels/protocol/frame/composition/tools, 330 generated observations, three opaque controls and retained report replay pass within their declared scope. |
| S6 | Partial: dump `073143` removes all 30 caller barriers and preserves targets/roots/premises. Callee completes with full parity. Caller dataflow and native completion exhaust action budgets, so both-frame completed-state equality is not established. Final-helper refresh `075602` passes exact request/three-proof equality for both frames, caller structural recovery/admission and callee full parity; caller completion is explicitly unattempted in that refresh. |

### Original-dump observations

Probe `073143` is bound to source archive `4a81b5c6b0439bcef53ab98c9c309c59ed0c4be16d522e5c2c691be653fe4f29` (935 files), distinct from the final qualification archive above. It validates 29 terminal receipts (27 INT3, UD2 and UD1), removes all 30 original caller coverage barriers with no replacement, and retains the exact UD1 consumed-span disagreement. All nine original table sets, 64 targets, 51 attempted formerly missing starts and both complete four-target loop receipts remain; roots/premises are unchanged.

The initial MOVAPS at `0x00007ff7744033b3` is aligned under the recorded normal-flow/entry premises. The later load at `0x00007ff7744035c9` remains unknown and stops normal preparation. Caller recovery attempts 9,600 starts and decodes 9,589, producing 11,321 edges; that load is its only `DecodeFailed` obligation. Rust stops in dataflow at 1,000,000 actions after 554,409 ms with 105,570,377 definition links. Native accepts the new proof input, then exhausts its completion action budget after 374,754 ms. Neither is a completed caller analysis.

The callee completes with 778 decoded sites, 895 edges, 1,304,602 definitions and exact native/Rust request/full-state equality. It retains indirect barriers at `0x00007ff77443da0e` and `0x00007ff77443e200`. NP10 frame listing is unavailable with zero paths and `missing-frame-query`, because the caller has no completed bound query. This is not a no-path result.

Final-helper refresh `075602` passes on the unchanged final 937-file source. Both normalized requests and all three guard/target/composition proof reports exactly match the original observation; all 30 caller barriers stay removed. Caller structural recovery completes with 9,589 decoded sites/11,321 edges, final helper `d39df81c64c1fd832b88dd48652572234422d8d8840d277cbb83fb88e783e725` accepts its proof input, and callee full parity passes. It records `caller_completion_attempted=false` and `full_parity_claimed=false`. Current Rust/native analysis routes are unchanged by the final legacy-dependency/test update, but the helper identity differs. Retain the runs separately; admission/structural equality does not establish completed caller parity or full S6 acceptance.

## Required controls

- Actual INT3, UD2, UD1 and MOVAPS-load captured shapes; all 27 original INT3 sites; retain the exact UD1 3-byte versus 5-byte disagreement.
- Empty BIL on ordinary opcodes, fake terminal NOP/CLC, conditional exception with normal continuation, extra effects, wrong exception number, unknown rule, missing scope/exception-exit annotation, malformed/truncated bytes, unsupported prefixes and mismatched spans.
- UD1 ModR/M/SIB/displacement boundaries; no generic decoder-disagreement bypass and no fabricated BAP effects.
- MOVAPS load/store destination/direction, high-half preservation, width, address and predicate-polarity negatives; unknown/misaligned keeps a stop; no load/vector effect before proved alignment.
- Every terminal has no normal successors and no must-defs; unsupported Stops remain barriers. Handler resumption is outside the stated scope and never imported as a normal incoming fact.
- Stale candidate epochs, completeness-only changes, late roots/edges, source stripping and profile/hash downgrade.
- Actual guard-only legacy report replay; actual combined v1 and v2 minidump/frame reports; old-helper capability rejection before processing a new profile.
- At least one behavioral mutation per critical rule: bytes/extent binding, terminal-source match, no-successor/scope check, guarded-load shape, proof-gated effect selection and legacy-version policy. Compile failures and timeouts earn no credit.

## Remote qualification

Run the affected cases plus root format/default/core-only/Clippy/layout checks; native capture/composition/frame/report suites; predicate, composition, target and loop models; independent oracle; isolated targeted mutations; generated core/stateflow replay and original dump. Do not build locally. Local document and whitespace checks are permitted.

Use task-private source and build directories. Freeze and verify source files, helper/runtime/decoder identities, exact budgets, original dump SHA, command lines and output. Capture-only precedence, semantic VAs, existing entry roots and explicit uncertainty remain invariants. Preserve earlier failed driver attempts separately from actual RED/runtime results.

The historical fast feedback command below diagnoses the qualified baseline and retained source-bound fixtures; it is not the final qualification command:

```sh
r_windev ':; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -u root -- bash /mnt/d/ariadne-caller-barriers-20261015-run-feedback.sh'
```

The confirmed RED run is `/loop-work/evidence/caller-barriers-20261015T060803`: exit 1, feedback present, four selected barriers, all 877 source files unchanged. Later implementation, qualification and dump runs have separately frozen capsules and helper identities; the baseline RED is preserved.

## Completion boundary

The semantic-coverage observation is met, but S6 additionally requires completed caller native/Rust state equality, which is still unmet. Do not weaken that criterion, substitute native initialization for completion or archive the plan. Complete the caller within declared budgets and rerun the required comparisons, then report the unknown later load, callee barriers and path outcome separately. No exception-handler, executed-history or whole-machine coverage claim follows. No commit, push or deployment is included unless requested.
