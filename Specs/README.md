# Ariadne formal model

`AriadneTypes.tla` defines semantic Apalache aliases shared across the suite.
`AriadneMachineCommon.tla` defines stateless knowledge shared by the machine
models. `Ariadne.tla` specifies the machine-code analysis engine for binary and
crash-dump inputs, while `AriadneMachineState.tla` consumes its frozen local CFG.
`AriadneLLVMIR.tla` separately specifies analysis of verified LLVM IR supplied
directly as `.ll` or `.bc`. The intended implementation is C++23, Bazel, and a
pinned LLVM release; no analyzer implementation is introduced here.

## Shared semantic types

`AriadneTypes.tla` is the single alias catalogue for specification-level roles.
Machine aliases cover addresses, snapshots, locations, instruction and edge
kinds, byte sources, definition origins, abstract states and values, machine
statuses, and terminal outcomes. LLVM IR aliases cover artifacts, modules,
functions, blocks, instructions, values, value kinds, terminator kinds, and
callees. Analysis phases and obligation reasons are shared where their role is
representation-independent.

Every semantic string position uses a meaningful `$alias` in Snowcat
annotations. `Str` remains only as the underlying representation in alias
declarations. These aliases are documentary and transparent, not nominal
newtypes; set-membership contracts still constrain their permitted values.

## Shared machine contract

`AriadneMachineCommon.tla` owns only knowledge that has the same meaning in CFG
recovery and post-recovery state propagation:

- local machine edge-kind vocabulary;
- the snapshot-scoped, finite, nonempty, nonnegative VA contract;
- snapshot-plus-VA external identity;
- the typed structural edge constructor; and
- well-formed normalized `uses`, `mustDefs`, and `mayDefs` sets.

The module has no constants, variables, phases, transitions, obligations, or
analysis policy. `Ariadne.tla` retains discovery, byte provenance, reaching
definitions, and slicing. `AriadneMachineState.tla` retains abstract valuations,
semantic transitions, fixed-point state propagation, and edge-feasibility
classification. Compatibility aliases in the consumers preserve their existing
public operator names while delegating definitions to the common module.

## Native LLVM IR model

The LLVM IR model consumes one normalized, verifier-accepted function from one
artifact. It does not lift machine code, reconstruct compiler IR, or assert that
an IR instruction corresponds to a machine address. Its identity is the tuple
of `ArtifactId`, `ModuleId`, `FunctionId`, block, and instruction.

The representation has two node domains:

- Basic blocks form the authoritative CFG. `ControlGraph` is derived exactly
  from each terminator's typed successors.
- LLVM instructions form the dependency and slice graph. Direct SSA uses name
  their unique instruction producers; argument, constant, global, and external
  values remain non-instruction inputs.

Phi inputs retain both predecessor block and incoming value. The contract
requires exactly one incoming record per CFG predecessor and keeps all incoming
values for conservative slicing. `MemoryPreds` is a trusted conservative input
for dependencies not represented by ordinary SSA def-use. Passing this model
does not validate an alias analysis or LLVM opcode semantics.

Calls occupy a separate `CallGraph`; they do not become intraprocedural block
CFG edges. Incomplete call targets produce a `call-targets` obligation. Adapter
obligations also preserve unsupported instructions, incomplete semantics,
unknown memory aliases, and unmodeled exceptional, system, or concurrent
behavior. A completed slice may therefore remain partial.

The LLVM IR state machine starts with the requested instruction seeds, adds SSA
and memory producers until dependency closure, and then reaches `done`. Its
properties check normalized input types, exact terminator-derived control
edges, phi/CFG correspondence, valid dependency producers, slice closure, and
fair termination. Interprocedural call/return matching, path feasibility, and
machine/IR correlation remain outside this model.

## Abstract machine-state model

`AriadneMachineState.tla` consumes the frozen decoded-node set and `LocalGraph`
produced by machine recovery. It does not discover instructions, change edges,
or follow `call` edges. A returning call summary is represented by the existing
local `summary` edge and an adapter-supplied semantic transition.

