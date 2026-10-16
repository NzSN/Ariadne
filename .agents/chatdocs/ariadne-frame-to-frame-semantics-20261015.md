# What the current frame-to-frame analysis means

**The current question asks Ariadne to list a bounded number of structural instruction paths between validated captured frame activations. A listed path follows admitted graph edges and call anchors; its complete machine-state feasibility is not proved by the path enumerator.**

This distinction matters for the earlier DFS discussion. “Find one feasible execution witness” would be a stronger goal. The current listing can return a structural alternative whose data conditions remain unknown.

## 1. What “frame 1 → frame 0” identifies

A frame index identifies one physical activation in a captured thread's validated unwind chain:

| Index | Meaning in this dump |
| --- | --- |
| Frame 0 | Innermost captured activation; its PC is `0x7ff77443dd6e` |
| Frame 1 | Its older caller; its recovered PC is `0x7ff77440410d`, the return continuation after the active call |

The question is bound to the same immutable dump, thread 23668, unwind chain and analysis scope. It does not combine arbitrary frames from different captures.

Different recursive invocations can execute the same instruction address. Nodes therefore have identity **`(frame index, instruction VA)`**, within the bound chain. Equal VAs in two activations remain different nodes.

Unwind recovery goes from the captured inner frame toward older callers. The requested path direction `1 → 0` follows forward control through the active call into the younger activation.

## 2. The exact start and end anchors

For `1 → 0`, the returned path starts **at the caller's active CALL instruction**, crosses into the callee at its function entry, and ends **at the captured PC in frame 0**.

For this dump, the expected anchors are:

```text
Preparation context in frame 1:
    function entry 0x7ff7744033a0 → ... → active CALL 0x7ff774404108
    ^ per-frame recovery starts here        ^ returned 1→0 path starts here

Requested forward path:
    (frame 1, 0x7ff774404108)     CALL
                  ↓ verified cross-frame Call edge
    (frame 0, 0x7ff77443d960)     callee function entry
                  ↓ zero or more local graph edges
    (frame 0, 0x7ff77443dd6e)     captured endpoint PC
```

The caller's function-entry-to-call corridor is prerequisite discovery context. It is not part of the returned `1 → 0` path. The caller's saved PC `0x7ff77440410d` is the continuation **after** CALL, so it is not the forward start anchor either.

Captured bytes at `0x7ff774404108` are `e8 53 98 03 00`. They encode a five-byte direct call:

```text
next instruction = 0x7ff77440410d
relative target  = next instruction + 0x00039853
                 = 0x7ff77443d960
```

These bytes identify the expected call candidate. The current unavailable listing has not admitted a completed caller graph, so this explanation does not substitute that candidate for the missing binding prerequisite.

The general rule is:

- Start at frame N's validated active call when `N > 0`.
- End at frame 0's captured PC when `M = 0`.
- If `M > 0`, end at frame M's active call site, before its call into the next younger frame.
- If `N = M`, matching anchors may yield a one-node, zero-edge path, subject to budgets.

<!--ANCHOR_FIGURE-->

## 3. How a cross-frame CALL edge becomes valid

The current implementation accepts a deliberately narrow active-call anchor. It requires:

1. Valid captured bytes for a five-byte `E8 rel32` instruction.
2. Its next-instruction address to equal the older frame's recovered return/resume PC.
3. Its decoded fall/target facts to match the calculated continuation and target.
4. Its target to agree with the younger activation's function entry.
5. Exactly one matching active-call candidate in the supplied graph.

Only then does composition insert a typed edge:

```text
(frame N, active CALL) --Call--> (frame N-1, child entry)
```

A captured unwind relationship alone is not an instruction-level connection accepted by this enumerator. The older diagram's dashed “recovery boundary / frame relationship” annotations were explanatory notes, not enumerated CFG edges. Its renderer explicitly stated that the active-call connection was unavailable.

Indirect calls, tail calls or other forms do not automatically pass this current E8-only anchor rule. Missing or ambiguous anchor evidence makes the question unavailable.

