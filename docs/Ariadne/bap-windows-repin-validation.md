# Controlled Crashpad replacement for the BAP Windows workload

## Context and follow-up

**Status.** Completed capture/repin campaign, retained as historical evidence. Its 2,000 ms timing condition was later superseded by the user-authorized [unlimited policy](bap-unlimited-validation.md). Measurements and original verdicts below retain their historical meaning.

**Why this document exists.** The [previous workload repair](bap-windows-workload-validation.md)
closed the implementation gaps but could not exercise a missing historical
Electron dump. The user requested a newly generated Crashpad capture and pin.

**What this document establishes.** The replacement's native capture,
independent artifact/query witness, durable input bundle and measured BAP
qualification. A controlled replacement does not recreate the old crash.

**Where to go next.**


- [Separate Windows I4 replacement](i4-windows-repin-validation.md) — binds this capture to the active investigation question under its unchanged timing ceiling.


- [Native Stage 2 qualification](bap-core-qualification.md) — records the completed successor analysis and its source-bound default-adoption evidence.

- [Unlimited timing policy](bap-unlimited-validation.md) — supersedes this campaign's former 2,000 ms condition by explicit user instruction.

- [Replacement plan](../../Plans/bap-windows-repin.md) — freezes the 98-instruction
  recipe, evidence conditions and unchanged 2,000 ms limit.
- [Crashpad demo recipe](../../native/crashpad-demo/README.md) — builds and runs
  the native Windows capture profile.
- [BAP integration plan](../../Plans/bap-integration.md) — records the resulting
  Stage 1 decision and the separate Stage 2 prerequisite.

**What remains unresolved.** This capture campaign did not implement Stage 2. The later [native Stage 2 delivery](bap-core-qualification.md) qualifies recovery, dataflow, slicing, stateflow and default adoption. Its BAP timing policy is unlimited. The separately authorized [active I4 replacement](i4-windows-repin-validation.md) uses this 98-start capture and remains above its unchanged 2,000 ms explanation-CLI limit. Historical Priority 4 records retain their original scope.

For the wider context, see the [documentation map](../documentation-map.md).

## Replacement boundary

The new active BAP workload is `crashpad-windows-checksum-98-v1`, a controlled
Windows AMD64 process captured by the pinned `crashpad-nzsn` handler. It is
analyzed on Linux. The capture is a real Crashpad output from a deliberately
faulting application; it is not a manually edited minidump.

The original `priority-4-real-capture-case.json` remains unchanged. Historical
Priority 4 measurements and earlier I4 records retain their own meaning. The
later [I4 re-pin](i4-windows-repin-validation.md) has its own manifest and
`ARIADNE_I4_WINDOWS_DUMP` override; its bounded timing policy is separate. BAP uses a separate manifest and `ARIADNE_BAP_WINDOWS_DUMP` override.
Its bundled input supplies the default reproducible workload after hash checks.

The new function has 98 local instruction starts: setup, eight input checksum
rounds, an indexed-load loop, a conditional diamond, stack spill/reload and an
explicit RCX producer followed by a four-byte null write. All checksum rounds
feed the address computation. The inspector checks the complete captured
function against both a byte oracle and the matching executable, plus an
independently computed checksum and exception/context evidence.

## Qualification contract

Workload schema v3 and aggregate schema v4 distinguish this capture from the
historical case. Raw sample validation, exact source/tool identities, captured
byte provenance and the producer witness remain required. The new pin requires
exactly 98 recovered starts. Full Stage 1 exit and the Stage 2 prerequisite
require all implementation gates and a release CLI median at most 2,000 ms,
using one warm-up and at least five measured samples.

The [source-bound record](../../evidence/Ariadne/bap-windows-repin-validation.json)
records capture/pin success and implementation success separately from that
failed timing condition. The workload and budget were frozen before measurement.

## Captured and pinned inputs

