# Ariadne minidump input

`ariadne-input` reads **AMD64 Windows and Linux/Crashpad minidumps** into an
immutable captured-memory snapshot, obtains bytes at discovered instruction
starts, and prepares the existing Ariadne analysis request. This package is
separate from the dependency-free core. PE/ELF images and ELF core files are
not implemented here.

```rust
use ariadne::effects::PreparationOptions;
use ariadne_input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
use std::path::Path;

let snapshot = FileSnapshot::open_minidump("crash.dmp", OpenLimits::default())?;
let query = AnalysisQuery {
    entry_points: [0x140001000].into(), // explicit VAs, not file offsets
    slice_seeds: [0x140001006].into(),
};
let prepared = snapshot.prepare(
    &query, Path::new("target/ariadne-llvm-mc"),
    &PreparationOptions::default(), PrepareLimits::default(),
)?;
let result = ariadne::analyze(prepared.prepared.request)?;
// Retain prepared.snapshot, reads, materialization and the remaining
// prepared.prepared instruction evidence/gaps alongside result.
# Ok::<(), Box<dyn std::error::Error>>(())
```

`from_minidump_bytes(Vec<u8>, limits)` runs the same validation for an already
owned artifact. `metadata()` exposes artifact identity, platform, streams,
modules, threads, exception observations and metadata gaps. `read_prefix(va, n)`
returns the contiguous unambiguous bytes available at a VA, their contributor
file offsets and a stop reason. Conflicting contributors at the first blocked
byte are retained separately from the usable prefix.

## Input and provenance rules

- Only little-endian AMD64 minidumps with Windows NT or Linux platform IDs are
  accepted. The input platform selects the decoder target, independently of the
  host. The native helper still needs to be built on the host being used.
- MemoryList, Memory64List and ordinary ThreadList stack descriptors supply
  bytes. Memory64 payload offsets advance by preceding payload lengths. Module
  and MemoryInfo records describe mappings but never create captured bytes.
- Adjacent capture fragments can compose an instruction. Identical overlapping
  bytes preserve all contributors; disagreeing bytes stop a read. Unavailable
  bytes are never synthesized, zero-filled or replaced from an executable.
- A short prefix can decode a complete instruction. A conflict or hole after
  that instruction does not invalidate it. A truncated instruction retains its
  read evidence and an unavailable obligation.
- Module names and CodeView records are retained as evidence. No referenced
  module, symbol or fallback file is opened. No runtime image identity is
  inferred from a filename, timestamp or matching size.
- Captured register groups honor AMD64 context-validity flags. Thread and
  exception observations stay separate; no fault address is substituted for
  RIP and no crash-time register value prunes earlier control flow.

Structural preflight bounds directories, supported-list counts, nested payloads
and all file/VA arithmetic before typed metadata parsing. Supported stream IDs
are 3, 4, 5, 6, 7, 9 and 16. Duplicate supported streams/thread IDs are rejected.
Unknown streams (including ThreadExList and optional Crashpad extensions) are
inventoried but not interpreted; their container ranges are still checked.
Absent/unsupported contexts become metadata gaps. A nonempty nested payload
outside the file is malformed and prevents snapshot publication.

The pinned `minidump` parser handles system/module/thread/exception metadata.
Ariadne preflights and indexes raw capture descriptors itself so the parser's
permissive skipping and first/last-overlap choices cannot discard evidence.
`state:other` and instruction effects retain the scope described in the
[effect rule matrix](../docs/Ariadne/operand-effects-rules.md); reading Linux
files does not add syscall, signal-handler or TLS semantics.

## Discovery and limits

The materializer follows only prepared local successors. It decodes explicitly
referenced overlapping x86 starts and records their overlap. It does not follow
call-only targets, promote slice seeds to roots, or run the Analyzer repeatedly
while constructing inputs. Independently supplied callee roots work normally.

A missing prefix is an ordinary partial-analysis outcome. A resource limit or
protocol failure is an error: no incomplete construction is published as a
finished `AnalysisRequest`. `LimitReached` carries diagnostic progress. After
successful construction the final Analyzer visit set matches the materializer's
attempted set. Unattempted call/seed references are distinguished from failed
memory reads; a missing seed need not imply absent bytes.

Default open limits are 256 MiB artifact bytes, 1,024 streams, 131,072 entries
per supported list, 131,072 capture ranges, 16 MiB cumulative nested metadata
payload, 64 overlapping captures at a VA, and 64 KiB per public read. Preparation
allows 4,096 starts, 8,192 referenced candidates, 61,440 returned prefix bytes,
4,096 decoder batches and at most 128 starts per batch. These are explicit
resource bounds, not large-dump performance guarantees. Owned buffering keeps
input bytes stable and intentionally excludes artifacts over the selected limit.

Long linear paths may launch many decoder batches. Calls and memory effects
remain conservative. Core `scope_closed()` does not certify missing seeds,
preparation precision, coherent process capture or complete ISA semantics.

## Build and verification

Dependencies are locked separately and declared Rust 1.85-compatible; execution
validation currently uses Rust 1.96.0. Root offline tests do not need this package.

```sh
cargo test --offline --locked --manifest-path input/Cargo.toml
cargo clippy --offline --locked --manifest-path input/Cargo.toml --all-targets -- -D warnings

# See the LLVM guide for matching headers/runtime setup.
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  bash native/llvm_mc/build.sh
ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" \
  cargo test --offline --locked --manifest-path input/Cargo.toml --test native -- --ignored
bash Specs/check-input.sh
```

The complete gate also checks the existing effects/MBT pipeline, isolated
minidump mutations and two explicitly supplied, hash-pinned Breakpad test dumps:

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
ARIADNE_REAL_DUMPS=/path/to/breakpad/src/processor/testdata \
  python3 tools/check_minidump.py
```

Missing external fixtures are reported as unavailable verification, not a pass.
No fixture is downloaded or repaired by the gate. The `inspect` example reads a
minidump and can optionally prepare an explicitly supplied hexadecimal root:

```sh
cargo run --offline --locked --manifest-path input/Cargo.toml --example inspect -- \
  crash.dmp target/ariadne-llvm-mc 140001000
```
