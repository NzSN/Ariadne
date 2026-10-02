# Stage D D1 review: MOV reg64, imm32

> **Retired 2026-10-02.** This document and its ISA proof/profile artifacts
> are historical reference, outside active development and qualification.
> Milestones and commands below describe the former research track. See the
> [current semantic assurance decision](semantic-assurance.md).

Reviewed **2026-09-29** for the first case of the now-retired Stage D project;
see the [retirement decision](semantic-assurance.md).
This closes a bounded **source and decoder observation**, not any of the
eight instruction-step obligations or the `register-core` milestone. The
[D0 baseline](../../evidence/Ariadne/stage-d-baseline.json) and [D1 observation report](../../evidence/Ariadne/stage-d-mov-observation.json)
retain the exact hashes and positive/negative rows.

## Authority and case identity

| Item | Current pinned value |
| --- | --- |
| Case | `register-core:AMD64-F-0503-R` |
| Source form SHA-256 | `d45a228c0720624d73a267ced2b728de85f0058ef94601f61e459329f8fbaa29` |
| Scoped case SHA-256 | `9ee47873244e00ea52502f00b5438fae3cbfaddede1925a74ddf88d3ce67d0c2` |
| User64 profile SHA-256 | `5c07adb4b1391d5b2ec29348b208789c2469b2728afd700f27cd3a90bef078cf` |
| AMD Volume 3, publication 24594 rev 3.38 | PDF SHA-256 `e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee`; PDF pages 54, 283–284 ([publisher](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB)) |
| AMD Volume 2, publication 24593 rev 3.45 | PDF SHA-256 `7257d41d3584822edb7934e2c630c7d3865eea30c0ab95b8de4e546088d5ea9a`; PDF page 93 ([publisher](https://docs.amd.com/v/u/en-US/24593_3.45_APM_Vol2_PUB)) |

Volume 3's MOV table gives `C7 /0 id` for a signed imm32 moved into a 64-bit
register or memory destination, and says MOV does not change rFLAGS. The
`-R` source-form variant selects only the **register** alternative. The generic
`AMD64-F-0503` memory alternative remains a separate `ram-data` case with its
own source-form issue. Volume 2 says ordinary 64-bit-mode operands default
to 32 bits and REX selects 64-bit operation; Volume 3's prefix chapter says
REX.W takes precedence over 66h. Volume 3's LOCK list excludes MOV and
specifies an invalid-opcode exception for an inapplicable LOCK prefix.

The form catalogue's `encoding.rex` value
`{"knowledge":"table-evidence","w_required":false}` records only what is
**explicitly printed in the opcode table cell**. Its reviewed
`constraints.prefixes.required=["rex-w"]` records the mode-dependent
64-bit operand requirement. These are distinct evidence layers, so no form
metadata or case hash is changed by this review. A future byte-to-form binder
must enforce REX.W; it must not treat the table-only `false` as permission to
execute the 64-bit case without W.

## Exact LLVM MC 20.1.2 observations

The pinned helper was run under both Windows AMD64 and Linux AMD64 targets.
Both produced the same relevant rows:

| Bytes | Observation | Case decision |
| --- | --- | --- |
| `48c7c0ffffffff` | `MOV64ri32`, RAX, immediate `-1`, length 7 | Candidate payload |
| `48c7c000000080` | `MOV64ri32`, RAX, immediate `-2147483648`, length 7 | Candidate sign bit |
| `49c7c000000080` | `MOV64ri32`, R8, immediate `-2147483648`, length 7 | Candidate extended GPR |
| `6648c7c0ffffffff` | `MOV64ri32`, RAX, immediate `-1`, length 8 | Candidate with REX.W precedence |
| `c7c0ffffffff` | `MOV32ri_alt`, EAX, length 6 | Different operand-size case |
| `48c700ffffffff` | `MOV64mi32`, memory tuple, length 7 | `ram-data`, not this register case |
| `f048c7c0ffffffff` | `LOCK_PREFIX` at length 1 | Never accept as this case; the manual, not LLVM's prefix row, supplies the #UD claim |
| `48c7c8ffffffff` | Invalid encoding | No candidate payload |

The [observation checker](../../tools/check_stage_d_mov_binding.py) validates
all pinned manual bytes, the form/profile/case identity and these rows under
both target profiles. An LLVM opcode name is **not** a proof of legal prefixes,
architectural values, faults or instruction retirement.

## Existing formal components and open boundary

`Specs/AMD64InstructionFormsCore.tla` and
`lean/AMD64/InstructionFormsCore.lean` define the signed 32-to-64 register
form. `AMD64IntegerExecution.tla` and `lean/AMD64/IntegerExecution.lean`
dispatch the reviewed form to a MOV **body**; existing checked examples cover
one signed payload. Their fallthrough helpers advance RIP only under supplied
fetch/event assumptions and label the result `fallthrough-applied`, not
`retired`. The later [historical Stage D validation record](../../evidence/Ariadne/stage-d-progress-validation.json) adds bounded
fault and analyzer-projection witnesses. There is still no case-bound proof
composing the full successful/faulting architectural boundary for all admitted
payloads, TLA+/Lean correspondence for that composition, or the general
conservative projection. The coverage ledger therefore retains **zero**
accepted semantic cases and this row's open obligations. D4 remains gated.
