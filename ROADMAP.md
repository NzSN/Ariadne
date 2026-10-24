# Ariadne roadmap

## Context and follow-up

**Status.** Current delivery direction; dated qualifications remain scoped.
The [native-64 P2-C completion follow-up](docs/Ariadne/amd64-coverage-design.md#1028-native64-p2-c-completion-follow-up)
delivers partial closure under the user's reaffirmed long-mode-only hypothesis.
Source-specific LOCK/REP interpretations, the scoped normal default64 rule,
new owned forms and a separate proof-derived C gate are validated. The three
remaining C references still require full prefix/size-form inventories.
The existing native `long-64` scope and applicable smaller-data/address-32
forms are retained; full C is not accepted.
The [latest validated P2-C continuation](docs/Ariadne/amd64-coverage-design.md#1027-vol3-precedence-and-xor-source-rows)
implements the user's Vol3 choice for the XORPS/XORPD legacy-prefix
disagreement and checks twelve instruction-owned source rows. Original
source observations remain preserved; this one additive question now has a
checked current rule. The five architectural reference roots and full P2-C
remain open.
The [preceding P2-C continuation](docs/Ariadne/amd64-coverage-design.md#1026-p2-c-continuation-and-prefix-question)
implements the accepted fixed-64 projection, typed B-1 size-family records
and the feature-qualified CR8 opcode-prefix exception. Full per-form/prefix
qualification remains unfinished. Its independently checked XORPS prefix
question is now resolved for the selected scope by the later Vol3 decision;
it was separate from the earlier near-branch decision.
The [2026-10-24 mapping continuation](CHECKPOINTS.md#2026-10-24--per-form-source-rule-mapping-resumed)
supersedes the earlier publication stop and completes the missing five-rule
mapping. The [paired-family source continuation](docs/Ariadne/amd64-coverage-design.md#1018-remaining-paired-family-source-constraints)
resumes selected source review after the conversion slice. The later
[section-5 execution](docs/Ariadne/amd64-coverage-design.md#1019-section-5-execution-and-current-exit-gates)
adds checked dispositions, a cross-volume scaling rule and a generated
frame-path output-cap repair. The subsequent
[P1 completion](docs/Ariadne/amd64-coverage-design.md#1020-p1-source-selection-and-structural-migration-completed)
accepts the exact five-edition source pool and completes structural migration.
The subsequent [P2 execution](docs/Ariadne/amd64-coverage-design.md#1021-p2-clause-and-reference-execution)
checks 30 more clauses, adds current dispositions for the original 516 cells,
and reduces nine current architectural reference scopes to five. Newly
identified conflicts and complete section/region clause reviews remain
explicit. P2 completeness, P3 legal domains and full AMD64 coverage remain open.
The later [P2 completion-task execution](docs/Ariadne/amd64-coverage-design.md#1022-p2-completion-task-execution)
implements source-checked page/section dispositions and current boundary
reconciliation, resolves the inherited MOV question and REX placeholder
notation, and finds a concrete GF inverse-table source conflict. That requires
an authoritative source answer; the remaining clause inventories and complete
page/section reviews are still unfinished work.
The [H64 hypothesis](docs/Ariadne/amd64-coverage-design.md#1023-h64-native-amd64-execution-only)
clarifies a native AMD64 64-bit execution target, consistent with the existing
`long-64` source scope. Non-64-only rows can be scoped out through checked
dispositions; smaller operands, address-32 forms and legacy encodings valid
in 64-bit mode remain required. This hypothesis adds no acceptance.
The [H64 execution](docs/Ariadne/amd64-coverage-design.md#1024-h64-source-projection-and-native64-inventories)
implements the checked non-64-only MOVD disposition and adds native-64
Appendix B/default-size and LOCK/REP source inventories. Complete per-form
size/prefix qualifications, section/region reviews and source questions remain
open; no runtime or full-stage acceptance follows.
The [accepted fixed-64 near-branch hypothesis](docs/Ariadne/amd64-coverage-design.md#1025-selected-fixed64-near-branch-hypothesis)
selects that operand-size case and excludes its possible 16-bit override
alternatives. It permits continuation without reconciling the excluded case;
the current-scope checker projection is implemented by the continuation above. Other
smaller operands, address-size rules and source questions remain separate.

**Why this document exists.** [Project overview](README.md) sets the snapshot-based crash-investigation goal.

**What this document establishes.** This is the current scope and delivery sequence: captured input, BAP effects and native analysis, Rust reference, reports and investigation questions.

**Where to go next.**

- [AMD64 operation coverage program](.agents/plans/amd64-operation-coverage.md) —
  user-requested expansion of machine-instruction semantics and captured Windows
  unwind operations. Implementation and independent operation tests are active;
  the exhaustive instruction-form and newer metadata gates remain pending.

- [Executable validation](tests/README.md) and the
  [T0–T5 migration](.agents/plans/generated-validation-retention.md) replace the
  retained collection with tests, small actual inputs and independent oracles.
  T0–T5 is complete for this migration: PBT, core and stateflow/IR replay,
  compiled mutations and root checks pass. Generated results stay outside source.
  Full native-core/capture, timing and release prerequisites remain explicit.

- [Structural frame report: Stage 5.1](docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
  and [SF0–SF6 ledger](.agents/plans/frame-structure-report.md) — recovery-only API,
  frame maps and separate CLI/report qualified in the
  [2026-10-16 finite scope](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/20261016/README.md).
  Existing completed-analysis and full frame-path gates remain separate.

- [Frame corridors and cycle summaries: Stage 5.2](docs/Ariadne/investigation-design.md#structural-corridors-and-cycle-summaries)
  and [FC0–FC6 plan](.agents/plans/frame-connections.md) — implemented
  reachability/SCC/example consumer of validated structural reports.
  [Remote finite/capture qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md)
  now passes for both declared saved sources; broad release remains separate.

- [All four section-5 priorities](docs/Ariadne/frame-question-investigation-design.md)
  and [program plan](.agents/plans/frame-question-investigation.md) — implemented
  one-question resolution, fair semantic work and local dependency/writer
  integration above the existing 5.1/5.2 products, with separate
  [remote qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md).
  The applicable FC5/M4 gates pass; frame-path F4 and release acceptance remain
  separate. Caller S6 has its own completed qualification.

- [Explicit alignment hypotheses](docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses)
  and [H0–H5 ledger](.agents/plans/alignment-hypotheses.md) — structural-only
  conditional MOVAPS normal selection, separately [qualified](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/alignment-hypotheses/20261016/README.md)
  while retaining the baseline unknown verdict and actual saved v1 replay.

- [Captured indirect-target R6 qualification](docs/Ariadne/indirect-target-resolution.md#r6-qualification-refresh)
  and [R0–R6 ledger](.agents/plans/indirect-target-resolution.md) — finite
  pointer-slot/signed-32 target admission, fresh resolver/model/replay/original
  Windows gates and retained source-verified core mutations. The
  [2026-10-20 evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/20261020/README.md)
  preserves incomplete target coverage and partial explanations.

- [Scanner partial-explanation follow-up](docs/Ariadne/investigation-design.md#scanner-partial-explanation-follow-up)
  and [S2–S4 ledger](.agents/plans/scanner-partial-explanation.md) — twenty-site
  control/decode audit and 123-location entry boundary, with [qualified partial
  evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/scanner-followup/20261020/README.md). All 28 gaps
  remain; the review establishes no executed history or actual writer.

- [Caller normal-flow coverage](docs/Ariadne/caller-semantic-coverage-design.md)
  and [completed S0–S6 ledger](.agents/plans/caller-semantic-coverage.md) — terminal/load
  support removes the original barriers, and its completed-caller gate has
  separate 2026-10-19 qualification.

- [Accepted P4 qualification](docs/Ariadne/file-reader-design.md#windows-replacement-capture-and-bounded-query) — current v3 corpus and user scope decision; the [historical audit](docs/Ariadne/bap-analysis-core-design.md#documentation-audit) preserves its earlier v2 inventory.

- [Selected I5c address-wrap design](docs/Ariadne/address-wrap-design.md) and
  [W0–W5 plan](.agents/plans/i5c-address-wrap.md) — the next fault-time arithmetic
  question; W0–W3 pass their separate recorded gates, including the
  [140-case/native114 W3 matrix](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/address-wrap/20261021/w3/README.md).
  W4 sources are implemented with product/capture gates pending; W5 remains pending.

- [Selected I5b design](docs/Ariadne/zero-base-offset-design.md) and
  [implementation plan](.agents/plans/completed/i5b-zero-base-offset.md) — the delivered bounded
  zero-base-plus-displacement hypothesis, with B0–B5 implemented and corpus-qualified.
- [Active plans](.agents/plans/README.md) — turn remaining work into explicit implementation and qualification steps.
- [Assurance decision](docs/Ariadne/semantic-assurance.md) — defines the BAP trust boundary and retired ISA-proof scope.

**What remains unresolved.** The [projection-admission extension](.agents/plans/completed/bap-projection-admission.md)
has P0–P4 accepted: v3 capabilities, conservative ordinary continuation and
source-bound qualification of the selected finite corpus.
Its [current replacement record](docs/Ariadne/file-reader-design.md#windows-replacement-capture-and-bounded-query) qualifies
P4 source/fixture, Rust release-runtime and native-default tiers remotely with
completion transport, exact parity and unchanged fixed budgets. The user
[accepted P4](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/p4-acceptance-20261010.json) with its
remaining historical real-Linux clauses excluded. No required P4 work remains.
The selected
Windows pin has its own baseline; the old six Linux hashes and real-Linux capture
coverage remain unexercised. Earlier v2 qualification retains its historical scope.
The replacement BAP Windows capture is pinned and passes correctness. The current BAP latency policy is unlimited. Stage 2 native algorithms and capture integration are qualified on the exercised corpus; native analysis is the CLI default with explicit Rust rollback. The first fault-address question is implemented, and [native I4 performance qualification](docs/Ariadne/workload-performance-design.md#native-investigation-qualification) meets the unchanged 2-second CLI limit for the exact re-pinned case. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

For the wider context, see the optional [documentation map](docs/documentation-map.md).

Ariadne produces evidence-bounded control-flow and data-flow results for crash
investigations using pinned BAP instruction lifting. Ariadne validates its own
transport, semantic projection, analysis and reports. The independent AMD64
instruction-step/Lean proof project remains retired under
the [semantic assurance decision](docs/Ariadne/semantic-assurance.md). The later
[operation program](.agents/plans/amd64-operation-coverage.md) reopens full
implementation coverage, with inventory and finite advanced-producer work in
progress; this does not restore the retired proof project.
Its [current finite execution](docs/Ariadne/amd64-coverage-design.md#10-source-review-and-validation-status)
accounts for all 2,657 historical manual gaps (zero unassigned, seven explicit
source-conflict records), while broader source constraints remain unparsed. It adds
a 56-point AMD memory-REP binding registry and separately selected v13/v14/v15
profiles. The R1 source boundary passed 416 native parity instances and 259
refusal controls. The AMD-specific v15 address-size successor has dated local
producer, binding and 448-instance capture checks. The [current resume](docs/Ariadne/amd64-coverage-design.md#1010-resumed-source-review-and-validation)
integrates bounded source adjudications, tightens MOV8 validation and passes
341 refusal controls with a fresh local native core. The [approved tool recovery](docs/Ariadne/amd64-coverage-design.md#1011-pinned-tool-recovery-and-current-source-replay)
restores exact PDF extraction and source producers, and passes full
source/authority replay. A [reviewed helper-build migration](docs/Ariadne/amd64-coverage-design.md#1012-helper-build-migration-v1-and-renewed-finite-qualification)
qualifies the two rebuilt executables, refreshes v2/v3/MOV8 bindings and passes
448 native v15 parity instances plus compatibility checks. Source completeness, broader
REP consumers and full AMD64 coverage remain open.

The [2026-10-24 mapping continuation](docs/Ariadne/amd64-coverage-design.md#1014-per-form-source-rule-mapping-resumed)
completes the five-rule mapping and affected reseals/reruns. The later
[memory-native gate](docs/Ariadne/amd64-coverage-design.md#1015-memory-mov8-native-consumer-continuation)
qualifies its finite address-64 consumer and address-32 refusals. The
[publisher entry review](docs/Ariadne/amd64-coverage-design.md#1016-publisher-migration-entry-review)
and selected source-constraint packs retain all 115 migration obligations,
ten architectural references and 516 unparsed cells. The
[remaining paired-family review](docs/Ariadne/amd64-coverage-design.md#1018-remaining-paired-family-source-constraints)
adds bounded claims for GF2 inverse affine, MOVD and scalar negative multiply-add;
source contradictions and whole-section review remain explicit.

Current validation follows the [executable test matrix](tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.

## Active specifications — finite S3 qualified

The [formal-model guide](Specs/README.md#specification-synchronization-s3-qualification-2026-10-20), [completed S0–S3 ledger](.agents/plans/specification-sync.md) and [evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync/20261020/README.md) close the declared finite model suite. The exact 1,118-file snapshot has 53 typecheck calls/32 root modules, 40 bounded calls, 24 TLC instances, 20 Memory partitions, six scripts and eight audited core TLC configurations. Full 120 Java calls include three identity checks; the eight preflight and three final equality controls are separate.

Bounded outcomes remain 30 `NoError` and 10 terminal `ExecutionsTooShort` with nonempty Init and matching complete TLC graphs; requested maximum lengths are unchanged and not claimed reached by short cases. Canonical algebraic authority, exact finite lookup equality/closure/coverage, original Safety TLC, all domains and bounds remain explicit. This does not qualify W2 runtime, ISA, wider widths/chains, universal refinement or release. Historical 20261011 counts and failed attempts retain their scopes.


## Captured indirect targets — finite R6 qualified

The [canonical contract](docs/Ariadne/indirect-target-resolution.md#r6-qualification-refresh)
and [2026-10-20 evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/20261020/README.md)
close the selected R6 profile. Final source identity is
`193e31bb835bda4a4e4b5fc59397c424f11adefc691d1e309faf7ff0348d43a5`
(1,076 files). Fresh 14 Rust/one native legacy-v1 mutations, 39 Python controls,
five model configurations and typechecking, 330 replay observations, native
fixtures and original Windows parity pass. Twelve core mutants are explicitly
retained after 221 relevant-input and identical-helper checks.

The original 58-entry/45-target dispatch stays non-exhaustive and its explanation
partial. Each measured resolver pass meets 1,000 ms and each current-source
JSON explanation-only CLI sample meets 60,000 ms; concrete timing samples and
archive identity are in the canonical qualification. The 60 s diagnostic response
timeout supplies state-parity evidence only; production native transport remains
30 s. Producer/runtime semantics are unchanged. Historical failures remain
historical. This finite result excludes real Linux full dumps, all-format full
base reports, packaged release, history/root cause and universal refinement.

## Guarded captured-target composition — scoped loop closure delivered

The [design](docs/Ariadne/guarded-target-resolution-design.md), [composition plan](.agents/plans/completed/guarded-target-resolution.md) and [loop plan](.agents/plans/completed/loop-aware-target-resolution.md) deliver paired guarded/target preparation, versioned legacy replay and checked local-region induction. [Qualification dated 2026-10-15](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) closes DA09 and DADD, all nine original incoming-coverage certificates and all 51 missing-start gates, with full native/Rust parity for both completed queries in that earlier stop-limited graph. The loop rule supplies coverage for already witnessed table entries. The caller follow-up below reaches a substantially larger graph; its completed-core gate now has S6 qualification. Finite original-capture frame-path F4 has the separate qualification below.

## Structural frame maps — Stage 5.1 delivered

The [structural report](docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
publishes final-request recovery prefixes before dataflow, with explicit local
frontiers, captured frame relations and admitted E8 call links. SF0–SF6 pass
their [2026-10-16 source-bound scope](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-structure/20261016/README.md):
finite model/oracle, root/capture/compatibility, compiled mutation, original-dump
and helper-free saved-replay gates. The named frame 1→0 pair drains with zero
dataflow/slice work and exact frozen-control agreement. Unknown guards/targets,
exceptional exits and opaque call context remain visible. Caller completion,
full frame-path acceptance and executed-history recovery retain separate gates.

The [explicit alignment extension](docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses)
is separately [qualified](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/alignment-hypotheses/20261016/README.md).
It admits the selected 35c9 normal continuation only under a retained
per-activation hypothesis, labels all derived structure conditional and
preserves baseline Unknown. It adds no target narrowing, accumulated-path
constraint solver or completed caller/frame-path gate.

## Caller normal-flow coverage — S0–S6 qualified

The [design](docs/Ariadne/caller-semantic-coverage-design.md), [ledger](.agents/plans/caller-semantic-coverage.md)
and [2026-10-19 evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/caller-semantic-coverage/20261019/README.md)
complete the original normal-flow/caller profile. Both original requests and
their full states match between Rust/native implementations. Every reaching row
is independently checked. Caller dataflow retains 141,301,903 links and finishes
in 91,175 actions within the original million-action limit.

Completion uses exact compact membership and RPO; ordinary replay remains
unchanged. The current LLVM rebuild restores the 30 original barriers after the
stale-helper partial attempt. Later MOVAPS alignment and two callee targets remain
unknown. Finite frame-path F4 is separately qualified below; broader
release/large-report qualification, history/root cause and universal refinement
remain open.

## Bounded structural frame paths — finite F4 qualified

The [contract](docs/Ariadne/investigation-design.md#f4-post-s6-qualification),
[F0–F4 ledger](.agents/plans/frame-path-enumeration.md) and
[2026-10-20 evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-paths/20261020/README.md) qualify
bounded structural enumeration for the unchanged original S6 requests and
physical frames 1→0, thread 23668, NP=10. The final listing returns
one structural path with native/Rust equality and helper-free
saved replay. Six finite model configurations and typechecking, independent
oracles/properties, compiled mutations and hostile codec controls pass their
recorded scope.

Explicit v7 graph admission and independent saved-decoder caps retain ordinary
legacy defaults. The selected 32-node/two-visit path policy keeps coverage
partial and preserves all possible writers and source unknowns. The initial
512-node/million-state attempt returned zero paths and remains a failed positive
gate. General unwinding, path feasibility/history, root cause, release and
universal refinement remain outside this result.

## Investigation direction

The [investigation-layer design](docs/Ariadne/investigation-design.md)
and [implementation plan](.agents/plans/investigation-layer.md) propose domain questions
above binary-analysis primitives. The first slice explains possible fault-address
producers with captured evidence, alternatives and missing-evidence requirements.
The [first fault-address delivery](docs/Ariadne/investigation-design.md#retained-delivery-evidence) now
implements the question for both platform fixtures and the retained controlled
Linux capture. The later [Windows I4 re-pin](docs/Ariadne/workload-performance-design.md#windows-investigation-replacement)
adds independently inspected real Windows producer evidence. All 17 gates pass,
while its historical 4,774.451 ms CLI median exceeded the unchanged 2,000 ms ceiling.
The [later native performance result](docs/Ariadne/workload-performance-design.md#native-investigation-qualification)
meets that ceiling at 1,692.696 ms with the same capture/query. The
original Electron manifest remains historical; no executed path or root cause
is established.
BAP analysis-core migration remains separate from this product capability.
The [OCaml foundation qualification](docs/Ariadne/bap-analysis-core-design.md#ocaml-foundation-qualification)
records the bounded native bootstrap and full A0 decision. The [Stage 2 qualification](docs/Ariadne/bap-analysis-core-design.md#native-qualification) records the completed algorithms and passing default-adoption gate.
The [I5a zero-address assessment](docs/Ariadne/zero-address-design.md) now evaluates
whether one selected scalar MOV access begins at zero under admitted Windows
AMD64 exception-context premises. Reader-owned context, a separate strict report
and explicit CLI modes are implemented. The [12-gate source/fixture validation](docs/Ariadne/zero-address-design.md#historical-source-and-fixture-qualification)
passes for its historical sources. The native successor qualifies controlled
Windows I5a; the later [I4 performance result](docs/Ariadne/workload-performance-design.md#native-investigation-qualification) meets its independent fixed budget; the original Electron case is historical.
The selected [I5b design](docs/Ariadne/zero-base-offset-design.md) and
[B0–B5 plan](.agents/plans/completed/i5b-zero-base-offset.md) define a distinct fault-time question:
is the encoded GPR base zero with a nonzero signed displacement? Its first
profile requires reviewed simple base/displacement decoded facts to agree with
BAP address evidence. B0–B5 are implemented, with [actual contracts](docs/Ariadne/zero-base-offset-design.md)
for machine-code debugging; [qualification](docs/Ariadne/zero-base-offset-design.md#retained-qualification) passes all
18 gates and separate source/fixture/controlled Windows timing criteria.
Historical null derivation and other hypotheses remain later work.
The next selected [I5c design](docs/Ariadne/address-wrap-design.md) and
[W0–W5 plan](.agents/plans/i5c-address-wrap.md) assess the unsigned base plus signed
encoded displacement before modular reduction. W0 passes its separate finite
model/oracle gate; W1–W3 now pass binding, pilot and full finite/native matrix
qualification. W4 product/capture and W5 full qualification remain pending. The first profile preserves lower-range fault admission, so it can
qualify upper-wrap/no-wrap cases while mathematical underflow remains unknown.
It introduces no historical-path, canonicality or root-cause claim.
The [native Windows Crashpad demo](docs/Ariadne/zero-address-design.md#controlled-windows-capture)
supplies real partial/full captures and correct numeric answers. Its historical
CLI median was approximately 1.82 s. The [native I5a refresh](docs/Ariadne/zero-address-design.md#native-qualification)
now qualifies both timing budgets and both capture modes. A read-only dependency
snapshot prevents concurrent MirrorRust edits from invalidating qualification.

The [original proof-gated MOVAPS delivery](docs/Ariadne/justified-branch-pruning-design.md)
adds opt-in Windows function-entry alignment premises, candidate closure and
versioned proof validation. Its early dump retry stopped at later XORPS width
admission; subsequent corrections and loop closure supersede that diagnostic.
The caller coverage extension above now proves the initial MOVAPS alignment,
while the later load remains unresolved. Caller completion and finite
original-capture frame-path enumeration now have their own separately bound
S6 and F4 evidence; the earlier admission results do not qualify those gates.

## Current checkpoint

Native BAP now owns production minidump recovery, may-reaching definitions,
slicing and supplied finite stateflow; Rust retains capture preparation,
transport/projection validation, questions and reports. The Rust analyzers
remain independent references and explicit rollback implementations. BAP is now the sole production
minidump semantic backend; LLVM MC remains an independent decode/control
reference. The semantic selector and LLVM effect fallback are removed. See the
[historical BAP-only delivery](docs/Ariadne/bap-analysis-core-design.md#bap-only-delivery) and
[controlled Windows replacement](docs/Ariadne/bap-analysis-core-design.md#windows-workload-replacement).
The replacement passed 17 implementation gates. The subsequent
[unlimited timing policy](docs/Ariadne/bap-analysis-core-design.md#unlimited-timing-policy) removes latency
as an acceptance barrier while retaining correctness and source/tool checks. Legacy
LLVM effect rules and their source-bound tests remain historical/research
reference evidence. Native BAP recovery, dataflow, slicing and finite stateflow are implemented; [Stage 2 qualification](docs/Ariadne/bap-analysis-core-design.md#native-qualification) records passing aggregate acceptance and default adoption. The [minidump package](docs/Ariadne/file-reader-design.md#public-interface) now provides captured-memory input and
local-start discovery for Windows/Linux AMD64. PE/ELF image and ELF core readers
remain deferred. A tool-produced [captured predecessor slice and versioned
investigator CLI](docs/Ariadne/file-reader-design.md#captured-predecessor-fixtures) are delivered. The
two historical Breakpad dumps still serve as independent crash-IP regressions.
A separate [controlled Chromium real-capture investigation](docs/Ariadne/file-reader-design.md#historical-controlled-chromium-capture)
now qualifies one possible predecessor slice with an exact matching-build
entry witness. It does not reconstruct the actual execution path or qualify
larger-workload performance.
The [Priority 2 effect review](docs/Ariadne/operand-effects-design.md#selected-path-no-change-decision-2026-09-29)
retains opaque calls on that path. [Priority 3 presentation](docs/Ariadne/result-rendering.md#presentation-acceptance)
adds a readable text overview and Linux/Windows examples without changing
JSON or DOT semantics. [Priority 4 measurements](docs/Ariadne/workload-performance-design.md#historical-llvm-workload-qualification)
record historical LLVM-backed qualification of a 98-instruction Windows
Electron capture and a measured optimization:
the CLI median falls from 3,846 to 1,788 ms against the fixed 2,000 ms budget,
with the visible schedule and report hashes preserved. This does not qualify
the current BAP path, whose current policy measures latency without a ceiling. The separate abstract-stateflow and supplied-IR paths pass
[Stage E generated conformance and report/CLI acceptance](docs/Ariadne/typed-replay-design.md#finite-corpus-and-claim-boundary). A
[proof-boundary and benchmark baseline](docs/Ariadne/semantic-assurance.md#universal-rust-refinement-boundary)
is recorded without a universal refinement or optimization claim.

## Delivery path

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Input and decode | The pinned LLVM MC adapter and Windows/Linux minidump reader are delivered; PE/ELF images and ELF cores remain deferred by the current input scope. Readers must provide one immutable address-space snapshot, VA mapping, and verified byte provenance. | The same known bytes decode consistently from binary and dump views; missing or conflicting bytes remain explicit. VAs are never confused with file offsets. |
| 2. Control-flow recovery | Translate decoded control transfers into the core's instruction kinds, direct targets, fallthroughs, calls, returns, and unresolved-edge obligations. | End-to-end binary and dump fixtures exercise direct branches, calls, returns, sparse bytes, and indirect branches. Every edge has source instruction evidence; unresolved targets are visible, not silently omitted. |
| 3. Conservative effects | Typed BAP projection supplies `uses`, `may_defs` and justified `must_defs` to the native analysis. The independent LLVM reference checks decoding/control facts; unsupported BIL, memory and call effects stay explicit. Broader admitted semantics and alias precision require scoped evidence. | Slices retain every possible origin in representative crash paths. An unknown effect cannot become a definite overwrite, a no-op, or a known successor. Alias and call-summary assumptions are recorded. |
| 5. Investigator output | Text, Graphviz DOT, JSON v1 and a readable per-instruction minidump overview are delivered. The [separate Stage E result envelopes and optional CLIs](docs/Ariadne/typed-replay-design.md#finite-corpus-and-claim-boundary) are delivered. | Pinned Linux/Windows examples and the controlled Chromium case retain matching identities, edges, possible origins and uncertainty across formats. |

Phases 1–3 and 5 define the practical minidump workflow. The former Phase 4
instruction-step project is retired. The immutable [analysis contract](docs/Ariadne/bap-analysis-core-design.md)
and [Rust reference](docs/implementation.md) remain the correspondence boundary.
Existing full-analysis CLI routes consume completed native analysis through
the shared `AnalysisView`; the opt-in structural route consumes a separate Rust
recovery prefix.

## Scope and priority rules

- Prioritize instructions that appear on the control-flow and backward-slice
  paths of representative Chromium/Electron crashes. Direct control transfers,
  stack operations, common data movement, arithmetic, comparisons, and ordinary
  RAM accesses have immediate value; coverage grows with supported investigations.
- Use LLVM MC as the independent byte/length/control reference and pinned BAP
  BIL as the production semantic input. Project only admitted expressions and
  keep unsupported effects, indirect targets and uncertain memory explicit.
- Preserve conservative unsupported-operation behavior: no invented successful
  step, architectural fault, definite write or known successor. Keep unavailable
  captured data distinct from unsupported BIL and architectural undefinedness.
- Keep coverage claims separate: decoded and discovered instructions, useful
  analyzer output, paired semantic bodies, and verified instruction steps are
  different achievements. Do not infer whole-mnemonic or whole-ISA support from
  a passing fixture.

The
[practical assurance queue](docs/Ariadne/semantic-assurance.md#practical-assurance-priorities)
lists the next release-facing work.
