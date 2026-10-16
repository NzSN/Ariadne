# Guarded preparation with captured target resolution

## Context and follow-up

**Status.** Guarded composition and its loop-aware extension are implemented and source-bound qualified within the declared captured-table scope, 2026-10-15. Original-dump probe `051409` completes all nine original target sites plus DADD, accepts both inductive loop receipts and matches native/Rust full requests and states. The [composition plan](../../.agents/plans/completed/guarded-target-resolution.md) and [loop plan](../../.agents/plans/completed/loop-aware-target-resolution.md) are complete. Full frame paths remain unavailable.

**Why this document exists.** The [dump03958 table witness](../../evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/README.md) finds captured tables for nine indirect jumps, while the baseline guarded frame preparation did not enable the resolver. Empty target sets contributed nine of the 28 recorded guard coverage barriers.

**What this document establishes.** A composition contract between the existing [target resolver](indirect-target-resolution.md) and [guard admission](justified-branch-pruning-design.md): candidate discovery, separate original/augmented control, a shared epoch, independent proof replay and final request publication.

**Where to go next.** Read the [2026-10-15 qualification](../../evidence/Ariadne/loop-aware-target-resolution/20261015/README.md), the loop contracts and original-dump outcome below, then the completed execution plans. The [2026-10-14 record](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md) retains its earlier partial result. The [frame-path ledger](../../.agents/plans/frame-path-enumeration.md) owns the remaining listing gate.

**What remains unresolved.** Caller guard coverage retains 30 barriers and the initial MOVAPS remains unknown; the callee retains 12 barriers. NP10 frame paths remain unavailable with `missing-or-ambiguous-active-call-anchor`. Regional guard coverage, independent semantic stops, general loop synthesis, heap traversal and executed history remain separate. The first loop rule supplies coverage only for table entries already supported by ordinary path witnesses.

## Scope and captured evidence

The immutable dump is `dump_03958DA4FCA844A786262A1053`, SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, frame pair 1:0, caller entry `0x00007ff7744033a0`.

Baseline guarded candidate discovery contained 4,764 sites. The capture-only inspection obtained nine bounded relative-32 tables in `electron.exe` `.rdata`: 370 entries across 1,480 bytes produce 64 distinct candidate destinations. Thirteen destinations were represented and 51 were absent from that baseline graph. Every destination has a captured 15-byte prefix. These are numeric witnesses under local bounds, not complete target certificates or historical branch outcomes.

Production recognition must use admitted BIL, definition identity and branch constraints. Table addresses and destination lists belong to independent expected evidence; they are not production configuration or hardcoded discovery roots.

## Candidate and final graphs

Keep three explicit layers:

1. **Original source facts:** captured bytes, original typed BIL and independent decoded control. Preserve these unchanged, including original empty/incomplete indirect target sets.
2. **Candidate graph:** original local control, only reviewed pending-guard continuations, and target additions justified by resolver witnesses. Record original control and augmentation separately. Known candidates may remain while their completeness is downgraded.
3. **Final normalized request:** checked target additions plus normal guard selections only when certified. Unknown or refuted guards retain their stops. Validate that final control is an authorized restriction/augmentation of the candidate/source layers; selected effects require their own guard proof.

Target-only replay uses the final request graph. Composition instead replays target witnesses against the sealed candidate graph: an unknown MOVAPS becomes `Stop` in the final request and can remove a continuation used during target discovery. A separate transformation check binds the sealed graph and both proof families to the final normalized request. Candidate discovery never authorizes final normal effects by itself.

## Local target frontiers and coverage

New combined preparation uses target report schema `ariadne.indirect-target-resolution/v3` and profile `captured-local-indirect-targets/v2`. The retained local v2 report/profile local-v1 and rooted target-only v1 have separate legacy validation paths. An ordinary local reverse path may stop at an explicit local frontier when its independently reconstructed target expression is bounded under arbitrary values of the architectural registers at that point. A frontier is a proof cut; it never becomes a discovery root and supplies no observed register value.

The accepted bounded forms remain the reviewed captured pointer load and relative-32 table expression. A relative-32 index must have a finite value set or a checked range within `max_entries`; branch constraints and register-definition identities are reconstructed along the reverse path. Reads and signed-offset arithmetic remain bound to their captured witnesses under `FrozenCapturedControlData`.

Under `ExistingPrefixTree` coverage, completeness requires coverage of every reverse-path prefix, not one bounded path or one receipt per address. At each nonterminal prefix, replay requires a child for every incoming candidate edge, including alternatives that reach the same site through different path contexts. An explicit frontier may terminate that prefix only after replay reconstructs its bounded expression for arbitrary input register values. A bypass, unsupported clobber, missing transfer, exhausted path/frontier budget or unbounded alternative retains an unresolved reason and prevents a complete target certificate. Guard coverage still uses the whole effective candidate graph and its barriers; a local target proof does not establish regional guard coverage.

