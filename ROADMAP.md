# Ariadne roadmap

## Context and follow-up

**Status.** Current delivery direction; dated qualifications remain scoped.

**Why this document exists.** [Project overview](README.md) sets the snapshot-based crash-investigation goal.

**What this document establishes.** This is the current scope and delivery sequence: captured input, BAP effects and native analysis, Rust reference, reports and investigation questions.

**Where to go next.**

- [BAP documentation audit](docs/Ariadne/bap-documentation-sync.md) — checks implemented BAP scope and the matching retained qualification.

- [Selected I5c address-wrap design](docs/Ariadne/i5c-address-wrap-design.md) and
  [W0–W5 plan](Plans/i5c-address-wrap.md) — the next fault-time arithmetic
  question; documentation is written, all implementation/qualification pending.

- [Selected I5b design](docs/Ariadne/i5b-zero-base-offset-design.md) and
  [implementation plan](Plans/i5b-zero-base-offset.md) — the delivered bounded
  zero-base-plus-displacement hypothesis, with B0–B5 implemented and corpus-qualified.
- [Active plans](Plans/README.md) — turn remaining work into explicit implementation and qualification steps.
- [Assurance decision](docs/Ariadne/semantic-assurance.md) — defines the BAP trust boundary and retired ISA-proof scope.

**What remains unresolved.** The [projection-admission extension](Plans/bap-projection-admission.md)
has P0–P3 implemented: v3 capabilities and conservative ordinary continuation.
Its [P4 aggregate/external acceptance](docs/Ariadne/bap-admission-checkpoint.md)
is incomplete; older v2 qualification does not transfer to the changed source.
The replacement BAP Windows capture is pinned and passes correctness. The current BAP latency policy is unlimited. Stage 2 native algorithms and capture integration are qualified on the exercised corpus; native analysis is the CLI default with explicit Rust rollback. The first fault-address question is implemented, and [native I4 performance qualification](docs/Ariadne/i4-performance-validation.md) meets the unchanged 2-second CLI limit for the exact re-pinned case. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

For the wider context, see the optional [documentation map](docs/documentation-map.md).

Ariadne produces evidence-bounded control-flow and data-flow results for crash
investigations using pinned BAP instruction lifting. Ariadne validates its own
transport, semantic projection, analysis and reports. The independent AMD64
instruction-step/Lean project and full-manual coverage goal are retired under
the [semantic assurance decision](docs/Ariadne/semantic-assurance.md).

## Investigation direction

The [investigation-layer design](docs/Ariadne/investigation-layer-design.md)
and [implementation plan](Plans/investigation-layer.md) propose domain questions
above binary-analysis primitives. The first slice explains possible fault-address
producers with captured evidence, alternatives and missing-evidence requirements.
The [first fault-address delivery](docs/Ariadne/investigation-validation.md) now
implements the question for both platform fixtures and the retained controlled
Linux capture. The later [Windows I4 re-pin](docs/Ariadne/i4-windows-repin-validation.md)
adds independently inspected real Windows producer evidence. All 17 gates pass,
while its historical 4,774.451 ms CLI median exceeded the unchanged 2,000 ms ceiling.
The [later native performance result](docs/Ariadne/i4-performance-validation.md)
meets that ceiling at 1,692.696 ms with the same capture/query. The
original Electron manifest remains historical; no executed path or root cause
is established.
BAP analysis-core migration remains separate from this product capability.
The [OCaml foundation qualification](docs/Ariadne/bap-ocaml-qualification.md)
records the bounded native bootstrap and full A0 decision. The [Stage 2 qualification](docs/Ariadne/bap-core-qualification.md) records the completed algorithms and passing default-adoption gate.
The [I5a zero-address assessment](docs/Ariadne/i5a-contracts.md) now evaluates
whether one selected scalar MOV access begins at zero under admitted Windows
AMD64 exception-context premises. Reader-owned context, a separate strict report
and explicit CLI modes are implemented. The [12-gate source/fixture validation](docs/Ariadne/i5a-validation.md)
passes for its historical sources. The native successor qualifies controlled
Windows I5a; the later [I4 performance result](docs/Ariadne/i4-performance-validation.md) meets its independent fixed budget; the original Electron case is historical.
The selected [I5b design](docs/Ariadne/i5b-zero-base-offset-design.md) and
[B0–B5 plan](Plans/i5b-zero-base-offset.md) define a distinct fault-time question:
is the encoded GPR base zero with a nonzero signed displacement? Its first
profile requires reviewed simple base/displacement decoded facts to agree with
BAP address evidence. B0–B5 are implemented, with [actual contracts](docs/Ariadne/i5b-contracts.md)
for machine-code debugging; [qualification](docs/Ariadne/i5b-validation.md) passes all
18 gates and separate source/fixture/controlled Windows timing criteria.
Historical null derivation and other hypotheses remain later work.
The next selected [I5c design](docs/Ariadne/i5c-address-wrap-design.md) and
[W0–W5 plan](Plans/i5c-address-wrap.md) assess the unsigned base plus signed
encoded displacement before modular reduction. All implementation stages are
pending. The first profile preserves lower-range fault admission, so it can
qualify upper-wrap/no-wrap cases while mathematical underflow remains unknown.
It introduces no historical-path, canonicality or root-cause claim.
The [native Windows Crashpad demo](docs/Ariadne/crashpad-demo-validation.md)
supplies real partial/full captures and correct numeric answers. Its historical
CLI median was approximately 1.82 s. The [native I5a refresh](docs/Ariadne/i5a-native-qualification.md)
now qualifies both timing budgets and both capture modes. A read-only dependency
snapshot prevents concurrent MirrorRust edits from invalidating qualification.

