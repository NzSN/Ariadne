----------------------------- MODULE Ariadne -----------------------------
EXTENDS Naturals, FiniteSets

\* WHAT THIS MACHINE DOES
\* ======================
\* This is a state machine for the ANALYZER, not the CPU being analyzed.
\* A transition visits an address, propagates analysis facts, or advances a
\* phase. It does not execute an x86 instruction. Spec describes how Ariadne
\* constructs a result from one fixed input snapshot.
\*
\* The pipeline is:
\*   recover  ->  dataflow  ->  slice  ->  done
\*   discover    compute       trace      expose the result,
\*   the CFG     reaching      producers  including any gaps
\*               definitions   backward
\*
\* Binary and dump inputs share every stage after byte-source selection.
\* A graph node is one decoded instruction, not a coalesced basic block.
\* Edges can also name boundaries or callees outside local discovery.
\* Calls use opaque summaries; this model does not enter callees automatically.
\*
\* The abstraction preserves addresses, possible local control transfers,
\* byte provenance, abstract reads/writes, and missing-information obligations.
\* It omits concrete bytes, numeric register values, flag equations, thread
\* interleavings, exceptions, unwind edges, and changes to code during analysis.
\* Decoding and semantic summaries are trusted inputs, not proved here.
\* Soundness relative to an actual executable therefore also depends on the
\* correctness and conservatism of the adapters supplying those inputs.
\*
\* TLA+ reading guide:
\*   x / x'          value before / after one analyzer transition
\*   UNCHANGED x     x' = x; this action cannot modify x
\*   /\, \/, ~       logical and, or, not
\*   \cup, \cap, \   set union, intersection, difference
\*   \A / \E         for every / there exists
\*   [f EXCEPT ![a] = v]  function f with only key a replaced by v
\*   @               old value at the key selected by EXCEPT
\* Conjuncts constrain a transition simultaneously; they are not sequential
\* assignments. For example, Visit uses visited' to refer to the new visited
\* set constrained by that same action.
\*
\* Comments containing @type are consumed by Apalache. Those annotations
\* also affect tool typechecking; ordinary explanatory comments do not.
\*
\* FIXED INPUTS
\* ============
\* Addresses: finite universe of candidate instruction starts, represented as
\* integers. Every represented target/continuation must belong to it, even if
\* its bytes are missing. Membership alone does not validate a code boundary.
\*
\* Locations: abstract storage identities, represented as strings. These can
\* name registers, individual flags, or memory regions. The adapter must handle
\* register overlap (such as EAX/RAX) and memory aliases conservatively; the
\* model treats different names as different locations.
\*
\* EntryPoints: roots of forward discovery. Starting at a crash instruction
\* alone discovers its successors, not earlier instructions or callers.
\* SliceSeeds: requested starting instructions for the backward data slice.
\* They are NOT additional discovery roots; undiscovered seeds are reported.
\*
\* InputKind: selects binary or dump byte policy, not a different CFG algorithm.
\* Captured: starts with a complete instruction-byte span supplied by the dump.
\* FileBacked: starts whose complete spans are available from the binary.
\* TrustedFallback: file-backed starts independently certified suitable for
\* filling dump gaps. Matching a filename alone is not such a certificate.
\* Decodable: starts where decoding selected bytes succeeds; actual success
\* also requires an available source, as expressed by CanDecode.
\*
\* Insn: total semantic table over Addresses. Entries at starts that never
\* decode are placeholders and contribute no edges or definitions. The table
\* and all other inputs remain fixed throughout this request.
\* Finite abstraction of one analysis request. Instruction semantics and byte
\* availability are immutable inputs, supplied by validated adapters/decoders.
CONSTANT
  \* @type: Set(Int);
  Addresses
CONSTANT
  \* @type: Set(Str);
  Locations
CONSTANT
  \* @type: Set(Int);
  EntryPoints
CONSTANT
  \* @type: Set(Int);
  SliceSeeds
CONSTANT
  \* @type: Str;
  InputKind
