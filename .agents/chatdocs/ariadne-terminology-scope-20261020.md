# Ariadne terminology scope and reader’s guide

## Context and follow-up

**Status.** Plain-language communication guide checked against source revision
`3d525e2929cae2416ad0a31f92bd201980e40827` on 2026-10-20. This requested Markdown
document explains vocabulary; it introduces no analysis result or qualification.

**Why this document exists.** Our discussions cross captured memory, program
graphs, value analysis, formal models and testing. Words such as *state*, *path*,
*trace*, *complete* and *replay* have different meanings in those areas.

**What this document establishes.** The meanings I will use in this repository,
the qualifiers needed to interpret them, and small examples for commonly
confused terms. Examples are illustrative unless explicitly linked to evidence.
The [canonical terminology convention](../../docs/terminology.md) owns repository
wording. This guide presents that vocabulary with additional explanations.

**Where to go next.** Use the [canonical vocabulary](../../docs/terminology.md)
for precise correspondences, the [architecture](../../docs/Ariadne/architecture.md)
for module ownership, the [implementation guide](../../docs/implementation.md)
for executable behavior, and the [plan index](../plans/README.md) for delivery
status. [Replay generation](../../mbt/README.md) and the
[assurance boundary](../../docs/Ariadne/semantic-assurance.md) explain the testing
and proof terms below.

**What remains unresolved.** Definitions do not establish executed history,
a crash’s root cause or correctness for every possible input. Feature designs
and dated evidence determine each implementation’s supported scope. Later
changes can supersede this guide’s source snapshot.

## How I will use these words

1. **Name the object.** “Analysis state,” “CPU state” and “abstract value state”
   identify different things. I will qualify “state” when its meaning is unclear.
2. **Name the scope.** “Complete target coverage under these premises” is more
   informative than an unqualified “complete.”
3. **Name the evidence.** Captured observations, calculated facts, assumptions
   and generated test expectations have different origins.
4. **Name the uncertainty.** “Unknown because the table entry is missing” tells
   us what prevents progress. Unknown never silently means zero or false.
5. **Name the validation.** “Six model configurations passed” and “native/Rust
   results matched” describe particular checks; “verified” alone is ambiguous.
6. **Preserve exact labels.** Backticks identify code/schema spellings. Ordinary
   prose explains their meaning without inventing additional enum values.

