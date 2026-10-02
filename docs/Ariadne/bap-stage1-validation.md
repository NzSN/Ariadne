# Stage 1 BAP semantic backend: implementation and validation

> Historical Stage 1 selection record. The subsequent
> [LLVM semantic-backend removal](../../Plans/bap-only-semantics.md) changes
> the production default and fallback policy; this record retains its original
> tested source hashes and does not certify the later implementation.

Recorded **2026-10-01** against the working tree following `b3fb3ce`.
The [Stage 1 plan](../../Plans/bap-integration.md#stage-1-bap-semantic-backend)
is implemented. **Its exit gate remains partial:** fresh selected-backend
acceptance and timing on the original 98-instruction Windows capture are
unavailable. This does not satisfy Stage 2's prerequisite or authorize default
promotion. LLVM remains the default; Stage 2 has not started.

The [source-bound record](bap-stage1-validation.json) passes **16/16 implementation
gates** with **92 stable source hashes**. Its `implementationGatesPassed` is true,
while `passed` and `stage1ExitPassed` are false because the missing S4/S5 clause
is required by the plan. The checker returns **2** for this partial outcome,
**1** for a failing implementation gate, and **0** only for full Stage 1 exit.
The original [pre-change baseline](bap-stage1-baseline.json) and historical
acceptance records remain separate.

## Delivered path

A [hash-pinned native helper](../../native/bap/README.md) hosts BAP's OCaml
runtime through its typed C API. The optional [Rust adapter](modules/bap.md)
validates bounded messages and projects a finite supported BIL subset into
canonical byte-register, flag and weak-memory effects. The immutable minidump
reader, query roots/seeds/limits and Rust analysis core continue to own their
existing responsibilities. The root crate remains dependency-free and forbids
unsafe code.

The CLI accepts `--semantics-backend llvm|bap`, plus `--bap-helper` and
`--bap-runtime` for BAP selection. Text, DOT and JSON include per-site provider,
helper/runtime/AST hashes, projection, quality, fallback and gaps. Default LLVM
output omits the optional semantic field. Selected infrastructure failures
prevent publication, and helper exit is checked before publishing a report.

The official v2.5.0 asset label reports **2.5.0-alpha+baa9022** in the upstream
CLI and **2.5.0-alpha** in the C runtime. Acceptance covers the exact locked
payloads and explicit **legacy** lifter, rather than clean stable-tag build
provenance. Linux-host BAP and LLVM MC 20.1.2 run in separate processes with
isolated loader settings; both Windows/Linux dump targets were exercised.
See the [design](bap-semantic-backend-design.md) and
[source/API review](bap-projection-source-review.md).

## Exercised evidence

| Boundary | Current evidence |
| --- | --- |
| Native producer | 34 retained exact byte/BIL cases; the current helper reproduces the corpus byte-for-byte. 23 opcode forms are admitted by the projection whitelist. |
| Projection | Independent AL/AH/AX/EAX/RAX, extension, address/load/store, CMOV, arithmetic/flags, stack, branch and shift expectations. Generic unknowns retain old origins; stores never must-kill `memory:any`. |
| Protocol | Malformed/duplicate/unknown fields, wrong schema/VA/snapshot/batch/bytes/length/count, missing rows, invalid AST bounds, oversized output, timeout, trailing output and failed exit are rejected. Failed sessions cannot be reused. |
| Reference comparison | Decode/consumption, control and reviewed effect-shape disagreements remain explicit. Unexplained empty lifts and unreviewed prefixes never establish no-ops or fallthrough. |
| Input/report | Both Stage B platform fixtures, short/conflicting/absent capture, missing seeds, call-only discovery, snapshot/target reset and all report formats. A separate [high-VA native probe](bap-stage1-high-va-probe.json) verifies the actual `0xffff800000001064` JNE target. |
| Model | 8 bounded BAP-produced inputs; independent TLC safety/termination checks and **99 complete observations**, comparing all **9 state fields** in sequence. This checks the Rust solver relative to produced summaries; producer semantics are separately exercised. |
| Mutations | **15/15** mechanically changed real producer/adapter implementations rejected through unchanged observers: reads, kills, unknowns, binding, control, snapshot reuse, call preservation and the native EXTRACT getter pair. Compile/timeout failures receive no detection credit. |
| Existing regression | Fresh **12/12 Stage E gates**, including the full minidump/effects/formal/mutation regression. Generated MirrorRust replay still matches **64 traces and 326 observations**, and detects its 15 existing engine mutants. |

The [fresh Stage E regression record](bap-stage1-stage-e-regression.json) binds
250 sources/artifacts. The original Stage E publication remains evidence for
its historical source snapshot. This change does not accept an AMD64 ISA step:
**Stage D remains 0/49**, and universal Rust refinement remains open.

## Release workload results

All runs use the same host, captured query, default limits and release builds.
Each backend has one warm-up and five measured CLI runs; hashes of all three
reports are stable within each query/backend. The phase benchmark uses the
same repeat policy and separates runtime verification, reference decoding,
helper startup, lift/transport, projection, shutdown, analysis and rendering.
The [CLI samples](bap-stage1-cli.csv) and [phase samples](bap-stage1-stage.csv)
retain spread and resource outcomes; full summaries and binary hashes are in
the machine-readable record.

| Query | LLVM median | BAP median | Result |
| --- | ---: | ---: | --- |
| Stage B Linux | 102 ms | 761 ms | Same 4 decoded sites and 2-site producer slice. |
| Stage B Windows | 88 ms | 762 ms | Same 4 decoded sites and 2-site producer slice. |
| Controlled NOT fixture | 47 ms | 771 ms | Coverage rises from 1 to 4 decoded sites; the missing store seed becomes the independently expected 3-site producer slice. |
| Retained real Linux capture | 651 ms | 1,296 ms | Same analysis result: 34 decoded, 45 edges, 28 slice sites and 1 obligation. |
| Original Windows 98-site query | Unavailable for fresh comparison | Unavailable | Historical LLVM timing does not qualify this backend. |

The measured optional-backend cost on the real Linux query is approximately
**645 ms**. Most added cost is runtime identity verification and helper startup;
the lift/projection phases remain separately measured. Peak RSS and min/max
spread are retained rather than inferred from the medians. These observations
establish a finite coverage benefit with an explicit cost, not a general speedup.

## Remaining exit clause and rerun

S4/S5 still require the [pinned original Windows capture](priority-4-real-capture-case.json):
**2,028,400 bytes**, SHA-256
`4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86`.
Its query is entry `0x00007ff6451d52d0`, seed `0x00007ff6451d530f`, with the
independent address-producer witness at `0x00007ff6451d530b`. No bytes were
reconstructed or substituted. The original 2,000 ms median target remains a
separate prerequisite before considering default promotion.

```sh
ARIADNE_PRIORITY4_DUMP=/path/to/pinned.dmp python3 tools/check_bap_semantics.py
```

The checker can reuse passing model, mutation, workload and Stage E records
only after exact source hashes and relevant binary hashes match. A supplied
Windows capture must match its hash/size and preserve the independent producer,
seed and eight RCX-byte origin witnesses before measurement can qualify it.
Re-freeze the final record after any source/tool changes.

The [retained evidence manifest](bap-stage1-evidence-manifest.json) binds a
[compressed derived-evidence bundle](bap-stage1-evidence.tar.gz): actual/oracle
traces, mutation/regression logs, native BIL and selected CLI reports. Raw dumps,
upstream runtime archives and compiled caches remain outside tracked files.
