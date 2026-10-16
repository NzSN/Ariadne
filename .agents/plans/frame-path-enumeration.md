# Bounded frame-to-frame path enumeration

## Context and follow-up

**Status.** Source/API/CLI implementation and finite fixture/native checks added
on 2026-10-11 for the strict `returned_count < NP` question. Full model, mutation
and actual full-dump qualification remain pending.
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
profile. Model/mutation and real full-dump qualification require their own records.
Remote endpoints were unavailable at the initial checkpoint. The 2026-10-13
application used windows-dev successfully; model/mutation gates were not run
in that task and remain unexercised.

## Stages and ownership

| Stage | Work and owner | Acceptance |
| --- | --- | --- |
| F0 — contract | `Specs/AriadneFramePaths.tla`, cfg/check command, independent integer/graph fixtures under `tests/investigation/fixtures/`. Freeze before runtime changes. | Strict NP, activation identity, valid edges, loops and partial/no-path distinction. |
| F1 — frame evidence | `src/investigation/frame_unwind.rs`, `src/input/frame_paths.rs`: bounded captured PE32+ runtime tables, Windows AMD64 v1 unwind operations, stack return slots and raw context validity. | Independent capture fixtures, read provenance, malformed/unsupported/budget stops; no stack scanning or image fallback. |
| F2 — bounded paths | `src/investigation/frame_paths.rs`: bind completed queries, validate active direct calls, compose activation-scoped local graphs and enumerate deterministically. | Independent diamond/loop/recursive oracle, strict count, all work/byte/time boundaries and unchanged memory-writer universe. |
| F3 — product | `src/reports/frame_paths.rs`, `src/bin/ariadne-minidump.rs`: separate strict report and opt-in query. | CLI argument negatives, JSON/text/DOT, strict round trip and evidence tamper rejection. |
| F4 — validation | Root checks, isolated mutation campaign, finite pinned-native integration, remote model checking and externally retained full-dump evidence. | Distinguish exercised portable/fixture/native tiers from pending model/mutation/external capture/release acceptance. |

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
support is delivered; the caller graph and unavailable frame-path answer remain.

## Property-based extension

The [specification synchronization](specification-sync.md) updates F0's search
model to typed-edge DFS, scan counters and conservative partial results. The
original freeze and source/property receipts remain historical; the revised
model has a separate audit record and still requires remote qualification.

The [owning coverage contract](../../docs/Ariadne/investigation-design.md#frame-path-property-based-coverage)
now adds ten shrinking graph properties and three generated capture properties
under optional `property-tests`. Fixed-seed 128-case runs cover independent
Cartesian edge-word expectations, strict NP, resource/capacity behavior,
ordering, scope IDs, evidence/codec integrity, unwind arithmetic and register
validity. The [separate property record](../../evidence/Ariadne/frame-paths/property-validation.json)
binds this test-only extension; original model/oracle/native evidence stays
historical. Remote model/mutation and real full-dump clauses remain pending.
