# BAP vector-register admission

## Context and follow-up

**Status.** V0–V2 implemented and validated at a finite tier on 2026-10-13. This extends
the accepted scalar producer profile with a separately identified finite vector
namespace; historical qualification remains bound to its original sources.

**Why this document exists.** The [BAP design](../../../docs/Ariadne/bap-analysis-core-design.md#projection)
rejects `YMM6` in the captured caller's MOVAPS lift, as recorded by the
[frame-path attempt](../../../evidence/Ariadne/frame-paths/dump03958-20261013/report.md).
The user requested vector-register namespace support.

**What this document establishes.** Admit XMM0–15 at 128 bits and YMM0–15 at
256 bits with canonical YMM backing and low-half XMM aliases. Map all vector
dependencies and possible writes to the existing `state:other` cell; a write
to one vector never establishes a definite replacement of that aggregate.
Support typed 128/256-bit memory payloads through BAP projection. Keep bounded
AST/type validation, unknowns, prefixes and exception/control refusals explicit.
Use producer profile `bap-bit-provenance-v4` to distinguish changed admission.

**Where to go next.** The [canonical BAP design](../../../docs/Ariadne/bap-analysis-core-design.md#vector-register-admission)
owns usage and semantics; [semantic assurance](../../../docs/Ariadne/semantic-assurance.md)
owns the trusted-lifting boundary. The [frame-path plan](../frame-path-enumeration.md)
retains its separate unwind, resource and qualification limits.

**What remains unresolved.** Fine vector-byte origins, ZMM/AVX-512/opmask state,
XMM unwind recipes and new exception modeling are outside this change. The
captured MOVAPS lift contains an alignment exception and can still stop after
namespace admission. No executed-history or root-cause claim follows.

## Stages

| Stage | Implementation and validation | Acceptance |
| --- | --- | --- |
| V0 | Freeze this finite namespace, alias and aggregate-write contract. | No new core/model transition; no `state:other` must-kill from vector writes. |
| V1 | Typed architectural admission, shared alias interpretation, conservative projection, producer identity and consumer/native compatibility. | Correct XMM/YMM widths and aliases; 128/256-bit stores retain address/payload dependencies; malformed and unmodeled state rejected. |
| V2 | Independent alias/store/conditional-origin tests, pinned native producer/native-core parity, root checks and captured-query retry. | Passing source-bound finite checks; remaining alignment/unwind/budget gaps explicitly recorded. |

Heavy builds and large-capture work use an isolated remote checkout and build
outputs. Preserve existing dirty documentation/evidence from the prior attempt.
No commit or push is included in this task.

## Dated validation

The [validation receipt](../../../evidence/Ariadne/bap-vector-registers/20261013/report.md)
binds 380 current source/tool/fixture hashes, the native helper manifest and
checked executable hashes. Remote fmt, default/core-only tests, all-feature
Clippy, root-target layout, pinned producer and capture/native parity pass.
The active core/stateflow replay passes; six focused mutants trigger seven
intended assertion failures with unchanged observers and restored sources.

The actual dump retry still returns zero paths with `coverage: unavailable`:
the namespace is admitted, but MOVAPS's alignment-exception branch is excluded.
Original runtime-table and XMM-unwind limits remain. Retained logs preserve two
runner configuration failures and the first disk-exhausted campaign; corrected
checks and a reduced-disk retry pass. Full P4, general SIMD, performance and
successful full-dump qualification are separate unexercised gates.
