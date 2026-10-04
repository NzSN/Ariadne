# Retained Ariadne evidence

## Context and follow-up

**Status.** Evidence interpretation, not a new acceptance result.

**Why this document exists.** [Assurance decision](../../docs/Ariadne/semantic-assurance.md) requires results to retain their premises and scope.

**What this document establishes.** JSON records identify checks, inputs and source/tool hashes; CSV files retain measurement samples; archive manifests bind logs and reports to exact bytes.

**Where to go next.**

- [Unlimited BAP timing policy](../../docs/Ariadne/bap-unlimited-validation.md) — distinguishes current qualification from earlier bounded-policy measurements.

- [Checkpoints](../../CHECKPOINTS.md) — connect evidence to dated deliveries.
- [Layout delivery](../../docs/Ariadne/rust-source-layout.md) — explains the regression tier before later tooling changes.
- [I5a delivery](../../docs/Ariadne/i5a-validation.md) — distinguishes the zero-address source/fixture tier from unexercised real Windows acceptance.
- [BAP workload repair](../../docs/Ariadne/bap-windows-workload-validation.md) — separates implementation evidence from the original Windows Stage 1 prerequisite.
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
checks and passing zero-address answers. The unchanged CLI timing condition is
not met, so controlled-case I5a acceptance remains false. Raw dumps and executables
stay external under ignored local artifact directories. The [delivery guide](../../docs/Ariadne/crashpad-demo-validation.md)
describes the resolved capture gap and remaining performance requirement.

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

## Complete native Stage 2 qualification (2026-10-04)

[bap-core-qualification.json](bap-core-qualification.json) records 20 passing
aggregate gates, 623 stable source hashes, `stage2Qualified=true` and verified
default-native selection with explicit Rust rollback. The
[archive](bap-core-evidence.tar.gz) and [manifest](bap-core-evidence-manifest.json)
retain 1,345 verified entries, including the default-helper-path smoke check.
The [qualification guide](../../docs/Ariadne/bap-core-qualification.md) explains
the 44 generated traces/330 observations, twelve native algorithm mutations,
five measured workloads and separate proof/release limits. Earlier Stage 1 and
A0 records remain historical evidence for their exact source sets.

The complete Stage 2 archive is stored with Git LFS. After cloning, run
`git lfs pull --include="evidence/Ariadne/bap-core-evidence.tar.gz"` to materialize
the archive before checking its manifest hash or extracting it. The LFS object
preserves the exact qualified archive bytes; a Git pointer is not the archive.