The model uses a finite collecting semantics. `statesAt[a]` contains abstract
state identities that may hold before instruction `a`. Each identity has a
`Valuation` mapping normalized register, flag, or memory locations to nonempty
finite value sets, plus a status. Separate identities can preserve correlations
that a single pointwise join would lose.

`StateSteps` is a trusted nondeterministic relation from a running before-state
through one instruction and one existing structural edge to a running
after-state. `TerminalTransitions` records faults, returns, and stops. Every
transition must preserve locations outside the instruction's `MayDefs`; the
model checks this frame property but does not prove the supplied transitions
faithfully implement an ISA.

Entry states are attached only to declared entry points. Propagation repeatedly
adds after-states along local structural edges until a fixed point. The graph is
never filtered. Instead, the final result partitions structural edges into:

- `FeasibleEdges`, witnessed by a reached semantic transition;
- `ProvablyInfeasibleEdges`, absent at a reached site whose semantics adapter
  supplied a trusted completeness certificate; and
- `UnknownFeasibilityEdges`, where reachability or semantic completeness is
  insufficient for either conclusion.

Missing semantic completeness produces an `incomplete-semantics` obligation.
Additional adapter obligations preserve unknown memory, unmodeled exceptions,
system calls, and concurrency. A crash-time state may seed its exact captured
instruction; the model does not authorize treating it as an earlier state or
using it to rewrite the structural CFG.

## Scope and abstraction boundary

The model specifies instruction-level CFG recovery, forward may-reaching
definitions, and a backward data slice over a finite analysis request. It models
the analyzer's execution, not execution of the analyzed program.

An address is the virtual address (VA) of a candidate instruction start in one
fixed address-space snapshot, identified by the nonempty `SnapshotId`. VAs are
nonnegative integers; architecture-specific address widths remain an adapter
constraint.
Apalache annotations represent addresses as the shared `$address` alias backed
by `Int`, and location identifiers as `Str`; record fields and function/set
element types are explicitly declared. The alias documents intent but is not a
nominal type, so the nonnegative-VA contract remains semantically necessary.
`Insn` is a trusted semantic description supplied by a decoder/semantics adapter.
`Decodable` identifies successful decodes. Thus the model verifies what the
engine does with decoded instructions; it does not verify x86 decoding, LLVM,
instruction semantics, PE/minidump parsing, or PDB matching.

The preserved information is instruction identity, typed local and call
edges, byte provenance, reads, may-writes, must-writes, and
explicit unresolved obligations. Concrete bytes, instruction widths, numeric
register values, flag equations, memory contents, thread scheduling, and timing
are abstracted away. A later semantic refinement can add those details.

The graph has one node per decoded instruction. Edges may also reference
unavailable/invalid local targets or callees outside local discovery. Local
decode failures produce obligations; an unvisited callee alone does not.
Coalescing nodes into basic blocks is a presentation/refinement step, not
modeled here.

## Input contract

| Input | Meaning |
| --- | --- |
| `SnapshotId` | Opaque identity of the one immutable address-space snapshot shared by all inputs |
| `Addresses` | Finite candidate instruction VAs, including every represented target and continuation, even when its bytes are unavailable |
| `EntryPoints` | Nonempty set of roots to analyze; successor discovery does not infer predecessors of arbitrary crash addresses |
| `SliceSeeds` | Instructions whose input dependencies should be traced |
| `InputKind` | `binary` or `dump` |
| `Captured` | Starts with a complete captured instruction-byte span |
| `FileBacked` | Starts with a complete byte span supplied by the binary provider |
| `TrustedFallback` | File-backed starts certified suitable for use when dump bytes are absent |
| `Decodable` | Starts whose selected bytes decode successfully |
| `Insn` | Instruction kind, continuation, known targets, target-completeness certificate, uses, must-defs, and may-defs |
| `Locations` | Finite normalized register/flag/memory locations for this request |

### Virtual addresses and storage mapping

