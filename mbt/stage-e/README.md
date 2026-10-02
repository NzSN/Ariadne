# Stage E generated MirrorRust replay

## Context and follow-up

**Status.** Generated Stage E replay and mutation workflow.

**Why this document exists.** [Typed replay design](../../docs/Ariadne/stage-e-mirrorrust-design.md) specifies compiler-owned interfaces and independent result observations.

**What this document establishes.** This guide runs the generated stateflow and IR replay/mutation corpus and documents binding freshness, observer identity and regeneration boundaries.

**Where to go next.**

- [Full Stage E delivery](../../docs/Ariadne/stage-e-completion.md) — combines replay with native handoff and report acceptance.
- [Compatibility record](../../docs/Ariadne/installed-modelmirrors-compatibility.md) — provides the bounded installed-stdio evidence.

**What remains unresolved.** Finite conformance checks do not prove the Rust implementation correct for every valid request. A universal refinement proof remains open, and adapter facts remain premises. Stage E qualification also includes native handoffs and reports beyond replay alone.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

The optional package uses `../../../MirrorRust` (`~/Repos/MirrorRust`) and
compiler-generated `mirrorrust-v1` ports for the two independent Stage E engines.
The root analysis crate remains dependency-free. Application ports own actual
Rust analyzers; generated modules own codecs, dispatch and lifecycle. Registered
factories construct ports only after exact semantic-digest admission.

The [completion plan](../../Plans/completed/stage-e-completion.md) and
[design](../../docs/Ariadne/stage-e-mirrorrust-design.md) define this stage.
The original [first integration plan](../../Plans/completed/stage-e-mirrorrust-integration.md)
and its two-fixture record remain historical evidence.

## Checked campaign

`cases.py` deterministically generates 16 machine-state and 16 normalized IR
requests, including independently verifier-produced native text/bitcode inputs.
It never imports or executes the Rust SUT. Generated TLA input tables instantiate
the original specifications; only the machine-state schedule selects the lowest
enabled VA. The case-ID initializer selects an owned fixed request and resets a
fresh analyzer. Observations use actual state, never expected/previous reports.

The corpus covers joins, loops, multiple/empty roots and seeds, sparse/high
addresses, equal-valued distinct state IDs, incomplete semantics, terminal
alternatives, summary edges, phi alternatives, memory/call uncertainty and
exception edges. Every mutable field and declared derived view is compared.
The integer-address map uses explicit `{va, states}` rows with an exact inverse,
including empty entries. Native IR uses string-keyed dependency maps.

TLC checks safety and fair termination and exports completion witnesses for the
ordinary cases. Its integers cannot represent full-width u64 addresses, so the
high-VA case uses Apalache bounded safety and a complete four-transition witness
with exact integers. Only fixed input tables are specialized; the original
wrapper and model actions remain unchanged. Raw witnesses and projections stay
in `corpus/`, bound by the manifest. The type witnesses use the recorded local
Apalache version; normal replay does not silently regenerate anything.

## Run

```sh
python3 mbt/stage-e/run.py
python3 mbt/stage-e/run.py --mirror /path/to/ModelMirrors
```

The runtime defaults to installed `ModelMirrors` when available. Binding checks
retain the compiler selected by the [core harness](../README.md).
The gate checks freshness/preflight, repeats the whole corpus in one negotiated
binding per engine, compares exact action/pair counts and reset order, checks
pre-factory digest rejection and actual port Drop, and runs 15 mechanical
mutants of real engine sources with unchanged observers/bindings. Only genuine
`StepMismatch` results count; build, callback, timeout or protocol failures do
not. Per-mutant executables are retained separately from shared Cargo caches.

```sh
# Explicit oracle and binding regeneration; review changed locks and bytes.
python3 mbt/stage-e/prepare.py
python3 mbt/stage-e/prepare.py --check

# Full Stage E acceptance, including native handoffs and report/CLI checks.
python3 tools/check_stage_e.py
```

The full gate requires pinned LLVM 20.1.2 headers/library and Graphviz. Select
`LLVM20_INCLUDE_DIR`, `ARIADNE_DOT` and any Graphviz loader/plugin paths for a
non-system installation. `ARIADNE_REAL_DUMPS` selects the existing Breakpad
fixtures used by the minidump regression gate. Prepared archives in ignored
`tmp/llvm20-headers` and `tmp/graphviz-headers` are recognized locally.

[Retained completion evidence](../../evidence/Ariadne/stage-e-completion-validation.json)
establishes bounded conformance and report/CLI acceptance. ISA-step acceptance,
faithfulness of supplied semantic relations, universal Rust refinement and
MirrorGate restricted execution are separate boundaries.
