# Ariadne

Ariadne is a machine-code analysis project for understanding control flow and
data dependencies in binaries and crash dumps. Its motivating use case is
investigating Chromium and Electron crashes: start from instructions of interest,
recover their surrounding control flow, and trace possible origins of the values
they use.

**Current status: Rust machine-analysis core and formal specifications.** The
Rust library implements `Specs/Ariadne.tla`: local CFG recovery, may-reaching
definitions, and backward data slicing from fixed adapter-supplied inputs.
An optional [LLVM MC byte-span adapter](docs/llvm-mc-adapter.md) now supplies
decoded control-flow summaries from caller-provided bytes. Its new
`ByteSnapshot::prepare()` interface adds structured operands, reviewed effects
and per-site evidence for an [explicit rule registry](docs/Ariadne/operand-effects-rules.md). Binary/dump file
readers, the analyzer CLI, and graph exporters have not been implemented.
The separate native LLVM IR, abstract machine-state, and initial x86-64
instruction-semantics models remain formal specifications.

The [immediate AMD64 milestone](docs/amd64-user64.md) is a verified 64-bit
user-mode subset, starting with 49 register/immediate form cases and then near
control/stack and common RAM operations. Unsupported semantics must retain
explicit analysis uncertainty. Full Volume 3 general-purpose and Volume 1 state
coverage remains the [long-term design target](docs/amd64-semantics-design.md). Its
[pinned source inventory](Specs/AMD64/README.md) and
[TLA+/Lean foundations](lean/README.md) now include CPU-state representation,
instruction-form validation, memory/exception contracts and integer kernels.
The conservative default fallback foundation is accepted for the exact user64
profile hash. Register-core acceptance remains pending: its 49 paired bodies
are recorded separately from its zero verified instruction steps. TLA+ stays
authoritative and the
[task list](docs/amd64-semantics-tasks.md) tracks the proof and implementation work.
The [roadmap](ROADMAP.md) orders binary/dump input, CFG recovery, conservative
effects, verified semantics and investigator output without requiring full AMD64
coverage for useful partial analysis.

The core uses **Rust 2024 and Cargo**, with no external crate dependencies.
The separate native decoder pins LLVM MC 20.1.2. Reviewed rules now provide
byte-level GPR and flag effects for the scoped registry. Memory remains
conservative, calls remain opaque, and broader effect coverage and precise
alias analysis remain future work. Decoder metadata alone does not provide
the complete analysis. See the [delivery evidence](docs/Ariadne/operand-effects-validation.md).

Build and test the Rust library from the repository root:

```sh
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
```

Use `ariadne::analyze(request)` for a completed result, or `Analyzer::step()` to
observe individual specification transitions. The input contract, runnable
example, and specification correspondence are described in
[the implementation guide](docs/implementation.md).

The [model-based test gate](mbt/README.md) uses Mirrors' generated `mirrorrust-v1`
binding and MirrorRust to replay TLC-generated traces against the real Rust
analyzer, with required interface negotiation, coverage checks, and deliberate
implementation mutations:

```sh
python3 mbt/run.py
```

Follow the MBT guide's one-time tool preparation first; ordinary Cargo tests
remain independent of the model-checking tools and client dependencies.

## Intended workflow

Binary and dump inputs should feed the same machine analysis through a common view
of addresses, available bytes, module mappings, and instruction semantics:

```mermaid
flowchart LR
    Binary[Binary] --> Input[Input adapters]
    Dump[Crash dump] --> Input
    Input --> View[Common address-space view]
    View --> Decode[Decode and summarize instructions]
    Decode --> CFG[Recover CFG]
    CFG --> Dataflow[Compute reaching definitions]
    CFG --> Stateflow[Propagate abstract machine states]
    Dataflow --> Slice[Build backward data slice]
    Stateflow --> StateResults[Report states and edge feasibility]
```

Native LLVM IR is a separate input path. It is not reconstructed from machine
code:

