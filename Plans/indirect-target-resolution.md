# Captured indirect target resolver implementation plan

## Context and follow-up

**Status.** R0–R5 implemented for the finite pointer-slot/signed-32 table profile;
2026-10-13 review corrections are committed at `b5d56b7`. The
[original-dump retry](../evidence/Ariadne/indirect-target-resolution/dump-retry-b5d56b7-20261013/report.json)
passes pinned native resolver tests, full native/Rust state parity and the
single-sample CLI timing criterion. The [correction record](../evidence/Ariadne/indirect-target-resolution/review-corrections-20261013/report.json)
retains portable/root checks. Full mutation/replay qualification remains pending. The initial R6
correctness claim was too broad: its mutation campaign omitted required seams.
Earlier native CLI samples exceeded the unchanged 60 s criterion; the retry's
38.61 s native / 19.92 s Rust samples pass individually. The [initial qualification record](../evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json)
binds historical sources, fixtures, models, helpers and results. The original
2026-10-12 dump inspection remains motivation with its original identity.

**Why this document exists.** The [canonical design](../docs/Ariadne/indirect-target-resolution.md)
defines how captured pointer slots and bounded relative tables can supply
indirect CFG targets while preserving snapshot identity and unresolved cases.
Implementation needs a model, evidence validation and discovery integration
before augmented graphs can be accepted by either core backend.

**What this document establishes.** Stage ownership, dependencies, compatibility
constraints, acceptance gates and the evidence required for the initial profile.

**Where to go next.**

