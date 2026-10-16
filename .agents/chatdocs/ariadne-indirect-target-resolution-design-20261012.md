# Captured indirect control target resolution

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

## Context and follow-up

**Status.** Proposed on 2026-10-12. The design and linked R0–R6 execution plan
are written; resolver implementation, model checking and qualification are
pending. Supplementary inspection of one Windows dump establishes a captured
switch table, not an implemented resolver or its completeness certificate.

**Why this document exists.** The [input design](../../docs/Ariadne/file-reader-design.md#why-a-reader-alone-is-insufficient)
discovers instruction starts from supplied control facts, while the
[BAP design](../../docs/Ariadne/bap-analysis-core-design.md) leaves indirect-target enumeration
outside delivery. A full dump can contain a table and its destination bytes
without the current pipeline connecting them to an indirect jump.

**What this document establishes.** The proposed owner, finite supported forms,
snapshot-relative target semantics, evidence and completeness contracts,
bounded discovery integration and qualification requirements.

**Where to go next.**

- [R0–R6 implementation plan](../plans/indirect-target-resolution.md) —
  stage ownership, acceptance gates and execution order for this design.
- [Core model](../../Specs/Ariadne.tla) and [formal-model guide](../../Specs/README.md)
  — existing target-set certificate and authority for the required extension.
- [Source ownership](../../docs/Ariadne/architecture.md#ownership-and-process-boundaries) —
  preparation freezes inputs before native or Rust analysis.
- [Inspection evidence](../../evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-inspection.json)
  — the captured table that motivates the first relative-table profile.

**What remains unresolved.** No resolver API, CLI mode, discovery fixed point,
receipt validator or resolver model is implemented. General value-set analysis,
mutable heap tables, arbitrary indirect calls, JIT/self-modifying code and
executed history remain outside the initial profile. Completeness requires
validated incoming-state coverage and an explicit captured-memory premise.

## Problem and source review

Source review uses local commit `50f3e9ce64bb21ec8e0805d51c3d1a038b618650`.
The existing pipeline has three relevant contracts:

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
Git history. The [Scanner follow-up](../plans/scanner-partial-explanation.md)
requires an owning design/model extension before changing recovery semantics.

## Ownership and integration

The integration owner is `input::materialize`. Proposed internal resolver logic
belongs under `src/bap/`, because admitted BIL supplies its semantic operations.
It obtains captured reads through the existing immutable reader; it does not
open module paths, debugger caches or live process memory.

| Owner | Proposed responsibility |
| --- | --- |
| `src/bap/target_resolution.rs`, new | Recognize admitted transfer expressions, propagate finite value constraints, enumerate targets and construct resolution receipts. |
| `src/input/address_space.rs` | Return captured bytes, all contributor offsets and explicit holes/conflicts. |
| `src/input/materialize.rs` | Coordinate bounded discovery and resolution, revisit affected sites, validate final certificates and freeze the expanded request. |
| `src/bap/core_adapter.rs`, `core_protocol.rs`, and native `capture.ml` | Bind and validate resolver receipts under a versioned capture profile before admitting augmented target sets. |
| Native `recovery.ml` and Rust `engine.rs` | Follow supplied indirect edges and retain an obligation when target coverage remains incomplete. |
| Input and investigation reports | Retain resolver evidence, premises and unresolved reasons alongside the original effects and query identity. |

New modules and APIs are proposals. Reuse the existing BAP AST/admission and
reader contracts; do not duplicate instruction effects or introduce a second
decoder. LLVM MC remains an independent decode/control reference.

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

The proposed operation is:

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
an earlier runtime load saw the same bytes. The proposed opt-in profile declares
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

The proposed preparation machine maintains:

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

The proposed CLI switch is `--resolve-indirect-targets`; it does not exist yet.
Keep the mode opt-in through qualification. Disabled mode preserves existing
queries and output. Enabled mode changes the query/semantic identity, extends
the capture profile and reports its premises explicitly. Do not add ad hoc
fields to strict existing report or native schemas; version the affected
contract and preserve legacy decoding/disabled-mode behavior.

Resolving one table does not establish `scope_closed` for the whole query or
change the meaning of investigation `partial`. Incoming RDX origins, other
indirects, opaque effects and unsupported control remain separate gaps.

## Limits and qualification

R0 must freeze defaults and performance criteria before runtime implementation.
Separately bound table entries, candidate targets, data-read bytes, retained
evidence, expression/value alternatives, transfer work, graph growth, resolution
revisits and cooperative elapsed time. Existing open/preparation limits and
helper timeouts remain separate. Zero/exhausted limits retain conservative
outcomes and never bypass receipt/identity validation.

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
[table record](../../evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-inspection.json),
[inspection checks](../../evidence/Ariadne/indirect-target-resolution/dump048B-20261012/jump-table-validation.json)
and [raw CDB log](../../evidence/Ariadne/indirect-target-resolution/dump048B-20261012/cdb-jump-table.log).

The original analysis used the existing remote 2026-10-10 BAP v3 runtime, with
only a diagnostic frontend's artifact cap raised from 256 MiB to 2 GiB.
Native/Rust explanations matched and remained partial: 329 decoded starts,
388 edges, 15 slice sites, an incoming-RDX boundary, this unresolved indirect
and three unsupported-control stops. The retained
[baseline summary](../../evidence/Ariadne/indirect-target-resolution/dump048B-20261012/baseline-summary.json)
records its query and runtime scope. It is not a build of the current checkout.

The supplementary target list did not modify that report, run resolver-enabled
recovery or certify the final incoming graph. It supplies the expected finite
table result for later qualification under declared premises. The actual crash
stopped at the earlier load; it does not select an executed switch target.

## Dated validation

2026-10-12: design and plan written from source review and the separately retained
table inspection. Documentation checking passes with 88 connected documents,
87 context sections and 2,093 local links; diff hygiene passes. All eight copied
inspection/baseline artifacts retain their original byte hashes, including the
three table artifacts in the original inspection validation record.

Resolver implementation/model/runtime/release acceptance remain pending. Browser
rendering is a delivery convenience, not a build, model exploration or resolver
qualification result.
