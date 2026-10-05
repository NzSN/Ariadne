# I5a implementation plan: zero-address consistency

## Context and follow-up

**Status.** H0–H5 delivered at the source/fixture tier in the working tree on
2026-10-03, following the 2026-10-02 plan based on `c9eb4c5`. All 12 acceptance
gates passed with retained evidence. The later native refresh qualifies controlled
Windows I5a; active Windows I4 performance remains separate and open.

**Why this document exists.** The [I5a design](../docs/Ariadne/i5a-zero-address-design.md)
asks whether one selected memory access starts at zero under admitted captured
context. The existing producer explanation cannot answer that numeric question:
it does not bind the required exception parameters and register observations.

**What this document establishes.** A staged implementation, source ownership,
finite admission/fixture matrix, delivered product interface and independently
reported qualification tiers. Existing analysis algorithms and evidence remain
the starting point.

**Where to go next.**

- [I5a design](../docs/Ariadne/i5a-zero-address-design.md) defines the hypothesis,
  premises and meanings of consistent, refuted-under-premises and unknown.
- [I5a contracts](../docs/Ariadne/i5a-contracts.md) document the implemented
  binding, report schema, limits and CLI.
- [Delivery and validation](../docs/Ariadne/i5a-validation.md) records the
  exercised source/fixture scope and remaining capture requirements.
- [Controlled Windows demo](../docs/Ariadne/crashpad-demo-validation.md) supplies
  actual partial/full captures and records its historical CLI timing gap.
- [Native qualification refresh](i5a-native-qualification.md) records completed
  native measurements, controlled acceptance and the repaired dependency boundary.
- [Investigation stage plan](investigation-layer.md) retains the overall I0–I7
  status and the separate active Windows I4 performance obligation.
- [Implemented contracts](../docs/Ariadne/investigation-contracts.md) describe
  current identity, limits and first-question behavior to preserve.

**What remains unresolved.** The controlled Windows demo's historical CLI median
was approximately 1.82 s. The [current native result](../docs/Ariadne/i5a-native-qualification.md)
qualifies both budgets and capture modes under its pinned dependency snapshot. The [active Windows I4 re-pin](../docs/Ariadne/i4-windows-repin-validation.md)
passes correctness but exceeds its separate 2-second CLI budget. The original
Electron case is preserved as historical evidence. Broader hypotheses and
Linux numeric admission remain separate work.

The [documentation map](../docs/documentation-map.md) is optional navigation.

## Scope and preserved behavior

Deliver `windows-amd64-av-scalar-mov-v1` for the single question **does the selected
access begin at address zero under the admitted exception context?** Begin with
`MOV32mi`, then cover the six candidate forms in the design with an explicit
reviewed form/addressing matrix. Preserve the distinction between zero effective
address, a zero base register and a null-pointer root cause.

Use one immutable snapshot, the existing BAP preparation and completed analysis.
The original delivery used Rust; the native refresh consumes the completed BAP
result through `AnalysisView`. Questions add seeds, never roots. Fault-time values apply only at the
selected exception instruction; they must not prune earlier CFG edges, replace
reaching definitions or select an actually executed producer alternative.

Keep existing fixture bytes, default reports and the first explanation's v1
schema stable. Linux numeric hypotheses, UAF/lifetime, noncanonical-address
classification, branch/path reconstruction, BAP core migration and ISA proofs
are outside this delivery.

## Sequence and ownership

The sequence below records the implementation contract. Keep Rust sources under
`src/`, standalone tests/fixtures under `tests/`, and targets in the root manifest.
Replay and mutation builds require separate root `target/` subdirectories.

| Step | Responsibility and likely files | Completion criterion |
| --- | --- | --- |
| H0 — Freeze admission and oracles | New source-review record in `docs/Ariadne/`; new fixture specification under `tests/input/fixtures/`; existing BAP corpus as a reference | Every admitted form/prefix and context fact has a reviewed interpretation and independently specified positive/negative expectations. |
| H1 — Retain exception evidence | `src/input/{mod,minidump}.rs`; reader tests and new fixture generator | Immutable exception/context observations preserve source spans, validity and field meanings without changing current report semantics. |
| H2 — Bind and assess one form | `src/input/investigation.rs`; `src/investigation/{fault_context,zero_address}.rs`; module exports and tests | `MOV32mi` works end to end through the same interface used by callers, including unknown/error cases and bounded output. |
| H3 — Complete the admitted matrix | The same module and focused BAP/input/investigation tests | All six reviewed forms and addressing cases pass independent expectations; unsupported cases stay unknown. |
| H4 — Reports and CLI | `src/reports/zero_address.rs`; `src/bin/ariadne-minidump.rs`; root Cargo test targets | Separate strict assessment schema and explicit CLI modes preserve identity, conclusions and atomic publication. |
| H5 — Qualify and retain | `tools/check_i5a.py`, mutation/measurement helpers and retained `evidence/Ariadne/` artifacts | Passing source/fixture tier and separately reported real-capture and performance outcomes with stable identities. |

