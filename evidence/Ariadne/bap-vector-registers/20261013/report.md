# Finite vector-register validation, 2026-10-13

## Context and follow-up

**Status.** The finite vector namespace is implemented and passes source-bound
root/native/replay/mutation checks. The original frame-path query remains
unavailable; this record does not pass its full-dump acceptance gate.

**Why this document exists.** The user requested vector-register admission after
the [dump03958 attempt](../../frame-paths/dump03958-20261013/report.md) stopped at
`MOVAPS/YMM6`. The [canonical BAP design](../../../../docs/Ariadne/bap-analysis-core-design.md#vector-register-admission)
defines the new namespace and coarse effect contract.

**What this document establishes.** Fresh validation of producer profile
`bap-bit-provenance-v4`, exact sources/tools, positive cases, conservative
refusals and the unchanged captured-query availability boundary.
[validation.json](validation.json) contains the executed gates and source/tool
hashes; [artifact-manifest.json](artifact-manifest.json) binds the original
retrieved evidence bytes.

**Where to go next.** The [V0–V2 plan](../../../../Plans/bap-vector-registers.md)
records execution and scope. Consult the [investigation contract](../../../../docs/Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing)
for frame anchors and unavailable answers, and the
[BAP trust boundary](../../../../docs/Ariadne/semantic-assurance.md) for lifting
and qualification limits.

**What remains unresolved.** General SIMD/ZMM/opmask coverage, fine vector-byte
origins, alignment-exception handling, XMM unwind recipes, production runtime
budget configuration and successful full-dump path enumeration remain outside
this change. Earlier P4/performance records retain their original source
identities; no new release or root-cause claim follows.

## Implemented contract

- XMM0–15 have 128-bit views of canonical 256-bit YMM0–15 backing values.
  Names, indices and widths are checked; other architectural namespaces remain
  explicit exclusions.
- Public vector effects use existing `state:other`. Individual writes never
  must-kill the aggregate's prior origins. Typed 128/256-bit stores retain both
  payload and address inputs, and never must-kill `memory:any`.
- A decoded vector operand cannot be replaced by a later filtered GPR address
  operand when binding destinations. This prevents false `RSP` writes on loads.
- BAP remains the semantic producer. LLVM MC remains the independent decode
  reference; no LLVM effect fallback or exception no-op is introduced.
- New reports identify profile v4. Strict scalar output migration accepts its
  declared metadata/derived-ID changes while rejecting changed effects/evidence.

## Executed checks and retained boundaries

All qualification builds ran in the established isolated remote WSL environment
via the [r-windev skill](/home/nzsn/Repos/skills/skills/local/r-windev/SKILL.md),
using a fresh task checkout and the frozen read-only MirrorRust dependency.
The verified source snapshot is uncommitted above parent `da7308aecda19b45c9257a5414b7d405fcd8a7dd`;
all 380 recorded source/tool/fixture hashes match the current checkout.

Remote root formatting, default/core-only tests, all-feature/all-target Clippy,
layout and release build pass. Ordinary root tests leave native prerequisites
ignored; the following separate commands explicitly exercised them:

| Check | Fresh result |
| --- | --- |
| Pinned native producer | 9 tests pass, including five projected vector cases and the explicit MOVAPS alignment refusal. |
| Decoder/lifter disagreement and conservative unknown handling | 1 native test passes. |
| Captured native/reference integration | 6 tests pass, including independent Windows/Linux vector captures and entry-origin preservation. |
| Frame-path native integration | 1 finite native test passes; this is synthetic qualification. |
| Core and finite-stateflow replay | Current source-bound replay passes; raw result is [replay/result.json](replay/result.json). |
| Focused vector mutation campaign | Six mutants rejected by seven intended assertions; unchanged observers and restored source. [Mutation report](mutations/report.json). |
| Profile migration and native qualification receipt contracts | 3 and 14 Python tests pass. |

Native vector cases are `MOVUPS` store/load, `MOVAPS` register move and VEX
`VMOVUPS` 128/256-bit register moves. The captured aligned-memory MOVAPS remains
an explicit refusal. Six mutants cover aggregate kills, bank collapse, wrong
XMM half, upper-half clobber, payload/address confusion and false GPR destination
binding. Compilation failures are not counted as sensitivity.

Logs preserve the initial runner errors: layout inherited `CARGO_TARGET_DIR`,
and the release command omitted the required `validation` feature. Corrected
commands pass. The first replay/mutation attempt exhausted remote disk; hashes
of checked debug executables were saved before removing only task-generated
debug caches. Private release caches and replay build outputs remain separate;
the retry passes. Earlier local preliminary checks are outside this fresh
remote qualification tier.

The retrieval archive was 9,592,290 bytes with SHA-256
`293d0e47e9762c5c2db3f9aaa653641db2416eabb1610d7f85ce7cf9565d2ed0`.
Its 85 retained files and all source hashes were checked after retrieval.
The archive excludes original dump/PDB binaries and build directories.
Large complete JSON reports are retained as gzip files.

## Actual dump retry

The original dump SHA-256 remains
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`.
The unchanged query is physical frames 1→0, exception thread 23668, `NP = 10`.
The public-API probe retains its explicit larger runtime/read/output budgets,
Rust reference analysis and pinned BAP preparation; no extra roots or symbol
bytes were supplied.

The retry recovers two frames and prepares the same 9-node caller / 768-node
Scanner graphs. It returns `coverage: unavailable`, zero retained paths and
zero search states because the caller's active call anchor is not admitted.
At `0x00007ff7744033b3`, bytes `0f29b42440020000`, the diagnostic now reports:

```text
projection: bap-bit-provenance-v4
status: opaque-unsupported
gap: unmodeled BIL control/special/loop semantics
```

`YMM6` is accepted; the remaining construct is the lift's alignment condition
and exception 13 (`#GP`). This is an analysis admission limit, not an observed
alignment fault. BIL hash
`fe37ab3c15e9e498522eb0cf192ed93706ea1e2dcc7339a9305434adaa10757a`
matches the original diagnostic: no lifter semantics were substituted.
The runtime-table default and older-frame `UWOP_SAVE_XMM128` stop remain.

Raw results: [probe summary](api-probe/probe-summary.json),
[frame-path result, gzip](api-probe/frame-paths.json.gz),
[instruction diagnostic](blocker-instruction.json) and [run log](frame-probe.log).
Zero paths is an unavailable answer, not proof that no path exists.
