# Analysis result rendering and minidump reports

## Context and follow-up

**Status.** Implemented core text/DOT rendering, versioned minidump report
contract and readable instruction presentation. This is the single design for
these layers; dated validation below remains historical evidence.

**Why this document exists.** The [analyzer implementation](../implementation.md)
produces graph and possible-origin facts; the [file reader](file-reader-design.md)
adds captured bytes and preparation evidence. Investigators need both in one
readable publication without changing their meaning.

**What this document establishes.** Pure rendering, the minidump CLI and JSON v1
contract, atomic output publication, escaping, and the instruction overview all
preserve the frozen query, structural graph, uncertainty and possible origins.

**Where to go next.**

- [Completed presentation plan](../../.agents/plans/completed/priority-3-investigator-presentation-plan.md)
  — implementation and cross-format equivalence checks for the instruction overview.
- [Investigation contract](investigation-design.md) — separate typed fault-address claims.
- [Typed replay and result contracts](typed-replay-design.md#result-families)
  — separate abstract-state and supplied-IR identities and envelopes.
- [Report codec contract](typed-replay-design.md#report-codecs) — strict codec and rendering interfaces.

**What remains unresolved.** Publication can succeed while analysis gaps remain.
A readable instruction or closed recovery graph does not establish historical
execution or a crash cause. Stateflow, IR and investigation claims have their
own contracts; minidump JSON v1 alone does not imply them.

For the wider context, see the optional [documentation map](../documentation-map.md).

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Layer ownership

`ariadne::render` presents `AnalysisResult`, the Rust implementation's output
for `Specs/Ariadne.tla`. It does not modify analysis, request validation, ISA
effects or input reading. The minidump report layer joins that completed result
with captured-byte and preparation evidence. The input package owns the join
because the pure renderer has no decoded operands, rule IDs or captured spans.

The [completed real-capture plan](../../.agents/plans/completed/priority-1-real-capture-plan.md)
uses JSON v1 to qualify a historical predecessor slice; its
[evidence-chain design](file-reader-design.md#independent-entry-and-real-capture-evidence) retains independent
entry witnesses in a separate case manifest. The
[completed presentation plan](../../.agents/plans/completed/priority-3-investigator-presentation-plan.md)
adds the instruction overview while preserving JSON v1 and DOT graph semantics.

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

The optional input-package example accepts distinct entry and slice-seed VAs.
Preparation requires the [BAP helper/runtime setup](bap-analysis-core-design.md#backend-usage); the LLVM
helper supplies independent decode/control facts:

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

## Minidump command and publication

`ariadne-minidump DUMP --decoder PATH --entry VA [--entry VA ...]
[--seed VA ...] [--seed-exception-rip] [--max-starts N]
--format text|dot|json` writes one complete
format to stdout. `--output-dir DIR` writes `report.txt`, `report.dot`, and
`report.json` from one frozen query/result to a new directory. A malformed
query, reader/decoder failure, resource limit, or output error exits nonzero;
the directory is first written under a temporary sibling name and published
only after all three writes succeed. Existing output directories are rejected.
There is no implicit earlier entry derived from the exception RIP. The CLI
defaults to the native BAP analysis backend; `--analysis-backend rust` selects
the reference analyzer. See the [backend setup](bap-analysis-core-design.md#backend-usage) and
[investigator examples](#investigator-cli-examples) for helper configuration.

The opt-in [indirect-target extension](indirect-target-resolution.md#evidence-and-product-contract)
uses base JSON v2 with a separate resolver receipt; disabled mode retains the
v1 contract below. Its explanation schema remains unchanged and lists the
captured-control-data premise.

## JSON v1

The top-level `schema` value is `ariadne-minidump-report-v1`. All semantic
virtual addresses are canonical `0x` plus 16 lowercase hexadecimal digits,
including addresses nested in edges, origins, operands and stop reasons.
Artifact offsets, immediate bits and other potentially wide integers are
also strings; counts and bounded widths may be JSON numbers. Arrays are
ordered by VA or source order, making a repeated report byte stable for the
same input and toolchain.

| Object | Required facts |
| --- | --- |
| `identity` | snapshot ID, artifact SHA-256, query ID, input platform, input/core package versions, decoder target/build/protocol, effects ruleset and location catalogue |
| `query` | explicit entry and seed VA arrays; exception-derived seed is identified by the command invocation, not reinterpreted as an entry |
| `input` | artifact size, stream inventory, metadata gaps, attempted/reference/unvisited sets, resource limits, per-site captured prefix, read stop, source spans and conflict contributors |
| `preparation` | opcode, length, normalized operands, exact decoded bytes, byte source, rule, quality, undefined flags and typed preparation gaps for each candidate |
| `analysis` | phase, recovery-only `scope_closed`, visited/decoded/slice/missing seeds, structural edges, reaching definitions before each VA and recovery obligations |

Each `preparation.sites[]` has an `issues` array using the finite strings
`not_captured`, `conflicting_capture`, `decode_failed`,
`unsupported_semantics`, `architecturally_undefined`, and
`unvisited_reference`. More than one issue can apply. `issues` does not turn a
reviewed analyzer effect into a verified ISA instruction step. The full
`input.reads[]` record distinguishes a read that stopped after a complete
instruction from missing bytes needed for decoding. There is no global
`complete` field; `scope_closed` is only the core's recovery property.

Text and DOT retain the existing core renderer. The report layer adds the same
identity and per-site input/preparation evidence to text as a prologue and to
DOT as parseable comments, leaving DOT graph/node/edge semantics untouched.
JSON is the structured exchange format. All three are generated from one
in-memory `FilePreparedAnalysis` and `AnalysisResult`, never from one another.
The [instruction overview](#instruction-overview-contract) now
precedes the detailed per-site JSON evidence in text. It uses typed operands,
captured spans and possible input-origin site counts from that same frozen
query. JSON v1 field names and DOT graph structure are unchanged.

## Investigator question

An investigator needs to scan from a crash-IP seed toward possible producers
without mistaking a decoder observation for a verified instruction step. Put
the decoded VA, exact captured bytes, normalized operands, effect rule and
quality, capture offsets, slice membership and outstanding issues together in
the text report. Present the possible input-origin count beside each decoded
site, with an explicit pointer to the unabridged reaching-definition section.

## Instruction overview contract

The **Instruction overview** appears before the detailed per-site JSON evidence in
`report.txt`. Sort by VA. Each site has a stable two-line form:

```text
0x...  <bytes or ?>  <opcode or ?>  <normalized operands>
  rule=<id or none> quality=<reviewed|opaque|unavailable> source=<captured|...> span=<stream/entry/file offset or none> slice=<yes|no> possible-input-origins=instruction:<count>,entry:<count> issues=<list or none>
```

The operand text comes from structured `Operand` values, not decoder assembly
strings. Register views use canonical x86 names; memory views show access width,
base/index/scale/displacement and RIP-relative next IP when present. Missing or
unsupported operands stay explicit. Instruction and entry-origin counts include only reaching
definitions for locations in that instruction's `uses` set, deduplicated by
site and origin tag; they are **possible** origins, not a chosen execution.
The full core text still contains every reaching definition and structural
edge. Avoid a truncated producer list that could appear complete.

The input package owns this join because the pure core renderer does not have
decoded operands, rule IDs or captured spans. JSON v1 field names and types
remain unchanged. DOT graph nodes and edges retain their current semantics;
its evidence comments continue to mirror JSON. A later visual redesign would
need its own report-contract review.

## Failure and uncertainty

An unvisited reference, missing capture, decoding failure or unsupported
control must not be printed as an ordinary instruction. Mark unknown bytes,
rule and operands plainly, while retaining typed issues and read-stop evidence
in the detailed report. `scope_closed` remains recovery-only. A faulting store
still receives no commit claim, and opaque calls retain all-location possible
effects without ABI preservation assumptions.

## Examples and presentation acceptance

The commands below exercise the shared fixture and output contracts. They are
usage examples, not new qualification of a capture or a claim that a listed
producer executed. Source-bound presentation results follow the commands.

### Investigator CLI examples

These commands run from the Ariadne repository root. Build the pinned LLVM MC
helper as described in the [input build guide](file-reader-design.md#build-and-verification),
then set `ARIADNE_LLVM_MC` to its executable path. The CLI selects its Windows
or Linux decoder target from the dump, independent of the host platform.
Also build the BAP lifter and native analysis helper using the
[backend setup guide](bap-analysis-core-design.md#backend-usage). The CLI defaults to native BAP analysis;
add `--analysis-backend rust` to select the reference analyzer.
The [Priority 3 design](result-rendering.md#instruction-overview-contract) defines
the readable text overview; [JSON v1](result-rendering.md#json-v1) remains the
machine contract.

```sh
export ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
mkdir -p tmp/priority3
report_root=$(mktemp -d tmp/priority3/run-XXXXXX)

cargo run --offline --locked --manifest-path Cargo.toml \
  --bin ariadne-minidump -- tests/input/fixtures/stage_b_linux.dmp \
  --decoder "$ARIADNE_LLVM_MC" --entry 0x401000 \
  --seed-exception-rip --output-dir "$report_root/linux-report"

cargo run --offline --locked --manifest-path Cargo.toml \
  --bin ariadne-minidump -- tests/input/fixtures/stage_b_windows.dmp \
  --decoder "$ARIADNE_LLVM_MC" --entry 0x7ff700001000 \
  --seed-exception-rip --output-dir "$report_root/windows-report"
```

Each destination must be new. A successful command publishes `report.txt`,
`report.dot` and `report.json` together. In the retained presentation run, both
fixture overviews showed an earlier captured `MOV64rr RAX,RBX`, an unrelated `MOV64rr RCX,RDX` outside
the slice, and the faulting `MOV32mi` at the exception RIP. The rule and
capture file offset appeared beside each instruction. The historical trailing
`RET64` was opaque; a new backend run retains its own actual semantic quality.
The Windows example preserves its full high virtual address.

To inspect one format on stdout, replace `--output-dir DIR` with
`--format text`, `--format dot` or `--format json`. To validate published
machine and graph formats, use:

```sh
python3 -m json.tool "$report_root/linux-report/report.json" >/dev/null
dot -Tsvg "$report_root/linux-report/report.dot" \
  -o "$report_root/linux-report/report.svg"
```

Graphviz is needed only for the SVG conversion or DOT parsing check; the CLI
itself writes DOT without launching Graphviz. The text report keeps the full
reaching-definition and gap sections after its brief overview. The overview's
input-origin counts are possible producer sites under the current graph and
effect rules, not a concrete execution path.

For a partial report with an uncaptured entry, run the Linux fixture with
`--entry 0x402000 --seed-exception-rip --format text`. It shows unknown bytes,
`not_captured`, an unvisited seed and the recovery obligation; it does not
invent an earlier instruction. Invalid arguments, missing decoder, exhausted
limits and failed output publication instead exit nonzero.

The separate [controlled Chromium real-capture case](file-reader-design.md#historical-controlled-chromium-capture)
uses an external raw dump and matching build. Its
[checker](../../tools/check_priority1_real_capture.py) verifies the entry
witness before accepting a report; the committed Stage B fixtures above
only demonstrate the supported CLI and presentation mechanics.

### Presentation acceptance

The [2026-09-29 23:26 CST source-bound record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/priority-2-3-validation.json)
retains exact Windows/Linux example identities, format hashes, controlled-case
replay and the 11-gate minidump run under the
[completed presentation plan](../../.agents/plans/completed/priority-3-investigator-presentation-plan.md).

| Check | Retained outcome |
| --- | --- |
| Linux/Windows fixture CLI | New output directories; high Windows VA, faulting memory operand, captured file offset, relevant producer count, unrelated instruction outside the slice and opaque return all checked. |
| Partial/failure behavior | Uncaptured Linux root retained unknown bytes, `not_captured` and unvisited seed. Malformed input, missing decoder, exhausted limits and publication failures exited nonzero without a completed directory. |
| Cross-format publication | Graphviz parsed DOT; the controlled Chromium case changed its text hash as intended while JSON v1 and DOT stayed byte-identical to the accepted predecessor outputs. |
| Regression boundary | 11/11 minidump components passed with 57 stable source hashes; decoded sites, CFG, reaching origins, slice and obligations unchanged. |

This was a presentation-only acceptance tier for the recorded sources/backend.
It does not qualify the current checkout without matching evidence, and did
not change reader, effects, analyzer or formal instruction semantics. The raw
controlled-case dump remains an external artifact, not a bundled release
example. Current results must preserve their own explicit semantic gaps.

## Historical renderer validation

The 2026-09-27 renderer delivery on top of `712a635` recorded these checks:

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

The analyzer and readers were unchanged at that delivery, so the full native
effects, formal, mutation and MBT gates were not rerun for that presentation
change. All counts here describe that historical source, not fresh checks of
the current checkout. The independent ISA/Lean track was later
[retired](semantic-assurance.md); it is not a current renderer acceptance gate.
