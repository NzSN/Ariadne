# LLVM MC byte-span adapter

The optional native decoder in `native/llvm_mc/` uses LLVM MC 20.1.2 to decode
x86-64 instruction bytes at snapshot-scoped virtual addresses. The Rust
`ariadne::llvm_mc::ByteSnapshot` adapter calls that decoder and constructs the
fixed `AnalysisRequest` consumed by the existing CFG, reaching-definition and
slice engine. No LLVM code is linked into the Rust crate; its offline build and
`unsafe_code = "forbid"` policy remain intact.

This is a byte-span adapter. It does **not** open a PE/ELF binary or crash dump,
map VAs to file offsets, validate image identity, or prove that a supplied span
is from the stated snapshot. Binary/dump readers must establish those facts
before populating `ByteSnapshot`. The [separate minidump package](../input/README.md) now supplies captured
memory and local instruction-start discovery. PE/ELF image readers, ELF core
readers and the analyzer CLI remain separate roadmap work.

## Build and check

The native module is pinned at compile time to LLVM 20.1.2. The current build
script targets Linux with `g++`; a Windows build has not been established. On
a Linux system with the matching development headers and runtime library:

```sh
bash native/llvm_mc/check.sh
```

`LLVM20_INCLUDE_DIR`, `LLVM20_C_INCLUDE_DIR`, and `LLVM20_LIBRARY` may specify
nonstandard header and library locations. Validation here used Ubuntu's
`llvm-20-dev` package version `1:20.1.2-0ubuntu1~24.04.3`, downloaded and
extracted into `/tmp` without installing it. Its package SHA-256 was
`e4b5cbfe19826dfb35ff3c2c33d4e3a9e8327de49ad5b7b4b780abb3f6d07b74`.
The installed matching runtime was `libLLVM.so.20.1`. To repeat that temporary
setup on the same distribution:

```sh
cd /tmp
apt download 'llvm-20-dev=1:20.1.2-0ubuntu1~24.04.3'
sha256sum llvm-20-dev_*.deb
mkdir -p /tmp/ariadne-llvm20
dpkg-deb -x llvm-20-dev_*.deb /tmp/ariadne-llvm20
cd /path/to/Ariadne
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
LLVM20_LIBRARY=/lib/x86_64-linux-gnu/libLLVM.so.20.1 \
  bash native/llvm_mc/check.sh
```

The check builds `target/ariadne-llvm-mc` and runs the ignored native integration
tests. Normal `cargo test --offline` remains independent of LLVM. The native
executable's line protocol accepts `decimal-VA hex-bytes` and emits
`decimal-VA status length kind target-or-dash`; `ByteSnapshot::to_request()`
checks its version and every response field before using it.

## Snapshot and graph contract

`ByteSnapshot` receives `captured` and `file_backed` maps of byte spans keyed
by semantic VA, plus an explicit `trusted_fallback` set. For dumps, captured
bytes win. An untrusted file span is unavailable, and a captured span that fails
decoding is never replaced with file bytes. Only the first 15 available bytes
at a start are passed to the x86-64 decoder. A failed decode with fewer than
15 bytes is reported as unavailable because the span may be truncated; a full
15-byte span that fails is reported as a decode failure. Missing starts remain
placeholders in the total request domain, so incoming edges and recovery
obligations survive.

LLVM MC supplies instruction length, branch classification, and direct target
when it can calculate one. The adapter adds the next VA for ordinary,
conditional, and call instructions. Indirect jumps and calls retain incomplete
target certificates, which produce Ariadne's existing obligations. Calls still
have a display-only call edge and a local summary edge. The core's `Visit`
algorithm remains the authority for discovery and graph policy.

Some decoded instructions have control effects that LLVM's generic flags do
not identify. The adapter treats system transitions, far transfers and
transactional control instructions as unsupported; it does not invent a
fallthrough. In the current `Ariadne.tla` vocabulary these are recorded as
`decode-failed`, which includes unsupported instruction decoding. This first
adapter does not certify instruction legality or exception delivery.

For the legacy `to_request()` interface, no precise effects are claimed. Every successfully decoded instruction is
summarized as possibly reading and writing **all caller-tracked locations**;
`must_defs` is empty. Thus a decoded write cannot incorrectly kill an earlier
origin, but slices may be much larger than necessary. Callers must choose a
complete tracked-location universe for the conclusions they intend to draw.
Reviewed AMD64 semantics and alias analysis are needed before promoting precise
effect summaries.

## First Rust use

