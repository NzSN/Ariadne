# Section 5 frame-investigation implementation program

## Context and follow-up

**Status.** P0–P10 pass the declared finite frame-question profile with
[source-bound remote qualification dated 2026-10-19](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md).
The imported FC5/FC6 and selected memory M4/Scanner candidate-table gates pass
on the same exercised source and corpus. The [2026-10-18 local record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261018/README.md)
remains historical. No broad release or universal refinement acceptance is implied.

**Why this document exists.** The [recommendation](../chatdocs/ariadne-frame-to-frame-recommendation-20261016.html#order)
orders structural reporting, connection summaries, question-directed work and
local dependencies without requiring completed caller dataflow.

**What this document establishes.** The implementation and finite acceptance
ledger for items 5.1–5.4. The [canonical design](../../docs/Ariadne/frame-question-investigation-design.md)
owns interfaces, model scope, defaults and result meanings; imported owners
retain their separate contracts and evidence identities.

**Where to go next.** Read the canonical design, the [new qualification record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md),
[SF0–SF6](frame-structure-report.md), [FC0–FC6](frame-connections.md),
[memory M0–M4](memory-provenance-refinement.md), [Scanner follow-up](scanner-partial-explanation.md),
[implementation guide](../../docs/implementation.md) and [model guide](../../Specs/README.md).

**What remains unresolved.** Frame-path F4, broader release, general SMT, historical traces, root cause and universal refinement remain outside this program. The original saved-source question stays Unknown at resolver/prefix bounds. The early raw refresh with stale LLVM helper remains a historical partial source; [caller S6](caller-semantic-coverage.md) separately restores original coverage and completed-state parity using the current decoder.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## All four items: inventory and ownership

| Recommendation item | Existing delivery and evidence | Remaining action / owning ledger | Completion meaning |
| --- | --- | --- | --- |
| 5.1 structural report | `BoundFrameStructure`, source v1/v2, recovery-only CLI, finite Windows AMD64/E8 source qualification. | SF0–SF6 stay in [the original ledger](frame-structure-report.md). P0 inventories source hashes and old codec versions; P2/P6 reuse admission. | Existing scoped delivery; source changes need applicable requalification, not a relabeling of old results. |
| 5.2 connections/cycles/examples | `BoundFrameConnections`, `--frame-connections`, exact represented corridor/SCC layers and bounded routes; two capture applications and local tests/model/mutations. | FC5/FC6 pass the matching remote source/corpus tier. | Scoped consumer qualification; no feasibility/history or universal refinement claim. |
| 5.3 question-directed bottleneck | Owned one-question coordinator, bounded GPR constraints, fair resolver work and immutable source revisions. | P0–P4/P6–P10 pass the declared remote finite profile. | Checked per-question conclusions or explicit unknowns, fair bounded work and immutable source revisions; no full-caller prerequisite. |
| 5.4 local fault dependencies | Completed-callee reuse, captured point facts and candidate-preserving local writer assessment. | P2/P5/P7–P10 and selected M4 clauses pass; Scanner S2–S4 remain separate. | Compatible completed-callee reuse, local value facts and scoped writer assessments with unchanged alternatives; no executed-writer claim. |

The program owns integration, not the old SF/FC/M acceptance records. Import
only the specific contracts and evidence that match the selected source/tool
identity. New-model or new-source passes do not retroactively close S6 or F4.

## Execution order and file responsibility

The owner column names responsibilities, not a request to spawn agents. Work
must preserve edits made by others and keep shared exports coordinated.

| Stage | Responsibility and implemented source paths | Dependencies | Exit evidence | Status |
| --- | --- | --- | --- | --- |
| P0 — freeze questions and imports | Design/model owner: canonical design, this ledger, existing SF/FC/M source/report inventory and literal expected cases. | Current source review | Exact typed question kinds, point/context/premise scopes, source import/revision rules, finite defaults, statuses and corpus identities frozen. | Passed; declared question/import profile frozen |
| P1 — authoritative models and independent oracles | Model owner: `Specs/AriadneFrameQuestion.tla`, `Specs/AriadneQuestionSchedule.tla`, configurations/checkers and `tests/investigation/fixtures/`. | P0 | Finite safety/fair-termination checks and independently generated expectations; all abstractions and unmodeled concrete checks stated. | Passed remote finite models and independent oracles |
| P2 — bound question and evidence adapter | Investigation/input owner: `src/investigation/frame_question.rs`, `src/input/frame_question.rs`, shared source/fault/transfer validation and exports. | P1 contract | Immutable privately constructed input/result; both structural source carriers and sealed live/embedded evidence providers work without large payload copies; invalid inputs reject before work stops. | Passed source/capture and both-carrier controls |
| P3 — fair target/resolution work | Resolver owner: `src/bap/target_resolution.rs`, private continuation and coordinator queue; composition/native validator compatibility as applicable. | P2 | Per-operation suspension, deterministic 2:1:1 scheduling, per-task/global caps, no starvation when budget permits, unchanged proof admission. | Passed fair-prefix controls and native compatibility |
| P4 — checked question constraints | Constraint owner: private question implementation reusing `src/bap/refinement.rs`, `src/investigation/backward_values.rs` and existing loop/guard checks. | P2; P3 for integrated work | Refutation, coherent model witness, abstract-only unknown and premise conflict distinguished; scoped inverses and invariant use match independent concrete evaluators. | Passed finite witness/refutation/unknown/premise controls |
| P5 — callee and memory-origin integration | Memory owner: `src/investigation/memory_refinement.rs`, frame import adapter, local fault witness/assessment and tests. | P2/P4; applicable M4 clauses | Full baseline origin universe recomputed/validated from completed state, not trusted from a standalone memory table; validated callee import or honest unavailable collection; checked per-instance/all-context exclusions; no caller completion dependency. | Passed controlled/original local dependency and Scanner candidate checks |
| P6 — immutable source revision | Source/composition owner: new question revision binding, existing frame preparation/structure recovery and resolver proof validation. | P3/P4 | Same snapshot/roots/range, candidate-to-admitted checks, parent identity, bounded revisions and stale negative/invariant/import invalidation. | Passed immutable revision and replay controls |
| P7 — codec, views and opt-in CLI | Product owner: `src/reports/frame_question.rs`, `src/bin/ariadne_minidump/frame_question.rs`, existing CLI parser, root test registrations and report/input tests. | P2–P6 | Strict self-contained replay, independent layers, JSON/text/DOT links, source/old-codec compatibility and pre-capture option/policy validation. | Passed live CLI, formats and helper-free saved replay |
| P8 — compiled behavioral mutations | Qualification owner: new mutation entry point and unchanged independent observers in tests, separate mutation target directory. | P7 | Each listed mutation has a passing original control and a compiled behavioral rejection; compile/transport failures earn no sensitivity credit. | Passed remote: 16 original controls and compiled behavioral rejections |
| P9 — finite/native/capture qualification | Qualification owner: isolated source/tool capsules and `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/DATE/`. | P7/P8; declared import gates | Required root/features, models/oracles, native compatibility, two capture applications and saved-source replay pass their named clauses; missing tiers remain explicit. | Passed remote finite/native/capture tiers and applicable FC5/M4 imports |
| P10 — product acceptance and documentation | Corpus/docs owner: canonical usage, result examples, remaining evidence requirements, plan and roadmap. | P9 plus imported gates required by the final claim | At least one new question improvement without completed caller analysis, useful fault-local explanation, honest original-case limits and source-bound publication. | Passed declared finite product acceptance and durable evidence |

P3 and P4 can proceed independently after P2; P5 consumes P4's checked value
scope. P6 must finish before a product may publish an extended source. P7 may
start on fixed-source views, but cannot pass while revision replay is missing.
Start with one narrow vertical slice: a fixed-source alternative question and
local scalar facts; then add fair resolver continuation, callee origins and
source revisions. That sequencing does not remove the later gates.

## P0: freeze concrete questions before implementation

Keep the canonical design as the single interface specification. Freeze:

1. Exactly one question per request: alternative consistency or fault dependency,
   with source-selected `N:M`, typed sites/edges/accesses and bounded predicates.
   Selection never adds discovery roots or silently expands activation scope.
2. Point-specific observed/derived/conditional facts, supported transfer profile,
   instance/context scope and premise compatibility. Valid contradictory
   premises get a conflict diagnostic, not arbitrary writer exclusions.
3. Owned source carriers for existing `BoundFrameStructure` and
   `BoundFrameConnections`; partial connection layers remain acceptable inputs.
4. Completed-callee import identity and source/request equivalence obligations;
   no borrowing a different capture's query by matching addresses.
5. Baseline candidate universe, explicit unknown/interference alternatives,
   quantified exclusion scope and the meaning of incomplete collection.
6. Finite bounds covering source/proof input, validation, work queues, quanta,
   states/expressions, candidates, source revisions, clocks and publication.
   Retain the old policies and validate new defaults against the large source.
7. Separate logical source/question identities and publication bindings,
   proof dependency epochs, deterministic ordering and deadline-prefix replay.
8. Independent statuses for frame binding, structure, optional connections,
   question coverage, feasibility, values/origins and execution evidence.
   Execution evidence is `not_supplied` in v1, not inferred from a dump.

Freeze literal expectations before examining implementation outputs. The
reference evaluator must not call the SUT or duplicate its scheduling/data
structures. Derive small-width value inverses and path consistency by exhaustive
concrete evaluation, alias relations by explicit modular byte sets, and fairness
by an independent service schedule. Reuse existing oracles only for unchanged
rules; new composition/coverage behavior needs its own expectations.

## P1: modeled properties and concrete proof obligations

Add models before accepting runtime behavior. Register model/checker links in
`Specs/README.md` only after those files exist. Use the existing memory,
frame-connection, guard/target and induction models as imported contracts, not
as a claimed universal proof of the new composition.

Required modeled properties:

- Snapshot/source/activation identity and original roots are immutable; selectors
  do not become roots and candidate targets cannot bypass admission.
- Fair quanta serve runnable admitted tasks across and within all priority bands
  when sufficient steps are supplied. A global stop makes unserved tasks unknown.
- Facts preserve point, width, correlated context and hypotheses. Observations
  cannot move backward without checked transfers; joining independent byte
  alternatives cannot produce a jointly exact pointer.
- Model witnesses satisfy every supported relation; abstract nonemptiness is
  unknown. Refutations require sound enclosing semantics and quantified coverage.
- A source revision invalidates dependent old-epoch closure/refutation evidence;
  a conditional result cannot shed its hypotheses or mix contradictory premises.
- The complete original writer universe survives selection, examples and stops.
  Exclusion requires every relevant access/instance covered; unknown footprints,
  other threads and open frontiers remain alternatives.
- Value precision survives an independent expansion stop; all result layers and
  producer stops remain distinct from malformed evidence and verifier refusal.
- Finite work, task/revision admission and fair stopping terminate in the modeled
  schedule. Nothing implies real executed history or program-level disconnection.

The models abstract bytes, cryptographic hashing, parser allocation and wall
clock. Concrete Rust/native tests must check those premises. Explain the
model-to-model assumptions and correspondence; do not claim a coupling theorem
or universal Rust/native/ISA refinement merely because finite checking passes.

## P2–P6: implementation controls and hard cases

| Case | Independent expected result / preserved fact |
| --- | --- |
| Selected late dispatch after an expensive earlier dispatch | It receives a bounded quantum under sufficient total work; old work is retained and no certificate is invented when time runs out. |
| Newly discovered tasks keep arriving | Existing peers remain ahead in their band's rotation; finite queue/admission stops are explicit. |
| Unknown continuation outside the represented corridor | It remains a relevant possible reconnection, even when no displayed sample uses it. |
| Empty abstract preimage vs nonempty abstract set | Checked emptiness may refute within scope; nonemptiness alone stays unknown until a coherent model witness is validated. |
| Captured RAX at fault, preceding overwrite, or generic load | Transport only through admitted point-specific relations; overwritten information or load-address inversion stops rather than guessing. |
| Inconsistent explicit premise with valid observation | Preserve both sources and report premise conflict; no vacuous blanket writer exclusion. |
| Whole pointer assembled from different byte paths | No exact whole-pointer fact without a shared context/correlation witness. |
| Recursive frames at equal VAs | Activation, call-point and value scopes remain distinct. Saved return PC is not a branch trace or historical argument value. |
| Existing dispatch loop invariant | Only its checked dispatch incoming-coverage conclusion is imported; it cannot become a value/iteration invariant. |
| Source gets a late edge or updated candidate epoch | Stale coverage/refutation/import dependencies reject or are recomputed; old source remains inspectable. |
| Missing capture bytes or old saved report lacks AST | Explicit unavailable evidence; no re-lifting, file fallback or later-run substitution. |
| Same source/request completed callee vs different snapshot/profile | First imports with a checked witness; second rejects even when addresses are equal. |
| No completed callee | Supported local value facts may survive; complete origin collection is unavailable, or separately bounded callee-only completion is requested. |
| Store has several accesses; one is unknown/overlapping | Static candidate remains unless all accesses and quantified contexts are proved disjoint. |
| Disjoint first loop occurrence, possible later occurrence | The all-visits candidate remains; one bounded-prefix result is not a static exclusion. |
| Equal starts, partial overlap or 64-bit wrap | Compare explicit modular byte ranges; equal-base claims require a compatible proved value instance. |
| No displayed route uses a writer; entry or opaque effects remain | All original candidates plus relevant unknown/interference alternatives survive. |
| One captured thread, or another thread has no stack match | No inferred absence of interval interference. |
| Zero work, queue/candidate overflow or one layer's deadline | Other validated layers and established facts survive; no clipped table or stopped computation earns a negative claim. |

Preserve existing guarded/target report versions unless a real semantic/wire
change requires a separately versioned profile. A changed producer schedule is
not permission to weaken validators. If a proof format changes, update and
qualify Rust/native validation together, retaining legacy decoding/replay.

## P7: product and replay gates

The proposed `ariadne.frame-question/v1` publication must embed the complete
source/evidence bytes required for verification. Reuse existing source codecs;
keep all references local and bound, with finite input/expanded proof caps.

The verifier reconstructs bound source/question evidence before replaying
scheduling, value rules, coverage, writer dispositions and source revisions.
Rehashing a forged envelope must not make a false conclusion valid. Check raw
collection bounds before typed copies/work. A verifier work/byte refusal creates
no trusted assessment. Replaying a producer deadline uses a validated work
prefix, not the verifier's elapsed wall clock.

CLI gates cover duplicate/unknown fields/options, invalid `N:M`, selectors,
widths/predicates and policy files before dump access; incompatible old modes;
atomic output-directory publication; no full caller completion; and identical
JSON/text/DOT conclusions, source links, hypotheses and independent statuses.
Source-based library use must work without input adapters or native helpers.

Keep source/output retention complete: failure to fit a byte policy is a refusal
or explicit unavailable layer, never hidden evidence clipping. Candidate/table
summary omissions cannot certify coverage. Preserve old structural v1/v2,
connection v1, memory v1 and normal full-analysis default behavior separately.

## P8–P9: qualification and mutation sensitivity

Run these real-code mutations against unchanged independent observers:

1. Starve a selected late site or let new tasks jump ahead of an existing peer.
2. Drop an off-corridor unknown frontier or a pending prerequisite after a stop.
3. Turn abstract nonemptiness into a model witness, or accept an invalid witness.
4. Transport crash-time values across an overwrite, wrong point or wrong frame.
5. Merge incompatible byte/premise contexts into an exact pointer.
6. Accept a stale-epoch refutation/invariant or strip a conditional hypothesis.
7. Admit a newly found target without captured-byte/guard/composition validation.
8. Import a callee from another snapshot/request or bypass completion/coverage.
9. Drop entry, opaque, unknown-memory or external-interference alternatives.
10. Exclude a multi-access/cyclic static writer using only one access/instance,
    same-register spelling or sample-route absence.
11. Mishandle partial overlap/wrap, or apply the wrong architectural register bank.
12. Raise verifier limits from producer policy, bypass zero budgets, or trust a
    rehashed false status/candidate/certificate without exact replay.

Freeze observer names and exact mutation seams when implementation exists.
Each campaign starts with its unmodified observer, records actual binary/source
hashes and requires a named behavioral failure. Compilation failures, missing
helpers, timeouts and transport problems remain failed/unexercised attempts.
Do not synthesize the expected output in the mutation harness.

Use isolated source/dependency capsules and separate replay/mutation target
subdirectories. Run the applicable root checks:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Also exercise reports-only, BAP-only and input builds; core-only must activate
no external dependencies. New native-affecting resolver/admission changes need
normal native-default execution and independent Rust parity for the selected
corpus. A pure question consumer is labeled as such, never as native-core work.
Ordinary Cargo tests do not exercise all ignored tests.

Follow the established remote Windows WSL qualification workflow for heavy
campaigns; discover and hash-verify the actual host/tools before execution.
The Stage 5.2 local record reports an unavailable remote launcher at its date.
If remote prerequisites remain unavailable, source/local progress may continue,
but P9's remote gate and imported FC5/M4 remote clauses stay unexercised.
Record that boundary rather than treating local output as a remote pass.

## Corpus and P10 acceptance

| Corpus | Required application | Identity / expected limit |
| --- | --- | --- |
| Original large Windows frame source | Import saved structural/connection sources, ask one documented targeted question and run a compatible callee-local dependency assessment when evidence exists. No full caller completion. | Dump `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, range 1:0; structural binding `229e9248025f1470110b652c92ea370131cee2bf4fe72484a8dee8cb4c39db18`. Missing fields/semantics or unresolved values remain explicit. |
| Controlled recursive Crashpad program | Positive point/activation and dependency cases; distinct recursive VAs, partial/work-stopped layers and a useful checked question conclusion. | Dump `47d93971541230b24d992e3c0f60a17df732145f083089844b99e44597f1ae34`, thread 17848, range 5:0; structural binding `5a7ce406aa508a0392b39281c36f8552c90487ec1ad80905d57795484154865b`. Existing 5.2 examples are not value/feasibility expectations. |
| Historical Scanner memory baseline | Preserve exact original candidate table and separately exercise its declared scope, if source/tool inputs can be verified. | The Scanner ledger identifies dump `ed82b4…`, different from the original large frame-source dump. Its retained 12-origin count must never be borrowed into another snapshot. |
| Independent finite controls | Positive and negative branch/value cases, scheduler starvation controls, cyclic instances, alias/wrap/interference and strict replay forgery cases. | Literal expectations precede implementation; bounded enumeration alone supplies no original-history claim. |

P10 requires at least one *new* scoped question improvement over structural-only
reporting and one useful fault-local explanation with preserved writer coverage,
without completing caller dataflow. Finite controls must include checked
refutations and model witnesses, as well as honest unknowns. Reprinting old
maps, returning only unknown for every positive control, or lowering an example
count does not satisfy this gate.

The original case may remain partial when its capture cannot answer the chosen
question. Its application must still preserve source/candidates, identify the
actual blocking obligation and state concrete evidence requirements. It may not
be replaced by a small fixture pass or recast as a historical root-cause result.
Freeze the chosen investigator question and expected bounded-model outcome
before the acceptance run; do not select a trivial passing query afterward.

Store raw source/tool/command/hash inventories, reports and failed/corrected
receipts under `https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/DATE/`. All evidence paths,
including copied report evidence, use Git LFS. Preserve original evidence
bytes/identities; staged pointers or fresh docs are not new qualification.
Update the canonical design, direct plan links, roadmap, status and usage after
actual stages pass. Do not overwrite dated recommendation/qualification claims.

## Planning record

2026-10-18: read all four recommendation items, current SF/FC/M ledgers and
source seams for frame recovery/connections, target scheduling, retained BIL
transfers, fault witnesses, completed memory origins and separate supplied
stateflow. Wrote the integration design and this complete program plan.
No new executable interface, model checker, runtime mutation or capture campaign
was created or run by this documentation change. Navigation/whitespace checks
are recorded after writing; implementation P0–P10 remains pending.


Documentation-only validation, 2026-10-18: the navigation checker passes with
78 connected documents, 77 Context and follow-up sections and 2,301 local links;
scoped whitespace checks pass. The original recommendation contains four
ordered items, each mapped to its current contract and remaining stages above.
These checks do not credit runtime/model/capture implementation or P0–P10
acceptance.

## 2026-10-18 implementation and local acceptance

The [canonical design](../../docs/Ariadne/frame-question-investigation-design.md#implemented-profile-and-usage)
owns the exact API, supported profile, usage and cooperative deadline limits.
The [source-bound record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261018/README.md)
retains every tested capsule, tool identity, raw log and product. Use the
`mutations-current` capsule as the final implementation baseline; earlier
mutation runs and failed attempts are historical, not interchangeable passes.

- P0/P1: typed selectors, immutable scopes, independent four-bit bit/inverse
  expectations, two new models, 18 TLC configurations and the imported memory
  model are checked locally. The memory model needed only a sequence type
  annotation; the original failed typecheck is retained.
- P2/P6: owned structural/connection carriers, conditional metadata, exact sealed
  callee imports, malformed selectors before budgets, and progressive source
  revisions are checked. Only consumed callee imports survive publication;
  unused caller imports do not force caller replay.
- P3: the existing target resolver rotates bounded reverse-prefix continuations
  through the private FIFO. Selected late sites receive service. Legacy callers
  retain the separate path. AST/table/induction operations use their existing
  finite policies; clocks are cooperative, not process preemption.
- P4/P5: model witnesses, scoped refutations, abstract-only unknowns and premise
  conflicts are distinct. Values stop at unsupported inverses or instance/depth
  boundaries. Full original reaching-memory candidates are retained, including
  entry/opaque effects and interference; samples never filter the universe.
- P7/P8: the opt-in CLI and strict v1 codec publish JSON/text/DOT and replay all
  conclusions without helpers. Both source carriers, zero expression/work/queue
  bounds, host refusal, rehashed false conclusions and clock receipts are covered.
  All 16 final mutations compiled, passed their original observer and failed
  that unchanged observer; compile failures earn no sensitivity credit.
- P9: 323 default/57 core/70 reports/194 BAP tests pass locally, with
  114/22/22/56 ignored respectively. Format/Clippy/layout/navigation pass. Nine
  native compatibility tests and a native-default/Rust byte comparison pass.
  The live finite controls and both saved capture products pass separately.
- P10: the real recursive Crashpad case adds 371 value records and preserves
  10 original memory origins plus interference without caller completion.
  Numerical depth exhaustion is explicit. The original large question stays
  unknown after 1,048,576 resolver operations and a scalar prefix-depth stop;
  all 610 source gaps remain. Finite controls establish both a new model witness
  and a new refutation beyond structural reporting.

No available registered remote executor, `r_windev` launcher or SSH host
configuration was found. Remote P9, FC5/M4, full Scanner/caller S6 and frame-path
F4 remain unexercised. This is local implementation/product acceptance, not
remote, release or universal refinement qualification.

### Point-ordering correction and final scope

A new synthetic breakpoint/counter fixture reproduced an invalid provisional
refutation: its captured RCX=2 can occur at a later loop visit, while applying it
to the first visit pruned that visit. The current profile returns unknown until
all-visit value coverage is admitted. Additional controls prevent before-state
witnesses from consuming unchecked after-state premises, prevent successful
normal transfer at the captured top PC, and prevent partial-word outputs/joins
from becoming exact whole-register values. Four new model configurations and
four additional compiled mutations cover these findings. Earlier provisional
artifacts are preserved as historical and do not qualify this corrected source.

## 2026-10-19 remote completion

The [qualification record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/frame-question/20261019/README.md)
binds the 875-file source capsule
`7e23bbd4aab5e12e48d342d4ab0a9c9b51e2aacbd8ed35c2a749919c088610c6`
to remote Windows WSL execution. Root default/core/reports/BAP counts are
323/57/70/194 passed, with 114/22/22/56 ignored; named native/capture/replay tiers
are exercised separately. Format, Clippy, feature/layout/core-dependency checks,
18 question/scheduler + 13 connection + one memory model configuration,
independent oracles and 16/12/5 compiled mutations pass.

Both declared saved sources pass public connection application/replay and
independent full-graph/SCC/shortest checks. The original question retains all
610 source gaps and returns unknown at 1,048,576 resolver operations and a
prefix-depth stop. The controlled real capture provides 371 point-value records
and preserves all 10 memory candidates plus interference. Its values stop at
depth while origin assessment finishes. The extra original fault query provides
25 records and all 12 visible baseline candidates; conservative origin-work
charging stops refinement, preserving an unknown count and unresolved entries.

Full Scanner assessment preserves baseline report bytes, exactly matches native
and Rust output and retains all 12 entry/instruction memory origins. Actual
prior/current question products, structural v1/conditional v2 and both legacy
combined-report versions replay with their named policies; BAP-only report
replay uses deliberately unavailable helper/runtime paths.

The new source-bound memory mutation driver records positive controls, actual
compiler executables, exact named behavioral failures and source stability.
Initial missing-rg, absent output-parent and independent-observer stopped-count
interpretation failures remain in the archive with their original statuses.
The final memory run uses its own root target subdirectory; a preliminary run
outside that directory contributes no additional final mutation count.

This completion qualifies the question/connection/memory consumers on the
explicitly declared finite sources. An additional fresh raw original refresh
stops at guard candidate coverage (caller 9 nodes, callee 769); the exact retained
large source remains the required 10,367-node consumer acceptance case. No caller
completion, broad release, execution-history or ISA refinement claim follows.
