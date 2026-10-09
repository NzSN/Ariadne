# BAP minidump semantic backend

## Context and follow-up

**Status.** V3 projection/admission and ordinary opaque continuation are
implemented. The [execution checkpoint](../bap-admission-checkpoint.md) records
P0–P3 checks and incomplete P4/external qualification. Native analysis remains
default; historical v2 qualification is source-bound to its earlier snapshots.
BAP latency remains measured under the unlimited policy.

**Why this document exists.** [Backend contract](../bap-semantic-backend-design.md) defines the helper, typed transport and admitted effects.

**What this document establishes.** This guide explains backend configuration, snapshot-scoped helper lifetime, preparation, clean shutdown and per-site semantic evidence. It is the usage entry point for production lifting.

**Where to go next.**

- [BAP documentation audit](../bap-documentation-sync.md) — current implementation/evidence inventory and the pending projection-admission stages.

- [OCaml foundation qualification](../bap-ocaml-qualification.md) — records the completed A0 SDK, native state and transport gates.

- [Unlimited timing policy](../bap-unlimited-validation.md) — records the user-authorized removal of the BAP latency ceiling and refreshed qualification.

- [Native helper guide](../../../native/bap/README.md) — builds the pinned external runtime boundary.
- [Historical removal record](../bap-only-removal-validation.md) — records the original semantics-only delivery and its bounded corpus.
- [Native qualification](../bap-core-qualification.md) — identifies the delivered Stage 2 scope and later source-bound refresh.
- [Previous workload repair](../bap-windows-workload-validation.md) — retains the earlier evidence decisions and available-corpus refresh.
- [Replacement workload validation](../bap-windows-repin-validation.md) — records the new captured Windows input, passing implementation gates and its historical timing condition.
- [Replacement plan](../../../Plans/bap-windows-repin.md) — preserves the authorized capture recipe and its former bounded timing contract; the later unlimited policy controls BAP qualification.
- [Integration plan](../../../Plans/bap-integration.md) — separates completed migration from the pending projection-admission extension.

**What remains unresolved.** The isolated OCaml SDK and bounded Init/Visit transport now qualify the A0 foundation. Complete native recovery, dataflow, slicing, finite stateflow and generated replay are implemented; the [Stage 2 qualification](../bap-core-qualification.md) records passing aggregate acceptance and default adoption. The user has removed the active BAP latency ceiling; valid capture/correctness evidence and implementation gates remain required. Historical Priority 4, active re-pinned I4 and controlled I5a qualification retain their separate contracts.

For the wider context, see the optional [documentation map](../../documentation-map.md).

`ariadne::bap` is the sole production minidump semantic adapter. Core-only Rust
builds have no activated external dependencies; the library forbids unsafe code.
BAP supplies typed BIL; LLVM MC 20 remains the decoded-fact reference. The
standalone [native analysis helper](../../../native/bap-core/README.md) implements
recovery, reaching definitions, slicing and supplied finite stateflow. The Rust
analyzers remain available as independent reference implementations.

Set up the [native lifter](../../../native/bap/README.md) and
[isolated analysis SDK](../../../native/bap-core/README.md), then build and run
the default BAP path:

```sh
python3 native/bap-core/build.py --output target/bap-core-native
cargo build --offline --locked --release --manifest-path Cargo.toml
target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 --seed-exception-rip \
  --bap-helper target/ariadne-bap-lift \
  --bap-runtime tmp/bap-setup/stable --output-dir tmp/bap-example
```

The semantic selector has been removed. `--bap-helper` and `--bap-runtime`
override the defaults resolved from `ARIADNE_BAP_HELPER` and `BAP_RUNTIME_ROOT`,
then the repository's native build/extraction paths. Every attempted BAP site
records provider/helper/runtime/AST hashes, projection, quality and gaps in all
three report formats. The compatibility `fallback` field is always null.

Analysis selection is separate from instruction lifting. Build the isolated
analysis helper with `python3 native/bap-core/build.py --output target/bap-core-native`.
Select it with `--analysis-backend bap`; `--bap-core-dir` overrides
`ARIADNE_BAP_CORE_DIR`, which otherwise defaults to `target/bap-core-native`.
`--analysis-backend rust` selects the reference/rollback analyzer while retaining
BAP instruction semantics. Native base reports include a validated backend/build
receipt; explanation-only and assessment-only modes retain their existing
schemas. A failed native session produces an error without automatic fallback.
The [Stage 2 qualification](../bap-core-qualification.md) records default-adoption
acceptance and exact tested workloads.
`external_lift` denotes exercised external semantics, not ISA-step acceptance.
Calls and returns stay opaque. Unsupported control, empty lifts and guarded/unmodeled semantics stop
conservatively. Valid ordinary data-only gaps retain opaque continuation,
all-location possible effects and no definite kills; diagnostics remain visible.
Neither outcome uses LLVM effect rules. `--decoder` is retained as an alias for the explicit
`--decoder-reference` option; it cannot select a semantic backend.