```rust
use ariadne::llvm_mc::ByteSnapshot;
use ariadne::{InputKind, analyze};
use std::path::Path;

let snapshot = ByteSnapshot {
    snapshot_id: "binary-build-and-layout-id".into(),
    input_kind: InputKind::Binary,
    file_backed: [(0x1000, vec![0x75, 0x02]), (0x1002, vec![0xc3]),
                  (0x1004, vec![0xc3])].into(),
    entry_points: [0x1000].into(),
    ..ByteSnapshot::default()
};
let request = snapshot.to_request(Path::new("target/ariadne-llvm-mc"))?;
let result = analyze(request)?;
assert_eq!(result.state.edges.len(), 2);
# Ok::<(), Box<dyn std::error::Error>>(())
```

The native integration fixtures exercise direct and conditional flow, calls,
returns, indirect targets, truncated bytes, dump capture precedence, untrusted
fallback, and opaque system/transactional control. They check the real LLVM
decoder together with `AnalysisRequest` construction and the Rust analyzer.


## Reviewed effect preparation

`ByteSnapshot::prepare()` adds an opt-in path using structured LLVM operands
and reviewed normal-continuation effect rules. Set `snapshot.locations` from
`Catalogue.locations()`; a mismatch is rejected before decoding. The legacy
`to_request()` path retains its coarse summaries and protocol 1 behavior.

```rust
use ariadne::effects::{Catalogue, PreparationOptions, PreparedAnalysis};
use ariadne::llvm_mc::ByteSnapshot;
use ariadne::analyze;
use std::path::Path;

let snapshot = ByteSnapshot {
    snapshot_id: "snapshot-with-reviewed-effects".into(),
    file_backed: [(0x1000, vec![0x48, 0x89, 0xd8]), // mov rax, rbx
                  (0x1003, vec![0x48, 0x89, 0xc6]), // mov rsi, rax
                  (0x1006, vec![0xc3])].into(),
    entry_points: [0x1000].into(),
    slice_seeds: [0x1003].into(),
    locations: Catalogue.locations(),
    ..ByteSnapshot::default()
};
let PreparedAnalysis { request, instructions, gaps, identity } =
    snapshot.prepare(Path::new("target/ariadne-llvm-mc"),
                     &PreparationOptions::default())?;
let result = analyze(request)?;
assert_eq!(result.state.slice, [0x1000, 0x1003].into());
// Retain instructions, gaps and identity alongside result.
# Ok::<(), Box<dyn std::error::Error>>(())
```

The catalogue has 137 disjoint locations: 128 GPR bytes, CF/PF/AF/ZF/SF/OF/DF,
`memory:any`, and `state:other` for FP/vector/opmask application data/status.
RIP and system/debug/control state, including RF/TF/IF, are outside the tracked
vocabulary. Untracked state is not certified preserved. Effects concern normal
long64 user-mode continuation with ordinary RAM and CET disabled, without
exception-handler, asynchronous or concurrent-interference paths.

The [rule matrix](Ariadne/operand-effects-rules.md) lists 137 exact LLVM opcode
identities and additional shape/prefix restrictions. MOV, LEA, selected integer
operations and branches gain useful GPR/flag effects. Memory uses one coarse
alias cell; stores never kill all memory. Calls, RET and control-only CLC/STC
remain opaque. Undefined flags retain an explicit annotation and conservative
may-write. The new path uses a positive control registry: unknown control stops
local discovery instead of inventing a fallthrough. This can discover fewer
instructions than the legacy interface, with the reason retained as evidence.

`PreparedAnalysis` exposes source bytes, provenance, normalized operands, raw
LLVM observations, rule IDs, effect quality and preparation gaps. Core
`scope_closed()` does not include these precision gaps. A gap can also describe
an input candidate that the analyzer never visits; reports should distinguish
candidate evidence from visited instructions.

See [the protocol](Ariadne/operand-effects-protocol.md),
[design](Ariadne/operand-effects-design.md), and
[implementation plan](Ariadne/operand-effects-plan.md). Run all effects gates:

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  python3 tools/check_effects.py
```

This runs core checks, both real native interfaces, the projection model,
isolated effect mutations, core MBT and a small batch measurement. It requires
prepared LLVM, TLA+ and MBT tools; none is an ordinary Cargo dependency. Full
AMD64 instruction-step acceptance is unchanged by effect-rule delivery.


The reader integration uses `prepare_captured_batch()` as a public seam. It
returns only explicitly requested candidate results and a preparation identity;
referenced targets are not silently turned into roots. It shares the existing
normalization/effect implementation rather than duplicating ISA rules. Each
candidate carries decodability and complete-capture status as well as its
instruction, evidence and gaps. The batch's temporary root set is solely for
validating preparation's finite domain; the eventual analysis uses the caller's
original roots. Explicit `DecoderTarget` selection keeps Linux captures out of
the legacy Windows-only profile.