Run H0 before changing admission behavior. H1–H2 form the first vertical slice;
review its explicit unknown results before expanding H3. H4 and H5 use the same
bound assessment interface, without adding a generic hypothesis/provider framework.

## Execution record — 2026-10-03

| Step | Delivered evidence |
| --- | --- |
| H0 | [Source review](../docs/Ariadne/i5a-source-review.md), 41 deterministic independent fixtures and six reviewed MOV forms. |
| H1 | Reader-owned exception fields/context with raw spans, validity groups and immutable binding; legacy metadata/report bytes preserved. |
| H2 | Bound assessment API, strict recomputation, 32/32 default output limits and the first-form pilot. |
| H3 | Native finite corpus, additional unsupported-shape/malformed-input checks, 56 budget combinations and 16 detected implementation mutants. |
| H4 | Separate JSON/text/DOT schema, explicit CLI modes and atomic publication; 24 prior reports remain byte-identical. |
| H5 | All 12 acceptance gates pass, including the full investigation/Stage E/minidump regressions. Nine measured fixtures meet the frozen criteria; [source-bound evidence](../evidence/Ariadne/i5a-validation.json) and its [manifest](../evidence/Ariadne/i5a-evidence-manifest.json) are retained. |

The [delivery record](../docs/Ariadne/i5a-validation.md) gives the exercised
scope and measurements. The remaining sections preserve each step's acceptance
contract. Controlled Windows I5a was open at that delivery and is now qualified
by the [native successor](../docs/Ariadne/i5a-native-qualification.md).
Active Windows I4 remains over its fixed CLI budget.

## H0 — Freeze exact admission and independent fixtures

Use the platform references and source facts already linked by the design.
Record the pinned reader/provider versions, raw field interpretations, byte
layouts, context-validity groups and the meaning of each allowed premise.

The [existing BAP corpus](../tests/bap/fixtures/corpus.json) contains these useful
byte observations. They seed source review; they do not supply the independent
expected arithmetic or establish whole-opcode coverage.

| Form | Existing corpus example | Planned address coverage |
| --- | --- | --- |
| `MOV32mi` | `c70005000000` | First base-only store; zero/nonzero base, then reviewed displacement cases |
| `MOV64mi32` | `48c70408ffffffff` | Indexed store; distinguish address terms from sign-extended payload |
| `MOV32rm` | `8b03` | Base-only load with 32-bit access width |
| `MOV64rm` | `488b448b08`, `488b0508000000` | Indexed/displaced and RIP-relative loads |
| `MOV32mr` | `8985b8feffff` | Negative displacement; payload register excluded from address inputs |
| `MOV64mr` | `488903` | Base-only store with 64-bit access width |

For each admitted case, specify the selected VA, consumed bytes, operation kind,
access width, affine terms/constant, required register observations, evaluated
address and reported inaccessible-data byte. Independently calculate RIP-relative
and modular-wrap expectations; never call the assessment evaluator to generate
its own expected values. Compare native BAP extraction against these expectations.

Create separate fixtures and a deterministic `--check` generator under
`tests/input/fixtures/`. A suitable first pair uses the existing six-byte
`MOV32mi` encoding at an explicitly declared captured entry, with exception RIP
and exception location equal to that entry, valid required context groups, write
operation parameter and coherent inaccessible-data address. Use RAX=0 for the
consistent case and RAX=0x1000 for the refuted case. No historical predecessor
execution is inferred from these tool-produced fixtures.

Add controlled variants for missing INTEGER validity with raw zero bytes,
missing CONTROL/RIP, missing/short parameter arrays, conflicting metadata,
wrong operation, another thread-list context and changed query/snapshot. Preserve
the old Stage B fixtures as unknown-result regressions rather than editing them
to satisfy I5a.

**Exit:** reviewed fixtures and an admission table cover all design prerequisites.
If a candidate cannot be justified, keep it unsupported and report the planned
matrix incomplete; do not silently promote it or narrow the completion claim.

## H1 — Retain immutable exception-context evidence

Extend reader-owned metadata with the exception record's fields and parameters,
context descriptor/spans, flags, per-register validity source, raw-span digests
and artifact-relative offsets. Preserve `reported_address` as the existing
exception-location observation. Give the inaccessible-data parameter its own
explicit meaning; absent parameters remain absent, never zero-filled.

