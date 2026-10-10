# Retained Ariadne evidence

## Context and follow-up

**Status.** Evidence interpretation, not a new acceptance result.

**Why this document exists.** [Assurance decision](../../docs/Ariadne/semantic-assurance.md) requires results to retain their premises and scope.

**What this document establishes.** JSON records identify checks, inputs and source/tool hashes; CSV files retain measurement samples; archive manifests bind logs and reports to exact bytes.

**Where to go next.**

- [P4 acceptance decision](bap-admission/p4-acceptance-20261010.json) — user
  acceptance with remaining historical real-Linux clauses excluded; original
  qualification flags and incomplete optional campaigns remain unchanged.
- [Post-acceptance documentation refresh](bap-admission/p4-documentation-followup-20261010.json)
  — updated guide hashes and verification that qualified implementation/fixture
  identities still match; earlier decisions and evidence remain unchanged.
- [Selected real-capture record](real-capture-repin-79938/report.json) and
  [verified manifest](real-capture-repin-79938/evidence-manifest.json) — current
  P4/I4 qualification under the user-selected Windows pin; its
  [guide](../../docs/Ariadne/real-capture-repin-79938.md) preserves Linux limits.
- [I5b qualification](i5b-qualification.json), [verified evidence manifest](i5b-evidence-manifest.json)
  and [controlled case pins](i5b-controlled-cases.json) — new source/fixture and
  real Windows machine-code debugging acceptance; see the
  [validation guide](../../docs/Ariadne/i5b-validation.md) for scope and timings.
- [Unlimited BAP timing policy](../../docs/Ariadne/bap-unlimited-validation.md) — distinguishes current qualification from earlier bounded-policy measurements.

- [Checkpoints](../../CHECKPOINTS.md) — connect evidence to dated deliveries.
- [Layout delivery](../../docs/Ariadne/rust-source-layout.md) — explains the regression tier before later tooling changes.
- [Historical I5a delivery](../../docs/Ariadne/i5a-validation.md) — distinguishes its original source/fixture result from the separately qualified native and controlled Windows successors.
- [Windows I4 re-pin](../../docs/Ariadne/i4-windows-repin-validation.md) — independent 98-start capture checks and historical timing failure;
  [native performance qualification](../../docs/Ariadne/i4-performance-validation.md) closes the fixed CLI clause.
- [Native I5a qualification](../../docs/Ariadne/i5a-native-qualification.md) — records accepted native measurements and the snapshot repair, while preserving earlier failures.
- [Historical BAP workload repair](../../docs/Ariadne/bap-windows-workload-validation.md) — preserves the original missing-artifact checkpoint before later replacement and native qualification.
- [Controlled BAP replacement](../../docs/Ariadne/bap-windows-repin-validation.md) — records the new active pin, durable input bundle and its own measured qualification.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. Embedded paths preserve the layout at the original run.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

This directory contains versioned validation results, benchmark samples, pinned
capture-case definitions and evidence archives. Human-readable guides and
contracts live in [docs/Ariadne](../../docs/Ariadne/README.md).

| Artifact | Purpose |
| --- | --- |
| `*-validation.json` and regression records | Gate results, source/tool identities, tested scope and unmet clauses |
| `*-evidence-manifest.json` and `*.tar.gz` | Archive identities and hashes for retained reports/logs |
| `*-real-capture-case.json` | Pinned capture/companion identities and query addresses used by validation tools |
| `bap-windows-workload-case.json` and `bap-windows-workload-inputs.tar.gz` | Active controlled Crashpad workload pin and hash-verified replay inputs, including the generated partial dump and matching executable |
| Mutation, negative-control and outcome JSON | Observed behavior and sensitivity to intentionally incorrect implementations/inputs |
| `*.csv` | Individual performance samples, phase timings, memory usage and graph sizes |

These artifacts moved from `docs/Ariadne/` on 2026-10-02 without changing their
bytes: 46 JSON files, 20 CSV files and four evidence archives. Manifest archive
names remain relative to this directory.

Embedded paths, source hashes, commands and timestamps retain their historical
meaning. In particular, a source-hash key beginning with `docs/Ariadne/` records
the layout at that run; it is not an instruction to recreate the old directory.
Current tools use `evidence/Ariadne/` for pinned cases and retained reports.
Relocation does not make historical validation current. Exact-source reuse may
reject older records after path or tool changes; rerun the relevant gate rather
than editing its stored hashes or pass/fail flags.

