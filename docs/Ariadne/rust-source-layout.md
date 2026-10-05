# Rust source layout consolidation

## Context and follow-up

**Status.** Delivered source consolidation and retained equivalence evidence.

**Why this document exists.** [Completed layout plan](../../Plans/completed/rust-source-layout.md) requires one Cargo package without changing analysis behavior.

**What this document establishes.** The delivery consolidated Rust modules, binaries, tests and generated bindings into one root Cargo package, with isolated campaign build directories and retained output-equivalence checks.

**Where to go next.**


- [2026-10-05 Windows I4 replacement](i4-windows-repin-validation.md) — supersedes the older missing-artifact obligation with an independently inspected active case; correctness passes and the unchanged CLI budget remains unmet.

- [Implementation guide](../implementation.md) — maps the consolidated modules to their responsibilities.
- [Repository rules](../../AGENTS.md) — preserve source layout and isolated campaign build directories.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. Consolidation did not close the missing Windows artifact requirement or add new semantic capability.

For the wider context, see the optional [documentation map](../documentation-map.md).

Delivered **2026-10-02**, following the
[source-layout plan](../../Plans/completed/rust-source-layout.md).

The repository now uses one Cargo package, one root manifest and lockfile, and
one build-artifact root. All 86 tracked Rust files are below `src/` or `tests/`.
The former BAP, input, IR, investigation, reports and benchmark directories are
replaced by modules, binaries, tests and module documentation.

```text
Cargo.toml
Cargo.lock
src/
  lib.rs                   analysis library and feature-gated modules
  bap/                     BAP lifting and projection
  input/                   minidump reader and query binding
  ir/                      supplied LLVM IR adapter
  investigation/           typed fault-address explanations
  reports/                 codecs and report renderers
  bin/                     CLIs and benchmark entry points
  examples/                Rust examples
  mbt/                     replay ports and unchanged generated Rust
tests/
  bap/ input/ ir/ investigation/ reports/ mbt/
  fixtures/                core effect fixtures
target/                    all Cargo/native build artifacts
```

Use `ariadne::{bap,input,ir,investigation,reports}` for the former package APIs.
Default features enable both investigator CLIs. `--no-default-features` retains
the standard-library-only core; `bench`, `validation` and `mbt` enable optional
benchmark, model-observer and MirrorRust replay tools. Benchmarks retain their
existing allocation counters; the library forbids unsafe code.

Run these commands from the repository root:

```sh
cargo build --offline --locked --release
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py

target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 \
  --explain-fault-address 0x401006 --memory-access 0 \
  --explanation-only --format text
```

Integration targets have distinct names such as `bap_native`, `input_native`,
`input_investigation`, `ir_native`, `investigation_explanations` and
`stage_e_bindings`. Fixture generators, validation inventories, isolated SUT
copies, compiler freshness checks and documentation use the new paths.
Replay and mutation campaigns build in separate root `target/` subdirectories,
preventing their executable names from colliding with production builds or
other campaigns. Release CLI tests and measurements use the default production
feature set; optional benchmark builds select their own binary explicitly.

The [source-bound validation](../../evidence/Ariadne/rust-source-layout-validation.json) records all
16 investigation gates and the nested 12-gate Stage E regression. Thirty
text/JSON/DOT reports are byte-for-byte identical to the preserved previous
executables, covering Linux/Windows fixtures, the NOT chain, the controlled
Linux capture, and supplied text/bitcode IR. All 16 BAP and 11 investigation
mutants are detected. Generated Stage E replay retains 64 traces, 326 matched
observations and 15 detected engine mutants; core replay retains 12 traces,
168 observations and five detected mutants.

The three generated Rust bindings, captured fixtures, BAP corpus and supplied IR
fixtures retain their original bytes. The engine/model source, formal
specifications and root `lean/` contents are unchanged. The merged lockfile
introduces no external package/version identities beyond the previous locks.
The [evidence manifest](../../evidence/Ariadne/rust-source-layout-evidence-manifest.json) binds the
[derived reports and logs](../../evidence/Ariadne/rust-source-layout-evidence.tar.gz).

Earlier validation JSON and evidence archives retain their original source
paths and hashes as historical records. At that layout checkpoint, full I4 qualification still required
the unavailable original Windows capture. The [later re-pin](i4-windows-repin-validation.md)
closes that gap and retains an unmet fixed timing condition; this consolidation adds no ISA-step
acceptance, execution-history proof or root-cause capability.
