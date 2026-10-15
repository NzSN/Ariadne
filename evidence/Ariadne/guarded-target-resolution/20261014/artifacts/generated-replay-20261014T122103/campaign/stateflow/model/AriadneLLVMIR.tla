------------------------- MODULE AriadneLLVMIR -------------------------
EXTENDS AriadneTypes, Naturals, FiniteSets

\* Native LLVM IR analysis model
\* =============================
\* This machine consumes a normalized view of LLVM IR supplied directly as
\* bitcode or textual IR. It does NOT lift machine code, reconstruct compiler
\* IR, or claim correspondence with a binary. ArtifactId identifies the exact
\* IR artifact whose functions, blocks, instructions and SSA values are modeled.
\*
\* Control flow and data flow deliberately have different node domains:
\*   - the authoritative CFG contains basic blocks and terminator-derived edges;
\*   - dependency and slice nodes are LLVM instructions.
\* Phi operands retain their predecessor block, while ordinary SSA uses are
\* represented by Uses. MemoryPreds is a conservative adapter-supplied relation;
\* LLVM SSA alone does not determine which stores or calls may reach a load.
\*
\* This model analyzes one LLVM function per request. Calls are visible in a
\* separate call graph and do not become intraprocedural CFG edges. Interprocedural
\* call/return matching and machine-address correlation require separate models.

CONSTANT
  \* @type: $artifactId;
  ArtifactId
CONSTANT
  \* @type: $moduleId;
  ModuleId
CONSTANT
  \* @type: $functionId;
  FunctionId
CONSTANT
  \* @type: Bool;
  VerifiedIR
CONSTANT
  \* @type: Set($blockId);
  Blocks
CONSTANT
  \* @type: $blockId;
  EntryBlock
CONSTANT
  \* @type: Set($instructionId);
  Instructions
CONSTANT
  \* @type: $instructionId -> $blockId;
  BlockOf
CONSTANT
  \* @type: $instructionId -> Int;
  InstructionIndex
CONSTANT
  \* @type: $blockId -> $instructionId;
  Terminator
CONSTANT
  \* @type: $blockId -> {kind: $terminatorKind,
  \*             successors: Set({dst: $blockId, kind: $edgeKind})};
  TermInfo
CONSTANT
  \* @type: Set($valueId);
  Values
CONSTANT
  \* @type: $valueId -> $valueKind;
  ValueKind
CONSTANT
  \* @type: $valueId -> $instructionId;
  DefSite
CONSTANT
  \* @type: $instructionId -> Set($valueId);
  Uses
CONSTANT
  \* @type: Set($instructionId);
  PhiNodes
CONSTANT
  \* @type: $instructionId -> Set({pred: $blockId, value: $valueId});
  PhiIncoming
CONSTANT
  \* @type: $instructionId -> Set($instructionId);
  MemoryPreds
CONSTANT
  \* @type: Set($instructionId);
  CallSites
CONSTANT
  \* @type: Set($calleeId);
  Callees
CONSTANT
  \* @type: $instructionId -> Set($calleeId);
  CallTargets
CONSTANT
  \* @type: Set($instructionId);
  CompleteCalls
CONSTANT
  \* @type: Set({site: $instructionId, reason: $obligationReason});
  AdapterObligations
CONSTANT
  \* @type: Set($instructionId);
  SliceSeeds

TerminatorKinds ==
  {"br", "switch", "indirectbr", "invoke", "callbr", "ret", "resume",
   "unreachable", "catchswitch", "catchret", "cleanupret"}
ControlEdgeKinds ==
  {"next", "true", "false", "case", "default", "indirect", "normal",
   "unwind", "fallthrough", "catch", "cleanup"}
ExitTerminatorKinds == {"ret", "resume", "unreachable"}
ValueKinds == {"instruction", "argument", "constant", "global", "external"}
ObligationReasons ==
  {"unsupported-instruction", "incomplete-semantics", "unknown-memory-alias",
   "call-targets", "unmodeled-exception", "unmodeled-system-call",
   "unmodeled-concurrency"}
Phases == {"slice", "done"}

\* Artifact-scoped identity. Textual names and instruction ordinals are only
\* meaningful inside the exact supplied artifact and function.
IRIdentity(i) ==
  [artifact |-> ArtifactId, module |-> ModuleId, function |-> FunctionId,
   block |-> BlockOf[i], instruction |-> i]

