# Controlled Windows I5a qualification on native analysis

## Context and follow-up

**Status.** Qualified on 2026-10-05 for the exercised Linux-hosted scope, using
an exact, read-only MirrorRust dependency snapshot. All 14 source/fixture gates,
17 investigation gates and both controlled Windows capture modes pass. The
refreshed Stage 2 aggregate passes all 20 gates. The live MirrorRust checkout
remains independently editable; these results bind the selected snapshot.

**Why this document exists.** [Stage 2](bap-core-qualification.md) changed the
analysis owner. The [historical I5a capture result](crashpad-demo-validation.md)
predates that default and cannot qualify the current native path.

**What this document establishes.** Native backend identity, independent corpus
coverage, fresh timing and controlled-capture acceptance with historical producer
provenance kept separate from current inspection tools. No production analysis
algorithm or performance patch was needed.

**Where to go next.**

- [Qualification plan](../../Plans/i5a-native-qualification.md) — implementation,
  frozen criteria and repeatable snapshot-based qualification.
- [Source/fixture record](../../evidence/Ariadne/i5a-native-fixture-validation.json)
  and [controlled record](../../evidence/Ariadne/i5a-native-controlled-validation.json)
  — exact gate outcomes, identities, raw sample summaries and acceptance tiers.
- [I5a contracts](i5a-contracts.md) — numeric question, premises and report meaning.
- [Demo guide](../../native/crashpad-demo/README.md) — independent capture inspection
  and controlled assessment commands.
- [Investigation ledger](../../Plans/investigation-layer.md) — separate active
  Windows I4 and later hypothesis/object/cross-capture work.

**What remains unresolved.** The [active Windows I4 re-pin](i4-windows-repin-validation.md) passes correctness;
the later [performance qualification](i4-performance-validation.md) meets its
separate 2-second CLI budget and retains refreshed BAP/I5a regressions. The
measurements below belong to the earlier native-I5a snapshot. The missing original Electron
case is historical following the user-authorized replacement. These results cover Linux-hosted analysis of the
recorded Windows-origin captures, not native Windows execution of Ariadne or a
packaged cross-platform release. Broader hypotheses, historical execution,
root causes and universal refinement remain outside this result. BAP lifting
remains trusted.

See the [documentation map](../documentation-map.md) for broader context.

## Native ownership and unchanged criteria

The phase benchmark consumes `NativeAnalyzer::from_capture(...).complete()`
through `AnalysisView`. Completed recovery stays outside the incremental timer
and inside the normal CLI timer. Each phase row binds the native helper manifest,
captured profile, artifact, snapshot, report query, distinct native protocol
query and assessment-output digest. Default and explicit BAP output are compared
outside the timed samples.

The criteria remain one warm-up and five measured repeats, assessment CLI median
at most **1,500 ms**, and combined binding/assessment/all-format rendering median
at most **10 ms**. Neither threshold was relaxed. Captures, independent expected
answers and original report meanings were preserved.

The fixture record passes all 14 gates with 216 source hashes and exact native
tool identities. All 41 independent corpus cases exercise completed native
analysis. Thirteen native contract controls and 28 controlled-capture controls
pass; all 16 I5a implementation mutants are detected. Comparison retains 24
legacy Rust output hashes, checks 24 native/reference outputs, and preserves
12 byte-exact explanation comparisons. The nested investigation aggregate passes
17 gates while keeping full active Windows I4 acceptance false for its
over-budget measured CLI. The older original-Windows I4 flag remains false.

Nine measured fixtures pass: assessment CLI medians range from **844.584 to
1070.294 ms**, and combined native phase medians from **0.590 to 1.059 ms**.
Raw samples and every measured report bundle are retained in the evidence archive.

## Controlled Windows results

The original partial/full dumps, matching executable, witness and producer-build
records retain their identities. Fresh inspections are separate files. Current
nearby demo-source observations do not replace historical producer source hashes.
The controlled runner verifies that provenance, repeated output hashes, unchanged
base reports, exact questions, native receipts and untimed default/explicit BAP
selection before assigning acceptance.