- [Semantic contract](../docs/Ariadne/indirect-target-resolution.md#semantic-contract)
  — target candidates, conditional completeness and captured-memory premises.
- [Formal-model guide](../Specs/README.md) — authoritative models and separate
  conformance/replay evidence; complete R0 before runtime edits.
- [Input preparation](../docs/Ariadne/file-reader-design.md#public-interface) and
  [BAP backend usage](../docs/Ariadne/bap-analysis-core-design.md#backend-usage)
  — existing capture, helper and native/Rust execution contracts.
- [Motivating capture](../docs/Ariadne/indirect-target-resolution.md#motivating-windows-capture)
  — exact original artifact, 58 entries, 45 destinations and retained limits.

**What remains unresolved.** Full R6 mutation/replay and release qualification
remain pending. The retry met the individual CLI timing criterion; earlier
over-budget samples remain historical. The expanded original-dump explanation remains
partial; 45 witnessed destinations are not exhaustive incoming-state coverage.
Real Linux full-dump and packaged release qualification are not credited.
General indirect calls, mutable dispatch data, broad value-set
analysis and execution-history reconstruction remain outside the first profile.

## Delivery scope and constraints

Deliver opt-in resolution for AMD64 near jumps through an established constant
pointer slot or a bounded signed-32 table-relative expression. BAP supplies
admitted semantics; LLVM MC independently checks decode/control facts. No
automatic LLVM effects fallback, live process reads or module-file byte filling.

All targets, receipts and source spans belong to one immutable snapshot. Use
machine-width arithmetic for target expressions and checked storage mapping for
reads. Maintain explicit holes/conflicts, unknown incoming states and unsupported
transfers. Caller-supplied entry points remain roots; slice seeds remain selectors.
Calls retain their existing summary/effect policy.

The first enabled profile explicitly declares `FrozenCapturedControlData`.
Completeness is relative to this premise and the covered incoming-state scope.
Readable or read-only metadata alone cannot establish historical stability.
Known targets with missing code remain edges and unavailable endpoints.

Keep disabled mode compatible with current preparation and reports. Version
enabled query/semantic/receipt/capture contracts. Core-only builds must continue
to activate no external crate dependencies. Heavy SDK, model, mutation and real
capture qualification use the established remote environment and separate
task-owned build directories.

## Stages and acceptance gates

| Stage | Owner and work | Required exit |
| --- | --- | --- |
| R0 — freeze contract and oracle | Canonical design, `Specs/AriadneTargetResolution.tla`, finite configurations/checker and independent fixtures under `tests/bap/fixtures/`. | Model bounded reads, index/value facts, unknown residuals, certificate invalidation and conditional completeness. Freeze supported BIL forms, default budgets, report/profile versions and timing criteria before runtime edits. |
| R1 — extract semantic evidence | `src/bap/target_resolution.rs`, existing BAP AST/admission/projection and address evidence. | Admitted width-correct pointer/table/guard expressions; definition and clobber witnesses; explicit unsupported outcomes. Production recognition must not scrape printed assembly or share oracle enumeration logic. |
| R2 — evaluate captured control data | Resolver and `src/input/address_space.rs`, through the existing reader API. | Exact little-endian pointer and signed-32 enumeration, deduplication, all contributor spans and conservative partial outcomes. Prove finite coverage conditions; retain known targets even when target code is absent. |
| R3 — integrate discovery | `src/input/materialize.rs` and prepared-analysis identity/evidence ownership. | New targets schedule local instruction reads; expanded incoming edges trigger fact/certificate revalidation. Bounded convergence or explicit partial stops, unchanged roots/seeds and frozen output only after final validation. |
| R4 — validate native admission | `src/bap/core_adapter.rs`, `core_protocol.rs`, native `capture.ml`, profile/handshake and product tests. | Strict identity/receipt/target coverage validation; forged, stale and cross-snapshot receipts rejected. Native and Rust consume the same augmented request. Preserve call-versus-summary policy and incomplete-target obligations. |
| R5 — expose the product | Input/investigation reports and `src/bin/ariadne-minidump.rs`, `--resolve-indirect-targets`. | Explicit memory premise, versioned enabled reports, all target evidence and residual gaps; disabled-mode regression. A resolved table alone must not change a still-partial explanation to explained. |
| R6 — qualify the extension | Root checks, finite oracle/model/replay tests, isolated real-code mutations and the external Windows capture. | Source/tool/artifact-bound acceptance for the declared finite profile, native/Rust parity, fixed R0 budgets and independently inspected real-capture targets. Record unexercised prerequisites and historical evidence separately. |

Proceed in stage order. R1/R2 may reuse existing reader and BIL structures, but
R3 cannot promote an incomplete prototype into the core's trusted target input.
R4/R5 must complete before calling the mode a supported product capability.

## R0 contract freeze

Review the existing [target certificate](../Specs/Ariadne.tla), not just the Rust
field layout. The resolver model separates discovered candidates,
remaining unknown alternatives and validated exhaustive coverage. Its required
property is containment of all admitted target values when `complete = true`,
not exact feasible-path reconstruction.

Freeze independent cases before implementation: a constant pointer, positive
and negative relative offsets, duplicates, default branch, nonzero lower index
bound, 32-bit index wrap, 64-bit target wrap, missing/partial/conflicting entries,
readable data with missing target code, a bypassed guard, a redefined base/index,
an opaque clobber and a newly discovered incoming edge invalidating coverage.
Include malformed and cross-snapshot receipt cases and every zero/exhausted
budget. Define separately bounded table entries, targets, read/evidence bytes,
value alternatives, transfers, revisits, graph growth and cooperative time.

TLA+ remains authoritative for the modeled contract. Parse/typecheck the new
model, explore finite safety and fair termination cases, and preserve existing
core/input/effects scenarios. Finite exploration, replay and mutations are
separate evidence; none is a universal ISA or Rust refinement proof.

## R1 and R2 semantic and read implementation

Expose only admitted transfer evidence needed by the selected forms. Retain
instruction VA/bytes, BIL/helper/projection identities, operand widths and
register-definition bindings. Conditional constraints belong to graph edges;
both structural edges remain. Treat unsupported outputs and opaque effects as
unknown, never as preserving a value without proof.

Evaluate through immutable captured reads. A table entry needs all four bytes;
a pointer slot needs all eight. Compose fragments according to the existing
reader contract. Preserve agreeing overlaps and reject arbitrary selection of
conflicting bytes. Sign extension, endianness and modulo arithmetic require
independent expected values. Unknown table contents retain an unresolved
alternative unless the enabled captured-memory premise is bound and visible.

## R3 discovery and coverage validation

Maintain separate instruction and resolution worklists. Add candidate indirect
edges and their endpoints to the finite request domain, then materialize newly
reachable local starts. Revisit value facts when predecessors change. A final
certificate must cover every admitted incoming route to its dispatch; a new
bypass, clobber or unmodeled route downgrades coverage.

Do not certify a guard solely on the initially recovered graph, or let a target
edge justify its own premise. Record unresolved frontier states and unsupported
incoming transfers. On resolver exhaustion, retain proven candidates and
unknown residuals under the selected partial-result contract. Existing ordinary
preparation bounds retain their existing failure behavior.

Freeze all instruction/target facts before native/Rust core initialization.
Reaching definitions and slicing run against the expanded frozen graph;
previous graphs/results and query identities remain historical artifacts.

## R4 and R5 evidence and product integration

The first expanded original-dump trial on 2026-10-12 exceeded the existing
256 MiB native completion representation; the Rust reference also exceeded the
60 s timing criterion. R4 therefore includes lossless definition/set interning
for the new capture profile and derived incoming/outgoing/delta/enabled caches
in both cores. Keep the old completion representation, 256 MiB encoded-result cap,
fixed input and observable scheduled actions unchanged. Validate dictionary
indices, uniqueness and a separate 16-million expanded-definition-link cap;
run core conformance/replay/mutations after the cache change. R6 must rerun the
same expanded query and retain these failed trials separately.

Native capture admission currently receives trusted normalized facts and bounded
instruction-prefix records. Table reads and completeness receipts need their
own versioned validation path, through the implemented separate receipt rather than those site records.
Bind covered graph/value revisions, premises, table read spans, arithmetic and
target sets; a matching hash alone is not a coverage proof.

Keep the enabled CLI opt-in through qualification. Display whether the target
set is complete within its declared scope or still has additional possibilities.
Propagate all remaining gaps into investigation status. Preserve disabled-mode
output and old strict schema decoding; enabled identities must include resolver
version, memory policy and limits. A production mode cannot depend on the
temporary diagnostic frontend used in the motivating dump inspection.

## R6 qualification procedure

Run affected portable tests and applicable root checks after behavior changes:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Follow the linked module/model guides for native helpers, ignored tests,
generated replay and mutations. The resolver tools are
[`target_resolution_oracle.py`](../tools/target_resolution_oracle.py),
[`check_target_resolution_mutations.py`](../tools/check_target_resolution_mutations.py)
and [`check_target_resolution.py`](../tools/check_target_resolution.py); the latter
verifies retained hashes and qualification clauses without rerunning campaigns. Keep model,
replay and mutation build outputs separate. Use a read-only dependency snapshot
when required by the existing BAP qualification workflow.

Mutate real production seams: wrong signedness/endian/base/scale, ignored guard,
lost incoming alternative, ignored clobber, stale completeness, dropped missing
entry, filtered unavailable target, skipped identity/premise validation and
seed-as-root discovery. Each selected mutant needs an independently expected
observable failure, not a test that mirrors the production helper.

For `dump_048B10C302A4460D8A1FC75088`, retain the original SHA-256, all table
contributors and the 58-entry/45-target oracle. Establish a supported large-input
execution path explicitly: the current CLI's 256 MiB cap rejects the 1.31 GB
artifact. The implemented `--max-artifact-bytes 2147483648` explicitly admits the original
without changing its bytes. Any reduced capture must retain original/derivative identities,
byte correspondence, query/entry premises and its narrower scope. Decide the
production size-limit/API path before claiming CLI support for this artifact.

The enabled query must expose the 45 witnessed indirect edges and preserve
additional unknowns unless final coverage is justified. Expect new discovered
instructions, edges and dependencies; do not require the old 329/388/15 counts
to remain unchanged. Compare native/Rust normalized requests and final results,
inspect new gaps, and retain the incoming-RDX boundary and unrelated unsupported
controls. The external inspection alone cannot supply Linux or general-table
coverage, executed-path evidence or root-cause attribution.

Write new qualification receipts under `evidence/Ariadne/indirect-target-resolution/`.
Retain exact sources, BAP/runtime/helper/decoder/native-build identities, platform,
input/query hashes, limits, mode/premises, phase timings and named corpus clauses.
Measure R0's fixed resource/performance criteria on both focused fixtures and
the expanded real query. Earlier backend timing does not qualify this extension.

## Completion checklist

- R0 contract, budgets, schemas, independent oracle and model gates frozen.
- R1/R2 admitted expressions and captured target enumeration pass positive and
  negative cases without losing unresolved alternatives.
- R3 discovery closes or stops conservatively; final coverage is revalidated.
- R4 native/Rust admission and results agree; hostile receipts are rejected.
- R5 enabled product is explicit and evidence-bound; disabled mode remains compatible.
- R6 model/replay/mutation/native/external-capture clauses are individually
  recorded, with no missing tier relabeled as passed.

The initial R0–R5 implementation now has the review follow-up below. R6 mutation
coverage and performance require separate acceptance; full plan acceptance is false. The
canonical design retains the [usage and limits](../docs/Ariadne/indirect-target-resolution.md#usage-and-public-api).

## 2026-10-13 execution ledger

This initial ledger describes the original source-bound run. The implementation
review below supersedes its unqualified R6 correctness conclusion.

| Stage | Result | Evidence and boundary |
| --- | --- | --- |
| R0 | Complete | Preserved initial/typed/completion freezes; Apalache typecheck and five TLC scenarios; independent integer oracle and original 58-entry/45-target bytes. Byte/BIL decoding remain producer premises. |
| R1–R2 | Complete | Admitted BIL extraction, bounded backward paths, unsigned guard domains, little-endian signed offsets/pointers, immutable reads and all contributors. Unknowns, holes and conflicts remain explicit. |
| R3 | Complete | New local targets schedule discovery without adding roots. Incoming-edge changes revalidate coverage; rounds/work/read/evidence limits retain conservative partial outcomes. |
| R4 | Complete | Rust source/read/proof replay plus native arithmetic/index/current incoming-coverage validation; direct hostile native receipts rejected. Compact completion and derived delta propagation preserve observations. |
| R5 | Complete | Opt-in CLI/API, explicit memory premise, versioned enabled base report, old disabled mode, declared large-artifact ceiling and unsupported composition errors. |
| R6 | Correctness passed; performance open | Root/default/core-only/Clippy/layout/docs; pinned synthetic Windows/Linux captures; original Windows full dump; 330 generated replay observations, 9 resolver and 12 core/stateflow mutants. Current local/native and Windows/WSL samples exceed 60 s; older 46.87 s / 27.74 s results remain historical. |

The [source-bound record](../evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json)
and raw evidence retain full native/Rust state parity and failed earlier trials.
The expanded query has 3,977 decoded starts, 4,819 edges, a 392-site slice and
10,744,212 reaching-definition links. Its 45 dispatch edges remain non-exhaustive;
`Partial` is the expected qualified answer. Full base report rendering in all
formats and a real Linux full dump are unexercised, not passing clauses. No
historical executed path, root cause, universal refinement or release claim follows.


Next performance work must repeat the exact current-source query under controlled
load and meet the original ceiling. Do not enlarge the ceiling, drop definitions,
filter targets or change the explanation to reduce the measured workload.

## Implementation review fixes

| Finding | Required change | Acceptance |
| --- | --- | --- |
| R3 loses retained witnesses on bounded revalidation | Merge still-valid prior evidence; stop additional admission atomically when the retained receipt would exceed a cap. | Destination-code expansion followed by exhaustion returns a valid partial result retaining earlier edges. |
| R4 checks only edge-union coverage | Check predecessor and root coverage for every reverse-path context in Rust and native admission. | Two successive branches require all four incoming combinations; deleting two receipts fails admission. |
| R4 accepts understated resource limits | Validate actual retained targets, reads, evidence and path/entry bounds. | Lowering each relevant limit below a valid receipt's usage fails admission; valid boundary and empty-stop cases pass. |
| R2 double-charges a shared destination | Count unique destination VAs across all dispatch sites. | Two sites sharing one target fit a one-target budget. |
| R5 builds JSON evidence twice | Reuse the constructed report value. | Existing enabled and disabled report regressions pass. |
| R6 omits required mutations | Add scale, guard, missing-entry, unavailable-target and identity/premise mutants and verify the required names. | Each isolated production mutant fails its independently expected semantic regression. |

Preparation modes use a named private type, and resolver convergence has a
private coordinator. These changes preserve the input module's ownership and
the disabled preparation contract. The canonical design records the
[review context and evidence boundary](../docs/Ariadne/indirect-target-resolution.md#implementation-review-follow-up).

Initial review-fix validation: 144 default tests, 46 core-only tests, format, all-feature/
all-target Clippy, Rust layout and documentation navigation pass. Four mutation
observer tests and every required mutation anchor pass. The revised campaign has
fourteen Rust mutants and one native mutant. At that checkpoint, its execution
and four pinned native target-resolution tests were pending after automatic
approval review rejected the private source archive transfer to `windows-dev`.
The [later retry](#original-dump-retry) resolved transfer and pinned-native
execution; the full mutation/replay aggregate remains pending.

### Second review corrections

| Finding | Correction | Acceptance |
| --- | --- | --- |
| Frontier admission counted fanout instead of the live stack | Replay ascending predecessor pushes and LIFO pops in both validators. | Complete successive-diamond receipts require capacity three; capacity two fails. Native ordering and internal-root cases pass source-level checks. |
| Prerequisite failures could count as mutation detection | Require a passing unmodified control before each mutation and the native arithmetic diagnostic. Bind and recheck control logs, source and executable identities in v2 evidence. | Missing controls, skipped tests, missing runtimes and unrelated failures cannot receive detection credit. A failed control aborts before source mutation. |
| Retention used every validation error as a capacity stop | Check union capacity explicitly, then propagate proof errors from fitting merges. | A corrupted merged AST fails preparation; valid budget stops retain prior witnesses. |

See the [canonical correction contracts](../docs/Ariadne/indirect-target-resolution.md#second-review-corrections)
and [source-bound correction record](../evidence/Ariadne/indirect-target-resolution/review-corrections-20261013/report.json).
At this correction checkpoint, pinned native and full mutation execution were
pending remote transfer authorization. The [later retry](#original-dump-retry)
resolved the pinned-native and individual timing-sample clauses. Full
mutation/replay and release qualification remain pending.

### Original-dump retry

The [b5d56b7 retry](../evidence/Ariadne/indirect-target-resolution/dump-retry-b5d56b7-20261013/report.json)
resolves the pinned-native and dump-rerun blockers above. Published sources
were verified, the pinned helper rebuilt, and all 26 resolver tests passed.
The original dump retains 45 witnessed targets and exact native/Rust full-state
and CLI-explanation parity. Individual native/Rust CLI samples pass the original
60 s ceiling; explanation output still reaches its 32,768-origin-link limit and
remains partial. The complete core state is compared without dropping definitions.

Remaining R6 work: the fifteen-mutant campaign with unmodified controls and
fresh aggregate replay/mutation receipts for the rebuilt helper. Historical
records retain their identities; full acceptance is false.
