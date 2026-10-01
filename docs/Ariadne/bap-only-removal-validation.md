# LLVM semantic-backend removal

Requested **2026-10-01**. The [Stage 1 follow-up plan](../../Plans/bap-only-semantics.md)
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
path remain independent of production minidump semantics. Rust still owns
recovery, reaching definitions and slicing; this is not Stage 2 core migration.

The BIL corpus now contains **41 exact byte cases** and **30 admitted opcode
forms**, including source-reviewed immediate stores, dword load/store and TEST
forms used by the retained captures. The plain `90` NOP is the explicit
empty-BIL no-effect case. Decoded MOV operands also bind partial-register
self-moves: writing AL/AH/AX remains a definition even if its bits retain their
value. Stores never must-kill `memory:any`.

The final source-bound removal record passes **16/16 gates** with
**93 stable current source hashes**; its nested Stage E regression passes
**12/12 gates** and binds 251 sources/artifacts.

Current evidence includes independent native effect/binding checks, both Stage
B platforms, short/conflicting capture, missing seeds, report/CLI publication
and hash-pinned external crash artifacts. All **16 mechanical producer/adapter
mutants** are detected, including lost partial self-move definitions. Independent
TLC replay matches **99 observations across eight cases**, comparing all nine
state fields in order. The [machine-readable removal record](bap-only-removal-validation.json)
binds the final gates and exact current sources. The
[derived-evidence manifest](bap-only-removal-evidence-manifest.json) binds retained
traces, logs and reports.

The release workload uses one warm-up and five measured repeats, with separate
startup/reference/lift/projection/analysis/render timing. Both Stage B fixtures
and the controlled NOT fixture keep their expected producer slices with no
legacy semantic fallback. The real Linux query retains **34 decoded sites,
45 edges, a 28-site slice and one obligation**. Per-site differences remain
visible: 25 projected sites, nine opaque calls/returns, one control disagreement,
and nine unattempted references. Samples, spread and peak RSS are recorded in
[bap-only-cli.csv](bap-only-cli.csv) and [bap-only-stage.csv](bap-only-stage.csv).

The user's explicit removal instruction authorizes the BAP-only default.
It does not qualify the missing original **98-instruction Windows capture**,
meet its **2,000 ms median condition**, satisfy Stage 2's prerequisite, or accept
an architectural ISA step. Stage D remains **0/49**. Earlier Stage 1 records
retain their historical source snapshots and rollout decisions.

```sh
python3 native/bap/setup.py
bash native/bap/build.sh
# Build the independent MC reference with the repo's matching LLVM headers.
bash native/llvm_mc/build.sh
cargo build --offline --locked --release --manifest-path input/Cargo.toml
input/target/release/ariadne-minidump input/tests/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 \
  --seed-exception-rip --output-dir tmp/bap-only-example
```

Use `python3 tools/check_bap_semantics.py` for the current removal gate, and
supply `ARIADNE_PRIORITY4_DUMP` for the still-required Windows acceptance.
A passing removal record and a passing full Stage 1 exit remain distinct fields.
