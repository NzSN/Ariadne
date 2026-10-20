# Bounded frame-to-frame path enumeration

## Context and follow-up

**Status.** F0–F4 pass the [2026-10-20 finite qualification](../../evidence/Ariadne/frame-paths/20261020/README.md)
for the strict `returned_count < NP` question, declared Windows captured-unwind
profile and original physical-frame 1→0 query. The source/API/CLI and earlier
fixture/native checks retain their historical source identities.
The [2026-10-13 dump03958 application attempt](../../evidence/Ariadne/frame-paths/dump03958-20261013/report.md)
ran the CLI and an explicitly larger-budget API probe; both returned unavailable.

**Why this document exists.** The [owning investigation design](../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing)
relaxes historical-path reconstruction to a bounded list of structural alternatives
supported by validated frames and captured instruction evidence.

**What this document establishes.** Ordered contract, frame adapter, composition,
product and validation stages. Original local core effects, roots, reports and
memory-writer candidates remain the compatibility baseline.

**Where to go next.**

- [Selected contract](../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing)
  — strict output count, call-site endpoints and scope of completeness.
- [Input contract](../../docs/Ariadne/file-reader-design.md#decision-and-supported-scope)
  — capture-only reads, identity and explicit missing/conflicting bytes.
- [Formal-model guide](../../Specs/README.md) — modeled authority and independent
  conformance evidence.

**What remains unresolved.** General Windows/Linux unwinding, JIT/inline/tail-call
recovery, exception handlers and actual executed history are outside the initial
profile. The finite model/mutation and original full-dump clauses now have
separate source-bound qualification; broader release and capture claims do not.
Remote endpoints were unavailable at the initial checkpoint. The 2026-10-13
application used windows-dev successfully but did not exercise model/mutation
gates; those original receipts are preserved as historical evidence.

## Stages and ownership

| Stage | Work and owner | Acceptance |
| --- | --- | --- |
| F0 — contract | `Specs/AriadneFramePaths.tla`, cfg/check command, independent integer/graph fixtures under `tests/investigation/fixtures/`. Freeze before runtime changes. | Strict NP, activation identity, valid edges, loops and partial/no-path distinction. |
| F1 — frame evidence | `src/investigation/frame_unwind.rs`, `src/input/frame_paths.rs`: bounded captured PE32+ runtime tables, Windows AMD64 v1 unwind operations, stack return slots and raw context validity. | Independent capture fixtures, read provenance, malformed/unsupported/budget stops; no stack scanning or image fallback. |
| F2 — bounded paths | `src/investigation/frame_paths.rs`: bind completed queries, validate active direct calls, compose activation-scoped local graphs and enumerate deterministically. | Independent diamond/loop/recursive oracle, strict count, all work/byte/time boundaries and unchanged memory-writer universe. |
| F3 — product | `src/reports/frame_paths.rs`, `src/bin/ariadne-minidump.rs`: separate strict report and opt-in query. | CLI argument negatives, JSON/text/DOT, strict round trip and evidence tamper rejection. |
| F4 — validation | Root checks, isolated mutation campaign, finite pinned-native integration, remote model checking and externally retained full-dump evidence. | Record finite model/mutation/capture acceptance separately from general unwind, release and history claims. |

## Initial finite profile

Windows AMD64 only; thread/exception CONTEXT_CONTROL and valid optional INTEGER
groups; captured module header/table bytes; complete sorted nonoverlapping
`RUNTIME_FUNCTION` table; v1 ordinary-body unwind codes for PUSH_NONVOL,
ALLOC_SMALL/LARGE, SET_FPREG and SAVE_NONVOL/FAR. Unannotated leaf unwinding uses
the explicit Windows ABI/table-completeness premise. Unsupported epilogue/prologue,
chained/handler/machine-frame/XMM recipes stop explicitly. Caller lookup uses the
saved return address minus one; saved return PCs are not execution start anchors.

Direct active-call sites must be reached from an independently bound caller root,
have a captured decoded length whose continuation equals the saved return PC,
and target the younger activation's bound entry. Missing or ambiguous call-site
witnesses make the query unavailable. Separate per-frame preparation is opt-in
and explicit in the returned query identities; no old query is rewritten.

Initial defaults: 64 recovered frames, 4,096 runtime entries per module,
1 MiB unwind-read evidence, 8,192 graph nodes, 32,768 graph edges, 4,096 expanded
search states, 16,384 scanned edges, 256 steps per path, two visits per activation
node, 4 MiB frontier/output payload each, and a cooperative 1,000 ms search deadline.
`NP` must be positive and is independently limited to 4,097 at input admission.
Capacity is `NP - 1`; zero budgets never weaken identity/question validation.
The byte budgets concern owned evidence/frontier/output payload, not a process RSS
guarantee. Existing open/preparation bounds and helper timeouts remain separate.

## Validation procedure

Run portable independent oracle/source suites, fmt, default/core-only tests,
all-feature/all-target Clippy under the frozen read-only MirrorRust snapshot,
layout and documentation checks. Keep ignored native prerequisites visible.
Use task-owned remote outputs for model/mutation/large-capture campaigns.
Tests must reject a frame/graph from another snapshot, forged call transitions,
invalid edges/endpoints/counts, lost cyclic frontiers and exclusions inferred
from an incomplete path list. Preserve the existing memory-refinement evidence.

## Implementation checkpoint

This section records the initial 2026-10-11 checkpoint. The later
[F4 execution](#f4-post-s6-execution--2026-10-20) supplies the successor outcome
without refreshing these historical receipts.

F0 has a pre-runtime graph oracle/model freeze and a later syntax-bound revision;
source/configuration parsing passes, while remote state exploration is pending.
F1–F3 have implemented source, strict codecs and opt-in CLI. F4 records portable
root/fixture checks and finite native/Rust parity on diamond and recursive
synthetic captures. The [source-bound record](../../evidence/Ariadne/frame-paths/source-validation.json)
retains exact hashes and incomplete acceptance clauses.

Resume remotely with `bash Specs/check-frame-paths.sh` and
`python3 tools/check_frame_path_mutations.py --remote --output-dir
target/frame-path-mutations-current`. The independent non-building seam check is
`python3 tools/check_frame_path_mutations.py --check-seams`. A real full-dump
qualification needs externally retained captured artifacts, independent frame
inspection and named byte/query/tool identities; synthetic minidumps cannot
substitute for that tier.

On 2026-10-13, the [real-dump attempt](../../evidence/Ariadne/frame-paths/dump03958-20261013/report.md)
preserved the default runtime-table refusal and a distinct larger-budget public
API probe. Two physical frames were recovered in the latter; unsupported
caller vector semantics prevented active-call binding, while an XMM unwind
recipe stopped older recovery. Neither attempt enumerated paths or satisfies
the successful full-dump acceptance gate. Broader runtime/read budgets, vector
alignment-exception admission and XMM unwind support remain separate follow-up decisions.
The [later finite vector namespace extension](completed/bap-vector-registers.md) admits
XMM/YMM and its [source-bound retry](../../evidence/Ariadne/bap-vector-registers/20261013/report.md)
advances the semantic refusal to MOVAPS's alignment-exception branch. Namespace
support was delivered; the caller graph and unavailable frame-path answer remained
at that retry. The final F4 section below records the later result.

## Property-based extension

The [specification synchronization](specification-sync.md) updates F0's search
model to typed-edge DFS, scan counters and conservative partial results. The
original freeze and source/property receipts remain historical; the revised
model has a separate audit record. The
[2026-10-20 F4 qualification](#final-finite-qualification--2026-10-20)
subsequently supplies its finite remote checks; broader specification-sync S3
remains separate.

The [owning coverage contract](../../docs/Ariadne/investigation-design.md#frame-path-property-based-coverage)
now adds ten shrinking graph properties and three generated capture properties
under optional `property-tests`. Fixed-seed 128-case runs cover independent
Cartesian edge-word expectations, strict NP, resource/capacity behavior,
ordering, scope IDs, evidence/codec integrity, unwind arithmetic and register
validity. The [separate property record](../../evidence/Ariadne/frame-paths/property-validation.json)
binds this test-only extension; original model/oracle/native evidence stays
historical. The later F4 qualification exercises remote model/mutation checks
and the selected original full-dump question under separately recorded policies.


## F4 post-S6 execution — 2026-10-20

The authorized closure sequence passes within the
[2026-10-20 finite evidence scope](../../evidence/Ariadne/frame-paths/20261020/README.md).
Older qualification and unavailable attempts remain historical.
The [owning design](../../docs/Ariadne/investigation-design.md#f4-post-s6-qualification)
records the corresponding resource-policy extension and proof boundary.

| Step | Work | Acceptance |
| --- | --- | --- |
| Scope freeze | Original dump SHA `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`, thread 23668, physical 1→0, NP=10; exact source/helper/runtime/query/premise identities. | No additional roots, target pruning, alignment hypothesis or historical-value premise. All heavy work runs in task-owned remote Windows WSL. |
| Integration readiness | Explicit graph admission policy for the 10,367-site S6 pair; preserve default 8,192/32,768 legacy admission. Extend bound/report policy with strict replay and source binding. Refresh mutation runner with full current compile inputs, passing controls and isolated builds. | Legacy reports/default APIs retain their policy; explicit larger policy survives publication/replay, rejects cap violations and cannot hide identity/proof failures. |
| Correctness campaign | Current-source root/features, graph/unwind oracles/properties, six frame-path model configurations, native/Rust integration, compiled mutations and report tamper controls. | Positive observers pass; every credited mutant compiles and fails its intended observer. Resource exhaustion preserves uncertainty and writer alternatives. |
| Original capture | Independently inspect frames/call/PC and identities; prepare the unchanged S6 requests; compare completed backends, bind and enumerate with explicit policy. | At least one and fewer than ten independently checked structural paths; all source gaps/premises retained. Reports replay without helpers; no feasibility/history claim. |
| Evidence and delivery | Seal source/tool/corpus/command/result hashes; update canonical contracts and ledgers. | Fresh qualification is separate from retained results and broad release/unwind/ISA/universal-refinement claims. |

Initial selected graph/search policy: 16,384 nodes, 65,536 edges, 1,000,000
expanded states, 4,194,304 scans, 512 path nodes, two visits per activation node,
128 MiB frontier, 512 MiB formatted output and a 30-second cooperative search
limit. Capture/runtime/proof/preparation policies remain independently explicit.
Any changed policy or source receives a new recorded attempt and final freeze;
no failed attempt is overwritten or credited as success.


### Review and first capture feedback, 2026-10-20

The review identified and corrected three acceptance-boundary gaps: saved v7
reports now require independent host graph caps; original replay requires a
trusted expected report hash plus exact artifact/thread/frame/NP checks; and
mutation success is published atomically only after complete source-inventory
stability. A narrow reports-only v7 guard-profile rejection preserves proof
requirements across feature selections. These corrections still require their
remote runtime gates. Legacy generic-v1 premise behavior remains historical.

The first raw original attempt preserves both S6 normalized requests and full
native/Rust states, but DFS exhausts 1,000,000 states with zero paths under the
initial 512-node path policy. It reports partial coverage and remains a failed
positive gate. A separate Python topology diagnostic finds the 22-edge route
with a 32-node limit after 35 expansions. The next explicitly selected path
policy therefore uses 32 nodes, retaining the other limits and two visits.
This bounds displayed alternatives; source graphs, unknowns, roots and semantic
premises remain intact. Depth-restricted enumeration must remain partial.

### Final finite qualification — 2026-10-20

The source2 implementation capsule contains 1,070 files and has SHA-256
`ed7b76ef6b9ac6f32e66c570d0234780861afe123fe0786916b33d7eba1bb84d`.
The [qualification record](../../evidence/Ariadne/frame-paths/20261020/README.md)
binds all source/tool/capture/request identities and passing commands. Six finite
model configurations and typechecking pass. Root/feature/property/native and
codec controls: `334 / 64 / 77 / 202 default/core/reports/BAP tests; 10 graph and 3 unwind properties; 7 native/legacy tests`. Compiled mutations with passing
controls: `6 compiled mutations rejected after 6 passing controls`. Reports-only proof-profile admission,
independent saved-decoder graph caps and foreign-report original-replay rejection
have their own recorded controls.

The unchanged original S6 requests and full native/Rust states support
one independently checked structural path for dump SHA
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`,
thread 23668, physical frames 1→0 and NP=10. Final path policy is 32 nodes and two
visits per activation node; graph admission remains 16,384 nodes/65,536 edges,
with the other explicitly recorded limits retained. The listing stays partial
under its depth restriction. No unknown alignment/target, root, source graph,
semantic premise or possible memory writer is removed by that restriction.

The initial 512-node, million-search-state, zero-path attempt remains a failed
positive gate. Successful report replay uses independent host caps and trusted
expected report identity. Archive SHA-256: `42feba66c6445de674ddaf0aa7f3ec3d63ca845a5c117c45d02c9e8352eb40ff`.
This closes F4 only within the recorded finite model/mutation/original-capture
profile; general unwind support, full path feasibility/history, release and
universal refinement remain outside the acceptance claim.