`EntryPoints` contains VAs at which discovery begins, not coordinate origins.
Every address-bearing field uses this same VA domain, including slice seeds,
instruction continuations/targets, edges, provenance keys, and definition sites.
`AddressSpaceContract` requires a nonempty snapshot identity and nonnegative
VAs. It appears both in `ASSUME` and in `TypeOK`, so fixture safety checks
exercise it even when instantiated-module assumptions are not enforced by TLC.
No implicit rebasing occurs. `AddressIdentity(a)` exposes the pair
`[snapshot |-> SnapshotId, va |-> a]` for identifying addresses across requests.
The adapter must assign distinct identities to distinct address-space snapshots;
a matching VA alone does not identify code across processes or capture times.

The provider contract is `resolve(snapshot, VA, length) -> bytes + provenance`
or unavailability. A dump provider locates a captured virtual-memory region;
a binary provider uses the selected module load base and section/segment layout
to locate file bytes. `VA - loadBase` is a module-relative offset, not generally
a file offset, and some virtual spans have no file backing. Standalone binaries
require a chosen virtual load layout. Compact internal node IDs are permitted
in an implementation only with a mapping back to these semantic VAs.

The model consumes the provider's whole-instruction availability and semantic
summaries. It does not implement or verify region tables, storage offsets,
byte lengths, relocation processing, or snapshot-identity uniqueness. All such
inputs must describe the same immutable snapshot. Successors remain explicit;
integer ordering or adjacency does not imply a control-flow edge.

For binary input, file bytes are used. For dump input, captured bytes take
precedence; file fallback requires `TrustedFallback`. File availability alone
does not authorize fallback. Certification must account for matching image
identity, VA mapping, relocations, and possible runtime modifications. A
captured decode failure does not silently trigger file substitution.

Availability is abstracted at the whole-instruction-span level. Mixed-source
spans and overlapping instruction streams need a richer provider refinement.
JIT code can be represented through captured bytes without file backing.
Unknown destinations outside the finite address universe must remain unresolved;
they must not be silently discarded with `complete = TRUE`.

`Locations` must normalize architectural aliasing, such as EAX/RAX overlap, and
conservatively abstract memory aliases. `uses` must include dependencies needed
for the requested slice, including address operands. `mayDefs` includes every
possibly written location; only `mustDefs` kills prior definitions. The latter
must be a subset of the former. Inadequate decoder or alias summaries invalidate
any claimed semantic soundness even if TLC passes.

## Control-flow policy

| Instruction kind | Unified graph effect |
| --- | --- |
| Ordinary | One `next` edge |
| Conditional | Both `taken` and `fallthrough` edges |
| Direct jump | One `jump` edge |
| Indirect jump | Every supplied target, plus an obligation unless the target set is certified complete |
| Call | A `call` edge to each supplied callee target and a potentially returning `summary` edge to the continuation |
| Return / stop | Exit from the current analysis scope |

All edges live in the single mutable `edges` set. `LocalEdgeKinds` is an explicit
allowlist; `EdgeKinds` adds `call`. `LocalGraph` and `CallGraph` are filtered views,
not separately stored state. `InstructionEdges(a)` combines the local and call
edges supplied by an instruction; `LocalSuccessors(a)` filters that result before
queuing addresses. `Preds(a)` consults only `LocalGraph`.

For a call at A to F with continuation B:

```text
A --call----> F
A --summary-> B
```

| Consumer | Local edges, including `summary` | `call` edges |
| --- | --- | --- |
| Graph display/export | Included | Included |
| Local recovery worklist | Follow destination | Do not follow |
| Reaching definitions / backward data slice | Follow local data-flow equations | Do not transmit definitions |

Calls are opaque summaries. Callee destinations are not traversed automatically
and do not receive definitions across call edges, even if independently decoded
through another root or local path. An unknown call can use and
may-write all modeled locations with no must-writes. A precise summary may
narrow that effect only with evidence. A summary edge at a call expresses a
possibility, not a guarantee that the callee returns. An interprocedural model
would need call/return matching and a context policy.

This is a structural CFG: no edge is removed using crash-time registers. Path
feasibility, implicit exceptions, interrupts, unwind edges, nonlocal jumps,
concurrency, self-modifying code, and recorded execution history are outside this
model. `return` and `stop` are scope exits, not missing-target obligations.