## 4. The pipeline has separate gates

There are several computations behind the phrase “frame-to-frame analysis.” They have different states and different budgets:

| Stage | Main job | What it produces |
| --- | --- | --- |
| Captured frame recovery | Validate thread/stack/unwind evidence | Physical frame activations and their provenance |
| Per-frame preparation | Discover instructions from an explicit entry; apply admitted BAP, guard and target semantics | A frozen request and CFG facts with explicit gaps |
| Local core analysis | Finish recovery, may-reaching definitions and slicing for that request | A completed local analysis, possibly still carrying unresolved control obligations |
| Investigation/frame binding | Match the exact completed request/state to capture/proof evidence | Activation-scoped frame graphs |
| Composition | Validate the selected anchors and connect active calls | One composed structural graph for the question |
| Path listing | Deterministic bounded DFS through that graph | Fewer than NP structural paths and a coverage/stop report |

“Completed local analysis” means the core reaches `Phase::Done` for its fixed admitted graph. It does not mean every indirect target was recovered or every instruction effect was precise. The completed callee can still retain two indirect-target obligations.

The current `BoundInvestigation` API requires `Phase::Done`. Although the final path search itself uses CFG topology, the current pipeline obtains that topology through completed investigations. A recovery-only caller cannot currently be substituted for the completed caller binding. This is an implementation/evidence contract, not an intrinsic requirement of all structural path-search algorithms.

## 5. Two different DFS procedures are involved

| Procedure | Direction and search state | Meaning |
| --- | --- | --- |
| Indirect-target resolver | Backward from a JMP; carries target expressions, rewritten branch guards and predecessor contexts | Justifies candidate destination addresses and incoming coverage |
| Frame-path enumerator | Forward from the selected anchor; carries node sequences and typed edge sequences | Lists structural walks between frame anchors |

The resolver discussion at `0x7ff77443da0e` concerned the first procedure. The frame listing uses the second procedure after graph preparation and binding.

The frame-path enumerator has no register/memory valuation or accumulated path-condition formula in its frontier state. It does not independently run a global solver to prove all branch conditions in a returned path jointly satisfiable.

Accepted earlier guard/target proofs can change the graph supplied to it. Once that graph is bound, the enumerator extends the supplied edges. Unknown feasibility remains eligible. A returned structural path is therefore an alternative **under the recorded premises**, not a reconstructed execution history.

## 6. What the edge kinds mean

| Kind | Interpretation |
| --- | --- |
| `Next` | Local ordinary continuation |
| `Taken` / `Fallthrough` | A represented conditional-branch alternative |
| `Jump` | A represented direct jump |
| `Indirect` | A retained candidate indirect target under its target-resolution contract |
| `Summary` | A call-to-continuation abstraction; the callee interior is not listed |
| `Call` | The specifically validated active-call transition into the next younger frame |

At active calls in queried frames strictly older than destination frame M, composition suppresses the local outgoing continuation and inserts the cross-frame Call edge. The returned path enters the selected child activation. If M > 0, enumeration stops at frame M's active-call anchor before entering M-1; its graph edges need not be removed to enforce that endpoint.

Other calls can remain opaque Summary edges. A path containing one does not enumerate the helper's instructions or establish that its concrete execution returned. The result marks `contains_opaque_summary`.

A path's identity includes both its node sequence and its typed edge sequence. Two parallel edges with the same source and destination but different kinds can therefore distinguish two paths.

## 7. The count bound is strict

```text
0 <= returned_count < NP
maximum retained paths = NP - 1
```

| NP | Maximum returned paths |
| ---: | ---: |
| 1 | 0 |
| 2 | 1 |
| 10 | 9 |

So **NP=2 already expresses a capacity of one structural path** in the current listing. It does not bypass graph/anchor prerequisites or add a feasibility proof. NP=1 cannot be used to ask for one path because its list capacity is zero.

The count limit does not bound preparation work. It also does not reveal the total number of program paths. If a count cap stops a search while prefixes remain, those prefixes might lead to more complete paths, or might lead only to dead ends.

