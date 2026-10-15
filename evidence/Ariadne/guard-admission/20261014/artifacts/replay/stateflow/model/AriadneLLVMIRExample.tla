---------------------- MODULE AriadneLLVMIRExample ----------------------
EXTENDS AriadneTypes, Naturals, FiniteSets

\* Native LLVM IR fixture with a conditional diamond, a phi join, possible
\* memory producers and an incomplete indirect call. The input is already LLVM
\* IR; no machine-code lifting or original-IR reconstruction is represented.
VARIABLES
  \* @type: $analysisPhase;
  phase,
  \* @type: Set($instructionId);
  slice

Blocks == {"entry", "left", "right", "join"}
Instructions ==
  {"entry.br",
   "left.def", "left.store", "left.br",
   "right.def", "right.store", "right.br",
   "join.phi", "join.call", "join.load", "join.combine", "join.ret"}
Values ==
  {"arg.cond", "arg.ptr", "left.value", "right.value", "joined.value",
   "loaded.value", "result.value"}

\* @type: $instructionId -> $blockId;
InstructionBlocks == [i \in Instructions |->
  CASE i = "entry.br" -> "entry"
    [] i \in {"left.def", "left.store", "left.br"} -> "left"
    [] i \in {"right.def", "right.store", "right.br"} -> "right"
    [] OTHER -> "join"]

\* @type: $instructionId -> Int;
Indices == [i \in Instructions |->
  CASE i = "entry.br" -> 0
    [] i \in {"left.def", "right.def", "join.phi"} -> 0
    [] i \in {"left.store", "right.store", "join.call"} -> 1
    [] i \in {"left.br", "right.br", "join.load"} -> 2
    [] i = "join.combine" -> 3
    [] OTHER -> 4]

\* @type: $blockId -> $instructionId;
Terminators == [b \in Blocks |->
  CASE b = "entry" -> "entry.br"
    [] b = "left" -> "left.br"
    [] b = "right" -> "right.br"
    [] OTHER -> "join.ret"]

\* @type: ($blockId, $edgeKind) => {dst: $blockId, kind: $edgeKind};
Successor(dst, kind) == [dst |-> dst, kind |-> kind]
\* @type: $blockId -> {kind: $terminatorKind,
\*             successors: Set({dst: $blockId, kind: $edgeKind})};
TerminatorsInfo == [b \in Blocks |->
  CASE b = "entry" ->
         [kind |-> "br",
          successors |-> {Successor("left", "true"),
                           Successor("right", "false")}]
    [] b = "left" ->
         [kind |-> "br", successors |-> {Successor("join", "next")}]
    [] b = "right" ->
         [kind |-> "br", successors |-> {Successor("join", "next")}]
    [] OTHER -> [kind |-> "ret", successors |-> {}]]

\* @type: $valueId -> $valueKind;
KindsOfValues == [v \in Values |->
  IF v \in {"arg.cond", "arg.ptr"} THEN "argument" ELSE "instruction"]

\* DefSite is total because the normalized interface is a total function. Its
\* entries for arguments are ignored; only instruction-kind values have sites.
\* @type: $valueId -> $instructionId;
DefinitionSites == [v \in Values |->
  CASE v = "left.value" -> "left.def"
    [] v = "right.value" -> "right.def"
    [] v = "joined.value" -> "join.phi"
    [] v = "loaded.value" -> "join.load"
    [] v = "result.value" -> "join.combine"
    [] OTHER -> "entry.br"]

\* @type: $instructionId -> Set($valueId);
InstructionUses == [i \in Instructions |->
  CASE i = "entry.br" -> {"arg.cond"}
    [] i = "left.store" -> {"arg.ptr", "left.value"}
    [] i = "right.store" -> {"arg.ptr", "right.value"}
    [] i = "join.phi" -> {"left.value", "right.value"}
    [] i = "join.call" -> {"joined.value"}
    [] i = "join.load" -> {"arg.ptr"}
    [] i = "join.combine" -> {"joined.value", "loaded.value"}
    [] i = "join.ret" -> {"result.value"}
    [] OTHER -> {}]

\* @type: ($blockId, $valueId) => {pred: $blockId, value: $valueId};
Incoming(pred, value) == [pred |-> pred, value |-> value]
\* @type: $instructionId -> Set({pred: $blockId, value: $valueId});
PhiInputs == [i \in Instructions |->
  IF i = "join.phi"
  THEN {Incoming("left", "left.value"), Incoming("right", "right.value")}
  ELSE {}]

\* The load may observe either branch's store or effects of the unknown call.
\* @type: $instructionId -> Set($instructionId);
MemoryDependencies == [i \in Instructions |->
  IF i = "join.load"
  THEN {"left.store", "right.store", "join.call"}
  ELSE {}]

\* @type: $instructionId -> Set($calleeId);
Targets == [i \in Instructions |->
  IF i = "join.call" THEN {"possible.callee"} ELSE {}]

\* @type: Set({site: $instructionId, reason: $obligationReason});
NoAdapterObligations == {}

Engine == INSTANCE AriadneLLVMIR WITH
  ArtifactId <- "fixture.bc.sha256",
  ModuleId <- "fixture-module",
  FunctionId <- "fixture-function",
  VerifiedIR <- TRUE,
  Blocks <- Blocks,
  EntryBlock <- "entry",
  Instructions <- Instructions,
  BlockOf <- InstructionBlocks,
  InstructionIndex <- Indices,
  Terminator <- Terminators,
  TermInfo <- TerminatorsInfo,
  Values <- Values,
  ValueKind <- KindsOfValues,
  DefSite <- DefinitionSites,
  Uses <- InstructionUses,
  PhiNodes <- {"join.phi"},
  PhiIncoming <- PhiInputs,
  MemoryPreds <- MemoryDependencies,
  CallSites <- {"join.call"},
  Callees <- {"possible.callee"},
  CallTargets <- Targets,
  CompleteCalls <- {},
  AdapterObligations <- NoAdapterObligations,
  SliceSeeds <- {"join.ret"}

Init == Engine!Init
Next == Engine!Next
Spec == Engine!Spec
Terminates == Engine!Terminates

ExpectedControlGraph ==
  {[src |-> "entry", dst |-> "left", kind |-> "true"],
   [src |-> "entry", dst |-> "right", kind |-> "false"],
   [src |-> "left", dst |-> "join", kind |-> "next"],
   [src |-> "right", dst |-> "join", kind |-> "next"]}
ExpectedSlice ==
  {"left.def", "left.store", "right.def", "right.store", "join.phi",
   "join.call", "join.load", "join.combine", "join.ret"}

FixtureInvariant ==
  /\ Engine!IRIdentity("join.phi") =
       [artifact |-> "fixture.bc.sha256", module |-> "fixture-module",
        function |-> "fixture-function", block |-> "join",
        instruction |-> "join.phi"]
  /\ Engine!ControlGraph = ExpectedControlGraph
  /\ Engine!CallGraph =
       {[site |-> "join.call", callee |-> "possible.callee", kind |-> "call"]}
  /\ Engine!Obligations =
       {[site |-> "join.call", reason |-> "call-targets"]}
  /\ (phase = "done" => slice = ExpectedSlice)

Safety ==
  Engine!TypeOK /\ Engine!CFGInvariant /\ Engine!DependencyInvariant
  /\ Engine!ResultInvariant /\ FixtureInvariant

\* A bounded counterexample to this predicate witnesses completion.
NotDone == phase # "done"

=============================================================================