## Current checkpoint

Native BAP now owns production minidump recovery, may-reaching definitions,
slicing and supplied finite stateflow; Rust retains capture preparation,
transport/projection validation, questions and reports. The Rust analyzers
remain independent references and explicit rollback implementations. BAP is now the sole production
minidump semantic backend; LLVM MC remains an independent decode/control
reference. The semantic selector and LLVM effect fallback are removed. See the
[historical BAP-only delivery](docs/Ariadne/bap-only-removal-validation.md) and
[controlled Windows replacement](docs/Ariadne/bap-windows-repin-validation.md).
The replacement passed 17 implementation gates. The subsequent
[unlimited timing policy](docs/Ariadne/bap-unlimited-validation.md) removes latency
as an acceptance barrier while retaining correctness and source/tool checks. Legacy
LLVM effect rules and their source-bound tests remain historical/research
reference evidence. Native BAP recovery, dataflow, slicing and finite stateflow are implemented; [Stage 2 qualification](docs/Ariadne/bap-core-qualification.md) records passing aggregate acceptance and default adoption. The [minidump package](docs/Ariadne/modules/input.md) now provides captured-memory input and
local-start discovery for Windows/Linux AMD64. PE/ELF image and ELF core readers
remain deferred. A tool-produced [captured predecessor slice and versioned
investigator CLI](docs/Ariadne/stage-b-c-validation.md) are delivered. The
two historical Breakpad dumps still serve as independent crash-IP regressions.
A separate [controlled Chromium real-capture investigation](docs/Ariadne/priority-1-real-capture-validation.md)
now qualifies one possible predecessor slice with an exact matching-build
entry witness. It does not reconstruct the actual execution path or qualify
larger-workload performance.
The [Priority 2 effect review](docs/Ariadne/priority-2-effects-validation.md)
retains opaque calls on that path. [Priority 3 presentation](docs/Ariadne/priority-3-presentation-validation.md)
adds a readable text overview and Linux/Windows examples without changing
JSON or DOT semantics. [Priority 4 measurements](docs/Ariadne/priority-4-performance-validation.md)
record historical LLVM-backed qualification of a 98-instruction Windows
Electron capture and a measured optimization:
the CLI median falls from 3,846 to 1,788 ms against the fixed 2,000 ms budget,
with the visible schedule and report hashes preserved. This does not qualify
the current BAP path, whose current policy measures latency without a ceiling. The separate abstract-stateflow and supplied-IR paths pass
[Stage E generated conformance and report/CLI acceptance](docs/Ariadne/stage-e-completion.md). A
[proof-boundary and benchmark baseline](docs/Ariadne/stage-f-proof-and-performance.md)
is recorded without a universal refinement or optimization claim.

## Delivery path

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Input and decode | The pinned LLVM MC adapter and Windows/Linux minidump reader are delivered; PE/ELF images and ELF cores remain deferred by the current input scope. Readers must provide one immutable address-space snapshot, VA mapping, and verified byte provenance. | The same known bytes decode consistently from binary and dump views; missing or conflicting bytes remain explicit. VAs are never confused with file offsets. |
| 2. Control-flow recovery | Translate decoded control transfers into the core's instruction kinds, direct targets, fallthroughs, calls, returns, and unresolved-edge obligations. | End-to-end binary and dump fixtures exercise direct branches, calls, returns, sparse bytes, and indirect branches. Every edge has source instruction evidence; unresolved targets are visible, not silently omitted. |
| 3. Conservative effects | Typed BAP projection supplies `uses`, `may_defs` and justified `must_defs` to the native analysis. The independent LLVM reference checks decoding/control facts; unsupported BIL, memory and call effects stay explicit. Broader admitted semantics and alias precision require scoped evidence. | Slices retain every possible origin in representative crash paths. An unknown effect cannot become a definite overwrite, a no-op, or a known successor. Alias and call-summary assumptions are recorded. |
| 5. Investigator output | Text, Graphviz DOT, JSON v1 and a readable per-instruction minidump overview are delivered. The [separate Stage E result envelopes and optional CLIs](docs/Ariadne/stage-e-completion.md) are delivered. | Pinned Linux/Windows examples and the controlled Chromium case retain matching identities, edges, possible origins and uncertainty across formats. |

Phases 1–3 and 5 define the practical minidump workflow. The former Phase 4
instruction-step project is retired. The immutable [analysis contract](docs/Ariadne/bap-analysis-core-design.md)
and [Rust reference](docs/implementation.md) remain the correspondence boundary.
The CLI consumes completed native analysis through the shared `AnalysisView`.

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
[practical assurance queue](docs/Ariadne/practical-assurance-priorities.md)
lists the next release-facing work.
