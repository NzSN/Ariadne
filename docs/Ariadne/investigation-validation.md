# First fault-address investigation delivery

## Context and follow-up

**Status.** Historical first-question evidence; the later [native I4 performance qualification](i4-performance-validation.md) meets both fixed budgets on the active replacement query.

**Why this document exists.** [Claim contract](investigation-contracts.md) requires identity-bound alternatives and explicit evidence gaps.

**What this document establishes.** The first delivery exercises identity, address extraction, alternatives, aliases, opaque effects and report publication on both platform fixtures and a controlled Linux capture.

**Where to go next.**


- [2026-10-05 Windows I4 replacement](i4-windows-repin-validation.md) — supersedes the older missing-artifact obligation with an independently inspected active case; correctness passes; the later [native performance qualification](i4-performance-validation.md) meets the unchanged CLI budget.

- [Remaining work](../../Plans/investigation-layer.md) — tracks full I4 and later I5–I7 instead of implying general root-cause support.
- [CLI examples](minidump-investigator-examples.md) — provide the surrounding captured-analysis workflow.
- [Evidence guide](../../evidence/Ariadne/README.md) — explains archive and measurement identities.

**What remains unresolved.** These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. The first fault-address question is implemented. The [active I4 replacement](i4-windows-repin-validation.md) closes its lost-artifact gap and passes correctness; the later [native performance qualification](i4-performance-validation.md) closes its fixed CLI timing clause. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered.

For the wider context, see the optional [documentation map](../documentation-map.md).

Implemented against the working tree following **`7de5a1e`** for
[I0–I4](../../Plans/investigation-layer.md). **I0–I3 are implemented; I4 is
qualified for both platform fixtures and the pinned controlled Linux capture.
Full real-Windows I4 acceptance was partial at this delivery.** The later
[native performance qualification](i4-performance-validation.md) closes the
replacement-query clause; subsequent I5a/I5b and BAP migration have separate records.

This record retains the pre-consolidation source paths. The
[Rust source-layout delivery](rust-source-layout.md) provides the current
source-bound regression and updated build/test paths.

The [current source-bound record](../../evidence/Ariadne/investigation-validation.json) passes all
**16 gates**. Its nested **12-gate Stage E regression** passes with stable
sources, including the full minidump/effects/native/formal pipeline and existing
MirrorRust replay/mutations. New investigation qualification adds **11 actual
producer/adapter/claim mutants**, rejected through unchanged observers. Compile
errors and tool timeouts receive no sensitivity credit.

The implemented module exposes one domain question through a small interface.
`input::investigation::bind_investigation` checks exact prepared/analyzer request
identity, recomputed query/limits identity and captured evidence. BAP preparation
retains bounded modular address expressions from typed BIL; the root analysis
semantics stay unchanged. The independent module returns typed, content-addressed
claims, byte origins, evidence references, alternatives and concrete evidence
requirements. Reports retain those relationships in text, strict JSON and DOT.
The [contracts](investigation-contracts.md) describe the actual schema and limits.

```sh
cargo build --offline --locked --release --manifest-path Cargo.toml
target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 \
  --explain-fault-address 0x401006 --memory-access 0 \
  --explanation-only --format json
```

Both Stage B platform cases identify the earlier MOV as a possible RAX-byte
producer and retain its dump offsets. The unrelated RCX write is excluded from
address producers. The controlled NOT case includes the NOT producer and the
upstream MOV dependency. Alias/self-move, branch-join, opaque-call, weak-memory,
query mismatch, absent/conflicting capture, missing seed, strict report and
transactional CLI publication cases pass.

The first fixture answer is **partial**, because its upstream RBX entry origin
is not observed historical input provenance. It identifies that requirement
rather than manufacturing a previous execution. Byte grouping remains
alternative-wise and cannot establish one co-occurring whole-pointer value.

The real controlled Chromium/Linux query retains its **34 decoded sites,
45 edges, 28-site slice and one recovery obligation**. Its fault-address
explanation has eight RBX-byte groups, 28 captured instruction evidence records,
4,168 typed claims and 37 gaps. The independently pinned possible producer
`0x0000566817922de6` remains among alternatives. Opaque-call, entry and memory
uncertainty remain visible; the module does not infer UAF from the fixture's name
or known trigger. Claim classes are observed captured bytes, derived dependencies
under premises, and unknown evidence requirements.

Release measurements use one warm-up and five repeats for the normal CLI and
separate binding/explanation/all-format rendering. The measured real-Linux
phase medians are approximately **1.12 ms binding**, **86.86 ms explanation**,
and **65.21 ms rendering**: about **153 ms combined**, below the frozen **250 ms
incremental phase condition**. Median full CLI time is approximately **1,408 ms
without** the explanation and **1,626 ms with** it. The low-level analysis is
identical in both modes. Min/max, RSS, counts and output hashes are retained in
[CLI samples](../../evidence/Ariadne/investigation-cli.csv), [phase samples](../../evidence/Ariadne/investigation-phase.csv)
and the machine-readable record. These measurements are bounded observations,
not universal scale or worst-case guarantees.

The [evidence manifest](../../evidence/Ariadne/investigation-evidence-manifest.json) binds the
[derived evidence archive](../../evidence/Ariadne/investigation-evidence.tar.gz): complete typed
explanations, reports and actual test/mutation/regression logs. Raw dump bytes,
compiler caches and native runtime archives remain ignored/external.

**Historical remaining full-I4 clause at this delivery:** the original 2,028,400-byte Windows artifact with
SHA-256 `4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86`
is unavailable for a fresh question acceptance and normal CLI measurement.
The existing 2,000 ms median condition remains unchanged. Windows synthetic
fixtures do not replace this historical-capture requirement. The passing
`passed` field credits the explicitly exercised tier; `fullI4RealCaptureAcceptance`
is false and the missing clause is retained. This does not qualify BAP Stage 2
or accept an AMD64 ISA step; the recorded Stage D count was **0/49**.
The independent ISA track is now [retired](semantic-assurance.md).

The current runner materializes the active replacement automatically; the
old original-dump environment variable no longer selects its Windows case.
Use the [snapshot wrapper](i4-windows-repin-validation.md#reproduction-and-retained-evidence)
for these current commands:

```sh
python3 tools/check_investigation.py
# Optional exact matching copy of the active replacement:
ARIADNE_I4_WINDOWS_DUMP=/path/to/active-pinned.dmp python3 tools/check_investigation.py
```

Validation and derived evidence were retained before the user-authorized
publication. No higher-level hypothesis/object/source/cross-capture capability
is claimed by this first delivery.