Construct the new evidence through the reader from its owned bytes. Carry an
owned immutable observation into `FilePreparedAnalysis`; downstream callers must
not certify an arbitrary public register map as fault context. Audit existing
struct-literal callers when evolving metadata types. Keep the ordinary minidump
JSON/text output stable unless a separately versioned opt-in field is required.

Respect validity groups per register, including CONTROL-owned RIP/RSP and the
INTEGER-owned GPRs. Use only the exception stream's associated context, not a
thread-list fallback. Distinguish malformed/out-of-bounds records (input errors)
from well-formed but absent/unsupported evidence (typed gaps).

**Exit:** parser and provenance tests recover independently specified raw fields;
invalid validity bits never create observations; existing captures, query
identities and default reports remain unchanged.

## H2 — Bind the first assessment

Implement the design's small interface:

```text
bind_fault_context(prepared, completed_analyzer) -> BoundFaultContext
assess_zero_address(bound, FaultAddressQuestion, AssessmentLimits)
  -> ZeroAddressAssessment
```

These interfaces are implemented. Keep acquisition
and normalization in the input adapter. The investigation module owns the pure
assessment and depends on root model types and normalized observations, not on
input, the BAP runtime or report renderers.

Binding must reuse the existing exact prepared/analyzer checks and add the
exception/context identity and admission-profile version. Reject cross-snapshot,
wrong-query and tampered observation bindings. Validate question site/access index
before applying budgets. A missing or unsupported context remains representable
so the assessment can explain why its conclusion is unknown.

For the first reviewed `MOV32mi` case:

1. Check platform, exception kind/parameters and context association.
2. Match valid RIP and exception location to the selected reached/decoded site.
3. Check consumed capture, admitted instruction form/prefix, single unconditional
   access, width/role and supported address expression.
4. Obtain only the required valid before-instruction GPR values. Unused registers
   need not be present. Evaluate the normalized expression modulo 2^64 without
   another RIP/length adjustment.
5. Require the design's nonwrapping low-range access span and coherent read/write
   and inaccessible-data observations. Contradictions give unknown, not refutation.
6. Emit consistent if the start is zero, refuted-under-premises if nonzero, or
   unknown if an admission/evidence/limit requirement is unmet. Retain the exact
   predicate and premises; none of these outcomes is a null-pointer root cause.

The frozen default assessment limits are 32 evidence records and 32 claims, plus
the existing maximum of 16 affine terms. Keep input byte/metadata limits in the
reader. Zero limits return unknown/truncated with valid references. Validate
these bounds against H0's record accounting before freezing the contract; if the
required evidence does not fit, revise the documented defaults before acceptance.
There is no dependency traversal or path search in the numeric assessment.

Record a small binding/assessment pilot on the first independently specified
fixtures. Use it to choose the additional I5a measurement criterion before H5;
the pilot itself is not a performance-acceptance result. H4 adds full CLI costs
to that frozen measurement contract before qualification starts.

**Exit:** the first form passes through reader, binding, domain assessment and
strict validation. Cases with a partial producer explanation can still produce
a bounded numeric conclusion when all fault-site premises hold; unrelated
upstream gaps must not silently become global eligibility requirements.

## H3 — Expand the reviewed matrix and challenge the result

Add the remaining reviewed forms and address cases through the same interface.
Test signed displacement, base/index/scale, modular cancellation to zero and
RIP-relative constants. Do not grow instruction-semantic coverage to avoid an
unknown result; reuse admitted BAP evidence and keep unsupported forms explicit.

Required negative controls include:

- Missing validity/parameters, wrong exception kind/platform, execute access,
  nested/chained records, RIP/location mismatch and incoherent data spans.
- Segment/address-size/LOCK/REP prefixes, stack/control/vector instructions,
  conditional/multiple accesses, unsupported expressions and excluded ranges.
- A zero base plus nonzero displacement, which refutes only zero-start; nonzero
  terms summing to zero, which do not prove a null base.
- Different thread-list values that would change the answer, and identical VAs
  from different snapshots or queries.
- Zero/one/exact-boundary resource limits and invalid questions under zero limits.

Use an independent integer oracle for the finite operand corpus and explicit
expected admission outcomes. Verify that assessment leaves requests, reaching
definitions, structural edges, slices and existing explanations unchanged.

**Exit:** every planned admitted form has native/input evidence and independent
domain expectations. All exclusions produce the intended gap/error, and no
unknown case becomes consistent/refuted through default values or missing checks.

## H4 — Strict reports and explicit product modes

