# Rust machine-analysis implementation

The `ariadne-analysis` package exports the `ariadne` Rust library. It implements
[Ariadne.tla](../Specs/Ariadne.tla) over an owned immutable request using the
standard library. The separate LLVM IR and abstract machine-state models do
not yet have Rust implementations.

## Build and use

The crate uses Rust 2024 with a declared minimum Rust version of 1.85. Validation
for this implementation uses Rust/Cargo 1.96.0. There are no external crate
dependencies, and the included Cargo lockfile permits offline builds.

```sh
cargo test --offline
cargo fmt --all -- --check
cargo clippy --offline --all-targets -- -D warnings
cargo doc --offline --no-deps
```

The [crate documentation example](../src/lib.rs) constructs the sparse-address
pipeline fixture and is executed by `cargo test`. Public API entry points are:

- `AnalysisRequest::validate()` checks the input contract and reports an
  `InvalidRequest` with the failing field, optional instruction VA, and reason.
- `analyze(request)` validates and runs one request to completion, returning
  `Result<AnalysisResult, InvalidRequest>`.
- `Analyzer::new(request)` validates and owns the inputs; `request()` and
  `state()` expose shared references for observation.
- `Analyzer::step()` performs one enabled model action. It returns `false` only
  at `Done`, leaving the terminal state unchanged.
- `Analyzer::finish()` consumes the analyzer, runs remaining actions, and moves
  the completed state into an owned result.

`AnalysisResult.state` retains the full specification variable tuple, including
visited failures, provenance, graph edges, reaching definitions, and slice.
`local_graph()` and `call_graph()` are borrowed iterators over the one stored
edge set. `identity_of(va)` attaches the request's snapshot identity.

`scope_closed()` means completion without recovery obligations under the
supplied summaries and traversal policy. Inspect `missing_slice_seeds`
separately: an unreachable requested seed can be missing even when recovery is
closed. Entry definitions remain in the reaching sets but never become slice
producer nodes.

## Correspondence with the specification

| TLA+ component | Rust implementation |
| --- | --- |
| Fixed constants and `ASSUME` | `AnalysisRequest` and `validate()` |
| `Kinds`, `Sources`, `EdgeKinds`, `Reasons`, `Phases` | Rust enums |
| Finite sets and total address-keyed functions | `BTreeSet` and `BTreeMap` |
| `Init` | `Analyzer::new()` |
| `Source`, `InstructionEdges`, `Visit` | `source()`, `instruction_edges()`, `visit()` |
| `FinishRecovery` | Empty recovery worklist in `step()` |
| `EntryDefs`, `Gen`, `Out`, `Preds`, `Incoming` | `incoming()`, following only decoded local predecessors |
| `Propagate`, `DataflowFixed`, `FinishDataflow` | Dataflow branch of `step()` |
| `Dependencies`, `SlicePredecessors` | `slice_predecessors()` |
| `ExpandSlice`, `FinishSlice` | Slice branch of `step()` |
| `LocalGraph`, `CallGraph`, `ScopeClosed`, `MissingSliceSeeds` | Result iterators, predicate, and missing-seed set |

Ordered collections give deterministic output. Where the model permits any
eligible address, the implementation chooses the lowest VA. Each successful
`step()` corresponds to one model action; phase transitions are separate steps.
The two-instruction pipeline reaches `Done` in eight steps, matching its bounded
completion witness. Finiteness and strict growth bound the work, so choosing a
low address repeatedly cannot starve another address forever.

Input sets and map keys preserve semantic VAs without rebasing or arithmetic.
`Address = u64` is a deliberate representation restriction relative to the
model's unbounded nonnegative integers. Adapters must reject addresses outside
that range and distinguish VAs from file offsets. Snapshot and location IDs
are owned strings. Architectural location aliasing must already be normalized.

Validation checks every instruction summary, including placeholders for
unreadable or undecodable addresses. It enforces continuation and target
cardinalities, input domains, `uses`/`may_defs` membership, and
`must_defs` being a subset of `may_defs`. Rust enums and owned finite collections
enforce the remaining representation-level vocabulary and finiteness rules.
Empty location and slice-seed sets are valid, as in this model.