\* The normalized adapter gives each terminator its explicitly represented
\* successors. Edge construction is therefore derivation, not heuristic CFG
\* recovery. Multiple typed edges between the same blocks remain distinct.
\* @type: ($blockId, {dst: $blockId, kind: $edgeKind})
\*          => {src: $blockId, dst: $blockId, kind: $edgeKind};
ControlEdge(b, successor) ==
  [src |-> b, dst |-> successor.dst, kind |-> successor.kind]
ControlGraph ==
  UNION {{ControlEdge(b, successor) : successor \in TermInfo[b].successors}
         : b \in Blocks}
PredBlocks(b) == {edge.src : edge \in {e \in ControlGraph : e.dst = b}}

\* Calls are graph-visible without becoming block CFG edges. CompleteCalls is
\* the adapter certificate that all possible callees in this scope are listed.
\* @type: ($instructionId, $calleeId)
\*          => {site: $instructionId, callee: $calleeId, kind: $edgeKind};
CallEdge(i, callee) == [site |-> i, callee |-> callee, kind |-> "call"]
CallGraph ==
  UNION {{CallEdge(i, callee) : callee \in CallTargets[i]} : i \in CallSites}
CallObligations ==
  {[site |-> i, reason |-> "call-targets"] : i \in CallSites \ CompleteCalls}
Obligations == AdapterObligations \cup CallObligations

\* SSA dependencies are direct: instruction-defined operands name their unique
\* producer. Argument, constant, global and external values are inputs, not
\* fabricated instruction nodes. MemoryPreds conservatively supplies additional
\* producers for effects not represented by ordinary SSA def-use chains.
SSAProducers(i) ==
  {DefSite[v] : v \in {value \in Uses[i] : ValueKind[value] = "instruction"}}
DependencyPreds(i) == SSAProducers(i) \cup MemoryPreds[i]

\* Input contract
\* --------------
\* VerifiedIR means an LLVM verifier accepted the source artifact. This model
\* still checks the normalized graph facts it consumes. It does not reimplement
\* LLVM's full verifier, type system, dominance rules, or opcode semantics.
InputContract ==
  /\ ArtifactId # "" /\ ModuleId # "" /\ FunctionId # ""
  /\ VerifiedIR
  /\ IsFiniteSet(Blocks) /\ Blocks # {} /\ EntryBlock \in Blocks
  /\ IsFiniteSet(Instructions) /\ Instructions # {}
  /\ DOMAIN BlockOf = Instructions
  /\ DOMAIN InstructionIndex = Instructions
  /\ \A i \in Instructions :
       /\ BlockOf[i] \in Blocks
       /\ InstructionIndex[i] >= 0
  /\ \A i, j \in Instructions :
       (BlockOf[i] = BlockOf[j] /\ InstructionIndex[i] = InstructionIndex[j])
       => i = j
  /\ DOMAIN Terminator = Blocks
  /\ DOMAIN TermInfo = Blocks
  /\ \A b \in Blocks :
       /\ Terminator[b] \in Instructions
       /\ BlockOf[Terminator[b]] = b
       /\ TermInfo[b].kind \in TerminatorKinds
       /\ \A successor \in TermInfo[b].successors :
            /\ successor.dst \in Blocks
            /\ successor.kind \in ControlEdgeKinds
       /\ \A i \in Instructions :
            BlockOf[i] = b => InstructionIndex[i] <= InstructionIndex[Terminator[b]]
       /\ (TermInfo[b].kind \in ExitTerminatorKinds
            => TermInfo[b].successors = {})
       /\ (TermInfo[b].kind = "invoke" =>
            /\ Cardinality({s \in TermInfo[b].successors : s.kind = "normal"}) = 1
            /\ Cardinality({s \in TermInfo[b].successors : s.kind = "unwind"}) = 1)
  /\ IsFiniteSet(Values)
  /\ DOMAIN ValueKind = Values
  /\ DOMAIN DefSite = Values
  /\ \A v \in Values :
       /\ ValueKind[v] \in ValueKinds
       /\ (ValueKind[v] = "instruction" => DefSite[v] \in Instructions)
  /\ \A v, w \in Values :
       (ValueKind[v] = "instruction" /\ ValueKind[w] = "instruction"
        /\ DefSite[v] = DefSite[w]) => v = w
  /\ DOMAIN Uses = Instructions
  /\ \A i \in Instructions : Uses[i] \subseteq Values
  /\ PhiNodes \subseteq Instructions
  /\ DOMAIN PhiIncoming = Instructions
  /\ \A i \in Instructions \ PhiNodes : PhiIncoming[i] = {}
  /\ \A phi \in PhiNodes :
       /\ {incoming.pred : incoming \in PhiIncoming[phi]}
            = PredBlocks(BlockOf[phi])
       /\ {incoming.value : incoming \in PhiIncoming[phi]} = Uses[phi]
       /\ \A incoming \in PhiIncoming[phi] :
            /\ incoming.pred \in Blocks
            /\ incoming.value \in Values
       /\ \A x, y \in PhiIncoming[phi] : x.pred = y.pred => x = y
       /\ \A i \in Instructions \ PhiNodes :
            BlockOf[i] = BlockOf[phi]
              => InstructionIndex[phi] < InstructionIndex[i]
  /\ DOMAIN MemoryPreds = Instructions
  /\ \A i \in Instructions : MemoryPreds[i] \subseteq Instructions
  /\ CallSites \subseteq Instructions
  /\ IsFiniteSet(Callees)
  /\ DOMAIN CallTargets = Instructions
  /\ \A i \in Instructions : CallTargets[i] \subseteq Callees
  /\ \A i \in Instructions \ CallSites : CallTargets[i] = {}
  /\ CompleteCalls \subseteq CallSites
  /\ \A obligation \in AdapterObligations :
       /\ obligation.site \in Instructions
       /\ obligation.reason \in ObligationReasons \ {"call-targets"}
  /\ SliceSeeds \subseteq Instructions

