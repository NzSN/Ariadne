# Frame corridors and cycle summaries: Stage 5.2

## Context and follow-up

**Status.** FC0–FC6 pass the declared finite consumer profile, with
[remote qualification on 2026-10-19](../../evidence/Ariadne/frame-question/20261019/README.md) and both independently checked
capture applications. The [2026-10-18 local record](../../evidence/Ariadne/frame-connections/20261018/README.md)
retains its original scope. Broader release acceptance remains separate.

**Why this document exists.** Section 5's second [recommendation](../chatdocs/ariadne-frame-to-frame-recommendation-20261016.html#order)
asks for represented reachability, cycles and useful examples over
[Stage 5.1 sources](frame-structure-report.md), without completed caller dataflow.

**What this document establishes.** The implemented bounded consumer and its
finite acceptance ledger. Stage 5.2 is distinct from Stage 5.1's SF5.2 mutation task.
The [canonical contract](../../docs/Ariadne/investigation-design.md#structural-corridors-and-cycle-summaries)
owns graph domains, statuses, policies, identities and replay.

**Where to go next.** Read the canonical contract, [new evidence](../../evidence/Ariadne/frame-question/20261019/README.md),
[complete section-5 program](frame-question-investigation.md),
[structural source contract](../../docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
and [model guide](../../Specs/README.md). Caller [S6](caller-semantic-coverage.md)
and frame-path [F4](frame-path-enumeration.md) retain separate gates.

**What remains unresolved.** Unknown continuations can reconnect; structural examples do not establish feasibility, history, loop invariants or writer exclusion. Broad release and universal refinement remain unqualified. The original large consumer application retains its exact saved source. The stale-decoder raw refresh is historical; [caller S6](caller-semantic-coverage.md) separately restores original coverage/full-state parity with the current helper.

## Frozen direction and implemented interface

Use the owning design as the single contract. Freeze its exact wire/interface
details before runtime acceptance rather than adding another feature design.

| Decision | Required outcome |
| --- | --- |
| Source | Privately validated `BoundFrameStructure`; never raw caller-supplied graph JSON or a candidate request. |
| Computation | Read-only activation-qualified graph composition, forward/reverse reachability, iterative SCC partition and separately bounded example search. |
| Range/anchors | Inherit the selected `N:M` and existing captured active-call anchor policy. Preserve auxiliary witnesses without expanding route scope. |
| Unknowns | Retain every source gap; annotate corridor/forward-reachable/outside/unclassified attachment where known. Unknown continuations outside the corridor can reconnect. |
| Negative meaning | Only `absent_in_represented_graph` after completed graph/traversal work; no negative program-reachability claim. |
| SCC meaning | Exact partition and condensation of the declared represented graph; no semantic iteration/termination invariant. |
| Examples | Default NP=2 allows one shortest represented route. Optional bounded edge-detour BFS attempts produce selected additional loop-free alternatives. Always fewer than positive NP; never all-path enumeration. |
| Identity | Logical source-facts/assessment identity in investigation, separate enclosing publication binding in reports; preserve old source IDs and all conditional hypotheses. |
| Product | `ariadne.frame-connections/v1`, JSON/text/DOT and opt-in `--frame-connections N:M`; no default-route change or native full completion. |
| Replay | Embed one unchanged structural source report, validate/replay it under host policy, then recompute the new assessment. Invalid evidence is rejected; verification exhaustion constructs no trusted result. |

Main interface:

```text
summarize_frame_connections(structure, positive example_count_bound, limits)
    -> BoundFrameConnections
```

Names and transport fields are implemented in the source paths below. Default
NP and algorithm restrictions belong in the serialized query;
independent host limits cannot be raised by producer declarations.

## Stage ledger and file ownership

The owner column describes responsibilities, not a request to spawn workers.
Implementers are not alone in the repository: preserve unrelated edits and
coordinate shared exports. Each stage's dependencies are evidence gates.

| Stage | Owner and paths | Dependency | Exit evidence | Status |
| --- | --- | --- | --- | --- |
| FC0 — contract and authority | Contract/model owner: canonical investigation section, this ledger, `Specs/AriadneFrameConnections.tla`, finite configurations/checker and literal expectations under `tests/investigation/fixtures/`. | Existing Stage 5.1 contracts and source/corpus inventory | Graph domain, identity, active-anchor scope, status values, finite host defaults, NP and independent expected results fixed before runtime acceptance. | Implemented; local checks pass |
| FC1 — source and composition | Investigation owner: `src/investigation/frame_connections.rs`, narrowly shared structural identity/active-link helpers, exports and focused `tests/investigation/`. | FC0 | Input remains byte/fact-identical; eligible graph, typed frontiers and active-call transitions match independent controls; no completed binder or 8,192-node clamp. | Implemented; local checks pass |
| FC2 — corridor and SCCs | Graph owner: private implementation inside the new module and focused tests. | FC1 | Forward/reverse sets, exact represented corridor, iterative SCC partition/quotient and unknown-reconnect annotations match independent oracles under every stop. | Implemented; local checks pass |
| FC3 — example routes | Example owner: private bounded BFS/detour search, result getters and focused tests. | FC2 graph interface | First shortest route when found, typed-edge identities, loop-free samples, strict NP, canonical ordering and independent caps. Examples cannot mutate corridor/SCC/source facts or writer candidates. | Implemented; local checks pass |
| FC4 — codec and CLI | Product owner: `src/reports/frame_connections.rs`, report exports, `src/bin/ariadne_minidump/` integration, root manifest test registrations and `tests/input/`/`tests/reports/`. | FC1–FC3 | Self-contained strict replay; JSON/text/DOT agreement; live capture and separately decoded source supported through the library. Existing structure/path routes and versions replay unchanged. | Implemented; local checks pass |
| FC5 — finite qualification | Qualification owner: isolated model/oracle/replay/mutation jobs and source/tool receipts under `evidence/Ariadne/frame-connections/`. | FC4 | Root/feature/layout/model/oracle/compiled-mutation/capture/legacy controls pass on declared sources; all ignored or missing prerequisites named. | Passed remote finite qualification, 2026-10-19 |
| FC6 — capture application and delivery | Corpus/docs owner: original and controlled capture comparisons, canonical usage/validation summary and this ledger. | FC5 | New product accepts the declared large source and recursive controlled source; preserves inputs/gaps and shows independently checked summaries/examples or honest layer stops. | Passed both declared capture applications remotely |

## FC0: contract, identity and finite policy

Inventory the complete current Stage 5.1 source interface, report versions,
conditional hypothesis behavior and old CLI routes. Retain baseline bytes for
actual saved v1 and conditional v2 reports. The current source publication ID
is codec-private: do not call a renderer from investigation to obtain it.
Specify a source-facts fingerprint over the actual validated chain, selected
range, roots, frame/query identities, recovery facts, active links, policies
and hypotheses. Specify separate logical and publication hash domains with no
cycles, and frozen canonical orderings.

Freeze one complete finite policy covering nested structural input/replay,
eligible graph nodes/edges, adjacency construction, traversal work, SCC stacks,
temporary/frontier/candidate bytes, BFS attempts, route length, deadlines,
assessment replay and published bytes. Zero work limits stay real limits;
malformed questions, scope and source evidence are rejected before work stops.
Default sizing must carry the recorded 9,589+778 decoded frame pair and its
source/proof payload; defaults are policy choices rather than hard maxima.
This stage must not inherit old frame-path admission/output clamps.

Add the authoritative finite model before runtime acceptance. Its checked
properties must include:

- The represented graph and original typed frontiers are preserved.
- Complete reachability sets equal finite closure under the admitted edges;
  exact corridor membership is the forward/reverse intersection.
- Only completed work can produce graph-relative absence. Unknown continuations
  can hide reconnection; no status turns them into a program disconnection.
- Complete SCC membership is a partition with mutual reachability and maximal
  components; its quotient is acyclic and preserves represented inter-component
  relations. Self-loop singletons are cyclic; recursive activations stay distinct.
- A shortest witness has minimum edge count in the represented graph; further
  examples are valid loop-free typed routes with strict NP and bounded work.
- Examples and truncation preserve all possible writers and inherited premises.
  Conditional hypotheses cannot be stripped or combined into a baseline claim.
- Resource stops terminate fairly within the modeled schedule and remain
  distinct from invalid evidence and missing anchors.

The model abstracts concrete byte/hash validation and wall clocks. Its guide
must state the adapter/source premises and exact Rust correspondence; finite
checking is not a universal refinement proof. Register model/checker commands
in `Specs/README.md` only when the files exist. Add an independent literal
graph oracle whose expected closures and SCC equivalence come from a different
finite procedure, not the SUT's outputs.

## FC1–FC3: implementation and independent cases

Start at the new investigation interface. The source is immutable and privately
validated. Keep route eligibility and boundary attachments explicit, including
edges to undecoded/out-of-function destinations. Shared helpers may be factored
only with legacy behavior/identity regression controls. Do not turn decoded
callee references into local roots or follow arbitrary call-only edges.

Required graph cases:

| Case | Required observation |
| --- | --- |
| Straight line and diamond | Exact corridor and shortest route; two branch alternatives retain their typed edge identities. |
| Parallel edge kinds | Equal node sequences with different typed edges remain distinct examples. |
| Self-loop, two-node cycle, nested/connected SCCs | Exact known partition/condensation and inspectable original members/edges; no iteration-count inference. |
| Cycle with an exit | Finite traversal terminates; the exit stays visible and a shortest example needs no loop unrolling. |
| Disconnected represented graph | Exact graph-relative absence only after complete work; scope and source gaps retained. |
| Unknown frontier outside the corridor | Forward-reachable unresolved continuation stays visible even when its known destination cannot reach the endpoint. A completion adding reconnection cannot contradict a prior program-level negative claim because none was made. |
| Failed/pending/out-of-function endpoint | Original edge and boundary identity retained; no invented terminal instruction or promoted route. |
| Missing/ambiguous active call or child entry | Cross-frame corridor/examples unavailable; independently available frame maps/SCCs survive. |
| Recursion with repeated VAs | Activation identities and exactly admitted younger-frame transitions retained; no cross-activation SCC merge. |
| Equal selected frame | A validated identical anchor permits a zero-edge example only when NP allows it. |
| Work stops at every layer, NP=1 and zero budgets | Source maps and completed independent layers survive; no false corridor, partition, shortest guarantee or absence. |
| Conditional source | All dependent results retain original hypothesis identity; baseline verdicts and source proofs remain unchanged. |

Implement iterative graph algorithms: no recursion proportional to graph depth.
Examples use the admitted graph and do not require completed SCC work;
their budgets and statuses remain independent. Stop provenance must identify the actual restricted operation. Do not
retry indefinitely to fill an example count or reuse a partial SCC label as if
the partition were complete. Minimize retained copies of large source/proof
payloads and check allocation estimates/overflow before work.

## FC4: product, replay and compatibility

The new JSON envelope embeds one unchanged structural source plus its binding
and the derived assessment. Nested source decoding calls the existing strict
decoder under a separately bounded host structural policy. Replay reconstructs
the privately owned source before recomputing corridor/SCC/examples and comparing
all claimed facts, statuses, IDs and work receipts. A verifier budget stop is a
refusal to trust the artifact, not a valid unexplained graph.

JSON/text/DOT must show source selection and hypothesis premises, separate layer
statuses, full memberships/typed frontier references, shortest guarantee scope,
example restrictions, counters and stop reasons. A collapsed SCC must link to
its member nodes/edges. Unclassified frontiers and non-corridor unknowns must
remain navigable. Do not hide source evidence to make the envelope fit.

Factor live structural capture preparation into a private shared function
where needed; preserve current `--frame-structure` output bytes and behavior.
The proposed new flags are `--frame-connections N:M`,
`--example-path-count-bound NP` and `--frame-connections-limits FILE`.
Reject explicit full-analysis backend, old path-listing, entry/seed and
explanation/assessment combinations. Keep `bap` as the old full-analysis
default; it does not label the new graph consumer as native core execution.
Library saved-source support does not require a new stdin replay CLI.

Run actual legacy v1/v2 structural replay, legacy path reports and current
default full analysis as separate compatibility controls. Keep core-only,
reports-only, BAP-only and input feature behavior explicit. All Rust sources
belong under `src/`, fixtures/tests under `tests/`, with the root manifest/lock
and root `target/` layout.

## FC5–FC6: qualification and capture scope

Implement named model/oracle/mutation entry points before citing them as
available. Follow the established remote Windows WSL workflow for heavy
qualification, using task-owned source capsules and isolated build directories.
Keep replay and mutation outputs in different `target/` subdirectories and
record exact executable/source/tool identities. Ordinary Cargo tests do not
exercise all ignored native/capture tests automatically.

Required root checks after runtime changes:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Compiled behavioral mutations must be rejected by unchanged independent
observers for: omitted off-corridor unknown frontiers, forged absence after a
work stop, incorrect SCC merge/split, self-loop omission, erased parallel edge
kind, an unsupported active-call link, false shortest labeling, NP off-by-one,
producer-raised host limits, hypothesis stripping and dropped writer alternatives.
Compilation/transport failures earn no mutant-sensitivity credit.

Use at least these separately identified capture products:

1. The original large Windows pair from the
   [Stage 5.1 record](../../evidence/Ariadne/frame-structure/20261016/README.md):
   original dump `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`,
   thread 23668, frames 1→0. Publicly replay its complete saved structural
   report rather than repeating full caller completion. Verify the actual
   original/conditional source version and binding selected for the run.
2. The independent controlled Windows Crashpad case from the
   [2026-10-18 report](../chatdocs/ariadne-crashpad-dump-analysis-20261018.html):
   dump `47d93971541230b24d992e3c0f60a17df732145f083089844b99e44597f1ae34`,
   thread 17848, frames 5→0. Its six maps/five active links and loops provide
   explicit recursion and cycle controls. Its nine old DFS samples do not
   define expected Stage 5.2 shortest routes or SCCs.

Independently check the new graph domain, source preservation, corridor sets,
SCC equivalence, quotient edges, frontier attachment and example validity. Name
missing raw inputs or prerequisites as unexercised. Resource-stopped examples
may be valid partial results, but FC6 must still demonstrate at least one
useful independently checked shortest route in its declared acceptance corpus.
A failure on the large case remains a failed or incomplete gate, not replaced
by a small fixture pass. No existing F4/S6 or release claim is implied.

## Execution record

2026-10-18: inspected the recommendation's §5 second item, canonical Stage 5.1
design/ledger, source types/getters, raw typed gaps, active-link composition and
codec-private identity. Drafted the owning design extension and this staged
plan. Runtime/model implementation and new qualification were not attempted.
Documentation/link validation passes: 76 connected documents, 75 context
sections and 2,221 local links, plus scoped whitespace checks. These checks
do not credit FC0–FC6 runtime acceptance.

2026-10-18 implementation: added the BAP-feature investigation consumer, private
source-owning bound result, activation-qualified graph/context/frontiers,
independent bounded forward/reverse traversal, iterative SCC/condensation and
BFS/edge-detour examples. Added strict `ariadne.frame-connections/v1` replay,
JSON/text/DOT, shared structural preparation and opt-in CLI. Source facts,
conditional hypotheses and old publication identities are preserved.

Local validation: 13 finite model configurations/typecheck, 516 independent
literal graph expectations, the 10,000-node depth case, public codec/host/stop
controls and 12 compiled behavioral mutations pass. Root tests pass (305,
111 ignored); core-only tests pass (57, 22 ignored); reports-only tests pass
(70, 22 ignored). Formatting, all-feature/all-target Clippy, layout and document
navigation pass. Live conditional/stop checks, legacy structural CLI, configured
native/Rust frame paths, both actual retained combined-report versions and a
fresh default native full-analysis control pass separately. Ignored tests
outside these named tiers remain unexercised.

Both saved capture products pass source-byte preservation, public BAP-only replay
and independent graph/SCC/shortest checks. Original large range 1:0: 10,367
nodes, 11,656 edges, 23-node corridor, 3,143 components/33 cyclic, one 22-edge
shortest example. Controlled recursive range 5:0: 176 nodes, 179 edges,
140-node corridor, 167 components/three cyclic, one 133-edge shortest example.
All 610/14 gaps survive. See the evidence record for exact source/binding and
qualification boundaries. FC5 remote qualification remains open; local passes
do not satisfy that remote gate.

## 2026-10-19 remote qualification

The [section-5 remote record](../../evidence/Ariadne/frame-question/20261019/README.md)
closes FC5/FC6 for the unchanged declared structural sources. The fresh campaign
checks 13 model scenarios, 516 literal graph expectations, 12 compiled mutations,
conditional/stopped live controls and strict public saved replay. Actual prior
structural v1/v2, legacy frame versions and normal native behavior have separate
compatibility receipts.

Original source `229e9248…`: 10,367 nodes, 11,656 edges, 23-node corridor,
3,143 SCCs/33 cyclic and one 22-edge shortest example. Controlled source
`5a7ce406…`: 176 nodes, 179 edges, 140-node corridor, 167 SCCs/three cyclic and
one 133-edge shortest example. All 610/14 source gaps remain. An independent
DFS/Tarjan/distance observer checks the entire represented result. No new
full-analysis or program-level negative reachability claim is supplied.