The finite scalar abstraction preserves eight- and sixteen-bit BIL loads as finite value domains, within the caller's value budget. The retained local v2 algorithm and current v3 prefix-tree strategy also support one bounded unfolding of a reviewed stable simple cycle and an explicit `infeasible` receipt when its exact reconstructed guard predicates have no satisfying assignment in the enumerated domain. Infeasibility requires exact predicate evaluation over every admitted finite assignment; intersecting convex ranges alone is insufficient.

Shared-load correlation across that cycle requires unchanged load addresses and admitted transfers. Original memory writes, the full original pending-store BIL, opaque calls, unknown memory effects and writes to address-input registers prevent that stability claim. A pending store's scalar identity never erases its memory write for this check. The new `InductiveDispatch` strategy may instead discharge whole-dispatch coverage for an admitted local region, while retaining independently replayed path/table witnesses. Unsupported cycles or failed induction proposals retain `cyclic-incoming-state` and explicit residuals. Infeasible receipts add no target and never become roots or evidence of an executed path.

## Independent pending-guard transfer

The resolver needs scalar-bank value flow past a possible normal continuation of the reviewed initial MOVAPS. Derive a narrowly checked scalar-register identity transfer from the exact original store bytes/BIL. This is conditional on following that candidate continuation; it neither assumes alignment nor commits the memory store. Preserve the possible memory write and its effects on unsupported memory/value reasoning. Covered table loads use the explicitly declared `FrozenCapturedControlData` premise.

Generic `If`, exceptions, opaque calls, arbitrary vector forms and unknown writes do not acquire identity transfers. The existing MOVAPS load at `0x00007ff7744035c9` remains a separate unsupported control boundary in this stage.

## One discovery and proof cycle

Use one materialization owner with instruction and resolution worklists. Enable guard source retention and target transfers together. Resolver candidate additions queue local targets as instruction starts; they never become new entry roots. Preserve structural conditional edges and visible call/summary distinctions.

Keep snapshot, activation, caller-supplied roots, slice seeds and supplied premise policy immutable within one query. Advance a shared graph epoch whenever proof-relevant control, completeness, barriers or transfer facts change, including changes that add no new target. A different rooted/premise scope starts a new query/intent, revalidates supplied premises and discards old receipts; it is not an inferred additional root. Invalidate both target completeness and tentative guard receipts. Resolve, discover and recheck until the final candidate graph is stable or a declared budget stops progress. Retain justified candidates with explicit residuals on incomplete coverage; do not manufacture completeness or drop missing-code endpoints.

Replay target evidence against that stable graph before evaluating guard coverage. Guard coverage uses effective receipt-backed control, with original source facts retained. Publish normal guard selections only after final closure and independent replay. Define snapshot/query/activation, graph epoch, source, premise, proof and final-request digests without a hash cycle.

A resolver or guard budget can produce a conservative partial result when its surviving receipts and the complete represented candidate domain can still be sealed. Such a final request retains witnessed targets, marks unresolved target coverage incomplete and keeps unproved guards as stops. A stopped proof is allowed in the combined envelope; it does not authorize normal effects or a positive frame-path result. Capture/discovery limits reached before sealing, an evidence payload that cannot fit, and later transport/output limits can instead reject the query explicitly. No partial result may publish an edge after losing the witness that justified it.

## Product and native validation

The current combined native input profile is `captured-guarded-targets/v2`; the previous v1 profile remains supported through its frozen admission contract. Its envelope carries `composition`, `target_resolution`, `guard_admission`, the final `normalized` request and capture provenance. New composition reports use schema `ariadne.guarded-target-resolution/v2`; it binds the immutable query scope, shared candidate epoch, original controls, sealed candidate request, both proof digests and the final-request digest. Its analysis identity is distinct from the guard-only analysis identity. Existing target-only and guard-only modes remain independently supported. A helper lacking the combined capability rejects the mode explicitly.

