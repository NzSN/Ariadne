# Windows I4 replacement and qualification

## Context and follow-up

**Status.** Historical re-pin result from 2026-10-05. Independent capture checks
and all 17 investigation gates pass; that run exceeded the 2,000 ms CLI limit.
The later [native performance qualification](i4-performance-validation.md)
closes the same fixed-budget clause at 1,692.696 ms. The original record and
its `fullI4RealCaptureAcceptance=false` flag remain unchanged.

**Why this document exists.** The [investigation design](investigation-layer-design.md)
required a real Windows 98-instruction workload, but its original artifact was
lost. The [replacement plan](../../Plans/i4-windows-repin.md) makes a new active
capture identity explicit without rewriting historical results.

**What this document establishes.** The active pin, independent producer witness,
source/tool-bound correctness checks, raw timing evidence and remaining budget
failure. It also distinguishes this bounded I4 obligation from BAP's unlimited
workload timing policy and the separate I5a numeric question.

**Where to go next.**

- [Completed native performance follow-up](i4-performance-validation.md) — meets both fixed budgets with preserved capture/query identity and verified regression evidence.
- [Active case](../../evidence/Ariadne/investigation-windows-workload-case.json) —
  exact inputs, query, replacement authorization and frozen timing contract.
- [Independent inspection](../../evidence/Ariadne/i4-windows-capture-inspection.json)
  — raw captured bytes, matching PE, instruction boundaries and checksum witness.
- [Accepted re-pin record](../../evidence/Ariadne/i4-windows-repin-validation.json)
  — correctness success and explicit full-I4 timing failure.
- [Investigation contracts](investigation-contracts.md) — possible producers,
  unknowns, schemas and exact-query measurement requirements.
- [Stage ledger](../../Plans/investigation-layer.md) — remaining performance and
  later investigation capabilities.
- [Capture recipe](../../native/crashpad-demo/README.md) — Windows producer,
  independent inspection and distinction from the small I5a capture.

**What remains unresolved.** The later performance campaign qualifies this
exact case within 2,000 ms. Future source/tool changes need fresh or exact-identity
verified evidence. The replacement does not qualify
the original Electron crash, reconstruct executed history, establish a lifetime
or root cause, or qualify a packaged cross-platform release. BAP lifting remains
trusted. Any performance change needs a measured diagnosis and fresh validation.

## Active input and independent evidence

The existing Windows AMD64 partial Crashpad capture was re-inspected and selected
as `crashpad-windows-checksum-98-i4-v1`. No new host-side crash was generated.
The dump is **217,936 bytes**, SHA-256
`1bd80af7a739471a7026776bfb37cbbe5953d01ad122e7cf7db0392f84da0b0a`.
Its matching PE is 428,032 bytes, SHA-256
`00906b04af5dfcfff66b15657e81c08152f3e49479820bf084123c41286fc89e`.

| Query component | Active value |
| --- | --- |
| Discovery entry | `0x00007ff7382f4840` |
| Fault instruction and slice seed | `0x00007ff7382f49b4` — `mov dword ptr [rcx], 5` |
| Independent address producer | `0x00007ff7382f49b1` — `mov rcx, rax` |
| Memory-access index | `0` |
| Workload | 98 instruction starts; 379 captured function bytes |

Independent inspection checks every function byte against the matching PE,
raw context/exception fields, query sites, instruction starts and the producer
checksum `0x4bea2`. Production analysis continues to use captured bytes only;
the PE is comparison evidence. Entries drive discovery and the fault seed
selects results. Possible producer alternatives retain their premises and gaps.

The unchanged [input bundle](../../evidence/Ariadne/bap-windows-workload-inputs.tar.gz)
contains all 23 hash-verified capture/PE/witness/build/source entries. Its SHA-256
is `8ef47d751829680caa4d9a852e3b9c9d6f2906150a7d9bfec8f96b3487f63222`.
The active I4 materializer verifies the complete archive inventory, rejects
unsafe members, and requires any explicit dump override to match the pin.
The [original manifest](../../evidence/Ariadne/priority-4-real-capture-case.json)
remains byte-identical history. Its missing artifact is retired as an active I4
obligation by this user-authorized replacement, without retroactive acceptance.

## Recorded re-pin result (2026-10-05)

The native-default release explanation CLI ran one warm-up and five measured
repeats on the exact query. Native receipts verify the captured BAP backend and
98 decoded starts; source/tool inventories and the dependency environment stay
stable. Repeated report identities, the expected producer and unchanged base
analysis pass. Explicit explanation gaps remain visible.

| Requirement | Observed result |
| --- | --- |
| Independent capture/query/producer checks | Pass |
| Investigation implementation gates | 17/17 pass |
| Windows explanation-CLI median | **4,774.451 ms** |
| Frozen Windows explanation-CLI ceiling | **2,000 ms** |
| Windows timing status | Valid measurement, over budget |
| Re-pin success | `repinPassed=true` |
| Complete I4 acceptance | `fullI4RealCaptureAcceptance=false` |

The existing Linux 250 ms incremental phase condition also passes. Its benchmark
uses the Rust reference analyzer and is labeled accordingly; it is not evidence
of native phase performance. Base CLI and phase timings cannot replace the
Windows explanation-mode CLI measurement. BAP's separate unlimited policy does
not apply to this I4 pin. No production performance patch or threshold change
was made.

The refreshed [core qualification](bap-core-qualification.md) passes 20 gates,
with 632 stable source files and 1,355 archive entries. The separate
[native I5a qualification](i5a-native-qualification.md) passes 14 gates and both
controlled capture modes with unchanged 1,500 ms CLI / 10 ms phase limits.
Those narrower successes do not grant full I4 acceptance.

## Reproduction and retained evidence

Use the same [read-only MirrorRust snapshot wrapper](../../tools/with_mirrorrust_snapshot.py)
for builds, qualification and evidence verification. The exercised dependency
manifest SHA-256 is
`f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56`.
The [native qualification guide](i5a-native-qualification.md#reproduction-and-retained-evidence)
explains creating a new snapshot and the required runtimes/helpers/model tools.

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/qualification-deps/mirrorrust-i5a-complete-20261004 \
  --sha256 f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56 -- \
  python3 tools/check_investigation.py
```

Default measurement materializes the active Windows bundle automatically.
`--windows-dump` on `tools/measure_investigation.py`, or `ARIADNE_I4_WINDOWS_DUMP`,
selects only an exact matching copy. Explicit `--skip-windows` produces an
implementation-only record and cannot grant full I4 acceptance. Workload v3
records bind the active case ID/digest; legacy records and incomplete source
inventories cannot qualify this replacement. The aggregate's narrower `passed`
field and process success do not override its full-I4 flag.

The [865-entry evidence archive](../../evidence/Ariadne/i4-windows-repin-evidence.tar.gz)
and [verified manifest](../../evidence/Ariadne/i4-windows-repin-evidence-manifest.json)
retain exact source snapshots, independent inspection, pin, nested producer
records, raw CSVs and repeated report bundles (18,012,236 bytes). Original runner
paths are mapped to retained entries. Previous accepted core and I5a bundles are
preserved under their `2026-10-05-before-i4-repin` history directories; previous
failed progress records retain their flags. Source/tool changes require fresh
or complete identity-verified evidence reuse.