Stage D records are retired research evidence. Earlier LLVM measurements do not
qualify the BAP backend, and absent Windows artifacts remain unmet requirements.

The [investigation correctness record](investigation-correctness-validation.json)
and [manifest](investigation-correctness-evidence-manifest.json) retain the later
qualification/truncation repairs. Their [delivery explanation](../../docs/Ariadne/investigation-correctness-validation.md)
distinguishes the passing 17-gate fixture/Linux tier from unavailable full Windows
acceptance. Earlier evidence files have not been rewritten.

The [I5a acceptance record](i5a-validation.json),
[manifest](i5a-evidence-manifest.json) and [archive](i5a-evidence.tar.gz) retain
12 passing source/fixture gates, their fresh investigation/model/input regressions,
41 independent fixtures, 16 I5a mutants, unchanged reports and frozen measurements.
The archive includes a source snapshot and derived outputs; real captures remain
external. Controlled real Windows I5a and original-Windows I4 are explicitly false
in the acceptance record. See the [delivery explanation](../../docs/Ariadne/i5a-validation.md)
for the exercised scope and remaining clauses.

The later [Crashpad demo record](crashpad-demo-validation.json),
[manifest](crashpad-demo-evidence-manifest.json) and [archive](crashpad-demo-evidence.tar.gz)
retain a native Windows build, partial/full real captures, independent field/code
checks and passing zero-address answers. That historical run did not meet the
CLI timing condition, so its controlled-case flag remains false. Raw dumps and executables
stay external under ignored local artifact directories. The [delivery guide](../../docs/Ariadne/crashpad-demo-validation.md)
describes the original capture gap and links the later passing native qualification.

## Native I5a refresh progress (2026-10-04)

The [progress summary](i5a-native-progress/progress.json),
[archive](i5a-native-progress-evidence.tar.gz) and
[manifest](i5a-native-progress-evidence-manifest.json) retain new native
measurements, raw samples, output bundles, mutation results and rejected aggregate
attempts. This records the earlier incomplete qualification: nine measured fixtures and
sixteen mutants passed; controlled diagnostics met both budgets, but that I5a
aggregate was 12/14 and investigation was 16/17. The failed formatting gate was
in the changing sibling MirrorRust checkout. The first Stage 2 refresh also
rejected its final dependency-identity check despite twenty passing components.

Original records retain their exact bytes and pass/fail flags. The archive's
path map connects temporary runner paths to retained entries. Real Windows dumps
and executables remain external and hash-pinned. The older I5a, Crashpad and
Stage 2 accepted records remain unchanged historical evidence; this progress
archive does not supersede them with a new acceptance result.

## OCaml recovery foundation

The [OCaml record](bap-ocaml-qualification.json) and
[verified archive inventory](bap-ocaml-evidence-manifest.json) retain the bounded
SDK, Init/Visit, transport and mutation checks. All OQ gates and full A0 exit
now pass after the approved formatting-only MirrorRust change and fresh
regression checks. The previous partial record/archive is preserved under
`bap-ocaml-history/2026-10-03-format-blocked/`. That bounded A0 record does not qualify complete Stage 2.
See the [qualification guide](../../docs/Ariadne/bap-ocaml-qualification.md) for
coverage, the resolved prerequisite and the successor A1–A6 work. Earlier Stage 1/A0
records remain historical and have not been rebound to replacement source hashes.

## Native I5a accepted under the dependency snapshot (2026-10-05)

The [source/fixture record](i5a-native-fixture-validation.json) passes all 14 gates;
the separate [controlled record](i5a-native-controlled-validation.json) qualifies
partial/full Windows captures under the unchanged 1,500 ms CLI and 10 ms phase
criteria. Active Windows I4 correctness passes; the later
[native performance qualification](../../docs/Ariadne/i4-performance-validation.md) meets its fixed CLI budget. The [archive](i5a-native-evidence.tar.gz)
and [manifest](i5a-native-evidence-manifest.json) retain 1,969 verified entries,
216 source hashes, exact producer records, raw samples, report bundles and
historical capture metadata. Real dump/executable bytes remain external.

