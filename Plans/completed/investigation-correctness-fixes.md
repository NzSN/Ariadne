# Investigation correctness fixes

## Context and follow-up

**Status.** Completed within the recorded fixture/Linux tier, 2026-10-02,
following the review of `12150b9`. All 17 investigation gates passed with stable
source hashes; the original-Windows qualification remains unavailable. The
[delivery record](../../docs/Ariadne/investigation-correctness-validation.md)
tracks exercised checks separately from full original-Windows qualification.

**Why this document exists.** The [investigation design](../../docs/Ariadne/investigation-layer-design.md)
requires evidence-bound answers and explicit partial results. Review found that
claim-budget exhaustion can break result validity, and that full Windows I4
acceptance does not enforce its documented total-query latency budget.

**What this document establishes.** Two bounded fixes, independent regression
cases, and acceptance criteria. The work preserves the analysis algorithms and
the distinction between implementation checks and real-workload qualification.

**Where to go next.**

- [Investigation contracts](../../docs/Ariadne/investigation-contracts.md) define the
  result invariants, limit behavior and timing requirements to preserve.
- [Workload design](../../docs/Ariadne/priority-4-workload-performance-design.md)
  explains why a budget result must refer to the exact artifact and query.
- [Broader investigation plan](../investigation-layer.md) tracks full I4 acceptance
  and later capabilities beyond these repairs.
- [Fix delivery](../../docs/Ariadne/investigation-correctness-validation.md) records
  implementation behavior, regression results and any unexercised tiers.

**What remains unresolved.** The original pinned Windows capture is still
required for fresh full I4 qualification. Synthetic regression tests can prove
the decision logic rejects invalid acceptance; they cannot qualify that workload.

The [documentation map](../../docs/documentation-map.md) is optional navigation.

## Reviewed failures

| Finding | Observed behavior | Required behavior |
| --- | --- | --- |
| Windows latency acceptance | A controlled workload record with a 9,000 ms Windows explanation-CLI median and a 2,000 ms budget produces `fullI4RealCaptureAcceptance=true`, with no missing clauses. | Full acceptance requires a valid, identity-bound Windows measurement within the unchanged 2,000 ms ceiling. |
| Explanation truncation | The existing fixture with `max_claims=1` returns `producer lacks its origin fact`. With `max_evidence=0`, it returns `selected site lacks evidence`. | Exhaustion returns a structurally valid truncated answer with an explicit budget gap, rather than an internally inconsistent result. |

The Windows reproduction mocked subprocess results; it was not a real capture
measurement. The truncation reproduction called the real Rust API using the
existing investigation fixture.

## 1. Enforce the Windows I4 latency condition

Primary files: [measure_investigation.py](../../tools/measure_investigation.py),
[check_investigation.py](../../tools/check_investigation.py), and focused Python
regressions under `tools/`.

1. Add failing tests for the measurement decision and its propagation into the
   acceptance report. Exercise the producer and consumer; testing only a helper
   that is never called by the runners is insufficient.
2. Derive the Windows result from `real-windows-98`, **explanation mode**, on the
   normal release CLI path. Use at least five measured repeats after warm-up.
   Preserve artifact/query binding, output repeatability and the fixed 2,000 ms
   threshold. Base-mode or explanation-phase-only timing cannot substitute.
3. Introduce an explicit Windows budget outcome: checked, valid sample count,
   measured median, required budget and target met. Validate numeric values as
   finite and nonnegative. Derive the decision from the measurements rather than
   trusting a caller-supplied success flag. Bind the Windows case manifest in the
   measurement source inventory alongside the Linux case manifest.
4. Require all of the following for `fullI4RealCaptureAcceptance`: passing
   implementation/regression gates, source/tool stability, successful pinned
   Windows query checks, valid measurement evidence and median at most 2,000 ms.
   Keep the existing exercised-tier `passed` distinct from full I4 acceptance.
5. Report unavailable capture, invalid/incomplete measurements and over-budget
   measurements as distinct unmet clauses. `missing` must remain nonempty when
   full acceptance is false due to an unmet Windows condition.
6. Advance the workload/acceptance report schema versions as needed for the new
   required decision fields. Old retained records without the required timing
   evidence must not grant full I4 acceptance. Preserve historical JSON/CSV bytes.

### Qualification regression cases

