# AMD64 delivery tasks

The user approved a scoped delivery strategy: [amd64-user64-v1](amd64-user64.md)
is immediate; full-manual coverage is a long-term roadmap. The active first
milestone is `register-core` (49 exact form/profile cases), followed by
`near-control-stack` (72) and `ram-data` (156). Source inventory and prior work
are preserved. The historical full-coverage tables below are roadmap records,
not prerequisites for the first scoped milestone.

Current scoped `general-purpose-gpt` responsibilities:

| Responsibility | Immediate work | Deferred expansion |
| --- | --- | --- |
| Profile gate review | Bind exact source forms and profile hashes; keep paired bodies distinct from verified cases | Later profile milestones |
| Default fallback foundation | Prove the no-trust unknown-instruction projection in TLA+ and Lean | Selective expert summaries and runtime integration |
| Shared integration | Review evidence, pin accepted fallback hashes, reconcile entry points/status and run scoped checks | Rust integration and full-manual closure |

The data, control, memory/atomic and external/I/O lanes are frozen roadmap work.
No existing artifacts or regression cases are discarded by the scope change.

The [accepted design](amd64-semantics-design.md) fixes proof boundaries.
Tasks are dependency ordered. `Complete` applies only to the named artifact,
never to its parent milestone unless all exit conditions have passed.

| ID | Task | Depends on | Exit condition | Status |
| --- | --- | --- | --- | --- |
| A1 | Pin public AMD Volumes 1–3 | — | Downloaded PDFs, revision checks, SHA-256 lock | Complete |
| A2 | Enumerate manual source entries | A1 | Reproducible instruction and source-section inventory | Complete |
| A3 | Review forms and architectural state fields | A2 | Every form, prefix/mode condition and state field reconciled with prose/tables | Partial artifacts; full review deferred |
| A4 | Record cross-volume dependencies | A3 | Required Volume 2 behavior attached to semantic cases | Partial artifacts; full review deferred |
| B1 | Register word/view foundation | A1 | TLA+ rules, Lean proofs and checked correspondence boundary | Complete for 64-bit-mode GPR storage |
| B2 | Complete typed state and validity contracts | A3, B1 | All state fields and alias invariants represented | Partial foundation; full closure deferred |
| B3 | Operand/encoding legality | A3, B1 | Widths, prefixes, feature and mode rules; illegal-form outcomes | Partial foundation; full closure deferred |
| B4 | Addressing, memory and exception foundation | A4, B2, B3 | Access, priority, commit and environment contracts checked | Partial foundation; full closure deferred |
| C1 | Data transfer and integer arithmetic | B2, B3, B4 | Every inventoried form, faults, flags, frames and Lean obligations | Pending |
| C2 | Shifts, bit operations, multiply/divide | C1 | Width/count boundaries, undefined outputs and exceptions checked | Pending |
| C3 | Stack and control transfer | B4, C1 | Near/far, direct/indirect, call/return and privilege dependencies | Pending |
| C4 | String and repeated operations | B4, C1, C3 | Interruptible iteration, partial completion and restart | Pending |
| D1 | Atomic operations and memory ordering | B4, C1 | Event semantics and bounded concurrent litmus checks | Pending |
| D2 | External, feature-specific and legacy forms | A4, B4, C1, D1 | Remaining general-purpose entries closed without opaque placeholders | Pending |
| E1 | Ariadne projection and bridge revision | C3, C4, D1, D2 | Sound effects, calls, dynamic targets and incomplete-analysis obligations | Pending |
| E2 | Old-subset correspondence | C1, C3, E1 | Regression against existing register-only outcomes and bridge fixtures | Pending |
| F1 | Full source/form/state coverage audit | A3–E2 | No pending in-scope rows or undocumented dependencies | Pending |
| F2 | Lean proof and correspondence audit | F1 | All intended theorems checked; translation trust boundary explicit | Pending |
| F3 | Independent/differential and mutation validation | F1, F2 | Profile-aware results and declared unavailable gates | Pending |

Implementation ownership is local to the new AMD64 specifications, Lean package,
source inventory tooling and documentation until E1 explicitly changes the
generic bridge. Existing Rust analysis and old instruction rules remain the
regression oracle. The continuation below dispatches the explicitly requested
`general-purpose-gpt` role. It does not authorize unrelated code changes.

## Delivered evidence, 2026-09-22

