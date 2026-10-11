# Typed replay and analysis result contracts

## Context and follow-up

**Status.** Implemented typed replay, direct verified IR input and separate
request/report contracts for the abstract-stateflow and supplied-IR machines.
Retained Stage E records identify the finite integration and completion campaigns.

**Why this document exists.** The [stateflow design](../machine-state-design.md)
and supplied-IR adapter require independent conformance evidence
and result identities distinct from minidump dependency analysis.

**What this document establishes.** Compiler-owned replay bindings, independent
model expectations, real-engine observations, native/recovery handoffs and
strict machine-state/IR report envelopes preserve each machine's contract.

**Where to go next.**

- [Completed initial integration plan](../../Plans/completed/stage-e-mirrorrust-integration.md)
  — typed ports, negotiated admission and the initial transport corpus.
- [Completed replay and report plan](../../Plans/completed/stage-e-completion.md)
  — generated corpus, mutations, handoffs and report/CLI delivery.
- [Replay guide](../../mbt/stage-e/README.md) — regeneration and rerun procedures.
- [Semantic assurance](semantic-assurance.md#universal-rust-refinement-boundary)
  — remaining universal refinement and semantic-producer boundaries.

**What remains unresolved.** Finite model-relative conformance does not verify
the semantic producer or prove compiled-Rust refinement for all inputs. Stateflow
feasibility depends on supplied entry facts and transitions; supplied verified
IR is not reconstructed machine-code IR.

For the wider context, see the optional [documentation map](../documentation-map.md).

## Integration and retained delivery

The integration uses `~/Repos/MirrorRust` through the prepared Mirrors
compiler's `mirrorrust-v1` target. The 2026-10-01 two-fixture
[integration record](../../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json)
records initial delivery. The later [source-bound completion evidence](../../evidence/Ariadne/stage-e-completion-validation.json)
records expanded replay, mutation, handoff and report/CLI acceptance. The
2026-10-02 scope update removes the retired independent ISA track from
qualification; the [assurance decision](semantic-assurance.md) preserves the
analysis-level clauses.

## Report and CLI interfaces

Strict result reporting is consolidated into
the root package's `ariadne::reports` module with the `reports` feature. It supplies
versioned machine-state request/semantic-input codecs and separate machine-state
and LLVM IR result envelopes. JSON, text and DOT derive from one validated
owned result. Machine addresses are canonical full-width hex; IR IDs remain
artifact/function-scoped strings. Input schemas reject unknown fields and
duplicates before constructing model requests.

`ariadne-minidump --stateflow-input PATH` accepts explicit trusted finite
semantic facts, checks their snapshot identity against the prepared dump,
and uses the frozen recovery handoff. Its additional reports retain the full
recovery graph, provenance and gaps beside stateflow classifications. No
instruction semantics or completeness assertion is inferred from crash registers.
The separate `ariadne-ir` CLI verifies a directly supplied `.ll`/`.bc`, then
reports its own block/instruction/call identities. Both paths finish validation
before publishing output.

## Report codecs

`ariadne::reports` keeps serialization outside the dependency-free analysis
core. Its root-package `reports` feature supplies strict normalized request
codecs for replay, semantic-input codecs for frozen minidump handoff and
independent machine-state/LLVM IR JSON, text and DOT envelopes.

The schemas are `ariadne.machine-state-request/v1`,
`ariadne.machine-state-semantics/v1`, `ariadne.llvm-ir-request/v1`,
`ariadne.machine-state-report/v1` and `ariadne.llvm-ir-report/v1`. Machine VAs
use `0x` followed by exactly 16 lowercase hexadecimal digits. Request inputs
reject unknown fields, duplicate object/table/set entries, noncanonical
addresses and invalid model contracts. JSON input defaults to an 8 MiB cap;
the native IR protocol retains its 32 MiB cap.

Semantic inputs contain `snapshot_id`, `value_domain`, `catalogue`,
`entry_states`, `steps`, `terminal_transitions`, `complete_sites` and
`adapter_obligations`. They supply no graph or instruction effects; those come
from frozen recovery. Catalogue rows contain `status` and a total `valuation`;
entry rows contain `va` and `states`; steps contain typed `edge`, `before` and
`after`; terminal rows contain `site`, `before`, `after` and `outcome`. See the
[generated request catalogue](../../mbt/stage-e/corpus/inputs/MachineStateReplay.json)
and `encode_semantics()` for semantic-only schema construction.

Supplied transitions and `complete_sites` are caller premises. The engine
classifies feasibility relative to these premises and entry facts; it never
derives past states from crash-time registers. Machine reports retain the
catalogue, complete state map, structural/feasible/infeasible/unknown edges,
terminal outcomes and obligations. Minidump stateflow additionally links the
separately versioned input/preparation report and all its gaps. IR reports
retain artifact/module/function identity, normalized input, instruction slice,
block CFG, calls, dependency predecessors and obligations. Serialization
agreement does not prove these semantic inputs true.

## Minidump stateflow

Build the [input helpers](file-reader-design.md#build-and-verification), then:

```sh
cargo build --offline --locked --manifest-path Cargo.toml
target/debug/ariadne-minidump DUMP --decoder target/ariadne-llvm-mc \
  --entry 0x0000000000401000 --seed-exception-rip \
  --stateflow-input semantics.json --output-dir NEW_DIR
```

`semantics.json` follows `ariadne.machine-state-semantics/v1` and must match
the prepared dump's snapshot identity. Recovery supplies the frozen graph and
effects; call-only edges stay in context and are excluded from stateflow.
Wrong identities or invalid contracts fail before publication.

Output-directory mode publishes the original `report.txt/.dot/.json` and
additional `machine-state.txt/.dot/.json`. `--format` selects one machine-state
envelope retaining the independently versioned minidump evidence. Unknown
control/effects, missing seeds, byte provenance and incomplete semantics stay
visible. Entry facts are supplied explicitly, not inferred from crash context.

## Direct verified IR

`ariadne-ir` accepts directly supplied LLVM `.ll` or `.bc` bytes for one
function. It hashes an owned artifact snapshot, asks pinned LLVM 20.1.2 to
parse and verify those exact bytes, validates normalized block/SSA/phi/memory/
call tables, and returns an
[`ariadne::llvm_ir::Request`](../../src/llvm_ir.rs). It neither lifts binaries
nor correlates LLVM values with machine VAs. The
[IR model](../../Specs/README.md) defines the analysis contract.

```sh
LLVM20_INCLUDE_DIR=/tmp/ariadne-llvm20/usr/include/llvm-20 \
  bash native/llvm_ir/build.sh
ARIADNE_LLVM_IR="$PWD/target/ariadne-llvm-ir" \
  cargo test --offline --locked --manifest-path Cargo.toml --test ir_native -- --ignored

cargo build --offline --locked --manifest-path Cargo.toml
target/debug/ariadne-ir tests/ir/fixtures/diamond.ll \
  --helper target/ariadne-llvm-ir --function diamond --seed i11 \
  --output-dir NEW_DIR
```

`open_verified_ir(path, helper, function, seeds)` accepts instruction IDs such
as `i11` in helper-stable order within the hashed artifact/function. Failed
verification, changed helper version, malformed protocol or failed model
contract returns an error. The helper limits a function to 4,096 instructions
and the coarse memory predecessor relation to 100,000 pairs. Each memory read
retains every possibly writing instruction as a candidate predecessor and an
explicit alias-uncertainty obligation. Indirect calls retain incomplete targets.

The CLI binds the helper hash and exact artifact/function identity and renders
text, DOT and JSON from one owned result. Wrong seeds/options, verifier or
protocol failures and reused output destinations fail before complete report
publication. SSA/phi dependencies, conservative memory edges, call obligations
and block/instruction identities survive all formats. Verification establishes
LLVM well-formedness, not precise aliases or machine-address correspondence.

## Replay ownership and observations

Replay accepts a typed case-ID initializer bound to a fixed independently
generated request catalogue. Expected transitions come only from the original
TLA+ specifications. Deterministic generated cases expand the bounded corpus;
mechanical engine mutants establish that the unchanged observation seam can
detect failures in every relevant result family. This remains finite conformance
evidence, with the supplied semantic relation and native adapter as explicit
boundaries.

Application ports and negotiated factories live under `src/mbt/stage_e` in the
root Cargo package; `mbt/stage-e` owns campaign orchestration and corpus files.
Generated modules own codecs, dispatch and lifecycle validation.
Factories construct the ports only after exact semantic-digest admission.
Each port owns its fixed request and resets a fresh real analyzer on initialization;
observations come only from that analyzer, never expected or previous model state.

Replay wrappers invoke the authoritative models' actions. Machine-state replay
chooses the lowest enabled address, matching Rust. Its observations retain phase,
the entire state map, structural graph, edge classifications, terminal outcomes,
not-reached nodes and obligations. LLVM IR retains phase, slice, control/call
graphs, dependency predecessors and obligations. Their identities remain separate.

The address-map wire projection uses explicit `{va, states}` rows with an
exact inverse check. String-keyed LLVM dependency maps keep their native map
representation. Raw model witnesses and projected type evidence remain retained.

## Finite corpus and claim boundary

| Recorded campaign | Scope and retained result |
| --- | --- |
| [2026-10-01 initial integration](../../evidence/Ariadne/stage-e-mirrorrust-integration-validation.json) | Five-node machine-state and four-block IR fixtures exercised transport, semantic-digest admission, generated binding ownership and actual-engine observations. |
| [Completion campaign](../../evidence/Ariadne/stage-e-completion-validation.json) | 16 machine-state and 16 IR inputs, twice per engine: 64 complete traces and 326 matched observations; all mutable fields/public derived views compared through generated MirrorRust ports. All 15 real-engine mutants produced genuine model mismatches. |
| High-address case in completion | Exact u64 values use Apalache because TLC integers are bounded; bounded safety evidence plus a complete four-transition witness. |
| [2026-10-02 assurance scope](semantic-assurance.md) | Independent ISA track retired; analysis-level replay, mutation and model contracts retained. |

The full completion gate verifies native text/bitcode and frozen recovery
handoffs, parses both CLIs' DOT with Graphviz, checks JSON identity and
uncertainty, and reruns minidump regression/mutation gates. Run it with:

```sh
python3 tools/check_stage_e.py
```

The [completed plan](../../Plans/completed/stage-e-completion.md) defines the
acceptance clauses; the source-bound completion JSON is the acceptance
authority. These results apply to the recorded source/backend/workload and
require fresh or exact-identity verification for a changed checkout. They are
finite conformance/report acceptance, not a universal compiled-Rust refinement
proof. BAP lifting remains trusted; caller-supplied abstract transitions and
native IR validation retain their separate premises. No historical execution
or machine/IR correspondence is claimed.

## Result families

These result families use independent versioned input/report schemas:
`ariadne.machine-state-request/v1`, `ariadne.machine-state-semantics/v1`,
`ariadne.llvm-ir-request/v1`, `ariadne.machine-state-report/v1` and
`ariadne.llvm-ir-report/v1`. Their codecs are documented in the
[report-codec contract](#report-codecs). Minidump capture and preparation remain in
the separately versioned [minidump report](result-rendering.md#json-v1).

| Path | Identity and fixed input | Mutable result | Derived observations |
| --- | --- | --- | --- |
| `ariadne::machine_state` | Recovery snapshot, decoded local nodes, full typed structural edges, finite state-ID catalogue, entry facts, trusted running/terminal transitions and completeness assertions | `Phase::Stateflow/Done`; possible state IDs **before** each node | Feasible, model-relative infeasible and unknown edges; reached terminal rows; not-reached nodes; adapter and incomplete-semantics obligations |
| `ariadne::llvm_ir` | SHA-256-bound directly supplied IR artifact, module/function identity, verifier-accepted block/SSA/phi/memory/call tables | `Phase::Slice/Done`; LLVM instruction-ID slice | Terminator-derived block CFG, separate call graph, direct SSA and conservative memory predecessors, incomplete-call and adapter obligations |

The machine-state recovery handoff retains the **full** recovery graph,
provenance, missing seeds and recovery obligations separately. Its stateflow
request excludes call-only edges but keeps summary edges. A stateflow
`complete_sites` assertion is supplied by an adapter and never inferred from a
decoded instruction's control-target completeness.

The IR path uses block, instruction, value and callee IDs scoped to the hashed
artifact and selected function. It does not assign machine VAs, reconstruct
original IR from a binary, or claim correspondence between native IR values
and crash-time register values. The LLVM helper's verifier certifies LLVM IR
well-formedness, while the adapter's all-writer memory predecessor set is a
coarse conservative policy carrying `unknown-memory-alias` obligations.

Both paths expose owned requests and results through shared-reference accessors.
They deliberately do not share the recovery analyzer's phase or obligation
enums. The CLI envelopes preserve each path's identity and uncertainty
without coercing one result into the other's graph.
