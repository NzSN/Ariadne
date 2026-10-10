# P4 bounded native completion transport

## Context and follow-up

**Status.** Implemented and finite-corpus-qualified P4 transport clause, 2026-10-10.
The restored native helper rejects the Scanner query when a response exceeds
8 MiB. A 20-node, 1,000-location normalized request reproduces this in under a
second. This plan preserves that per-frame limit and the analysis equations.
Remote root/native/model/replay/mutation checks and large-result parity pass,
including twelve hostile page/lifecycle modes. Scanner now completes through
paging. The [remote record](../evidence/Ariadne/bap-admission/remote-20261010/report.json)
retains its original identities and explicit gaps. The later
[acceptance decision](../evidence/Ariadne/bap-admission/p4-acceptance-20261010.json)
accepts P4 on the selected Windows corpus and excludes the remaining historical
real-Linux clauses. Heavy work must remain on the remote machine.

**Why this document exists.** The [admission plan](bap-projection-admission.md)
requires completed, evidence-bound external queries. Its newly recovered paths
expose a transport limit rather than a new instruction-admission failure.

**What this document establishes.** Bounded native action batches and immutable
pages for the complete final response. No intermediate result is published.

**Where to go next.**

- [Native-core design](../docs/Ariadne/bap-analysis-core-design.md) — unchanged
  input, action, observation, attribution and clean-exit contracts.
- [Admission resume record](../docs/Ariadne/bap-admission-resume.md) — earlier
  prerequisite recovery and incomplete acceptance.
- [Admission plan](bap-projection-admission.md#p4--qualification-and-the-electron-investigation)
  — full qualification, fixed budgets and external-query acceptance.

**What remains unresolved.** Paging does not improve alias precision, prove
universal refinement or identify an executed path. Result-size/action/time
exhaustion still fails without publishing a partial analysis. The missing
historical controlled Linux capture is excluded from the accepted P4 scope;
its coverage and output hashes remain unexercised.

## Contract and ownership

1. Keep normal `step`/`advance`/`observe` exchanges and generated per-action
   replay unchanged. Advertise additional completion operations in the checked
   helper handshake. Stateflow remains on its existing path.
2. `run-batch` performs at most 64 existing deterministic recovery actions per
   exchange. It reports the actual action count and done status without emitting
   the growing full observation. The total one-million-action limit remains.
3. At done, freeze the ordinary complete response, including all nine state
   fields, attribution and missing seeds. Limit its total bytes to 256 MiB.
   Retrieve ordered hex-encoded byte pages with at most 256 KiB decoded bytes
   per page. Every wire frame remains below the existing 8 MiB limit.
4. Bind every progress/page/close exchange to session, snapshot, query, family,
   sequence, generation and action index. Validate contiguous offsets, byte
   counts, a stable content checksum, final envelope and state/attribution
   invariants. The checksum checks transport consistency; SHA-256 request and
   helper identities retain their existing trust roles.
5. `result-close` requires completed transfer and done state, acknowledges the
   same immutable result and exits cleanly. Rust publishes only after complete
   decoding, validation and clean child exit. A failed exchange poisons/reaps
   the session; no automatic Rust fallback is added.

Native ownership: `native/bap-core/main.ml` and `build.py`. Rust transport and
validation: `src/bap/core_protocol.rs`, `core_session.rs`, `core_adapter.rs`.
Standalone regressions remain under `tests/bap/`.

## Acceptance

- The fast large-response regression completes through paging and matches the
  Rust reference exactly; its ordinary observation exceeds 8 MiB.
- Missing, duplicate, reordered, corrupted, oversized and wrong-identity pages
  fail before publication. Operation/action counters and clean exit are checked.
- Existing per-action native replay, algorithm/boundary/capture mutations, root
  checks and owned report/phase parity pass on the changed sources.
- Exact Scanner/PreParser requests complete or preserve explicit remaining
  semantic/resource gaps. Quiet I4/I5 measurements retain their fixed budgets.
- Retain older failed records and seal only the tiers actually exercised.
