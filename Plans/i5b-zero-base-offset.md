# I5b implementation plan: zero base plus nonzero displacement

## Context and follow-up

**Status.** Executing on 2026-10-07 after selection of this machine-code debugging
hypothesis. B0–B5 are implemented and qualified for the recorded finite source/
fixture and controlled partial/full Windows tiers. [Contracts](../docs/Ariadne/i5b-contracts.md)
describe the actual interface; [validation](../docs/Ariadne/i5b-validation.md) and
the [aggregate](../evidence/Ariadne/i5b-qualification.json) bind all 18 gates to
exact source/tool/dependency identity.

**Why this document exists.** The [I5b design](../docs/Ariadne/i5b-zero-base-offset-design.md)
defines a fault-time zero-base/nonzero-displacement question. Existing I5a
evidence binds valid context but lacks the encoded-role receipt needed for an
auditable base assertion.

**What this document establishes.** A sequential implementation with source
ownership, exact decision/admission criteria, independent oracle cases, CLI and
report compatibility, mutation controls and separate acceptance tiers.

**Where to go next.**

- [Source review](../docs/Ariadne/i5b-source-review.md),
  [implemented contracts](../docs/Ariadne/i5b-contracts.md) and
  [validation progress](../docs/Ariadne/i5b-validation.md) — actual B0–B4 outputs.
- [Selected design](../docs/Ariadne/i5b-zero-base-offset-design.md) — predicate,
  admission profile, implemented interface and explicit limits.
- [Investigation ledger](investigation-layer.md) — selected I5b versus other
  deferred hypotheses and the separately completed I4 performance qualification.
- [I5a contracts](../docs/Ariadne/i5a-contracts.md) and [execution plan](i5a-zero-address.md)
  — reusable context acquisition and the old behavior that must be preserved.
- [Native qualification](../docs/Ariadne/i5a-native-qualification.md) and
  [dependency snapshot runner](../tools/with_mirrorrust_snapshot.py) — reproducible
  native/reference qualification without a moving sibling dependency.
- [Formal-model guide](../Specs/README.md) — authoritative modeled contracts and
  the distinction between model checks, Rust/native replay and universal proof.

**What remains unresolved.** Later changes require fresh or exact-inventory-verified
qualification. The
profile excludes indexed and Linux assessments and historical provenance.
Source/fixture success cannot qualify real Windows evidence or close I4.

## Delivery definition

Implement `windows-amd64-av-scalar-mov-base-displacement-v1` for the predicate
`valid captured encoded base == 0 AND signed displacement != 0`. Admission
requires a simple GPR-base-plus-displacement memory access and coherent context,
decoded facts and BAP expression. Definite conclusions are conditional; missing,
unsupported or contradictory prerequisites yield unknown, never refutation.

Use one prepared snapshot and one completed analysis. Do not add roots, prune
earlier branches, change reaching definitions, select a historical producer or
rerun lifting inside investigation. Preserve current strict v1 schemas, default
reports, old fixtures, BAP-only semantics, native default and explicit Rust mode.

## Sequence, ownership and exits

The sequence below preserves ownership and exits; the execution ledger identifies
which outputs now exist.
Keep implementation under `src/`, tests and fixtures under `tests/`, and one root
manifest/lockfile/target directory. Keep replay and mutation build subdirectories
separate. Execute stages in order; a partial form matrix remains partial.

| Stage | Owned sources and outputs | Exit condition |
| --- | --- | --- |
| B0 — Freeze contract and oracle | New `docs/Ariadne/i5b-source-review.md`, `Specs/AriadneZeroBaseOffset.tla` and bounded config/check script; new fixture specification and performance contract | Exact six-form decoded-row review, base/disp predicate and independent expectations; finite decision model passes without reviving ISA-step obligations. |
| B1 — Retain decoded roles and bind | `src/llvm_mc/reference.rs`, new decoded-address module under `src/llvm_mc/`, `src/effects.rs`, `src/bap/prepare.rs`, `src/input/investigation.rs`; new bound types under `src/investigation/` | A question-specific sealed bundle binds the receipt to exact captured bytes/context/query; affine index-only lookalikes cannot become bases. |
| B2 — First vertical slice | New `src/investigation/zero_base_offset.rs`, exports in `src/investigation/mod.rs`, dedicated test target in root Cargo.toml and new fixtures | MOV32mi base/disp positive, refuted, unknown/error and budget cases pass through the same binding/assessment interface callers use. |
| B3 — Complete finite admission | Decoded-role projection, assessor, input/native tests and new fixture corpus | Reviewed base/disp variants of all six MOV forms pass; unsupported shapes remain unknown. |
| B4 — Strict result and product modes | New `src/reports/zero_base_offset.rs`, report exports, `src/bin/ariadne-minidump.rs`, report/CLI tests and new contracts document | Independent v1 schema, recomputation, all three formats and atomic bundle publication; old outputs remain equivalent. |
| B5 — Qualification and evidence | New fixture/check/mutation/measurement/equivalence tools, controlled-demo profile and source-bound evidence | Separate source/fixture, partial/full controlled-Windows and timing outcomes under stable source/tool/dependency identities. |

