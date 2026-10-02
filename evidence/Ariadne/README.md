# Retained Ariadne evidence

This directory contains versioned validation results, benchmark samples, pinned
capture-case definitions and evidence archives. Human-readable guides and
contracts live in [docs/Ariadne](../../docs/Ariadne/README.md).

| Artifact | Purpose |
| --- | --- |
| `*-validation.json` and regression records | Gate results, source/tool identities, tested scope and unmet clauses |
| `*-evidence-manifest.json` and `*.tar.gz` | Archive identities and hashes for retained reports/logs |
| `*-real-capture-case.json` | Pinned capture/companion identities and query addresses used by validation tools |
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
