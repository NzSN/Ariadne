# BAP analysis-core qualification

## Context and follow-up

**Status.** Stage 2 A1–A6 and native default adoption are implemented. The
standalone record linked below retains the 2026-10-05 I4 re-pin refresh: 20
passing gates, 632 stable sources and 1,355 verified archive entries at that run.
The later [2026-10-07 performance qualification](i4-performance-validation.md)
contains a newer native-core refresh with 20 passing gates and 712 source
identities. The [documentation audit](bap-documentation-sync.md) verifies that
later record against this checkout; the older standalone inventory has drifted.
Native BAP remains the CLI default, with explicit Rust rollback. Controlled
I5a and I4 retain their separately qualified fixed budgets.

**Why this document exists.** The [analysis design](bap-analysis-core-design.md)
and [execution plan](../../Plans/bap-stage2-implementation.md) require evidence
for actual native algorithms, capture integration and product adoption.

**What this document establishes.** The exercised A1–A6 scope, reproduction
commands and limits of the retained result. Older [A0 evidence](bap-ocaml-qualification.md)
qualifies its own bounded bootstrap only.

**Where to go next.**

- [Native I4 performance qualification](i4-performance-validation.md) — later 20-gate core refresh and fixed-budget product acceptance.
- [Documentation/source audit](bap-documentation-sync.md) — identifies the matching nested record, verified archive and current implementation limits.