## State transitions

1. `Init` queues the entry points and initializes empty results.
2. `Visit(a)` nondeterministically processes a queued address once. Successful
   decoding records provenance, local and call edges, and unresolved target
   obligations. Only local successors enter the worklist. Failure records
   `unavailable` or `decode-failed`.
3. `FinishRecovery` freezes the graph once the worklist is empty.
4. `Propagate(a)` adds reaching definitions until the data-flow fixed point.
5. `FinishDataflow` initializes the slice with decoded seeds.
6. `ExpandSlice` follows instruction definitions of locations used by slice
   members until closure; `FinishSlice` marks the request done.

For each decoded instruction `a`, reaching definitions represent values before
that instruction. The transfer equations are:

```text
OUT(a) = (IN(a) minus definitions of mustDefs(a)) union GEN(mayDefs(a))
IN(a)  = entry definitions, if a is a root
         union OUT(p) for every decoded local predecessor p
```

The implementation model starts at empty sets and applies monotone updates,
computing the least fixed point over the recovered graph. Entry definitions are
tagged separately from instruction definitions. They describe unknown incoming
values and remain available in reaching sets, but do not become slice nodes.

The slice is an instruction-level may-data-dependency closure. It includes all
uses of each included instruction, so it can overapproximate dependencies of a
particular output operand. It does not include control dependencies and is not
a path-feasibility proof. Partial graphs yield results relative to recovered
edges; an unresolved predecessor path can introduce additional definitions.

## Properties

| Property | Checked claim |
| --- | --- |
| `TypeOK` | The address-space contract holds (nonempty snapshot identity, nonnegative VAs), and every state component remains in its declared domain |
| `RecoveryInvariant` | Local-only worklist bookkeeping, exact unified edges/obligations, successful decodes, and byte provenance stay consistent |
| `DefinitionInvariant` | Definitions have valid origins and propagation never exceeds the current transfer equation |
| `ResultInvariant` | Slicing starts only at the data-flow fixed point, includes decoded seeds, and finishes closed under data dependencies |
| `FixtureResult` | Each concrete scenario has the independently specified final decoded set, slice, and obligations |
| `CallPolicy` (call fixture) | Call edges are visible, an independently analyzed callee receives no caller definitions, and a callee reachable only by call stays unvisited |
| `Terminates` | Every weakly fair behavior eventually reaches `done` |

Termination follows from the finite address/definition domains: each visit
consumes a previously unvisited address, each propagation strictly grows a
finite definition set, each slice expansion strictly grows a finite set, and
phase changes move forward. `WF_vars(Next)` prevents infinite stuttering while
work remains. Once done, stuttering is allowed.

`ScopeClosed` means done with no outstanding recovery obligations **relative to
this input contract and control-flow policy**. It is not proof that every real
execution path has been recovered. `MissingSliceSeeds` separately reports seeds
that were not decoded, including seeds outside the reachable region; closed
recovery alone does not establish that the requested slice was available.

## Model checking

### Apalache

All TLA+ modules must remain Apalache-compatible. The check script discovers
and typechecks every `Specs/*.tla` file. Each new executable scenario must also
be registered in the script with its constant initialization, `Init`/`Next`,
safety invariant, and a practical transition bound. Shared parameterized
modules are exercised through those concrete scenarios.

Compatibility here means typechecking and bounded safety checking through
`Init`/`Next`. The fair temporal `Spec` and `Terminates` remain the TLC interface;
a passing Apalache safety run does not establish fair termination.

The modules include Snowcat type annotations. `AriadneExample.tla` exposes
`Init`, `Next`, `Safety`, and four constant initializers (`BinaryConstants`,
`DumpConstants`, `LoopConstants`, and `ClosedConstants`). `Safety` conjoins the
same five invariants used by TLC. Type invariants check record fields and
function domains directly, avoiding large Cartesian products in SMT encoding.

Run the compatibility checks from the repository root:

```sh
bash Specs/check-apalache.sh
```

