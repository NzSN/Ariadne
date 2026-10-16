# Synchronize active specifications

## Context and follow-up

**Status.** S0–S2 source synchronization and bounded local checks complete on
2026-10-11; S3 remote qualification pending. The audit covers
17 active specification modules, five replay modules, configurations and check
entry points. Remote model qualification remains a separate prerequisite.

**Why this document exists.** The [formal-model guide](../../Specs/README.md)
still governs analysis, while recently implemented memory and frame-path
extensions outgrew their initial component models and checking instructions.

**What this document establishes.** Source owners, correction scope, preservation
requirements and validation tiers for synchronizing those existing contracts.

**Where to go next.**

- [Model ownership and current scope](../../Specs/README.md#current-model-ownership)
  — identifies implemented contracts and intentionally unmodeled boundaries.
- [Memory refinement](../../docs/Ariadne/memory-provenance-refinement.md)
  and [frame-path design](../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing)
  — own the affected feature contracts and pending qualification stages.
- [Assurance boundary](../../docs/Ariadne/semantic-assurance.md)
  — separates finite conformance, trusted lifting and universal refinement.

**What remains unresolved.** Apalache typechecking and exhaustive TLC/liveness
qualification require the task-owned remote environment. Bounded local parsing,
expression/trace probes and source tests do not satisfy that tier. No missing
address-wrap implementation/model or retired ISA work is introduced here.

## Audit and correction stages

| Stage | Scope | Completion criterion |
| --- | --- | --- |
| S0 | Inspect the 22 model modules, configurations, scripts and current source owners. | Record current/unchanged contracts, actual drift and explicit abstraction limits. |
| S1 | Synchronize typed-edge DFS, scan/visit/step/count stops and partial-result interpretation; add represented scalar constraints and stopping boundaries. | Current source operations have explicit model counterparts; no weakened invariant or fabricated writer exclusion. |
| S2 | Parse all models/configurations, exercise bounded direct evaluator probes and checker registration, run applicable Rust tests and check navigation. | Exact command/tool/source identities and failures are retained; unchanged runtime, corpus, historical evidence and architecture edits stay byte-identical. |
| S3 | Run the declared Apalache/TLC scripts remotely and refresh affected qualification. | Fresh source-bound remote type/safety/liveness records; earlier receipts remain historical. |

The [source-bound audit](../../evidence/Ariadne/specification-sync-20261011/report.json)
and [artifact manifest](../../evidence/Ariadne/specification-sync-20261011/evidence-manifest.json)
retain S0–S2 evidence: 22 parsed modules, 19 parsed configurations, 13 bounded
frame traces, 22 scalar probes and candidate/wrap controls, checker registration
and failure propagation with stub tools, plus 117 default/45 core tests and all
13 property tests. A zero-scan probe detected an unparenthesized Boolean stop
assignment during editing; the corrected model passes that probe.
All 934 existing runtime/native/corpus/Lean/evidence/architecture bindings and
the core/Stage E oracle bindings are preserved. No native or release refresh
is credited. No reachable remote host has been supplied for S3.

Core recovery, shared types, stateflow, supplied IR and their replay bindings
stay unchanged when their contract matches implementation. The effects model
only refreshes its producer/trust wording. Scalar checking uses four-bit words
and a representative two-operation chain limit; it does not enumerate 64-bit
machine states. Frame byte costs, hash/capture validation and actual clock
observations remain admitted external boundaries, exercised by separate source
and property tests.

## Remote commands

```sh
bash Specs/check-apalache.sh
bash Specs/check-effects.sh
bash Specs/check-input.sh
bash Specs/check-zero-base-offset.sh
bash Specs/check-memory-refinement.sh
bash Specs/check-frame-paths.sh
```

The shared runner registers bounded safety scenarios as well as discovering
all module typechecks. The specialized TLC scripts separately exercise fair
termination and finite-instance invariants. A source or comment hash change
invalidates exact-source reuse for the affected file; never rewrite an old
receipt to manufacture a match.