CONSTANT
  \* @type: Set(Int);
  Captured
CONSTANT
  \* @type: Set(Int);
  FileBacked
CONSTANT
  \* @type: Set(Int);
  TrustedFallback
CONSTANT
  \* @type: Set(Int);
  Decodable
CONSTANT
  \* @type: Int -> {kind: Str, fall: Set(Int), targets: Set(Int), complete: Bool,
  \*               uses: Set(Str), mustDefs: Set(Str), mayDefs: Set(Str)};
  Insn

\* Small string vocabularies make graph labels and result states explicit.
\* The provenance sentinel "unavailable" also means no successful decode has
\* yet been recorded; pending/visited/decoded distinguish unprocessed starts
\* from processed failures.
Kinds == {"ordinary", "conditional", "jump", "indirect", "call",
          "return", "stop"}
Sources == {"captured", "file", "unavailable"}
\* Unified storage/display vocabulary, with an explicit local-analysis policy.
\* Adding a new edge kind does not silently opt it into discovery or data flow.
LocalEdgeKinds == {"next", "taken", "fallthrough", "jump", "indirect", "summary"}
EdgeKinds == LocalEdgeKinds \cup {"call"}
\* @type: {src: Int, dst: Int, kind: Str} => Bool;
IsLocalEdge(e) == e.kind \in LocalEdgeKinds
Reasons == {"unavailable", "decode-failed", "indirect-targets", "call-targets"}
Phases == {"recover", "dataflow", "slice", "done"}

\* fall is a set of zero or one continuation addresses; targets is a set of
\* possible control-transfer destinations. complete is a trusted certificate
\* that targets exhausts an indirect jump/call's possibilities in this scope.
\* uses contains all relevant inputs, including memory-address operands.
\* mayDefs contains every location this instruction might write.
\* mustDefs contains locations definitely replaced on a summarized outgoing
\* path; only these locations may discard earlier definitions.
\*
\* For an imprecise call, mayDefs can be Locations with mustDefs empty: both
\* old and potentially new origins survive. Its uses should likewise include
\* every possibly relevant read. These summaries are supplied, not inferred.
\*
\* No output-specific dependency relation is provided. Once an instruction
\* enters the slice, ALL of its uses are followed, potentially overapproximating
\* the dependencies of one particular output operand.
InstructionType ==
  [kind : Kinds, fall : SUBSET Addresses, targets : SUBSET Addresses,
   complete : BOOLEAN, uses : SUBSET Locations,
   mustDefs : SUBSET Locations, mayDefs : SUBSET Locations]

\* Well-formedness contract for inputs, not a runtime repair procedure.
\* Ordinary, conditional and call instructions have exactly one continuation;
\* direct jumps and conditionals have exactly one explicit branch target.
\* All listed targets must be represented in Addresses, even at a boundary.
\* An empty indirect target set with complete = FALSE is wholly unresolved;
\* complete = TRUE is a stronger, trusted claim about the analysis scope.
ASSUME /\ IsFiniteSet(Addresses) /\ Addresses # {}
       /\ IsFiniteSet(Locations)
       /\ EntryPoints \subseteq Addresses /\ EntryPoints # {}
       /\ SliceSeeds \subseteq Addresses
       /\ InputKind \in {"binary", "dump"}
       /\ Captured \subseteq Addresses
       /\ FileBacked \subseteq Addresses
       /\ TrustedFallback \subseteq FileBacked
       /\ Decodable \subseteq Addresses
       /\ Insn \in [Addresses -> InstructionType]
       /\ \A a \in Addresses :
            /\ Insn[a].mustDefs \subseteq Insn[a].mayDefs
            /\ Cardinality(Insn[a].fall) =
                 IF Insn[a].kind \in {"ordinary", "conditional", "call"}
                 THEN 1 ELSE 0
            /\ (Insn[a].kind \in {"ordinary", "return", "stop"}
                 => Insn[a].targets = {})
            /\ (Insn[a].kind \in {"conditional", "jump"}
                 => Cardinality(Insn[a].targets) = 1)

