# Memory provenance refinement implementation

## Context and follow-up

**Status.** Source implementation added on 2026-10-11 from `8007236`, with
independent expectations, root/source checks and two finite pinned-runtime
probes. The section-5 integration now adds local model checking and compiled
component controls; remote model qualification, the complete dedicated mutation
campaign and full Scanner qualification remain pending. Full acceptance is not granted.

**Why this document exists.** The [design](../../docs/Ariadne/memory-provenance-refinement.md)
defines bounded candidate-writer assessment and per-value backward inference.
Its execution needs separate evidence for the mathematical rules, admitted
semantic receipts, product integration and source-bound qualification.

**What this document establishes.** Ordered implementation stages and gates for
the complete selected design. Existing effects, original explanations, query
roots and historical evidence remain the compatibility baseline.

**Where to go next.**

- [Section-5 frame integration](frame-question-investigation.md) — implemented P2/P5 frame/callee binding and local dependencies; M4 remains separate.

- [Design and implementation details](../../docs/Ariadne/memory-provenance-refinement.md#implementation-details)
  — input/output contracts, precision outcomes and source ownership.
- [Model guide](../../Specs/README.md) — active analysis-model authority.
- [BAP integration](../../docs/Ariadne/bap-analysis-core-design.md) — semantic
  admission, helper identities, native/default and Rust reference boundaries.

**What remains unresolved.** Remote model qualification, real-code mutations
and the bound Scanner case are pending. The local cached helper was historical;
a hash-verified accepted helper restored finite native parity. Heavy builds,
model checks, mutation and large-query work must run remotely. The previously
recorded remote endpoint is not currently reachable through SSH; local contract,
oracle and source work can continue without claiming a remote tier.

## Execution ledger

The [specification synchronization](specification-sync.md) updates M0's finite
component model for represented constrained values, expression-cap boundaries
and unavailable/candidate preservation. It preserves the original freeze and
receipts; remote qualification must bind the revised model's own hashes.

| Stage | Work | Acceptance |
| --- | --- | --- |
| M0 — independent contract | 784 range / 1,280 inverse expectations frozen; TLA+ source and remote check command specified. | Oracle and 2026-10-18 local Apalache/TLC checks pass; a sequence type annotation resolves the initial local typecheck failure. Remote checks remain unexercised. |
| M1 — symbolic assessment | Source implemented with full candidate coverage, bounded constant/common-base comparisons and immutable witnesses. | Finite oracle and source controls pass; broader qualification is M4. |
| M2 — transfers and backward values | Opt-in canonical BIL sidecars, receipt validation, exact/constrained/unknown scalar rules and path-scoped worklist implemented. | Source controls and captured RBX/RCX seed probe pass; no general joint-state or loop-instance inference. |
| M3 — product and reporting | Separate strict v1 codec, recomputation, JSON/text/DOT and explicit CLI mode implemented. | Finite probe preserves original JSON bytes and native/Rust assessments agree on one controlled capture. |
| M4 — qualification | Root default/core-only and all-feature Clippy checks pass in bounded local checks; accepted helper restored for finite probes. | Remote model/mutation and complete Scanner clauses remain pending. |

## Resume commands

Use the task-owned remote workspace and read-only MirrorRust snapshot for the
heavy campaign. Transfer only the reviewed source/test/model changes; preserve
raw captures as external artifacts. Bind fresh source/tool hashes before credit.

```sh
python3 tests/investigation/fixtures/memory_refinement_oracle.py
bash Specs/check-memory-refinement.sh
python3 tools/check_memory_refinement_mutations.py --remote \
  --output-dir target/memory-refinement-mutations-current
cargo test --offline --locked --test input_bap_backend memory_provenance \
  -- --ignored --nocapture
```

The mutation runner gives each mutant its own source/build directory and credits
only compiled behavioral test rejection, preserving compilation/prerequisite
failures without turning them into detections. Use a current manifest-verified
native helper; the older cached helper lacks completion-page capabilities.

## Source ownership

- `src/bap/refinement.rs`: normalized transfer extraction and canonical sidecar.
- `src/bap/prepare.rs`, `src/input/materialize.rs`: opt-in receipt retention.
- `src/investigation/memory_refinement.rs`, `backward_values.rs`: binding,
  candidates, range witnesses and numerical worklist.
- `src/input/investigation.rs`: capture-owned binding and fault observations.
- `src/reports/memory_provenance.rs`, `src/bin/ariadne-minidump.rs`: strict report
  and explicit product invocation.
- `tests/investigation/` and `tests/reports/`: standalone regressions and oracles.

## Required validation

Run affected independent oracle and Rust suites, layout and documentation checks.
Rust behavior changes require the root format/default/core-only/Clippy checks
specified by [repository instructions](../../AGENTS.md). Follow the native and
investigation gates from the owning feature documents. Isolate mutation/replay
build outputs under separate `target/` subdirectories. Retain missing prerequisites
and failures as such; no old performance or accepted P4 receipt qualifies these
changed sources automatically.