## Execution ledger — 2026-10-07

| Stage | Current result |
| --- | --- |
| B0 | Reviewed six decoded tuple layouts; 57 independent fixtures plus one auxiliary case; finite model passes; separate 64/64 defaults and frozen timing contract. |
| B1 | Retained receipt, whole-preparation decoder identity checks and sealed question-specific binding. |
| B2 | Pilot positive/refuted/unknown, strict binding and bounded-output tests pass. |
| B3 | Complete 57-case native/reference corpus passes for all six reviewed forms and admission negatives. |
| B4 | Actual schema and CLI/report modes; machine-code facts lead text; transactional/root-selection and opaque-call tests pass. |
| B5 | Qualified: all 18 gates, 15 detected mutants, 246 preserved I5a assessment outputs plus 24 old reports; nine fixture and six controlled timing cases pass. Archive verifies 2,005 entries; exact source/tool/dependency inventories remain stable. |

B0 completed before admission code changes. B1–B2 form the pilot; review its
unknown/error behavior before expanding B3. B4 builds on the same bound interface.
Full source/fixture acceptance requires all B0–B4 work and the B5 regression,
mutation, equivalence and fixture-measurement gates. Real Windows acceptance is
reported independently and requires actual retained captures.

## B0 — Admission review and independent oracle

Read the [input guide](../docs/Ariadne/modules/input.md),
[BAP guide](../docs/Ariadne/modules/bap.md),
[I5a source review](../docs/Ariadne/i5a-source-review.md) and
[LLVM reference projection](../src/llvm_mc/reference.rs). Review exact LLVM 20
raw operand rows for MOV32mi, MOV64mi32, MOV32rm, MOV64rm, MOV32mr and MOV64mr.
Record the memory tuple's position, no-register sentinel, base/index bank mapping,
displacement width/sign interpretation and access association. Do not infer row
positions from another opcode or opcode-name similarity.

Freeze an independently specified fixture table with exact bytes, VA, opcode,
base, index, signed displacement, affine expression, context-validity groups,
read/write width, B, EA, reported inaccessible byte and expected conclusion.
Expected decoded roles must come from reviewed encodings/source facts; expected
arithmetic uses independent integer/bitvector calculations rather than the SUT
evaluator. BAP/LLVM agreement alone is not an independent oracle.

The finite TLA+ decision model specifies admission-gated conclusions and output
availability, with invariants that definite output requires complete premises,
budget exhaustion implies unknown, and context disagreement is never refutation.
It consumes decoded/semantic facts as premises and does not model hardware
instruction execution. Its bounded check remains separate from Rust conformance.
If the model and the Rust decision contract diverge, resolve the design against
the authoritative modeled contract before accepting code.

The B0 accounting found 32 existing evidence records and 32 existing claims
before I5b adds a decoded receipt and derived role/base/displacement claims.
Freeze separate 64/64 defaults using `ZeroBaseOffsetLimits`; I5a's defaults remain
unchanged. Freeze new I5b budgets at 10 ms combined phase / 1,500 ms CLI,
one warm-up and at least five measured release repetitions per declared workload.
Existing I4/I5a limits and manifests remain untouched.

## B1 — Decoded-address receipt and exact binding

Add typed decoded-address reference projection during the existing decoder pass.
Keep BAP as the only effect producer. The receipt contains exact site/consumed
bytes/length/opcode, selected memory operand mapping, GPR base or its absence,
index/scale, signed displacement, widths and RIP-relative classification, plus
the raw record and decoder executable/version/protocol identity. Retain explicit
unsupported and disagreement diagnostics instead of guessing missing fields.
Hash the same executable used by preparation and reject a change during use.

The old display-operand projection currently covers only two immediate-store
forms. Prefer a dedicated decoded-role projection so extending fact retention
does not silently change old display operands or historical report bytes. Add
internal preparation evidence as needed; old strict SiteEvidence/AddressUse v1
records do not acquire new serialized fields.

The implemented `bind_zero_base_offset(prepared, completed, question)` adapter
must retain the following contract.
Reuse existing BoundFaultContext validation, then bind the new selected-site
receipt and explicit gaps. No extra decoder process is launched. Exact snapshot,
artifact, request/query, question, captured byte spans and receipt identities
must agree. Preserve absent supporting evidence as an assessable unknown; reject
substitution/tampering or malformed records. Legitimate decoded/BIL disagreement
is an explicit unknown and cannot admit LLVM effects.