\* These sets describe complete instruction-byte spans, not single bytes.
\* For dumps, captured bytes win. Fallback requires a separate certificate
\* covering image identity, address relocation and suitability of file bytes.
\* Source selection is deterministic and independent of discovery order.
\* Captured JIT code needs no file backing. Captured bytes that fail to decode
\* are NOT silently replaced with different file bytes. Availability describes
\* whole instruction spans; mixed-source spans need a richer provider model.
Source(a) ==
  IF InputKind = "binary"
  THEN IF a \in FileBacked THEN "file" ELSE "unavailable"
  ELSE IF a \in Captured THEN "captured"
       ELSE IF a \in TrustedFallback THEN "file" ELSE "unavailable"

\* Success requires both byte availability and a successful decoder result.
CanDecode(a) == Source(a) # "unavailable" /\ a \in Decodable
\* Records are identified structurally. Edge kind is part of identity: taken
\* and fallthrough edges to the same destination remain distinct records.
Edge(a, b, k) == [src |-> a, dst |-> b, kind |-> k]
\* An obligation records a gap at a site; it is not an inferred edge.
\* Obligations accumulate and are never discharged within this fixed request.
Obligation(a, r) == [site |-> a, reason |-> r]

\* Calls are opaque, potentially returning summaries. This operator describes
\* only local edges; CallEdges adds callee destinations to the unified graph.
\* Both conditional edges are retained. Crash-time register values do not
\* establish values at an earlier branch, and no path pruning occurs here.
\* The call summary edge permits returning to the continuation; it does not
\* assert that the callee always returns. Return/stop end the local scope.
\* This operator describes edges; Visit later schedules their endpoints.
LocalEdges(a) ==
  CASE Insn[a].kind = "ordinary" ->
         {Edge(a, b, "next") : b \in Insn[a].fall}
    [] Insn[a].kind = "conditional" ->
         {Edge(a, b, "taken") : b \in Insn[a].targets}
         \cup {Edge(a, b, "fallthrough") : b \in Insn[a].fall}
    [] Insn[a].kind = "jump" ->
         {Edge(a, b, "jump") : b \in Insn[a].targets}
    [] Insn[a].kind = "indirect" ->
         {Edge(a, b, "indirect") : b \in Insn[a].targets}
    [] Insn[a].kind = "call" ->
         {Edge(a, b, "summary") : b \in Insn[a].fall}
    [] OTHER -> {}

\* Call edges use the same record type and storage as local edges. They expose
\* possible callee entries for display/future expansion, but IsLocalEdge excludes
\* them from this request's traversal and reaching-definition equations.
\* A callee need not have readable bytes or be decoded. Even if decoded through
\* another root/local path, it must not receive definitions across a call edge.
CallEdges(a) ==
  IF Insn[a].kind = "call"
  THEN {Edge(a, b, "call") : b \in Insn[a].targets}
  ELSE {}

\* A call at a with target f and continuation b contributes two distinct edges:
\*   a --call--> f      a --summary--> b
\* The first identifies the callee; the second applies the opaque call summary
\* on a possible return. No matched callee-return edges are inferred here.
InstructionEdges(a) == LocalEdges(a) \cup CallEdges(a)
LocalSuccessors(a) ==
  {e.dst : e \in {edge \in InstructionEdges(a) : IsLocalEdge(edge)}}

\* Successful decoding does not imply complete control-flow knowledge.
\* Keep supplied partial targets AND their unresolved-target obligation.
\* Finding one indirect destination is insufficient to remove that obligation.
DecodeObligations(a) ==
  IF Insn[a].kind = "indirect" /\ ~Insn[a].complete
  THEN {Obligation(a, "indirect-targets")}
  ELSE IF Insn[a].kind = "call" /\ ~Insn[a].complete
       THEN {Obligation(a, "call-targets")} ELSE {}