Rust and native independently check original BIL/control, captured reads/contributors, arithmetic/index coverage, target augmentation, candidate/final graph relations and selected guard effects. Target transfer rows are bound to the same original bytes/BIL as the guard source rows. Stripping either proof, altering a premise or swapping snapshots/activations must fail. New combined minidump reports use `ariadne-minidump-report-v5`, fault-address explanations use `ariadne.fault-address-explanation/v4`, and frame-path listings use `ariadne.frame-paths/v4`. Retained combined v4/v3/v3 reports select legacy proof replay. These retain both proof scopes, the full normalized request, original capture sources and unresolved reasons in JSON/text/DOT. Full capture-source rows, including contributors and access evidence, are additionally bound to the combined report identity. Earlier ordinary, target-only and guard-only schemas retain their behavior. `input::report::validate_saved_composition(bytes, max_bytes)` replays a saved combined minidump's proof, normalized request and capture-source binding; it does not reanalyze the saved presentation/state rows. `reports::decode_frame_paths_with_limit` supplies a caller-selected finite saved-report bound without changing the default decoder limit.

## API and CLI usage

Use `FileSnapshot::prepare_frame_with_bap_assuming_windows_call_entry_and_target_resolution(&chain, index, entry, &setup, guard_limits, target_limits)`. `setup` is `FramePreparation`, supplying the decoder reference, pinned BAP configuration, preparation options and discovery limits. The entry must equal the recovered frame's validated `function_begin`. The API binds the normal-call assumption `RSP mod 16 = 8` to that physical Windows activation; a later captured RSP does not establish an earlier entry residue. The returned `FilePreparedAnalysis` exposes `composition()`, `target_resolution()` and `guard_admission()`.

Frame CLI composition requires both `--resolve-indirect-targets` and `--assume-windows-call-entry`. The guard and target JSON limit files are independent full typed budget objects; `--bap-core-max-request-bytes` controls native request transport separately. For example:

```sh
ariadne-minidump DUMP --decoder-reference LLVM_MC_HELPER \
  --list-frame-paths 1:0 --path-count-bound 16 --thread-id 23668 \
  --assume-windows-call-entry --resolve-indirect-targets \
  --guard-admission-limits guard-limits.json \
  --target-resolution-limits target-limits.json \
  --analysis-backend bap --bap-core-dir NATIVE_CORE_DIR \
  --bap-core-max-request-bytes 33554432 --format json
```

Output declares both the normal-call entry premise and `FrozenCapturedControlData`. Target coverage is relative to the named captured snapshot; it does not assert historical memory stability or an executed path. Guard, target, discovery, unwind recovery, frame graph/output and native transport budgets remain independent. Guard and target defaults are finite policy choices rather than hard maxima; zero budgets retain their explicit stop/rejection behavior. The existing aggregate frame-binding limits and formatted-output checks still apply. Increasing one budget does not release another contract or establish completeness.

### Bounded BAP child sessions

Materialization now selects the BAP backend's finite aggregate instruction bound from `PrepareLimits.max_starts`. Each lifting child session keeps its existing 8,192-site protocol capacity. The backend finishes and replaces a child before a batch would exceed that capacity, retaining aggregate guard/target evidence across children. Snapshot, decoder target, pinned helper/runtime identity and query budgets stay fixed; rotating a process adds no root, fallback semantics or source exception. A directly constructed `Backend` retains the 8,192-site aggregate default unless its owning query builder selects another bound before preparation starts.

This corrects a first original-dump attempt that grew beyond 8,192 caller starts and hit the former hidden backend query cap despite a declared preparation bound of 16,384. The retained 2026-10-14 probe `121127` represented 9,590 caller sites, and the scoped qualification includes the dedicated 8,193-site boundary control. This correction does not release guard evidence, target work, frame binding, native transport or output limits.

`guard_limits.max_closure_rounds` bounds the shared candidate epoch in combined mode. It is not merely the number of target solver passes: source/control/completeness/barrier/transfer changes also advance that epoch. An earlier probe allowance of 64 was below the callee's recorded epoch 129 and correctly produced a stopped guard check. Final probe `121127` selected 32,768; the caller reached epoch 610 and the callee epoch 129. A larger finite allowance does not imply alignment or complete target coverage.

## Source-review corrections

The implementation review identified and corrected these separate contract seams:

