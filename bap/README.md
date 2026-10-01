# BAP minidump semantic backend

`ariadne-bap` is the sole production minidump semantic adapter. The root Rust analysis crate remains
free of external dependencies and unsafe code. BAP supplies typed BIL;
LLVM MC 20 remains the decoded-fact reference, and the existing Rust engine
performs recovery, reaching definitions and slicing.

Build the [native helper](../native/bap/README.md), then run the default BAP path:

```sh
cargo build --offline --locked --release --manifest-path input/Cargo.toml
input/target/release/ariadne-minidump input/tests/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 --seed-exception-rip \
  --bap-helper target/ariadne-bap-lift \
  --bap-runtime tmp/bap-setup/stable --output-dir tmp/bap-example
```

The semantic selector has been removed. `--bap-helper` and `--bap-runtime`
override the defaults resolved from `ARIADNE_BAP_HELPER` and `BAP_RUNTIME_ROOT`,
then the repository's native build/extraction paths. Every attempted BAP site
records provider/helper/runtime/AST hashes, projection, quality and gaps in all
three report formats. The compatibility `fallback` field is always null.
`external_lift` denotes exercised external semantics, not ISA-step acceptance.
Calls and returns stay opaque. Unsupported lifts stop conservatively without
using LLVM effect rules. `--decoder` is retained as an alias for the explicit
`--decoder-reference` option; it cannot select a semantic backend.

`Backend::prepare` consumes captured batches and checks LLVM decoded facts only.
One backend belongs to one snapshot/target. Call `Backend::finish` before
publishing a query to require a clean helper exit; drop also kills and reaps
an abandoned process. A fresh backend creates a fresh knowledge-base lifetime.
`Metrics` separates runtime validation, reference decoding, helper startup,
lift/transport validation and projection. The benchmark also times shutdown,
analysis and all three report formats.

The [design](../docs/Ariadne/bap-semantic-backend-design.md) and
[Stage 1 plan](../Plans/bap-integration.md#stage-1-bap-semantic-backend) define
admission and exit. The retained corpus has 41 exact byte cases with independent
effect expectations. It is deliberately finite: supported opcode names and
prefix guards do not imply universal ISA coverage. The native API source
review is [here](../docs/Ariadne/bap-projection-source-review.md).

```sh
cargo test --offline --locked --release --manifest-path bap/Cargo.toml -- --include-ignored
python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --windows-dump /path/to/pinned.dmp
```

The [Stage 1 backend-removal plan](../Plans/bap-only-semantics.md) records the
user-authorized default change. The original 98-instruction Windows qualification
and 2,000 ms condition remain pending.

Native tests are explicitly ignored until the pinned helpers/runtime are
available; the qualification tool invokes them and rejects missing prerequisites.
Stage 2 BAP-owned analysis remains separate.
