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
before populating `ByteSnapshot`. The planned file readers and analyzer CLI are
separate roadmap work.

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

No precise effects are claimed. Every successfully decoded instruction is
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