- Conditional-write predicates are expanded to pre-state once. Existing downstream guards cross the instruction's output rewrite; its own already-expanded predicate is then added. This prevents a LOOP-style counter update from being applied twice in the target proof. Rust extraction/production/replay and native replay use the same rule.
- Captured control-data read structure is checked independently of arithmetic. A full admitted scalar/table read requires `RequestedLength`, no conflict sources and contiguous contributor-backed span coverage; a partial prefix cannot justify a full table entry. Byte/word load abstraction remains finite and does not invent captured contents.
- Every target transfer uses the guard source's exact original BIL and bytes. Every effective indirect target set/completeness flag needs the matching target receipt, and retained original controls cannot be rewritten by resealing public hashes. Nonpending final summaries preserve the sealed candidate's control and effects.
- Combined transport negotiates its own profile and includes it in paged native completion decoding. Source-control/opacity and exact stopped shapes remain conservative; the reviewed pending store supplies only the independently justified scalar continuation.
- Native symbolic term equality compares JSON objects by field names and recursively equal values, preserving list order and scalar values. Constructor declaration order is transport formatting rather than term identity. This corrects the retained object-order RED without weakening expression/source digests or predicate checks.
- Saved minidump v4 identities retain the full `semantic_profile` commitment in every format. Frame v3 decoding replays structural recovery from the sealed final request and requires the exact reached node domain, typed local edges and recovery gaps. Individually valid nodes cannot hide an omitted branch, invented edge or erased coverage gap. This replay stops before dataflow/slicing.

These corrections are exercised by the scoped source-bound qualification and retained RED/positive controls; the original-dump result follows below.

## Implementation and scoped validation

The current source implements paired preparation and epoch tracking, local target v3 prefix-tree or inductive receipt replay, candidate/final transformation validation, the v2 combined native profile, versioned consumers and paired-proof/source tamper controls. C0–C4 implementation was delivered on 2026-10-14; loop-closure implementation followed on 2026-10-15 and its fresh runtime/dump qualification is in progress. The C0 model and independent cases are recorded in [`AriadneGuardedTargetResolution.tla`](../../Specs/AriadneGuardedTargetResolution.tla) and the [composition oracle](../../tests/bap/fixtures/composition/oracle.py).

For the 2026-10-14 source snapshot, final checks passed in validation run `120753`, including default/core-only tests and applicable root checks. Scoped model/native controls pass: 19 finite model configurations, the independent oracle's ten infeasible-context controls, twelve native infeasible controls and all 273 actual infeasible receipts. The [qualification record](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md) retains exact gate logs, model/tool/source identities, isolated mutation results and historical RED controls. These checks establish the exercised analysis-level scope; they do not prove all instruction semantics, all incoming loop states or successful full-dump path enumeration.

The corrected native checker accepted and completed both final queries with `request_equal=true` and `full_state_equal=true`. Its recorded identity is `cc9ff8718659af45e3d86ba0949915615f8bdb64822638597522af63dba0c0f8`. The earlier order-sensitive comparison failure and probe `115408` remain historical diagnostics; final positive probe `121127` elapsed 192,204 ms. Native parity closes the exercised result-comparison gate, not the ninth complete target certificate.

The probe used 4,096 as a diagnostic decoded-site threshold: after Rust completed, it used that threshold to decide whether to request native completion. It is not a native action limit. The native engine's one-million-action ceiling, eight-MiB response bound and paged completion contracts remain in force. A larger finite transfer-evaluation allowance, `max_elapsed_ms=120000` and epoch allowance 32,768 distinguish resource exhaustion from remaining semantic barriers. Actual JSON controls are retained with the result; global defaults are unchanged.

## Final original-dump probe 121127

The caller's sealed candidate graph contains 9,590 sites at shared epoch 610. All nine original dispatch candidate sets match the independent numeric witness exactly: 370 table entries yield 64 distinct destinations, and all 51 starts absent from the original graph were attempted. This meets the original candidate/discovery gate; it does not imply complete incoming-state coverage for every dispatch.

Eight original dispatches have complete target certificates. At `0x00007ff77440da09`, all four known destinations are retained but completeness remains false with `cyclic-incoming-state`. Newly discovered dispatch `0x00007ff77440dadd` also retains four known destinations and remains incomplete. The new normal loop advances RCX, preventing the implemented stable-load/cycle correlation rule from closing these incoming contexts.

The caller retains 32 guard-coverage barriers. Its initial MOVAPS is `Unknown` with residual `candidate-coverage-incomplete`, so final recovery keeps the stopped guard. Rust and native completed both final queries with exact normalized-request and full-state equality. Candidate-site count and final decoded count describe different graph layers:

| Query | Candidate sites | Epoch | Final decoded | Final edges | Reported definition count |
| --- | ---: | ---: | ---: | ---: | ---: |
| Caller | 9,590 | 610 | 9 | 9 | 1,269 |
| Callee | 778 | 129 | 768 | 895 | 1,289,259 |

The frame question `1:0`, `NP=10` returned an unavailable listing with zero paths and reason `missing-or-ambiguous-active-call-anchor`. This is a final-request recovery outcome, not proof that execution took no path. The candidate target successes do not authorize a normal MOVAPS continuation or reconstruct the missing active call anchor.

