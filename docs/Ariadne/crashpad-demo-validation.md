# Native Windows capture with crashpad-nzsn

## Context and follow-up

**Status.** Native Windows x64 integration and two real captures demonstrated on
2026-10-03. This historical record passes independent checks and I5a answers,
but its CLI medians exceed the frozen 1,500 ms condition. The [2026-10-05 native successor](i5a-native-qualification.md) qualifies both
capture modes under the unchanged budgets and its pinned dependency snapshot.

**Why this document exists.** The [first I5a delivery](i5a-validation.md) had
source/fixture evidence but no controlled real Windows capture. This experiment
supplies a small reproducible native process and retained capture identities.

**What this document establishes.** The user-selected `crashpad-nzsn` fork can
be embedded in this demo, capture its deliberate null write in partial/full mode,
and supply the context and bytes needed for Ariadne's conditional zero-address answer.

**Where to go next.**

- [Demo and reproduction commands](../../native/crashpad-demo/README.md) describe
  the program, isolated dependency preparation and Windows scripts.
- [Native qualification successor](i5a-native-qualification.md) records fresh
  native-default measurements, passing gates and the selected dependency snapshot.
- [Retained record](../../evidence/Ariadne/crashpad-demo-validation.json) and
  [archive manifest](../../evidence/Ariadne/crashpad-demo-evidence-manifest.json)
  retain exact build, capture, inspection, answer and timing evidence.
- [I5a contracts](i5a-contracts.md) define the assessment and its premises.
- [I5a plan](../../Plans/i5a-zero-address.md) retains the independent qualification tiers.

**What remains unresolved.** The historical original Windows I4 artifact/query remains
separate and unexercised. The native successor qualifies these two captures;
this function does not establish broad Windows workload, instruction coverage,
Linux integration or complete process-memory capture.

The [documentation map](../documentation-map.md) is optional navigation.

## Build and capture

The original checkout stayed clean on `nzsn` at
`7a884c25c84c46352fc6f16ef0a798ece2b77e84`. The demo links `client:client` and starts
the matching handler synchronously. Uploads are disabled in the database, and no
upload URL is configured. It records an independently declared null-write witness
before calling the separate fault function.

GN 2077 and Ninja 1.8.2 built the program, handler and database utility on Windows
11 using the fork-pinned Clang 20, MSVC libraries 14.51.36231 and Windows SDK
10.0.28000.0. The isolated build required three mini_chromium compatibility
headers and an x86/x64-only build-helper adjustment, described in the
[recipe](../../native/crashpad-demo/README.md#isolated-source-preparation).
Crashpad's capture implementation was not edited. Unsupported ARM64 generation
fails explicitly; repeated x64 GN generation is stable.

Both runs exited with the expected access violation `0xc0000005`. A missing
handler and an invalid mode separately exited before the deliberate crash and
produced no witness or dump. The database utility independently confirmed uploads
disabled after each successful capture.

| Mode | Dump bytes | Memory stream | Full-memory flag |
| --- | ---: | --- | --- |
| Partial | 225,408 | `MemoryList` | Clear |
| Full | 15,987,422 | `Memory64List` | Set |

Local raw artifacts and matching executables are retained beneath
`tmp/crashpad-demo/20261003/{partial,full}/`; they are ignored and not committed.
The native build/database also remains under
`C:\Users\ayden\AppData\Local\Temp\ariadne-crashpad-demo-20261003-final`.

## Independent observations and Ariadne result

The [raw inspector](../../native/crashpad-demo/inspect_capture.py) separately
checks dump structure, Windows NT/AMD64 fields, process ID, exception parameters,
CONTROL/INTEGER validity, RIP and module/PE agreement. It checks the requested
256-byte code range for holes/conflicts and compares the relevant captured bytes
to the supplied executable. Its focused synthetic tests cover both memory stream
forms, identical/conflicting overlaps, invalid context/RIP, unexpected opcodes,
truncation and exclusive output creation.

In both real captures:

- Exception instruction and captured RIP equal the recorded fault-function entry.
- The executable's fault RVA is `0x3ae0`; bytes are `c7 01 05 00 00 00`.
- Independent disassembly is `mov dword ptr [rcx], 5`, followed by `ret`.
- Captured `RCX` is zero. The instruction writes four bytes; the exception
  independently reports access operation write and inaccessible data address zero.
- Context flags are `0x10001f`, with the required validity groups present.

In the original run, the Linux-hosted Ariadne CLI, using its Windows decode target
and pinned BAP semantic provider, returned `consistent_with_evidence`, evaluated address
zero and no assessment gaps for both dumps. Base reports remain byte-identical
when assessment is enabled. Text/JSON/DOT are retained; both DOT families parse
with Graphviz. These are conditional numeric results, not inferred crash history
or a general root-cause diagnosis.

## Historical measurement and qualification

The original 2026-10-03 assessment runner checked that run's source/fixture
acceptance record and source/tool hashes. It performed one warm-up and five
measured repeats per base/assessment mode, plus separate bound-assessment phases.
These measurements predate adoption of the native analysis default; they do not
qualify its performance. The original criteria remain unchanged.

| Capture | Combined phase median | Assessment CLI median | Assessment CLI range |
| --- | ---: | ---: | ---: |
| Partial | 1.720 ms | 1,820.299 ms | 1,742.791–1,853.441 ms |
| Full | 1.625 ms | 1,824.496 ms | 1,804.609–2,056.832 ms |

Both historical phase medians meet 10 ms. Both historical CLI medians exceed
1,500 ms, so that controlled-case acceptance result is false. Capture generation
and numeric correctness remain demonstrated. Source/tool identities stayed stable; output
hashes repeat. The differences between base and assessment timings do not
establish a speedup or identify the cause of the CLI cost.

## Native successor qualification

The original dump, witness, executable, capture and build records are preserved.
Fresh independent inspections use separate files and retain the original
producer identities. Current inspector source metadata does not replace the
historical build's source identities.

The [2026-10-05 native successor](i5a-native-qualification.md) passes all 14
source/fixture gates, 17 investigation gates and both controlled capture modes
under a read-only MirrorRust dependency snapshot. Fresh assessment CLI medians
are 869.642 ms for partial and 873.537 ms for full; native phase medians are
1.067 ms and 1.032 ms after the I4 source refresh. Both unchanged criteria pass. No production performance
patch was needed. Earlier diagnostics and rejected aggregates remain unchanged
in the [progress record](../../evidence/Ariadne/i5a-native-progress/progress.json).

The [assessment runner](../../native/crashpad-demo/assess.py) requires a current
passing `ariadne.i5a-acceptance/v2` record through `--source-fixture-record`,
separate fresh partial/full inspections through `--inspection-dir`, and the
matching qualification environment. It rejects historical partial and v1
prerequisites. The [reproduction commands](../../native/crashpad-demo/README.md#inspect-and-analyze)
explain the snapshot wrapper and default/explicit-native report checks.

The [separately re-pinned Windows I4](i4-windows-repin-validation.md) uses the
98-instruction capture and retains the 2,000 ms condition. Correctness passes;
its CLI median is over budget. This two-instruction I5a demo does not qualify I4.