A1 and A2 deliver the pinned three-volume source lock, 154 instruction reference
entries, 931 table-row candidates, and 298 Volume 1 source sections. A fresh
extraction from the locked PDFs reproduces both generated JSON files exactly.
Form expansion and field-level state review are still A3, not implied by A2.

B1 delivers low/high-byte, low-word, low-dword and full-qword storage views in
64-bit mode. Nine primary Lean theorems cover view bounds, read-after-write,
frames, zero-extension, replacement, representation round trips and correspondence
with the reviewed one-based transcription. It does not validate instruction
encodings or implement legacy-mode storage rules.

The foundation gate, source-integrity regressions and four negative checks
passed. Exact commands, versions, limitations and artifact locations are in
[the validation record](amd64-validation.md). The full-coverage gate remains
intentionally failing. Next work is A3/A4, then the remaining B foundations;
none of C1–F3 is marked delivered.

## Full-coverage continuation: assigned workstreams

The tables below preserve the earlier full-coverage workstream decomposition.
They are deferred roadmap routing, not live worker status or an acceptance
decision. Immediate acceptance uses the profile-bound gate above.

| Task | Owner role / workstream | Scope | Dependencies | Acceptance |
| --- | --- | --- | --- | --- |
| S1 | general-purpose-gpt / architectural_state | Reconcile Volume 1 into field-level state obligations, guards, aliases and reserved bits | A1/A2 | State obligations source-linked; informational sections justified |
| S2 | same / architectural_state | Architectural state types and validity in TLA+/Lean | S1, B1 | Checked definitions and alias proofs; no opaque placeholders counted as coverage |
| I1 | general-purpose-gpt / instruction_forms | Reconcile 154 entries and 931 candidate rows, including aliases and merged cells | A1/A2 | Stable form IDs, operands, modes, features, prefixes and behavioral obligations |
| I2 | same / instruction_forms | Decoded-form validation and operand legality | I1, B1 | Architectural invalidity separated from missing implementation; checked rules |
| I3 | same / instruction_forms, dispatched follow-up | Executable operand identities/values/address expressions and shape-erasure coupling; bounded core form review | I2, S2/M2 interfaces | Actual payload AST, fixed-register identity checks and source-grounded reviewed constraints |
| I4 | same / instruction_forms, dispatched follow-up | Wider non-memory core forms and instruction-specific immediate extension coupling | I3 | Reviewed16/32/64-bit forms and negative encoded/semantic-width tests |
| M1 | general-purpose-gpt / memory_exceptions | Volume 2 dependencies and address/access/exception/commit contracts | S1/I1; independent source review first | Named dependencies; no unconstrained system callbacks |
| M2 | same / memory_exceptions | Memory, protection, faults and restart foundations | M1, S2/I2 | TLA+/Lean definitions, positive/negative cases and priority checks |
| M3 | same / memory_exceptions, dispatched follow-up | Explicit legacy/PAE/4-level/5-level page walks, combined permissions, reserved-bit faults and A/D effects | M2 | Reviewed page-walk certificates and variant-specific positive/negative TLA+/Lean evidence |
| M4 | same / memory_exceptions, dispatched follow-up | Total concrete byte storage separated from captured knowledge, refinement and page-table evidence binding | M2/M3 | Concrete read/write/frame proofs and snapshot refinement without zero-filling unknown bytes |
| X1 | general-purpose-gpt / instruction_execution | Data/integer, flags, shifts, rotates, bit and multiply/divide kernels | B1; integrate S2/I2/M2 afterward | Computations and nondeterminism checked; kernels distinct from full instructions |
| X2 | same / instruction_execution | Bind kernels to corresponding forms and architectural effects | X1, S2/I2/M2 | Every assigned semantic case has TLA+/Lean evidence |
| X2a | same / instruction_execution, dispatched follow-up | Actual CPU register/immediate execution using operand payloads, alias writes and complete rFLAGS framing | X1, S2, I3 | 8/16/32/64-bit and same-register cases, state preservation, old-subset projection and honest unavailable boundaries |
| X2b | same / instruction_execution, deferred follow-up | Bind all current reviewed forms and compose justified next-IP/instruction boundaries | X2a, I4, C3a coordination | Actual wide-form dispatch; body application remains distinct from retirement until all boundary conditions are modeled |
| C3 | follow-up general-purpose-gpt / instruction_forms | Stack, near/far transfers, calls/returns and privilege dependencies | S2/I2/M2 | Assigned forms and exceptional/restart behavior complete |
| C3a | same / instruction_forms, dispatched follow-up | Branch predicates/targets and stack-width foundations, followed by actual near control effects | I3/I4, S2/M2 | Source-backed target/stack rules; full calls/returns not implied by helpers |
| C4 | follow-up general-purpose-gpt / architectural_state | Strings, repeated operations and restart | S2/I2/M2/X1 | Count/direction, partial completion and interruption checked |
| C4-M | same / architectural_state, dispatched follow-up | MOVS/STOS/LODS/CMPS/SCAS CPU and memory iteration binding | C4 control, M2, X1 | Real byte movement, overlap, compare flags, restart and unavailable-memory checks |
| IO1 / C4-IO | same / architectural_state, deferred follow-up | Shared permission/device-event contracts and INS/OUTS binding, coordinated with IN/OUT execution owner | C4-M, M2/M4 | Explicit ports/widths/events and permission/fault ordering; no arbitrary CPU-state callback |
| D1 | follow-up general-purpose-gpt / memory_exceptions | Atomics, ordering and concurrent litmus cases | M2/X2 | Event-level semantics and bounded concurrent validation |
| D1a | same / memory_exceptions, deferred follow-up | Effective memory attributes and concrete atomic read-modify-write foundations | M3/M4, X1 | PAT/MTRR/profile constraints, explicit unresolved attributes, atomic effects and profile-specific ordering checks |
| D2 | follow-up general-purpose-gpt / instruction_execution | Remaining external, feature-specific and legacy general-purpose forms | I1/I2/M2/X2 | No omission due to host support or difficulty |
| E1/E2 | parent with bounded general-purpose-gpt follow-ups | Ariadne bridge, old-subset correspondence and dynamic targets | S2–D2 | Sound integration and regressions |
| F1/F2/F3 | parent and cross-review general-purpose-gpt follow-ups | Coverage closure, independent proof review, mutations and differential checks | E1/E2 | All gaps explicit; no complete label before closure |

