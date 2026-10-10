# Native BAP analysis core

## Context and follow-up

**Status.** ABI 2 native recovery, dataflow, slicing and finite stateflow are
implemented and selected by default in the minidump CLI. The
[Stage 2 qualification](../../docs/Ariadne/bap-core-qualification.md) records all
20 passing gates, rollback acceptance and the verified source-bound archive.
The later [P4 resume](../../docs/Ariadne/bap-admission-resume.md) records bounded
completion pages and current remote checks. The
[selected replacement](../../docs/Ariadne/real-capture-repin-79938.md) qualifies
active-corpus P4. The [user decision](../../evidence/Ariadne/bap-admission/p4-acceptance-20261010.json)
accepts that scope and excludes the remaining historical real-Linux clauses;
old coverage and six historical outputs remain unexercised.
Heavy work must remain remote.

**Why this document exists.** The [Stage 2 contract](../../docs/Ariadne/bap-analysis-core-design.md)
requires an isolated, pinned runtime for native analysis passes.

**What this document establishes.** SDK setup, native helper build, CLI selection
and qualification commands. The OCaml helper owns actual analysis state; it does
not call Rust analyzers to construct observations. The earlier C-interface probe
remains a separate historical facility check.

**Where to go next.**


- [Windows I4 performance qualification](../../docs/Ariadne/i4-performance-validation.md) — records the later native-core refresh and passing 98-start explanation workload under the unchanged 2-second limit, independent of the unlimited BAP policy.
- [Historical BAP documentation audit](../../docs/Ariadne/bap-documentation-sync.md) — earlier v2 inventory; the accepted v3 successor supplies current projection qualification.


- [Snapshot-based native qualification](../../docs/Ariadne/i5a-native-qualification.md) — explains the read-only MirrorRust dependency environment used by current core and controlled-I5a records.

- [A0 plan](../../Plans/bap-stage2-a0.md) — preserves the historical capability probe; the later OCaml foundation closed its SDK/state-exchange gap.
- [Analysis contract](../../docs/Ariadne/bap-analysis-core-design.md) — specifies
  the custom-pass interface and formal observation mapping.
- [Completion transport](../../Plans/bap-completion-pages.md) — preserves the
  per-frame budget while retrieving large completed recovery results.
- [Existing lifter](../bap/README.md) — remains the production lifting module.

**What remains unresolved.** Qualification covers the recorded workspace-local
corpus, not universal refinement or a packaged cross-platform release. Historical
A0 records describe the older bounded bootstrap. BAP lifting remains trusted.

For the wider context, see the [documentation map](../../docs/documentation-map.md).

## Historical A0 facility probe

Run the bounded A0 campaign:

```sh
python3 tools/check_bap_core_a0.py
```

The checker validates the Stage 1 prerequisite's complete current inventory,
tests envelope/attribution admission, builds the probe under `target/bap-core-a0/`
and starts two independent native processes. It records SDK/header limitations
and does not install or alter any OCaml switch.

Observed behavior: addresses above signed-i64 maximum round-trip correctly;
persistent term/graph updates retain old versions; multiple TIDs can share a
machine VA; two distinct edge labels between the same TIDs collapse to one edge.
The analysis's typed parallel-edge relation must therefore be retained separately.
The probe's `passed` field denotes these facilities, never a migrated analyzer.

## Isolated SDK and bootstrap

`setup-sdk.py` owns only `target/bap-core-sdk/`: its private opam root, frozen
repository and local switch. It uses OCaml 4.12.1 and the selected BAP source
revision, with exact dependency metadata in `sdk-packages.export`. Existing user
switches and the packaged Stage 1 runtime are separate. The two source archives
listed in `sdk.lock.json` must be present with their recorded digests. Acquisition
uses the private download cache; builds do not silently select newer packages.

```sh
python3 native/bap-core/setup-sdk.py
python3 native/bap-core/check-sdk.py
bash native/bap-core/build.sh
cargo test --offline --locked --test bap_core_bootstrap -- --ignored
python3 tools/check_bap_ocaml.py
```

The helper is `target/bap-core-native/ariadne-bap-core`; its adjacent manifest
binds the executable and handshake. `CoreConfig` and `CoreSession` in
`src/bap/core_session.rs` provide the intended Rust process transport. Select it with `--analysis-backend bap --bap-core-dir target/bap-core-native`;
`--analysis-backend rust` selects the reference/rollback engine. Operations and map-row shapes are specified in
the [analysis contract](../../docs/Ariadne/bap-analysis-core-design.md).

`recovery.ml` admits immutable premises and performs real model updates.
`project_state.ml` owns the reader-scoped BAP project and term attribution.
`main.ml` enforces framing, launch identities, sequence, action guards and
shutdown. Observations come from this state; the Rust reference is used only
by external acceptance tests. Normalized summary terms do not claim new lifting.
`NativeAnalyzer::finish` drives recovery through batches of at most 64 existing
actions, then validates ordered final-result pages and clean shutdown. Each frame
remains below 8 MiB; final results are bounded at 256 MiB. Ordinary per-action
replay and finite stateflow keep their original operation path.

The qualification checker runs source-bound native tests, hostile protocol and
SDK identity controls, a clean helper rebuild and seven real-code mutations.
It then refreshes affected Stage 1 and A0 checks, verifies every retained archive
entry, and records separate booleans for SDK, native state, transport and full A0
exit. A failing required check keeps `a0ExitPassed=false`; `stage2Qualified` is
always false for this bounded campaign.

## Complete Stage 2 checks

```sh
python3 tools/check_bap_core.py --output target/bap-stage2-qualification
```

`recovery.ml` implements every core action; `stateflow.ml` admits and propagates
the finite catalogue relation. `capture.ml` admits capture-only production input.
Generated replay uses `ARIADNE_REPLAY_BACKEND=bap` and an explicit helper directory;
the selected ports never run the Rust solver. The aggregate checker includes
native/generated tests, real-code mutations, five release workloads and existing
Stage 1/Stage E regression gates. The supplied LLVM IR engine remains separate.