The [delivery record](../../evidence/Ariadne/guarded-target-resolution/20261014/README.md) retains the declared scope and reproduction requirements; its source/tool-bound artifact archive and 330-observation replay supplement are sealed. It records probe inputs, source/tool/dump identities, all nine comparisons, discovered dispatches, known/incomplete targets, remaining barriers and final native status. Source-bound records, rather than a table match or a successful initialization alone, support reuse of this scoped result.

## Proposed stable-base invariant follow-up

The loop-aware extension was designed, implemented and source-bound qualified on 2026-10-15 under its [L0–L6 plan](../../.agents/plans/completed/loop-aware-target-resolution.md). The [new qualification](../../evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) closes the parent ninth C5 clause through fresh Rust/native induction and original-dump evidence. This section owns the implemented contract. The 2026-10-14 result retains its original scope and identities.

### Decision and first support scope

The existing target resolver now has a private loop-closure module, with one discovery coordinator, one candidate epoch and the existing pointer/table evaluation. A loop closure is an additional coverage-proof strategy, not another competing target resolver. No resolver registry, general SMT solver, new runtime dependency or new CLI switch is required for this first scope.

The first rule supports bounded, source-checked local dispatch regions with an already witnessed captured relative-32 table. It extends coverage only: every required table entry must already have an independently replayable ordinary path witness, and the derived target set must exactly match those retained candidates. It publishes no loop-only target or new table-read witness. Prove a constant table-base bank across every region entrance and internal edge, permit changing object pointers and fresh selector loads, and prove a finite unsigned selector domain at each indexed table load. Rooted target-only v1 remains unchanged in this stage; the new proof is used by local combined preparation. General nested-loop synthesis, arbitrary heap traversal, memory alias proofs, regional MOVAPS admission and successful frame-path enumeration remain separate work.

The analysis must terminate within its budgets. It need not prove that the program's loop terminates: an inductive invariant covers arbitrary finite traversals even when an infinite runtime traversal is possible.

### Dump-specific feasibility inspection

A read-only inspection on 2026-10-15 used the final caller [captured/candidate report](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/minidump-rust.json.gz) and [target receipts](../../evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127/frame-1/target-report.json). This is structural evidence, not a new closure proof or dump execution.

| Property | Original dispatch | Newly exposed dispatch |
| --- | --- | --- |
| Dispatch VA | `0x00007ff77440da09` | `0x00007ff77440dadd` |
| Captured table base | `0x00007ff77ba909a8` | `0x00007ff77ba909d0` |
| Base initialization | LEA at `0x00007ff77440d9e2`, bytes `488d15bf2f6807` | LEA at `0x00007ff77440dab6`, bytes `488d15132f6807` |
| Represented region entrance | `0x00007ff77440d9e9 → 0x00007ff77440d9f7` | `0x00007ff77440dabd → 0x00007ff77440dacb` |
| Pointer-changing backedge | Table index 3 → `0x00007ff77440d9eb`, `mov rcx,[rcx]` | Table index 3 → `0x00007ff77440dabf`, `mov rcx,[rcx]` |
| Selector / compare / unsigned branch | `0x00007ff77440d9f7` / `0x00007ff77440d9fc` / `0x00007ff77440da00` | `0x00007ff77440dacb` / `0x00007ff77440dad0` / `0x00007ff77440dad4` |
| Inspected local region | 9 instructions, 10 internal edges, 1 entrance, 4 exits | 9 instructions, 10 internal edges, 1 entrance, 4 exits |
| Local base clobbers / calls / memory writes | 0 / 0 / 0 | 0 / 0 / 0 |
| Maximal candidate SCC | 4,694 nodes; 37 entrances; 631 sites may-define RDX; 246 calls | 411 nodes; 1 entrance; 53 sites may-define RDX; 18 calls |

The maximal SCC is unsuitable for the proposed constant-base invariant. The small phase region is the relevant proof domain: every represented entrance passes a base-reset LEA followed by an unconditional jump. Region construction must discover this shape from controls, transfers and definition boundaries; the addresses above are acceptance fixtures, never production dispatch conditions. The checker must independently enumerate every actual entrance and exit, so a producer cannot hide a clobber by shrinking its claimed region.

In that retained baseline, the caller candidate epoch is 610 and `composition.candidate_sha256` is `50b54d681fe01f9488da4cf2c90948afe52cb2ab13dad2e960bad55648122a3f`. The original dump SHA-256 remains `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`. Do not substitute the guard graph digest for this candidate-request identity. Exact region members, edges, original BIL, bytes, contributors and initialization chains are retained in the [source-bound loop fixtures](../../tests/bap/fixtures/loop-closure/dump-provenance.json). Those fixtures are acceptance evidence, not production dispatch configuration.

