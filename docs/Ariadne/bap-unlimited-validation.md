# BAP workload qualification with unlimited latency

## Context and follow-up

**Status.** Historical policy delivery on 2026-10-03; its unlimited BAP workload
timing policy remains active. That record passes 17 gates and 60 controls, with
full Stage 1 exit and the Stage 2 prerequisite satisfied. The later
[Stage 2 qualification](bap-core-qualification.md) records native adoption.

**Why this document exists.** The [replacement capture delivery](bap-windows-repin-validation.md)
measured a 10.67 s CLI median under the former 2 s condition. The user explicitly
requested removing that limit.

**What this document establishes.** Valid measured latency no longer rejects the
active BAP workload. Artifact identity, capture provenance, independent producer
evidence, exact 98-start coverage, source/tool integrity and implementation gates
remain qualification requirements.

**Where to go next.**


- [Native Stage 2 qualification](bap-core-qualification.md) — records the later completed native implementation and current retained acceptance.

- [BAP integration plan](../../Plans/bap-integration.md) — applies the new Stage 1
  exit and Stage 2 prerequisite policy.
- [Active workload pin](../../evidence/Ariadne/bap-windows-workload-case.json) —
  records `windowsBudgetMs: null` and `timingPolicy: unlimited`.
- [BAP module guide](modules/bap.md) — provides the native qualification commands.

**What remains unresolved.** Unlimited qualification establishes no performance bound. Native
Stage 2 is now [qualified](bap-core-qualification.md) within its exercised corpus.
The [active Windows I4 replacement](i4-windows-repin-validation.md) retains its
unmet 2,000 ms CLI ceiling; [controlled Windows I5a](i5a-native-qualification.md)
passes separate 1,500 ms CLI and 10 ms phase limits. This policy does not waive
either investigation budget.

For the wider context, see the [documentation map](../documentation-map.md).

## Policy and evidence

Workload schema `ariadne.bap-workloads/v4` requires the explicit
`windowsWorkloadTimingPolicy: unlimited` and `windowsWorkloadBudgetMs: null`
fields. Missing fields, a numeric budget or an infinity value are rejected.
Aggregate schema `ariadne.bap-only-removal/v5` applies the same policy.

Measurements still require a release build, one warm-up and at least five
finite, nonnegative raw samples with a matching recomputed summary. For valid
evidence the qualification status is `unlimited`, `valid=true` and
`targetMet=true`; the measured median is retained. Missing or invalid evidence
cannot qualify, and implementation failures still block full Stage 1 exit and
the Stage 2 prerequisite.

The policy removes the latency acceptance ceiling. Operational subprocess
timeouts and analysis resource limits remain separate failure controls.
The frozen dump, query and input bundle are unchanged. Earlier measurement
records retain their original budget and verdict as historical evidence.

All 60 controlled workload/validator/aggregate tests pass, including very large
finite timings, old-schema rejection, explicit manifest policy checks and the
existing malformed-evidence controls. The [fresh acceptance record](../../evidence/Ariadne/bap-unlimited-validation.json)
passes all 17 gates with 178 stable source hashes. Native integration and five
release workloads were rerun; the model, mutation and Stage E records were
reused after complete source and applicable tool-hash checks.

The new measured Windows CLI median is **3,111.33 ms**, retained as an
observation without an acceptance ceiling. The analysis binaries are unchanged
by this policy update. Earlier runs retain their own measurements; no performance
optimization is claimed.

`stage1ExitPassed=true`, `stage2PrerequisiteSatisfied=true` and
`stage2Started=false` in that historical policy record. The later native
Stage 2 result remains a separate qualification. The [evidence manifest](../../evidence/Ariadne/bap-unlimited-evidence-manifest.json)
binds the raw samples, reports, logs and source copies. Earlier evidence archives
remain unchanged.