| Capture | Base CLI median | Assessment CLI median | Native incremental median | Result |
| --- | ---: | ---: | ---: | --- |
| Partial | 881.653 ms | 869.642 ms | 1.067 ms | Pass |
| Full | 875.029 ms | 873.537 ms | 1.032 ms | Pass |

Both answers are consistent with the independent zero-address oracle under the
admitted capture/lifting premises. The fresh controlled record has
`controlledWindowsCasePassed=true`, stable inputs/sources/tools, and
`originalWindowsI4AcceptancePassed=false`. The source/fixture record independently
keeps its own controlled-case flag false because that tier does not exercise the
real captures. The separate controlled record supplies that acceptance.

## Dependency repair and qualification scope

The first refresh rejected changing MirrorRust source identities even though all
20 component gates passed. Subsequent formatting checks also failed on concurrent
changes in the live checkout. Formatting was repaired, but further live edits
showed that a stable qualification dependency was still needed.

The [snapshot wrapper](../../tools/with_mirrorrust_snapshot.py) now copies all
non-ignored worktree inputs, including root-level compile resources, formats the
copy, and retains both original and formatted bytes. A manifest digest selects
the snapshot. Linux bubblewrap presents it read-only at the ordinary dependency
path, and validation checks both mount identity and file hashes. Edits to the
live checkout cannot change this view. Records carry the selected environment;
reuse across different snapshot identities is rejected. Protocol/snapshot
controls pass, and all 190 Python qualification tests pass after their synthetic
fixtures were updated to isolate the new environment probe.

The exercised snapshot manifest SHA-256 is:

```text
f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56
```

It records base revision `afbb694bd847ad34dbfbbba75a05038653a350a1` and the exact
captured worktree bytes; it does not claim that those bytes equal the clean Git
revision. The Stage 2 archive retains the full dependency manifest, including
file contents. Its 20-gate result covers 632 Ariadne source files and the selected
dependency inventory. Final release CLI and helper identities match the I5a
records and the default-helper-path smoke check.

The [earlier progress record](../../evidence/Ariadne/i5a-native-progress/progress.json)
and [progress archive](../../evidence/Ariadne/i5a-native-progress-evidence.tar.gz)
remain unchanged historical evidence. Their failed flags have not been promoted.
The [previous accepted I5a records and bundle](../../evidence/Ariadne/i5a-native-history/2026-10-05-before-i4-repin/i5a-native-evidence-manifest.json)
remain byte-identical history before the I4 source refresh.
The previous Stage 2 adoption record is preserved in
[adoption history](../../evidence/Ariadne/bap-core-history/2026-10-04-adoption/bap-core-qualification.json).

## Reproduction and retained evidence

Create a new dependency snapshot, then run every qualification command through
that same snapshot and its printed digest:

```sh
python3 tools/with_mirrorrust_snapshot.py create \
  --output target/qualification-deps/mirrorrust-recheck
snapshot_sha256=REPLACE_WITH_PRINTED_SHA256
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/qualification-deps/mirrorrust-recheck \
  --sha256 "$snapshot_sha256" -- \
  python3 tools/check_bap_core.py --output target/bap-stage2-recheck
```

Use the same wrapper for `tools/check_investigation.py`, `tools/check_i5a.py`,
`native/crashpad-demo/assess.py` and evidence verification. Reuse components only
when their complete source/tool and qualification-environment identities match.
The [demo guide](../../native/crashpad-demo/README.md#inspect-and-analyze) explains
fresh separate inspections and the required passing v2 source/fixture record.
Pinned native helpers/runtime, SDK, Graphviz, model tooling and raw capture inputs
are prerequisites; missing inputs are not skipped acceptance.

The [complete archive](../../evidence/Ariadne/i5a-native-evidence.tar.gz) and
[verified manifest](../../evidence/Ariadne/i5a-native-evidence-manifest.json)
retain source snapshots, exact producer records, logs, timing CSVs, report
bundles, fresh inspections and unchanged historical producer metadata. The path
map preserves original runner locations. All 1,969 archive entries were reread and verified (27,059,376 bytes).
Raw real dump/executable bytes remain external and hash-pinned. Archive contents and accepted source/tool inventories
were verified after retention; a later change requires a fresh check.