Quick navigation: [input](#1-input-and-identity),
[semantics and backends](#2-instructions-semantics-and-backends),
[control flow](#3-control-flow-and-indirect-targets),
[frames and loops](#4-frames-loops-and-paths),
[dataflow](#5-values-origins-and-memory),
[premises and results](#6-premises-evidence-and-result-status),
[models and testing](#7-formal-models-replay-and-mutation-testing),
[delivery](#8-qualification-and-delivery), and
[abbreviations](#9-abbreviations-and-stage-names).

## 1. Input and identity

| Term | Meaning in Ariadne |
| --- | --- |
| **Artifact** | Exact bytes of a file or external record. An artifact hash identifies those bytes. A filename alone does not. |
| **Dump / minidump** | Captured process information stored in a dump format: selected memory, thread contexts and metadata. A file called a minidump can include full-memory capture. |
| **Full-memory dump** | A capture configured to retain much more process memory. Availability and consistency still depend on the actual recorded streams and bytes. |
| **Immutable snapshot** | The fixed byte view used for one analysis. Ariadne does not update it from a running process during that analysis. |
| **Captured bytes** | Bytes recorded in the artifact and mapped to an address. Their presence establishes captured content, not what every earlier runtime load read. |
| **Snapshot identity** | Identifier of the snapshot view. Equal instruction addresses in different snapshots are different analysis sites. |
| **Analysis query / request** | The selected roots, slice seeds, instruction facts and applicable options supplied to an analysis. Different queries can use the same snapshot. |
| **Scope** | The exact question, source revision, activations, semantics, premises and limits within which a conclusion applies. |
| **Fingerprint / digest / SHA-256** | A content identity used to detect changes and bind records together. A matching digest establishes content identity; semantic validation has separate rules. |
| **Virtual address, VA** | An address in the captured process’s address space. Instruction and data addresses are VAs. |
| **Effective address, EA** | The address calculated for a selected memory access from its address operands. |
| **Exception instruction address / inaccessible-data address** | The captured instruction location and the reported byte associated with a failed access. The computed access start is a third address; these need not coincide. |
| **Access width / access span** | The number of bits/bytes accessed and the corresponding byte range beginning at EA. State the unit. |
| **File offset / RVA** | A position in stored data. A minidump RVA refers to a dump-file offset; a PE image RVA is relative to an image base. Specify the format. |
| **Capture contributor** | A recorded stream/descriptor and offset supplying bytes for a VA range. Agreeing overlaps retain every contributor. |
| **Capture hole / conflict** | Required bytes are absent, or recorded contributors disagree. Neither condition permits inventing a byte value. |
| **Byte-source provenance** | Where instruction bytes came from. Keep this separate from the origins of values computed by instructions. |
| **Module / symbol / PDB** | A loaded image, a name/address association, and Windows debugging-symbol data. Matched symbols can justify context or entry evidence; they do not fill captured-memory holes. |
| **CDB / WinDbg** | Windows debuggers used for independent capture inspection. Their output still needs matching artifact/module/symbol identities. |

Example: “Read eight captured bytes at VA `0x1000`” requires a valid mapping from
that VA to file storage. Seeking to file offset `0x1000` is a different operation.

Owner: [input and read contract](../../docs/Ariadne/file-reader-design.md).

## 2. Instructions, semantics and backends

| Term | Meaning in Ariadne |
| --- | --- |
| **Decoding** | Interpreting instruction bytes to identify instruction length, operands and control facts. |
| **Instruction semantics** | Rules describing the instruction’s represented behavior: values read/written, conditions and control effects. |
| **Lifting** | Translating machine-code bytes into an intermediate semantic representation. |
| **BAP / BIL** | Binary Analysis Platform and its instruction-level expressions/statements. BAP supplies production minidump semantics. |
| **Typed AST** | A structured expression/statement tree with explicit operations, types, widths and variable identities. Printed assembly is a display of information, not this admitted tree. |
| **Machine width / bitvector / modular arithmetic** | A fixed number of bits and arithmetic reduced to that width. A 64-bit wrapped address calculation differs from an unbounded mathematical integer sum. |
| **Signedness / sign extension / endianness** | Interpreting bits as signed or unsigned; extending a signed value to a wider width; and byte order. Each affects decoding a table entry into a target. |
| **LLVM MC reference** | Independent instruction decoding/control reference facts. It does not provide an automatic replacement for unsupported BAP effects. |
| **Projection** | Converting admitted BIL into the control, dependency and address-use summaries Ariadne tracks. |
| **Instruction summary / effects** | Frozen facts such as successors, targets, used locations and possible/definite definitions. These abstract the instruction’s behavior. |
| **Admission / validation** | Checking that supplied facts satisfy an interface’s conditions before accepting them. A recognized opcode name alone is insufficient. |
| **Profile** | A named, versioned set of supported forms, assumptions and rules. Support for one profile does not imply support for every instruction form. |
| **Schema / protocol / handshake** | A record format; interaction/message rules; and initial agreement on compatible versions, capabilities and identities. Shape compatibility does not replace semantic checks. |
| **Semantic backend** | The producer of instruction semantics: BAP for the production minidump path. |
| **Analysis backend** | The implementation running Ariadne’s analysis: the native OCaml/BAP core or the Rust reference core. Selecting Rust analysis retains BAP minidump semantics. |
| **Helper / adapter** | A helper is a separate tool/process performing a task. An adapter joins interfaces and validates/translates their data. Name the lifting or analysis helper when relevant. |
| **Opaque effect / opaque summary** | Behavior represented conservatively because its precise data effects are unavailable. Control certainty and data precision are separate questions. |
| **Unsupported semantics** | Behavior outside the admitted semantic rules. Depending on the owning contract, it produces an explicit gap, conservative continuation or stop. |
| **Namespace / operand width** | The admitted register/variable names and their bit widths. Accepting `YMM6` as a name does not establish precise semantics for every AVX operation. |
| **Register alias** | Overlapping views such as RAX, EAX, AX and AL. The location model tracks shared byte cells instead of treating these as independent registers. |
| **LLVM IR analysis** | A separate analysis family consuming supplied LLVM IR. Reading a minidump does not reconstruct the program’s original LLVM IR. |

I will qualify **native**: “native analysis helper,” “native lifting helper,” or
“native Windows capture.” Those phrases refer to different components.

Owners: [architecture](../../docs/Ariadne/architecture.md) and
[BAP integration](../../docs/Ariadne/bap-analysis-core-design.md).

## 3. Control flow and indirect targets

| Term | Meaning in Ariadne |
| --- | --- |
| **Control-flow graph, CFG** | Nodes and typed edges representing admitted possible control transfers. |
| **Node / site / instruction start** | Usually an instruction VA within one snapshot. In a frame graph, activation identity also distinguishes nodes. Other graph IDs need their own qualification. |
| **Edge** | A represented relation from a source node to a destination, with a kind such as `taken`, `fallthrough`, `indirect`, `call` or `summary`. |
| **Incoming edge / predecessor** | An edge entering the node currently being discussed; its source is a predecessor. “Incoming” is relative to that destination node. |
| **Outgoing edge / successor** | An edge leaving the current node; its destination is a successor. |
| **Entry point / recovery root** | An explicitly supplied starting address for discovery. A captured PC or a slice seed becomes a root only through the applicable input contract. |
| **Slice seed** | An instruction selecting a backward dependency result. It does not independently start control-flow recovery. |
| **Recovery / discovery** | Following admitted local control facts from roots to find instruction sites and edges. It does not establish which route executed. |
| **Call edge** | A visible reference to a callee. Ordinary local analysis does not propagate through it as if it were an ordinary jump. |
| **Summary edge** | A local possible continuation around a call, with conservative caller-visible effects. It does not prove an actual return occurred. |
| **Branch guard** | A condition controlling an alternative, such as an index range check or an alignment condition. A structural edge may exist while its feasibility remains unknown. |
| **Path constraint / path-sensitive reasoning** | Accumulated conditions along a path, and reasoning that distinguishes such paths. Merged origin alternatives do not by themselves establish that all selected facts coexist on one feasible path. |
| **Direct / indirect jump** | A direct jump encodes its destination; an indirect jump obtains a destination from an operand expression, register or memory. |
| **Target** | A candidate destination of a control transfer. Recovered targets need not all be feasible or executed. |
| **Target resolver** | Analysis deriving candidate indirect destinations from admitted semantics, value facts and captured control data. The reader’s separate byte-resolution operation has a different role. |
| **Jump table / pointer slot** | A table of encoded destination data, or one memory slot containing a pointer. The admitted encoding determines how bytes become candidate VAs. |
| **Selector / table index** | A value used to choose a table entry. This is descriptive analysis vocabulary, not a special implicit operand of a near `JMP`. |
| **Target completeness** | The supplied target set covers every admitted target under its declared incoming-state scope and premises. `complete = false` leaves additional destinations unresolved. |
| **Coverage certificate / receipt** | Structured evidence checked to justify a coverage or target claim: graph facts, definitions, reads, arithmetic, identities and premises. A hash alone supplies no coverage proof. |
| **Incoming-state coverage** | Coverage of the relevant alternative ways of reaching a site and the value facts along them. Seeing every graph edge is not always enough to cover every path combination. |
| **Graph epoch / source revision** | Identity of a particular graph/source version. Newly discovered edges can invalidate a conclusion that relied on earlier coverage. |
| **Frontier** | Known unfinished work or unresolved continuation at an analysis boundary. Its absence from a displayed sample does not eliminate it. |

Example: with edges `A → B` and `C → B`, **B has two incoming edges** and two
predecessors, A and C. A definite value along one incoming route need not be the
same along the other route.

For `JMP RAX`, the instruction uses RAX as its destination operand. An earlier
table calculation may have used a selector to produce that RAX value.

Owner: [indirect-target contract](../../docs/Ariadne/indirect-target-resolution.md).

## 4. Frames, loops and paths

| Term | Meaning in Ariadne |
| --- | --- |
| **Frame / activation** | One particular invocation in a captured thread’s call chain. Recursive calls to the same function are distinct activations. |
| **Frame index / physical frame** | A validated stack activation’s position. Frame 0 is innermost; larger indices refer to older callers. Debugger inline rows are not automatically additional physical activations. |
| **Captured context** | Recorded registers and validity information for a thread/exception. Earlier values require separate derivation and premises. |
| **PC / RIP / SP / RSP** | Program counter/instruction pointer and stack pointer; RIP/RSP are the AMD64 register names. |
| **Return address / active-call anchor** | A saved continuation address, and a validated call site whose continuation and target agree with the selected frame relation. The return address is not the caller’s function entry. |
| **Unwinding** | Deriving older frame contexts from captured stack data, unwind metadata and ABI rules. It supplies evidence-bound caller information, not complete past CPU states. |
| **Structural path** | A sequence whose typed edges occur in the admitted graph. Path existence alone does not establish satisfiable accumulated branch constraints. |
| **Feasible path under a model** | A path whose conditions and transfers can be satisfied within the stated supported model and premises. |
| **Executed path / history** | The instructions and branches actually taken by the real program. Establishing it requires stronger execution evidence than a snapshot-derived structural route. |
| **Corridor** | Nodes lying on represented connections between selected anchors: the intersection of forward and reverse reachability. Unknown continuations outside it may reconnect. |
| **SCC / strongly connected component** | A maximal group of graph nodes that can reach each other. A singleton is cyclic only if it has a self-loop. |
| **Condensation graph** | The acyclic graph formed by replacing each SCC with one component node. This simplifies graph structure while retaining underlying evidence. |
| **Loop invariant / induction** | A property established at loop entry and preserved by admitted iterations. Those obligations can justify reasoning across iterations without enumerating each one. |
| **Unrolling / visit bound** | Exploring only a bounded number of repeated traversals. A chosen bound does not establish the program’s actual iteration count. |
| **`cyclic-incoming-state`** | A resolver residual indicating unresolved incoming-state reasoning involving a cycle. The label alone establishes neither an infinite program loop nor a nonterminating analyzer. |
| **DFS / BFS** | Depth-first and breadth-first search. They choose exploration order; they do not themselves establish branch feasibility. |
| **Bounded path listing / NP** | Retain strictly fewer than positive NP paths under separate work/path limits. `NP = 10` allows at most nine retained paths. |
| **Reachability / decidability** | Reachability in a finite supplied graph is computable. General unbounded concrete path feasibility can be undecidable; bounded analysis must retain explicit unknowns when it cannot decide. |

A cyclic graph can still yield a terminating analysis: work limits, finite
abstract domains or checked loop reasoning bound the analyzer’s own work.

Owners: [frame paths](../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing),
[corridors and SCCs](../../docs/Ariadne/investigation-design.md#structural-corridors-and-cycle-summaries),
and [question-directed investigation](../../docs/Ariadne/frame-question-investigation-design.md).

## 5. Values, origins and memory

| Term | Meaning in Ariadne |
| --- | --- |
| **Dataflow analysis** | Propagating information through the admitted graph, such as possible definitions reaching each instruction. |
| **Tracked location / cell** | An abstract location used for dependencies and effects: a register byte, flag or coarse memory/state cell. |
| **Use** | A tracked input dependency of an instruction. Conservative summaries can contain more possible dependencies than a particular concrete execution uses. |
| **May-definition, `may_defs`** | A possible write. It adds an origin candidate while retaining earlier origins unless a justified must-definition removes them. |
| **Must-definition, `must_defs`** | A replacement justified for every admitted alternative. It permits removing earlier origins for that location. It need not produce a numerically different value. |
| **Kill / strong versus weak update** | Killing removes old origins through a justified must-definition. A weak update retains them while adding new possibilities. |
| **Origin / possible producer** | A static site that may supply a tracked value, or an entry origin representing a value already present at a root. It is not a particular dynamic loop iteration. |
| **Reaching definitions / reaching origins** | Definitions that may reach a location before the selected instruction under the supplied graph and effects. |
| **Dependency / backward slice** | A possible producer/use relation, or the instructions collected by following such relations backward from seeds. A slice is a set/graph of dependencies, not one ordered executed path. |
| **Value fact / constraint** | Numerical knowledge at a program point: an exact value, finite set, range, known bits or other admitted relation. This is separate from knowing a value’s possible origin. |
| **Value refinement** | Narrowing the represented possible values using justified additional constraints. This use of refinement is distinct from a formal implementation-refinement proof. |
| **Join / intersection** | A join combines alternatives, often retaining their possible origins or values. Intersection applies compatible constraints. The owning analysis defines the exact operations. |
| **Fixed point** | A stable information relation under further applications of the analysis rules. The real program may contain loops while its abstract dataflow reaches a fixed point. |
| **`memory:any` / alias uncertainty** | The core’s coarse memory cell can overlap any access. Aliasing asks whether accesses may refer to overlapping bytes. |
| **Possible memory writer** | A candidate memory origin. Additional range, value-instance, interference and execution reasoning is needed to identify a particular store as the actual writer. |
| **Clobber / opaque call effect** | A possible overwrite or loss of knowledge about tracked state. A prior value cannot be preserved through it without justification. |
| **Backward preimage** | Earlier values/states compatible with a later constraint and an admitted transfer relation. It is relational reasoning and may yield many values or no values. |
| **Candidate exclusion** | A scoped justification for ruling out a candidate in a separate assessment. It does not silently delete the original core candidate universe. |
| **Abstract stateflow** | A separate analysis propagating caller-supplied finite state transitions over a frozen graph. It is distinct from the core’s reaching-definition analysis. |

Example: in `MOV [RAX], RBX`, RAX contributes to the destination address and RBX
supplies the stored payload. Explaining an address and explaining stored content
are different questions.

Owners: [core implementation](../../docs/implementation.md) and
[memory refinement](../../docs/Ariadne/memory-provenance-refinement.md).

## 6. Premises, evidence and result status

| Term | Meaning in Ariadne |
| --- | --- |
| **Observed** | Supported by an admitted captured observation, with identity and validity evidence. An observed crash-time register does not automatically become an earlier register fact. |
| **Derived fact / claim** | A calculation or assertion obtained from evidence and rules. Its premises and question scope must remain visible. |
| **Premise / assumption / hypothesis** | A stated condition under which reasoning proceeds. A selected hypothesis remains conditional even if it enables additional analysis. |
| **Conditional result / baseline result** | A result using added hypotheses, or the result without those added hypotheses. Preserve their separate meanings and evidence. |
| **`FrozenCapturedControlData`** | The selected policy interprets covered table/pointer loads using named captured bytes. It does not establish that historical memory contents were immutable. |
| **Alignment premise / residue** | An assumed or derived address-alignment relation, or a possible remainder modulo an alignment. Knowing `RSP mod 16` is weaker than knowing exact RSP. |
| **Normal-flow scope** | Reasoning under admitted normal-completion conditions. A selected local scope does not include every exceptional exit or exception-resumption behavior. |
| **Guard admission / justified branch** | Checking evidence that permits a particular normal alternative under the declared rules. An assumption-based alternative must retain its conditional basis. |
| **Evidence receipt** | A record connecting an asserted fact to its inputs, bytes, tools, identities and validation rules. Validation rechecks the relevant content and relations. |
| **Gap / obligation / bottleneck** | Missing or unfinished evidence/semantics, a required unresolved analysis fact, or the specific unresolved item blocking a selected question. |
| **Unknown** | The supported information does not settle this question. It can result from missing bytes, unsupported rules, open incoming alternatives or a budget stop. |
| **Sound / conservative** | Claims are justified under the declared model/premises; an asserted covering approximation preserves admitted possibilities. Incomplete target lists retain an explicit unknown remainder. |
| **Precision / exactness** | How tightly information describes possibilities. Qualify the field and model: an exact represented graph relation can coexist with uncertain real-program behavior. |
| **Complete / coverage** | Always specify the object: target set, incoming states, fixed-point calculation, path enumeration, report field or exercised test corpus. These are separate properties. |
| **Partial / unavailable** | Partial retains useful results with unresolved gaps or restrictions. Unavailable lacks the evidence required to supply that result family’s usable answer. |
| **Truncated / exhausted** | Truncated means an expansion/retention restriction limited the result. Exhausted means the particular exploration drained under its own contract; other semantic gaps may remain. |
| **Resource budget / timeout** | A limit on work, visits, bytes, paths or elapsed time. Reaching it does not show that a missing path or value is impossible. |
| **Model witness / refutation** | Checked satisfying evidence, or a justified exclusion, within a named supported model and quantified scope. A model witness does not establish historical execution. |

### Exact labels depend on the result family

| Result family | Labels and interpretation |
| --- | --- |
| Fault-address explanation | `explained`, `partial`, `unavailable`: availability and remaining gaps for the admitted question. `explained` does not establish a root cause. |
| Claim classification | `observed`, `derived_under_premises`, `unknown`: where the claim comes from. |
| Frame-question verdict | `possible_under_model`, `refuted_under_model`, `unknown`, `premise_conflict`: a scoped model answer or unresolved/inconsistent premises. |
| Frame-question layer | `finished`, `work_stopped`, `unavailable`: the work/result status of one layer, separate from the overall verdict. |
| Alignment guard | `aligned`, `misaligned`, `unknown`, `unreached`: the guard analysis’s verdict, interpreted with its coverage and premises. |
| Conditional alignment basis | `proved`, `assumed`, `unreachable`, `unknown`: how the conditional decision is justified. `proved` concerns the scoped guard decision. |
| Numerical precision | `Exact`, `Constrained`, `Unknown`: one compatible value, useful restrictions on multiple values, or no useful numerical restriction, under the declared premises. |

**Completion example.** Core dataflow can finish at a fixed point while an
indirect target remains unknown. A path listing can contain a valid example
while remaining partial because of depth bounds and source gaps.

Owners: [investigation contracts](../../docs/Ariadne/investigation-design.md),
[frame-question types](../../src/investigation/frame_question/model.rs),
[guard types](../../src/bap/guard_admission.rs) and
[conditional alignment](../../src/bap/alignment_hypothesis.rs).

## 7. Formal models, replay and mutation testing

| Term | Meaning in Ariadne |
| --- | --- |
| **Formal model / specification** | Explicit mathematical rules for admitted inputs, states, transitions and properties. TLA+ is authoritative for the modeled analysis contract. |
| **Model state / analysis state / CPU state** | Model variables, the analyzer’s bookkeeping, and architectural registers/memory are distinct objects. A model of the analyzer does not automatically execute the captured program’s ISA. |
| **Action / transition** | One allowed change in a modeled or implemented analysis state. A replay `Visit` or `Propagate` action is an analyzer operation. |
| **Invariant / safety property** | A condition that must remain true, or a rule excluding prohibited behavior within the model. |
| **Liveness / fair termination** | Required eventual progress, with the stated scheduling/fairness assumptions. A safety check alone does not establish it. |
| **Model checking / bounded checking** | Exploring a selected model instance’s states or checking executions up to a stated bound. Record the instance/bound and the properties checked. |
| **Typechecking** | Checking that a model or program uses values consistently with its type rules. Passing it alone does not establish the intended safety or termination properties. |
| **Oracle / expected result** | An independently established expectation, such as model-generated states or arithmetic computed separately from the production resolver. |
| **Fixture / case / corpus** | A controlled input, one test scenario, or a named collection of cases and artifacts. A generated dump fixture is distinct from an actual crash capture. |
| **Generated model trace** | A sequence of model actions and expected states. In the core corpus, TLC generates traces from the TLA+ model; Stage E’s high-address witness uses Apalache. |
| **Observation / observer** | State/result data actually read from the tested implementation, or the component extracting/checking that data. Expected model fields must not substitute for actual observations. |
| **Replay conformance** | Execute the trace’s actions against the implementation and compare its observations with expected states. This checks the named finite corpus. |
| **Receipt/report replay** | Decode retained evidence, revalidate bindings and proofs, and reconstruct/check results under the owning codec contract. This is a different use of “replay.” |
| **Execution recording / execution replay** | Recording and reproducing the real program’s runtime events. The presence of model traces or saved analysis reports does not establish such a recording. |
| **Model/interface digest / lock** | Identity checks tying traces, model/interface definitions and generated bindings together. A wrong digest must be rejected before observations are dispatched. |
| **Generated binding / port** | Code implementing the typed interface between model replay and the real implementation. The adapter supplies actual observations through that interface. |
| **System under test, SUT** | The actual implementation/helper being exercised. State whether the campaign tests Rust analysis, native analysis or an adapter boundary. |
| **Mutation test / mutant** | Deliberately change real production code in an isolated copy and check whether unchanged tests catch the intended defect. |
| **Mutation seam / anchor** | The selected production-code location changed by a mutation, and the mechanism locating it. A stale/nonunique anchor is a setup problem. |
| **Unmodified control** | Run the same relevant test against unchanged code first. It must pass before the mutant’s failure can count. |
| **Killed / detected mutant** | The mutant built and its intended observer rejected the deliberately introduced behavior. A compilation failure or unrelated error earns no detection credit. |
| **Surviving mutant** | The intended behavioral fault was not detected. Investigate observer coverage, the mutation’s applicability and any equivalent behavior. |
| **Negative control / tamper test** | Intentionally invalid input, identity or evidence that must be rejected. This tests a boundary rather than introducing a production-code mutation. |
| **Regression test** | A test preserving previously corrected behavior. A meaningful regression distinguishes the defect from the corrected result. |
| **Conformance / refinement proof** | Conformance is agreement on exercised cases. A refinement proof establishes a specified relation between representations/transitions over its stated scope. Finite test agreement does not supply a universal proof. |

### Where model replay comes from

```text
TLA+ rules + fixture inputs
    → model checker generates actions and expected states
    → trace files are stored with source hashes
    → the implementation executes the actions
    → its actual observations are compared with the expectations
```

The [core generator](../../mbt/generate.py) does not run the Rust SUT to obtain
expected states. A concrete stored trace is
[Binary.itf.json](../../mbt/corpus/Binary.itf.json). R6 currently reuses shared
core/stateflow replay; resolver-specific checks also need their own oracle,
mutation and captured-input evidence.

### Mutation example

With a table base of `0x1000` and entry bytes `FC FF FF FF`:

```text
correct signed-32 decoding:   -4             → target 0x0ffc
mutated unsigned decoding:   4,294,967,292   → target 0x100000ffc
```

An independently expected target test should distinguish those results. The
unchanged implementation must pass, and the compiled mutant must fail for the
intended target-arithmetic reason.

Owners: [core MBT guide](../../mbt/README.md),
[Stage E guide](../../mbt/stage-e/README.md),
[native replay runner](../../tools/check_bap_core_replay.py) and
[resolver mutation campaign](../../tools/check_target_resolution_mutations.py).

## 8. Qualification and delivery

| Term | Meaning in Ariadne |
| --- | --- |
| **Source review** | Inspecting code and contracts. It establishes what the inspected source says; runtime execution is separate evidence. |
| **Fresh check / retained evidence** | A check executed in a named run, or stored results bound to their source/tool/input identities. Reusing retained evidence requires the relevant identity checks. |
| **Qualification** | A source-, tool-, input- and scope-bound collection of required checks and recorded outcomes. |
| **Acceptance gate / tier / clause** | A required completion condition, a category of evidence, or an individual requirement within it. Passing some clauses does not finish the whole gate. |
| **Passing within scope** | The declared clauses passed for their named corpus and premises. State what that scope is. |
| **Unexercised / ignored / excluded** | Not run; marked to skip in ordinary tests; or explicitly outside the accepted scope. None means a test passed. |
| **Supported / implemented / qualified** | A declared supported profile, code providing a behavior, and evidence satisfying its named gate. These words need separate justification. |
| **Historical / superseded / retired** | A record describes its original revision; a successor replaces its current role; or the project has ended that work track. Retirement does not establish completion. |
| **End-to-end latency / phase timing** | Total execution time of the specified CLI workload versus time spent in one internal phase. Compare like-for-like workloads and statistics. |
| **Commit / push / remote parity** | Recording a local revision, transferring it to the remote repository, and verifying the intended local/remote commits match. Delivery does not create new analysis evidence. |
| **Release qualification** | Acceptance of the packaged product and declared operating environments. A passing finite development campaign has its own narrower identity and scope. |

I will report outcomes in this shape:

> At revision X, check Y passed for corpus/query Z under premises P.
> The remaining limits are L.

Owner: [assurance and qualification boundaries](../../docs/Ariadne/semantic-assurance.md).

## 9. Abbreviations and stage names

| Label | Meaning or required qualifier |
| --- | --- |
| **AMD64 / x86-64** | The architecture name; the repository generally prefers AMD64 in supported-profile prose. |
| **GPR / SIMD / ABI** | General-purpose register; single-instruction multiple-data operations; application binary interface. ABI assumptions require explicit scope. |
| **ISA** | Instruction-set architecture. Ariadne’s independent instruction-step assurance track is retired; BAP lifting remains a trusted dependency with an explicit boundary. |
| **BIL / BIR / AST / IR** | BAP instruction expressions/statements; BAP program representation; abstract syntax tree; intermediate representation. Name the particular IR. |
| **CFG / SCC / DFS / BFS** | Control-flow graph; strongly connected component; depth-first search; breadth-first search. |
| **TLA+ / TLC / Apalache** | Specification language; explicit-state model checker; symbolic model-checking/type-analysis tool used by this repository. |
| **MBT / SUT** | Model-based testing; system under test. |
| **SMT / symbolic execution** | Constraint solving over logical theories; execution reasoning using symbolic values and path constraints. Do not infer a general solver from Ariadne’s finite supported constraint rules. |
| **R0–R6 / F0–F4 / S0–S6** | Stage identifiers belonging to the indirect-target, frame-path and caller-semantic-coverage plans respectively. Other plans can reuse letters/numbers. |
| **Stage 5.1 / Stage 5.2** | Structural frame reporting / corridors, cycles and bounded examples in the frame-investigation recommendation. |
| **I5a / I5b / I5c** | Separate fault-time address questions: zero effective address; zero encoded base plus nonzero displacement; selected address-wrap design. Their delivery statuses differ. |
| **Version / profile number** | Version of a named schema, producer or contract. `v3` needs its owning name; it does not automatically mean a BAP library version. |

## Phrases I will make precise

| If I say… | The clarification I should supply |
| --- | --- |
| “The value is known.” | Which program point, value instance, width and premises establish it? |
| “There are two incoming edges.” | Into which node or activation-qualified site? |
| “The target is resolved.” | Which candidate targets are justified, and is the list complete within its scope? |
| “A path was found.” | Structural example, checked model-feasible path, or recorded executed path? |
| “The analysis completed.” | Which calculation finished, and which obligations/partial result layers remain? |
| “The guard is proved.” | Which guard predicate, source revision, incoming coverage and premise basis? |
| “Replay passed.” | Model-trace conformance or saved report/proof replay, against which implementation and corpus? |
| “The mutation was detected.” | Did the unchanged control pass, did the mutant compile, and did the intended semantic observer fail? |
| “The result is exact.” | Exact with respect to which represented field, finite model and scope? |
| “The feature is done.” | Which plan gate and evidence record establish acceptance, and what remains outside it? |

For future discussion, naming a section and term—for example “section 7, replay
conformance”—provides a short, stable way to identify the intended meaning.