### Private module and invocation

The private [Rust loop module](../../src/bap/target_resolution/loop_closure.rs) owns bounded region discovery, finite invariant proposal and loop-receipt validation. Keep ordinary path substitution, existing target recognition and discovery ownership in their current modules. The native checker independently implements the same receipt contract from original source evidence.

```text
propose(snapshot, artifact, candidate_graph, original_transfers,
        dispatch_site, retained_table_evidence, shared_budget)
  -> NotApplicable
   | Candidate { coverage_receipt }
   | Partial { reason }
```

Attempt this strategy for eligible local cyclic table contexts before finalizing `cyclic-incoming-state`. Preserve existing bounded-frontier, infeasible and stable-simple-cycle paths. A failed proposal leaves the original conservative result; a successful proposal is still candidate evidence until independent validation accepts it. A proposal requiring a missing path/table witness is declined; `loop-closure-requires-retained-table-witness` identifies a failed retained-entry obligation. The loop proof never supplies the missing target itself. No instruction address, expected target list or concrete crash-time register may select or initialize the strategy.

For the first version, a loop receipt proves **whole-dispatch incoming coverage** and attaches at that dispatch's root coverage obligation. It does not claim to close an arbitrary accumulated reverse-prefix context. Existing path receipts remain individually replayed target/infeasibility evidence. This avoids equating different reverse contexts or weakening the current repeated-path checks.

### Inductive proof obligations

Let `R` be a proposed finite local region, `G` the bound candidate graph and `I[n]` an assertion about the relevant scalar state immediately before region instruction `n`.

```text
Entrance:     every represented edge u outside R → v inside R
              has source-replayed initialization establishing I[v].

Preservation: original normal-path BIL at n, together with its edge predicate,
              maps every state admitted by I[n] into I[successor]
              for every internal edge.

Dispatch:     the assertion at the table-load point bounds its selector;
              captured reads and modular signed-offset arithmetic derive
              every possible target at the dispatch.

Coverage:     all region entrances, internal edges, exits, relevant roots,
              and all derived table successors are represented and checked.
```

An entrance proof may begin at a source-checked assignment that resets the base for arbitrary prior scalar values. Replay the complete short corridor from that assignment to the entrance. Any edge entering after the reset, any root inside the region or any alternate initialization needs its own proof; it cannot be silently ignored. First-scope unsupported entrances return partial.

Use a small width-aware private abstract domain: `Top`, constant, finite unsigned interval and finite word set. This is a resolver-proof implementation, separate from the supplied abstract-stateflow API. Proposal may iterate assertions within budgets; replay checks asserted inclusions directly and does not rerun or trust the producer's convergence decisions.

For each region, the intended point-specific assertions are:

1. RDX equals the captured base at all relevant points.
2. Each unknown selector-byte load produces a fresh arbitrary value in `0..255`; MOVZX preserves that unsigned interpretation.
3. The source-replayed CMP/JA chain establishes `selector ≤ 9` on the edge to the indexed load. Preserve compare/flag definition identity; wrong polarity, signed comparisons or intervening flag/selector writes cannot establish this bound.
4. The signed table load changes R8 from selector to offset, and ADD changes it to a member of the derived target set. The `0..9` assertion applies before the table load, not to R8 at the jump.

Fresh means an independent abstract value per transition. Even the range-check loop may be overapproximated with fresh loads; the new proof never needs two iterations' selector values to agree. Existing stronger stable-load contradiction proofs remain valid under their own unchanged premises.

The first scope rejects original stores, hidden pending-store BIL, opaque calls, unknown memory writes, unsupported relevant effects and unproved base clobbers inside the region or its initialization corridors. Changing RCX and ordinary pointer loads are permitted when the required invariant remains established. Unrelated scalar values may become `Top`. This rule introduces no normal-effect admission, LLVM effect fallback, concrete heap reads or historical memory premise.

### Avoiding circular target and region proofs

An incomplete target set or `Instruction.complete` flag cannot establish a loop's successor coverage. The ordinary path resolver first supplies captured table-entry witnesses. The loop checker independently reconstructs the table form and finite selector domain from original transfers/assertions, validates every required captured slot and derives the full successor set. Every entry must match a retained path witness, and the derived destinations must equal both the row's witnessed targets and the current candidate dispatch targets. A mismatch declines induction. Ordinary discovery remains responsible for any new destination; region boundaries and assertions must then be recomputed before admitting coverage on a stable candidate epoch.

A missing destination may remain an explicit recovery endpoint; it cannot be erased from the target set. Unsupported control inside a claimed proof region prevents closure. A new graph entrance, changed source transfer, target-completeness change or changed boundary invalidates the affected receipt. One coordinator owns target union, proof invalidation and guard re-evaluation; no independent loop cache may outlive its bound epoch/scope.

