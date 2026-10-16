# Configurable guard-admission budgets

## Context and follow-up

**Status.** G5 completed on 2026-10-14 with fresh remote WSL checks and original caller retry. The hard guard-profile ceilings are released; independent transport and incomplete-coverage boundaries remain explicit.

**Why this document exists.** The [guard-evidence diagnosis](../../../evidence/Ariadne/guard-evidence-budget/20261014/README.md) found that the captured caller exceeds 4 MiB, while the existing profile rejects a larger configured budget before preparation.

**What this document establishes.** Ownership, implementation and validation gates for caller-selected finite guard budgets. The canonical contract remains the [justified branch design](../../../docs/Ariadne/justified-branch-pruning-design.md#configurable-guard-budgets).

**Where to go next.** Read the [original G0–G4 ledger](justified-branch-pruning.md) for predicate behavior, and [BAP integration](../../../docs/Ariadne/bap-analysis-core-design.md) for independent native transport bounds.

**What remains unresolved.** Removing guard-policy ceilings does not supply unlimited memory/time, close an incomplete candidate graph, add unwind semantics or qualify full-dump paths. Native initialization still has an independent 8 MiB frame limit; this stage changes guard budgets rather than the native transport protocol.

## Contract and ownership

Keep the seven current defaults. Allow callers to select higher or lower finite site, edge, update, evaluation, closure, evidence and deadline budgets. Preserve zero-budget stops, actual resource checks, conservative unknown decisions and exact budget binding in query/proof identities. Typed Rust unsigned fields remain finite. Native parsing reuses the existing checked unsigned-64 parser and unsigned comparisons, accepting the full matching range instead of introducing an OCaml signed-integer ceiling. Malformed, negative and unsigned-overflow inputs remain rejected.

Remove the native guard's separate absolute 8,192-site and 32,768-edge checks. The declared guard budgets and existing normalized recovery/transport contracts remain applicable. Predicate semantics and producer profiles remain unchanged; checker/helper source hashes bind the changed validator contract. Preserve historical qualification and diagnosis records as evidence of their original sources.

| Task | Owner / files | Dependency | Acceptance |
| --- | --- | --- | --- |
| G5.0 contract | Root: canonical design, this plan, plan index | Diagnosis | Scope and direct design/plan links recorded before runtime edits. |
| G5.1 validator and controls | Guard preparation worker: `src/bap/guard_admission.rs`, `native/bap-core/guard.ml`, `tests/bap/guard_admission_unit.rs`, `tests/input/bap_core.rs` | G5.0 | Above-default values accepted in Rust/native; unsigned parsing and overflow rejection consistent; actual budget exhaustion and proof tampering remain conservative. |
| G5.2 CLI configuration | Root: `src/bin/ariadne-minidump.rs`, applicable CLI tests | G5.0 | `--guard-admission-limits JSON` binds exact strict seven-field limits to guarded frame preparation and rejects incompatible usage. |
| G5.3 review | Independent transport explorer, root source review | G5.1/G5.2 | No default ceiling remains in the guard validator; independent protocol limits and unchanged proof requirements documented. |
| G5.4 remote qualification | Root: isolated remote WSL source/build, `evidence/Ariadne/guard-budget-configuration/` | G5.3 | Affected Rust/native tests plus root format/default/core-only/Clippy checks; source-bound artifacts retained; original dump retries distinguish actual configured budget stops from profile rejection. |
| G5.5 delivery | Root: canonical design, archive/index | G5.4 | Current usage/results reconciled; document links and layout pass; completed stage archived without altering old evidence. |

## Validation scope

Test each budget above its old default, small and zero budgets, full unsigned values and malformed/overflow controls, native admission with above-default configured limits and rehashed invalid evidence controls. Exercise CLI configuration through the native guarded fixture. All Cargo/native builds run on `windows-dev` WSL; the local machine runs only static source/document checks. Use task-private build outputs and preserve unrelated dirty work.

Retry the original captured caller with 32 MiB evidence under both the original discovery budgets and explicitly expanded discovery/guard budgets. Do not credit an unavailable listing as path enumeration or infer that removing one resource gate proves the next gate passes. Do not replace captured bytes or add query roots to obtain a passing result.

## Dated delivery, 2026-10-14

G5.0–G5.5 are complete. The [source-bound qualification](../../../evidence/Ariadne/guard-budget-configuration/20261014/README.md) retains 686 matching source/tool/document hashes and 86 archived files. Final remote checks pass: 14 guard controls, 189 default/46 core-only tests, format/Clippy, 12 native kernel/nine capture/two frame-path tests, strict contract controls and all 27 predicate-model configurations. Independent source/test review returned no concrete finding. Mutation seam checking is not a fresh mutation campaign.

The initial native CLI test requested three frames from a fixture that cannot recover them. It was corrected to exercise the guarded one-frame fixture and three-frame diamond separately; the failed attempt remains archived.

A 32 MiB configured evidence budget now passes profile validation. Original discovery stops conservatively at 4,096 instruction starts. Explicit expanded discovery prepares 4,764 candidate sites and a 9,001,701-byte report, but candidate coverage remains incomplete and MOVAPS stays unknown. Native initialization rejects the oversized request under its separate 8 MiB frame contract. No original-dump core steps or paths are qualified by this stage. Defaults, producer profiles, captured bytes, roots and older evidence remain unchanged.
