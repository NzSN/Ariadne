# Stage 2 A0: contract and native capability evidence

## Context and follow-up

**Status.** Historical first A0 contract/probe result from 2026-10-03. Its
`a0ExitPassed=false` remains unchanged. The [OCaml successor](bap-ocaml-qualification.md)
implements and checks the isolated SDK and bounded Init/Visit transport; consult
that record for the later full A0 decision.

**Why this document exists.** The user requested Stage 2 after the
[Stage 1 prerequisite](bap-unlimited-validation.md) passed under unlimited timing.

**What this document establishes.** The [analysis contract](bap-analysis-core-design.md),
seven executable admission tests and an actual pinned BAP term/graph probe are
delivered. The record distinguishes these checks from a migrated analyzer.

**Where to go next.**

- [OCaml qualification plan](../../Plans/bap-ocaml-qualification.md) — records the successor SDK and real custom-pass gates; this first probe record retains its historical scope.

- [A0 plan](../../Plans/bap-stage2-a0.md) — tracks completed and remaining clauses.
- [Analysis contract](bap-analysis-core-design.md) — defines ownership, messages,
  both formal observation mappings and required typed-edge preservation.
- [Native experimental module](../../native/bap-core/README.md) — runs the probe
  and source-bound qualification utility.

**What remains unresolved.** This first record does not qualify a custom OCaml
pass. The OCaml successor supplies that bounded foundation. The later
[complete Stage 2 work](bap-core-qualification.md) implements recovery, dataflow,
stateflow, generated replay and product integration and records adoption acceptance.
The independent ISA track stays retired.

For the wider context, see the [documentation map](../documentation-map.md).

## Exercised evidence

The Stage 1 prerequisite's full 178-entry source inventory and workload tool
hashes still match. A0's experimental files are isolated from that production
build; no Rust algorithm, model or existing lifter source changed.

Seven tests exercise initialization/operation envelopes, family-specific action
names, identity and sequence binding, canonical unsigned addresses, duplicate
JSON keys, frame bounds, nonfinite/overflowing JSON numbers, same-VA term
attribution, synthetic terms and invalid/cyclic ancestry. They validate interface
admission only; complete initialization payload semantics and native action
guards are still required before production admission.

The C++ probe builds against the hash-pinned BAP library and starts two fresh
processes. Both return the same observed facts:

| Capability | Actual observation |
| --- | --- |
| Unsigned address attribution | `0xfffffffffffffff0` survives a BAP term attribute round-trip. |
| Persistent terms | Adding an address preserves the earlier un-attributed term and its TID. |
| One instruction, multiple terms | Two distinct TIDs retain the same machine VA without collapsing. |
| BAP-owned graph versions | Native graph objects retain node counts 0, 1 and 2 across updates. |
| Repeated observation | Reading graph contents does not change them. |
| Parallel-edge labels | Inserting two labels between the same TIDs leaves **one** edge. The model's typed edge relation must be separate. |
| Fresh graph | A new graph is empty; process recreation remains required for full snapshot isolation. |

The exact C header lacks `bap_project_empty`, custom project-input construction
and a sub-builder result accessor. The installed runtime extraction contains
zero `.cmi` and `.cmxa` SDK files. An installed OCaml compiler alone does not
establish compatibility with this packaged runtime. A compatible isolated SDK
and a real custom-pass initialize/observe exchange remain the next A0 clause.

## Qualification limits

The [retained record](../../evidence/Ariadne/bap-stage2-a0-validation.json) binds
15 source/design files, compiler/helper/header/library identities and raw probe
outputs. Its `passed=true` denotes the exercised A0 checks;
`a0ExitPassed=false`, `stage2Started=true` and `stage2Qualified=false` preserve
the remaining clauses. `implementedAlgorithms` is empty. No generated model
replay or mutation campaign is credited for a solver that does not yet exist.

The [archive manifest](../../evidence/Ariadne/bap-stage2-a0-evidence-manifest.json)
binds the reports, logs, reviewed contract and probe sources. The next build
must keep the Rust reference independent and expose actual OCaml state after
each action; C++ graph operations alone do not satisfy that implementation goal.