| Item | Verified value |
| --- | --- |
| Active pin | [bap-windows-workload-case.json](../../evidence/Ariadne/bap-windows-workload-case.json) |
| Durable replay bundle | [bap-windows-workload-inputs.tar.gz](../../evidence/Ariadne/bap-windows-workload-inputs.tar.gz), 399,636 bytes and 23 verified entries |
| Partial dump | 217,936 bytes; SHA-256 `1bd80af7a739471a7026776bfb37cbbe5953d01ad122e7cf7db0392f84da0b0a` |
| Query entry | `0x00007ff7382f4840` |
| Fault/seed | `0x00007ff7382f49b4` |
| Independent RCX producer | `0x00007ff7382f49b1` |
| Captured function | 379 bytes, 98 reviewed instruction starts |
| Crashpad revision | `7a884c25c84c46352fc6f16ef0a798ece2b77e84`, original checkout unchanged |

The native Windows build used pinned Clang/`llvm-ml`, installed Windows SDK/MSVC
libraries and the existing isolated compatibility setup. The capture used a
minimal process environment and disabled uploads. Missing-handler, invalid-mode
and invalid-profile controls all exited before creating a witness or dump.
The original default null-write profile also produced a fresh capture that
passed its independent inspector.

The new inspector compares every function byte with the matching PE and a
reviewed encoding oracle, validates short-branch targets and all four labels,
and checks the captured input array, checksum, PID, module and exception context.
The exception is a four-byte write to zero at the fault label, with RCX and RAX
both zero. The executable is retained for comparison; it supplies no fallback
bytes to Ariadne.

## Measured result and retained evidence

The fresh aggregate passes **17/17 implementation gates** with **178 stable
source hashes**. It includes **59 controlled workload/gate tests** and fresh
native integration and five release workloads. The independent inspector has
**9 passing controlled tests**. The exact replacement query produces
**98 decoded starts, 99 edges, a 90-instruction slice and zero obligations**,
with no missing seeds and all eight RCX byte origins bound to the pinned producer.

BAP's eight model cases/99 states, 16 detected mutations and the 12-gate Stage E
regression were reused after complete current inventory checks (162, 159 and
315 sources respectively), plus applicable observer/native-tool hash checks.
They were not freshly rerun for this capture-only replacement. The workload
record binds 168 source entries and all six analysis tools.

One warm-up and five measured release CLI runs give a median of
**10,667.76 ms**, range **10,408.02–10,821.89 ms**. The fixed **2,000 ms** condition
fails. The separate phase benchmark identifies these median costs:

| Phase | Median |
| --- | ---: |
| Reference decoding | 7,572.13 ms |
| BAP helper startup | 1,178.30 ms |
| Core analysis | 69.61 ms |
| Report generation | 397.33 ms |

These are separate component medians, not an additive decomposition of the CLI
median. They support investigating reference-decoder startup and batching on this
fixed query next; no performance change was made in this delivery.

CLI eligibility uses the monotonic `perf_counter_ns` samples retained in
`cli.csv`. Ancillary GNU `time` wall readings differ by about 0.70 and 0.73 seconds
on two measured runs; that clock discrepancy was not diagnosed. Both timing sets
remain far above the budget, so it cannot turn this result into a pass.

The [derived-evidence manifest](../../evidence/Ariadne/bap-windows-repin-evidence-manifest.json)
verifies **199 archive entries** and the delivery record's **192 source hashes**.
It binds build/capture/inspection records, raw samples, analyzer reports,
controlled tests, assembler proof and the separate input archive. Earlier
acceptance records are unchanged historical results.

The final flags are `implementationGatesPassed=true`,
`windowsWorkloadQualification.valid=true`, `targetMet=false`,
`stage1ExitPassed=false` and `stage2PrerequisiteSatisfied=false`.
Stage 2 was unstarted at this historical capture checkpoint; its later
[qualification](bap-core-qualification.md) is a separate accepted record.

The bundled workload runs without an external dump path:

```sh
python3 tools/measure_bap.py --output /new/workload-directory
python3 tools/check_bap_semantics.py --workload-record /new/workload-directory/report.json
```
