# BAP-owned analysis: Stage 2 contract

## Context and follow-up

**Status.** Native recovery, reaching definitions, slicing, finite stateflow,
generated replay and capture-bound integration are implemented. The CLI selects
BAP analysis by default and retains explicit Rust rollback. The
[qualification guide](bap-core-qualification.md) records acceptance for the exact
sources; the [execution plan](../../Plans/bap-stage2-implementation.md) records delivery.

**Why this document exists.** The [BAP assessment](bap-core-refactor-assessment.md)
and [integration plan](../../Plans/bap-integration.md#stage-2-bap-analysis-core)
require moving actual analysis state and computation into BAP-owned passes.

**What this document establishes.** Ownership, immutable inputs, actions, full
observations, BIR attribution, error semantics and the correspondence to the
authoritative TLA+ machines. Contract validation does not prove a pass correct.

**Where to go next.**

- [P4 bounded completion transport plan](../../Plans/bap-completion-pages.md) —
  adds action batches and paged final-result retrieval while retaining the
  per-frame budget, complete observations and unchanged core transitions.
- [Qualification guide](bap-core-qualification.md) — current aggregate decision and adoption evidence.

- [Complete Stage 2 execution plan](../../Plans/bap-stage2-implementation.md) — implements and qualifies A1–A6 on the completed A0 foundation.

- [OCaml foundation qualification plan](../../Plans/bap-ocaml-qualification.md) — closes the remaining A0 SDK, helper-state and transport clauses before A1.

- [A0 implementation plan](../../Plans/bap-stage2-a0.md) — scopes this first stage
  and its executable contract/capability checks.
- [Core model](../../Specs/Ariadne.tla) — defines recovery, definitions and slicing.
- [Stateflow model](../../Specs/AriadneMachineState.tla) — defines finite relational
  propagation and feasibility on a frozen structural graph.
- [Rust correspondence](../implementation.md) — provides the reference implementation.

**What remains unresolved.** Stage 2 acceptance is valid only for the passing
aggregate record and its verified source/tool archive. BAP lifting remains trusted; finite
model replay is not a universal refinement or ISA-step proof. Richer BIR
transformations are separate future contracts.
The recovered Scanner query exceeds the ordinary per-action 8 MiB response
budget. The implemented [P4 transport extension](../../Plans/bap-completion-pages.md)
completes it through bounded batches/pages without dropping definitions or raising
that frame limit. The [selected real-capture replacement](real-capture-repin-79938.md)
qualifies P4 source/fixture and native-default gates remotely. The
[user decision](../../evidence/Ariadne/bap-admission/p4-acceptance-20261010.json)
accepts that scope with remaining historical real-Linux clauses excluded; their
coverage and six output hashes remain unexercised.

For the wider context, see the [documentation map](../documentation-map.md).

## Ownership and implementation selection

Rust owns capture parsing, explicit byte trust policy, transport validation,
question construction and report validation. The BAP module owns its immutable
input, BIR attribution, typed graph relation and mutable analysis state. OCaml
passes must implement the actual transitions. Rust's existing `Analyzer` and
`machine_state::Analyzer` remain separate reference/rollback implementations.
Neither an observer nor a transport adapter may call the Rust solver to construct
the purported BAP state.

The first implementation target is an isolated OCaml executable linked against
a pinned BAP SDK and run as one process per snapshot/query/family. Its `Project`
is constructed from an empty target plus explicitly admitted instruction terms;
default image loading, recursive discovery and speculative scans are forbidden.
The packaged Stage 1 C runtime is retained for lifting and capability probes.
The C header exposes terms/graphs, but lacks `Project.empty`/custom-input and
custom typed-storage constructors available in the reviewed OCaml interface.
It is not a sufficient SDK for this design's custom OCaml passes.

Do not load a plugin built by either installed OCaml compiler into the packaged
runtime without verified compiler/library compatibility. The isolated pinned SDK/executable now freezes source/compiler/library
identities and exercises startup, real Init/Visit state changes and process
cleanup. The [qualification record](bap-ocaml-qualification.md) separately decides
whether every required A0 gate passed before complete A1 recovery.
No user opam switch is modified by A0. The native capability probe is explicitly
not a production analysis helper or an OCaml-pass qualification.

## Immutable requests and finite domains

Two family names are fixed: `recovery` and `stateflow`. Supplied LLVM IR remains
its own existing analysis path. `snapshot` is the exact opaque nonempty snapshot
identity; `query` is a SHA-256 of canonical, length-delimited request data;
`session` is a fresh orchestration token, never a BIR TID or a machine address.
All wire addresses are lowercase, full-width `0x` plus 16 hexadecimal digits.
Map rows and sets have unique keys/elements; no narrowing to signed OCaml `int`.
Use unsigned 64-bit keys (or exact bitvectors with unsigned ordering) in the pass.
String state identifiers preserve distinct identities even for equal valuations.

Canonical query construction uses UTF-8 JSON with recursively sorted object
keys, no insignificant whitespace and unescaped Unicode. Validated set/map-row
arrays are sorted by their canonical JSON encodings; duplicate elements/keys
are rejected before hashing. Concatenate the domain separator
`ariadne.bap-core-query/v1` plus a zero byte, then the UTF-8 byte strings for
snapshot, family, input profile and canonical input, each preceded by its
unsigned 64-bit big-endian byte length. SHA-256 of those bytes is `query`.
This includes semantic evidence identities carried in the immutable input;
process paths and previous/expected results are not input fields. The Rust bootstrap caller constructs this query digest; the helper validates the
complete recovery payload and binds each exchange to the launch identities.

The initial replay profile is `normalized-fixed-input/v1`. It carries no finished
graph, reaching definitions, expected trace, cached observations or prior result.
Its full instruction domain is supplied as immutable premises, as in the model.
Production admission additionally requires the Stage 1 evidence for every site.
A1 may use a bounded reader bridge for lazy preparation; read exchanges are
transport events and cannot masquerade as model actions or mutate observations.
Candidate domains are frozen before model initialization. Extending them requires
a new request/session; A0 does not redefine the current fixed-input model.

| Family | Required immutable input / model constants |
| --- | --- |
| Recovery | `snapshot`, `addresses`, `locations`, `entry_points`, `slice_seeds`, `input_kind`, `captured`, `file_backed`, `trusted_fallback`, total `instructions` rows with `kind`, `fall`, `targets`, `targets_complete`, `uses`, `may_defs`, `must_defs`; `decodable` |
| Stateflow | `snapshot`, `nodes`, `entry_points`, `locations`, total `value_domain`, `state_ids`, total `valuation` and `state_status`, total `initial_states`, immutable typed `structural_edges`, total `uses`/`may_defs`/`must_defs`, `state_steps`, `terminal_transitions`, `complete_sites`, `adapter_obligations` |

Input validation preserves the exact `InputContract` of each model, including
nonempty domains where required, targets inside the finite universe, total maps,
`must_defs` contained in `may_defs`, continuation cardinalities, running entry
states, transition/frame consistency and terminal-outcome status. The core's
general file-fallback contract remains representable for reference replay;
the production minidump profile requires empty file-backed/trusted-fallback sets.
Byte evidence retains exact consumed bytes, VA, capture contributors and hashes;
holes/conflicts remain failed premises, never zero-filled or repaired from a PE.

## Versioned interface and lifecycle

The proposed stream is UTF-8 JSON Lines, schema `ariadne.bap-core/v1`, one request
and exactly one response at a time. Reject duplicate JSON keys, unknown fields,
nonfinite numbers, noncanonical identities and frames over 8 MiB before admission.
The implementation must also enforce per-request node/edge/location/state/term
budgets before allocation. Both families have native admission. The production
`captured-fixed-input/v1` recovery profile wraps `normalized` premises and a
`capture` object containing snapshot, artifact/query digests, semantic profile
and a total site map. Site rows bind canonical VA, consumed bytes, captured
availability, semantic status/helper/runtime/AST/projection identities and reader
spans/contributors. Rust verifies the prepared query and reads; native admission
checks the capture-only profile and evidence coverage before creating terms.

Every request contains `schema`, `session`, `snapshot`, `query`, `family`,
monotonically increasing `sequence`, `operation` and `payload`. Every response
echoes the complete identity and sequence, with either typed success or error.
The success envelope includes `generation`, `action_index`, `changed` and the
complete family observation when requested. Protocol failures poison the session;
terminate/reap it and discard unpublished results. A rejected semantic action
leaves every state field, action index and generation unchanged.

| Operation | Effect and restrictions |
| --- | --- |
| `initialize` | Sequence zero only, admits one immutable family input and returns actual `Init` observation at action index zero. Reinitialization in an active process is rejected. |
| `advance` | Payload selects exactly one named model action and its address when applicable. Check phase, guard and deterministic selected address before changing state. Exactly one successful action increments the action index. |
| `observe` | Read-only serialization of current pass state; repeated reads are equal. It cannot advance, normalize away differences or consult expected/reference results. |
| `finish` | Returns an owned result only from `done`; it does not secretly execute remaining actions. Per-action replay retains this operation. |
| `reset` | Acknowledges shutdown and closes the helper process. A fresh process/session is required even for the same VA set; OCaml knowledge-base caches never cross snapshots. |
| `run-batch` | Recovery completion only: runs at most 64 existing scheduled actions and reports progress; the one-million-action limit remains. |
| `result-page` | Retrieves ordered hex pages of one immutable final envelope, at most 256 KiB decoded bytes each and 256 MiB total. No partial result is published. |
| `result-close` | Requires complete transfer, acknowledges the bound result and exits cleanly. The client validates identities, counters, checksum, final state and exit before publication. |

The runtime handshake must report helper/pass ABI, pinned SDK/compiler/library
identities, supported family/profile, implemented operations and limits. Negotiated
capabilities cannot advertise A2/A3 algorithms before their validation exists.
The transport sequence counts requests; the action index counts real model
actions. A trace hash or index alone does not prove that the observed state is
native: A4 replay and A5 mutations must exercise the actual pass implementation.

## Recovery state and transitions

The complete observation is the nine-field tuple in `Specs/Ariadne.tla`:
`phase`, `pending`, `visited`, `decoded`, total `provenance`, typed `edges`,
`obligations`, total `reaching`, and `slice`. Wire map rows use explicit address
keys, including empty values for every candidate. No field is inferred from a
previous response. A result additionally contains `snapshot` and
`missing_slice_seeds = slice_seeds - decoded`.

| Action | Guard, update and mapping |
| --- | --- |
| Init | `phase=recover`, `pending=EntryPoints`; empty visited/decoded/edges/obligations/slice; all provenance unavailable and all reaching sets empty. |
| Visit(a) | Least pending unsigned VA; mark visited/remove pending. Successful admission adds the instruction, byte source, all typed edges/obligations and only local successors excluding visited. Failure records unavailable/decode-failed without a node. Other fields unchanged. |
| FinishRecovery | Only when pending is empty; change phase to dataflow and freeze graph/byte facts. Internal indexes are invisible. |
| Propagate(a) | Least decoded VA with `Incoming(a)` not contained in `reaching[a]`; union its incoming facts into that row only. |
| FinishDataflow | Every decoded row satisfies its fixed-point equation; phase becomes slice, seeded by `SliceSeeds ∩ decoded`. |
| ExpandSlice | Add one dependency layer, simultaneously, from instruction origins reaching locations used at current slice members. |
| FinishSlice | Only at slice closure; phase becomes done. Outstanding obligations are retained in a completed partial analysis. |

`Out(a) = {d in reaching[a] : d.loc not in must_defs[a]} ∪ Gen(a)`.
`Incoming(a)` unions unknown entry origins at roots with `Out` from decoded
local predecessors. Calls retain their `call` edges, but only `summary` edges
carry local recovery/dataflow. A root with a back edge retains entry and loop
origins. Possible writes never remove old definitions. An entry origin is not
an instruction producer and does not grow the backward slice.

The specification permits any enabled action. The adapter implements the same
lowest-VA schedule as the Rust reference for comparable full traces. Asking for
another enabled address is a rejected action under this deterministic profile.
No action is enabled at done. Finish/observe remain read-only there.

## Stateflow state and transitions

The actual mutable tuple is `phase` and total `states_at`, initialized from the
total `InitialStates` map. The observation also serializes derived views:
immutable structural edges, feasible/provably-infeasible/unknown edges, reached
terminal transitions, not-reached nodes and obligations. Derive them directly
from the current OCaml state and fixed input, not from the Rust reference.

`Propagate(a)` chooses the least node whose incoming state IDs grow, unioning
initial IDs with `after` IDs from steps whose `before` ID reached their source.
`FinishStateflow` requires every node's equation to be equal and changes only
phase. Infeasible edges are empty before done; at done, absence is infeasible
only for a reached source in `CompleteSites`. All other absent structural edges
remain unknown. Structural edges are never deleted. Reached fault/return/stop
transitions remain terminal results, not ordinary successor states. Catalogue
IDs with equal valuations remain distinct and running-only propagation is kept.

## BIR attribution and graph preservation

Maintain an explicit registry keyed by session-local TID: term class, origin
kind, source instruction identity or null, generation and derivation parents.
Every machine-origin term maps to the exact snapshot/VA/consumed-byte evidence;
one instruction may own multiple BIR blocks/definitions/jumps. Phi/temporary or
helper-generated terms are `synthetic`, have no invented VA/bytes, and retain
parent attribution. An unavailable target is a typed graph endpoint, not an
invented BIR instruction. Native TID allocation order is not a replay observable.

The authoritative analysis edge relation is a set of `(src VA, dst VA, kind)`.
Several kinds may connect the same pair. Treat BAP's BIR CFG as a structural view
unless its parallel-edge semantics are independently proven equivalent. A call
and a summary, or taken and fallthrough edges, must never collapse into one fact.
No SSA conversion, block coalescing or dead-code elimination is enabled by default.
Any future transformation must preserve registry attribution and model observables.

The pinned native probe actually inserted two TID-graph edges with distinct
labels but identical endpoints: only one remained. It also observed immutable
graph versions with 0/1/2 nodes and full `0xfffffffffffffff0` address attribution.
These are capability observations, not model actions. The independent typed
edge relation is therefore required, rather than relying on this TID graph to
encode the model's parallel edge kinds.

## Acceptance boundaries

A0's executable envelope/attribution checks and native term/graph probe establish
contract and runtime-facility evidence only. They do not establish a migrated
solver. A1 implements reader-scoped recovery; A2 adds genuine origin/slice passes;
A3 adds finite stateflow; A4 binds real helper actions to generated replay; A5
tests mutations in those passes and connects reports; A6 qualifies adoption.
The already accepted unlimited timing policy still requires valid measured
workload evidence; older Rust results do not qualify the new implementation.

## Implemented ABI 2 wire details

The standalone helper advertises `recovery` and `stateflow` families and both
fixed-input profiles. Recovery supports all six model actions; stateflow supports
Propagate and FinishStateflow. `step` chooses one actual native enabled action;
its optional action name must match that selection. `advance` additionally
checks the supplied address. `observe`, `finish` and `reset` are read-only;
finish requires done and reset acknowledges before a clean process exit.
The frame limit is 8 MiB; address, location and potential typed-edge sets are
bounded at 65,536 entries. JSON nesting is bounded at 64 levels.
Production recovery completion uses the batch/page extension above. Generated
per-action replay and stateflow retain their original observation path. The
transport checksum checks consistency; existing SHA-256 request/helper identities
retain their trust roles. Overflow, malformed pages and failed exits poison the
session without automatic Rust fallback.

Instruction map rows contain `address` plus the instruction fields above.
Provenance rows are `{address, source}`; reaching rows are
`{address, definitions}`. Both maps include every candidate, including empty
reaching sets. Definition rows carry `loc`, `site` and `origin`. The nine state fields remain separate from the response's
`attribution` rows. Generation is one for this one-process/one-query lifetime;
request sequence and model action index advance independently.

The OCaml record owns recovery state and its reader-scoped BAP project. A successful
Visit adds a block and subroutine term attributed to the admitted machine VA;
these are normalized-summary attribution terms, not a new instruction lift.
The program term has synthetic ancestry without an invented VA. Term addresses
and snapshot attributes are read back from BAP values. Captured-profile block
and subroutine terms also store and return the admitted capture-evidence row.
The Rust facade checks term uniqueness, decoded-site coverage, captured evidence,
synthetic ancestry and identity before exposing a completed result. A sealed
`AnalysisView` lets investigations and stateflow preparation reuse that result;
it does not construct or execute a Rust reference analyzer. No filename or image loader
is supplied to the helper. The packaged Stage 1 lifter remains separate.

The SDK uses OCaml 4.12.1 and the full BAP revision in
[`sdk.lock.json`](../../native/bap-core/sdk.lock.json), with a frozen opam export.
The source revision matches the selected Stage 1 source archive; binary/plugin
ABI equivalence to the packaged runtime is not claimed.
