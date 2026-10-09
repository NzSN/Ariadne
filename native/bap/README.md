# Pinned BAP instruction helper

## Context and follow-up

**Status.** Pinned production instruction-lifting helper. BAP workload timing
is unlimited. The separate [native analysis helper](../bap-core/README.md)
owns default minidump recovery, dataflow, slicing and finite stateflow;
Rust retains preparation, validation, reports and explicit reference/rollback.

**Why this document exists.** [Native boundary design](../../docs/Ariadne/bap-semantic-backend-design.md) isolates OCaml/BAP behind a typed process protocol.

**What this document establishes.** The helper hosts the pinned BAP runtime outside Rust and transports typed lifting results. Setup locks actual archive/library/plugin identities rather than relying on a release label.

**Where to go next.**

- [BAP documentation audit](../../docs/Ariadne/bap-documentation-sync.md) — current projection limits and exact retained source/tool bindings.

- [Unlimited timing policy](../../docs/Ariadne/bap-unlimited-validation.md) — records the user-authorized removal of the BAP latency ceiling and refreshed qualification.

- [Rust backend guide](../../docs/Ariadne/modules/bap.md) — connects the helper to minidump preparation.
- [Binding review](../../docs/Ariadne/bap-projection-source-review.md) — explains the measured accessor and projection assumptions.
- [Active Windows replacement](../../Plans/bap-windows-repin.md) — defines the authorized workload pin and independent capture evidence.
- [Replacement validation](../../docs/Ariadne/bap-windows-repin-validation.md) — records completed capture/pinning, passing implementation checks and the former latency limit.

**What remains unresolved.** The [native core qualification](../../docs/Ariadne/bap-core-qualification.md)
records passing clean-build, algorithm, replay and default-adoption checks on
the exercised corpus. Pinned lifting remains trusted; universal refinement and
packaged cross-platform release qualification remain open. The
[active I4 question](../../docs/Ariadne/i4-windows-repin-validation.md) meets
its fixed CLI budget in the later [performance qualification](../../docs/Ariadne/i4-performance-validation.md); controlled I5a has separate passing records.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

This Linux AMD64 host executable lifts reader-approved Windows/Linux
AMD64 instruction prefixes with BAP. It hosts the OCaml runtime through the
packaged typed C API. Rust stays outside that runtime.

```sh
python3 native/bap/setup.py
bash native/bap/build.sh
```

The setup downloads and extracts hash-pinned packages below ignored
`tmp/bap-setup/`. It requires Python, `dpkg-deb`, network access and a C++17
compiler. It does not install packages or modify existing opam switches.
Use `--check --runtime DIR` to verify an existing extraction, or set
`BAP_RUNTIME_ROOT` for the build. A matching libffi6 is extracted alongside
BAP; substituting the host libffi8 is unsupported. Child loader and cache
settings are isolated from LLVM MC 20.

The v2.5.0 asset label differs from the actual fingerprints:
`2.5.0-alpha+baa9022` for the CLI and `2.5.0-alpha` for the C runtime.
The lock qualifies these archive/library/plugin hashes. It does not establish
a clean stable-tag build or an upstream OCaml compiler version. Only the
`llvm` and `x86` providers are explicitly required, with the `legacy` lifter
passed through BAP's configuration argv. Other installed plugins are outside
the selected configuration.

The production entry point is `ariadne-bap-lift PLUGIN_DIR`; `--version`
probes the helper protocol. The [Stage 1 design](../../docs/Ariadne/bap-semantic-backend-design.md)
defines the bounded request stream, typed JSON AST, strict adapter and conservative
projection. No dump/executable paths or discovery policy enter this helper.
The packaged EXTRACT accessors are reversed; the encoder uses their measured
meaning, with independent alias tests and a native binding mutant.

```sh
python3 tests/bap/fixtures/make_corpus.py --check
python3 tools/check_bap_semantics.py
```

The default qualification command uses the bundled
[`crashpad-windows-checksum-98-v1` capture](../../evidence/Ariadne/bap-windows-workload-case.json).
The Linux benchmark verifies the archive and capture hashes before materializing
the native Windows partial dump. The active query requires exactly 98 decoded
starts with captured provenance and the independent RCX-producer witness.
Full Stage 1 exit and the Stage 2 prerequisite require valid release samples
(one warm-up and five measurements), complete source/tool bindings and passing
implementation gates. The [current policy](../../docs/Ariadne/bap-unlimited-validation.md)
has no latency ceiling. The earlier 10.67 s result remains a historical
measurement under its former 2 s condition.

```sh
python3 tools/measure_bap.py --output /new/workload-directory
ARIADNE_BAP_WINDOWS_DUMP=/absolute/path/to/replacement.dmp \
  python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --windows-dump /absolute/path/to/replacement.dmp \
  --output /new/explicit-workload-directory
python3 tools/measure_bap.py --skip-windows --output /new/implementation-directory
```

Explicit paths must match the active pin. `--skip-windows` requests an
implementation-only run and cannot qualify the workload. Workload v4 and
aggregate v5 use `windowsWorkload*` fields. The former `ARIADNE_PRIORITY4_DUMP`
selector is not used by BAP. Historical Priority 4 retains its original artifact;
the later I4-specific re-pin has its own manifest and bounded timing contract.
The earlier BAP capture campaign did not implement Stage 2; the later
[native core qualification](../../docs/Ariadne/bap-core-qualification.md) does.
