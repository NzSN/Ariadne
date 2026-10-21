# Structural frame report before dataflow: Stage 5.1

## Context and follow-up

**Status.** SF0–SF6 are complete within the [2026-10-16 qualified scope](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/20261016/README.md).
The corrected source capsule is `8266a844e60e3afbcaa8f0bba557899a0466e18940d8fa881630377cf78bb37c`
(1,093 files), based on `4811d7de6f2b86319135a5f0a1a18c397a4cd4c2`. Runtime, model,
oracle, compiled mutation, compatibility, original-dump and saved-replay evidence
have separate source/tool receipts. The original planning review at
`6192dee19a5b2f133177a21187952e28d603c2d9` remains historical.

**Why this document exists.** The [canonical structural-report design](../../docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
addresses a concrete coupling: the [retained caller run](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/caller-semantic-coverage/20261015/README.md)
recovered control flow but exhausted dataflow before the existing frame binder
could consume it. Stage 5.1 delivers a separate structural result.

**What this document establishes.** Implementation order, file ownership,
interface decisions, finite policies, independent controls and remote acceptance
for this stage. The investigation design owns the resulting API and contracts.

**Where to go next.** Read the canonical section, [core implementation guide](../../docs/implementation.md),
[formal-model guide](../../Specs/README.md), [input interface](../../docs/Ariadne/file-reader-design.md#public-interface)
and [BAP usage](../../docs/Ariadne/bap-analysis-core-design.md#backend-usage).
The [existing frame-path plan](frame-path-enumeration.md) and
[caller-coverage S6 ledger](caller-semantic-coverage.md) keep their separate gates.
The [dated qualification record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/20261016/README.md)
binds the exercised sources, finite controls, final dump and saved replay to
their declared qualification scope.

The [complete section-5 program](frame-question-investigation.md) is the
successor integration: it reuses this structural source without changing SF
acceptance.

**What remains unresolved.** No required Stage 5.1 work remains within the
recorded Windows AMD64 physical-frame/E8-call profile. Preparation checkpoints,
SCC summaries, path enumeration, new target/loop rules, backward values and
writer refinement remain outside this stage. The caller unknown guarded load,
two callee indirect target boundaries and opaque call context remain explicit.
Caller-coverage S6, frame-path F4, full caller state parity and executed history
retain their separate unmet gates.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Frozen delivery contract

| Decision | Stage 5.1 contract |
| --- | --- |
| Product | A distinct privately constructed structural binding and `ariadne.frame-structure/v1` report family. Public bound types remain privately constructed; raw serialized transport is private. |
| Core result | A standard-library-only `RecoveryResult`, produced by bounded deterministic recovery. It implements no `AnalysisView` and cannot be supplied as a completed investigation. |
| Input | Successful `FilePreparedAnalysis`, exact final normalized request, original capture evidence, unchanged roots and verified guard/target/composition bindings. |
| Capture profile | Existing finite Windows AMD64 physical-frame/unwind and E8 direct-call profile. Core recovery stays platform-neutral; no new Linux/JIT/tail-call/handler-frame support is part of v1. |
| Producer | `rust-recovery/v1`, using production BAP semantics and the LLVM decode/control reference. This does not claim native-core execution or qualification. |
| Stop | Run Visit actions while pending work and budget remain. Stop before `FinishRecovery`, including when pending becomes empty. No dataflow/slice action is executed. |
| Meaning | Recovery `drained` or `work_stopped` is separate from semantic/control gaps. Neither is `Done`, `ScopeClosed`, an executed path or a writer exclusion. |
| CLI | Opt-in `--frame-structure N:M` and `--frame-structure-limits FILE`, independent of `--list-frame-paths`; no NP or path enumeration. Preserve the existing route by default. |
| Saved evidence | V1 is self-contained and replayable under host policy. Deduplicate immutable payloads with checked references; a hash-only reference cannot substitute for missing evidence. |
| Compatibility | Existing `BoundInvestigation`, frame-path codecs/limits, native-default full analysis, roots, effects and evidence identities retain their contracts. |

A missing final guard decision remains a Stop/frontier. Candidate continuations
are not admitted merely because dataflow is skipped. Preserve typed call facts
while local recovery follows summary edges. New frame links use the existing
captured E8/continuation/child-entry checks against reached caller sites.

## Execution waves and ownership

SF0–SF6 satisfy their scoped exit gates. Dependencies below record the
qualification order, not additional permission questions. Workers are not alone: preserve unrelated edits and do not
revert other workers. A stage owns its stated files; coordinate shared exports
through that stage's integration owner. Only disjoint model/oracle work or
independent reviews should run in parallel until their prerequisite interfaces
are frozen.

| Wave / stage | Owner and file responsibility | Depends on | Exit evidence |
| --- | --- | --- | --- |
| W0 / SF0: authority and oracle | Contract/model owner: owning design, this plan, `Specs/AriadneFrameStructure.tla`, finite configurations/checker, independent oracle and fixtures under `tests/`. | Source/corpus inventory | Frozen schema/status/limit/CLI meanings; independent expectations and authoritative recovery-prefix contract before runtime acceptance. |
| W1 / SF1: core recovery result | Core owner: `src/recovery.rs`, `src/lib.rs`, narrowly necessary engine accessors, `tests/`; no serde/hash dependencies in the core. | SF0 | Exact bounded recovery prefix, private construction, deterministic work receipt and zero dataflow/slice work. |
| W2 / SF2: prepared-capture binding | Input owner: `src/input/frame_structure.rs`, existing `capture_context`/validation seams, input exports, focused `tests/input/` and root manifest targets. | SF1 | Final-request and capture/proof validation; preparation diagnostics never become sealed graphs. |
| W3 / SF3: frame structure | Investigation owner: `src/investigation/frame_structure.rs`, module exports and shared active-call helper; focused investigation tests. | SF2 | Independently useful frame maps, verified adjacent-call links, typed gaps/frontiers and aggregate policy checks. |
| W4 / SF4: codecs and CLI | Product owner: `src/reports/frame_structure.rs`, reports exports, `src/bin/ariadne-minidump.rs`, focused report/CLI tests and root test registrations. | SF3 | Strict saved replay, JSON/text/DOT views and explicit structural mode without any full-completion call. |
| W5 / SF5: finite qualification | Qualification owner plus independent reviewer: isolated remote model/oracle/replay/mutation jobs and source/tool records under `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/`. | SF4 | Applicable root, fixture/capture, model and behavioral mutation gates; compatibility and source identity checked. |
| W6 / SF6: dump and reconciliation | Root/corpus owner: original-dump driver, retained qualification bundle, canonical usage/validation summary and this ledger. | SF5 | Public API and CLI structural report on the named dump; independent replay/control equality and explicit remaining gaps. |

## Fine-grained task ledger

Each row's deliverable belongs to its wave owner. Source/model hashes and actual
commands are retained in the dated evidence bundle. Passed rows refer only to
that finite source/tool/corpus scope.

| Task | Dependency | Owns / deliver | Acceptance | Status |
| --- | --- | --- | --- | --- |
| SF0.1 | Baseline | Contract, API/CLI/status/identity and producer-vs-semantic-backend inventory; payload sizing. | Decisions below frozen without changing old reports or input roots. | Passed |
| SF0.2 | SF0.1 contract | Independent finite recovery/frame oracle, TLA+ projection/status model and checker registration. | Expected edges, frontiers, stop receipts and call links are not calculated by the SUT. Model bounds and trusted capture premises explicit. | Passed |
| SF1.1 | SF0 | Owned core recovery result/factory and immutable getters. | Only Visit actions; result cannot be upcast/deserialized as a completed analysis. | Passed |
| SF1.2 | SF1.1 | Work-stop handling and core fixture tests. | Exact pending/visited/decoded/edges/obligations at zero, boundary and drained budgets; completed-run control projection matches. | Passed |
| SF2.1 | SF1 | Final capture/request/proof binding and feature-correct input API. | Reuses opaque-ordinary, target, guard and composition checks; tampering fails even after rehashing. | Passed |
| SF2.2 | SF2.1 | Preparation-failure and per-frame status handling. | A hard preparation failure has diagnostics only; other valid frames survive when independently preparable. | Passed |
| SF3.1 | SF2 | Frame graph extraction, boundaries and shared active-call validation. | Reached captured E8 + exact continuation + child entry is required for each CALL link. Stack relation alone remains an annotation. | Passed |
| SF3.2 | SF3.1 | Aggregate frame result and bounded validation. | Missing/ambiguous anchors are partial evidence; forged identities/proofs are errors. Recursion preserves activation identity. | Passed |
| SF4.1 | SF3 | Strict structure codec, evidence dictionary and renderers. | Standalone replay, host-controlled decode/check limits and deterministic outputs; old codecs unchanged. | Passed |
| SF4.2 | SF4.1 | New CLI mode, arguments and finite-policy input. | No native `complete()` or `CompletedAnalysis`; invalid mode combinations rejected; BAP prerequisites remain explicit. | Passed |
| SF5.1 | SF4 | Root/model/oracle/capture qualification on an isolated remote source snapshot. | All declared tiers pass or remain explicitly unexercised; exact hashes retained. | Passed |
| SF5.2 | SF5.1 | Compiled behavioral mutations, compatibility replay and independent review. | Intended behavior observers reject mutants; compile/transport failure earns no mutation credit. | Passed |
| SF6.1 | SF5 | Source-bound corpus and payload preflight. | Dump/helper/reader/normalized-request/proof identities verified; finite policy can carry the real pair. | Passed |
| SF6.2 | SF6.1 | Public API and CLI original-dump run plus saved replay. | Useful admitted structural report with zero dataflow/slice work, exact control comparison and preserved unknowns. | Passed |
| SF6.3 | SF6.2 | Canonical API/CLI usage and dated validation summary; final ledger/evidence inventory. | Every accepted claim has source/tool/corpus evidence. Full caller S6 and path F4 remain separate. | Passed |

## SF0: freeze interfaces and finite policies

Private bound types and raw transport forms are implemented. The source
request/activation/proofs are immutable. The structure identity binds
those inputs, its recovery prefix, producer/ruleset, limits and stop receipt in
a separate hash domain from completed analysis. Avoid hash cycles.
Selected frames and necessary auxiliary caller-entry witnesses have explicit
activation scope and aggregate limits.
An independently validated auxiliary caller may establish an entry witness, but
does not change the requested frame range; its evidence and work count against
the same trusted policy.

Preserve the existing feature chain and register focused tests in the root
manifest rather than adding another Cargo package:

| Surface | Intended feature/test boundary |
| --- | --- |
| Core `RecoveryResult` | Standard library only, available in core-only builds; standalone recovery tests need no external features. |
| BAP proof-bound structural types/codecs | Gate verification on `bap`; a reports-only build must not accept the BAP family by silently omitting proof fields. |
| File-backed factory and CLI | `input`; add focused input/CLI test targets under `tests/input/`. |
| Report/replay controls | BAP-enabled structural contract tests under `tests/`; retain current reports-only APIs and their gates. |

The authoritative model must retain `Ariadne.tla`'s recovery invariant: visited
starts reflect attempts; decoded starts reflect admitted successful visits;
pending and visited account for original roots and discovered local destinations;
edges, provenance and obligations are exact. `FinishRecovery` leaves those
control fields unchanged, so the structural product can seal a prefix before
that action without claiming the original model's `Done`/`ScopeClosed` property.
Model frame-link admission, partial-status propagation and budget stops as
separate properties. Finite checks are not universal Rust/native refinement.

| Policy layer | Freeze and exercise |
| --- | --- |
| Open/read/unwind | Artifact/read evidence, supported unwind profile, frame count and runtime-table entry bounds. The named Electron image exceeded the old 4,096-entry default. |
| Preparation | Existing lifting/discovery/guard/target inputs and their distinct limits; successful final request is required for a trusted structure. |
| Owned source/proofs | Nodes, edges, original captures, normalized request and proof bytes, checked references and arithmetic overflow. |
| Recovery producer | Visit count, cooperative time and retained prefix/frontier size; stop before the next Visit. |
| Frame aggregation | Total frames/nodes/edges and boundary/anchor evidence, with no inherited 8,192-node hard clamp. |
| Saved decoding/replay | Host-selected byte/node/proof/replay limits checked before expensive allocation or work. A report cannot raise host caps using its own declared limits. |
| Rendering/publication | Format/payload limits and bounded diagnostics if a valid self-contained report cannot fit. No silent graph clipping. |

Choose finite defaults only after sizing the frozen workload. They are policy
choices, not new arbitrary hard maxima. The existing frame-path 8,192-node,
4 MiB output and 8 MiB decode defaults are unchanged and do not govern this
new family. Boundary and zero-limit semantics must be explicit.

Producer stops and verifier stops are different: a producer may emit a validated
partial prefix with its pending work; a decoder that exhausts its verification
budget must refuse a trusted bound result. Deadline receipts validate the exact
recorded visit prefix and separately describe clock observations; replay does
not pretend to reproduce elapsed time.

## SF1–SF3: build the structural boundary

1. Reuse `Analyzer`'s deterministic Visit behavior. Publish only the core control
   projection and its work receipt; do not expose reaching/slice facts through
   the new type. Preserve the core-only dependency boundary.
2. Validate the exact final prepared request through the current input ownership
   and proof-dispatch rules. Keep all effects needed for proof validation even
   though this producer does not propagate definitions. Never traverse a pending
   candidate continuation that is a final nondecodable Stop.
3. Distinguish pending local work, failed decode endpoints, unknown indirect
   destinations, final unresolved guards, opaque call context and local edges
   leaving the declared function. Unfollowed call targets are not automatically
   pending local work; preserve call facts while following local summaries.
4. Preserve the frame chain and independently available local maps if another
   frame cannot prepare or bind. A child without a runtime function entry may
   use only a separately verified parent direct-call entry witness; otherwise
   report the missing entry. Do not guess roots from saved PCs or slice seeds.
5. Factor shared active-call evidence checks without widening their supported
   E8 profile or weakening the old completed binder. Equal VAs in recursive
   activations remain different frame nodes.

Today `PreparationError::LimitReached` contains a `MaterializationReport`, not
publishable instructions/evidence/seals. Treat it as progress diagnostics only.
Its `unattempted_references` may not yet be finalized; derive referenced-minus-
attempted for progress when needed, and distinguish deliberately unqueued call
references from actual local frontiers. Preparation checkpoint sealing is out
of scope.

## SF4: product and persistence

The implemented CLI is a separate mode:

```text
ariadne-minidump <dump> --frame-structure N:M
    [--frame-structure-limits <policy.json>] [existing supported BAP/input options]
```

The route branches before full analysis and performs no native-core
completion. Existing frame index/thread/entry provenance rules remain binding. Define the structural policy bundle to
cover the relevant unwind/read, preparation, recovery, validation and publication
limits, so the real corpus does not silently inherit an unrelated default.
Validate `N >= M >= 0` against the recovered physical chain. An equal-frame
selection yields one frame map, with no zero-edge-path claim. Missing frames in
a truncated chain remain unavailable evidence, not an invented connection.

Reject combinations with `--list-frame-paths`, NP/path-count options and
origin/assessment modes. Track explicit full-analysis backend options: an
explicit `--analysis-backend` or native-core-only option is incompatible with
v1 structural mode. The implicit existing default `bap` still governs old
full-analysis routes; it
must not falsely label the new projection as native-core execution. Report
`semantic_backend = bap` and `producer = rust-recovery/v1` separately.

V1 saved reports retain one self-contained, deduplicated evidence dictionary.
Resolve and validate every reference. Decode untrusted raw forms first; only
successful replay constructs a privately owned bound object. JSON, text and
DOT expose the same structural facts and gaps. Reject unknown schema fields,
duplicate keys, malformed addresses and contradictory counters. A missing
anchor does not erase valid local maps; a frame-chain relation alone is never
rendered as a proven
CALL edge. The new type is not accepted by origin assessment or current path
listing. Adding a native structural producer or a new path consumer is later work.

## SF5: independent controls and remote qualification

Run all Cargo/native/model/replay/mutation/dump work in remote Windows WSL via
the existing `r_windev` workflow. Hash-verify the task-owned source archive and
frozen sibling dependency snapshot. Keep replay and mutation build directories
separate under the remote root `target/`; preserve exact executable identities.
All heavy runtime/model/mutation/dump work runs in remote Windows WSL;
local reconciliation checks documentation and source identities.

Required independent cases:

- Straight line, both arms of a diamond, cycle, recursion, unreachable seed,
  intentionally unfollowed call target, failed/out-of-function endpoint and
  incomplete indirect target.
- Drained recovery with gaps; work-stopped prefix; zero recovery work; hard
  preparation failure; independently valid frame beside an unavailable frame.
- Captured reached E8 link, uncaptured/unreached call, return/target mismatch,
  ambiguous call and repeated VAs in different activations.
- Rehashed node/edge/gap edits, changed capture bytes/spans, wrong snapshot,
  request/activation/epoch/producer, missing proof and candidate-edge promotion.
- Each trusted-host and producer limit at below/exact/above boundaries; integer
  overflow; proof dictionary corruption; oversized raw input and rendered output;
  verifier-budget exhaustion without trusted publication.
- Projection equality with completed-control fixtures; zero dataflow/slice work;
  legacy proof/version replay and unchanged current path/origin behavior.

Add behavioral mutants for missing edges/frontiers, forged drained/coverage
status, a Visit after queue drain, admitting an unknown guard's candidate edge,
accepting an unreached call and ignoring an independent limit. Expected outcomes
come from an independent oracle/model, not only the same producer and replay
implementation. Existing native/capture regressions must name actual helpers
and exercised ignored tests. The new producer makes no claim of native
structural parity; optional native comparisons are separate evidence.

Run the applicable root checks remotely on the final source snapshot:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

The implemented finite-check entry points are `Specs/check-frame-structure.sh`,
`tests/investigation/fixtures/frame_structure_oracle.py` and
`tools/check_frame_structure_mutations.py`. The literal oracle and its negative
observer controls are distinct from compiled-SUT behavioral mutations. Ordinary
Cargo success cannot substitute for ignored capture tests, model checking or a
real dump.

## SF6: named dump acceptance

Use `dump_03958DA4FCA844A786262A1053`, SHA-256
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`,
thread 23668, physical pair 1 → 0. Start from the exact recorded roots/premises
and named matching helper/source evidence. No expected destination is a new root.

The [final-helper refresh 075602](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/caller-semantic-coverage/20261015/artifacts/final-dump-admission-20261015T075602/probe-summary.json)
provides a frozen control oracle: caller 9,590 visited, 9,589 decoded and 11,321
edges; callee 778 decoded and 895 edges. Materialization's 9,600 attempted
starts is a different counter. Compare those sets/receipts exactly only when
the prepared request/proofs and source identities are identical; record and
explain newly discovered differences instead of hardcoding these counts.

Preserve the caller boundary at `0x00007ff7744035c9`: its `DecodeFailed`
obligation reflects a final unknown guarded load, not an observed architectural
fault there. Preserve the two callee indirect barriers and original premises.
A reached/verified call link may be shown; missing admission evidence remains
an unresolved link rather than an invented edge.

Preflight the whole self-contained payload: the recorded proof reports alone
are about 25 MiB for the caller and 7.4 MiB for the callee, before other source
and request evidence. Exercise the public API, CLI with explicit finite corpus
policy, saved decode/replay and text/DOT output. An isolated positive run must
not need the native-core executable, but still needs the BAP lifter/runtime,
LLVM reference and actual capture prerequisites it claims to exercise.

Pass SF6 when the new structural family publishes and independently validates
useful control evidence with zero dataflow/slice propagation and precise gaps.
This does not require a path, SCC summary, full caller parity or exact history.
Freeze source/tool/policy/query identities, observer logs, original/stored hashes
and stop receipts under `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/`. Preserve older
qualification bytes and failure history.
If SF6 exposes a runtime correction, reopen its affected implementation stages
and repeat SF5's affected source-bound gates before crediting the corrected run.

## Completion ledger and retained validation

The [2026-10-16 bundle](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/20261016/README.md)
records SF0–SF6 completion on corrected source capsule `8266a844e60e3afbcaa8f0bba557899a0466e18940d8fa881630377cf78bb37c`
(1,093 files) and the independently verified 693-file runtime inventory.
Documentation reconciliation preserves the exercised source capsule rather
than rewriting its identity. The archive/sidecar manifests bind each receipt,
helper, binary, policy, corpus and output to its exact bytes.

Remote checks pass formatting, 285 default tests including three doctests,
57 core-only tests including three doctests, all-feature/all-target Clippy and
Rust layout. The root runs leave 106 default and 22 core-only tests ignored;
these counts are not claims of exercised capture prerequisites. The new
structural capture CLI test passes separately. Reports-only and BAP-only builds
pass, and the core-only dependency tree activates no external crates.

The final model sources pass 43 finite configurations and the independent
literal oracle passes 65 cases with eight negative observer controls. Nine
compiled behavioral mutants have passing unmodified controls and are rejected
by the intended observers on the final source. Thirty-eight named release
compatibility/native/capture tests pass: five native kernels, nine BAP producer,
five backend capture, nine native capture, six frame-path (including two actual
legacy report versions) and four investigation controls. Unrelated ignored
tests and broader platform/release claims remain outside this corpus.

Final run `dump-final-20261016T055748` publishes physical frames 1→0 with caller
9,590 visited / 9,589 decoded / 11,321 edges and callee 778 / 778 / 895. Both
prefixes drain in Recover with zero dataflow/slice actions. Final normalized
requests, captured source projections, guard, target and composition proofs
match the frozen 075602 inputs exactly. An independent oracle also matches the
entire typed graph, provenance, obligations and reached E8 link for both frames.
Public BAP-only saved replay passes without helper/runtime availability, with
byte-identical JSON, text and DOT outputs and zero dataflow/slice metrics.

The earlier Stop-barrier validator defect was corrected and the affected final
checks rerun. Earlier source observations, storage/namespace/temp-file failures
and failed probes remain historical evidence. Caller load
`0x00007ff7744035c9`, callee indirect sites `0x00007ff77443da0e` and
`0x00007ff77443e200`, exceptional exits and opaque call context remain explicit.
Caller-coverage S6 and frame-path F4 are not discharged.

The 2026-10-16 planning checks remain historical: 74 connected documents,
73 context sections and 2,148 local links, plus presentation/diff validation.
Final reconciliation checks navigation locally against the maintained archive;
the isolated remote source capsule does not contain all old chat archives.
These document checks are distinct from remote runtime qualification.
