# Captured indirect control target resolution

## Context and follow-up

**Status.** The finite `captured-indirect-targets/v1` profile passes the
[2026-10-20 R6 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/20261020/README.md).
The [R0–R6 ledger](../../.agents/plans/indirect-target-resolution.md) records fresh
resolver/model/replay/original-capture gates and explicitly retained,
source-verified core-mutation evidence. Producer/runtime semantics remain
unchanged; the diagnostic validation driver pins and exports the original query.
The original 2026-10-13 correction and retry records keep their dated scope. The [initial source-bound record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json)
is historical evidence for its original sources and exercised corpus, not
acceptance of the revised implementation. Its native timing exceeded the frozen
60 s criterion, and its mutation set did not cover every required R6 seam.

**Why this document exists.** The [input design](file-reader-design.md#why-a-reader-alone-is-insufficient)
discovers instruction starts from supplied control facts, while the
[BAP design](bap-analysis-core-design.md) originally left indirect-target
enumeration outside delivery. A full dump can contain a table and its destination
bytes without the baseline pipeline connecting them to an indirect jump.

**What this document establishes.** Current usage, ownership, finite supported forms,
snapshot-relative target semantics, evidence and completeness contracts,
bounded discovery integration and qualification requirements.

**Where to go next.**

- [Guarded target-resolution composition](guarded-target-resolution-design.md) and its [C0–C6 plan](../../.agents/plans/completed/guarded-target-resolution.md) — recorded scoped composition delivery and bounded loop-aware follow-up for the nine captured table dispatches.

- [Dump03958 table witness](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/README.md) — fresh captured reads for nine bounded relative jump tables; numerical candidates are separate from a resolver/guard completion certificate.

- [R0–R6 implementation plan](../../.agents/plans/indirect-target-resolution.md) —
  stage ownership, acceptance gates and execution order for this design.
- [Finite R6 qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/20261020/README.md)
  — final sources, fresh and retained tiers, timing samples and original-query evidence.
- [Core model](../../Specs/Ariadne.tla) and [formal-model guide](../../Specs/README.md)
  — existing target-set certificate and authority for the required extension.
- [Source ownership](architecture.md#ownership-and-process-boundaries) —
  preparation freezes inputs before native or Rust analysis.
- [Inspection evidence](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-inspection.json)
  — the captured table that motivates the first relative-table profile.

**What remains unresolved.** Full base report rendering in all formats, a real
Linux full dump and packaged release remain unqualified; passing individual CLI
samples do not establish a latency distribution. Finite R6 is complete within
its separately bound declared profile. The
selected full-dump explanation remains partial;
its 45 witnessed targets do not certify all incoming paths. General value-set analysis,
mutable heap tables, arbitrary indirect calls, JIT/self-modifying code and
executed history remain outside the initial profile. Completeness requires
validated incoming-state coverage and an explicit captured-memory premise.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## R6 qualification refresh

The authorized [R6 execution sequence](../../.agents/plans/indirect-target-resolution.md#r6-qualification-refresh--2026-10-20)
passes its [2026-10-20 finite aggregate](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/20261020/README.md).
The final capsule contains 1,076 files with SHA-256
`193e31bb835bda4a4e4b5fc59397c424f11adefc691d1e309faf7ff0348d43a5`.
Source-bound in-task root/feature/native controls (`default 334, core-only 64, reports 77, BAP 202, resolver 46`), 39 Python controls
(23 runner/observer plus 16 aggregate), the independent byte/integer oracle,
five finite target-model configurations and typechecking pass. All 14 Rust plus
one native legacy-v1 resolver mutations compile and fail their intended observers
after passing unmodified controls. Fresh native replay matches 168 core and
162 stateflow observations; wrong-digest cases dispatch zero observations.

Twelve ordinary core/stateflow mutants are retained S6 evidence. Import checks
bind the original archive/member identities, all 221 relevant source/corpus/
observer inputs and native helper
`6c444024fddae8d9050570e2e3f1c4cb6c9d463954c5eaf5c3f0c29ebfe3d562`.
They are not relabeled as a fresh campaign.

The exact original Windows dump048B query retains all 45 witnessed targets from
58 entries, `complete=false`, partial explanations and the captured-control-data
premise. Native/Rust full states agree on 3,977 decoded sites, 4,819 edges,
392 slice sites and 10,744,212 definition links; their state digest remains
`4b5c6d947ac8622932e63d8731733e4cf328b7d7401302fcc68ffa0d2ffcf30c`.
The independent observer is bound to the exact raw resolution bytes and current
sources; timed CLI request fingerprints match the pinned normalized request.

Native/Rust JSON explanation-only CLI samples are
`37070` / `15990` ms; maximum measured resolver
passes are `88753` /
`68248` µs. Each CLI sample meets 60,000 ms and each
resolver pass 1,000 ms. Production native transport remains 30 s per response. The pinned
full-state diagnostic driver uses the public 60 s response timeout and exports
request identity/normalized facts; its execution supplies no CLI timing credit.
Producer and runtime semantics retain their existing contracts.

Native controls and mutants explicitly enable helper diagnostics. The runner
captures stdout and stderr separately and appends diagnostics after completion,
so child output cannot split the test-result line. Generic EOF failures and the
earlier interleaved passing-control log earn no credit. All fifteen mutations
reran with the corrected runner. Eight earlier in-task Rust/native checks retain
exact unchanged compiled-input identities; the final Python controls reran.

Archive SHA-256: `bb44c1a28ebee857e5775fac304f74383e7c75bfdd0286b41cc45642880064ba`. The native wrong-seam review, Cargo
stale-mtime feedback, Windows/WSL launch failures, missing oracle inspection
metadata and stopped preliminary mutation attempts remain uncredited in the
archive. The final freeze includes the missing metadata. Earlier historical
`full_plan_acceptance=false` fields retain their original outcomes; the current
finite result does not rewrite them or close release, real Linux full-dump,
all-format full-base-report, executed-history/root-cause or universal-proof gates.

## Problem and source review

The initial 2026-10-12 source review used commit
`50f3e9ce64bb21ec8e0805d51c3d1a038b618650`. These baseline contracts motivated
the extension. The extension and review corrections are committed at `b5d56b7`,
with source/tool/artifact identities bound by the later retry record:

1. [BAP projection](../../src/bap/projection.rs) derives effects from one
   instruction's typed BIL. A load contributes address dependencies and
   `memory:any`; it does not return a captured numeric value. A jump records a
   target only when its expression evaluates to a constant in that projection.
2. [Materialization](../../src/input/materialize.rs) reads captured instruction
   prefixes, follows supplied local successors and freezes the request.
   Its batch-preparer interface supplies instruction prefixes, not arbitrary
   captured data-table reads or cross-instruction value facts.
3. [Core instructions](../../src/model.rs) contain `targets` and `complete`.
   [The core model](../../Specs/Ariadne.tla) treats completeness as a trusted
   certificate. Native and Rust recovery consume these supplied facts; they do
   not discover the values of table entries.

The existing specification's `resolve(snapshot, VA, length)` describes byte
resolution. It is not an indirect-control-target resolver. No earlier dedicated
target-resolver design or API was found in the checked source, plans or relevant
Git history. The [Scanner follow-up](../../.agents/plans/scanner-partial-explanation.md)
requires an owning design/model extension before changing recovery semantics.

## Ownership and integration

The integration owner is `input::materialize`. Resolver logic resides in
`src/bap/target_resolution.rs`, because admitted BIL supplies its semantic operations.
It obtains captured reads through the existing immutable reader; it does not
open module paths, debugger caches or live process memory.

| Owner | Responsibility |
| --- | --- |
| [`src/bap/target_resolution.rs`](../../src/bap/target_resolution.rs) | Recognize admitted transfer expressions, propagate finite value constraints, enumerate targets and construct resolution receipts. |
| `src/input/address_space.rs` | Return captured bytes, all contributor offsets and explicit holes/conflicts. |
| `src/input/materialize.rs` | Coordinate bounded discovery and resolution, revisit affected sites, validate final certificates and freeze the expanded request. |
| `src/bap/core_adapter.rs`, `core_protocol.rs`, and native `capture.ml` | Bind and validate resolver receipts under a versioned capture profile before admitting augmented target sets. |
| Native `recovery.ml` and Rust `engine.rs` | Follow supplied indirect edges and retain an obligation when target coverage remains incomplete. |
| Input and investigation reports | Retain resolver evidence, premises and unresolved reasons alongside the original effects and query identity. |

The implementation reuses the BAP AST/admission and reader contracts. LLVM MC
remains an independent decode/control reference; unsupported effects retain
explicit gaps. The resolver does not scrape printed assembly.

## Initial finite profile

Use the existing AMD64 minidump snapshot interface. Portable Windows and Linux
fixtures exercise the shared arithmetic/read rules; the selected external
acceptance case is Windows and does not supply real Linux qualification.

The first profile supports:

- A near indirect jump through a pointer slot whose address is established by
  admitted constant or RIP-relative address computation.
- A near register jump formed by adding a known table base to a sign-extended
  little-endian 32-bit table entry, with a finite, justified unsigned index range.

The relative-table slice admits only the reviewed operations needed for the
case: register copies, RIP-relative base construction, the selected mask and
32-bit modular index adjustment, unsigned comparison/branch, indexed 32-bit
load, sign extension and 64-bit modular addition. Unsupported expressions,
unknown outputs, uncertain definitions or an opaque clobber stop the affected
inference. A recognizable opcode pattern alone is insufficient.

Keep indirect calls, general heap pointer chasing, writable or dynamically
changed dispatch structures, unbounded indices and general symbolic execution
outside this first delivery. Existing calls retain display-only call edges,
opaque effects and local summary edges.

## Semantic contract

The semantic operation is:

```text
resolve(snapshot, graph, site, before_site_value_facts, limits)
    -> target_set, coverage, receipt, premises, unresolved
```

The snapshot fixes artifact identity, captured bytes and semantic VAs. The graph
and admitted BIL identify incoming paths and register definitions. Value facts
are indexed by program point and machine width; they distinguish exact values,
finite sets/ranges and unknown values. They are derived from admitted semantics,
not copied from crash-time registers into earlier states.

For snapshot `S`, graph `G`, incoming-state abstraction `Gamma` and jump `p`,
write `S, G, Gamma |- p => (T, c) under Pi`. It means the resolver derives
candidate targets `T`, with a completeness flag `c` and explicit premises `Pi`.
The required soundness condition for `c = true` is:

```text
For every admitted state sigma reaching p under Gamma and Pi:
    evaluated_target(p, sigma) belongs to T.
```

`T` may overapproximate feasible destinations. Equality with the feasible set is
not required. When `c = false`, `T` is not an exhaustive bound: unresolved
alternatives remain explicit, including the possibility of additional targets.
Empty/incomplete does not mean that the jump has no destination.

All arithmetic follows the admitted machine widths. Register-bank/alias and
virtual-variable identity come from the typed BIL binding; textual names alone
do not identify definitions. Numeric VAs remain distinct from storage offsets.

### Captured memory premise

The reader owns immutable *captured* bytes. That fact alone does not prove that
an earlier runtime load saw the same bytes. The opt-in profile declares
`FrozenCapturedControlData`: the covered pointer/table loads are interpreted
using the named captured bytes for this analysis. The premise is visible in
resolver receipts, the semantic profile, native admission and reports.

Results are complete only relative to that stated model and its incoming-state
scope. They cannot claim historical table immutability. A PE read-only section
is corroborating metadata, not proof that every possible runtime write was
excluded. Without the declared policy or other independently admitted stability
evidence, retain the unknown runtime-content alternative and do not promote
captured-table candidates into an exhaustive target certificate.

### Captured table evaluation

For a known table base `B`, an admitted finite index domain `I` and this relative
encoding, compute:

```text
slot(i)   = u64(B + 4 * i)
offset(i) = sign_extend_32_to_64(read_little_endian_32(S, slot(i)))
target(i) = u64(B + offset(i))
T         = unique { target(i) : i belongs to I and its entry is readable }
```

`u64` denotes reduction modulo `2^64`, not checked host-language addition.
Mapping a read into capture storage uses checked offsets and bounded lengths.
An unsupported wrapped read is an explicit gap, not a fabricated value.
Conflicting overlaps never select an arbitrary contributor; agreeing overlaps
retain every contributor. Partial entries do not become zero-filled integers.

The pointer-slot form similarly evaluates an admitted slot address and reads
one little-endian 64-bit candidate under the captured-memory premise.

### Completeness and failure rules

Certify `Instruction.complete = true` only after checking:

1. Every admitted incoming path establishes the covered base and index facts;
   no alternative entry bypasses the guard or base definition.
2. Intervening writes, aliases, unsupported semantics and opaque calls do not
   invalidate the value facts. Unknown incoming definitions remain alternatives.
3. Every required entry is unambiguous and fully captured, with a bound receipt.
4. Widths, load encoding, sign extension and target arithmetic agree with admitted
   BIL and independent decoded facts.
5. The captured-memory policy and all other premises are declared in the query.
6. Enumeration and final certificate validation finish within all limits, on the
   final discovery graph rather than a stale earlier graph.

A guard constrains the states on its relevant outgoing edge; both structural
conditional edges remain in the graph. This is an inference about states that
reach the table load, not an assertion about the branch taken at crash time.

When any premise is missing, retain verified candidates with `complete = false`
where the profile permits a partial result, and retain an unresolved reason.
Malformed identities, forged receipts or invalid bindings are hard errors.
Missing bytes, unsupported semantics and budget exhaustion are conservative
resolution outcomes, not reasons to invent an edge or silently change backend.

A known target with unavailable instruction bytes remains a target. The reader
and core preserve its unavailable endpoint; the resolver must not filter it out
merely because decoding or capture at that destination fails.

## Discovery state and freezing

The preparation machine maintains:

```text
(captured snapshot, discovered sites/edges, value facts,
 pending starts, pending resolution sites, receipts, gaps, remaining budgets)
```

Start from the explicit entry points. Lift captured prefixes, derive permitted
value constraints, resolve eligible indirect sites, and queue newly discovered
local targets. Repeat until both worklists are empty or a declared bound stops
progress. Slice seeds never become additional roots.

New edges can expose new incoming states and invalidate an earlier guard/base
argument. Recompute affected facts and revalidate certificates. Retained target
edges grow conservatively; coverage certificates can be downgraded. Never keep
a stale `complete = true` merely because a site was resolved once. A retained
edge cannot establish the very incoming-state premise used to justify itself.

Freeze `AnalysisRequest` only after final validation. A stopped resolver may
freeze partial target sets with explicit residual obligations under the selected
profile. Ordinary preparation limits keep their existing error contracts; a new
resolver stop does not silently reinterpret those limits.

Both core analyzers consume the same frozen request. Existing fixed-request
core obligations are not discharged by mutating a running analyzer. Target
discovery is not a new root policy or a replacement for the core's recovery,
reaching-definition and slice transitions.

The abstraction preserves identity, machine-width facts, structural alternatives
and evidence. It erases historical ordering, concrete heap/object lifetime and
which candidate actually executed. The existing supplied-stateflow and supplied
LLVM IR paths remain separate.

## Usage and public API

Build the pinned lifter, LLVM reference decoder and native core as described in
[backend usage](bap-analysis-core-design.md#backend-usage). Rebuild the native
helper after this source change; an older helper lacking the profile is rejected.

```sh
cargo build --offline --locked --release --bin ariadne-minidump
python3 native/bap-core/build.py --output target/bap-core-native
./target/release/ariadne-minidump /path/to/original.dmp \
  --decoder-reference target/ariadne-llvm-mc \
  --entry 0x00007ff640079640 --seed 0x00007ff640079670 \
  --resolve-indirect-targets --max-artifact-bytes 2147483648 \
  --bap-core-response-timeout-ms 30000 \
  --explain-fault-address 0x00007ff640079670 --memory-access 0 \
  --explanation-only --format json
```

`--max-artifact-bytes` explicitly raises the default 256 MiB input ceiling, up to
2 GiB. `--bap-core-response-timeout-ms` declares a native response deadline in
`1..60000` ms, with the existing default of 10000 ms. A large completion can need
more than ten seconds in one response even when the total query completes. This
transport deadline is separate from resolver limits and the frozen CLI criterion.
`--target-resolution-limits limits.json` accepts a strict, complete
`Limits` object with fields from the table below and requires enabled mode.
Resolver mode currently rejects composition with frame paths, supplied stateflow
or memory refinement. Explanations and numeric fault assessments otherwise use
the same expanded graph. `--analysis-backend rust` selects the reference core;
native is the default. An explicit `--bap-core-dir` can select a task-owned helper.

The library entry point is
[`FileSnapshot::prepare_with_bap_target_resolution`](../../src/input/materialize.rs).
It accepts the ordinary query/decoder/BAP/preparation options plus resolver
`Limits`, returns a frozen `FilePreparedAnalysis`, and exposes its receipt via
`target_resolution()`. Final validation replays admitted BIL and every captured
read against a retained immutable snapshot view; large byte storage is shared
through `Arc`, rather than duplicated. Native admission independently checks
receipt shapes, source bindings, entry arithmetic, index enumeration, incoming
edge/root coverage and normalized target equality. The reader/BIL producer
remains trusted under the existing assurance boundary.

Enabled base JSON uses `ariadne-minidump-report-v2` and includes the separate
`ariadne.indirect-target-resolution/v1` receipt. Disabled reports retain v1.
Enabled query identities include the profile, memory premise and limits.
The new native profile interns definitions and reaching sets in a lossless
completion dictionary; strict indices/order/uniqueness and expanded size checks
precede expansion. Legacy profiles keep their completion encoding. Private
incoming/outgoing/delta/enabled caches preserve the smallest eligible `Propagate`
action and its full observable reaching state; they add no new analysis rule.
Dictionary lookup uses full integer-sequence hashes followed by exact equality;
FNV-1a uses two 32-bit halves under the pinned 64-bit SDK. Target-profile minor
heap allocation is 2,097,152 words. The host releases the native process after
fully receiving and checksum-validating the immutable envelope, then validates
and expands its content before returning any analysis. Completed states are
shared immutably with investigation; consuming an owned result still isolates
mutations. Claim/fact indexes and location-range lookup preserve report order.

## Evidence and product contract

A resolution receipt binds the artifact/query/semantic identities, site and
graph/value-fact revision, admitted dispatch/guard bytes and BIL hashes, memory
policy, table base and index domain, read spans/contributors, entry encodings,
per-entry derived targets, deduplicated target set, completeness argument,
unresolved alternatives and all exhausted limits.

Digest equality alone is not evidence validation. Admission must verify the
receipt's domains, arithmetic, coverage and bindings before accepting its
target certificate. Retain evidence for data-table reads separately from the
instruction-prefix read map and its current 15-byte site records.

Completeness validation keeps each reverse-path prefix as a separate context.
Every context must include every local predecessor alternative and, at an entry
point, its terminal root witness. Covering each graph edge somewhere across the
receipts is insufficient: successive branches can combine in additional ways.
For complete receipts, Rust and native admission replay ascending predecessor
pushes and LIFO pops over the proof tree. `max_values` bounds the whole pending
frontier, including siblings from earlier branches, rather than each node's
fanout. Partial receipts can combine valid witnesses retained across bounded
passes and do not assert one complete traversal within that frontier limit.

The CLI switch is `--resolve-indirect-targets`. The mode remains opt-in. Disabled mode preserves existing
queries and output. Enabled mode changes the query/semantic identity, extends
the capture profile and reports its premises explicitly. Do not add ad hoc
fields to strict existing report or native schemas; version the affected
contract and preserve legacy decoding/disabled-mode behavior.

Resolving one table does not establish `scope_closed` for the whole query or
change the meaning of investigation `partial`. Incoming RDX origins, other
indirects, opaque effects and unsupported control remain separate gaps.

## Limits and qualification

The first expanded capture trial exposed a native completion representation
larger than its existing 256 MiB cap and a slow Rust reference scan. The linked
R4 stage adds lossless definition/set interning for enabled-profile completion
and derived native/Rust flow caches, with a 16,777,216 expanded-link cap. This changes
representation/work, not targets, effects, reaching sets or the deterministic
action sequence; disabled native completion remains the original encoding.

The [R0 contract freeze](../../tests/bap/fixtures/target-resolution-limits.json)
sets the defaults below. Callers may tighten them; larger values are rejected.
Read caching charges unique slot/width reads, and target budgets count distinct
VAs. Work and cooperative time apply to each resolution pass; the separate
round cap bounds repeated discovery. This is not a hard real-time deadline. Existing open/preparation limits and
helper timeouts remain separate. Zero/exhausted limits retain conservative
outcomes and never bypass receipt/identity validation.

Admission checks retained evidence size, distinct destinations and unique
slot/width reads against the declared limits, including partial receipts. Work
and elapsed time bound each producer pass; revalidating shared proof prefixes
does not reconstruct the original elapsed time or charge retained paths as a new
producer pass. A new pass that cannot retain additional evidence within the
limits keeps the previously admitted witnesses and marks coverage incomplete.
The producer reserves space for that downgrade before accepting evidence.
Retention fallback checks target, read and evidence capacity explicitly. A
budget-fitting merge with invalid proof data propagates the validation error.


| Limit | Default / maximum |
| --- | ---: |
| `max_entries` | 4,096 |
| `max_targets` | 65,536 |
| `max_read_bytes` | 1,048,576 |
| `max_evidence_bytes` | 4,194,304 |
| `max_values` | 256 |
| `max_steps` | 262,144 |
| `max_path_steps` | 256 |
| `max_rounds` | 16 |
| `max_elapsed_ms` | 1,000 |

Qualification needs an independent integer/table oracle, negative semantic and
capture fixtures, finite TLA+ exploration, native/Rust parity and mutations of
real implementation seams. The oracle must not share production recognition
or enumeration helpers. Include stale-completeness, bypassed-guard, incomplete
table, sign-extension, endian, wrapping, unknown-clobber and identity mutants.
Expanded CFG/dataflow/slices require renewed exact-query evidence; old output
counts and backend performance results do not qualify this extension.

## Motivating Windows capture

On 2026-10-12, supplementary inspection used original dump
`dump_048B10C302A4460D8A1FC75088`, filename
`d6196d6a-0b59-4321-8b1e-4e52c43a050d.dmp`, size `1,305,482,568` bytes and
SHA-256 `5fea4ca614706fe0040ed3231efee0edf9ce4004a51d902bb581025b48bade08`.
Its module debug ID is `A7877FFB94F2DB3E4C4C44205044422E1`; the matching CDB
symbols identify `CallPrinter::VisitNoStackOverflowCheck` at entry
`0x00007ff640079640` and the fault at `0x00007ff640079670`.

The captured dispatch following that faulting load is:

```text
0x00007ff640079669  lea     r15, [rip + displacement]   ; B = 0x00007ff64791ef58
0x00007ff640079673  mov     eax, ebp
0x00007ff640079675  and     eax, 0x3f
0x00007ff640079678  add     eax, -2                    ; 32-bit modular result
0x00007ff64007967b  cmp     eax, 0x39
0x00007ff64007967e  ja      0x00007ff6400797e5          ; default edge retained
0x00007ff640079684  movsxd  rax, dword ptr [r15 + rax*4]
0x00007ff640079688  add     rax, r15
0x00007ff64007968b  jmp     rax
```

The unsigned guard's fallthrough admits indices `0..57`. The 232 captured table
bytes yield 45 distinct destinations from 58 entries. Three overlapping copies
agree; a separate CDB pass agrees with the parsed words, and all candidate
destination prefixes are captured. Entry 0 has offset `-126,503,947` and target
`0x00007ff64007a34d`. See the retained
[table record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-inspection.json),
[inspection checks](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-validation.json)
and [raw CDB log](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump048B-20261012/cdb-jump-table.log).

The original analysis used the existing remote 2026-10-10 BAP v3 runtime, with
only a diagnostic frontend's artifact cap raised from 256 MiB to 2 GiB.
Native/Rust explanations matched and remained partial: 329 decoded starts,
388 edges, 15 slice sites, an incoming-RDX boundary, this unresolved indirect
and three unsupported-control stops. The retained
[baseline summary](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump048B-20261012/baseline-summary.json)
records its query and runtime scope. It is not a build of the current checkout.

The supplementary target list did not modify that report, run resolver-enabled
recovery or certify the final incoming graph. It supplies the expected finite
table result for later qualification under declared premises. The actual crash
stopped at the earlier load; it does not select an executed switch target.

## Dated validation

These entries preserve their recorded sources, false acceptance flags and
unexercised clauses. The later [R6 refresh](#r6-qualification-refresh) supplies
current finite closure without refreshing any historical receipt.

### Implementation review follow-up

The implementation review found that bounded revalidation could retain old
target edges while replacing their witnesses with a smaller receipt, causing
final admission to fail instead of publishing a partial result. It also found
that edge-union coverage admitted missing combinations of incoming paths,
receipt admission did not enforce retained resource usage, a shared destination
was charged once per dispatch, and JSON rendering constructed the full report
twice. The fixed implementation checks path contexts and actual receipt budgets,
retains prior witnesses on bounded revalidation, counts destinations globally,
and reuses one JSON report value. Preparation modes now use a named private type,
and a private coordinator owns resolver convergence.

The initial mutation campaign omitted scale, guard, missing-entry,
unavailable-destination and premise/source-validation seams required by the
plan. Passing its nine selected mutants did not complete that R6 clause.
The revised runner defines fourteen Rust mutants and one native mutant, requires
each expected named runtime-test failure, and rejects compilation or unrelated
failures as evidence. Four observer tests and all mutation-anchor checks pass.
At that checkpoint, the [review-fix record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/review-fixes-20261013/report.json)
recorded 144 passing default tests, 46 passing core-only tests, format, Clippy,
layout and documentation checks. Four target-resolution native tests and the
fifteen-mutant campaign still required remote execution. Automatic approval
review had rejected the prepared source-archive transfer to the existing
`windows-dev` qualification workspace pending explicit payload/destination
authorization. The original record and raw evidence retain their identities.
The [later retry](#original-dump-retry-at-b5d56b7) resolved the pinned-native and
individual timing-sample clauses; the full mutation/replay aggregate remains open.
That first review-fix record is historical; the subsequent corrections below
have a separate source binding.

### Second review corrections

The next review found two remaining gaps: frontier admission counted only the
children of one proof node, and the mutation observer could count a prerequisite
failure in the expected test as detection. Frontier admission now reproduces
the producer's deterministic stack schedule. The successive-diamonds regression
rejects capacity two and accepts capacity three; a native source test also
checks predecessor ordering and internal roots. Invalid fitting retention
merges now fail explicitly instead of falling back to an older result.

Mutation evidence now uses `ariadne.target-resolution-mutations/v2`. Each Rust
mutant first runs the selected test with unmodified sources in its isolated
checkout. The native mutant first builds and tests an unmodified helper under
the same runtime configuration. A failing control stops the campaign before
mutation. Logs, source hashes and executable identities bind each control;
the native mutant additionally requires the expected `resolver target arithmetic`
diagnostic. The retained checker rechecks both the passing control and failure
cause. Older mutation records without controls cannot satisfy this contract.

The [correction record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/review-corrections-20261013/report.json)
binds fresh root/portable checks, nine observer/runner/checker tests and six
native source-level frontier cases. The latter compile the actual recovery and
capture modules with local OCaml 5.1 and do not qualify the pinned SDK/helper.
At the correction checkpoint, four pinned native tests and the complete
fifteen-mutant campaign were pending remote archive-transfer authorization.
The [later retry](#original-dump-retry-at-b5d56b7) completed the pinned-native tests
and met the individual timing criterion. Full mutation/replay qualification
remains pending.

### Original-dump retry at b5d56b7

The [retry record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/dump-retry-b5d56b7-20261013/report.json)
supersedes the preceding pinned-native and dump-rerun blockers. Anonymous Git
access verified the published commit before its source-only archive was sent
to the existing qualification workspace; the original dump stayed on that host.
The native helper was rebuilt after validating the existing pinned SDK inputs.
All 26 resolver tests passed, including the four previously unexercised native
cases, actual Windows/Linux synthetic captures and direct receipt controls.

The unchanged original 1,305,482,568-byte dump recovered all 45 independently
expected dispatch targets. Full states agree with each other and the historical
digest `4b5c6d947ac8622932e63d8731733e4cf328b7d7401302fcc68ffa0d2ffcf30c`:
3,977 decoded starts, 4,819 edges, a 392-site slice and 10,744,212 definition
links. The diagnostic driver changes only the public response timeout to 60 s;
the production CLI separately uses its explicit 30 s response deadline.

Native/Rust CLI samples completed in 38.61 s / 19.92 s, both below 60 s;
resolver passes were below 38 ms. Explanations are byte-identical with SHA-256
`e3ef3ce6c3e0b515fdcf00ab8e8b797e136712427fe34a9c06d83c35cb1d8ab0`.
The full core state is retained, while the explanation remains `Partial` and
`truncated=true` after its existing 32,768-origin-link limit. Incomplete dispatch
coverage, entry origins, unknown memory/call effects and 13 decode failures
remain explicit. Captured control data remains a stated premise; no executed
path or root cause follows. At that retry the fifteen-mutant campaign and full
revised-helper aggregate remained pending, so its acceptance flag was false.
The later [finite R6 refresh](#r6-qualification-refresh) closes those declared
clauses while preserving this historical result.

2026-10-12: design and plan written from source review and the separately retained
table inspection. Documentation checking passes with 88 connected documents,
87 context sections and 2,093 local links; diff hygiene passes. All eight copied
inspection/baseline artifacts retain their original byte hashes, including the
three table artifacts in the original inspection validation record.

Initial qualification run on 2026-10-13: R0–R5 were implemented, and the record
reported passing R6 correctness tiers for its declared finite corpus while the
native CLI timing criterion was unmet. The later implementation review found
that the mutation coverage was incomplete; the [retry](#original-dump-retry-at-b5d56b7)
subsequently met the individual timing criterion. The historical
[source-bound record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json)
retains Apalache typechecking, five TLC safety/fair-termination scenarios,
independent integer/table oracles, pinned-lifter Windows/Linux fixtures,
malformed-receipt controls, nine resolver and twelve core/stateflow mutations,
330 generated replay observations, root checks and the original capture query.

The original artifact is unchanged. Both cores agree on all 3,977 decoded
starts, 4,819 edges, 392 slice sites and 10,744,212 reaching-definition links;
the dispatch has 45 indirect edges. Its final certificate is incomplete because
expanded incoming routes include cycles/unknown states. The fault explanation
remains `Partial`, including the incoming-RDX boundary. Earlier native/Rust CLI samples of 46.87 s / 27.74 s are retained as historical
results before the later completion/ownership changes. At the initial
qualification run, default-runtime native samples completed with the explicitly
declared 30 s response deadline, but the local native sample was 68.34 s
(Rust: 51.06 s), and a contended Windows/WSL native sample was 123.79 s,
above 60 s. The Windows host was also running an unrelated Clang/Ninja build.
Those diagnostic runs with a longer library deadline established full-state
equality; they did not satisfy the production CLI timing gate. An experimental range
codec and GC configuration did not improve the gate and were discarded.
No latency distribution or packaged release qualification is claimed.

Failed oversized/slow completion trials, the interrupted earlier reference run
and failed replay prerequisites remain historical in the new record. Full base
report rendering in all formats, a real Linux full dump, general indirect-control
forms and packaged release qualification are not credited by this campaign.
Browser rendering remains a delivery convenience, separate from qualification.