<!--STRUCTURAL_DEMO-->

## 8. How the actual enumeration runs

The supplied edges are sorted into a canonical order. The enumerator keeps a stack of path prefixes. It pops one prefix, appends it to the result if it reaches the endpoint, or pushes permitted outgoing extensions in reverse order so the next pop follows the canonical edge order.

A prefix contains:

```text
(nodes visited in order, typed edges traversed in order)
```

The current algorithm does not select a particular concrete register state for that prefix. It is not an unbounded “find every execution” operation.

Independent limits restrict search states, scanned edges, nodes in a path, repeated visits to an activation-scoped node, frontier bytes, output bytes and elapsed time. A node may be visited at most twice by default. Hitting that visit cap omits longer structural unrollings; it does not prove that a real loop could execute only twice.

| Limit | Default | Retained full-dump request |
| --- | ---: | ---: |
| Composed graph nodes | 8,192 | 8,192 |
| Composed graph edges | 32,768 | 32,768 |
| Expanded search states | 4,096 | 65,536 |
| Scanned edges | 16,384 | 262,144 |
| Nodes retained in one path | 256 | 4,096 |
| Visits per activation-scoped node | 2 | 2 |
| Frontier bytes | 4 MiB | 32 MiB |
| Output bytes | 4 MiB | 128 MiB |
| Cooperative deadline | 1,000 ms | 10,000 ms |

Frame binding separately has hard aggregate admission limits of 8,192 decoded nodes and 32,768 core edges, counted before in-function filtering. Increasing only the later enumerator's graph limit does not change that earlier binding cap.

The target resolver's 2,097,152 symbolic work units and the caller core's 1,000,000 diagnostic actions belong to earlier stages. They are not this path DFS's search-state limit.

## 9. What the result fields mean

| Field or status | Meaning |
| --- | --- |
| `available=false`, `coverage=unavailable` | Required input graphs, frames or anchors could not be supplied/composed; the requested listing is not available |
| `coverage=partial` | The available result does not establish complete enumeration/graph coverage in the declared scope |
| `truncated=true` | A work, size, depth, visit or other declared search restriction cut work short |
| `enumeration_exhausted=true` | The frontier was drained without search restrictions or an earlier stop |
| `complete_within_declared_scope` | Enumeration exhausted and the retained graph has no reported gaps, under its declared scope |
| `returned_count` | Number of retained paths; always strictly less than NP |

`enumeration_exhausted` and graph completeness are different. The represented frontier can drain while input gaps remain, leaving coverage partial.

A zero count needs its accompanying status:

- **Unavailable + zero:** the question could not be composed; no disconnection conclusion follows.
- **Partial/truncated + zero:** no path was retained within the work completed; no impossibility conclusion follows.
- **Exhausted + closed declared graph + zero:** no structural path exists in that admitted graph/scope. This is still not a universal statement about every concrete program execution.

Complete structural enumeration is not the same as proving each listed path feasible. The graph and its scope are part of the claim.

## 10. What the current dump result actually says

The latest retained **full** listing attempt is `dump-20261015T073143`, for thread 23668, question `1:0`, NP=10:

```text
available             = false
coverage              = unavailable
returned_count        = 0
stop_reason           = missing-frame-query
truncated             = false
enumeration_exhausted  = false
expanded_states       = 0
scanned_edges         = 0
```

The caller core reached its one-million-action bound while still in Dataflow, so it did not supply a completed bound frame-1 graph. The callee completed and supplied frame 0. Composition requires both graphs for 1→0, sees frame 1 missing, and returns `missing-frame-query` before a DFS frontier is started.

This explains the perhaps surprising combination: **zero returned paths, but `truncated=false` and no search work.** The failure is availability before search. It is not evidence that the frame pair is disconnected, nor is it a DFS proof that every path is infeasible.

The later `075602` refresh validates final-helper admission and caller structural recovery, and retains full callee parity. It deliberately does not repeat caller completion or frame-path enumeration. It does not turn the earlier unavailable result into a new successful listing.

