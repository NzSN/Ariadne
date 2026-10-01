# Stage 1 BAP semantic backend protocol and projection

Implementation contract for [Stage 1 of the BAP plan](../../Plans/bap-integration.md#stage-1-bap-semantic-backend).
The [assessment](bap-core-refactor-assessment.md) remains the architecture basis.
Stage 2 analysis-core replacement is separate. The
[Stage 1 LLVM semantic-backend removal plan](../../Plans/bap-only-semantics.md)
records the user-authorized follow-up: BAP becomes the sole minidump semantic
producer, with LLVM MC retained only for decoded-fact validation.

## Selected native boundary

Host BAP's OCaml runtime in a separate C++ helper through the packaged typed
`bap-api` C interface. Rust never links OCaml or uses unsafe FFI. This changes
the helper's host language, not its semantic provider: all instruction lifts
come from BAP's x86 legacy lifter. The official v2.5.0 artifacts report
prerelease fingerprints; `native/bap/toolchain.lock.json` records actual
versions, source reference, plugin/library/header and archive hashes rather
than claiming clean stable-tag provenance.

Initialize only `llvm` and `x86` providers, with `--x86-lifter=legacy` passed
through the actual BAP configuration argv. This avoids unrelated symbolic
executor plugins. A fresh process owns one snapshot/target and one BAP
knowledge-base lifetime. Reuse it for bounded batches within that snapshot,
then terminate it; never reuse semantic caches across snapshots.

## Versioned stream

The native executable supports a version probe and a stream mode. Requests
are bounded ASCII lines: an initialization header with protocol version,
target (`windows-amd64` or `linux-amd64`) and SHA-256 snapshot token; then
`batch ID COUNT` followed by unique canonical full-width VA and captured hex
prefix rows (1–15 bytes). The helper sees no dump/executable paths and performs
one basic decode per requested site, without recursive discovery or synthetic
byte filling. A batch ends with a matching ID/count marker.

Responses are bounded JSON lines containing schema, batch/snapshot identity,
VA, status, length, exact consumed bytes, opcode and control-property facts,
and a recursively tagged BIL AST. Expressions preserve variable name, width,
virtual/architectural distinction, integer width/value, operation, child
expressions, load/store width and extraction/cast bounds. Statements preserve
move, branch, jump, exception, special and loop forms. Pretty BIL/assembly may
be diagnostic evidence; projection consumes only typed fields.

Rust validates identities, counts, duplicate/unknown fields, canonical addresses,
consumed bytes/length, AST depth/node/width limits, version and helper exit.
Timeout/transport/version failures invalidate the selected query before output.
Unavailable capture remains distinct from decoder/lifter failure. Retain
unsupported constructs and generic unknown values conservatively.

## Projection

Use a bounded abstract bit-provenance interpreter for supported BIL nodes.
Initial architectural bits refer to canonical GPR byte/flag cells; virtual
variables hold intermediate values and never become user locations. Constants,
extract/concat and casts preserve bit identity where justified. Supported
arithmetic produces new bits with conservatively collected input dependencies.
Track alternatives for conditional writes; combine possible effects while
requiring definite replacement on every alternative for `must_defs`.

Preserved original bits are not killed by whole-register IR assignment.
EAX zero-extension replaces upper RAX cells; partial AL/AH/AX writes preserve
untouched cells. Loads use `memory:any` plus address dependencies. Stores use
address/value dependencies, only may-define `memory:any`, and never must-kill
that alias cell. Unsupported operations, unknown outputs, unfamiliar state
and unresolved control retain gaps; calls retain opaque all-location effects.

The finite whitelist admits the 30 opcode forms exercised by the 41-case
corpus: scalar register/immediate moves, selected loads/stores/extensions,
LEA, ADD/ADC/CMP/INC, NOT, CMOV, PUSH/POP, short Jcc/JMP, register JMP
and selected shifts. LOCK, REP, segment and address-size overrides are
guarded. The plain `90` NOP is the separately reviewed empty-BIL no-effect
case. Other unsupported forms stop conservatively, without semantic fallback. This list is exercised projection
scope rather than architectural instruction-step acceptance.

LLVM MC remains the decoded control/operand reference. Admission requires
matching consumed bytes/length and compatible typed control facts. The
reference boundary constructs no reviewed uses/defs/rules and never calls the
legacy effect preparer. BAP alone supplies reads and replacements. Decoded
register operands bind MOV source/destination footprints, including AL/AH/AX
self-moves whose unchanged value still constitutes a definition. Control or
operand disagreement stops with opaque effects and no assumed fallthrough.
Generic unknowns keep conservative dependencies and cannot establish kills. Direct BIL jump
targets are checked against decoded successors where applicable. An empty
lift is not presumed a no-op; only a reviewed exact no-effect case can receive
that interpretation. Undefined architectural flags remain a separately reviewed
label rather than being inferred from a generic BIL unknown string.

The existing request validator and Rust engine consume admitted summaries.
Report per-site semantic backend/build, AST identity, projection ruleset,
quality and disagreements separately from architectural ISA acceptance.
BAP is now the sole minidump provider by explicit user instruction. The
semantic selector is removed and `fallback` is always null. Fresh validation
qualifies this changed source tier; the missing historical Windows workload
does not become a pass because the default changed.
