# Consolidate Rust sources and Cargo targets

Implement the user-requested source layout without changing analysis semantics.
The [implementation design](../docs/implementation.md) links this plan directly.
The [delivery record](../docs/Ariadne/rust-source-layout.md) documents the
implemented layout and source-bound validation.

1. Replace the separate Rust package manifests with one root Cargo package.
   Keep analysis, BAP, input, IR, investigation and reporting as modules in `src/`.
   Move CLI and benchmark entry points under `src/`, and integration tests and
   captured fixtures under `tests/`. Keep generated MirrorRust bytes unchanged.
2. Build both investigator CLIs by default. Keep benchmarks and replay tooling
   behind optional features; retain a dependency-free core build through
   `--no-default-features`. Use the root `target/` for repository builds.
3. Update native fixture references, validation inventories, isolated mutation
   builds, binding freshness checks, documentation and examples. Keep historical
   validation records unchanged and retain a fresh record for the new layout.
4. Verify formatting, default and core-only tests, all-feature Clippy, native
   minidump/IR/explanation acceptance, unchanged generated bindings, replay and
   mutation checks. Compare representative reports with the previous build.

All tracked Rust files must be below `src/` or `tests/`; there must be one tracked
Cargo manifest and lockfile. Formal specifications and native helpers retain
their existing locations. The missing original Windows capture continues to
limit full I4 qualification.