There is another subsequent admission boundary: the caller already has 9,589 decoded nodes; together with the callee's 778, that is 10,367, above the current hard binding cap of 8,192. The current unavailable result occurs earlier, but completing caller dataflow alone will not remove that next cap.

Earlier reports used `missing-or-ambiguous-active-call-anchor` when caller recovery had not reached the expected call. The latest full record's immediate stop is the missing completed caller query, so these dated results should not be conflated.

## 11. Relationship to the “at least one path exists” hypothesis

The current question has fields `from_frame`, `to_frame` and `np`. It does not introduce a hypothesis that one feasible historical path must be constructible from the available model.

A witness-first target-resolution phase could help obtain table evidence, and NP=2 can request at most one structural frame path once inputs are admitted. Those are different stages. A hypothesis does not supply a missing completed graph or active-call certificate, and it does not make a structural result into a feasibility proof.

If the desired future question is “find one path whose complete data/branch conditions are satisfiable,” that requires an explicit stronger witness contract and adequate feasibility evidence. It is not what the current structural listing claims.

## 12. Memory writers, observations and scope

The frame-path list does not remove candidates from the core's may-reaching-definition or possible-writer results. A writer absent from a bounded list remains possible unless a separate proof excludes it across all relevant contexts.

Crash-time flags/registers do not automatically supply earlier branch outcomes. Saved registers recovered by unwinding have individual provenance; they do not constitute a complete historical register file for each frame.

The current guarded normal-flow scope also excludes exception-handler/debugger resumption from the modeled local continuation. Certified exception exits have no normal successor; the listing does not silently add handler-resumption edges. These limits remain in its premises.

## Source and verification

This explanation was checked against the current source and the retained full-result artifact. No build, model campaign or fresh dump execution was needed.

- Contract: `docs/Ariadne/investigation-design.md:350–475`.
- Completed-query binding: `src/investigation/validate.rs:143–154`.
- Frame graph admission: `src/investigation/frame_paths.rs:189–357`.
- Active direct-call verification: `src/investigation/frame_paths.rs:133–146`.
- Graph composition/anchors: `src/investigation/frame_paths.rs:907–1002`.
- DFS and coverage classification: `src/investigation/frame_paths.rs:1004–1213`.
- Strict report replay: `src/investigation/frame_paths.rs:1235–1264`.
- Authoritative modeled search contract: `Specs/AriadneFramePaths.tla`.
- Full-result artifact: `evidence/Ariadne/caller-semantic-coverage/20261015/artifacts/dump-20261015T073143/frame-paths.json.gz`.

The latest combined report uses `ariadne.frame-paths/v6`; the structural search contract is separate from those versioned proof-carrier generations.

<!--ADVANCED_START-->

## Optional formal view: the current structural judgment

### From implementation to invariants

The implementation owns an immutable bound input containing a captured frame chain and per-frame graph/proof payloads. It constructs anchors and composed edges, then mutates only frontier/result/counter state. It does not mutate captured bytes or the earlier core writer sets.

Its key checks are exact snapshot/query identity, validated activation-qualified nodes, typed edge membership, validated active calls, strict count bounds and explicit incomplete outcomes. Malformed input is rejected; missing query/anchor evidence can yield an unavailable listing.

The first abstraction preserves admitted graph topology, activation identities, anchors, typed edges, path ordering, limits and coverage. It replaces concrete capture/proof replay with an `InputAdmitted` premise. JSON layout, Rust allocation and SDK transport are erased.

### Minimal search machine

```text
Inputs = (G, start_anchor, end_anchor, NP, limits, graph_gaps)
State  = (frontier_stack, listed_paths, counters, blocked, stop_reason)
Path   = (node_sequence, typed_edge_sequence)
```

Initially the frontier contains the one-node start prefix, subject to admission/zero limits. A transition pops the newest prefix. An endpoint prefix may be retained; another prefix is extended by permitted outgoing edges in canonical DFS order. Limit transitions retain partial status. An empty unrestricted frontier allows exhaustion classification.