ASSUME InputContract

VARIABLE
  \* @type: $analysisPhase;
  phase
VARIABLE
  \* @type: Set($instructionId);
  slice
vars == <<phase, slice>>

Init ==
  /\ phase = "slice"
  /\ slice = SliceSeeds

SlicePredecessors == UNION {DependencyPreds(i) : i \in slice}

ExpandSlice ==
  /\ phase = "slice"
  /\ ~(SlicePredecessors \subseteq slice)
  /\ slice' = slice \cup SlicePredecessors
  /\ UNCHANGED phase

FinishSlice ==
  /\ phase = "slice"
  /\ SlicePredecessors \subseteq slice
  /\ phase' = "done"
  /\ UNCHANGED slice

Next == ExpandSlice \/ FinishSlice
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

TypeOK ==
  /\ InputContract
  /\ phase \in Phases
  /\ slice \subseteq Instructions
  /\ \A edge \in ControlGraph :
       /\ DOMAIN edge = {"src", "dst", "kind"}
       /\ edge.src \in Blocks /\ edge.dst \in Blocks
       /\ edge.kind \in ControlEdgeKinds
  /\ \A edge \in CallGraph :
       /\ DOMAIN edge = {"site", "callee", "kind"}
       /\ edge.site \in CallSites /\ edge.callee \in Callees
       /\ edge.kind = "call"
  /\ \A obligation \in Obligations :
       /\ DOMAIN obligation = {"site", "reason"}
       /\ obligation.site \in Instructions
       /\ obligation.reason \in ObligationReasons

\* These restate the important adapter correspondences as safety properties so
\* concrete fixtures exercise them even when assumptions in instantiated modules
\* are not enforced by a model checker.
CFGInvariant ==
  /\ \A edge \in ControlGraph :
       edge \in {ControlEdge(edge.src, successor)
                  : successor \in TermInfo[edge.src].successors}
  /\ \A b \in Blocks :
       {edge \in ControlGraph : edge.src = b}
         = {ControlEdge(b, successor) : successor \in TermInfo[b].successors}
  /\ \A phi \in PhiNodes :
       {incoming.pred : incoming \in PhiIncoming[phi]}
         = PredBlocks(BlockOf[phi])

DependencyInvariant ==
  /\ \A i \in Instructions : DependencyPreds(i) \subseteq Instructions
  /\ \A i \in Instructions :
       SSAProducers(i)
         = {DefSite[v]
              : v \in {value \in Uses[i] : ValueKind[value] = "instruction"}}

ResultInvariant ==
  /\ SliceSeeds \subseteq slice
  /\ (phase = "done" => SlicePredecessors \subseteq slice)

Terminates == <> (phase = "done")

=============================================================================