Implement the separate `ariadne.zero-address-assessment/v1` envelope. Include
question/profile/context identity, used observations and source references,
expression and evaluated value when justified, conclusion, premises, gaps,
evidence requirements and truncation. Keep conclusion values separate from the
existing explanation v1 classification enum.

The validator checks identity/reference integrity and recomputes bounded numeric
facts from retained inputs. It rejects a definite conclusion with an unmet
admission premise or missing supporting records. Renderers remain pure and must
not turn conditional evidence into historical statements.

Implemented CLI modes:

```text
--assess-zero-address VA --memory-access N --assessment-only --format text|json|dot
--assess-zero-address VA --memory-access N --output-dir NEW_DIR
```

The usual dump, decoder and explicit-entry options still apply. The selected site
adds a seed, never an entry. Prepare/analyze once, bind before consuming the
analyzer and publish only after validation. Directory mode keeps the original
reports and adds `zero-address-assessment.{txt,json,dot}` in the same transaction.
Assessment-only mode emits the independent envelope; it does not silently add
fields to the existing minidump JSON contract.

For this first CLI delivery, reject simultaneous assessment/explanation question
flags, assessment plus stateflow, or incompatible output modes. Library callers
may request separate origin and numeric results for the same bound query. The
execution must preserve all existing CLI modes when the new flag is absent.

**Exit:** independent JSON parsing, strict round trips, Graphviz parsing and
cross-format semantic comparisons pass. Unknown/truncated results publish as
valid answers; invalid options, tampering and publication failures do not leave
a completed bundle. The prior default-output comparison remains byte-identical.

## H5 — Qualification, mutations and performance

Use the dedicated `tools/check_i5a.py` and retain a separate I5a record.
Bind its result to source, fixture manifest, oracle, helper/runtime, profile,
input and output identities. Invoke all new test targets explicitly; ordinary
Cargo tests may skip ignored native tests. Use a separate `target/i5a-mutations/`
build directory and leave existing replay/mutation outputs isolated.

Mechanically mutate the real implementations with unchanged observers. Detect
zero-filling invalid registers, substituting another context, confusing exception
location with data address, dropping index/displacement, adding RIP twice,
bypassing prefix/range/admission checks, cross-query binding, incorrect conclusion
classification, omitted premises and broken budget references. Compile failures
and timeouts are not sensitivity passes.

Measure binding, assessment and all-format rendering separately, plus the normal
CLI path with/without assessment: one warm-up and at least five measured repeats,
identity-bound outputs, median/spread and resource outcomes. Freeze an I5a latency
criterion after the H2 pilot and before the qualification campaign; report pilot
measurements as observations. Never weaken or substitute for the existing I4
250 ms incremental or 2,000 ms active real-Windows conditions.

Run focused reader/domain/report/CLI tests and the applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
python3 tools/check_investigation.py
```

Follow the affected BAP/input/Stage E module qualification procedures where
shared evidence or reporting changes. Retain previous evidence unchanged and
new derived artifacts under `evidence/Ariadne/`, with a readable delivery record
under `docs/Ariadne/`. Raw real captures stay external/hash-pinned.

## Completion tiers and remaining work

| Tier | Passing evidence | Limit of the claim |
| --- | --- | --- |
| Source/fixture I5a acceptance | H0–H5 source/fixture checks: native coverage, independent oracles, mutations, output equivalence, stable identities and the frozen fixture measurement criterion | Supports the finite admitted profile/corpus. It does not qualify a real Windows capture. |
| Controlled real-Windows I5a acceptance | A separately pinned real case with independently established site/context/access evidence, successful question/report checks and the frozen I5a measurement criterion | Qualifies that I5a case only; no historical-path/root-cause claim. |
| Active Windows I4 acceptance | The separately pinned 98-start capture, exact query and unchanged I4 gate/budgets | [Re-pinned correctness passes; CLI budget unmet](../docs/Ariadne/i4-windows-repin-validation.md). Neither I5a tier satisfies it. |

Report the tiers with separate named outcomes and missing clauses; a fixture pass
must not become a full I5a or I4 pass through one aggregate boolean. If a required
real artifact/tool is unavailable, complete and record the independent work, then
state the unexercised tier. Acceptance comes from records, not the plan alone;
the [current native result](../docs/Ariadne/i5a-native-qualification.md) separately
qualifies the source/fixture and both controlled Windows tiers.

The plan, design and stage ledger now record the exercised native and
controlled tiers. Broader I5 hypotheses, Linux numeric admission and I6/I7
remain later work. BAP-owned analysis has separate
[qualified native records](../docs/Ariadne/bap-core-qualification.md).