The script typechecks all ten modules, checks each larger machine scenario through
six transitions, checks `AriadnePipeline.tla` through eight transitions, and
checks `AriadneCalls.tla` through the same configurable bound (six by default).
It checks `AriadneLLVMIRExample.tla` through eight transitions and
`AriadneMachineStateExample.tla` through six. It writes all artifacts to a fresh
temporary directory and prints its path. Set `APALACHE_MC` to select an
executable. To change the bound for the larger scenarios or select one scenario:

```sh
bash Specs/check-apalache.sh 10 Loop
```

Equivalent individual commands, run from `Specs/`:

```sh
apalache-mc --out-dir=/tmp/ariadne-apalache-types typecheck Ariadne.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-binary check \
  --cinit=BinaryConstants --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneExample.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-pipeline check \
  --init=Init --next=Next --inv=Safety \
  --length=8 --no-deadlock AriadnePipeline.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-calls check \
  --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneCalls.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-llvmir check \
  --init=Init --next=Next --inv=Safety \
  --length=8 --no-deadlock AriadneLLVMIRExample.tla
apalache-mc --out-dir=/tmp/ariadne-apalache-machine-state check \
  --init=Init --next=Next --inv=Safety \
  --length=6 --no-deadlock AriadneMachineStateExample.tla
```

The six-step runs primarily cover recovery, not completion of the larger
scenarios. The pipeline fixture uses two instructions: a definition followed by
a use. It exercises recovery, reaching-definition propagation, backward slice
expansion, and completion within eight steps. `NotDone` is a deliberately false
invariant in that fixture; checking it at bound eight provides a reachability
witness ending in `done`, rather than a vacuous completion-property check.

The call fixture has a call at 1, continuation 2 and two known callee targets,
3 and 4. Both callees have readable, decodable instructions, but only 3 is an
independent root. The fixture checks that all three edges are visible, 4 stays
unvisited, and 3 receives only its own entry definitions. The continuation 2
must receive both the caller's incoming and possible new definitions of `x`.
This tests the edge policy even when a callee already exists as a decoded node.
Its six-step Apalache run covers recovery and early propagation, not completion;
TLC checks its complete finite state space. Exploratory Apalache runs at bound
twelve were stopped after prolonged checks at the data-flow boundary, under
both the default strategy and `search.invariant.mode=after`. Those deeper runs
are not recorded as passes or as discovered model errors.

```sh
# Expected result: a counterexample to NotDone, ending with phase = "done".
apalache-mc --out-dir=/tmp/ariadne-apalache-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=8 --no-deadlock AriadnePipeline.tla

# Expected result: a counterexample to NotDone with the exact LLVM IR slice.
apalache-mc --out-dir=/tmp/ariadne-apalache-llvmir-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=5 --no-deadlock AriadneLLVMIRExample.tla

# Expected result: a counterexample with the exact final machine-state map.
apalache-mc --out-dir=/tmp/ariadne-apalache-machine-state-witness check \
  --init=Init --next=Next --inv=NotDone \
  --length=5 --no-deadlock AriadneMachineStateExample.tla
```

These commands check **bounded safety**, not fair termination. They deliberately
use `Init`/`Next` instead of the fair temporal `Spec`; `--no-deadlock` permits the
terminal state. The original TLC configurations retain `Spec` and `Terminates`
for exhaustive finite-instance liveness checking. Increasing the Apalache bound
may substantially increase SMT cost.

