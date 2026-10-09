# Consolidate Rust sources and Cargo targets

## Context and follow-up

**Status.** Completed plan, archived; acceptance is limited to the recorded scope.

**Why this document exists.** [Motivating design](../../docs/implementation.md) defines the problem and contract this plan implements.

**What this document establishes.** The delivery consolidated Rust modules, binaries, tests and generated bindings into one root Cargo package, with isolated campaign build directories and retained output-equivalence checks.

**Where to go next.**

- [Delivery and follow-up](../../docs/Ariadne/rust-source-layout.md) — records what was exercised and which limits remain.
- [Active plan index](../README.md) — prevents completed steps from being mistaken for pending work.

**What remains unresolved.** The implementation steps below are archived, not a current task list. These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. Consolidation did not close the missing Windows artifact requirement or add new semantic capability.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Implement the user-requested source layout without changing analysis semantics.
The [implementation design](../../docs/implementation.md) links this plan directly.
The [delivery record](../../docs/Ariadne/rust-source-layout.md) documents the
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
their existing locations. The original Windows capture was missing at this layout checkpoint. The
later [I4 replacement](../../docs/Ariadne/i4-windows-repin-validation.md) closes
that artifact gap. The later [native performance qualification](../../docs/Ariadne/i4-performance-validation.md) meets the separate fixed budget; the consolidation record retains its historical scope.