```mermaid
flowchart LR
    IR[Supplied .ll or .bc] --> Adapter[Verified IR adapter]
    Adapter --> IRCFG[Terminator-derived block CFG]
    IRCFG --> Dependencies[SSA, phi, memory and call dependencies]
    Dependencies --> IRSlice[Build backward data slice]
```

Each request uses one immutable address-space snapshot, identified by
`SnapshotId`. `Addresses` and `EntryPoints` contain virtual addresses directly;
entry points start discovery and do not define an address base. Adapters map
those VAs to dump regions or binary sections/segments. Storage offsets and
compact graph node IDs are not semantic addresses.

Snowcat annotations use the shared `$address` type alias for every semantic VA.
The alias expands to `Int` for Apalache and is documentary rather than nominal;
unrelated integer quantities retain explicit `Int` annotations.

The machine model abstracts the input adapters and decoder as fixed inputs. It
specifies the engine's behavior once byte availability and instruction summaries
have been supplied. Planned outputs include annotated assembly, a unified graph,
and dependency information, with JSON and Graphviz DOT export for SVG rendering.

## Machine analysis phases

The model describes the analyzer's execution, rather than executing the program
under investigation.

| Phase | Behavior | Completion condition |
| --- | --- | --- |
| `recover` | Visit entry points and known local successors; record instruction provenance, edges, and unresolved information | Every discovered local address has been attempted |
| `dataflow` | Propagate possible value origins, combining alternatives at joins and revisiting loops | Reaching definitions reach a fixed point |
| `slice` | Follow data producers backward from the requested decoded instructions | No further producer instructions can be added |
| `done` | Expose the graph, data-flow results, slice, and remaining gaps | Terminal analysis state |

A reaching definition identifies an instruction that could have supplied a
location's value. A definite overwrite removes earlier definitions of that
location; a possible overwrite preserves both old and new origins. The backward
slice follows these relationships from the instructions being investigated.

The LLVM IR model starts with a verified, normalized function. Its CFG is
derived from explicit terminator successors rather than recovered heuristically.
Ordinary SSA dependencies are direct; phi inputs retain predecessor blocks, and
conservative memory predecessors are supplied by an analysis adapter.

The separate machine-state model starts from a frozen recovered local CFG. It
propagates finite abstract states to a fixed point using a trusted ISA-semantics
relation. The structural graph is never pruned: feasibility, proven
infeasibility under stated entry facts, and unknown feasibility are derived
classifications.

## Modeling decisions

- **Preserve byte provenance.** Dump-captured bytes take precedence. Filling a
  missing span from a binary requires a separate suitability certificate covering
  image identity, address mapping, relocations, and possible runtime changes.
- **Represent uncertainty explicitly.** Missing bytes, decode failures, and
  incomplete indirect-jump or call targets become unresolved obligations. A
  finished analysis can still be partial.
- **Keep structural alternatives.** Conditional branches retain both edges.
  Crash-time register values do not automatically establish earlier branch
  outcomes or justify pruning paths.
- **Use one machine-edge representation.** Local and `call` edges share the graph, while
  explicit policies determine which edges discovery and data flow follow.

For a call at A to F with continuation B, the graph contains:

```text
A --call----> F
A --summary-> B
```

The `call` edge identifies a possible callee. The `summary` edge represents the
call's summarized effects followed by a possible return. Local analysis follows
the summary edge; it neither visits the callee automatically nor transmits
definitions across the call edge. This remains true when the callee is analyzed
independently as another entry point.

## Scope and limitations

The machine specification models an instruction-level CFG, forward may-reaching
definitions, and a backward **data** slice over a finite request. Its inputs
already contain decoded instruction summaries; checking the model does not
validate an instruction decoder, dump parser, symbol file, or alias analysis.

