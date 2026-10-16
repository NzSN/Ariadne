# Unresolved blockers for dump03958

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

Verified against the latest source-bound request-budget retry on 2026-10-14. All 686 recorded source/tool/document hashes match the current checkout. No build or new dump analysis was required for this inventory.

Dump: `dump_03958DA4FCA844A786262A1053`  
Thread: **23668**; requested frame pair: **1 → 0**; original requested path bound: **10**.  
SHA-256: `9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`.

**The remaining analysis blocker is incomplete candidate coverage.** The guard report contains **28 barriers: nine unresolved indirect jumps and 19 semantic stops**. Consequently, MOVAPS at `0x00007ff7744033b3` remains **unknown**. A 32 MiB native request budget now admits the larger request successfully.

## Current blockers and their relationship

| Item | Observed result | Why it matters |
| --- | --- | --- |
| Incomplete candidate coverage | `candidate-coverage-incomplete`; 28 explicit barriers. | The checker cannot certify the represented incoming control flow under its current contract. |
| Indirect control targets | Nine register jumps have empty target sets and `complete=false`. | Their possible destinations remain unresolved; absence of targets in the report does not establish absence of target addresses in the dump. |
| Semantic/control stops | Nineteen sites have `kind=stop`, `complete=false`, `opaque=true`. | They retain unadmitted control/exception behavior and contribute to the guard coverage barrier. |
| Initial MOVAPS normal admission | At `0x00007ff7744033b3`, verdict `unknown`, residue mask `0xffff`, residual `normal-or-alignment-fault-unresolved`; no normal AST selected. | This is a consequence of incomplete coverage. It is not an observed misalignment or proof that the instruction faults. |
| Guard coverage policy | `closure_complete=true`, but the stronger coverage check fails. | Discovery reached a fixed point; proof coverage additionally requires no barriers, complete indirect control and represented/reviewed local continuations. The current checker widens all residue facts to TOP when that contract fails. |

The initial MOVAPS bytes are `0f29b42440020000`: `movaps [rsp+0x240], xmm6`. The normal-call entry premise is still explicitly assumed. The present whole-graph widening prevents that premise from yielding an alignment certificate for this query. Region-specific incoming coverage has not been qualified.

## Nine unresolved indirect jumps

These are captured instructions represented by the candidate report. Their target lists are empty; this inventory does not determine which jump executed or its historical register value.

| Address | Captured bytes | Form | Reported targets |
| --- | --- | --- | --- |
| `0x00007ff77440361f` | `ffe0` | `jmp rax` | Empty; incomplete. |
| `0x00007ff774403fd7` | `ffe2` | `jmp rdx` | Empty; incomplete. |
| `0x00007ff77440417a` | `ffe1` | `jmp rcx` | Empty; incomplete. |
| `0x00007ff774404384` | `ffe0` | `jmp rax` | Empty; incomplete. |
| `0x00007ff7744048c5` | `ffe0` | `jmp rax` | Empty; incomplete. |
| `0x00007ff774408ab0` | `ffe0` | `jmp rax` | Empty; incomplete. |
| `0x00007ff774409837` | `ffe1` | `jmp rcx` | Empty; incomplete. |
| `0x00007ff7744099bf` | `41ffe0` | `jmp r8` | Empty; incomplete. |
| `0x00007ff77440da09` | `41ffe0` | `jmp r8` | Empty; incomplete. |

## Nineteen semantic stops

The bytes below identify the sites. Labels for INT3/UD2 describe their instruction encodings; their occurrence in the candidate graph is not evidence that those traps executed. BIL admission is recorded separately.

| Address | Captured bytes | Current boundary |
| --- | --- | --- |
| `0x00007ff7744035c9` | `0f28b42440020000` | `movaps xmm6, [rsp+0x240]` load with an alignment branch; current reviewed normal selector covers the store form. |
| `0x00007ff77440b0e0` | `670fb94012` | Retained BIL is empty; no admitted normal/control semantics. Exact mnemonic/lifter failure is not attributed here. |
| `0x00007ff77440b30d` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440b753` | `0f0b` | UD2 encoding; retained BIL is empty; no admitted normal semantics. |
| `0x00007ff77440ba62` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba65` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba68` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba6b` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba6e` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba71` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba74` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440ba77` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440c709` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440c7a0` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440c7a3` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440dd2b` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440dd2e` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440dd7e` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |
| `0x00007ff77440dd81` | `cc` | INT3 encoding; BAP `Exception(3)` remains an unsupported control/exception stop. |

## Independent conditions and outstanding validation

| Item | Status | Scope |
| --- | --- | --- |
| Original 4,096-start discovery budget | Still stops with `materialization limit: instruction starts`. | Configuration condition: explicit expanded discovery bypasses it and prepares **4,764** candidate sites, **4,744** decodable sites. |
| Older-frame unwind | `unsupported-unwind-operation` when continuing beyond the recovered frames. | Both requested frames are recovered, so this does not by itself prevent the requested **1 → 0** pair. Exact additional unwind diagnosis is separate. |
| Full native core execution and frame-path enumeration | Not performed in the latest retry. | Native initialization succeeded, but the probe deliberately ran **no core steps or path enumeration**. A new zero-path or full-analysis result has not been established. |
| Response/result and other module limits | Still apply independently. | The latest initialization did not fail these limits; they are not observed current blockers. |

## Resolved blockers

- XORPS at `0x00007ff7744075b3` no longer fails shift operand-width admission.
- Guard-profile defaults no longer act as hard ceilings; the larger query uses a **32 MiB evidence budget**.
- The native request limit is configurable. The **9,001,701-byte guard report** is admitted at **33,554,432 request bytes**. The unchanged **8,388,608-byte default** still rejects that larger request.

Budget increases permit transport/preparation; they do not replace missing control semantics, incoming-coverage evidence or an alignment proof.

## Evidence and source

- [Latest initialization comparison](../../evidence/Ariadne/native-request-budget/20261014/artifacts/probe-expanded/preparation-outcome.json): exact budgets, successful 32 MiB native initialization, preserved incomplete-coverage result.
- [Guard report](../../evidence/Ariadne/native-request-budget/20261014/artifacts/probe-expanded/guard-report.json): all 28 barrier sites, original captured BIL, candidate graph and unknown MOVAPS verdict.
- [Original discovery-budget outcome](../../evidence/Ariadne/native-request-budget/20261014/artifacts/probe-original-discovery/preparation-outcome.json): 4,096-start stop and recovered-frame count.
- [Qualification summary](../../evidence/Ariadne/native-request-budget/20261014/README.md): exercised corpus and explicit unperformed work.
- [Coverage check](../../src/bap/guard_admission.rs#L764) and [global widening](../../src/bap/guard_admission.rs#L979): explain why a discovery fixed point still yields TOP and an unknown guard.

This list reports possible structural/semantic dependencies of one immutable snapshot. It does not identify executed history, a selected writer or a crash root cause.


## Context and follow-up

**Status.** Restored historical chat explanation. The original text and its evidence scope remain dated.

**Why this document exists.** It preserves an explanation presented through `wslview`; the [chat-document convention](../../../skills/skills/productivity/chatdoc/SKILL.md) gives it a durable home.

**What this document establishes.** The body records the mechanism, observations and limits stated in that conversation.

**Where to go next.** The [chat report index](ariadne-reports-index.md) links related reports; the [assurance contract](../../docs/Ariadne/semantic-assurance.md) defines current responsibilities.

**What remains unresolved.** Restoration does not verify the report against the current implementation or refresh its original qualification.
