# Guarded target resolution qualification — 2026-10-14

## Context and follow-up

**Status.** Implementation and finite source-bound qualification completed. The final original-dump run accepts both paired native queries and matches their full Rust states. Candidate recovery and complete incoming-state coverage are separate gates. The ninth original dispatch retains an explicit cyclic coverage residual.

**Why this document exists.** The [canonical design](../../../../docs/Ariadne/guarded-target-resolution-design.md) and [C0–C6 plan](../../../../Plans/completed/guarded-target-resolution.md) compose target recovery with guarded frame preparation on one immutable candidate graph.

**What this document establishes.** Remote WSL source/tool identities, positive and negative controls, retained failed controls, finite model checks and original-dump recovery. Original evidence identities remain distinct from the final qualification.

**Where to go next.** Read the canonical design for usage and proof contracts, the completed plan and the linked later loop qualification for closure of the former gate, and the [numeric table witness](../../indirect-target-resolution/dump03958-table-witness-20261014/README.md) for the independent candidate expectation.

**What remains unresolved.** The normal object-advancing loop at `0x00007ff77440da09` and the newly exposed dispatch at `0x00007ff77440dadd` retain incomplete incoming-state coverage. Semantic stops prevent whole-candidate guard coverage, so the initial MOVAPS stays unknown and frame paths remain unavailable. No executed history, root cause, full-ISA assurance or full target-closure acceptance is claimed.

**Later follow-up.** The [2026-10-15 loop delivery](../../loop-aware-target-resolution/20261015/README.md) closes DA09/DADD and the ninth incoming-coverage clause. This record retains the original eight-complete result and its identities. Guard coverage and frame paths remain open in the successor.

## Original snapshot and requested analysis

Dump `dump_03958DA4FCA844A786262A1053`, SHA-256 `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`; thread 23668; frame pair 1:0; NP10. The caller entry is `0x00007ff7744033a0`. Two frames recover; a later unsupported unwind operation remains outside the requested pair.

All nine candidate sets match the 370-entry/1,480-byte captured `.rdata` witness exactly: 64 distinct destinations, all 51 formerly absent starts attempted. Eight original table sites have complete certificates; DA09 retains its four witnessed targets with `cyclic-incoming-state`. No destination is supplied as a new root or inserted from the expected witness.

The reports retain `FrozenCapturedControlData` and the explicit Windows normal-call entry premise. Symbolic byte/short loads constrain possibilities without reading an unknown heap address or importing a crash-time register value into an earlier frame entry.

## Qualification scope

All Cargo, native SDK/helper, model, replay and mutation work ran in remote `windows-dev` WSL. Local work was source inspection, formatting, packaging and document/layout checks.

The final qualification exercises default and core-only tests, Clippy, native kernels/capture/frame reports, paired admission controls, the 8,193-site bounded helper-rotation control, symbolic/infeasible loop checks and all 273 actual infeasible receipts. Apalache typechecks the model; 19 finite TLC configurations check safety and fair termination. The [qualification record](qualification.json) retains exact gate counts: 218 default tests, 46 core-only, 17 native kernels, nine native capture cases, four native frame/report cases, paired preparation and bounded-session controls. Generated recovery/stateflow replay passes 330 observations; both wrong-digest controls dispatch zero observations.

Four isolated native implementation variants were built. Three receive behavioral mutation credit with passing originals and named admitted negatives. The paired-source-check variant remains rejected by the independent original-AST check and receives no mutation credit. Compile errors and timeouts receive no credit.

Retained RED controls demonstrate conditional-write double substitution, byte-loop loss of precision and native JSON object-order sensitivity before their corrections. Earlier unsuccessful qualification/probe runs remain historical diagnostics.

## Evidence layout and reproduction

The [artifact manifest](manifest.json) retains every gate log, 711 verified source hashes, native manifest, tool hashes, model output, original-dump paired reports and candidate/final requests. The final gate run is `artifacts/validation-20261014T120753`; the final dump run is `artifacts/dump-20261014T121127`. Large JSON files use lossless gzip. [qualification source-text relocations](source-text-relocations.json) retain standalone Rust reproduction source as `.rs.txt` without changing its bytes. `artifact-identities.ndjson` records original names, byte lengths and SHA-256 values; `lossless-compression.json` records preserved identities for the first diagnostic probe.

Use the saved task-private qualification/probe drivers with the pinned BAP runtime, LLVM reference and isolated native SDK. Select the helper directory and finite budgets recorded in the dump summary. Source/model/tool hash matches are prerequisites for reusing this evidence. Native response and frame-binding limits remain independent of the request and discovery budgets.