A representative successful structural trace is:

```text
[frame1:CALL]
→ [frame1:CALL, frame0:ENTRY]
→ [... local structural steps ...]
→ [frame1:CALL, frame0:ENTRY, ..., frame0:captured_PC]
→ retain path, subject to NP/output limits
```

This example is the intended shape of an admitted result, not a claimed path already returned for this dump.

The second abstraction erases per-node instruction internals and preserves only admitted typed graph transitions. The frame enumerator never had a global register valuation or branch formula in its search state; this is a limit of its claim, not a feasibility proof hidden in the abstraction.

### Syntax and judgments

Let `Γ` bind the admitted snapshot/thread/activation scope, composed graph `G`, anchors `A_N` and `A_M`, and declared summary/normal-flow premises.

```text
node  v = (frame_index, instruction_VA)
edge  e = (source_node, destination_node, edge_kind)
path  p = v0, e0, v1, ..., ek-1, vk
```

The useful judgment is:

```text
Γ ⊢ p : StructuralPath(A_N, A_M)
```

It means the first and last nodes are the validated anchors and every typed step belongs to the composed graph with matching endpoints. Typed edge identity distinguishes parallel alternatives. Activation identity prevents recursive frames from aliasing one node.

It does not mean:

```text
there exists a concrete machine-state execution realizing p
```

That stronger statement would need a state/condition semantics and evidence not carried by this enumerator.

### Statics and dynamics

A bound input is well formed when its capture/query/graph/anchor checks pass. A path prefix starts at `A_N` and contains only matching graph edges. A completed structural path also ends at `A_M`.

```text
EXTEND:
    prefix ends at u, and (u,v,kind) is an admitted edge
    → append that edge and v, subject to visit/path/byte/work limits

RETAIN:
    prefix ends at A_M, and list/output capacity permits
    → retain the distinct path

UNAVAILABLE:
    a required frame graph or anchor is absent
    → unavailable result, before path search

RESTRICT:
    a declared resource or loop-unrolling restriction prevents work
    → partial/truncated outcome, with its reason
```

The returned set `L` satisfies:

```text
L is a subset of the admitted structural paths
|L| < NP
```

Exhaustion with no input gaps justifies completeness within that declared structural scope. It supplies no additional judgment about actual execution or a selected memory writer.

### Correspondence and abstraction boundary

| Semantic concept | Current implementation |
| --- | --- |
| Input admission | `BoundInvestigation::new`, `bind_frame_paths`, `validate_input` |
| Anchors and cross-frame graph | `compose` and `call_target` |
| Path extension/retention | `list` |
| Stable scope/path identity | hashes of frozen input/question/limits and ordered path |
| Result validity | deterministic recomputation in `FramePathListing::validate` |
| Search-model authority | `AriadneFramePaths.tla` |

The TLA model assumes graph/anchor admission and models structural prefixes, deterministic DFS, NP bounds, resource stops, visits and preservation of writers. It abstracts wall-clock deadlines by an admitted work-count receipt. Capture binding, JSON sizing, concrete hashes and process memory are outside that model. Finite conformance evidence does not establish universal implementation refinement.

<!--ADVANCED_END-->

## Context and follow-up

**Status.** Retained explanation of structural frame-path enumeration, restored on 2026-10-16.

**Why this document exists.** It preserves the conversation explanation associated with the [frame-path contract](../../docs/Ariadne/investigation-design.md) and [retained caller qualification](../../evidence/Ariadne/caller-semantic-coverage/20261015/README.md).

**What this document establishes.** The body records the stated mechanism, examples and evidence boundaries as of the report date.

**Where to go next.** Use the [frame-path contract](../../docs/Ariadne/investigation-design.md) and [retained caller qualification](../../evidence/Ariadne/caller-semantic-coverage/20261015/README.md); the [report index](ariadne-reports-index.md) links related explanations.

**What remains unresolved.** The explanation distinguishes structural paths, feasibility and incomplete query binding; restoration does not rerun the dump.