- [Native module](../../native/bap-core/README.md) — SDK, helper build and selection.
- [Integration plan](../../Plans/bap-integration.md#stage-2-bap-analysis-core) — milestone acceptance clauses.
- [Assurance boundary](semantic-assurance.md) — trusted lifting and independent proof limits.
- [Evidence guide](../../evidence/Ariadne/README.md) — archive interpretation.

**What remains unresolved.** These checks do not prove universal refinement or
ISA semantics. BAP lifting is trusted. Supplied LLVM IR uses the separate Rust
engine. This is workspace-local Linux-hosted qualification, including captured
Windows inputs, not a packaged cross-platform release qualification. The [active Windows I4 re-pin](i4-windows-repin-validation.md) has a later [passing performance qualification](i4-performance-validation.md) under its separate fixed CLI budget; controlled Windows I5a has its own passing
[native qualification](i5a-native-qualification.md). The live MirrorRust checkout
is outside the pinned dependency view used by this record.

For the wider context, see the [documentation map](../documentation-map.md).

## Implemented scope

The standalone OCaml/BAP helper owns recovery, reaching definitions, slicing and
finite supplied stateflow. Rust reads captured bytes, freezes semantic inputs,
validates transport/results and renders reports. Completed native results feed
investigation and stateflow preparation without executing the Rust reference
solver. The capture-only profile binds snapshot, query, consumed bytes, stream
contributors and Stage 1 semantic evidence to reader-scoped BAP terms.

Generated replay observes real helper transitions: 12 recovery traces with
168 observations and 32 stateflow traces with 162 observations. Wrong-digest
controls require rejection before any observation. Twelve native algorithm
mutants must cause genuine generated observation mismatches; boundary mutations
exercise transport, identity and projection rejection independently.

Five release workload comparisons cover Linux and Windows fixtures, the NOT
precision fixture, the retained 34-start Linux capture and pinned 98-start
Windows capture. Each backend gets one warm-up and five measured samples.
JSON, text and DOT outputs must agree after validating and removing the native
backend receipt. Default selection must reproduce explicit native output;
explicit `--analysis-backend rust` remains the rollback path. The timing policy
is unlimited; measurements are still retained.

## Reproduction

```sh
python3 native/bap-core/setup-sdk.py --check
python3 native/bap-core/build.py --output target/bap-core-native
python3 tools/check_bap_core.py --output target/bap-stage2-recheck
```

For the recorded dependency view, run the aggregate command through the
[snapshot wrapper](../../tools/with_mirrorrust_snapshot.py) and the manifest digest
shown in the [I5a qualification guide](i5a-native-qualification.md#reproduction-and-retained-evidence).
Use the same wrapper for evidence verification and select a new output directory
for each run. The dependency manifest, including exact source bytes, is retained
as `dependencies/mirrorrust-snapshot.json` in the Stage 2 archive.

The aggregate checker also builds a second clean helper, checks root tests and
Clippy, runs native kernels/capture/stateflow tests, generated replay and mutation
campaigns, and refreshes Stage 1/Stage E regressions. Existing pinned native
helpers, SDK archives, Graphviz, TLC, MirrorRust and captured workload artifacts
are required. Missing prerequisites are failures, not skipped acceptance.

The final report must have `passed`, `stage2Qualified`, `defaultNativeVerified`
and `sourcesStable` all true. Its archive manifest must verify every retained
entry and bind the exact report. Source/tool changes invalidate that decision.

## Retained result

The standalone files in this section are historical snapshots. The latest
matching native-core record is nested at
`records.regressions.records.native-core-stage-e-input-bap-regressions` in the
[I4 performance record](../../evidence/Ariadne/i4-performance-qualification.json).
Its Stage 1 refresh is `records.stage1-regression` within that core record.
Those records qualify their own inventories, not the obsolete standalone
source lists. The [audit](bap-documentation-sync.md) checks them separately.

The [analysis contract](bap-analysis-core-design.md) and
[Stage 2 execution plan](../../Plans/bap-stage2-implementation.md) retain their
accepted source-bound bytes. The plan's candidate-stage directions describe the
historical sequence; its completed A6 checkbox and this guide's adoption record
state the delivered result. The design's implemented ABI 2 section governs the
current helper beyond the earlier A0 proposal.

- [Qualification report](../../evidence/Ariadne/bap-core-qualification.json) —
  20 passing gates, complete source/tool identities and nested regression records.
- [Evidence archive](../../evidence/Ariadne/bap-core-evidence.tar.gz) and
  [verified manifest](../../evidence/Ariadne/bap-core-evidence-manifest.json) —
  sources, helper, observations, mutation records, logs and product reports.

The explicit-native candidate passed 19 gates before adoption. The
[original adoption record](../../evidence/Ariadne/bap-core-history/2026-10-04-adoption/bap-core-qualification.json)
and its archive/manifest remain byte-identical in that history directory.
The [pre-I4 refresh](../../evidence/Ariadne/bap-core-history/2026-10-05-before-i4-repin/bap-core-qualification.json)
and its archive/manifest are also preserved byte-for-byte. The retained
2026-10-05 refresh uses thirteen protocol/snapshot controls and a verified
current Stage 1/Stage E record under the same dependency snapshot. Root default/core-only tests, all-feature Clippy, native
capture/investigation/stateflow tests and Stage 1/Stage E regressions pass.
Stage 1 workload measurements explicitly select Rust; their nested records do
not decide Stage 2 acceptance.

The additional `artifacts/0/default-path-smoke-check.json` archive entry binds a
successful invocation with no backend flag or helper-directory override to the
same final release executable. Its default helper manifest matches both clean
qualification builds. The product gate separately verifies native/default/Rust
selection across all five workloads and all three report formats.

| Stage | Exercised result |
| --- | --- |
| A1 | Scoped recovery, capture identities, reader-owned evidence and term attribution pass. |
| A2 | Complete native reaching definitions and slicing match reference and model observations. |
| A3 | Finite stateflow, terminal outcomes and edge classification pass native and CLI checks. |
| A4 | 44 generated traces match 330 observations; wrong digests fail before observation. |
| A5 | Twelve algorithm mutants produce intended mismatches; boundary controls and product differentials pass. |
| A6 | Two clean helper builds agree; all 20 gates, default selection, Rust rollback and archive verification pass. |

Historical 2026-10-05 release medians, in milliseconds, from five measured
samples after one warm-up per backend:

| Captured workload | Rust reference | Native BAP |
| --- | ---: | ---: |
| Linux fixture (4 starts) | 895.39 | 964.30 |
| Windows fixture (4 starts) | 921.57 | 957.16 |
| NOT precision fixture (4 starts) | 900.27 | 964.70 |
| Retained Linux capture (34 starts) | 1566.21 | 2248.97 |
| Pinned Windows capture (98 starts) | 2967.88 | 5020.08 |

Native analysis was slower on these recorded 2026-10-05 workloads. The later
[performance qualification](i4-performance-validation.md) changes preparation
and native transport/core costs; this table is not a current performance
comparison. Correctness and identity checks passed under the accepted unlimited
timing policy; these measurements do not
establish a general performance guarantee or qualify the separate I5a budget.