Tool conventions: [Apalache type annotations](https://apalache-mc.org/docs/HOWTOs/howto-write-type-annotations.html)
and [bounded checking](https://apalache-mc.org/docs/apalache/running.html).

Validated on 2026-09-17 with Apalache **0.57.0**, build `635865a`:

| Instance / check | Bound | Result |
| --- | ---: | --- |
| Binary / `Safety` | 6 | No error |
| Dump / `Safety` | 6 | No error |
| Loop / `Safety` | 6 | No error |
| Closed / `Safety` | 6 | No error |
| Calls / `Safety` (includes `CallPolicy`) | 6 | No error |
| Pipeline / `Safety` | 8 | No error |
| Pipeline / `NotDone` reachability witness | 8 | Expected counterexample; final phase `done`, slice `{1, 2}` (original fixture addresses) |

All four modules passed typechecking, including the instantiated modules in
the bounded checks. The `NotDone` check intentionally exits with code 12;
the safety checks exit with code 0. The TLC results below were rechecked after
the unified call-edge change; all five original scenarios retain their state counts.

### TLC

`AriadneExample.tla` instantiates the engine with seven candidate addresses and
two abstract locations. Its configurations exercise:

| Configuration | Coverage |
| --- | --- |
| `Binary.cfg` | Conditional diamond, partial indirect targets, missing bytes, decode failure, unknown call, conservative call writes |
| `Dump.cfg` | Same request with captured precedence, trusted fallback, an available but untrusted file span, and a missing slice seed |
| `Loop.cfg` | Two definitions joining, a back edge, a must-write kill, fixed-point convergence, and data-slice closure |
| `Closed.cfg` | Certified indirect targets, visible call/summary edges, unvisited callee, and obligation-free completion using dump/file bytes |

`Pipeline.cfg` checks the additional two-instruction `AriadnePipeline.tla`
instance, including termination and the exact final reaching definitions/slice.
Its sparse VAs 4096 and 4100 also check that addresses are preserved as supplied,
with an explicit successor rather than an implicit adjacent node index.
`Calls.cfg` checks `AriadneCalls.tla`, including the independent `CallPolicy`
assertions and exact final unified graph and data-flow results.
`LLVMIR.cfg` checks `AriadneLLVMIRExample.tla`: an exact four-block CFG, a phi
join, conservative store/call memory predecessors, a separate call edge, an
incomplete-call obligation, artifact-scoped identity, final dependency slice,
and fair termination.
`MachineState.cfg` checks `AriadneMachineStateExample.tla`: propagation of a
finite entry state through a constant and flag update, preservation of both
structural branch edges, separate feasible/infeasible classification, the
unreachable fallthrough node, the reached return outcome, and fair termination.

Run from `Specs/` with Java and the TLA+ tools available:

```sh
tlc -workers 2 -metadir /tmp/ariadne-tlc-binary -config Binary.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-dump -config Dump.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-loop -config Loop.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-closed -config Closed.cfg AriadneExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-pipeline -config Pipeline.cfg AriadnePipeline.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-calls -config Calls.cfg AriadneCalls.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-llvmir -config LLVMIR.cfg AriadneLLVMIRExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-machine-state -config MachineState.cfg AriadneMachineStateExample.tla
```

If no `tlc` launcher is installed, substitute `java -cp /path/to/tla2tools.jar
tlc2.TLC`. Each configuration checks the engine invariants, its fixture result,
and `Terminates`. The call fixture additionally checks `CallPolicy`; the smaller
fixtures conjoin their safety checks in `Safety`.
Deadlock checking is disabled because `done` intentionally has no nonstuttering
successor; the termination property still detects premature permanent stalls.
Exhaustive checks of these finite instances are not a proof for every instance
or a validation of the external semantic adapters.

Validation on 2026-09-17 with TLC 2.19 (revision `5a47802`), Java 17,
and two workers completed with no errors:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `Binary.cfg` | 149 | 74 | 17 |
| `Dump.cfg` | 86 | 46 | 16 |
| `Loop.cfg` | 91 | 51 | 15 |
| `Closed.cfg` | 104 | 56 | 15 |
| `Pipeline.cfg` | 11 | 10 | 9 |
| `Calls.cfg` | 27 | 19 | 11 |

The call-edge regression was also checked against two deliberately broken
temporary copies of the model. Queuing all edge destinations (including calls)
and letting `Preds` inspect all edges each caused TLC to reject `Safety`.
The repository model retains the local-edge filters in both operations.

### Virtual-address contract validation (2026-09-17)

After adding `SnapshotId`, `AddressSpaceContract`, and the sparse-VA pipeline,
TLC 2026.03.24.222644 (revision `1476e7f`) passed all six configurations,
including safety and fair termination, with the same state counts listed above.
Two temporary copies of the pipeline were also checked: replacing VA 4096 with
-1 (and importing `Integers` to express it), and replacing `pipeline-snapshot`
with the empty string. Both violated `Safety` in the initial state (exit 12).
This checks contract rejection through `TypeOK`, independently of how TLC
handles assumptions inside instantiated modules.

Apalache 0.61.0 (build `831d473`) passed typechecking of all four final modules
and bounded `Safety` checks for Binary, Dump, Loop, Closed, and Calls through
six transitions, and Pipeline through eight. Binary was rerun after adding
the contract to `TypeOK`; the other bounded runs used that final contract.
The updated pipeline's `NotDone` check at bound eight produced the expected
counterexample (exit 12), ending in `done` with slice `{4096, 4100}`.
These checks do not validate a byte provider or uniqueness of snapshot IDs.

### Native LLVM IR validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked `AriadneLLVMIR.tla` and
`AriadneLLVMIRExample.tla`. Its bounded `Safety` check through eight transitions
reported no error; the fixture has no executions as long as the supplied bound
because it reaches `done` after five transitions.

The full `check-apalache.sh 6 all` run also typechecked all six modules and
reported no safety error for Binary, Dump, Loop, Closed, and Calls through six
transitions or for Pipeline and LLVM IR through eight.

The LLVM IR `NotDone` reachability check at bound five produced the expected
counterexample (exit 12). Its final state is `done` with the exact nine-node
`ExpectedSlice`, demonstrating that the fixture's completion assertion is
exercised rather than vacuous.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers
exhaustively checked `LLVMIR.cfg`, including safety and fair termination:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `LLVMIR.cfg` | 5 | 5 | 5 |

The seven configurations present at that point passed together in the same
environment. The six existing machine fixtures retained their generated and
distinct state counts.

### Abstract machine-state validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked `AriadneMachineState.tla` and
`AriadneMachineStateExample.tla`. Its bounded `Safety` check through six
transitions reported no error and reached the terminal analysis state before
the supplied bound.

The final `check-apalache.sh 6 all` run typechecked all eight modules and
reported no safety error for Binary, Dump, Loop, Closed, and Calls through six
transitions, Pipeline and LLVM IR through eight, or machine state through six.

The `NotDone` reachability check at bound five produced the expected
counterexample (exit 12). Its final state is `done` with `statesAt` equal to
`ExpectedStates`, demonstrating that the final edge classifications are
exercised rather than vacuous.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers
exhaustively checked `MachineState.cfg`, including safety and fair termination:

| Configuration | Generated states | Distinct states | Search depth |
| --- | ---: | ---: | ---: |
| `MachineState.cfg` | 5 | 5 | 5 |

The full eight-configuration TLC suite passed in the same environment. The
seven prior configurations retained their generated and distinct state counts.

### Shared machine contract extraction validation (2026-09-19)

Apalache 0.61.0 (build `831d473`) typechecked
`AriadneMachineCommon.tla`, `Ariadne.tla`, and
`AriadneMachineStateExample.tla`. Bounded `Safety` checks reported no error for
the Binary recovery fixture and the machine-state fixture through six
transitions.

TLC 2026.03.24.222644 (revision `1476e7f`) with Java 25 and two workers passed
all eight configurations after the extraction. Generated and distinct state
counts remained unchanged, providing a behavioral-preservation check for both
common-module consumers and the unaffected LLVM IR model.

### Semantic type-alias validation (2026-09-19)

`AriadneTypes.tla` declares Apalache lower-camel aliases for every semantic
`Str` role and `address = Int`. Machine-model annotations use `$address` for
semantic VAs, address-keyed functions, graph endpoints, definition sites, and
obligations. Unrelated numeric quantities remain annotated as `Int`.

Apalache 0.61.0 typechecked all ten modules with the aliases, with no raw `Str`
remaining in `@type` annotations. Bounded `Safety` checks reported no error for
Binary recovery and machine-state propagation through six transitions, or for
LLVM IR through eight. All eight TLC configurations passed with unchanged state
counts; as expected, Snowcat aliases change annotations rather than untyped
TLA+ behavior.
