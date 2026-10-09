# BAP projection admission and coverage plan

## Context and follow-up

**Status.** P0–P4 plan written on 2026-10-09 against `e648055`. All implementation
and qualification stages are pending. This document changes no runtime policy.

**Why this document exists.** The current [BAP projection contract](../docs/Ariadne/bap-semantic-backend-design.md#projection)
rejects forms outside a finite opcode whitelist before interpreting their BIL.
An Electron Scanner/PreParser investigation encountered nonempty BAP lifts for
SUB64ri8, MOVZX32rm8, XOR64rr and CMP8mi, yet recovery stopped at each form.
The [assurance boundary](../docs/Ariadne/semantic-assurance.md) assigns projection
validation to Ariadne; installing another analysis solver does not close it.

**What this document establishes.** A staged extension: admit the four observed
forms with independent expectations, replace opcode-name admission with supported
BIL and operand/control contracts, and preserve normal continuation where only
data effects are unknown. Each change has its own source-bound acceptance gates.

**Where to go next.**

- [Backend design](../docs/Ariadne/bap-semantic-backend-design.md) — current
  protocol, projection invariants and the explicitly pending admission extension.
- [Pinned binding review](../docs/Ariadne/bap-projection-source-review.md) —
  getter/extraction mapping, register aliases and defined/undefined flag limits.
- [Input guide](../docs/Ariadne/modules/input.md) and
  [investigation contracts](../docs/Ariadne/investigation-contracts.md) —
  discovery roots, captured evidence, unknowns and explanation completeness.
- [BAP integration ledger](bap-integration.md) and
  [plan index](README.md) — distinguish this pending extension from delivered
  Stage 1/Stage 2 qualification.

**What remains unresolved.** No new forms, generic admission, diagnostic policy
or ordinary opaque continuation are implemented or qualified here. Broader BIL
coverage does not establish an executed path, a correct saved-slot lifetime,
all indirect targets, precise memory aliases or the cause of the bad RSI value.
Universal lifter/ISA correctness and analysis refinement remain separate limits.

For the wider context, see the [documentation map](../docs/documentation-map.md).

## Delivery intent and preserved boundaries

Release the restriction that an otherwise supported BIL program is rejected
solely because its opcode spelling is absent from a hand-maintained list. The
test corpus becomes regression evidence for the projection rules; it must not
remain an exhaustive list of permitted instruction names.

Admission must still establish matching captured bytes/length, compatible
decoded control, valid typed BIL, recognized architectural locations, supported
operations/widths, sound register-byte effects and applicable prefix/address
semantics. Unknown data remains conservative. Malformed input, decode/control
disagreement and unresolved control must not receive invented fallthrough.

Keep these contracts:

- BAP is the sole instruction-semantic producer; LLVM MC supplies independent
  decoded facts and operand/control binding, not semantic fallback.
- Only justified `must_defs` remove old origins. Conditional and uncertain
  writes retain alternatives; unknown flags do not become definite kills.
- Loads depend on address inputs and `memory:any`; stores never must-kill that
  global alias cell. Address dependencies exclude store payload dependencies.
- Calls/returns retain their existing opaque policy. No ABI-preservation
  assumption, interprocedural matching or recovered execution history is added.
- Snapshot identity, capture precedence, holes/conflicts, explicit discovery
  roots and seeds, resource limits and process shutdown remain enforced.
- Keep active analysis-model/replay checks. Do not revive retired ISA/Lean
  proof milestones or substitute old qualification records for the new sources.

Use the pinned downloaded BAP release runtime and existing bridge for the Rust
projection stages. Do not rebuild BAP or install a separate OCaml SDK merely to
exercise that path. Native-core parity is a separate tier requiring an available
current source-bound helper; missing prerequisites remain unexercised.

## Stages, ownership and acceptance

Proposed new outputs below are names, not links to files that already exist.
Implement stages sequentially; P1 is the bounded initial delivery, and P2 is the
actual removal of opcode-name restrictions. P3 changes recovery policy separately.

| Stage | Owned modules and outputs | Exit |
| --- | --- | --- |
| P0 — Contract and independent evidence | BAP design/source review, projection test manifest and admission/error decision tests | Exact initial forms, effect expectations, prefix/control decisions, profile/version policy and negative cases are frozen independently of SUT outputs. |
| P1 — Four observed forms | `src/bap/projection.rs`, `prepare.rs`, `tests/bap/fixtures/`, native/input tests and corpus tooling | Exact dump forms and boundary variants project with checked reads/writes/flags/address facts; old admitted cases and negative controls still pass. The next blocker is recorded rather than hidden. |
| P2 — BIL capability admission | Projection/AST preparation and a proposed private `src/bap/admission.rs`; binding, protocol and projection tests | Supported BIL/control/operand shapes are admitted without an opcode-name membership test. Unsupported constructs, prefixes, state and widths retain precise reasons; invalid inputs still fail. |
| P3 — Opaque ordinary continuation | `prepare.rs`, input materialization/evidence, report rendering and native capture admission | Validated ordinary instructions with unknown data effects retain a structural next edge, all-location possible effects and no definite kills. Unknown control and malformed inputs still stop/fail; diagnostics distinguish these outcomes. |
| P4 — Regression and capture qualification | BAP/input/investigation gates, measurements, source/tool inventories and new evidence/validation record | Separate source/fixture, Rust release-runtime, native parity and external-capture tiers report actual coverage and remaining gaps. Existing workload contracts pass on the changed sources; no root-cause claim is inferred. |

## P0 — Freeze admission decisions and independent expectations

Retain the current four-form failure baseline: bytes, semantic VA, BAP opcode,
nonempty raw BIL, LLVM reference facts, projection profile and the exact rejected
condition. The observed encodings are:

| Form | Observed bytes | Required initial case |
| --- | --- | --- |
| SUB64ri8 | `48 83 ec 58` | `sub rsp,0x58` at `0x7ff77443d96c` |
| MOVZX32rm8 | `0f b6 40 38`, `44 0f b6 70 38` | Byte memory load into EAX or R14D |
| XOR64rr | `48 31 e0` | `xor rax,rsp` at `0x7ff77443d97a` |
| CMP8mi | `80 78 38 76` | Byte memory comparison, including fault VA `0x7ff77443dd6e` |

Hand-review or generate expectations independently of Ariadne's evaluator and
BAP/LLVM agreement. Specify uses, may-defs, must-defs, preserved register bytes,
flag uncertainty, memory-access role/width/address and control successors.
Include negative encodings and unsupported constructs, not only positive cases.

Freeze a decision matrix separating precise projection, conservative partial
effects with established ordinary continuation, unavailable semantics/control,
malformed input and resource exhaustion. An empty lift is not a no-op; retain
the independently reviewed exact `90` NOP case. Empty/invalid BIL or unfamiliar
control must not silently acquire an ordinary continuation.

Audit existing ordinary-stop assumptions in `src/bap/prepare.rs`, input
materialization, native capture admission and evidence/report validators before
P3. Retain typed input invariants and the analysis model's local-edge policy.
If the decision or effect contract changes, update the active analysis-level
contract and its finite conformance checks before accepting runtime changes.

Assign a new projection profile (proposed `bap-bit-provenance-v3`) and bind it
into semantic/query identities. Preserve old evidence as historical artifacts.
Do not rewrite old reports to conceal intended coverage/profile changes. Freeze
an explicit schema migration if transport or report fields must change.

## P1 — Admit and validate the observed forms

### Effects to check

- **SUB64ri8:** sign-extension of the encoded immediate, positive/negative/zero
  operands, RSP and another GPR destination, result dependencies and CF/OF/AF/PF/
  SF/ZF. Verify immediate values at signed boundaries; decoded operand width
  must agree with the lift and the selected address/flag interpretation.
- **MOVZX32rm8:** eight-bit memory access, base/index/displacement dependencies,
  REX destination banks and 32-bit writes that replace/zero-extend the entire
  64-bit destination. A memory load retains `memory:any`; it does not become a
  concrete byte merely because the dump contains a convenient value.
- **XOR64rr:** distinct-register and self-XOR cases, preserved versus replaced
  cells, zero-result dependence, and defined/undefined flags. Generic BIL unknown
  flags remain uncertain; attach an ISA undefined-flag label only after reviewing
  that exact form. Do not turn an AF unknown into a definite origin kill.
- **CMP8mi:** the byte load and its address, flag-only architectural writes and
  no data-GPR replacement. Check zero/equality, borrow, signed-overflow and byte
  boundary cases with independently calculated expected flags/dependencies.

Extend the retained BIL corpus and the installed-provider probe together. Bind
each row to exact bytes, VA, provider/helper/runtime/AST/profile hashes and
independent expectations. Preserve C ABI EXTRACT bounds and alias regressions.
Derive exercised case/form counts from actual manifests instead of leaving the
hard-coded 41/30 qualification totals in `tools/check_bap_semantics.py`.

The initial four forms are not a claim that the whole parser is now recoverable.
Immediately following blockers can include long Jcc, other immediate arithmetic
or memory-compare forms. Discover and inventory those from the same query; do
not skip them by introducing undocumented block roots or removing gaps.

## P2 — Replace opcode-name admission with validated BIL capabilities

Separate three responsibilities:

1. **Input/control admission:** pinned identities, consumed bytes/length,
   structural control agreement, applicable prefix/address policy and supported
   architectural namespace.
2. **BIL capability validation and projection:** typed operations, widths,
   extraction/cast bounds, supported statement/control shapes, virtual-variable
   bindings, bounded alternatives and conservative effects.
3. **Reviewed instruction-specific obligations:** decoded source/destination
   footprints, implicit effects where needed, partial writes/zero extension,
   undefined-flag labels and exact no-effect special cases.

Use the semantic AST and these contracts to select a projection rule/profile.
Opcode names remain descriptive evidence and may identify a genuinely
instruction-specific obligation; they must not be a closed membership gate for
otherwise supported effects. Keep unsupported SIMD/x87/system/transactional
state, unbounded loops and unknown control explicit until their contracts exist.

Add generated BIL composition tests for loads/stores, casts, arithmetic,
comparisons and conditional writes across admitted widths. Add paired actual
encodings for equivalent semantic/control shapes, such as immediate arithmetic
and short/long conditional branches. Merely spoofing an opcode string is not an
acceptance test: bytes, consumed length, typed control and operand binding must
remain consistent.

Keep prefix checks as semantic obligations, not indiscriminate removal of the
existing guards. LOCK, REP, FS/GS and address-size override need explicit models
of their atomicity, repetition, state or address widths. A prefix becomes admitted
only when those obligations are met; otherwise preserve a precise gap.

Exit requires no generic opcode whitelist in production admission, independent
positive/negative capability tests and demonstrated detection of mutations that
drop a dependency, widen a definite kill, discard an unknown or ignore a prefix.

## P3 — Preserve proven ordinary continuation with unknown data effects

Stop labeling every effect-projection failure as an architectural control gap.
Only retain fallthrough when exact-byte/control validation establishes an
ordinary instruction and the unsupported construct cannot introduce unknown
control. Empty lifts, unmodeled control/state affecting control, decode mismatch,
malformed AST and invalid operand binding do not pass this predicate.

For an admitted ordinary continuation whose data effects are unknown:

- Keep captured/decoded evidence and the structural next edge.
- Set uses and may-defs conservatively to all tracked locations unless a narrower
  independently justified footprint exists; `must_defs` stays empty.
- Retain the unsupported-data/effect reason and partial precision in reports.
  A successfully visited successor does not make the whole explanation complete.
- Do not synthesize unknown branch targets, treat the instruction as a no-op,
  discard `memory:any`, or allow a later precise node to erase unresolved origins.

Audit the native capture validator and Rust report binding for this new outcome.
Prefer existing compatible gap/effect fields where sufficient. If a new typed
classification is required, update its schema/version and all admission,
serialization and recomputation tests together. Preserve ordinary versus
unsupported-control distinctions in text, JSON and DOT.

Test a supported producer, an opaque ordinary instruction and a later consumer:
the old origin and the opaque alternative must both survive. Mutations that
erase the gap, add a must-kill, assume no effect or invent a control edge must
fail. Exercise the same frozen request through Rust and an available native
helper; native unavailability cannot be reported as parity acceptance.

## P4 — Qualification and the Electron investigation

Use exact captured starts and preserve the distinction between discovery roots
and slice seeds. Start with the Scanner function root and fault seed, then the
PreParser caller root and RSI consumer. Publish reachable starts, rejected forms,
unknown calls, indirect-target obligations, memory uncertainty and missing seeds.

For original `dump_03958DA4FCA844A786262A1053` / `412f79ae`, keep the original hash
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`
and thread `0x5c74` bound to the external artifact. If using a scoped derivative
to satisfy reader limits, retain original/derivative hashes, copied context and
per-range byte equality; qualify that derivative's explicit scope. Raw customer
dump/source files remain external artifacts, not committed fixtures.

Capture acceptance must show that the four forms are no longer rejected merely
by name, that their supported successors retain legitimate dependencies, and
that newly discovered gaps are still reported. Reaching the consumer may remain
partial because of calls, unsupported constructs or unresolved jump tables.
Do not inject assumed execution paths or ABI preservation to report a producer.

Run the relevant finite corpus, hostile protocol/binding cases, real-code
mutations, input/investigation tests and root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_bap_semantics.py
python3 tools/check_doc_links.py
```

Run the applicable active analysis-model/replay checks and installed native
tests from the linked module/qualification guides. A command that skips missing
helpers, captures or runtimes is not a passing external/native tier. Use separate
target directories for replay and mutation builds.

Measure the changed capture queries and retain all preparation/analysis/render
phases, resource limits and emitted report sizes. Preserve existing fixed I4/I5
workload budgets and the separate unlimited BAP timing policy. Report Rust
release-runtime and native-default qualifications separately; a missing native
helper leaves that tier pending without forcing an SDK installation.

Record fresh source/tool/semantic-profile/corpus/capture identities, all observed
counts, failed controls and remaining gaps in a new durable evidence bundle.
Keep old 41-case and workload qualification records unchanged as historical
evidence. Update design, guides and ledgers only to the stage actually achieved.

## Completion checklist

- [ ] P0 admission, effect and diagnostic contract frozen with independent cases.
- [ ] P1 four observed forms and boundary/negative controls qualified.
- [ ] P2 opcode-name whitelist removed; capability/operand/control checks qualified.
- [ ] P3 conservative ordinary continuation and visible gaps qualified.
- [ ] P4 source/fixture and Rust release-runtime tiers qualified.
- [ ] P4 native parity/default tier qualified, or explicitly retained as pending.
- [ ] Electron captured-query results and subsequent coverage gaps preserved.
- [ ] New evidence identities, schema/profile changes and navigation verified.

No checked item in this plan implies that the historical bad RSI producer has
been identified. That conclusion requires its own captured causal evidence.
