# Ariadne roadmap

## Context and follow-up

**Status.** Current delivery direction; dated qualifications remain scoped.

**Why this document exists.** [Project overview](README.md) sets the snapshot-based crash-investigation goal.

**What this document establishes.** This is the current scope and delivery sequence: captured input, BAP effects, Rust analysis, reports and investigation questions.

**Where to go next.**

- [Active plans](Plans/README.md) — turn remaining work into explicit implementation and qualification steps.
- [Assurance decision](docs/Ariadne/semantic-assurance.md) — defines the BAP trust boundary and retired ISA-proof scope.

**What remains unresolved.** Full original-Windows qualification is still open. The BAP analysis-core replacement has not started; neither selecting BAP nor passing a fixture closes those requirements. The first fault-address question is implemented, but full original-Windows I4 qualification remains open. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

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
Linux capture. Original-Windows acceptance remains partial; no historical path
or general root-cause proof is claimed.
BAP analysis-core migration remains separate from this product capability.

## Current checkpoint

The Rust core already recovers a local instruction-level CFG, computes
may-reaching definitions, and builds a backward data slice from fixed,
adapter-supplied instruction summaries. BAP is now the sole production
minidump semantic backend; LLVM MC remains an independent decode/control
reference. The semantic selector and LLVM effect fallback are removed. See the
[current BAP-only record](docs/Ariadne/bap-only-removal-validation.md). Legacy
LLVM effect rules and their source-bound tests remain historical/research
reference evidence. The BAP analysis-core replacement has not started. The [minidump package](docs/Ariadne/modules/input.md) now provides captured-memory input and
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
the current BAP path, whose original-Windows gate remains open. The separate abstract-stateflow and supplied-IR paths pass
[Stage E generated conformance and report/CLI acceptance](docs/Ariadne/stage-e-completion.md). A
[proof-boundary and benchmark baseline](docs/Ariadne/stage-f-proof-and-performance.md)
is recorded without a universal refinement or optimization claim.

## Delivery path

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Input and decode | The pinned LLVM MC adapter and Windows/Linux minidump reader are delivered; PE/ELF images and ELF cores remain deferred by the current input scope. Readers must provide one immutable address-space snapshot, VA mapping, and verified byte provenance. | The same known bytes decode consistently from binary and dump views; missing or conflicting bytes remain explicit. VAs are never confused with file offsets. |
| 2. Control-flow recovery | Translate decoded control transfers into the core's instruction kinds, direct targets, fallthroughs, calls, returns, and unresolved-edge obligations. | End-to-end binary and dump fixtures exercise direct branches, calls, returns, sparse bytes, and indirect branches. Every edge has source instruction evidence; unresolved targets are visible, not silently omitted. |
| 3. Conservative effects | Initial scoped rules and evidence are delivered; broader forms and precise aliasing remain. Supply `uses`, `may_defs`, and justified `must_defs` for the reaching-definitions and slicing core. Start with decoded operand and instruction metadata, then add reviewed rules for important register, flag, stack, and memory effects. | Slices retain every possible origin in representative crash paths. An unknown effect cannot become a definite overwrite, a no-op, or a known successor. Alias and call-summary assumptions are recorded. |
| 5. Investigator output | Text, Graphviz DOT, JSON v1 and a readable per-instruction minidump overview are delivered. The [separate Stage E result envelopes and optional CLIs](docs/Ariadne/stage-e-completion.md) are delivered. | Pinned Linux/Windows examples and the controlled Chromium case retain matching identities, edges, possible origins and uncertainty across formats. |

Phases 1–3 and 5 define the practical minidump workflow. The former Phase 4
instruction-step project is retired. The existing Rust core and its
[input contract](docs/implementation.md) remain the integration boundary.

## Scope and priority rules

- Prioritize instructions that appear on the control-flow and backward-slice
  paths of representative Chromium/Electron crashes. Direct control transfers,
  stack operations, common data movement, arithmetic, comparisons, and ordinary
  RAM accesses have immediate value; coverage grows with supported investigations.
- Use LLVM MC for decoding and available branch/operand metadata. Metadata is
  a starting point for conservative summaries, not proof of exact architectural
  effects. Keep indirect targets and uncertain memory aliases as obligations.
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