## Preserved behavior

Dump-captured bytes take precedence. File fallback requires membership in
`trusted_fallback`; an available untrusted file is insufficient. Decode failure
on selected captured bytes stays a failure. Recovery retains incoming edges to
failed targets, records obligations, and attempts each discovered local VA once.

Call and local edges share one set. Call edges are visible to consumers but do
not queue callees or transmit reaching definitions. A callee independently
supplied as a root retains its own entry definitions. The local summary edge
transmits the opaque call summary to a possible continuation.

Reaching definitions start empty and grow monotonically. Only `must_defs`
removes previous origins from a predecessor's output; every `may_defs` location
generates an instruction origin. Entry and instruction origins have distinct
tags even when their address and location match. Slicing begins only at the
fixed point and follows all uses of each included instruction.

The implementation uses straightforward ordered-set propagation and scans the
frozen edge set for predecessor queries. It provides an inspectable executable
baseline; large-binary performance has not been benchmarked.

## Validation and limits

On 2026-09-19, `cargo test --offline` passed all 19 integration tests and the
runnable documentation example. Formatting checks, Clippy with warnings denied,
and the offline documentation build also passed with Rust/Cargo 1.96.0. The
generated-request test includes the 256 cases described below.

[Conformance tests](../tests/conformance.rs) port the Binary, Dump, Loop, Closed,
Pipeline, and Calls scenarios, with explicit final graph, slice, provenance,
definition, and obligation expectations where relevant. Further cases cover
self-loops, typed parallel edges, incomplete empty targets, JIT capture,
captured decode failures, missing seeds, may/must writes, entry-origin exclusion,
zero and maximum `u64` addresses, ownership, and empty valid domains. A table of
27 malformed requests checks contract rejection, including invalid undecodable
placeholders.

The [shared test harness](../tests/common/mod.rs) checks initialization and every
transition for local-only discovery bookkeeping, valid origin identities,
monotone growth, frozen recovery products, phase boundaries, and the finite
progress bound. It also checks that terminal stepping has no effect.

[Generated tests](../tests/generated.rs) exercise 256 reproducible requests with
cycles, multiple roots, all instruction kinds, variable byte availability, and
two locations. An independently constructed graph drives expected recovery;
per-definition walks along paths without definite overwrites supply the expected
reaching sets. A separate dependency traversal supplies the expected slice.
These oracles do not use the implementation's node-wise fixed-point algorithm.

These are executable conformance checks, not a mechanically checked refinement
proof for all inputs. The unchanged TLA+ suite retains its own recorded model
checking evidence. The Rust tests do not verify decoder correctness, byte-provider
mapping, fallback certificates, memory-alias soundness, or machine semantics.
Results are relative to those supplied facts and preserve their explicit gaps.

## Model-based replay

The separate [MBT integration](../mbt/README.md) drives the real `Analyzer`
through a compiler-generated `mirrorrust-v1` binding, required MirrorRust
negotiation, and a live Mirrors checker. The application adapter implements the
generated typed port; the compiler owns input decoding, wire codecs, dispatch,
and binding lifecycle checks.
TLC supplies complete traces by invoking the original `Ariadne.tla` actions
under the implementation's deterministic scheduling policy. Apalache supplies
the raw declaration types. All nine state fields are compared; integer-address
maps have an explicit reversible wire projection, and fixture setup has a
separate public identifier.

The recorded run passed 12 complete trace occurrences and 168 state comparisons,
then rejected five actual engine mutants as model mismatches with the same
observer. Wrong-digest registration executed no adapter factories or SUT
callbacks. The MBT guide records the isolated Mirrors compatibility patch,
projection boundary, coverage requirements, source/tool identities, and exact
reproduction commands. Migration preserved the existing oracle, implementation,
coverage, and first mutant mismatch positions. Cleanup evidence now observes
the generated binding's actual port `Drop`. This is local conformance evidence; Gate isolation and
restricted authoring were not exercised.
