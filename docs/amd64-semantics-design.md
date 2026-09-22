# AMD64 semantics and Lean correspondence

Status: staged delivery approved. The immediate target is the explicit
64-bit user-mode profile in [the subset plan](amd64-user64.md). Complete manual
coverage is a long-term roadmap target, not the first-release gate.
The [work list](amd64-semantics-tasks.md) distinguishes completed artifacts from
remaining semantic coverage. No inventory entry alone establishes ISA support.

## Accepted scope

The current implementation priority is `amd64-user64-v1`: long64, CPL 3,
validated decoded inputs, ordinary write-back RAM where accessed, and explicit
instruction-boundary outcomes. The first milestone is 49 register/immediate
form/profile cases; near control/stack and common RAM forms follow separately.
Unsupported forms and modes use a conservative analysis contract. A smaller
scope does not relax correctness, source review, fault/frame behavior or Lean
evidence within an advertised case. Source inventory remains comprehensive.
Profile lookup can identify a candidate case only; it does not select a runtime
semantic handler or discharge payload, state and profile preconditions.

The paragraphs below define the retained full-manual roadmap. They no longer
require unrelated legacy, device, optional-extension or system behavior to be
finished before accepting a scoped milestone.

TLA+ remains authoritative. Deliver a machine-checked Lean formalization,
correspondence obligations, and a typed-theory explanation in Markdown without
LaTeX. Keep the existing Rust analyzer independent of the new proof toolchain.

The instruction scope is every entry and form in Volume 3's **General-Purpose
Instruction Reference**, including all applicable operating modes, feature and
prefix conditions, implicit operands, exceptions, and partially completed
execution. It is not restricted to 64-bit execution or instructions supported
by the current development host. References and aliases remain visible in the
inventory instead of disappearing through mnemonic deduplication.

The state scope is every application-visible architectural state component in
Volume 1. This includes integer, segment, flag, instruction-pointer, memory,
floating-point, MMX, vector, and control/status state. Modeling a state bank does
not claim implementation of all instructions from Volumes 4 and 5. An in-scope
instruction that accesses that bank must receive complete rules for its effects.

Volume 2 dependencies needed by these instructions are in scope: protection,
segmentation, address translation, exception ordering/delivery, control
transfers, I/O permissions, and relevant configuration. Unrelated system
instructions are not silently added to the instruction target. Cross-volume
dependencies receive explicit entries; they cannot be satisfied by arbitrary
environment callbacks.

## Pinned authority and coverage evidence

The live AMD document API superseded the older URLs found by search. The
[source lock](../Specs/AMD64/manuals.lock.json) records exact downloaded PDF
hashes, byte lengths, revision dates, and public URLs. The baseline is Volume 1
3.25 (May 2026), Volume 2 3.45 (July 2026), and Volume 3 3.38 (July 2026).
PDFs and extracted prose stay in a local cache, not in git. Replacing a source
requires an explicit lock update and inventory diff; a failed download never
substitutes an unverified revision.

The coverage inventory has separate levels:

1. Reference entries and source sections recovered from the pinned PDFs.
2. Operand/encoding forms reconciled with each entry's tables and prose.
3. Semantic cases: mode, feature, prefix, exception, undefined-result and
   restart alternatives.
4. Implemented TLA+ rules and corresponding Lean definitions.
5. Checked evidence and closed proof obligations.

Source enumeration is not form review. A mnemonic with one implemented form
does not count as complete. A rule returning every possible state, an opaque
callback, a `sorry`, or a coverage flag without evidence cannot close an entry.
The source section inventory includes all Volume 1 sections so an omitted
state topic cannot be hidden by a hand-selected list; review classifies each
section and records its state/behavior obligations or why it is informational.

## State design

Separate these three concepts:

```text
ArchitectureProfile
  Supported capabilities, address widths, implementation-defined parameters.

ArchitecturalState
  Concrete values and architectural execution context.

AnalysisKnowledge
  What a binary/dump adapter knows about an ArchitecturalState.
```

Unknown captured bytes are an analysis fact, not a special architectural byte
and not zero. Undefined instruction results are constrained nondeterministic
choices; implementation-defined behavior is tied to a consistent profile.

| Component | Representation and constraints |
| --- | --- |
| GPRs | One canonical bank with overlapping low/high-byte, word, dword and qword views; mode and encoding determine which views exist |
| IP | Explicit architectural storage; width and control-transfer rules depend on mode; current instruction site is checked against it |
| RFLAGS | Documented bits, reserved-bit constraints, and instruction-specific read/write restrictions |
| Segments | Selectors and effective descriptor information, including FS/GS bases; selector storage is not the whole segment state |
| Memory | Bytes and memory attributes; distinguish effective offsets, linear addresses and physical addresses |
| x87 | Eight physical 80-bit registers, logical stack indexing via TOP, tags, status/control, pointer and opcode metadata |
| MMX | Views of shared x87 storage, never an independent writable duplicate |
| Vector state | Canonical overlapping XMM/YMM/ZMM storage and mask state as specified by the pinned profile; feature/mode availability is explicit |
| SIMD control | MXCSR and documented reserved, mask, status and rounding constraints |
| Execution context | Mode, privilege, enabled features, and relevant system configuration |
| External state | Constrained I/O/device and asynchronous-event interfaces, with observable events |
| Restart state | Architectural progress plus an internal continuation only where execution is interruptible or can partially complete |

