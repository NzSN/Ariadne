# Execute the complete BAP analysis-core migration

## Context and follow-up

**Status.** A1–A6 implementation is complete. The explicit-native candidate
passed all 19 aggregate gates on 2026-10-04 with stable source/tool identities
and a verified archive. The [qualification guide](../docs/Ariadne/bap-core-qualification.md)
records the final default-adoption verdict for the exact implemented sources.

**Why this document exists.** The [whole integration plan](bap-integration.md#stage-2-bap-analysis-core)
defines milestones; the user requested execution of all remaining Stage 2 work.

**What this document establishes.** Concrete implementation ownership, sequencing,
validation and the adoption gate for the [analysis design](../docs/Ariadne/bap-analysis-core-design.md).

**Where to go next.**

- [Native module](../native/bap-core/README.md) — isolated SDK/build entry point.
- [Core model](../Specs/Ariadne.tla) and [stateflow model](../Specs/AriadneMachineState.tla)
  — authoritative input, action, observation and result contracts.
- [A0 qualification](../docs/Ariadne/bap-ocaml-qualification.md) — historical entry evidence.
- [Integration plan](bap-integration.md) — receives the final A1–A6 verdict.
- [Qualification guide](../docs/Ariadne/bap-core-qualification.md) — final acceptance record, measured workloads and limits.

**What remains unresolved.** The final aggregate record must independently
qualify default native selection and explicit Rust rollback. Implemented checks
do not themselves establish acceptance; consult the linked qualification guide
and its source-bound report. BAP lifting remains trusted and universal refinement
and cross-platform packaged release qualification remain separate.

For wider context, see the [documentation map](../docs/documentation-map.md).

## Fixed implementation decisions

- Extend `native/bap-core/`, keeping the packaged Stage 1 lifter separate.
  Rust owns capture reading/preparation and evidence validation; the OCaml
  process owns recovery, dataflow, slicing and finite stateflow transitions.
- Preparation freezes the candidate domain and semantics. Native recovery starts
  from entry points and independently constructs the accepted typed graph.
  Seeds never become roots. Production input binds each admitted machine term
  to consumed bytes and Stage 1 evidence; no helper-side image scan is enabled.
- Evolve the experimental helper ABI explicitly. Named `advance` remains the
  replay interface; a native `step` selects exactly one enabled action for product
  orchestration. `finish` remains read-only and requires `done`.
- Keep per-process snapshot/query/family isolation and fail-closed transport.
  A shared completed-analysis view admits native results to reports/investigation
  without executing the reference Rust solver to manufacture native state.
- Supplied LLVM IR remains a separate path. Existing IR replay remains a
  regression gate; it does not become credit for a migrated machine-code pass.
- The existing unlimited BAP workload timing policy applies. Measure latency
  and retain operational watchdogs; do not invent a new acceptance ceiling.

## Execution sequence and exit checks

| Stage | Concrete work | Required evidence |
| --- | --- | --- |
| A1 | Complete recovery/phase boundary in `recovery.ml`; add captured evidence admission and reader-scoped term attribution; extend the typed Rust session/facade. | Full Init/Visit/FinishRecovery comparisons, holes/conflicts, root/seed separation, calls, parallel edges, high VAs, capture identities and reset isolation. |
| A2 | Implement native reaching-definition fixed points, weak/must writes, entry origins and simultaneous slice expansion. Return a completed native result through a strict Rust adapter. | Every action and all nine fields match independent fixtures and the Rust reference; include loops, weak memory, opaque calls, missing seeds and phase-guard negatives. |
| A3 | Implement `stateflow.ml` with complete finite-input admission, ID-preserving propagation, terminal outcomes and three-way edge classification. | Full observations for equal-valued distinct IDs, joins/loops, incomplete/unreached sources, terminals and invalid frame/status relations. |
| A4 | Add native-helper MirrorRust ports and generated core/stateflow campaign runners under `src/mbt/` and `mbt/`; leave generated sources compiler-owned. | Actual native Init/action/observe/reset per generated trace; required fixture/action/pair coverage and negative digest controls. Native state never comes from expected data or reference execution. |
| A5 | Add isolated OCaml/transport/projection mutations; integrate `--analysis-backend rust\|bap`, capture binding, reports and investigation using completed-analysis interfaces. | Intended behavioral mismatches with unchanged observers; independent JSON/text/DOT parsing and backend/identity binding; same-input product differentials. |
| A6 | Add `tools/check_bap_core.py`, verify a second clean build, run root/native/formal/product gates and measured workloads; retain archive and manifest. Then adopt BAP as the CLI default and rerun default/explicit Rust rollback acceptance. | Stable complete source/tool/corpus inventories; every required gate passes; current-source archived evidence verifies. Only then set `stage2Qualified=true`. |

Each stage gets focused tests before integration. The final campaign runs root
format/default/core-only tests, all-feature Clippy, Rust layout and documentation
checks, existing Stage 1/Stage E regressions, native generated replay, mutations,
capture/report/investigation tests and workload comparisons. Build, replay and
mutation outputs use distinct directories under `target/`.

## Evidence and progress

The verified A0 entry record is copied to `tmp/bap-stage2-execution/a0-entry.json`.
Existing retained records remain historical when implementation hashes change;
they are never rebound to new sources. The final Stage 2 record and readable
qualification guide will list individual A1–A6 results, exact corpora, native
tool identities, unavailable prerequisites and the separate adoption decision.

These checkboxes record implementation delivery; acceptance is controlled by the
final report linked from the qualification guide.

- [x] Verify and preserve qualified A0 entry baseline.
- [x] A1: complete scoped recovery and capture binding.
- [x] A2: native reaching definitions and slicing.
- [x] A3: native finite stateflow.
- [x] A4: generated native-helper replay.
- [x] A5: mutations and product integration.
- [x] A6: aggregate qualification, default adoption and explicit rollback checks.

The candidate aggregate passed root/native tests, 168 recovery and 162 stateflow
observations, twelve native algorithm mutations, boundary controls, complete
Stage 1/Stage E regressions and five release workload comparisons. The candidate
record deliberately has `stage2Qualified=false`; the final run must verify the
new default independently. The Stage 1 workload runner explicitly selects Rust,
while Stage 2 measures native, reference and default CLI paths separately.
