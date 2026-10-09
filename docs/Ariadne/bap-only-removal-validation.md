# LLVM semantic-backend removal

## Context and follow-up

**Status.** Historical backend-removal evidence from 2026-10-01. Later BAP workload and native Stage 2 qualification supersede its implementation checkpoint; the later [native I4 performance qualification](i4-performance-validation.md) meets its separate fixed CLI budget.

**Why this document exists.** [Completed removal plan](../../Plans/completed/bap-only-semantics.md) requires BAP-only production semantics without LLVM effect fallback.

**What this document establishes.** This records the removal of CLI semantic selection and automatic LLVM effect fallback. BAP became the sole minidump semantic producer while LLVM decode-reference checks remained.

**Where to go next.**

- [Current backend guide](modules/bap.md) — shows how to use and validate the resulting path.
- [Workload repair and source refresh](bap-windows-workload-validation.md) — supersedes this historical source inventory and clarifies the full-exit predicates.
- [Integration ledger](../../Plans/bap-integration.md) — records completed Stage 1 and native Stage 2 qualification, with remaining proof and release limits.
- [Investigation design](investigation-layer-design.md) — uses the resulting semantic evidence to answer a domain question.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. The later [native Stage 2 record](bap-core-qualification.md) qualifies its separate algorithms and adoption. The [active I4 replacement](i4-windows-repin-validation.md) closes the missing-artifact gap; the later [performance qualification](i4-performance-validation.md) meets its fixed CLI budget. Universal refinement and packaged release qualification remain open.

For the wider context, see the optional [documentation map](../documentation-map.md).

Requested **2026-10-01**. The [Stage 1 follow-up plan](../../Plans/completed/bap-only-semantics.md)
removes the LLVM semantic backend from the production minidump workflow.

BAP is now the sole provider for the CLI and ordinary `FileSnapshot::prepare`.
`--semantics-backend llvm|bap` is rejected with an explicit removal diagnostic.
`--bap-helper` and `--bap-runtime` override the normal environment/repository
configuration. `--decoder-reference` names the independent LLVM MC checker;
`--decoder` remains an argument alias for existing consumers.

The BAP adapter invokes `decode_captured_batch`, which produces byte/length,
operand and control facts without calling legacy effect rules. BAP provides all
admitted reads, possible writes and definite replacements. The old fallback
and rule-shape comparison are removed. Unsupported or inconsistent lifts
stop with opaque effects and explicit gaps; their `fallback` field is null.
Calls and returns retain opaque all-location effects and no definite kills.
The root LLVM effect-rule research/oracle and the separate supplied LLVM IR
path remain independent of production minidump semantics. Rust owned recovery, reaching definitions and slicing at this delivery.
The later [Stage 2 migration](bap-core-qualification.md) moves production minidump
analysis into the native helper; explicit Rust remains the reference/rollback.

The BIL corpus now contains **41 exact byte cases** and **30 admitted opcode
forms**, including source-reviewed immediate stores, dword load/store and TEST
forms used by the retained captures. The plain `90` NOP is the explicit
empty-BIL no-effect case. Decoded MOV operands also bind partial-register
self-moves: writing AL/AH/AX remains a definition even if its bits retain their
value. Stores never must-kill `memory:any`.

The 2026-10-01 source-bound removal record passed **16/16 gates** with
**93 source hashes stable at that run**; its nested Stage E regression passed
**12/12 gates** and binds 251 sources/artifacts.

That historical evidence includes independent native effect/binding checks, both Stage
B platforms, short/conflicting capture, missing seeds, report/CLI publication
and hash-pinned external crash artifacts. All **16 mechanical producer/adapter
mutants** are detected, including lost partial self-move definitions. Independent
TLC replay matches **99 observations across eight cases**, comparing all nine
state fields in order. The [machine-readable removal record](../../evidence/Ariadne/bap-only-removal-validation.json)
binds the gates and exact sources at that delivery. The
[derived-evidence manifest](../../evidence/Ariadne/bap-only-removal-evidence-manifest.json) binds retained
traces, logs and reports.

The release workload uses one warm-up and five measured repeats, with separate
startup/reference/lift/projection/analysis/render timing. Both Stage B fixtures
and the controlled NOT fixture keep their expected producer slices with no
legacy semantic fallback. The real Linux query retains **34 decoded sites,
45 edges, a 28-site slice and one obligation**. Per-site differences remain
visible: 25 projected sites, nine opaque calls/returns, one control disagreement,
and nine unattempted references. Samples, spread and peak RSS are recorded in
[bap-only-cli.csv](../../evidence/Ariadne/bap-only-cli.csv) and [bap-only-stage.csv](../../evidence/Ariadne/bap-only-stage.csv).

The user's explicit removal instruction authorizes the BAP-only default.
It does not qualify the missing original **98-instruction Windows capture**,
meet its **2,000 ms median condition**, satisfy Stage 2's prerequisite, or accept
an architectural ISA step. Stage D remains **0/49**. Earlier Stage 1 records
retain their historical source snapshots and rollout decisions.

For the current native-default CLI, build the analysis helper as well as the
lifter/reference. The original removal campaign used Rust analysis.

```sh
python3 native/bap/setup.py
bash native/bap/build.sh
python3 native/bap-core/setup-sdk.py
python3 native/bap-core/build.py --output target/bap-core-native
# Build the independent MC reference with the repo's matching LLVM headers.
bash native/llvm_mc/build.sh
cargo build --offline --locked --release --manifest-path Cargo.toml
target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 \
  --seed-exception-rip --output-dir tmp/bap-only-example
```

Current qualification uses `python3 tools/check_bap_semantics.py`, which
materializes the active 98-start [bundled workload](bap-windows-repin-validation.md).
`ARIADNE_BAP_WINDOWS_DUMP` selects an exact matching copy; the old
`ARIADNE_PRIORITY4_DUMP` no longer selects this workload. Implementation gates
and full Stage 1 exit remain distinct fields. I4 has its own separate pin and runner.