This table is an organization of the target, not the final exhaustive field
catalogue. The state inventory drives field-level elaboration and validity
predicates. No unit type, empty record, or undifferentiated integer may stand in
for an unfinished component while claiming state completeness.

Register view primitives are defined before instruction semantics. For example,
a high-byte write changes bits 8 through 15 and preserves all other bits. In
64-bit mode a dword GPR write zeroes the upper half. The primitive's width and
offset validity does not establish encoding legality: REX/high-byte restrictions
belong to the instruction-form layer. Legacy upper-bit behavior must be defined
from the manual, not guessed from the 64-bit write rule.

## Semantic layers

```text
raw encoding / decoder evidence
  -> validated instruction form
  -> operand and address evaluation
  -> instruction relation and observable events
  -> architectural outcome
  -> analysis projection and finite bridge
```

The initial boundary continues to accept decoded instructions, but the normalized
form must retain every encoding fact that changes legality or behavior. Byte
decoding is a separately validated adapter contract. Invalid architectural
encodings produce the specified exception; missing implementation coverage is a
tool limitation. Neither may silently become a no-op or impossible execution.

Use a relational core rather than enumerating all outcomes of a full machine:

```text
InstructionStep(profile, environment, instruction, before, event, after)

ExecutionState :=
  Boundary(architecturalState)
  | InProgress(architecturalState, continuation)
```

Single-instruction outcomes distinguish retirement, faults/traps, partial
progress, and specified external interaction. Repeated string operations need
restart behavior and per-iteration progress. Instructions are not globally
assumed transactional: commit and fault ordering follow each instruction's
contract. Faults retain the information needed to distinguish faulting and
resume addresses, error codes and access details.

Memory and I/O are observable events with ordering constraints. A globally
sequential byte map alone is not the memory model. Locked operations and fences
need an execution-level relation and finite multiprocessor litmus scenarios.
Internal caches, pipelines and speculation are not simulated unless an
architecturally observable obligation requires their abstraction.

## TLA+ and Lean correspondence

TLA+ modules carry Snowcat annotations and rich comments. Their unbounded
architectural meaning is separate from the finite constants used by TLC and
Apalache fixtures. Width reduction is only used for explicitly stated helper
lemmas; architectural vectors still exercise full 8/16/32/64-bit behavior.

Lean uses structural and refinement types for validated values and relations
for nondeterministic behavior. Pin the toolchain and start with Lean's standard
library so the first proof build does not depend on a large external framework.

For each component provide:

```text
Representation:
  encode : TypedValue -> SourceRepresentation
  decode : WellFormedSourceRepresentation -> TypedValue

Round trips:
  decode(encode(value)) = value
  encode(decode(source)) = source       // on the specified source domain

Correspondence:
  TypedStep(before, event, after)
    iff SourceStep(encode(before), encode(event), encode(after))
```

The first source representation is a reviewed Lean transcription of individual
TLA+ operators, not a verified TLA+ parser or a formal semantics for all TLA+.
State this trusted boundary beside every correspondence theorem. Source hashes,
operator maps and cross-language fixtures detect drift; they do not prove that
the transcription equals the TLA+ text. General correspondence requires either
a checked translation for the used TLA+ fragment or a separately justified
embedding. Do not rename a proof between two Lean functions as a proof about
the entire source module.

Reject admitted proofs, new unproved axioms, and native-computation proof
shortcuts in the accepted proof surface. Audit theorem axiom dependencies;
ordinary Lean logical axioms such as propositional extensionality are reported
separately from project assumptions. Finite tests supplement proofs and are not
reported as proofs over every machine state.

## Ariadne integration

Keep architectural execution separate from CFG recovery and abstract-state
propagation. Existing recovery uses a frozen snapshot; the semantics must not
mutate it or pretend a newly computed destination already exists in its CFG.

The bridge revision must cover dynamic memory effects, calls/returns, indirect
destinations, exceptional outcomes and incomplete external information. Exact
state identities preserve correlations; duplicate matching IDs are retained.
Missing states, edges or environmental outcomes create explicit obligations and
cannot certify pruning.

```text
ISA coverage:
  An instruction form has complete architectural rules.

Analysis completeness:
  This analysis represents all relevant outcomes under its explicit assumptions.
```

For the old supported subset, project the expanded relation back to the current
GPR/six-flag interface under the old environment assumptions. Prove or check the
appropriate correspondence before replacing the old facade. Preserving AF
nondeterminism, 32-bit zero-extension and edge-label identity are mandatory
regressions.

## Delivery and validation

Follow the dependency-ordered [tasks](amd64-semantics-tasks.md). Introduce the
state primitives before instruction families, and exceptions alongside each
family rather than as a final success-path patch.

Validation combines source inventory audits, Apalache typing, TLC/SMT bounded
checks, Lean proofs, independent expected vectors, mutation tests, and later
differential execution on supported hardware/emulators. Hardware observations
are checked for membership in allowed outcomes when semantics is
nondeterministic; one observed AF or random value cannot restrict the model.

Completion requires reviewed coverage of every in-scope form and state field,
all dependency contracts, passing validation, and a documented proof boundary.
No current milestone claims complete AMD64 semantics. The Rust implementation
and the full Lean/TLA+ equivalence are separate deliverables from a source
inventory or a proved bit-vector helper.
