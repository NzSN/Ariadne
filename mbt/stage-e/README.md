# Stage E MirrorRust integration

This optional package connects Ariadne's machine-state and LLVM IR analyzers
to the local `../../../MirrorRust` checkout (`~/Repos/MirrorRust` in this
workspace). The dependency-free core remains unchanged. The
[design](../../docs/Ariadne/stage-e-mirrorrust-design.md) and
[first-stage plan](../../Plans/stage-e-mirrorrust-integration.md) describe the seam.
The [installed ModelMirrors compatibility check](../../docs/Ariadne/installed-modelmirrors-compatibility.md)
also passes against the local installed server, with its executable identity
recorded separately from the `v0.0.3.1` source tag.

Two separately compiler-generated `mirrorrust-v1` bindings own codecs,
dispatch and lifecycle checks. Application ports own the actual Rust analyzers
and observe their state/results. Registered deferred factories require exact
semantic-digest admission before port construction. Initialization resets a
fresh analyzer using the port's owned fixed request; neither expected nor
previous model state supplies observations.

The existing five-node machine-state and four-block LLVM IR fixtures supply
the first inputs. Replay wrappers instantiate the authoritative specifications
and select Rust's lowest-enabled-address propagation schedule. Machine-state
observations include phase, the full address/state map, structural graph,
feasible/infeasible/unknown edges, terminal outcomes, not-reached nodes and
obligations. IR observations include artifact/module/function identity, phase,
slice, control/call graphs, dependency predecessors and obligations.

The machine-state map becomes explicit `{va, states}` rows with a checked
inverse, preserving sparse addresses and empty entries. LLVM's string-keyed
dependency map uses the native generated map codec. Generated source must
not be hand-edited or formatted.

## Run the integration gate

Use the prepared Mirrors toolchain selected by `../.work/toolchain.json`, or
an explicitly compatible `MIRRORS_ROOT`. See the
[core harness prerequisites](../README.md#prepare-and-run).

```sh
python3 mbt/stage-e/run.py
```

The gate checks frozen oracle and generated-file freshness, compiler preflight,
three projection tests, four Rust binding tests, formatting and Clippy. It then
replays each fixture twice over real negotiated stdio transport, compares
every declared observation, and requires wrong-digest rejection with zero
factories/initializations/observations. Actual port `Drop` is checked after
successful replay. Client/SUT/oracle/generated artifacts are hash-bound and
checked for changes during the run. Machine-specific results go to ignored
`results/latest.json`; detailed logs are under the core harness's `.work/`.

## Explicitly regenerate model artifacts

```sh
python3 mbt/stage-e/prepare.py
python3 mbt/stage-e/prepare.py --check
```

Generation executes no Rust SUT. Apalache provides a typed initialization
witness. TLC checks safety and fair termination, then deliberately violates
`TraceComplete` only at completion to export a full trace. Raw type witnesses,
TLC JSON, raw ITF and projected ITF stay in `corpus/`; the manifest binds their
sources and bytes. Mirrors resolves the locks, emits the Rust bindings, checks
freshness and preflights the traces. Regeneration is explicit; normal replay
never silently repairs stale evidence. Review changed locks and bindings.

## Acceptance boundary

This is the first Stage E integration stage. The LLVM fixture supplies a
normalized verifier-accepted input assumption; this gate does not launch the
native LLVM verifier or test machine-code/IR correspondence. The existing
native-adapter checks remain separate.

The retained [integration record](../../docs/Ariadne/stage-e-mirrorrust-integration-validation.json)
establishes bounded replay of the two existing fixtures, typed port ownership,
reset and admission behavior. Broader generated scenarios, Stage E mechanical
engine mutants, recovery/native-adapter handoffs, and report/CLI acceptance
remain open. Stage E is still partial; no universal refinement or ISA claim is
made. MirrorGate restricted execution is not exercised by this local gate.