\* Used for a visited start that cannot decode. Missing bytes and a failed
\* or unsupported instruction decode are distinct findings for the caller.
Failure(a) ==
  IF Source(a) = "unavailable" THEN "unavailable" ELSE "decode-failed"

\* Definition identity is tagged, so entry values cannot collide with VAs.
\* DEFINITION IDENTITIES
\* =====================
\* A definition identifies a possible ORIGIN, not the concrete stored value.
\* For example, [loc |-> "rax", site |-> a, origin |-> "entry"] represents an
\* unknown incoming value at root a. With origin "instruction", it represents
\* a possible write by instruction a. Different roots get distinct entry
\* origins even when they name the same location.
DefinitionType == [loc : Locations, site : Addresses, origin : {"entry", "instruction"}]
\* Every tracked location has an unknown incoming value at every entry root.
EntryDefs(a) == {[loc |-> l, site |-> a, origin |-> "entry"] : l \in Locations}
\* Generate one origin for each possible write, not only definite writes.
Gen(a) == {[loc |-> l, site |-> a, origin |-> "instruction"] : l \in Insn[a].mayDefs}

\* MUTABLE ANALYZER STATE
\* ======================
\* phase: current stage; phases advance and never return to recovery.
\* pending: discovered addresses awaiting a visit, as an unordered worklist.
\* visited: processed addresses, including missing bytes and decode failures.
\* decoded: successful subset of visited; the actual instruction-node set.
\* provenance: source of each successful decode; other entries retain a sentinel.
\* edges: unified local/call edges; kind determines the analysis policy.
\*        LocalGraph and CallGraph are derived views, not duplicate state.
\* obligations: recovery gaps; a completed result may still contain them.
\* reaching: candidate-address -> definitions BEFORE that instruction.
\*           Undecoded addresses keep empty sets throughout the analysis.
\* slice: decoded instructions currently included in the backward data slice.
VARIABLE
  \* @type: Str;
  phase
VARIABLE
  \* @type: Set(Int);
  pending
VARIABLE
  \* @type: Set(Int);
  visited
VARIABLE
  \* @type: Set(Int);
  decoded
VARIABLE
  \* @type: Int -> Str;
  provenance
VARIABLE
  \* @type: Set({src: Int, dst: Int, kind: Str});
  edges
VARIABLE
  \* @type: Set({site: Int, reason: Str});
  obligations
VARIABLE
  \* @type: Int -> Set({loc: Str, site: Int, origin: Str});
  reaching
VARIABLE
  \* @type: Set(Int);
  slice
\* The complete state vector defines stuttering and the fairness condition.
vars == <<phase, pending, visited, decoded, provenance, edges,
          obligations, reaching, slice>>

\* Consumers rendering the graph use edges. Local recovery/data-flow consumers
\* use the local projection. Callee references require no separate mutable set.
LocalGraph == {e \in edges : IsLocalEdge(e)}
CallGraph == {e \in edges : e.kind = "call"}

\* PHASE 1: RECOVER THE LOCAL GRAPH
\* ===============================
\* Queue the roots with no facts inferred yet. Reaching definitions are not
\* preloaded: entry facts are introduced by transfer equations after recovery.
\* Starting from empty definition sets is essential for computing the LEAST
\* fixed point rather than selecting an arbitrary closed solution.
Init ==
  /\ phase = "recover"
  /\ pending = EntryPoints
  /\ visited = {}
  /\ decoded = {}
  /\ provenance = [a \in Addresses |-> "unavailable"]
  /\ edges = {}
  /\ obligations = {}
  /\ reaching = [a \in Addresses |-> {}]
  /\ slice = {}

