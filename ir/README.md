# Native LLVM IR input

`ariadne-ir` accepts directly supplied LLVM `.ll` or `.bc` bytes for one
function. It hashes an owned artifact snapshot, asks the pinned LLVM 20.1.2
helper to parse and verify those same bytes, validates the normalized block,
SSA, phi, memory and call tables, then returns an
[`ariadne::llvm_ir::Request`](../src/llvm_ir.rs). It does not lift binary code
or correlate LLVM values with machine virtual addresses.

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  bash native/llvm_ir/build.sh
ARIADNE_LLVM_IR="$PWD/target/ariadne-llvm-ir" \
  cargo test --offline --locked --manifest-path ir/Cargo.toml --test native -- --ignored
```

The adapter's `open_verified_ir(path, helper, function, seeds)` API accepts
instruction IDs such as `i11` from the helper's stable order within the
hashed artifact/function. It returns an error for a failed verifier, changed
helper version, malformed protocol or failed model contract. The current
native helper bounds a function to 4,096 instructions and the coarse memory
predecessor relation to 100,000 pairs. Each memory-reading instruction gets
all possibly writing instructions as potential predecessors plus an explicit
alias-uncertainty obligation. An indirect call retains an incomplete-target
obligation. See the [Stage E validation](../docs/Ariadne/stage-e-validation.md).