In particular, the first accepted proposal can change `Instruction.complete` without adding a destination. That changes the candidate fingerprint and advances the epoch. Recompute and independently replay the summary on the resulting candidate graph before sealing; copying a receipt and replacing its epoch field is not revalidation.

### Receipt and coverage representation

The new local report retains existing path witnesses and adds a tagged coverage alternative for each row:

```text
CoverageEvidence =
    ExistingPrefixTree { path_receipt_refs }
  | InductiveDispatch { loop_closure_receipt }
```

`ExistingPrefixTree` preserves the existing exact incoming-prefix rules. `InductiveDispatch` independently covers every incoming state at one site through the entrance and preservation obligations above; it is not an `infeasible` receipt or an arbitrary-register local frontier. Retained path witnesses are individually validated even when the row uses inductive coverage. Every required table entry still needs its ordinary path witness, whose arithmetic and substitutions are checked independently from the coverage choice. Induction cannot supply missing target or captured-read evidence. No reason is removed merely because a new strategy returned nonempty targets.

A strict `LoopClosureReceipt` carries its rule version, dispatch site, ordered region VAs, complete typed boundary/internal edge inventories, initialization corridors, point assertions and guard-definition references, captured table/domain/entry references, and original transfer/byte identities. The receipt directly binds the snapshot, artifact, model/engine ruleset and complete candidate-graph digest. The surrounding composition seal additionally binds that exact receipt family to the immutable query, activation, premises and shared candidate epoch. It contains no trusted “proof succeeded” Boolean. Rust and native reconstruct the graph/effects, check all inclusions and table arithmetic, and derive acceptance themselves.

Replay preserves the old prohibition on general cycles in ordinary path receipts. The new induction rule is the sole additional way to establish cyclic dispatch coverage. If any remaining required context or read is unresolved, the row stays partial with its known candidates and explicit reasons.

### Version and compatibility decision

Current producers and readers implement the following version split. Fresh release/dump qualification remains in progress:

| Surface | Retained 2026-10-14 identity | Current loop-capable identity |
| --- | --- | --- |
| Local target report / profile | `ariadne.indirect-target-resolution/v2` / `captured-local-indirect-targets/v1` | `ariadne.indirect-target-resolution/v3` / `captured-local-indirect-targets/v2` |
| Combined native input | `captured-guarded-targets/v1` | `captured-guarded-targets/v2` |
| Composition report | `ariadne.guarded-target-resolution/v1` | `ariadne.guarded-target-resolution/v2` |
| Combined minidump / explanation / frame-path reports | v4 / v3 / v3 | v5 / v4 / v4 |

New combined queries use the new identities consistently, including queries where the loop strategy declines. Keep rooted v1, target-only and guard-only behavior and legacy saved-report decoding explicitly supported. Old helpers reject the new combined profile before analysis; never silently strip a loop proof or fall back to weaker admission. New readers dispatch by version and preserve exact old/new semantics. Model/engine hashes and profile commitments include the new closure checker; receipt binding must not hash its own enclosing report into itself.

Legacy compatibility includes **semantic replay of retained reports**, not parsing alone. Version dispatch selects dedicated legacy Rust/native replay and the exact pre-extension sources preserved as [hash-verified fixtures](../../tests/bap/fixtures/loop-closure/legacy-manifest.json). A legacy proof keeps its historical model/checker identity instead of being rebound to the new helper or current source files. Its admitted model/checker pair is `e142a6fd22d78044c444c26211b7c659a56fedb5f9e555aa20e3aa1be23e8b10` / `c36c8876810e35ed10b7e366e650d7854958b0ad7b07d33084039d39b68e9580`. Native build metadata advertises version-indexed supported proof identities separately from the current helper's own build identity. Retained receipt identities remain unchanged; legacy identities cannot authorize new loop fields or weaker replay. The qualification gate replays actual retained 2026-10-14 combined minidump and frame reports after the new build, alongside profile/hash downgrade and proof-stripping negatives.

Legacy v1/v2 target rows must omit `coverage` entirely. Explicit JSON `null`, an unknown coverage tag or a loop variant under a legacy identity is rejected. New local v3 rows require a nonnull `ExistingPrefixTree` or `InductiveDispatch` variant, including queries where induction declines; the existing path-cycle prohibition remains intact.