\* Consume exactly one queued address. On success, add its instruction,
\* provenance, all local/call edges and target obligations in one
\* atomic analyzer step. On failure, record why, without fabricating a node.
\* Even a failed attempt enters visited, avoiding retries of immutable inputs.
\*
\* pending' removes visited', not just visited. Thus a self-loop a -> a cannot
\* requeue the instruction currently being processed. Back edges and duplicate
\* targets are harmless because these collections are sets. If decoding a
\* previously discovered target fails, its incoming edges remain as evidence
\* of where recovery encountered a boundary.
Visit(a) ==
  /\ phase = "recover" /\ a \in pending
  /\ visited' = visited \cup {a}
  /\ IF CanDecode(a)
     THEN /\ decoded' = decoded \cup {a}
          /\ provenance' = [provenance EXCEPT ![a] = Source(a)]
          /\ edges' = edges \cup InstructionEdges(a)
          /\ obligations' = obligations \cup DecodeObligations(a)
          /\ pending' = (pending \cup LocalSuccessors(a)) \ visited'
     ELSE /\ pending' = pending \ {a}
          /\ obligations' = obligations \cup {Obligation(a, Failure(a))}
          /\ UNCHANGED <<decoded, provenance, edges>>
  /\ UNCHANGED <<phase, reaching, slice>>

\* Worklist exhaustion means every discovered local target was attempted,
\* not that every attempt succeeded or every indirect destination is known.
\* Freeze the graph even with outstanding obligations. All later analysis is
\* relative to this recovered graph and must retain its limitations.
FinishRecovery ==
  /\ phase = "recover" /\ pending = {}
  /\ phase' = "dataflow"
  /\ UNCHANGED <<pending, visited, decoded, provenance, edges,
                 obligations, reaching, slice>>

\* Forward may-reaching definitions. Only must-defs kill previous values;
\* may-defs alone preserve them (essential for aliasing and opaque calls).
\* PHASE 2: FORWARD MAY-REACHING DEFINITIONS
\* =======================================
\* For example, suppose reaching[a] contains an earlier origin for "rax":
\*   mustDefs = {"rax"} replaces that origin with a's generated origin;
\*   mayDefs = {"rax"}, mustDefs = {} retains BOTH old and new origins.
\* These are alternatives in provenance, not known numeric values and not
\* proof that every represented path can execute.
Out(a) == {d \in reaching[a] : d.loc \notin Insn[a].mustDefs} \cup Gen(a)
\* Only decoded LOCAL predecessors contribute. Local edge labels do not select
\* feasible paths; two local edges between the same nodes still identify one
\* predecessor. Summary edges transmit call effects to continuations. Call edges
\* never transmit them into callees, even when a callee is independently decoded.
Preds(a) == {p \in decoded : \E e \in LocalGraph : e.src = p /\ e.dst = a}
\* Join all predecessor outputs and, for a root, its unknown entry origins.
\* A root with a back edge keeps both entry and loop-derived possibilities.
\* A join combines alternatives instead of selecting an execution path.
Incoming(a) ==
  (IF a \in EntryPoints THEN EntryDefs(a) ELSE {})
  \cup UNION {Out(p) : p \in Preds(a)}

\* Add facts at one decoded instruction only when new definitions exist.
\* EXCEPT changes that address's set while preserving all other keys.
\* Scheduling is nondeterministic: a node can be processed before predecessors
\* stabilize, then revisited when they acquire additional facts.
\*
\* Out removes killed origins, but its kill set is fixed by Insn. Therefore
\* its transfer is monotone: growing an input cannot shrink the output.
\* Union updates from bottom (empty sets) converge to the least fixed point
\* over the frozen finite graph, including loops, regardless of update order.
Propagate(a) ==
  /\ phase = "dataflow" /\ a \in decoded
  /\ ~(Incoming(a) \subseteq reaching[a])
  /\ reaching' = [reaching EXCEPT ![a] = @ \cup Incoming(a)]
  /\ UNCHANGED <<phase, pending, visited, decoded, provenance, edges,
                 obligations, slice>>

\* Every decoded node must satisfy its equation exactly before slicing starts.
\* This is a global condition, not just one node failing to gain new facts.
DataflowFixed == \A a \in decoded : reaching[a] = Incoming(a)

