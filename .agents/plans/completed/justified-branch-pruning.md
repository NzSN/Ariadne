# Proof-gated MOVAPS admission execution

## Context and follow-up

**Status.** G0–G4 implemented and finitely checked on remote WSL on 2026-10-14. Original dump retry is exercised but remains unavailable at a later XORPS typed-admission stop. Scope is the
proof-gated normal outcome in the [canonical design](../../../docs/Ariadne/justified-branch-pruning-design.md).
Unknown/refuted alignment remains stopped with explicit residuals. General
guarded exception graphs are excluded.

**Why this document exists.** The [vector-qualified dump retry](../../../evidence/Ariadne/bap-vector-registers/20261013/report.md)
still refuses MOVAPS's alignment exception. The user authorized implementing
the design, with all builds and heavy checks on remote WSL.

**What this document establishes.** Owned implementation stages, dependencies,
finite limits and acceptance gates. Preserve all current uncommitted vector
changes and original evidence identities; no commit/push is included.

**Where to go next.** Read the [design](../../../docs/Ariadne/justified-branch-pruning-design.md)
for premise/closure/identity semantics and the [BAP integration guide](../../../docs/Ariadne/bap-analysis-core-design.md)
for producer/native trust and qualification. The [model guide](../../../Specs/README.md)
owns analysis-model authority.

**What remains unresolved.** General exceptions, page/protection faults, XMM
unwind, large default runtime tables, full SIMD and successful full-dump path
enumeration are not guaranteed by this work. ABI facts are opt-in assumptions,
not inferred historical observations.

## Stages, dependencies and ownership

| Stage | Ownership | Dependency / acceptance |
| --- | --- | --- |
| G0 | Predicate-admission TLA+ model/configurations/checker and independent residue oracle/contract fixtures. | Freeze model and oracle before runtime edits; no unknown/vacuous/stale proof admission. |
| G1 | New `src/bap/guard_admission.rs` and dedicated tests: exact guard recognition, RSP transfers, candidate fixed point and receipt replay. | G0; all candidate predecessors included, opaque effects havoc, independent pending-guard transfer. |
| G2 | BAP preparation, capture materialization and frame/CLI opt-in coordinator. | G1 interface freeze; candidate closure precedes immutable final request; no added roots or LLVM effects. |
| G3 | Structured evidence, guard capture profile, native validation/handshake and report binding. | G1/G2 identities; exact premise/request/receipt binding and rejection of tampering. |
| G4 | Root checks, native/reference/codec parity, model replay/mutation and original dump retry. | G1–G3; all Rust/native/model builds remotely, source-bound records, explicit remaining gaps. |

Initial bounds: 4,096 candidate sites, 16,384 candidate edges, 131,072 residue
updates, 262,144 transfer evaluations, eight closure rounds, 4 MiB guard evidence
and a cooperative 1,000 ms predicate deadline. Existing byte/preparation bounds
remain separate. Exhaustion cannot publish a partial-prefix proof.

G2 initially exposes the explicit Windows normal-call entry assumption for
validated frame/function entry roots. Every unseeded or additional root starts
at top. Guard-enabled requests use their own producer/capture profile; ordinary
v4 behavior remains the default.

## Validation

Run the applicable root fmt/default/core-only/Clippy checks, portable independent
oracle and tamper tests, pinned producer/native capture parity, model checks and
focused mutations. Use private target directories and check free disk before
remote compilation; preserve failure logs and avoid copying historical bulk
evidence into build snapshots. Retry dump03958 with the same captured-only
frame pair and declared larger table/read budgets, adding only the named ABI
assumption and guard policy. A still-unavailable answer is recorded honestly.

## Execution checkpoint, 2026-10-14

All owned stages are complete within the selected first-delivery scope.
[Validation](../../../evidence/Ariadne/guard-admission/20261014/validation.json) binds
670 implementation/fixture/tool sources and the hash-verified remote artifacts.
Root/default/core-only/Clippy/layout, affected pinned native suites, 27 model
configurations, independent oracle, six guard mutants/seven observer pairs and
330 existing native replay observations pass. The Rust mutation campaign remains
source-bound to unchanged compiled subjects; native tests/replay were rerun after
the final opaque-data/empty-AST closure corrections. The complete local documentation
check passes; remote source-only navigation failures are retained separately.

The exact original frame pair was retried with default v4 and opt-in guarded
preparation. Guarded candidate discovery reaches XORPS at `0x00007ff7744075b3`,
then typed operand-width admission aborts before a final receipt/query. Returned
paths remain zero with unavailable coverage. The [canonical design's dated entry](../../../docs/Ariadne/justified-branch-pruning-design.md#implementation-validation-2026-10-14)
owns review corrections, usage and scope. No general SIMD, exception graph,
full-dump path, full-release or performance acceptance follows. No commit/push
was performed.