The loop engine identity hashes both the parent `src/bap/target_resolution.rs` and private loop-checker source under the tagged `ariadne.loop-target-engine/v1` aggregate. The v2 composition checker identity binds its own source and that loop-engine aggregate. Its model identity binds both the composition and loop TLA+ files under `ariadne.guarded-target-model/v2`. The native build computes the same identities. Changes to parent extraction, typed coverage decoding or the private checker therefore invalidate new proof reuse. New local graph digests also include instruction completeness, while legacy digests retain their original encoding.

Keep the current API and CLI opt-ins and the existing target-limit JSON fields. Charge graph scans, assertion transfer/inclusion checks, domain operations and validation work to finite counters derived from `max_steps`, `max_values`, `max_entries`, `max_read_bytes`, `max_evidence_bytes`, `max_rounds` and `max_elapsed_ms`. Loop computation has no uncapped nested work or changed global defaults. Rooted and disabled modes gain no new semantics. Limits still allow explicit zero-work outcomes. Producer and checker use separately charged finite work; report decoding and transport retain their own byte bounds. The accepted budget fields and global defaults are unchanged.

### Qualification and acceptance boundary

The [L0–L6 plan](../../.agents/plans/completed/loop-aware-target-resolution.md) orders the authoritative loop-closure component and independent oracle before runtime changes, then Rust production/replay, native replay, integration/codec checks, source-isolated mutation/replay and the original dump retry. The [component interface](../../Specs/README.md#loop-target-closure-component-interface) states the assurance boundary: existing target/composition models consume accepted coverage as a premise. There is no mechanically checked inter-model coupling theorem, refinement mapping or proof that the Rust/native implementation universally refines the models. All Cargo, native, model and replay work runs in remote `windows-dev` WSL. Local checks for this design change are documentation/navigation and whitespace only.

The original-dump gate requires both DA09 and DADD to retain their four witnessed targets and become complete through independently accepted induction receipts, with all other original table candidates preserved and native/Rust full-state parity. Inventory every remaining coverage barrier and path outcome. Closing these two sites does not qualify the maximal SCCs, eliminate other semantic stops, prove MOVAPS alignment or guarantee an active call anchor or available frame paths.

### Dated loop delivery and publication correction — 2026-10-15

[Fresh qualification](../../evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) binds source archive `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee` (877 files), 227 default/46 core-only tests, seven focused loop tests plus the publication regression, 41 native controls, eight behavioral mutants, 49 finite model configurations and 330 generated replay observations. Actual retained legacy minidump/frame reports replay under their frozen identities. All heavy work ran remotely.

Probe `051409` on the byte-identical dump accepts DA09 and DADD as complete, each with four targets and a nine-instruction inductive region. All nine original tables match 370 entries and 64 destinations, all 51 missing starts were attempted, and all nine original sites retain complete coverage; DADD brings the caller to 10/10 complete target sites. Native and Rust full requests/states match for both frames. Caller materialization remains 9,590 sites at epoch 609; the callee has 778 sites at epoch 129.

An earlier full-dump attempt `050210` exposed a publication mismatch after finite fixtures had passed. The resolver omitted represented Stop endpoints for non-followed call targets and unattempted seeds, while final request construction included them. The corrected coordinator totalizes that same represented graph before proof production. The endpoints remain unattempted and do not become roots. The final stale-proof rejection stays intact; a regression checks exact resolver/receipt/final graph identity and complete-only epoch advancement.

The caller still has 30 guard barriers and an unknown initial MOVAPS; the callee has 12 barriers. Final core states are caller 9 decoded/9 edges/1,269 reported definitions and callee 768 decoded/895 edges/1,289,259 reported definitions. NP10 listing is unavailable with zero returned paths and `missing-or-ambiguous-active-call-anchor`. Closing target coverage does not establish historical execution or full frame-path acceptance. The original 2026-10-14 and failed `050210` records remain historical evidence.

## Acceptance boundary

The finite initial target oracle is the captured nine-table witness. Reconcile each table entry/destination and attempt all 51 previously absent starts, or produce an explicit checked index-exclusion rationale. Every site reports its candidates, complete/incomplete status, premises and remaining gaps. A narrower set requires a validated constraint, not silent filtering.

Full incoming-state coverage remains required for `complete=true`. Source/table bytes alone are insufficient. The initial nine barriers must acquire checked resolution outcomes; the 19 other stops and newly discovered obligations must remain visible. The original MOVAPS can remain unknown under the current global coverage policy.

Analysis-level TLA+ models and independent cases precede runtime changes. Fresh paired Rust/native tests, replay, targeted mutations and the original dump run qualify this composition separately from historical records. All Cargo/native/model compilation runs on remote `windows-dev` WSL; local work is limited to source/document checks. The retired ISA-step track is not revived.