| Input | Full Windows I4 result |
| --- | --- |
| Capture absent; fixture/Linux tier passes | False; capture/qualification remains missing |
| Correct bound workload, five measured repeats, median 1,999 ms | True only if all other required gates pass |
| Same conditions, median exactly 2,000 ms | True only if all other required gates pass |
| Median above 2,000 ms, including the reproduced 9,000 ms case | False; latency condition reported unmet |
| Fast base CLI, slow explanation CLI | False; base timing cannot substitute |
| Missing Windows timing or an old record containing only `windows98Checked` | False; timing evidence required |
| Too few samples, negative/nonfinite timings, wrong workload/mode or artifact/query mismatch | Reject invalid evidence or retain incomplete qualification; never grant full acceptance |
| Fast timing with failed gates or changed source/tool identities | False |

**Exit criterion:** both measurement and aggregate regression tests enforce the
table, while the current missing-capture case stays explicitly partial. Passing
mock tests is recorded as decision-logic validation only.

## 2. Preserve valid explanations when limits are exhausted

Primary files: [explain.rs](../../src/investigation/explain.rs),
[validate.rs](../../src/investigation/validate.rs), and
[explanations.rs](../../tests/investigation/explanations.rs).

1. Add failing API regressions for `max_claims=1` and `max_evidence=0`, alongside
   the existing positive `max_evidence=1` truncation test. Add zero, one and exact
   boundary cases for each limit and combinations that exhaust more than one.
2. Make builder operations report whether they retained the required records.
   Admit a producer only when its required origin fact and any referenced
   evidence can be retained. Keep evidence/fact/claim dependencies consistent
   when a budget is exhausted, including exhaustion triggered by recording a
   producer's captured-instruction claim.
3. If the selected site's evidence cannot be retained, omit the selected address
   and origins that require it. Return `unavailable` with `truncated=true` and a
   budget gap. If a supported address and its evidence are retained but expansion
   is incomplete, return `partial` with `truncated=true`.
4. Keep zero budgets valid and explicit: publish the identity and available
   diagnostics without inventing claims or exceeding configured limits. Stop
   expansion when its prerequisites cannot be retained; do not keep adding
   dangling producers or dependencies after a budget failure.
5. Preserve `Explanation::validate()` as the structural guard. Do not relax
   origin-fact, selected-evidence, scope or reference checks to make malformed
   truncated output pass. Invalid queries must still return errors.
6. Update the contract to state the distinction between unavailable and partial
   truncated answers. Ordinary default-limit answers and their serialized output
   must remain unchanged when no limit is reached.

### Truncation regression cases

- Every accepted limit combination returns an explanation that passes
  `Explanation::validate()` and report serialization/round-trip checks.
- Exhaustion always sets `truncated`, retains a diagnostic budget gap and never
  reports `explained`.
- Every returned producer has its origin fact; all evidence/fact references
  resolve, and a selected address has retained selected-site evidence.
- Evidence, origin-link, dependency-node and claim counts stay within their
  respective limits. Test loops and shared producers so deduplication does not
  accidentally spend the budget twice or bypass it.
- Requests outside the query and invalid access indices retain their error
  behavior; resource exhaustion must not turn invalid input into success.
- Existing unconstrained fixture results preserve identities, claims, origins,
  alternatives and uncertainty across text, JSON and DOT.

**Exit criterion:** the two reproduced failures return valid bounded answers,
all limit invariants hold, and existing default-limit results remain unchanged.

## 3. Integration, evidence and delivery

Implement the qualification fix first, then the builder fix. They can be reviewed
separately; integrate only after each focused regression passes. No new semantic
backend, ISA proof work, admission coverage or analysis-core migration is needed.

Run the focused Python tests and Rust investigation/report tests, followed by:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_doc_links.py
```

Follow the investigation module's qualification procedure, including
`python3 tools/check_investigation.py`, for the affected native, report, replay
and mutation tiers. Preserve isolated campaign build directories. Exercise the
normal CLI publication path, and confirm malformed evidence still fails strict
validation. If required native tools or captures are unavailable, record the
unexercised tier explicitly instead of treating focused tests as a full pass.

Retain fresh fix-validation evidence under `evidence/Ariadne/` with source/tool
identities and exact exercised tiers. Update the contracts, design follow-up,
checkpoint and plan status only to the level actually validated. Keep the full
original-Windows condition open until its real capture is exercised successfully.
Commit and push require a separate user instruction.
