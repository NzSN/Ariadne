# Pinned BAP instruction helper

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
python3 bap/tests/fixtures/make_corpus.py --check
python3 tools/check_bap_semantics.py
```

Full Stage 1 exit additionally requires the external hash-pinned Windows
capture. Pass its path through `ARIADNE_PRIORITY4_DUMP` or
`tools/measure_bap.py --windows-dump PATH`. Failure or unavailable prerequisites
cannot qualify Stage 2 or default promotion.
