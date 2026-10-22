# Semantic assurance and proof boundaries

## Context and follow-up

**Status.** Current assurance contract: BAP lifting is trusted, independent ISA
proofs are retired and their specifications/checkers were removed on 2026-10-11.
Their model guides were removed on 2026-10-16. Universal Rust refinement remains
open.

**Why this document exists.** [BAP assessment](bap-analysis-core-design.md#architectural-rationale) separates external semantics from ownership of analysis correctness.

**What this document establishes.** Pinned BAP lifting is an explicit trusted
dependency. Ariadne owns transport, projection, analysis and evidence validation.
The contract distinguishes finite conformance, the open universal Rust
refinement boundary, retirement of the independent AMD64 instruction-step
proof track, and the practical priorities that shaped the delivered workflow.

**Where to go next.**

- [Active Windows I4 qualification](workload-performance-design.md#windows-investigation-replacement) — keeps producer correctness and the separately qualified fixed CLI timing condition distinct from the lifter trust decision.
- [Projection contract](bap-analysis-core-design.md) — defines the boundary Ariadne still validates.
- [Backend delivery ledger](../../.agents/plans/completed/bap-integration.md) — records qualified native migration and the remaining proof, workload and release limits.
- [Typed replay](typed-replay-design.md) — finite conformance for the stateflow
  and supplied-IR machines, distinct from universal refinement.
- [Generated-validation and retention plan](../../.agents/plans/generated-validation-retention.md)
  — executable generated tests and removal of retained qualification artifacts.
- [Workload performance design](workload-performance-design.md#historical-baseline-2026-09-29)
  — preserves the initial measured baseline and links its later qualification
  successors; performance acceptance does not discharge a proof obligation.

**What remains unresolved.** The [active Windows I4 replacement](workload-performance-design.md#windows-investigation-replacement) passes correctness; the later [native performance qualification](workload-performance-design.md#native-investigation-qualification) meets its unchanged CLI budget; the original Electron case is historical. The native analysis-core replacement is implemented; its [qualification](bap-analysis-core-design.md#native-qualification) is separate from those product criteria. The universal Rust refinement boundary remains open; retired ISA obligations were not discharged.

For the wider context, see the optional [documentation map](../documentation-map.md).

Decision: **2026-10-02**, approved by the user. Ariadne retires its independent
AMD64 instruction-step project, including the user64 milestones, Stage D, Lean
ISA proofs and full-manual coverage objective. Retirement changes project scope;
it does not mark the former proof obligations as satisfied.

On **2026-10-22**, the user requested full AMD64 operation implementation
coverage. The [operation coverage program](../../.agents/plans/amd64-operation-coverage.md)
reopens implementation coverage across the semantic producer/projection and
captured unwind layers. This later implementation objective does not restore
the retired independent ISA-proof track or discharge its former obligations.
Its versioned inventory and fresh operation tests must establish their own
coverage; conservative unsupported results remain gaps.

Ariadne relies on a pinned BAP lifter for AMD64 instruction semantics and
validates its own semantic projection and analysis. Results remain conditional
on supported lifting behavior and captured evidence.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Active responsibility

The selected backend uses BAP's legacy x86 lifter and typed BIL. A formal
semantics for BIL does not itself prove that every AMD64 lift matches hardware.
The pinned helper/runtime identities and supported projection scope remain part
of the [backend contract](bap-analysis-core-design.md).

Ariadne owns validation of the helper protocol, exact bytes and identities,
typed AST transport, register aliases, uses/may-defs/must-defs projection,
conservative memory and call behavior, analysis algorithms and evidence-bound
reports. Unsupported operations retain explicit gaps. Corpus tests, independent
decode/control checks, model replay and actual mutation sensitivity remain active.

The CFG, reaching-definition, slicing, abstract-stateflow, supplied-IR and
effects specifications remain active. The Rust implementations and their
finite replay checks remain model-relative evidence; a universal refinement
proof is a separate open boundary. This decision adds no execution-history or
root-cause guarantee.

## Generated validation and evidence retention

The user-selected policy replaces the entire retained evidence collection with
executable tests and actual test inputs. It supersedes the earlier compact-receipt,
archive-deduplication and on-demand-fetch policy. The
[implementation plan](../../.agents/plans/generated-validation-retention.md)
tracks this complete migration; the [test matrix](../../tests/README.md) owns
commands, prerequisites and coverage.

### What is maintained

Maintain TLA+ contracts and generated replay corpora, PBT generators, independent
oracles, compiled mutation controls, minimized failures, explicit golden vectors
and small input fixtures that tests actually consume. Keep byte/snapshot/query
identities and supported-semantic premises in those tests. Product-level captured
evidence remains part of the analysis contract and report schemas.

Do not retain qualification reports, prior passing flags, measurements, raw
logs, copied source trees or qualification archives in source. Current tests
must execute without the former collection or its LFS objects. Explicitly supplied
reports from the same run may be validated by aggregators, but they are disposable
run products and do not become repository acceptance records.

The old archive writers and archive-export helper have been removed. A selected
full native/capture campaign executes its actual validators and emits transient
results, with no sealing or archive-publication phase. I5c runs its current native
matrix instead of importing prior W2/W3 runtime streams. Stage E replay is
unexercised until its current command executes; no old passed field supplies it.

### Running generated validation

```sh
python3 tools/run_generated_validation.py
python3 tools/run_generated_validation.py --mbt all
python3 tools/run_generated_validation.py --mbt skip --seed 42 --cases 512
```

The default selects two fixed core seeds, three core properties per seed, ten
graph properties and three synthetic-unwind properties: 3,200 configured generated
cases, followed by current TLA+-generated core replay and five compiled mutants.
`--mbt all` also selects supplied-state/IR replay. `--mbt skip` explicitly records
that generated replay is unexercised; missing selected tools fail the run.

The [core properties](../../tests/core_properties.rs) compare every public state
transition with an independent literal reference derived from `Specs/Ariadne.tla`.
They span one to seven nodes, three locations, both byte policies, sparse low/high
u64 addresses, call summaries, byte precedence, decode failures, multiple roots,
possible/definite writes and undiscovered slice seeds. Optimized completion is
checked against the same final reference result. This source-reviewed executable
model is separate from TLC-generated replay and does not establish refinement.

All runner output stays in a fresh ignored `target/generated-validation/run-*`
directory. There are no publication or archival options. Failures retain transient
raw diagnostics and persisted regression seeds; fixed bugs should receive small
concrete regression cases. Zero executed tests, missing cases, stale nested
results, source drift and tool drift cannot produce a passing run.

### Replacements for former record dependencies

- A small Windows input archive contains only a controlled dump, matching PE and
  witness. The independent byte/PE/context/checksum inspector executes afresh;
  an old inspection's passed flag is never consulted.
- Scalar BIL tests obtain fresh lifts from the pinned helper and compare them
  with independent integer/flag equations. Missing native prerequisites fail
  that selected tier.
- Explicit compatibility vectors define all 666 expected output sizes/digests;
  no old output payload, runtime path or historical acceptance flag is retained.
- Compact signed table inputs and normalized codec sources are actual test
  inputs. Independent arithmetic/oracle checks consume them directly.
- Tests prevent recreating the collection, archival writers or LFS-only fixture
  inputs. The collection's old LFS attributes and download policy are removed.

### Historical results and limits

Dated documentation may point into the exact Git revision that contained a run.
Those links provide historical context, not current qualification. Git history
and existing cached LFS objects are not rewritten or pruned. Fresh tests and their
prerequisites determine current coverage; prior native, performance or release
claims cannot be inferred from PBT/MBT success alone.

The migration changes validation storage and execution, not captured-byte
precedence, conservative dependencies, uncertainty, product schemas or the
trusted-BAP premise. Unavailable real captures, helper/runtime dependencies,
full model exploration and universal refinement remain explicit limits.

### Test-only migration validation, 2026-10-22

The retained collection was removed: 5,229 working-tree files, approximately
3,646.58 decimal MB of payloads, including the preceding compact-retention
experiment's metadata. No qualification archive was moved elsewhere in source.
About 0.5 decimal MB of selected raw inputs, expected values and source pins
remain as actual test fixtures; normalized codec inputs were renamed by their
role. Historical Git/LFS history is not rewritten or pruned.

Fresh execution without the collection passes all 3,200 configured property
cases, twelve core traces / 168 observations / five compiled mutants, and
64 stateflow/IR traces / 326 observations / fifteen compiled mutants. The
current native scalar helper passes 104 independent arithmetic/flag comparisons.
All 247 Python controls pass, including the new output/fixture policy and fresh
native-oracle transport checks. Independent composition, caller and loop oracles
also pass, including all nine table inputs / 370 entries / 64 distinct targets.

Formatting, default Rust tests (361 pass / 129 ignored), core-only tests
(64 / 22), reports-only tests (77 / 23), all-feature/all-target Clippy, root
layout and documentation checks pass. Private helper gates were aligned with
actual input/BAP ownership so the no-input MBT configuration also passes its
strict Clippy check. The standard-library-only dependency tree remains empty
apart from the root package. Run products are ignored and are not published.

The installed native analysis helper's source bindings differ from the checkout,
and the full qualifier's sealed read-only MirrorRust snapshot is inactive.
Full native-core/capture, timing and release qualification therefore remain
unexercised. The fresh scalar-lifter check is its separate, narrow tier. Model
checking of wider domains and universal refinement remain separate obligations;
old reports do not discharge any of them.

## Universal Rust refinement boundary

The Rust `Analyzer` executes the transition phases of `Specs/Ariadne.tla` on
validated, owned inputs. The 2026-09-29
[source-bound progress report](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/stage-b-f-validation.json)
rechecked generated-request regressions and the then six-fixture MBT gate
(12 complete traces, 168 matched states, five engine mutants) within the effects
regression. Those are dated finite conformance results, not a universal proof.
The later [typed replay campaign](typed-replay-design.md) expands bounded
stateflow and IR evidence without changing this proof boundary.

TLA+ and Rust still need an explicit proved representation relation from finite TLA+ addresses/sets/maps to `u64` and ordered Rust
collections, plus obligations for input validation, initialization, each
`step()` action, the deterministic schedule as an allowed TLA+ choice, result
views and finite termination. A proof about an abstract machine does not by
itself connect compiled Rust to that proof. The decoder, effect rules, captured
bytes and semantic projection remain additional trusted or checked boundaries.
The independent ISA campaign is retired under the scope decision above;
retirement does not establish a proof of BAP lifting.
**No universal Rust refinement claim is made.**

The baseline originally published beside this boundary is preserved in the
[workload performance design](workload-performance-design.md#historical-baseline-2026-09-29).
Its [later LLVM qualification](workload-performance-design.md#historical-llvm-workload-qualification),
[native BAP qualification](bap-analysis-core-design.md#native-qualification) and
[fixed-budget investigation qualification](workload-performance-design.md#native-investigation-qualification) answer
separate measured performance and finite correctness questions. None establishes
a universal implementation refinement proof.

## Dependency audit and retained references

Neither the native-default minidump path nor the Rust reference executes the
independent AMD64 TLA+/Lean library. Before retirement, orchestration scripts invoked
the register-core profile gate: `check_b_f_progress.py`, `check_stage_e.py` and
`check_bap_semantics.py`. Those calls and their pass/fail dependencies are removed.
New reports replace `registerCoreAcceptance` with an explicit
`instructionStepTrack` retirement status. Stage E and BAP qualification
reports advanced to schema v2 for that retirement update; current BAP
workload aggregates use v5 and Stage E completion retains v2. The
retirement status remains explicit in their successors; historical JSON files retain
their original fields and bytes. The B/C/E/F report remains unversioned.

On **2026-10-11**, the user requested removal of the retired specifications.
The checkout now omits 73 ISA-only TLA+ modules, 38 configurations, ten shell
checkers, the AMD64 source/coverage inventory directory and fifteen obsolete
Python tools/tests. This includes the initial `AriadneX86_64Semantics` research
and its integration fixtures. Active analysis and question-level model bodies
remain unchanged, including memory refinement and frame paths.

The effects gate still binds the AMD manual pin as source-review provenance.
Its exact bytes moved from `Specs/AMD64/manuals.lock.json` to
[amd-manuals.lock.json](../../tests/bap/fixtures/amd-manuals.lock.json), with SHA-256
`eb8e6fea525e43a1f2740e97f4bff0dede564cac1fda64c5a5e2e9a46a6699f3`.
This file identifies reviewed sources; it is not an ISA specification or coverage
claim. Active effects/progress inventories continue to exclude retired models.

The [last retained specification tree](https://github.com/NzSN/Ariadne/tree/01ae404e8c8556966e219118945082ff8e213f7e/Specs)
and [obsolete tooling](https://github.com/NzSN/Ariadne/tree/01ae404e8c8556966e219118945082ff8e213f7e/tools)
remain available at an immutable Git revision. Old commands require that historical checkout.
The pre-retirement state also remains at `2ba80a9`.

On **2026-10-16**, the user also requested removal of the model documentation.
All 26 `docs/amd64-*.md` guides and `docs/x86-64-semantics.md` were removed,
together with their navigation entries and the retired ISA terminology section.
The root [Lean reference](../../lean/README.md) retains a short scope notice in
place of its component guide. Git history preserves the removed documentation.

The Lean sources and machine-readable Stage D evidence remain for interpretation
of earlier results. Recorded evidence keeps its original bytes, source paths and
pass flags; the moved manual pin does not rebind any previous qualification.
Retirement and removal leave former proof obligations unresolved. Active product
gates depend on BAP projection and analysis contracts.

The **2026-10-11** cleanup validation passed the three active-qualification tests, SANY
parsing of all 17 remaining TLA+ modules, documentation links and Rust layout.
The qualification test's stale mock checkout now supplies the corpus file read
by the BAP runner; the original HEAD test independently reproduced that fixture
failure. A hash audit confirms 677 existing implementation/fixture/model/Lean/
raw-evidence files retain their pre-cleanup bytes, as does the relocated manual
pin. These are cleanup checks, not model exploration, native or release qualification.

The **2026-10-16** documentation-removal check passes navigation and section
validation for all 73 remaining connected documents and 2,129 local links.
A separate check passes all 157 local Markdown/HTML links in the chat reports;
`git diff --check` passes. The source diff confirms that runtime code, active
model bodies, retained Lean sources and raw evidence are unchanged. No build,
model campaign or dump analysis was rerun for this documentation cleanup.

## Qualification limits preserved

The user separately authorized a [controlled BAP Windows replacement](bap-analysis-core-design.md#windows-workload-replacement)
and an [unlimited BAP timing policy](bap-analysis-core-design.md#unlimited-timing-policy). Active Stage 1
requires that replacement's valid captured evidence, measured finite samples and
passing implementation gates. Investigation I4 uses its own
[re-pinned query](workload-performance-design.md#windows-investigation-replacement) and unchanged fixed budget, met
by the later [performance qualification](workload-performance-design.md#native-investigation-qualification). The
missing original Electron capture remains historical.

Retiring ISA proofs did not deliver those changes or waive their evidence
clauses. Native Stage 2 has [separate analysis qualification](bap-analysis-core-design.md#native-qualification).
The [projection-admission extension](../../.agents/plans/completed/bap-projection-admission.md)
was separately accepted on 2026-10-10 for its selected Windows replacement
corpus and declared tiers. Its [acceptance record](file-reader-design.md#windows-replacement-capture-and-bounded-query)
retains the excluded historical real-Linux capture/phase clauses and report
hashes. Retirement itself admitted no new forms and refreshed no old records;
later admission acceptance does not establish a universal or release proof.

The [roadmap](../../ROADMAP.md),
[agent instructions](../../AGENTS.md) and
[practical priorities](#practical-assurance-priorities) describe active scope.

<a id="retirement-validation"></a>

## Historical retirement validation (2026-10-02)

`python3 -m unittest discover -s tools -p test_active_qualification.py -v`
passed three tests in the retirement delivery. Controlled subprocess fixtures
exercised all three runners
without ISA files, gate failures, source-hash changes and both outcomes of the
Windows workload condition: eleven runner executions in total. An inventory
check confirmed that effects qualification retained the analysis specifications
and manual provenance while excluding retired ISA models.

The Rust layout check and documentation link/diff checks also passed. These were
focused orchestration and documentation checks, not fresh native execution,
model replay, mutation campaigns or release qualification. Production Rust,
native helper code, formal model bodies and retained JSON evidence were unchanged
in that retirement delivery.

## Practical assurance priorities

The delivery is **Windows/Linux AMD64 minidump → local graph → possible value
origins → backward slice → report** using BAP. The 2026-10-02 retirement decision
superseded the original long-term independent ISA-proof commitment. The
[roadmap](../../ROADMAP.md) now prioritizes captured investigations under explicit
premises. Passing results support different claims:

| Assurance level | Supported claim | Remaining boundary |
| --- | --- | --- |
| Captured input and decode reference | Bytes, VAs, provenance, independent decode/control observations | Historical execution is not established |
| BAP projection | Exercised typed-BIL transport, dependencies, aliases and conservative effects | No universal lifter correctness/full ISA coverage |
| Analysis and investigation | Model-relative CFG/dataflow/slicing and evidence-bound claims | No root-cause or historical-path proof |

The practical priorities were delivered at these dated scopes:

| Priority / completed plan | Decision and evidence |
| --- | --- |
| [Representative capture](../../.agents/plans/completed/priority-1-real-capture-plan.md) | 2026-09-29 controlled Chromium/Linux case used a hash-pinned dump, independently established earlier captured entry and crash-IP seed. Its [capture design/evidence](file-reader-design.md#independent-entry-and-real-capture-evidence) binds matched-build entry evidence and a possible producer. Backward decoding and companion executable bytes cannot invent missing capture. |
| [Path-driven effects](../../.agents/plans/completed/priority-2-path-driven-effects-plan.md) | The first path required no change; the later Windows path needed eight ordinary-control bindings with opaque effects. [Effect/source review](operand-effects-design.md#path-driven-control-review) preserves weak memory, flags/alias uncertainty and unknown control. New paths can reopen coverage. |
| [Investigator presentation](../../.agents/plans/completed/priority-3-investigator-presentation-plan.md) | [Rendering design](result-rendering.md#instruction-overview-contract) brings exact bytes, typed operands, rule quality, provenance, possible origins and gaps together; versioned JSON and DOT meanings remain stable. |
| [Measured workload performance](../../.agents/plans/completed/priority-4-workload-performance-plan.md) | 2026-09-30 [historical LLVM result](workload-performance-design.md#historical-llvm-workload-qualification) used 98 captured instructions and a 19-node slice; median 3,845.7 → 1,787.6 ms met 2,000 ms while all 277 actions and report hashes stayed equal. Bounded 128/256/512-node families completed; no worst-case claim follows. |

Earlier LLVM timings do not qualify BAP. The missing original Electron capture
was separately replaced by the authorized
[Windows investigation pin](workload-performance-design.md#windows-investigation-replacement);
its failed timing record and later passing performance successor remain distinct.
Other BAP workload/corpus acceptances retain their own source and policy scope.

[Typed replay and reports](typed-replay-design.md) qualify supplied machine-state
and directly supplied LLVM IR at a finite tier with explicit semantic premises.
Universal Rust refinement remains open. PE/ELF image and ELF core readers remain
deferred under the minidump-only input scope.

### Initial historical-capture audit

Both older hash-pinned Breakpad dumps had a 256-byte MemoryList capture around
RIP, including **128 contiguous bytes before RIP**:

| Dump | Crash RIP | Captured code range | Module-relative RIP |
| --- | --- | --- | --- |
| Linux `linux_null_dereference.dmp` | `0x401f26` | `0x401ea6`–`0x401fa5` | `driver` + `0x1f26` |
| Windows `write_av_non_canonical.dmp` | `0x7ff738721331` | `0x7ff7387212b1`–`0x7ff7387213b0` | `crash.exe` + `0x1331` |

This byte availability did not establish an earlier instruction boundary. No
matching symbol artifact was found beside those fixtures at decision time.
A module filename or backward decode from RIP is insufficient entry evidence.
Companions must match build identity and cannot fill missing dump bytes; the
later controlled Chromium case supplied a separate exact-matched companion.