The LLVM IR specification models one directly supplied, verifier-accepted
function per request: a block CFG, instruction-level SSA dependencies,
edge-sensitive phi inputs, conservative memory predecessors, separate call
edges, obligations, and a backward data slice. It does not recover original
LLVM IR from a binary, prove LLVM's verifier, validate alias analysis, or claim
a correspondence between IR instructions and machine addresses.

The machine-state specification models possible abstract register, flag, and
memory states before decoded instructions. State identities preserve
cross-location correlations, while valuations expose finite per-location value
sets. It does not reconstruct historical execution, prove ISA semantics, or
justify applying a crash-time observation to an earlier program point.

`AriadneX86_64Semantics.tla` now supplies executable rules for a register/immediate
subset of x86-64 and derives inputs for the state-propagation model. See the
[supported forms and assumptions](docs/x86-64-semantics.md). It is not a complete
ISA model, a decoder, or a Rust implementation.

The slice follows all modeled inputs of each included instruction. It does not
yet select individual operands, include control dependencies, or establish which
instructions actually executed. Missing slice seeds are reported separately.

Interprocedural call/return matching, general concrete CPU execution, exception
delivery and unwinding, concurrency, self-modifying code, and TTD history remain
outside these models. State/branch reasoning is limited to supplied or supported
semantics, and `UD2` records a fault without delivering it. Basic-block coalescing
is also deferred.
These boundaries matter when interpreting a result: a possible dependency is
evidence for investigation, not proof of a crash's root cause.

See [the formal-model guide](Specs/README.md) for the complete input contract,
state transitions, invariants, and interpretation of partial results.

## Repository guide

| Path | Purpose |
| --- | --- |
| [src/lib.rs](src/lib.rs) | Rust library entry point and runnable API example |
| [src/model.rs](src/model.rs) | Request validation, semantic types, state, and result views |
| [src/engine.rs](src/engine.rs) | Executable implementation of `Specs/Ariadne.tla` |
| [tests/](tests/) | Specification fixtures, transition checks, and independent generated-request oracles |
| [docs/implementation.md](docs/implementation.md) | Rust API, model correspondence, and implementation boundaries |
| [docs/llvm-mc-adapter.md](docs/llvm-mc-adapter.md) | Optional pinned decoder build, snapshot input contract, and validation |
| [docs/machine-state-design.md](docs/machine-state-design.md) | Proposed Rust design for abstract machine-state propagation |
| [docs/x86-64-semantics.md](docs/x86-64-semantics.md) | Supported x86-64 instruction rules, stateflow composition, and validation limits |
| [mbt/README.md](mbt/README.md) | Mirrors/MirrorRust MBT setup, checked corpus, mutation gate, and evidence |
| [Specs/AriadneTypes.tla](Specs/AriadneTypes.tla) | Shared Apalache aliases for semantic identities, labels, states, and values |
| [Specs/AriadneMachineCommon.tla](Specs/AriadneMachineCommon.tla) | Stateless machine address, local-edge, and effect contracts shared by machine models |
| [Specs/Ariadne.tla](Specs/Ariadne.tla) | Core state machine, with detailed behavioral comments and Apalache type annotations |
| [Specs/AriadneExample.tla](Specs/AriadneExample.tla) | Binary, dump, loop, and closed-graph scenarios |
| [Specs/AriadnePipeline.tla](Specs/AriadnePipeline.tla) | Small end-to-end recovery, propagation, and slicing scenario |
| [Specs/AriadneCalls.tla](Specs/AriadneCalls.tla) | Call visibility, discovery isolation, and data-flow isolation regression |
| [Specs/AriadneLLVMIR.tla](Specs/AriadneLLVMIR.tla) | Native LLVM IR CFG, dependency, obligation, identity, and slicing model |
| [Specs/AriadneLLVMIRExample.tla](Specs/AriadneLLVMIRExample.tla) | Branch/phi, memory-dependency, and incomplete-call IR fixture |
| [Specs/AriadneMachineState.tla](Specs/AriadneMachineState.tla) | Post-recovery finite abstract machine-state propagation and edge classification |
| [Specs/AriadneMachineStateExample.tla](Specs/AriadneMachineStateExample.tla) | Constant/flag propagation and branch-feasibility fixture |
| [Specs/AriadneX86_64Semantics.tla](Specs/AriadneX86_64Semantics.tla) | Executable register/immediate x86-64 subset and finite-state bridge |
| [Specs/AriadneX86_64SemanticsChecks.tla](Specs/AriadneX86_64SemanticsChecks.tla) | Arithmetic, flags, operand, branch, and bridge regression checks |
| [Specs/AriadneX86_64SemanticsExample.tla](Specs/AriadneX86_64SemanticsExample.tla) | Instruction-derived stateflow with complete and incomplete inputs |
| [Specs/check-x86-64.sh](Specs/check-x86-64.sh) | x86-64 Apalache typechecks and executable TLC checks |
| [Specs/check-apalache.sh](Specs/check-apalache.sh) | Typechecking and bounded safety checks |
| [Specs/README.md](Specs/README.md) | Checking commands, assumptions, and recorded validation results |