Qualification uses the manifest-selected, read-only MirrorRust view described
in the [guide](../../docs/Ariadne/i5a-native-qualification.md). The Stage 2 archive
contains `dependencies/mirrorrust-snapshot.json`, including exact source bytes.
This qualifies that dependency snapshot; live-checkout changes have their own
identities. Earlier failed records retain their original flags and bytes.

## Complete native Stage 2 refresh (2026-10-05)

[bap-core-qualification.json](bap-core-qualification.json) records 20 passing
aggregate gates, 632 stable source hashes, `stage2Qualified=true` and verified
default-native selection with explicit Rust rollback. The
[archive](bap-core-evidence.tar.gz) and [manifest](bap-core-evidence-manifest.json)
retain 1,355 verified entries, including the default-helper-path smoke check.
The [qualification guide](../../docs/Ariadne/bap-core-qualification.md) explains
the 44 generated traces/330 observations, twelve native algorithm mutations,
five measured workloads and separate proof/release limits. Earlier Stage 1 and
A0 records remain historical evidence for their exact source sets. The original
623-source/1,345-entry adoption record and archive are preserved under
[bap-core-history/2026-10-04-adoption](bap-core-history/2026-10-04-adoption/bap-core-qualification.json).

The [pre-I4 core refresh](bap-core-history/2026-10-05-before-i4-repin/bap-core-qualification.json)
and [pre-I4 I5a bundle](i5a-native-history/2026-10-05-before-i4-repin/i5a-native-evidence-manifest.json)
remain byte-identical historical evidence.

The complete Stage 2 archive is stored with Git LFS. After cloning, run
`git lfs pull --include="evidence/Ariadne/bap-core-evidence.tar.gz"` to materialize
the archive before checking its manifest hash or extracting it. The historical
adoption archive is also tracked with Git LFS at its history path. The LFS object
preserves the exact qualified archive bytes; a Git pointer is not the archive.

## Active Windows I4 re-pin (2026-10-05)

The [new case](investigation-windows-workload-case.json) pins the independently
inspected 98-start native Windows Crashpad capture and exact entry/fault/producer
query. Its [inspection](i4-windows-capture-inspection.json),
[validation record](i4-windows-repin-validation.json),
[archive](i4-windows-repin-evidence.tar.gz) and
[verified manifest](i4-windows-repin-evidence-manifest.json) retain the complete
identity and measured result: 17 gates pass, five explanation-CLI samples have
a 4,774.451 ms median, and full I4 acceptance is false against the unchanged
2,000 ms limit. The archive contains 865 verified entries (18,012,236 bytes).
Raw input bytes remain in the unchanged [23-entry input bundle](bap-windows-workload-inputs.tar.gz),
which is also retained with the I4 source inventory. The original Electron
manifest and prior acceptance flags retain their historical meaning.

## Native I4 performance accepted (2026-10-07)

The [qualification record](i4-performance-qualification.json) and
[validation guide](../../docs/Ariadne/i4-performance-validation.md) close the
active exact-query timing clause: 1,692.696 ms Windows explanation CLI against
2,000 ms, and 182.924 ms Linux incremental phases against 250 ms. The original
re-pin's over-budget flag above remains historical. Capture/query pins and all
fixed budgets remain unchanged.

The [archive](i4-performance-evidence.tar.gz) and
[manifest](i4-performance-evidence-manifest.json) retain 3,625 verified members,
712 source inputs, 12 tool identities and complete nested 18-gate I5b / 20-gate
native-core / 14-gate I5a regressions. The [completion audit](i4-performance-audit.json)
rechecks current source/tool/dependency inventories and every archive member;
it distinguishes that new verification from the retained runtime campaign.
[CLI](i4-performance-cli.csv), [phase](i4-performance-phase.csv) and
[native profile](i4-performance-native-phases.csv) samples are byte-exact copies.
The archive uses Git LFS; materialize it before hash verification. The separately
[controlled I5a record](i4-performance-i5a-controlled.json) also passes current
identity checks and both existing timing budgets for partial/full captures.

Both [rejected attempts](i4-performance-history/2026-10-07-rejected/evidence-manifest.json)
retain their original failed reports, raw timings and output bundles. Their
results cannot supply acceptance credit. The 2026-10-05 re-pin, older Stage 2,
I5a and I5b records remain unchanged. This is finite workspace-local controlled
capture qualification under the sealed dependency view, with no original
Electron, universal proof, general latency or packaged-release claim.
