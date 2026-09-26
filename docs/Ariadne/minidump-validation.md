# Minidump input delivery and validation

2026-09-26, working-tree implementation based on `aee833f`. The current user
scope is **only minidump input**, including Windows and Linux/Crashpad AMD64.
PE/ELF images and ELF cores remain design work. No commit/push is included.

## Delivered interface

The separate [`ariadne-input` package](../../input/README.md) exposes
`FileSnapshot::open_minidump`, `from_minidump_bytes`, `metadata`, `read_prefix`
and `prepare`. Its `minidump=0.26.1` and `sha2=0.10.9` dependencies have their
own lockfile. The root core keeps its dependency-free manifest.

Snapshots own and hash their bytes. Supported memory, module, thread, exception
and system descriptors are preflighted for bounded structure/ranges. Capture
contributors are indexed independently of the parser's overlap lookup. Missing
and conflicting bytes stop reads; identical/adjacent fragments retain provenance.
Module paths and memory-info records never supply bytes or cause file opens.
Thread/exception integer observations honor actual AMD64 context group flags.

The materializer records original roots/seeds, explicit limits, attempted and
referenced addresses, byte/batch counts, overlap observations and query identity.
It follows local successors only. A call target or slice seed is not silently
promoted to a root. Resource exhaustion returns diagnostic progress without
publishing a partial request. Successful input construction leaves the existing
Analyzer responsible for all recover/dataflow/slice transitions.

A shared captured-batch preparation seam uses the existing semantic rules.
Target-profile negotiation selects Windows or Linux from minidump metadata and
records the target triple. The default legacy invocation remains Windows.
Both target profiles exercise the 137-entry frozen LLVM opcode registry.

## Acceptance evidence

The final source-bound report is [minidump-validation.json](minidump-validation.json).
It records all command results, log locations, input/source hashes and whether
sources stayed unchanged through the run. Its effects-regression gate also
executes the preexisting Rust, native, effect-model, effect-mutation and core
MBT checks. The broader AMD64/Lean proof suite is not part of this gate.

| Gate | Scope |
| --- | --- |
| Reader tests | Eight tests, including 512 bounded corruptions, sparse MemoryInfo, descriptor bounds, identical/conflicting overlap, memory64 payload sums and context flags |
| Input native tests | Six tests: both platforms, local discovery/slicing, calls versus roots/seeds, loops/overlapping starts, unavailable/unsupported control, budgets and frozen opcode coverage |
| Real artifacts | One test over two hash-pinned Breakpad-produced Windows/Linux dumps |
| Input formal model | Two Apalache typechecks; TLC normal-completion and budget-exhaustion fixtures, respectively 5 and 4 distinct states |
| Input negative controls | Six isolated mutations rejected by unchanged assertion-based observers |
| Format and Clippy | Root and input checks, warnings denied |
| Existing regressions | Existing effects suite plus 12 core MBT traces / 168 states and five rejected core mutants |

Input mutations cover wrong file offsets, memory64 descriptor-size stepping,
choosing a conflicting byte, zero-filled gaps, traversing call-only targets, and
publishing after budget exhaustion. Each mutation runs in a copied SUT after the
correct implementation passes the same observer. Compile/tool/protocol failures
do not count as successful semantic rejection.

The formal model checks byte-to-artifact mapping, agreement of contributors,
local discovery closure, call isolation and no publication on exhaustion in
finite fixtures. It is not a proof of the external parser, real capture
coherence or every Rust input.

## Real artifact observations

The artifacts were supplied from the existing Breakpad test-data checkout, not
copied into this repository. The real-artifact gate requires their exact hashes:

| Artifact | SHA-256 | Observed metadata |
| --- | --- | --- |
| `linux_null_dereference.dmp` | `1d82d1d98bb46fb9aa3498fce733e724e9b501824f8b8a36de22066d6d4bca33` | Linux, 8 modules, 1 thread, exception RIP `0x401f26` |
| `write_av_non_canonical.dmp` | `7012f0b943f5eacf681bcb29fc2766b75b87da1664280eaadc5dfa024f0a3abf` | Windows, 15 modules, 2 threads, exception RIP `0x7ff738721331` |

Both supply 15 captured bytes at the explicitly chosen exception RIP. Both stop
at the first instruction because those specific forms are outside the current
reviewed effect/control registry: zero decoded analyzer nodes, one obligation,
one missing slice seed. This is **successful input/provenance handling with an
explicit semantic gap**, not a successful crash explanation or new ISA coverage.
The synthetic native fixtures separately demonstrate successful CFGs and slices.

## Reproduction and limits

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
ARIADNE_REAL_DUMPS=/path/to/breakpad/src/processor/testdata \
  python3 tools/check_minidump.py
```

The gate does not install dependencies, download fixtures, regenerate the frozen
opcode oracle or refresh model acceptance. Missing external fixture input makes
that gate unavailable/failing rather than passing silently. The inspection
example documents ordinary API use; it is not a production analyzer CLI.

Validation runs on Linux/WSL with Rust 1.96.0, LLVM MC 20.1.2, Apalache 0.61.0
and TLC revision `1476e7f`. Cargo resolved the input lock against the declared
Rust 1.85 requirement; execution on Rust 1.85 itself and native Windows-host
builds were not exercised. The first dependency fetch timed out; a retry with
HTTP multiplexing disabled completed. Matching LLVM headers were downloaded
and extracted under `/tmp` without installing system packages.

Only the supported streams listed in the usage guide are interpreted. Larger
artifacts, unrecognized streams/register extensions, image fallback, precise
memory aliases, syscalls, signal handling and full ISA semantics retain their
explicit limits. No user64 instruction-step acceptance was promoted. Unrelated
working-tree Lean moves/deletions were left untouched and are not certified here.
