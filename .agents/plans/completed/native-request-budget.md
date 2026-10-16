# Configurable native request budget

## Context and follow-up

**Status.** T0–T4 completed on 2026-10-14 with source-bound remote WSL checks and successful larger original caller native initialization.

**Why this document exists.** The [G5 captured retry](../../../evidence/Ariadne/guard-budget-configuration/20261014/README.md) creates a 9,001,701-byte guard report but native initialization rejects its request under the fixed 8 MiB inbound limit.

**What this document establishes.** Paired host/native transport configuration, capability negotiation, test ownership and finite acceptance gates. The canonical contract remains [BAP native request limits](../../../docs/Ariadne/bap-analysis-core-design.md#configurable-native-request-limit).

**Where to go next.** Read the [completed guard-budget stage](guard-budget-configuration.md) for proof-budget configuration and [bounded completion transport](bap-completion-pages.md) for independent response/result limits.

**What remains unresolved.** Larger requests do not repair incomplete candidate coverage, justify MOVAPS alignment or qualify full-dump paths. Response, completion, normalized-input and investigation budgets remain separate. This stage configures one JSON request frame rather than adding an input paging protocol.

## Contract

Add `CoreConfig.max_request_bytes`, defaulting to 8 MiB. Accept positive finite representable unsigned values above and below the default, with no default-based ceiling. Every request's byte count includes its final newline. Store the exact chosen budget in the process-owning session and reject an oversized request before writing it. Protocol failures still poison and reap the session.

Keep `MAX_FRAME` and native outbound limits at 8 MiB for response framing. Native input reads use the separately configured request budget. Pass a nondefault choice at launch as `--max-request-bytes DECIMAL`; parse it through the existing checked unsigned-64 parser and compare sizes unsigned, preserving the entire supported range and avoiding an OCaml signed-integer replacement ceiling. Zero, malformed and overflowing options are rejected.

The additive ABI 2 capability fields are `configurable_request_bytes: true` and default `max_request_bytes: 8388608` in the build manifest. Runtime ready changes only `max_request_bytes` to the exact launch value. Rust validates that exact negotiated ready against the manifest plus its selected budget. Keep the recorded build manifest immutable in backend identity and record the effective transport budget separately. Legacy helpers without the capability work with the default; nondefault requests require a capable helper and fail explicitly otherwise. Operations, semantic inputs, query digests, observations and model actions remain unchanged.

CLI exposes `--bap-core-max-request-bytes N` and applies it to all native recovery, stateflow and frame-path configurations. Omission retains 8 MiB. Native semantics and proof validation run unchanged after a larger request is admitted.

## Tasks and acceptance

| Task | Ownership | Dependency | Acceptance |
| --- | --- | --- | --- |
| T0 contract | Root: this plan, canonical design, plan index | G5 diagnosis | Design and direct execution link recorded before edits. |
| T1 native reader | Native worker: `native/bap-core/main.ml`, `build.py` | T0 | Separate inbound/outbound budgets; exact capability/launch negotiation; newline-inclusive reader limits and full unsigned parsing. |
| T1 Rust session | Transport worker: `src/bap/core_session.rs`, `core_protocol.rs` | T0 | Configurable exact writer budget, legacy capability handling, immutable build identity, unchanged response bound and failure cleanup. |
| T2 CLI | Root: `src/bin/ariadne-minidump.rs`, CLI controls | T1 interface | Positive finite CLI budget reaches every native configuration; invalid and duplicate options reject before dump access. |
| T2 boundary/native tests | Test worker: `tests/bap/core_bootstrap.rs`, `core_analysis.rs`; root CLI tests | T1 interface | Exact and one-byte-over host/native boundaries; direct reader test bypassing host cap; capable/legacy negotiation and mismatch controls; a valid request above 8 MiB with small response. |
| T3 review and remote checks | Independent reviewer and root | T1/T2 | Root format/default/core-only/Clippy plus pinned native suites; hostile transport and unchanged response limits; source-bound artifacts and original dump native initialization with raised budget. |
| T4 delivery | Root: canonical docs, evidence, plan archive | T3 | Distinguish larger-request admission from incomplete coverage/path qualification; document links/layout pass; historical evidence preserved. |

All Cargo/native compilation runs in remote `windows-dev` WSL. Use task-private build directories and preserve unrelated changes. A failing test or timeout receives no acceptance credit. Keep the full original dump remote; retrieve bounded results and qualification artifacts only.

## Dated delivery, 2026-10-14

T0–T4 are complete. The [qualification record](../../../evidence/Ariadne/native-request-budget/20261014/README.md) retains 686 matching source/tool/document hashes and 35 archived files. Final remote checks pass: 191 default and 46 core-only tests, format/Clippy/layout, 17 native kernel tests (five new request controls), nine capture and two frame-path tests, plus 14 Python contract controls. Exact host/direct-reader bounds, full unsigned parsing, capability/legacy/ready mismatch, child cleanup, unchanged response limits and a valid input above 8 MiB are exercised. Independent review returned no concrete finding.

The original 4,764-site captured caller and 9,001,701-byte guard report are rejected under the 8 MiB default and initialize successfully under 32 MiB. No core steps or paths are run. Candidate coverage remains incomplete and MOVAPS stays unknown. Defaults, response bounds, semantic inputs/model actions, captured bytes/roots and old qualification records retain their original scope. Model source hashes match retained G5 evidence; no fresh model or mutation campaign is claimed.
