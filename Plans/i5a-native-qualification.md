# Qualify controlled Windows I5a on the native default

## Context and follow-up

**Status.** Implementation and the exercised qualification are complete on
2026-10-05. The native source/fixture aggregate passes 14 gates, investigation
passes 17, refreshed Stage 2 passes 20, and both retained controlled Windows
capture modes meet the unchanged timing criteria. Qualification uses the
recorded read-only MirrorRust snapshot.

**Why this document exists.** The [I5a design](../docs/Ariadne/i5a-zero-address-design.md)
requires evidence for the selected analysis backend. The historical controlled
runner used an older fixture record, and its phase benchmark exercised Rust
analysis while the product CLI had moved to native BAP.

**What this document establishes.** The completed native benchmark and identity
checks, preserved capture provenance, separate acceptance tiers, and repeatable
qualification without depending on a concurrently edited client checkout.
No production performance patch was needed.

**Where to go next.**

- [Qualification guide](../docs/Ariadne/i5a-native-qualification.md) — accepted
  records, measurements, snapshot identity and limits.
- [I5a implementation plan](i5a-zero-address.md) — frozen admission, reports,
  budgets and independently reported qualification tiers.
- [Historical capture evidence](../docs/Ariadne/crashpad-demo-validation.md) —
  original Windows producer and preserved partial/full inputs.
- [Stage 2 qualification](../docs/Ariadne/bap-core-qualification.md) — native
  analysis evidence refreshed after the qualification tooling changes.
- [Investigation contracts](../docs/Ariadne/investigation-contracts.md) — exact
  query/evidence binding and the separate active Windows I4 timing obligation.

**What remains unresolved.** Active Windows I4 performance, packaged release qualification,
other hypotheses and broader workloads retain their separate requirements.
Acceptance covers the selected dependency snapshot; later live-checkout edits
or source/tool changes require new qualification.

See the [documentation map](../docs/documentation-map.md) for wider context.

## Preserved criteria and completed work

Keep one warm-up and five measured repeats, assessment CLI median at most
1,500 ms and combined binding/assessment/all-format rendering median at most
10 ms. Preparation and completed native recovery stay outside the incremental
phase interval and inside the normal CLI interval. Capture inputs, independent
oracles, report meanings and thresholds remain unchanged.

1. Measured the existing native default on both original captures. Diagnostics
   met the CLI criterion, so no analysis-algorithm optimization was justified.
2. Moved the phase benchmark to completed native capture analysis and bound rows
   to helper/build, artifact, snapshot, both query identities and output digests.
3. Added strict receipt, inventory, provenance and qualification-environment
   checks. Preserved legacy Rust hashes and verified native output equivalence.
4. Reinspected the original raw bytes into separate records while preserving
   historical producer build, capture, witness and inspection metadata.
5. Replaced the changing dependency view with a hash-selected, read-only snapshot.
   Fresh aggregate, replay, mutation and controlled-capture qualification passed.
6. Retained exact records, samples, logs, report bundles and verified archives.
   Earlier rejected records and the original adoption archive remain historical.

## Reproduce with a stable dependency snapshot

[The snapshot wrapper](../tools/with_mirrorrust_snapshot.py) copies all non-ignored
MirrorRust worktree inputs, formats the copy, and retains original/formatted
bytes and hashes. Linux bubblewrap mounts the selected copy read-only at the
ordinary dependency path. The wrapper validates the mount identity and digest;
records carry that environment and reject cross-snapshot prerequisite reuse.
The live checkout remains independently editable.

```sh
qualification_snapshot=target/qualification-deps/mirrorrust-recheck
python3 tools/with_mirrorrust_snapshot.py create --output "$qualification_snapshot"
qualification_sha=REPLACE_WITH_PRINTED_MANIFEST_SHA256
qualify() {
  python3 tools/with_mirrorrust_snapshot.py run \
    --snapshot "$qualification_snapshot" --sha256 "$qualification_sha" -- "$@"
}
qualify cargo fmt --all -- --check
qualify python3 tools/check_bap_core.py --output target/bap-stage2-recheck
qualify python3 tools/check_investigation.py
qualify python3 tools/check_i5a.py
```

Choose new output directories for reruns. Use the same wrapper for controlled
assessment and evidence verification. The [demo guide](../native/crashpad-demo/README.md#inspect-and-analyze)
explains fresh separate inspections and the required passing v2 fixture record.
Reuse individual components only after complete source/tool and environment
identity checks; never promote a failed aggregate or rewrite its hashes.

## Acceptance and retained boundaries

The [fixture record](../evidence/Ariadne/i5a-native-fixture-validation.json)
qualifies the source/fixture tier; its controlled-case flag remains false by
scope. The separate [controlled record](../evidence/Ariadne/i5a-native-controlled-validation.json)
qualifies both real Windows capture modes. Its historical original-Windows I4
flag stays false in both records. The [separate active I4 re-pin](../docs/Ariadne/i4-windows-repin-validation.md)
passes correctness but exceeds its fixed budget. The [verified archive](../evidence/Ariadne/i5a-native-evidence-manifest.json)
binds retained files and maps their original runner paths.

The [initial progress record](../evidence/Ariadne/i5a-native-progress/progress.json)
and [progress archive](../evidence/Ariadne/i5a-native-progress-evidence.tar.gz)
preserve the earlier rejected attempts. Their flags remain unchanged; the new
accepted records establish the later result.

Run the applicable root Rust checks, native contracts/corpus, replay, mutations,
performance and controlled-capture gates after relevant changes. Keep timing
campaigns separate from builds. A partial tier or one passing capture cannot
satisfy the complete controlled tier. Commit and push remain separate actions.
