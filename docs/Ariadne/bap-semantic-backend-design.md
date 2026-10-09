# Stage 1 BAP semantic backend protocol and projection

## Context and follow-up

**Status.** Current Stage 1 lifting/transport/projection contract. Native Stage 2
analysis is [qualified](bap-core-qualification.md) and selected by default;
Rust remains the reference and explicit rollback. BAP workload timing is
unlimited, with investigation budgets qualified separately.

**Why this document exists.** [BAP assessment](bap-core-refactor-assessment.md) motivates an isolated provider feeding the existing analyzer.

**What this document establishes.** The implemented boundary transports typed BIL from a pinned isolated helper, checks identity and decoded facts, then projects admitted operations into conservative byte/flag/memory effects.

**Where to go next.**

- [Projection admission and coverage plan](../../Plans/bap-projection-admission.md) —
  pending P0–P4 work to admit the observed parser forms, replace opcode-name
  restrictions and retain conservative ordinary continuation.


- [Complete Stage 2 qualification](bap-core-qualification.md) — records native default adoption, explicit Rust rollback, exact source/tool scope and the passing aggregate.

- [OCaml foundation qualification](bap-ocaml-qualification.md) — records the completed A0 SDK, native state and transport gates.

- [Stage 2 analysis contract](bap-analysis-core-design.md) and [A0 plan](../../Plans/bap-stage2-a0.md) — begin the user-authorized analysis-core migration.

- [Unlimited timing policy](bap-unlimited-validation.md) — records the user-authorized removal of the BAP latency ceiling and refreshed qualification.

- [Stage 1 Windows workload replacement plan](../../Plans/bap-windows-repin.md) — implements the authorized replacement of the unavailable capture with a controlled Crashpad case.

- [Pinned source review](bap-projection-source-review.md) — checks native binding details and projection assumptions.
- [Backend delivery](bap-only-removal-validation.md) — records removal of semantic fallback and remaining Windows limits.
- [Previous workload delivery](bap-windows-workload-validation.md) — retains the R0–R2 repair/refresh evidence and its original-capture limit.
- [Replacement validation](bap-windows-repin-validation.md) — records the inspected capture, durable bundle and former latency condition.
- [Integration plan](../../Plans/bap-integration.md) — tracks open workload qualification and later core migration.
- [Current execution ledger](../../Plans/bap-integration.md#current-execution-ledger) — retains completed R0–R2 evidence and tracks replacement qualification before the separate Stage 2 migration.

**What remains unresolved.** Native recovery, reaching definitions, slicing, finite stateflow and generated replay are implemented and [qualified on the exercised corpus](bap-core-qualification.md). The minidump CLI selects native BAP analysis by default with explicit Rust rollback. BAP lifting remains trusted; universal refinement and packaged cross-platform release qualification remain open. BAP timing is unlimited, while the [active Windows I4 pin](i4-windows-repin-validation.md) keeps its unmet 2,000 ms CLI ceiling and [controlled Windows I5a](i5a-native-qualification.md) passes its separate fixed budgets.

For the wider context, see the optional [documentation map](../documentation-map.md).

Implementation contract for [Stage 1 of the BAP plan](../../Plans/bap-integration.md#stage-1-bap-semantic-backend).
The [assessment](bap-core-refactor-assessment.md) remains the architecture basis.
Stage 2 analysis-core replacement is separate. The [semantic assurance
decision](semantic-assurance.md) retires independent ISA proofs; the linked Stage 1
plan retains its BAP projection and workload requirements. The
[Stage 1 LLVM semantic-backend removal plan](../../Plans/completed/bap-only-semantics.md)
records the user-authorized follow-up: BAP becomes the sole minidump semantic
producer, with LLVM MC retained only for decoded-fact validation.

The [previous workload repair](bap-windows-workload-validation.md), recorded on
2026-10-03 before the repin, fixed source-inventory bookkeeping for Windows-origin
dumps analyzed on Linux. Its retained workload v2/aggregate v3 delivery passed
17/17 implementation gates with 177 stable source hashes and 39 controlled tests;
full exit remained false because the original Windows capture was unavailable.

The [replacement follow-up](bap-windows-repin-validation.md) implements the user's
authorization to generate a new Crashpad capture and repin active BAP S4/S5.
`crashpad-windows-checksum-98-v1` is generated, independently inspected and bundled.
Workload v4 and aggregate v5 bind the active manifest, exactly 98 decoded starts,
captured preparation evidence and the independent RCX producer. The user has
removed the latency ceiling; all implementation gates, one warm-up and at least
five valid measured samples remain required. The [unlimited policy](bap-unlimited-validation.md)
supersedes the historical replacement record's 2,000 ms condition. Historical
Priority 4 and I4 were not repinned or requalified by this Stage 1 change.
The later [I4-specific replacement](i4-windows-repin-validation.md) separately
changes the active investigation pin and records its remaining fixed-budget gap.

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

**Planned successor, not current behavior.** The
[admission and coverage plan](../../Plans/bap-projection-admission.md) first
validates SUB64ri8, MOVZX32rm8, XOR64rr and CMP8mi. It then replaces opcode-name
membership with typed BIL capability, operand/control and effect checks. A
separate stage retains structural continuation for validated ordinary control
with unknown data effects, while preserving gaps and no definite kills. Empty
semantics, malformed inputs and unresolved control do not gain invented
fallthrough. All P0–P4 implementation and qualification remains pending.

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

The request validator freezes admitted summaries for the native-default
analysis helper and the independent Rust reference/rollback engine. Rust owns
capture preparation and transport/result validation; the native helper owns
production recovery, dataflow, slicing and supplied finite stateflow.
Report per-site semantic backend/build, AST identity, projection ruleset,
quality and disagreements separately from architectural ISA acceptance.
BAP is now the sole minidump provider by explicit user instruction. The
semantic selector is removed and `fallback` is always null. Fresh validation
qualifies each changed source tier. The active workload replacement has its own
capture and timing contract; default selection does not establish that result.
