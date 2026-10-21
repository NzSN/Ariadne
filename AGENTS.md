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
  [input](docs/Ariadne/file-reader-design.md#public-interface) and [BAP](docs/Ariadne/bap-analysis-core-design.md#backend-usage)
  module guides. BAP supplies production minidump semantics; LLVM MC supplies
  independent decode/control reference facts. Preserve explicit unsupported
  semantics instead of reintroducing automatic LLVM effect fallback.
- For fault-address explanations, read
  [investigation design and contracts](docs/Ariadne/investigation-design.md).
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

## Validation and tests

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

Validate the current source with executable tests; see [the test matrix](tests/README.md).
Keep models, generators, minimized regressions and small actual inputs under
tests or the owning model/replay directory. Do not retain qualification reports,
acceptance flags, raw logs, copied source trees or archives as repository evidence.
Generated run products belong under ignored target/work or system temporary
directories. Historical documentation may reference an immutable Git revision;
old passing flags never replace current tests. Name the exercised corpus and
unmet clauses; a partial tier does not satisfy a full acceptance gate.
Earlier backend performance measurements do not qualify a replacement backend.

The independent AMD64 instruction-step track is retired; its ISA specifications,
model documentation, coverage inventories and checkers have been removed.
Retained Lean sources are historical reference. Follow the
[BAP trust boundary](docs/Ariadne/semantic-assurance.md): pinned lifting is a
trusted dependency; Ariadne owns transport, projection, analysis and evidence
validation. Keep analysis-level TLA+ models, replay and mutation checks active.

## Design and implementation plans

Maintain one canonical document per feature design in `docs/Ariadne/`.
Keep its usage, contracts, source-review findings and dated validation summaries
in that document. Keep stage execution in `.agents/plans/`, executable validation
and small fixtures in tests, and disposable run products outside maintained source.

When creating or updating an implementation plan for an existing design, add
a direct relative link to the plan in the design document in the same change.
Name the stage if the plan covers only part of the design. Verify the link
resolves before finishing.

When editing documentation, maintain its `Context and follow-up` section:
explain its status, motivating problem, contribution, direct next reading and
unresolved limits in the document itself. Give direct origin and successor links
with their purpose; the map is optional. Update older wording when later work
resolves, supersedes or retires a question. See
[the documentation network](docs/documentation-map.md) and run
`python3 tools/check_doc_links.py` to check links and navigation coverage.