Bind question/profile/context/receipt digests into the new scope. Public callers
receive a read-only owned value without an arbitrary-evidence constructor.
Preserve unsigned semantic VAs, signed displacement and dump offsets as distinct
roles. An invalid site/access index remains an error even with zero budgets.

## B2 — Pilot decision and bounded output

Deliver MOV32mi base-only/no-displacement and base-plus-disp8/disp32 cases first.
Use `assess_zero_base_offset(bound, ZeroBaseOffsetLimits)`.

Decision order:

1. Validate identities, required context fields, exception-site association,
   reached/captured bytes and supported scalar-MOV semantics.
2. Admit the decoded GPR-base/no-index shape and exact widths/prefixes; compare
   its base/disp tuple with BAP's selected affine expression and access.
3. Require the full valid base observation; evaluate EA modulo 2^64, then check
   the nonwrapping lower-range span and coherent data-byte/operation parameters.
4. Evaluate B = 0 and D != 0 only when every prerequisite passes. Retain unknown
   for missing, unsupported or conflicting prerequisites; invalid bindings fail.
5. Admit evidence and claims atomically under explicit limits. Missing mandatory
   evidence or a decision claim removes the definite conclusion and sets
   unknown/truncated with actionable requirements; retained references stay valid.

Share a private scalar-access admission helper with I5a only if required to avoid
duplicated checks and only after preserving I5a oracle outcomes and serialized
outputs. Do not derive I5b from I5a's conclusion: an I5a-refuted address may have
a zero base, and an I5a-consistent address may have a nonzero base. Keep this
numeric question independent from backward producer traversal.

## B3 — Mandatory admission and negative-control matrix

All rows below must have named independent tests. Each reviewed MOV form gets a
base/disp positive, nonzero-base refutation and zero-displacement refutation.
Do not count an unexercised form as covered.

| Cases | Required behavior |
| --- | --- |
| B = 0, D = +8, coherent reported byte | Consistent; record EA = 8. |
| B = 0, D = 0, coherent zero-start | Refuted for I5b; preserve I5a's distinct consistent result. |
| B = 0x1000, D = +8 | Refuted with EA = 0x1008. |
| B = 0xfffffffffffffff8, D = +8 | Refuted with EA = 0; never infer zero base from the resulting address. |
| Signed disp8/disp32; B nonzero and D negative with admitted EA | Refuted; preserve sign interpretation and arithmetic. |
| Zero base and negative displacement outside admitted range | Unknown, not a positive answer based solely on B and D. |
| SIB with a real base and no index; RSP/RBP/R12/R13 special encodings | Correct reviewed base role and required context validity. |
| Indexed, index-only, scaled-only, absolute and RIP-relative | Unknown, even if normalized terms resemble base + displacement. |
| Base/index same bank, canceled affine terms, or raw/BIL tuple disagreement | Unknown; no role reconstruction from merged terms. |
| Store payload zero/nonzero with unchanged address | Identical address assessment; exclude payload from H. |
| Reported data byte inside a multi-byte span but after EA | Admit when every other premise holds. |
| Missing validity group with raw zero bytes; missing context/parameters; other thread-list context | Unknown with precise requirements; no fallback or zero fill. |
| Wrong RIP/location, operation, data byte/span or unsupported platform/prefix/form | Unknown with explicit inconsistent/unsupported evidence. |
| Different snapshot/query/question/bytes/receipt, duplicate fields or bad IDs | Binding/schema error. |
| Zero/tiny/exact-fit limits, omitted receipt or decision claim | Valid unknown/truncated output; no dangling references or unsupported definite claims. |
| Opaque upstream call but valid selected fault-site evidence | Numeric conclusion can coexist with a partial producer explanation. |

Preserve existing fixtures; create a new generator and manifest in
`tests/input/fixtures/i5b/`. Native tests must exercise actual BAP/LLVM preparation
and both completed-analysis selections. Decode/lift failures and missing helpers
are unexercised prerequisites, not successful unknown-case coverage.

## B4 — Strict schema, CLI and compatibility

Implement `ariadne.zero-base-offset-assessment/v1` with the design's profile and
conclusions. Record source observations, decoded receipt, expression agreement,
base/value, signed displacement/bitvector, EA and explicit premises. Observed
claims concern captured bytes/fields; decoded roles, arithmetic and conclusions
are derived. Do not add fields to the existing explanation or I5a v1 schemas.