\* Initialize the slice with requested seeds that have decoded instructions.
\* Missing seeds are not invented as nodes; MissingSliceSeeds exposes them.
\* After this phase boundary, both graph and reaching definitions stay fixed.
FinishDataflow ==
  /\ phase = "dataflow" /\ DataflowFixed
  /\ phase' = "slice"
  /\ slice' = SliceSeeds \cap decoded
  /\ UNCHANGED <<pending, visited, decoded, provenance, edges,
                 obligations, reaching>>

\* Instruction-level backward DATA slice. Control dependencies are deliberately
\* separate; this slice is not a claim of path feasibility or a full program slice.
\* PHASE 3: BACKWARD DATA-SLICE CLOSURE
\* ==================================
\* Select reaching definitions for locations read by a. Unknown entry origins
\* are excluded because they are inputs, not producer instructions. They remain
\* available in reaching[a] for a report that displays unknown dependencies.
Dependencies(a) ==
  {d \in reaching[a] : d.loc \in Insn[a].uses /\ d.origin = "instruction"}
\* Collect producer instruction addresses for ALL current slice members.
\* Here "predecessor" means a data producer, not necessarily an adjacent CFG node.
SlicePredecessors == UNION {{d.site : d \in Dependencies(a)} : a \in slice}

\* Grow by one dependency layer while retaining every existing slice member.
\* If instruction 30 reads a value defined at 20, and 20 reads a value defined
\* at 10, the seed {30} expands to {20,30}, then {10,20,30}. Cyclic dependencies
\* stop adding nodes after all their members are included; no recursive walk
\* or assumption of an acyclic graph is needed.
ExpandSlice ==
  /\ phase = "slice" /\ ~(SlicePredecessors \subseteq slice)
  /\ slice' = slice \cup SlicePredecessors
  /\ UNCHANGED <<phase, pending, visited, decoded, provenance, edges,
                 obligations, reaching>>

\* Closure means every known instruction producer of a sliced use is included.
\* Next has no action enabled at done. A result with nonempty obligations is
\* still a completed partial analysis, not a stalled analyzer.
FinishSlice ==
  /\ phase = "slice" /\ SlicePredecessors \subseteq slice
  /\ phase' = "done"
  /\ UNCHANGED <<pending, visited, decoded, provenance, edges,
                 obligations, reaching, slice>>

\* WHOLE BEHAVIOR AND CHECKED PROPERTIES
\* ====================================
\* Any enabled action may be chosen. Phase guards prevent discovery,
\* propagation and slicing from interleaving. No worklist order is prescribed.
Next == (\E a \in Addresses : Visit(a)) \/ FinishRecovery
        \/ (\E a \in Addresses : Propagate(a)) \/ FinishDataflow
        \/ ExpandSlice \/ FinishSlice

\* [][Next]_vars permits either a Next step or an unchanged-state stutter.
\* WF_vars(Next) excludes endless stuttering while progress remains enabled.
\* Aggregate fairness suffices here: every real step grows a bounded set or
\* advances the phase. Infinite real work elsewhere cannot starve one pending
\* item, because there cannot be infinitely many such real steps. At done,
\* Next is disabled and infinite stuttering is permitted.
\*
\* TLC checks this fair behavior with Terminates. Documented Apalache bounded
\* safety runs instead use Init/Next via the instance wrappers. Passing those
\* finite checks does not establish the unbounded liveness property.
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

\* State-shape invariant: valid tags, domains, fields and location identities.
\* It alone does not justify CFG edges or prove definition reachability; the
\* subsequent invariants constrain bookkeeping and transfer-equation results.
TypeOK ==
  /\ phase \in Phases
  /\ pending \subseteq Addresses /\ visited \subseteq Addresses
  /\ decoded \subseteq Addresses
  \* Fieldwise checks avoid materializing Cartesian products of record fields
  \* in the SMT encoding. DOMAIN checks retain the exact record/function shape.
  /\ DOMAIN provenance = Addresses
  /\ \A a \in Addresses : provenance[a] \in Sources
  /\ \A e \in edges :
       /\ DOMAIN e = {"src", "dst", "kind"}
       /\ e.src \in Addresses /\ e.dst \in Addresses /\ e.kind \in EdgeKinds
  /\ \A o \in obligations :
       /\ DOMAIN o = {"site", "reason"}
       /\ o.site \in Addresses /\ o.reason \in Reasons
  /\ DOMAIN reaching = Addresses
  /\ \A a \in Addresses : \A d \in reaching[a] :
       /\ DOMAIN d = {"loc", "site", "origin"}
       /\ d.loc \in Locations /\ d.site \in Addresses
       /\ d.origin \in {"entry", "instruction"}
  /\ slice \subseteq decoded