`Backend::prepare` consumes captured batches and checks LLVM decoded facts only.
One backend belongs to one snapshot/target. It reuses one checked LLVM reference
process across captured batches; the standalone LLVM adapter remains one-shot.
Runtime validation hashes every compiled pinned file using bounded streaming
workers and retains both constructor and helper-start checks. Call `Backend::finish` before
publishing a query to require clean lifter and reference-decoder exits; drop also kills and reaps
an abandoned process. A fresh backend creates a fresh knowledge-base lifetime.
`Metrics` separates runtime validation, reference decoding, helper startup,
lift/transport validation and projection. The benchmark also times shutdown,
analysis and all three report formats.

The [design](../bap-semantic-backend-design.md) and
[Stage 1 plan](../../../Plans/bap-integration.md#stage-1-bap-semantic-backend) define
admission and exit. The current corpus has 58 exact byte cases with independent
effect expectations. It is deliberately finite: supported opcode names and
prefix guards do not imply universal ISA coverage. The native API source
review is [here](../bap-projection-source-review.md). Production uses
`bap-bit-provenance-v3` and typed capability admission. SUB64ri8, MOVZX32rm8,
XOR64rr and CMP8mi pass focused checks. The [P0–P4 ledger](../../../Plans/bap-projection-admission.md)
tracks implementation and remaining qualification separately; P4 has no passing
aggregate for this changed source snapshot.

```sh
cargo test --offline --locked --release --manifest-path Cargo.toml -- --include-ignored
python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --output /new/workload-directory
```

These commands run on Linux. A Windows workload is a Windows-origin minidump
input; it does not require Ariadne to execute on Windows. The qualification tool
configures the local Graphviz bundle when present; otherwise set `ARIADNE_DOT`
and its required library/plugin environment for native render tests.

The [active workload contract](../bap-windows-repin-validation.md) uses
`crashpad-windows-checksum-98-v1`, a native Windows partial capture of a controlled
checksum function with a loop and conditional diamond. The default benchmark
verifies the [pinned input bundle](../../../evidence/Ariadne/bap-windows-workload-case.json)
and materializes its dump locally. It requires exactly 98 decoded starts,
captured preparation evidence at every decoded site and the independent RCX
producer in the slice and all eight reaching byte origins. Workload schema v4
and aggregate schema v5 retain `windowsWorkload*` qualification fields, raw
release samples and complete source/tool bindings.

Full Stage 1 exit and the Stage 2 prerequisite require all implementation gates
and valid active Windows evidence. The [unlimited timing policy](../bap-unlimited-validation.md)
retains one warm-up and five measured samples without a latency ceiling.
Missing, skipped or malformed evidence cannot qualify. The earlier replacement
record's 10.67 s median and false exit flags remain historical results under its
former 2 s policy.

The historical bounded capture campaign measured reference decoding at
7,572.131181 ms, helper startup at 1,178.301727 ms and Rust core analysis at
69.614232 ms. Those phase samples describe that earlier pipeline; they do not
diagnose the later native-default I4 timing failure. The [active I4 result](../i4-windows-repin-validation.md)
retains its historical samples. The later [performance design](../i4-performance-design.md)
and [qualification](../i4-performance-validation.md) measure and close this exact-query timing clause.

To use an explicit copy of the same pin, or deliberately run only the available
implementation workloads:

```sh
ARIADNE_BAP_WINDOWS_DUMP=/absolute/path/to/replacement.dmp \
  python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --windows-dump /absolute/path/to/replacement.dmp \
  --output /new/explicit-workload-directory
python3 tools/measure_bap.py --skip-windows --output /new/implementation-directory
```

`ARIADNE_PRIORITY4_DUMP` no longer selects BAP's workload. The old Priority 4
manifest remains historical. That earlier BAP authorization did not repin I4;
the later [I4-specific replacement](../i4-windows-repin-validation.md) now uses
the same raw 98-instruction capture with an independent bounded timing contract.

The [Stage 1 backend-removal plan](../../../Plans/completed/bap-only-semantics.md) records the
user-authorized default change. The [replacement plan](../../../Plans/bap-windows-repin.md)
separately records the user's authorization to generate and pin a new BAP input
after confirming the original dump no longer exists.

Native tests are explicitly ignored until the pinned helpers/runtime are
available; the qualification tool invokes them and rejects missing prerequisites.
Stage 2 BAP-owned analysis remains separate.
