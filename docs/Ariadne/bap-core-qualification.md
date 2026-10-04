# BAP analysis-core qualification

## Context and follow-up

**Status.** Stage 2 A1–A6 is implemented and qualified on 2026-10-04 for the
exercised workspace-local scope. All 20 aggregate gates pass; `stage2Qualified`,
`defaultNativeVerified` and `sourcesStable` are true. The CLI defaults to native
BAP analysis, with explicit Rust rollback. The archive verifies 1,345 entries
and binds 623 current source hashes.

**Why this document exists.** The [analysis design](bap-analysis-core-design.md)
and [execution plan](../../Plans/bap-stage2-implementation.md) require evidence
for actual native algorithms, capture integration and product adoption.

**What this document establishes.** The exercised A1–A6 scope, reproduction
commands and limits of the retained result. Older [A0 evidence](bap-ocaml-qualification.md)
qualifies its own bounded bootstrap only.

**Where to go next.**

- [Native module](../../native/bap-core/README.md) — SDK, helper build and selection.
- [Integration plan](../../Plans/bap-integration.md#stage-2-bap-analysis-core) — milestone acceptance clauses.
- [Assurance boundary](semantic-assurance.md) — trusted lifting and independent proof limits.
- [Evidence guide](../../evidence/Ariadne/README.md) — archive interpretation.

**What remains unresolved.** These checks do not prove universal refinement or
ISA semantics. BAP lifting is trusted. Supplied LLVM IR uses the separate Rust
engine. This is workspace-local Linux-hosted qualification, including captured
Windows inputs, not a packaged cross-platform release qualification. Original
Windows I4 and controlled real Windows I5a retain their own acceptance criteria.

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
python3 tools/check_bap_core.py --output target/bap-stage2-qualification
```

The aggregate checker also builds a second clean helper, checks root tests and
Clippy, runs native kernels/capture/stateflow tests, generated replay and mutation
campaigns, and refreshes Stage 1/Stage E regressions. Existing pinned native
helpers, SDK archives, Graphviz, TLC, MirrorRust and captured workload artifacts
are required. Missing prerequisites are failures, not skipped acceptance.

The final report must have `passed`, `stage2Qualified`, `defaultNativeVerified`
and `sourcesStable` all true. Its archive manifest must verify every retained
entry and bind the exact report. Source/tool changes invalidate that decision.

## Retained result

- [Qualification report](../../evidence/Ariadne/bap-core-qualification.json) —
  20 passing gates, complete source/tool identities and nested regression records.
- [Evidence archive](../../evidence/Ariadne/bap-core-evidence.tar.gz) and
  [verified manifest](../../evidence/Ariadne/bap-core-evidence-manifest.json) —
  sources, helper, observations, mutation records, logs and product reports.

The explicit-native candidate passed 19 gates before the default changed. The
final run refreshed all regressions after that change and added the seven-test
contract-checker gate. Root default/core-only tests, all-feature Clippy, native
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

Final release medians, in milliseconds, from five measured samples after one
warm-up per backend:

| Captured workload | Rust reference | Native BAP |
| --- | ---: | ---: |
| Linux fixture (4 starts) | 861.21 | 902.57 |
| Windows fixture (4 starts) | 871.56 | 920.86 |
| NOT precision fixture (4 starts) | 855.80 | 907.47 |
| Retained Linux capture (34 starts) | 1455.56 | 2108.74 |
| Pinned Windows capture (98 starts) | 2820.26 | 4901.01 |

Native analysis is slower on these workloads. Correctness and identity checks
pass under the accepted unlimited timing policy; these measurements do not
establish a general performance guarantee or qualify the separate I5a budget.
