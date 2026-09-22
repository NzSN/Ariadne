# Conservative unsupported-semantics analysis contract

`Specs/AMD64Unsupported.tla` and `lean/AMD64/Unsupported.lean` define the
fallback used when an instruction is decoded but its architectural semantics
are outside the currently verified subset. This is an analyzer knowledge
projection. It is not an instruction transition.

The contract follows the existing Ariadne boundaries:

- `AriadneX86_64Semantics.Execute` returns no modeled outcome for unsupported
  forms, while `UsesOf` and `MayDefsOf` conservatively cover every projected
  location and `MustDefsOf` is empty.
- `AriadneMachineState` creates an `incomplete-semantics` obligation for sites
  outside `CompleteSites`. Absent semantic steps cannot prove an edge
  infeasible.
- `Ariadne.tla` retains structural edges and keeps incomplete indirect/call
  targets unresolved rather than inventing a destination.

`UnknownInstructionFallback(before)` is the accepted safe entry point. It has
no caller-supplied trust, may-write, or mutable-location inputs. Every observed
register, flag, memory, and control location is mutable, so it discards every
concrete fact and architectural-undefined marker, reports
`unsupported-semantics`, and produces no
retirement, successful transition, fault vector, or successor. In particular,
it does not execute an unsupported instruction as a no-op and does not turn a
tool limitation into #UD.

The parameterized `UnsupportedFallback` helper derives its mutable-location
universe from every location already present in concrete or undefined
knowledge, then unions caller-supplied extras. An empty caller set therefore
cannot preserve observed facts. It permits selective invalidation only when an
external source has established a trusted, dependency-closed effect summary
contained in the derived universe. Control locations are still invalidated
because fallback cannot certify a successor. The `trusted` and
`dependencyClosed` fields record that external adapter assumption; this module
does not prove the decoder or adapter constructed a sound dependency closure.
Those fields do not establish profile acceptance, and profile code must use
`UnknownInstructionFallback` unless that external proof obligation is met.

Valid knowledge contains at most one concrete value per location. Two values
for the same register, flag, memory location, or control location are a
contradiction rather than extra precision. The fallback is proved to preserve
this location-uniqueness invariant.

Three cases stay separate:

| Case | Meaning | Result |
| --- | --- | --- |
| semantic gap | decoded form lacks verified semantics | dependent facts removed; incomplete-semantics obligation |
| evidence gap | required bytes/registers/system state were not captured | dependent facts removed; missing-capture observation |
| architectural undefined | a supported rule explicitly leaves named outputs undefined | named facts removed and locations marked architecturally undefined; supported transition may still retire |

`KnowledgeLE` is the positive-fact information order. General theorems prove
that `UnknownInstructionFallback` discards every concrete fact, remains below
its input in the information order, preserves valid knowledge (including
location uniqueness), and excludes retirement, faults, successful
transitions, and completed control-flow successors. Separate helper theorems
prove every required dependent fact is absent after selective fallback.

Adapters should bind this contract to the existing machine analysis as follows:

```text
Projection      = UnknownInstructionFallback(before)
Uses(site)      = every possibly read location
MustDefs(site)  = {}
MayDefs(site)   = every dependent location
StateSteps      contributes no fallback step
TerminalSteps   contributes no fallback transition
CompleteSites   excludes site
StructuralEdges remain present with unknown feasibility
```

An adapter may retain already discovered structural successors, but it must not
mark them exhaustive from this fallback. The `successors=[]` field means this
contract itself contributes no target; `successorsComplete=false` preserves the
unresolved-control obligation.

Validation:

```sh
cd Specs
apalache-mc typecheck AMD64Unsupported.tla
apalache-mc typecheck AMD64UnsupportedChecks.tla
tlc -deadlock -cleanup -config AMD64Unsupported.cfg AMD64UnsupportedChecks.tla
cd ../lean
lake build AMD64.Unsupported AMD64.UnsupportedChecks
lake env lean AMD64/UnsupportedChecks.lean
lake env lean AMD64/UnsupportedAudit.lean
```
