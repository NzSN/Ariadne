# Synchronize active specifications

## Context and follow-up

**Status.** S0–S3 are complete within the [2026-10-20 finite remote profile](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync/20261020/README.md). The historical 2026-10-11 audit covers 17 active and five replay modules. The final S3 snapshot types 32 root modules and exercises the declared six-script/eight-core-TLC suite; this is model qualification, separate from runtime and universal refinement.

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
  — own the affected feature contracts and separately qualified product scopes.
- [Assurance boundary](../../docs/Ariadne/semantic-assurance.md)
  — separates finite conformance, trusted lifting and universal refinement.

**What remains unresolved.** Wider word widths, arbitrary facts/chains, universal Rust refinement, ISA semantics, runtime and release qualification remain outside this finite profile. Address-wrap W0 retains its separate model/oracle qualification; its two exact models received fresh global typing here, with no new address-wrap BMC or runtime credit. No required S3 gate remains in the declared suite.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Audit and correction stages

| Stage | Scope | Completion criterion |
| --- | --- | --- |
| S0 | Inspect the 22 model modules, configurations, scripts and current source owners. | Record current/unchanged contracts, actual drift and explicit abstraction limits. |
| S1 | Synchronize typed-edge DFS, scan/visit/step/count stops and partial-result interpretation; add represented scalar constraints and stopping boundaries. | Current source operations have explicit model counterparts; no weakened invariant or fabricated writer exclusion. |
| S2 | Parse all models/configurations, exercise bounded direct evaluator probes and checker registration, run applicable Rust tests and check navigation. | Exact command/tool/source identities and failures are retained; unchanged runtime, corpus, historical evidence and architecture edits stay byte-identical. |
| S3 | Run the declared Apalache/TLC scripts remotely and refresh affected qualification. | Fresh source-bound remote type/safety/liveness records; earlier receipts remain historical. |

The [source-bound audit](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync-20261011/report.json)
and [artifact manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync-20261011/evidence-manifest.json)
retain S0–S2 evidence: 22 parsed modules, 19 parsed configurations, 13 bounded
frame traces, 22 scalar probes and candidate/wrap controls, checker registration
and failure propagation with stub tools, plus 117 default/45 core tests and all
13 property tests. A zero-scan probe detected an unparenthesized Boolean stop
assignment during editing; the corrected model passes that probe.
All 934 existing runtime/native/corpus/Lean/evidence/architecture bindings and
the core/Stage E oracle bindings are preserved. No native or release refresh
is credited. At that date no reachable remote host had been supplied for S3; the later remote profile below supplies that separate tier.

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

## S3 finite remote qualification, 2026-10-20

The final lookup8 snapshot preserves all 1,118 pathname/hash bindings (17,032,829 bytes), inventory SHA-256 `22bf9f64c8de770d8656c22b0fbd93e615288835fb4d671dd79a3e99dfd1c8a4`. Pinned Apalache 0.62.2 and ordinary TLC pass 53 typecheck calls covering 32 root modules, 40 bounded calls, 24 TLC instances (19 original plus five equality/closure/coverage prerequisites), all six scripts, eight audited core configurations and five replay module types. All20 exact Memory partitions and canonical IdealSafety/CandidateSafety pass without narrowed domains, bounds or assumptions.

The full 120 guarded Java invocations reconcile as53 type +40 bounded +24 TLC +3 identity/version checks. Forty bounded calls retain30 `NoError` and 10 `ExecutionsTooShort` outcomes separately: every short case has one initial state, intended terminal Next and matching fresh complete TLC depth. Requested maximum bounds remain unchanged; short cases do not claim a full-length execution. The separate preflight has eight checks (one type, six TLC, one bounded), and three final ordinary-TLC fold/range controls also pass.

DOMAIN preserves admitted sequences including empty; official left folds preserve order for all finite sequences; residue representatives preserve the modular range for integer lengths. The eight-stop TypeOK domain is inductive and stronger only on unreachable arbitrary valuations. Canonical Memory definitions stay algebraic. A deterministic external solver copy changes only the admitted finite And/Forward operations, preceded by exact pointwise/whole-record/closure/full-Safety equality and complete20-class coverage checks. Adjacent pinned Apalache standard source/license makes ordinary TLC reproducible without alternate classes.

All source/tool/derived rechecks and archive member checks pass. Earlier encoding, syntax, timeout, stack, resource, partial-stop and packaging attempts remain historical with no success credit. The final suite reran every required gate. Exact sources, commands, terminal-depth audit and archive identities are retained in the [qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/specification-sync/20261020/README.md); historical 20261011 counts and receipts are unchanged.
