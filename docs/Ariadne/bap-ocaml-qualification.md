# OCaml recovery foundation qualification

## Context and follow-up

**Status.** OQ0–OQ6 pass on 2026-10-03. The bounded OCaml foundation is
qualified: `a0ExitPassed=true`. This historical record predates complete Stage 2;
its production analyzer used Rust. See the [Stage 2 successor](bap-core-qualification.md)
for native algorithms and adoption acceptance.

**Why this document exists.** The [OCaml qualification plan](../../Plans/bap-ocaml-qualification.md)
closes the custom SDK, native state exchange and transport gaps left by the
[earlier A0 probe](bap-stage2-a0-validation.md).

**What this document establishes.** A bounded recovery bootstrap, its source
and process boundaries, and the evidence needed for each separate acceptance
claim. It does not change the production analyzer.

**Where to go next.**

- [Native module](../../native/bap-core/README.md) — build and launch commands.
- [Analysis contract](bap-analysis-core-design.md) — immutable input and wire shapes.
- [Stage 2 plan](../../Plans/bap-integration.md#stage-2-bap-analysis-core) — complete
  A1 recovery, A2/A3 algorithms, replay and eventual adoption.

**What remains unresolved.** This bounded record does not qualify complete
recovery, definitions, slicing, stateflow or product adoption. Their implementation
and current acceptance are recorded by the [Stage 2 successor](bap-core-qualification.md).

For the wider context, see the [documentation map](../documentation-map.md).

## Implemented scope

The private SDK uses OCaml 4.12.1 and BAP source revision
`baa902209ee4be975bdd8db7d1160b0a0ec2831f`. The package metadata snapshot and
resolved export are pinned separately from the installed SDK inventory. This is
a standalone executable; no custom plugin is loaded into the packaged lifter,
and binary ABI equivalence to that runtime is not claimed.

The helper owns its immutable recovery input, BAP project/term attribution and
mutable state. It validates the complete normalized recovery input, initializes
the nine modeled fields and applies one unsigned-lowest-address `Visit` per
successful action. Typed edge identity includes kind. The observer serializes
owned state. The Rust reference runs only in external tests.

The handshake advertises `initialize`, `advance:Visit`, `observe` and `reset`.
There is no completed-result capability. Reset acknowledges process shutdown;
the Rust caller requires clean exit and reaps failed or abandoned children.
The default production selection is unchanged.

## Evidence and decision

The [retained record](../../evidence/Ariadne/bap-ocaml-qualification.json) binds
199 source hashes. Its [archive manifest](../../evidence/Ariadne/bap-ocaml-evidence-manifest.json)
verifies all 327 entries, including build inputs, helper binaries, observations,
mutation diffs/assertions and nested regression records. Run
`python3 tools/check_bap_ocaml.py` to refresh it.
The checker records SDK smoke and substitution controls, two builds, full native
observations, Rust transport failures, seven mutation assertions, root checks,
fresh Stage 1 regressions and the refreshed A0 contract/probe.

Read the separate `sdkQualified`, `helperBuildQualified`,
`nativeStateExchangeQualified`, `transportLifecycleQualified` and
`bootstrapMutationChecksPassed` fields. `a0ExitPassed` additionally requires all
required gates and stable source identities. `stage2Qualified` remains false.
The earlier Stage 1/A0 records are preserved as historical evidence rather than
updated with replacement source hashes.

Ordinary Cargo tests skip the explicitly ignored native bootstrap tests. Their
qualification invocation includes `--ignored`. Finite fixture and mutation checks
do not establish a universal refinement proof or complete A1 recovery.

## Resolved formatting prerequisite

The first run failed `cargo fmt --all -- --check` on formatting in the separate
MirrorRust checkout. After explicit user approval, only
`/home/nzsn/Repos/MirrorRust/tests/protocol.rs` was formatted using its declared
Rust 2021 edition. Fresh root, effects, minidump, Stage E, Stage 1 and A0 checks
then passed. No failed aggregate was relabeled as passing.

The [earlier partial record](../../evidence/Ariadne/bap-ocaml-history/2026-10-03-format-blocked/bap-ocaml-qualification.json)
and its archive remain preserved. The current record binds 199 unchanged
Ariadne source hashes and verifies all 327 archive entries. The facility-only
A0 probe retains its narrower scope; this successor composes the SDK, native
state and transport evidence into the full A0 foundation decision.

## Recorded result

| Claim | Result |
| --- | --- |
| Isolated SDK and custom helper build | Pass |
| Native nine-field Init/Visit exchange | Pass |
| Rust transport and process lifecycle | Pass |
| Seven actual-code mutations | All rejected by the intended assertions |
| Second clean helper build | Identical executable hash and normalized observations |
| Source/tool stability and archive verification | Pass |
| Full A0 exit | Pass: every required gate and prerequisite passes |
| Complete Stage 2 | Not qualified |

The explicit native target ran six test groups. Coverage includes ordinary,
conditional, call, jump/self-loop, indirect and terminal summaries; missing bytes,
decode failures, unsigned high addresses, captured/file provenance, non-root
seeds, actual term attribution, rejected actions, fresh/concurrent sessions and
controlled process/identity/sequence failures. External Rust-reference checks
compare complete recovery observations. No phase completion is advertised.
