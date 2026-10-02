# Rendering analyzer outcomes

## Context and follow-up

**Status.** Pure core text/DOT rendering interface.

**Why this document exists.** [Analyzer result](../implementation.md) exposes graph, possible origins and obligations that need readable presentation.

**What this document establishes.** The pure renderer turns completed core outcomes into text and DOT while preserving graph edges, possible definitions, missing seeds and recovery obligations.

**Where to go next.**

- [Minidump report contract](stage-c-report-schema.md) — adds capture and preparation evidence to core rendering.
- [Instruction overview delivery](priority-3-presentation-validation.md) — addresses readability of per-instruction output.
- [Stateflow/IR reports](stage-e-report-contracts.md) — keep additional result families distinct.

**What remains unresolved.** Core rendering alone does not provide capture provenance or domain claims. The minidump report layer adds capture evidence; investigation and Stage E use their own result contracts.

For the wider context, see the optional [documentation map](../documentation-map.md).

Implemented 2026-09-27 on top of `712a635`. The module presents
`AnalysisResult`, the output of the Rust implementation of `Specs/Ariadne.tla`.
It does not modify the analyzer, request validation, ISA effects or input readers.
The [versioned minidump report layer](stage-c-report-schema.md)
joins this pure core rendering with captured-byte and preparation evidence.

## Interface and use

```rust
use ariadne::render::{render, Format};

let result = ariadne::analyze(request)?;
let report = render(&result, Format::Text);
let graph = render(&result, Format::Dot);
std::fs::write("analysis.txt", report)?;
std::fs::write("analysis.dot", graph)?;
```

`render(&AnalysisResult, Format) -> String` is pure: it performs no file I/O,
launches no process and changes no result fields. There are no new Cargo
dependencies. Callers choose storage, terminal output or Graphviz invocation.
The format is a presentation of the result, not a JSON serialization contract.

```sh
cargo run --offline --quiet --example render_outcome -- text
cargo run --offline --quiet --example render_outcome -- dot > analysis.dot
dot -Tsvg analysis.dot -o analysis.svg
```

A retained example shows a completed partial analysis: a definition in the
slice, an incomplete call, an unavailable continuation and an unvisited callee.
See [text](rendering-example/result.txt), [DOT](rendering-example/result.dot)
and [rendered SVG](rendering-example/result.svg). Regenerate these files using
`src/examples/render_outcome.rs`; the SVG is illustrative output from Graphviz
2.42.2, not a geometry or font-layout compatibility contract.

## Meaning of the views

| Core fact | Text | DOT / SVG |
| --- | --- | --- |
| Snapshot and phase | Report header | Graph caption |
| Pending, visited and decoded addresses | Explicit sets and node statuses | Pending/visited/unvisited/decoded node labels |
| Byte provenance | Per-node source | Per-node source |
| Every structural edge and its kind | Labeled edge list | Directed, labeled graph edges |
| Call-edge policy | Explicit excluded-from-local-analysis note | Dashed call edge and legend |
| Reaching definitions before each address | Complete location/site/origin listing | Node tooltips |
| Data slice | Explicit set and node annotation | Blue fill plus textual annotation |
| Recovery obligations | Per-node reasons and complete obligation list | Per-node reasons, orange outline and total count |
| Missing slice seeds | Explicit set and node annotation | Annotated placeholder nodes and total count |

DOT is a non-strict graph so two edge kinds between the same pair of addresses
remain distinct. Nodes include all addresses present in the result's domains
and references, including undecoded boundaries and unvisited callees. No edge,
origin or seed is silently dropped for presentation. Full-width hexadecimal
addresses avoid truncation and retain `u64::MAX` exactly. Node IDs are derived
only from numeric addresses, never arbitrary metadata strings.

An unvisited node's `ByteSource::Unavailable` value is a sentinel meaning that
no successful decode was recorded; it does not prove missing underlying bytes.
The presentation says **no successful decode** and separately shows whether the
node was visited. Actual unavailable/decode-failed obligations remain explicit.

`scope_closed` is labeled recovery-only and remains relative to supplied inputs.
A result can have closed recovery and still have missing slice seeds. The data
slice and structural graph do not establish executed paths or a crash cause.
Entry origins remain distinguishable from instruction origins at the same VA.

The renderer does not draw producer/use dependency edges from reaching sets.
`AnalysisResult` contains possible origins but not the instruction `uses` sets
needed to determine which origins a particular instruction consumes. The CFG
view plus explicit reaching information preserves that distinction. Annotated
assembly and input/preparation evidence require the separate upstream records.

All metadata strings are quoted/escaped. Embedded quotes, backslashes, newlines,
control characters and Graphviz escape sequences cannot introduce DOT records
or fake text-report lines. Graphviz HTML labels and URL/image attributes are
not generated from metadata. Output order follows the ordered result sets/maps.

## Minidump example

The optional input-package example accepts distinct entry and slice-seed VAs:

```sh
cargo run --offline --quiet --locked --manifest-path Cargo.toml \
  --example render_minidump -- crash.dmp target/ariadne-llvm-mc \
  ENTRY_VA_HEX SEED_VA_HEX dot > crash.dot 2> crash-evidence.txt
dot -Tsvg crash.dot -o crash.svg
```

Use `text` instead of `dot` for a readable report. Input and preparation gap
messages go to stderr, keeping stdout a valid standalone rendering. Retain both
outputs: the core result cannot represent all upstream evidence. No platform
assumption is introduced by rendering; the existing minidump reader continues
to choose Windows/Linux target profiles from the input metadata.

## Validation

Fresh checks for this delivery:

- Seven renderer tests cover deterministic/nonmutating output, phase/status,
  all recovery-gap reasons, captured/file provenance, missing seeds, call policy,
  parallel edge labels, possible-origin identities, escaping and 64-bit VAs.
- An additional real-Graphviz test parses hostile metadata and asserts exact
  node/edge counts, preventing escaping errors from creating extra graph objects.
- Root tests: 31 tests plus two doctests passed. Input tests: eight passed.
  Formatting and Clippy with warnings denied passed for both packages.
- The retained example's SVG parsed as XML with four nodes and three edges.
- The new minidump example was executed on the pinned Linux null-dereference
  fixture. Its SVG parsed with one undecoded node and zero edges; the existing
  unsupported-semantic gap was retained in stderr and the core obligation.

Graphviz was downloaded/extracted into `/tmp`; it is not a runtime dependency
of the Rust library. The optional parser test can be reproduced with:

```sh
ARIADNE_DOT=/path/to/dot cargo test --offline --test render -- --ignored
```

The analyzer and readers were unchanged, so the full native effects, TLA+/Lean,
mutation and MBT gates were not rerun for this presentation-only change. Their
previous records remain historical evidence, not fresh renderer checks.