Workers own new files for their workstream only. The parent owns `coverage.json`,
the main inventory checker, `lean/AMD64.lean`, `lean/Audit.lean`, shared check
entry points, correspondence locks and top-level status documents. Workers
report proposed shared interfaces early and do not edit another owner's files.
All preexisting uncommitted work is preserved. Dispatch evidence and acceptance
results are recorded as implementation progresses.

The machine-readable [work assignments](../Specs/AMD64/work-assignments.json)
cover all 154 source entries exactly once for execution: X2 has 82, C3 has 21,
C4 has 7, D1 has 17, and D2 has 27. All entries also retain the instruction-form
review owner. The inventory integrity check rejects dropped assignments,
changed source identities, and silent substitution of the requested agent role.

Parent integration has added `AMD64LegacyProjectionChecks.tla`: 1,296 boundary
combinations compare the new arithmetic/logical kernels with the original eight
register data operations at widths 32 and 64, including CMP/TEST frames and both
undefined-AF outcomes. TLC and Apalache typing passed. This is a bounded private
oracle regression, not acceptance of E2's full architectural-state correspondence.

## Continuation checkpoints

These are component handoffs, not full-coverage acceptance:

- `architectural_state` delivered 124 field rows and classification of all 298
  Volume 1 sections, CPU-local TLA+/Lean representation, alias/frame laws and
  reset/mode checks. Partial validity and delegated memory/I/O fields remain
  explicit. The same agent is now assigned C4 string/repetition foundations.
- `instruction_forms` reconciled all 931 table candidates and 154 reference
  entries. The shape validator distinguishes architectural rejection, malformed
  normalization/profile data, undefined encodings and insufficient review.
  Payload identity and shape-erasure coupling are I3; full semantic review of
  the form catalogue is still open.
- `memory_exceptions` delivered a constrained effective-page-map/access
  projection and exception/commit/restart contracts. It is extending these with
  M3 explicit page walks; page-walk, delivery, I/O and ordering dependencies are
  not certified by the projection.
- `instruction_execution` delivered arithmetic/logical/shift/bit/multiply/divide
  kernel modules and directed checks. Per-family proof and instruction-binding
  gaps are in `Specs/AMD64/integer-coverage.json`. Full decoded instruction
  execution is not implied by these value/flag kernels.

