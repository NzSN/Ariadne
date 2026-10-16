# Captured tables for the nine unresolved jumps

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

## Context and follow-up

**Status.** Read-only remote WSL witness on 2026-10-14. The dump contains all nine tables and captured destination prefixes. Production target lists and guard coverage remain unchanged.

**Why this document exists.** The [latest guard retry](../../evidence/Ariadne/native-request-budget/20261014/README.md) lists nine indirect jumps with empty target sets. The question is whether their destinations can be recovered from heap/captured dump memory.

**What this document establishes.** Retained typed BIL shows a common bounded relative-32 table form. Fresh reads through the qualified immutable reader obtain all 370 entries and 64 distinct snapshot-relative candidate destinations. [Raw reads](../../evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/tables.json) retain table spans/contributors, signed offsets and destination code prefixes; [verification](../../evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/verification.json) binds the diagnostic and source graph.

**Where to go next.** Read the [target-resolver contract](../../docs/Ariadne/indirect-target-resolution.md#captured-memory-premise) for the required memory premise, and the [guard contract](../../docs/Ariadne/justified-branch-pruning-design.md) for complete incoming coverage. Combined resolver/guard preparation needs separate integration and validation.

**What remains unresolved.** This is a candidate witness, not a complete resolver certificate, executed index or historical branch. The official graph has not acquired these edges. Full incoming-state closure, semantics/alias validation, discovery of new targets and receipt/native binding remain unperformed.

## What memory supplies

All nine tables reside in captured `electron.exe` **`.rdata`**, with region type `MEM_IMAGE` (`0x1000000`) and captured protection `PAGE_READONLY` (`0x2`). Heap/object byte loads provide some index values; enumerating a conservative branch-bounded index range does not require identifying the exact historical heap value.

The common admitted instruction pattern is:

```text
index <= unsigned_bound
slot   = table_base + 4 * index
offset = sign_extend_32_to_64(captured_read32(slot))
target = u64(table_base + offset)
jmp target
```

The table base is an instruction-derived RIP-relative constant. All tables form the contiguous captured interval `[0x00007ff77ba90408, 0x00007ff77ba909d0)`: **1,480 bytes / 370 signed 32-bit entries**. Every table read is complete and conflict-free. Entries yield **64 distinct targets** in the caller's runtime function range. Every target has a fully captured 15-byte prefix; instruction decoding and final discovery are separate work. **13** destinations already occur in the current candidate graph and **51** do not.

| Jump | Table base | Conservative indices | Entries | Distinct targets |
| --- | --- | --- | --- | --- |
| `0x00007ff77440361f` | `0x00007ff77ba90408` | 0–113 | 114 | 13 |
| `0x00007ff774403fd7` | `0x00007ff77ba905d0` | 0–38 | 39 | 7 |
| `0x00007ff77440417a` | `0x00007ff77ba90718` | 0–38 | 39 | 7 |
| `0x00007ff774404384` | `0x00007ff77ba907e0` | 0–113 | 114 | 13 |
| `0x00007ff7744048c5` | `0x00007ff77ba90690` | 0–24 | 25 | 4 |
| `0x00007ff774408ab0` | `0x00007ff77ba907b4` | 0–10 | 11 | 6 |
| `0x00007ff774409837` | `0x00007ff77ba906f4` | 0–8 | 9 | 5 |
| `0x00007ff7744099bf` | `0x00007ff77ba9066c` | 0–8 | 9 | 5 |
| `0x00007ff77440da09` | `0x00007ff77ba909a8` | 0–9 | 10 | 4 |

Bounds are derived from retained local unsigned comparisons/fallthrough edges; earlier conditions may narrow them. The ninth site has a local bounds-check loop whose observed edges preserve its table base. This does not independently close all incoming paths of the expanded graph.

## Why they remain unresolved in the current query

The existing finite resolver supports this relative-32 encoding. Guarded frame preparation currently selects `PreparationExtension::GuardAdmission`, which supplies no target-resolution coordinator; the two preparation extensions are separate. Empty target sets therefore do not indicate missing table bytes.

To use the witness, combined preparation must run admitted target/value analysis on the provisional candidate graph, read the named captured tables, add verified candidate edges, queue newly reached starts and recheck both resolution and guard receipts until discovery closes. The 51 new destinations can expose additional instructions and obligations. Neither guard stops nor unknown memory/call effects can be treated as no-ops to force closure.

A complete certificate is relative to the explicitly declared `FrozenCapturedControlData` premise or other independently admitted stability evidence. The read-only section metadata corroborates table storage; it does not prove that all earlier runtime loads saw today's captured bytes. Crash-time registers must not be substituted into earlier jumps. Reading unrelated executable-looking heap pointers cannot establish this dependency chain or completeness.

## Scope

Fresh evidence is limited to captured memory reads and numeric candidate enumeration under the local BIL table form/bounds. No production source, budgets, query roots, target sets, completed core analysis or execution history was changed. The full dump stays remote. The diagnostic used the already-qualified library on remote WSL; there was no local Cargo/native compilation.
