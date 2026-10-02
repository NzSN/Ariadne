# Native LLVM IR input

## Context and follow-up

**Status.** Current directly supplied and verified LLVM IR path.

**Why this document exists.** [IR model](../../../Specs/README.md) defines block successors, SSA/phi dependencies and conservative memory edges.

**What this document establishes.** The path verifies supplied LLVM .ll/.bc, normalizes one function and analyzes explicit control flow, SSA/phi dependencies, conservative memory predecessors and separate call edges.

**Where to go next.**

- [IR result contract](../stage-e-report-contracts.md) — defines identity and uncertainty fields.
- [Delivery evidence](../stage-e-completion.md) — records verifier, replay and CLI acceptance.

**What remains unresolved.** It neither recovers original LLVM IR from a binary nor proves alias-analysis facts. Calls and unknown memory retain their declared obligations.

For the wider context, see the optional [documentation map](../../documentation-map.md).

`ariadne-ir` accepts directly supplied LLVM `.ll` or `.bc` bytes for one
function. It hashes an owned artifact snapshot, asks the pinned LLVM 20.1.2
helper to parse and verify those same bytes, validates the normalized block,
SSA, phi, memory and call tables, then returns an
[`ariadne::llvm_ir::Request`](../../../src/llvm_ir.rs). It does not lift binary code
or correlate LLVM values with machine virtual addresses.

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  bash native/llvm_ir/build.sh
ARIADNE_LLVM_IR="$PWD/target/ariadne-llvm-ir" \
  cargo test --offline --locked --manifest-path Cargo.toml --test ir_native -- --ignored
```

The adapter's `open_verified_ir(path, helper, function, seeds)` API accepts
instruction IDs such as `i11` from the helper's stable order within the
hashed artifact/function. It returns an error for a failed verifier, changed
helper version, malformed protocol or failed model contract. The current
native helper bounds a function to 4,096 instructions and the coarse memory
predecessor relation to 100,000 pairs. Each memory-reading instruction gets
all possibly writing instructions as potential predecessors plus an explicit
alias-uncertainty obligation. An indirect call retains an incomplete-target
obligation. See the [Stage E completion](../stage-e-completion.md).

The direct investigator CLI now emits independently versioned text/DOT/JSON:

```sh
cargo build --offline --locked --manifest-path Cargo.toml
target/debug/ariadne-ir tests/ir/fixtures/diamond.ll \
  --helper target/ariadne-llvm-ir --function diamond --seed i11 \
  --output-dir NEW_DIR
```

See [Stage E completion](../stage-e-completion.md) for identity,
uncertainty, native verification and transactional publication boundaries.