Strict decode recomputes scope/content IDs, raw decoded-row interpretation,
receipt/BIL agreement, context validity, arithmetic and predicate. Duplicate or
unknown fields, noncanonical values, altered receipts/claims, dangling references
and unjustified definite classifications fail. Internal record consistency is
distinct from proving that an externally supplied dump is authentic.

Add `--assess-zero-base-offset VA --memory-access N`. Retain the existing
assessment-only single-format convention and new-output-directory bundle flow.
Reject combinations with another numeric question, explanation or stateflow.
Question sites become seeds only. Produce
`zero-base-offset-assessment.txt/.json/.dot`; stage all files before publication.
DOT retains the same typed result and evidence/claim relationships.

Before changing shared code, freeze the exercised old fixture/default/I5a report
bytes and owned generated files. Compare outputs after B4, including native/Rust
selection. A compatibility pass requires the old schemas/decisions and ordinary
reports to retain their baseline meanings and bytes. Build identities that must
change after a rebuild require explicit receipt-only comparison rules; never
strip evidence or decision content to manufacture equivalence.

## B5 — Qualification and evidence

Add a dedicated `tools/check_i5b.py` plus independent mutation, measurement and
CLI-equivalence tools. These commands now exist; the runner must reject missing prerequisites and bind
all gates/results to exact source, helper/runtime, decoder, profile, fixture,
capture and dependency identities. Use the existing read-only MirrorRust snapshot
runner for native/reference campaigns and isolated target directories for mutants.

Required mutation controls include replacing encoded base with the first affine
term, admitting index-only addressing, ignoring displacement/sign, testing EA
instead of B, including store payloads, zero-filling invalid registers, selecting
thread-list context, suppressing data-span conflicts, allowing cross-query receipt
substitution and preserving definite answers after budget omission. Detected
compile errors/timeouts are not behavioral mutation sensitivity.

Run affected tests and all applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Also run the input/BAP/investigation/I5a/native-core/Stage E gates applicable to
changed sources, through the pinned dependency environment where required.
Explicitly exercise ignored native tests; ordinary Cargo success is insufficient.
Run the new bounded decision model and independent Rust oracle separately.
Keep all historical manifests/results unchanged. Refresh changed source/tool
inventories before citing retained acceptance for the new implementation.

For real Windows qualification, extend the controlled demo with an isolated
zero-base-plus-offset profile and deterministic intended witness. Native compiled
code must be independently inspected to show an actual simple GPR-base-plus-
nonzero-displacement access. C/C++ source or a requested compiler flag does not
guarantee that encoding; a compiler-materialized absolute address is not a
positive case. If needed, use an isolated reviewed assembly fault function after
recording its build identity. Retain partial and full capture modes, exact source/
binary/dump hashes and independently verified base/context/access facts. A
pre-crash witness alone is not proof of fault-time values or an earlier path.

The old zero-displacement demo is a refutation regression, not positive evidence.
Qualification also needs an independent refuted and an unknown capture/control;
do not mutate observed fields and label the result a fresh real capture. Preserve
the existing profiles and their pinned artifacts. Capture generation is a later
implementation task executed in B5: six isolated owned captures now exist;
their presence alone does not grant qualification.

Measure binding, assessment and all-format rendering separately from preparation,
core analysis and end-to-end release CLI. Use the frozen workloads/ceilings and
native-default mode, keep at least five raw samples after warm-up, report median
and spread, and verify semantic outcomes/native receipts for each sample. Windows
CLI and phase results cannot substitute for one another or for I4 performance.

| Acceptance field | Requirements |
| --- | --- |
| `sourceFixtureAcceptance` | Full finite form matrix, decision-model/Rust checks, strict-report/CLI/budget tests, required regressions, detected behavioral mutants, old-output compatibility and frozen fixture timings. |
| `controlledWindowsPartialAcceptance` | Independently inspected positive partial capture and declared controls, exact binding, correct reports, native-default receipts and both frozen timing conditions. |
| `controlledWindowsFullAcceptance` | The separately inspected full-mode corpus with the same identity, correctness and timing requirements; the mode label alone does not prove complete memory capture. |
| `fullI5bAcceptance` | Source/fixture and both declared controlled-Windows tiers pass with stable source/tool/dependency identities. This is corpus-scoped, not packaged-release or universal-proof acceptance. |

Missing, skipped, malformed, changed-identity or over-budget evidence keeps the
relevant field false. Retain raw reports/samples, fixture and capture manifests,
independent inspection, source/tool/dependency inventories and a verified evidence
archive. Update this plan's ledger and publish an I5b contract/validation guide
only when the corresponding work and evidence exist. Keep other I5 hypotheses,
I6/I7 and the open I4 clause explicitly separate.
