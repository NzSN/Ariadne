# Repository instructions

## Start with the relevant contract

Ariadne analyzes one immutable snapshot to recover local control flow, compute
possible value origins and explain captured fault-address dependencies.

- For project status or delivery scope, read [CHECKPOINTS.md](CHECKPOINTS.md)
  and [ROADMAP.md](ROADMAP.md). Treat dated entries as historical evidence;
  verify current source and validation records before making acceptance claims.
- For core analysis changes, read [the implementation guide](docs/implementation.md)
  and [the formal-model guide](Specs/README.md). TLA+ is authoritative for the
  modeled contract; Rust conformance tests and replay are separate evidence.
- For minidump or semantic-adapter changes, read the
  [input](docs/Ariadne/modules/input.md) and [BAP](docs/Ariadne/modules/bap.md)
  module guides. BAP supplies production minidump semantics; LLVM MC supplies
  independent decode/control reference facts. Preserve explicit unsupported
  semantics instead of reintroducing automatic LLVM effect fallback.
- For fault-address explanations, read
  [investigation contracts](docs/Ariadne/investigation-contracts.md).
  Reuse the completed core analysis and bind claims to the exact query and
  captured evidence.

## Analysis invariants

- Preserve snapshot identity and semantic virtual addresses throughout adapters,
  analysis and reports. Keep file offsets and graph identifiers distinct.
- Preserve captured-byte precedence and explicit holes/conflicts. Any file
  fallback requires the core's explicit trust contract; the production minidump
  reader remains capture-only.
- Entry points drive discovery; slice seeds select results without becoming roots.
- Keep call edges visible while local recovery and dataflow follow summary edges.
- Preserve old origins for possible writes; remove them only for justified
  `must_defs`. Keep unknown memory, call effects and control targets explicit.
- Report possible dependencies and their premises. Crash-time observations do
  not establish earlier branch outcomes, executed history or a root cause.
- Keep abstract stateflow and directly supplied LLVM IR analysis separate from
  minidump dependency analysis. Preserve structural CFG edges when classifying
  feasibility under supplied semantics.

## Rust layout

Keep Rust implementation, example and generated binding sources under `src/`,
and standalone test sources and fixtures under `tests/`. Use the root Cargo
manifest, lockfile and `target/` directory. After layout changes, run
`python3 tools/check_rust_layout.py`.

Give replay and mutation campaigns separate build subdirectories under `target/`;
shared executable names can otherwise cause one SUT's binary to be copied as another.

Keep the retired Lean reference tree at root `lean/`. Consult `Cargo.toml` for feature and
target definitions; core-only builds must retain no activated external crate
dependencies.

## Validation and evidence

For Rust behavior changes, run the affected tests and the applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
```

For native adapters, reports, investigation or model changes, also follow the
relevant module/model guide's qualification commands. Ordinary Cargo tests can
skip ignored native tests; report missing helpers, runtimes or capture artifacts
as unexercised prerequisites. Keep replay and mutation build outputs isolated.

Distinguish fresh tests, retained source-bound evidence and release qualification.
Check recorded source/tool hashes before relying on retained evidence after a
change, and preserve older records as historical results. Name the exercised
corpus and unmet clauses; a partial tier does not satisfy a full acceptance gate.
Earlier backend performance measurements do not qualify a replacement backend.

The independent AMD64 instruction-step/Lean track is retired. Its files remain
historical reference; do not add its milestones to active validation. Follow the
[BAP trust boundary](docs/Ariadne/semantic-assurance.md): pinned lifting is a
trusted dependency; Ariadne owns transport, projection, analysis and evidence
validation. Keep analysis-level TLA+ models, replay and mutation checks active.

## Design and implementation plans

When creating or updating an implementation plan for an existing design, add
a direct relative link to the plan in the design document in the same change.
Name the stage if the plan covers only part of the design. Verify the link
resolves before finishing.
