# Ariadne minidump input

## Context and follow-up

**Status.** Current minidump API and preparation workflow.

**Why this document exists.** [Reader design](../file-reader-design.md) defines immutable storage, provenance and local-start discovery.

**What this document establishes.** The module opens captured memory, retains holes/conflicts and evidence, and materializes local instruction starts from supplied entries. Seeds select analysis questions without becoming discovery roots.

**Where to go next.**

- [BAP module](bap.md) — supplies semantics for captured instruction prefixes.
- [Native analysis qualification](../bap-core-qualification.md) — validates the
  capture-bound native analyzer, report equivalence and backend selection.
- [Minidump report contract](../stage-c-report-schema.md) — joins preparation evidence with analysis output.
- [Investigation contracts](../investigation-contracts.md) — bind a fault-address question to the prepared analysis.
- [I5a contracts](../i5a-contracts.md) — bind retained exception-context observations to a zero-address assessment.

**What remains unresolved.** A minidump cannot establish an earlier executed path by itself. Entry evidence must be supplied; unsupported instructions and missing capture may keep the result partial.

For the wider context, see the optional [documentation map](../../documentation-map.md).

`ariadne::input` reads **AMD64 Windows and Linux/Crashpad minidumps** into an
immutable captured-memory snapshot, obtains bytes at discovered instruction
starts, and prepares the existing Ariadne analysis request. The module is enabled
by the root package's `input` feature. PE/ELF images and ELF core files are
not implemented here.

The supported [minidump investigator CLI](../../../src/bin/ariadne-minidump.rs) now
joins the reader, BAP instruction effects, analyzer and renderer into one
[versioned evidence report](../stage-c-report-schema.md). A
tool-produced [captured predecessor fixture](../stage-b-c-validation.md)
demonstrates an earlier address producer reaching the crash-IP seed.
A separate [controlled Chromium real-capture case](../priority-1-real-capture-validation.md)
retains an independently anchored local entry, possible RBX producer and
explicit opaque-call gaps. Its raw dump remains an external, hash-pinned
artifact rather than a committed fixture.
The [investigator examples](../minidump-investigator-examples.md)
show the Linux/Windows CLI commands and the readable instruction overview.

BAP is the sole semantic backend for `FileSnapshot::prepare` and the CLI.
Build the [BAP helper/runtime](../../../native/bap/README.md) and LLVM MC decode reference
first. The CLI additionally requires the [native analysis helper](../../../native/bap-core/README.md)
by default; preparation itself does not run either solver. `prepare_with_bap`
accepts an explicit configuration; the ordinary method
uses `Config::from_env`. No semantic fallback is made to LLVM. The separate
[Stage 1 removal plan](../../../Plans/completed/bap-only-semantics.md) defines this change.

The following library example deliberately selects the Rust reference with
`ariadne::analyze`; it does not illustrate the CLI's native default. Native
callers use `NativeAnalyzer::from_capture(&core_config, session, &prepared)?.complete()`
with a manifest-bound `CoreConfig`, as in the [CLI](../../../src/bin/ariadne-minidump.rs).

```rust
use ariadne::effects::PreparationOptions;
use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
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
[effect rule matrix](../operand-effects-rules.md); reading Linux
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

The module shares the root Cargo manifest and lockfile, with declared Rust
1.85 compatibility; recorded execution used Rust 1.96.0. Ordinary root tests
exercise portable input behavior, while ignored native tests require helpers.

```sh
cargo test --offline --locked --manifest-path Cargo.toml
cargo clippy --offline --locked --manifest-path Cargo.toml --all-targets -- -D warnings

# Build the BAP provider, default analysis helper and independent decode reference.
python3 native/bap/setup.py
bash native/bap/build.sh
python3 native/bap-core/setup-sdk.py
python3 native/bap-core/build.py --output target/bap-core-native
# See the LLVM guide for matching headers/runtime setup.
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  bash native/llvm_mc/build.sh
ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" \
  cargo test --offline --locked --manifest-path Cargo.toml --test input_native -- --ignored
bash Specs/check-input.sh
```

The complete gate also checks the existing effects/MBT pipeline, isolated
minidump mutations, the pinned Stage B/C fixtures and CLI, and two explicitly
supplied, hash-pinned Breakpad test dumps:

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
ARIADNE_REAL_DUMPS=/path/to/breakpad/src/processor/testdata \
  python3 tools/check_minidump.py
```

Missing external fixtures are reported as unavailable verification, not a pass.
No fixture is downloaded or repaired by the gate. The `inspect` example reads a
minidump and can optionally prepare an explicitly supplied hexadecimal root:

```sh
cargo run --offline --locked --manifest-path Cargo.toml --example inspect -- \
  crash.dmp target/ariadne-llvm-mc 140001000
```


To render a result with distinct entry and seed addresses, use the
[`render_minidump` example](../../../src/examples/render_minidump.rs). It writes the core
report/DOT to stdout and upstream diagnostics to stderr. See the
[rendering guide](../result-rendering.md). The existing `inspect`
example retains its summary output.

To publish text, DOT and JSON v1 together from one frozen query:

```sh
cargo run --offline --locked --manifest-path Cargo.toml \
  --bin ariadne-minidump -- tests/input/fixtures/stage_b_windows.dmp \
  --decoder target/ariadne-llvm-mc --entry 0x7ff700001000 \
  --seed-exception-rip --output-dir /tmp/ariadne-investigation
```

Use `--format text|dot|json` instead of `--output-dir` for one stdout format.
`--entry` and `--seed` may repeat and are semantic hexadecimal VAs. The
exception RIP option adds a seed only; it never invents an earlier root. The
output directory must not exist. `--max-starts N` bounds local discovery and
fails before publishing when exhausted. See the [Stage B/C validation](../stage-b-c-validation.md)
for exact fixtures, graph and output evidence.

The investigator optionally accepts `--stateflow-input SEMANTICS_JSON` for
explicit finite semantic facts bound to the prepared snapshot. It emits separate
`machine-state` reports beside the original minidump reports. See
[Stage E completion](../stage-e-completion.md) for the input schema,
model-relative feasibility and preserved recovery/preparation evidence.

## Fault-address investigation question

The [first investigation module](investigation.md) explains per-byte
possible address producers with captured evidence, alternatives and concrete
missing-evidence requirements. Select an instruction and its explicit access
index with `--explain-fault-address VA --memory-access N`; the site becomes a
slice seed, never an entry root. `--explanation-only --format text|json|dot`
returns its independently versioned result. Output-directory mode adds
`explanation.txt/.json/.dot` beside the existing reports.

The [contracts](../investigation-contracts.md) and
[qualification](../investigation-validation.md) define the current
scope. Partial answers retain unknown entry, call and memory alternatives;
producer dependencies are not a historical execution trace or UAF proof.

The separate [I5a assessment](../i5a-contracts.md) retains reader-owned raw
exception/context fields, source spans and valid register observations behind
the ordinary metadata view. `bind_fault_context` rejects changed public metadata
and binds the same completed analysis. Use `--assess-zero-address VA --memory-access N`
with `--assessment-only --format text|json|dot` or a new output
directory. It admits only the reviewed Windows AMD64 scalar MOV profile and
returns unknown for absent or contradictory prerequisites. Old report formats
and Stage B fixture bytes are unchanged.