\* Recompute expected recovery products from successful and failed visits.
\* These operators check for missing or fabricated facts; they do not update
\* the graph or obligations. ExpectedEdges includes both local and call records.
ExpectedEdges == UNION {InstructionEdges(a) : a \in decoded}
ExpectedObligations ==
  UNION {DecodeObligations(a) : a \in decoded}
  \cup {Obligation(a, Failure(a)) : a \in visited \ decoded}

\* Every visited start is classified consistently with the fixed inputs.
\* pending and visited partition the roots plus all discovered LOCAL targets:
\* nothing discovered is lost, and nothing outside that discovery is queued.
\* Graph products and provenance match the visits exactly. Leaving recovery
\* requires an empty worklist, but unresolved-information obligations may remain.
RecoveryInvariant ==
  /\ decoded = {a \in visited : CanDecode(a)}
  /\ pending \cap visited = {}
  /\ pending \cup visited = EntryPoints \cup {e.dst : e \in LocalGraph}
  /\ edges = ExpectedEdges
  /\ obligations = ExpectedObligations
  /\ \A a \in decoded : provenance[a] = Source(a)
  /\ \A a \in Addresses \ decoded : provenance[a] = "unavailable"
  /\ (phase # "recover" => pending = {})

\* Undecoded starts have no data-flow facts. A decoded node's approximation
\* may lag behind Incoming but cannot exceed it, and every origin must identify
\* a possible writer or a declared entry input. This invariant alone does not
\* prove leastness; bottom initialization and monotone propagation supply that
\* argument for the fixed point actually reached by the algorithm.
DefinitionInvariant ==
  /\ \A a \in Addresses \ decoded : reaching[a] = {}
  /\ \A a \in decoded :
       /\ reaching[a] \subseteq Incoming(a)
       /\ \A d \in reaching[a] :
            IF d.origin = "instruction"
            THEN d.site \in decoded /\ d.loc \in Insn[d.site].mayDefs
            ELSE d.site \in EntryPoints /\ d.loc \in Locations

\* Phase-sensitive postconditions: slicing sees stable data-flow facts,
\* retains all decoded seeds, and is closed under data dependencies at done.
\* These claims do not imply path feasibility, inclusion of control dependencies,
\* absence of recovery gaps, or identification of the root cause of a crash.
ResultInvariant ==
  /\ (phase \in {"slice", "done"} => DataflowFixed)
  /\ (phase \in {"slice", "done"} => SliceSeeds \cap decoded \subseteq slice)
  /\ (phase = "done" => SlicePredecessors \subseteq slice)

\* Completion is algorithm termination, NOT a certificate that all actual
\* machine-code paths were recovered. ScopeClosed is relative to the inputs.
\* Even with no obligations, a certified call edge need not have a decoded
\* callee. Omitted exception/unwind behavior is outside the local scope.
\* This predicate therefore must not be advertised as whole-program completeness.
ScopeClosed == phase = "done" /\ obligations = {}
\* Seeds missing from the decoded graph, due either to decoding failure or to
\* being unreachable from the supplied roots. ScopeClosed may hold with this
\* set nonempty, so a caller should inspect both when judging its result.
MissingSliceSeeds == SliceSeeds \ decoded
\* Eventually the ANALYZER finishes; it need not resolve every obligation.
\* Finite domains bound visits, definition additions and slice additions;
\* Spec's fairness prevents enabled progress from being postponed forever.
Terminates == <> (phase = "done")

=============================================================================