The `.cfg` files in `Specs/` configure TLC scenarios. Temporary directories,
model-checker outputs, Cargo build output, and Bazel output paths are covered by
[.gitignore](.gitignore).

## Run the specification checks

Use Java and the corresponding TLA+ tools. Recorded validation includes
**Java 17**, **Apalache 0.57.0**, and **TLC 2.19**, plus the current native-IR
validation with **Java 25**, **Apalache 0.61.0**, and TLC revision `1476e7f`.
These are tested versions, not a repository dependency lock. The Rust library
and the TLA+ model checks can be built and run independently.

From the repository root, run Apalache with `apalache-mc` on `PATH`:

```sh
bash Specs/check-apalache.sh
```

To select another installation, set `APALACHE_MC` to its absolute executable path:

```sh
APALACHE_MC=/absolute/path/to/apalache-mc bash Specs/check-apalache.sh
```

The script typechecks all ten modules, checks the four general scenarios and
the call regression through six transitions, and checks the pipeline through
eight transitions. The native LLVM IR fixture is also checked through eight
transitions, and the machine-state fixture through six. Artifacts go to a fresh
temporary directory whose path is printed at startup. These checks can take
several minutes.

An optional bound and general-scenario selector are supported:

```sh
bash Specs/check-apalache.sh 6 Loop
```

This selects `Loop` among the general scenarios; the pipeline, call regression,
LLVM IR fixture, and machine-state fixture still run. The supplied bound also
applies to the call regression, while the other specialized checks retain their
documented bounds. Higher bounds can be substantially more costly.

For an exhaustive TLC check of the call scenario, with a `tlc` launcher on `PATH`:

```sh
cd Specs
tlc -workers 2 -metadir /tmp/ariadne-tlc-calls -config Calls.cfg AriadneCalls.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-llvmir -config LLVMIR.cfg AriadneLLVMIRExample.tla
tlc -workers 2 -metadir /tmp/ariadne-tlc-machine-state -config MachineState.cfg AriadneMachineStateExample.tla
```

If using the tools JAR directly, replace `tlc` with
`java -cp /absolute/path/to/tla2tools.jar tlc2.TLC`. Commands for all eight TLC
scenarios are in [Specs/README.md](Specs/README.md#tlc).

## Validation status

The [recorded checks](Specs/README.md#model-checking) passed for all eight TLC
scenarios, including safety and fair termination. Apalache passed bounded safety
at the default bounds described above. The call regression also rejected
deliberately broken variants that traversed call edges or allowed them into
local data-flow propagation.

Apalache's bounded checks do not establish unbounded termination or exercise
completion of every larger scenario. Exploratory call-case checks at bound
twelve were stopped for runtime and are not counted as passes. TLC checks the
entire reachable state space of each supplied finite instance; that is not a
proof for every possible input or for a future C++ implementation.
