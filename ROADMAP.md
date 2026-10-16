# Ariadne roadmap

## Context and follow-up

**Status.** Current delivery direction; dated qualifications remain scoped.

**Why this document exists.** [Project overview](README.md) sets the snapshot-based crash-investigation goal.

**What this document establishes.** This is the current scope and delivery sequence: captured input, BAP effects and native analysis, Rust reference, reports and investigation questions.

**Where to go next.**

- [Structural frame report: Stage 5.1](docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
  and [SF0–SF6 ledger](.agents/plans/frame-structure-report.md) — recovery-only API,
  frame maps and separate CLI/report qualified in the
  [2026-10-16 finite scope](evidence/Ariadne/frame-structure/20261016/README.md).
  Existing completed-analysis and full frame-path gates remain separate.

- [Explicit alignment hypotheses](docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses)
  and [H0–H5 ledger](.agents/plans/alignment-hypotheses.md) — structural-only
  conditional MOVAPS normal selection, separately [qualified](evidence/Ariadne/alignment-hypotheses/20261016/README.md)
  while retaining the baseline unknown verdict and actual saved v1 replay.

- [Caller normal-flow coverage](docs/Ariadne/caller-semantic-coverage-design.md)
  and [active S0–S6 plan](.agents/plans/caller-semantic-coverage.md) — source-qualified
  terminal/load support removes the original caller coverage barriers; completing
  the much larger caller dataflow and its native/Rust parity gate remains open.

- [Accepted P4 qualification](docs/Ariadne/file-reader-design.md#windows-replacement-capture-and-bounded-query) — current v3 corpus and user scope decision; the [historical audit](docs/Ariadne/bap-analysis-core-design.md#documentation-audit) preserves its earlier v2 inventory.

- [Selected I5c address-wrap design](docs/Ariadne/address-wrap-design.md) and
  [W0–W5 plan](.agents/plans/i5c-address-wrap.md) — the next fault-time arithmetic
  question; documentation is written, all implementation/qualification pending.

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
[accepted P4](evidence/Ariadne/bap-admission/p4-acceptance-20261010.json) with its
remaining historical real-Linux clauses excluded. No required P4 work remains.
The selected
Windows pin has its own baseline; the old six Linux hashes and real-Linux capture
coverage remain unexercised. Earlier v2 qualification retains its historical scope.
The replacement BAP Windows capture is pinned and passes correctness. The current BAP latency policy is unlimited. Stage 2 native algorithms and capture integration are qualified on the exercised corpus; native analysis is the CLI default with explicit Rust rollback. The first fault-address question is implemented, and [native I4 performance qualification](docs/Ariadne/workload-performance-design.md#native-investigation-qualification) meets the unchanged 2-second CLI limit for the exact re-pinned case. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

For the wider context, see the optional [documentation map](docs/documentation-map.md).

Ariadne produces evidence-bounded control-flow and data-flow results for crash
investigations using pinned BAP instruction lifting. Ariadne validates its own
transport, semantic projection, analysis and reports. The independent AMD64
instruction-step/Lean project and full-manual coverage goal are retired under
the [semantic assurance decision](docs/Ariadne/semantic-assurance.md).

## Guarded captured-target composition — scoped loop closure delivered

The [design](docs/Ariadne/guarded-target-resolution-design.md), [composition plan](.agents/plans/completed/guarded-target-resolution.md) and [loop plan](.agents/plans/completed/loop-aware-target-resolution.md) deliver paired guarded/target preparation, versioned legacy replay and checked local-region induction. [Qualification dated 2026-10-15](evidence/Ariadne/loop-aware-target-resolution/20261015/README.md) closes DA09 and DADD, all nine original incoming-coverage certificates and all 51 missing-start gates, with full native/Rust parity for both completed queries in that earlier stop-limited graph. The loop rule supplies coverage for already witnessed table entries. The caller follow-up below reaches a substantially larger graph; its completed-core and frame-path gates remain open.

## Structural frame maps — Stage 5.1 delivered

The [structural report](docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
publishes final-request recovery prefixes before dataflow, with explicit local
frontiers, captured frame relations and admitted E8 call links. SF0–SF6 pass
their [2026-10-16 source-bound scope](evidence/Ariadne/frame-structure/20261016/README.md):
finite model/oracle, root/capture/compatibility, compiled mutation, original-dump
and helper-free saved-replay gates. The named frame 1→0 pair drains with zero
dataflow/slice work and exact frozen-control agreement. Unknown guards/targets,
exceptional exits and opaque call context remain visible. Caller completion,
full frame-path acceptance and executed-history recovery retain separate gates.

The [explicit alignment extension](docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses)
is separately [qualified](evidence/Ariadne/alignment-hypotheses/20261016/README.md).
It admits the selected 35c9 normal continuation only under a retained
per-activation hypothesis, labels all derived structure conditional and
preserves baseline Unknown. It adds no target narrowing, accumulated-path
constraint solver or completed caller/frame-path gate.

## Caller normal-flow coverage — S5 qualified, S6 partial

The [design](docs/Ariadne/caller-semantic-coverage-design.md), [active plan](.agents/plans/caller-semantic-coverage.md) and [qualification](evidence/Ariadne/caller-semantic-coverage/20261015/README.md) add control-only INT3/UD terminal certificates, exact guarded MOVAPS loads and explicit `local-normal-completion/v1` scope. S0–S5 pass on the declared final sources/helper; final admission refresh `075602` passes exact request/proof equality for both frames, caller structural recovery/admission and callee full parity. It does not repeat full caller completion. Legacy rules/proofs remain versioned, pending loads commit no vector effect, and exception-handler resumption is outside scope rather than assumed impossible.

Original-dump probe `073143` removes all 30 caller coverage barriers and retains all target, root and premise facts. The initial MOVAPS is aligned under the recorded premises; the later load is still unknown. Caller recovery now decodes 9,589 sites and 11,321 edges, then Rust and native completion exhaust their selected action budgets. The callee completes with full request/state parity and two remaining indirect barriers. NP10 frame listing is unavailable with `missing-frame-query` because no completed caller query exists.

The next acceptance gate for this completed-analysis milestone is completed caller analysis and full native/Rust state comparison under declared budgets. Passing terminal admission or native initialization does not satisfy it. Keep S6 and its plan open, and report load alignment, callee targets and frame-path availability separately; normal-flow closure does not establish historical execution or whole-machine coverage. The separately implemented Stage 5.1 structural report does not discharge S6.

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
encoded displacement before modular reduction. All implementation stages are
pending. The first profile preserves lower-range fault admission, so it can
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
while the later load and caller completion remain unresolved. None of these
scoped results qualifies full-dump frame-path enumeration.

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