The parent is running `Specs/check-amd64.sh`, reviewing source-sensitive rules,
and returning correctness/typing failures to their owners before acceptance.
The evidence-backed coverage ledger remains authoritative for closure;
dispatch, a successful module check, and a reviewed table are distinct states.

The stable multi-agent checkpoint passed 33 TLA+ typechecks, 14 TLC fixtures,
the full-width register-view symbolic check, all discovered Lean modules and
the expanded axiom audit, 30 Python tests, and negative admission/semantic
checks. See [the recorded evidence](amd64-validation.md). It contains 33 reviewed
forms, 142 partial forms and 124 state-field obligations; it certifies zero
complete instruction reference entries. The remaining C3/D1/D2/E/F tasks are
still assigned work, not delivered semantics.

After the stable aggregate passed, a later wave produced additional C3a, X2b,
D1a and IO1/C4-IO work in progress. Those sessions ended and the broad wave is
now frozen. The validation record identifies the last aggregate checkpoint;
focused checks on later modules do not replace it.

## Deferred roadmap routing

The previous broad implementation sessions ended. Their logical routing remains
in `work-assignments.json` so no source entry loses an owner when full-manual
work resumes:

| Roadmap lane | Execution ownership | Deferred deliverable |
| --- | --- | --- |
| `control_stack` | C3, 21 entries | Stack operands, PUSH/POP and flags, ENTER/LEAVE; distinguish staged effects from architectural fault commits |
| `data_execution` | X2, 82 entries | CPU-bound arithmetic, shifts, multiply/divide and memory operands |
| `memory_atomic` | D1, 17 entries and memory dependencies | CPU-bound atomic operations, optional versus implicit locking, permissions and memory attributes |
| `external_io` | D2, 27 entries; C4, 7 entries | Direct IN/OUT, legacy decimal/external operations, string fault/restart composition |
| Integration | Form review, state composition and acceptance | Review supplements, validator parity, shared imports and aggregate checks |

`work-assignments.json` marks these paths as historical logical workstream
routing, not live agent sessions. The routing does not change instruction scope
or accept any entry. Missing semantic obligations remain open even when the
corresponding typed helper builds successfully.

### Pairing and state-review follow-up

The continuation audit distinguishes source review, a TLA projection, a Lean
CPU prototype, paired body execution, and full architectural acceptance.
`control-coverage.json` now records exact symbols and the authoritative TLA gap
for each of its 21 entries. No paired full control instruction body is claimed.
The larger Lean prototypes need matching TLA CPU/memory transitions before
instruction acceptance, followed by fetch, exception and restart composition.

The next control tranche must address those paired bodies and then the retained
far-transfer descriptor/gate/privilege/CET, INT/INTO, ENTER nesting, memory and
segment stack operands, and virtual-8086 CR4.VME paths. Assumed descriptor
projections are not descriptor validation.

The state review must read prose as well as bookmark titles. Volume 1 section
4.12.4 contained shared-memory ordering requirements despite its performance
heading; those requirements now route to the memory-attribute obligation.
CR0/CR4/XCR0 enablement composition and all other bookmark-only classifications
remain explicit review work. No section is accepted merely because its fields
are representable in Lean.

### Frozen implementation tranche: general-purpose-gpt only

The user restricted all delegated work to `general-purpose-gpt`. The completed
handoffs below are preserved as work in progress, while further broad expansion
is deferred behind the user64 milestone.

| Agent | Owned new modules | Dependency order |
| --- | --- | --- |
| `memory_atomic` | `MachineAccess`, `AtomicExecution` | Publish verified concrete access interface, then paired atomic CPU bodies |
| `control_stack` | `ControlExecution` | Pure stack/flag projections, then MachineAccess integration and full ENTER nesting |
| `data_execution` | `IntegerShiftExecution`, `IntegerMulDivExecution` | Verified register bodies first; concrete memory after MachineAccess |
| `external_io` | `SystemState`, `Monitor`, `LWPLayout` | Raw control/enablement binding first, then concrete monitor access and LWP byte layouts |

The listed handoffs have authoritative TLA+ and Lean artifacts plus focused
checks recorded by their original lanes. `SystemState` remains routed with the
external/I/O roadmap lane. Shared integration retains catalogue generation,
the acceptance ledger, root imports and aggregate checks. A body result does
not establish retirement; access resolution does not by itself choose an
instruction's fault commit policy. Source ambiguity and unpaired behavior
remain open until supported by evidence.
