# Stage C minidump investigator report schema

Design fixed 2026-09-29 for implemented minidump report contract.
The [file-reader design](file-reader-design.md) supplies captured bytes and
provenance; `ariadne::render` supplies core analyzer facts. This report layer
joins them without changing the dependency-free analyzer crate.
The [Priority 1 real-capture implementation plan](../../Plans/completed/priority-1-real-capture-plan.md)
uses this unchanged schema to qualify a historical predecessor slice.
Its [evidence-chain design](priority-1-real-capture-design.md) keeps the
independent entry witness in a separate case manifest.
The [Priority 3 presentation implementation plan](../../Plans/completed/priority-3-investigator-presentation-plan.md)
adds a readable text overview under the unchanged JSON v1 and DOT graph
contracts; see its [design](priority-3-investigator-presentation-design.md).

## Command and publication

`ariadne-minidump DUMP --decoder PATH --entry VA [--entry VA ...]
[--seed VA ...] [--seed-exception-rip] [--max-starts N]
--format text|dot|json` writes one complete
format to stdout. `--output-dir DIR` writes `report.txt`, `report.dot`, and
`report.json` from one frozen query/result to a new directory. A malformed
query, reader/decoder failure, resource limit, or output error exits nonzero;
the directory is first written under a temporary sibling name and published
only after all three writes succeed. Existing output directories are rejected.
There is no implicit earlier entry derived from the exception RIP.

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
The [Priority 3 text overview](priority-3-presentation-validation.md) now
precedes the detailed per-site JSON evidence in text. It uses typed operands,
captured spans and possible input-origin site counts from that same frozen
query. JSON v1 field names and DOT graph structure are unchanged.
