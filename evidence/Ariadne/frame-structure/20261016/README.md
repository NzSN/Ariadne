# Stage 5.1 structural frame report — qualified finite scope

## Context and follow-up

**Status.** SF0–SF6 pass the 2026-10-16 qualification within the Windows AMD64
physical-frame/unwind and reached E8-call profile. The corrected source capsule,
runtime inventory, model/oracle, compiled mutations, capture/compatibility,
named-dump and saved-replay tiers have separate retained receipts.

**Why this document exists.** The [canonical contract](../../../../docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
separates useful recovery structure from full caller dataflow. The
[SF0–SF6 ledger](../../../../.agents/plans/frame-structure-report.md) records the
implemented stages and finite acceptance boundaries.

**What this document establishes.** Source-bound qualification of
`ariadne.frame-structure/v1`, its `rust-recovery/v1` producer and opt-in CLI.
The report uses production BAP semantics and the LLVM MC independent
decode/control reference. It does not qualify a native structural producer or
replacement full-analysis backend.

**Where to go next.** Read the [qualification summary](qualification.json),
[artifact manifest](manifest.json), [source inventory](source-manifest.json),
[runtime inventory](runtime-source.json), [corpus policy](corpus-policy.json)
and [final dump comparison](dump-summary.json). The
[evidence archive](evidence.tar.gz) retains raw logs, exact source/tool/runtime
inventories, failure history and complete output files; its byte identity is
recorded in the manifest. The [earlier caller record](../../caller-semantic-coverage/20261015/README.md#original-dump-result)
defines the frozen 075602 comparison baseline. The
[checkpoint](../../../../CHECKPOINTS.md) records delivery chronology.

**What remains unresolved.** Caller guarded load `0x00007ff7744035c9`, callee
indirect sites `0x00007ff77443da0e` / `0x00007ff77443e200`, exceptional exits and
opaque call context remain explicit. Caller-coverage S6, frame-path F4, full
caller state parity, general unwinding, path enumeration, origins and executed
history are outside this completed Stage 5.1 scope. Finite conformance is not
universal Rust/native refinement or independent ISA proof.

## Source, producer and artifact identities

| Item | SHA-256 / identity |
| --- | --- |
| Baseline revision | `4811d7de6f2b86319135a5f0a1a18c397a4cd4c2` |
| Corrected source capsule, 1,093 files | `8266a844e60e3afbcaa8f0bba557899a0466e18940d8fa881630377cf78bb37c` |
| Runtime inventory, 693 files, verified unchanged | `fc946604484523b903a97b84a8e49526099fdb74aaae890981516d3a5bbeff05` |
| Qualified CLI binary | `a5121bd1f57b5cd67ccfa87e7e461a1d3483f0cbc3379f99419497009f40a982` |
| BAP helper | `6d910bf619f6ece729e85e857b60d7a22953bb633a4a43ffd99c5a5919ecc1cf` |
| LLVM decode/control reference | `6bb0005e6416f172f88c4d122ae8908862adbe9d1d2f225046df17ae857d9349` |
| Frozen comparison receipt | `ab5a62fb40c105d94edd04da27bf9d3e0a5cbe281c08a5132240a151c62dc890` |

The complete source/runtime/tool/dependency inventories and raw campaign
receipts are retained in the archive and sidecar manifest. Documentation
reconciliation preserves the exercised source capsule. Earlier capsules,
storage/namespace/executable-temp failures and the Stop-barrier validator
failure are historical attempts; corrected final passes do not rewrite them.
The validator correction admits a complete captured Stop only with a valid
normal-flow terminal certificate and its exact decoder record. Ordinary opaque
Stops still cannot claim completeness.

All heavy Cargo, native, model, mutation and dump work ran in remote Windows
WSL. Final navigation checks ran locally against the maintained documentation
and old chat archives, which are not all present in the isolated remote source
capsule. Navigation checks are separate from runtime qualification.
The [publication checks](publication-verification.json), [navigation log](local-doc-links.log)
and [layout log](local-layout.log) record the final coordinator checks. The
[original remote manifest](remote-manifest.json) preserves its exact bytes;
the local manifest records the archive's repository filename.

## Exercised validation tiers

| Tier | Result and exact boundary |
| --- | --- |
| Root formatting and Clippy | `cargo fmt --all -- --check` and all-feature/all-target Clippy with warnings denied pass. |
| Root default tests | 285 pass including three doctests; 106 tests remain ignored in the ordinary run. |
| Root core-only tests | 57 pass including three doctests; 22 remain ignored. The core dependency tree activates no external crates. |
| Feature boundaries/layout | Reports-only and BAP-only checks, plus remote Rust layout, pass. |
| Structural capture CLI | One explicitly exercised ignored positive capture test passes with the pinned lifter/runtime and LLVM reference. |
| Authoritative finite model | 43 configurations pass safety/scenario/fair-termination checks on the exact retained model sources. |
| Independent literal oracle | 65 cases and eight negative observer controls pass. These are not compiled-SUT mutation credit. |
| Compiled behavioral mutations | Nine real-code mutants have passing unmodified controls and are rejected by the intended behavior observers on the final source; compile/transport failures earn no credit. |
| Release native/capture compatibility | 38 named ignored positive tests pass: five native kernels, nine BAP producer, five backend capture, nine native capture, six frame-path and four investigation controls. The frame-path set includes two actual retained legacy report versions. |
| Original dump | Final CLI publication, exact frozen-input equality and independent full-control/link comparison pass for physical frames 1→0. |
| Public saved-report API | One standalone BAP-only replay test passes with all helpers and runtime absent; JSON/text/DOT outputs are byte-identical and actual metrics confirm zero dataflow/slice work. |

The named compatibility cases qualify their declared finite source/corpus
scope. This is not a claim that every ignored test, all platform captures, full
caller analysis, all historical replay or broad release qualification passed.

## Final named-dump result

Run `dump-final-20261016T055748` analyzes
`dump_03958DA4FCA844A786262A1053`, SHA-256
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`,
thread 23668, selected physical frames 1→0. The captured chain supplies both
frames; older unwinding stops at an unsupported operation, so no general or
complete-older-stack unwinding claim is added.

| Frame | Entry | Visited | Decoded | Core edges | Pending | Stop |
| --- | --- | --- | --- | --- | --- | --- |
| 1, caller | `0x00007ff7744033a0` | 9,590 | 9,589 | 11,321 | 0 | Drained |
| 0, callee | `0x00007ff77443d960` | 778 | 778 | 895 | 0 | Drained |

Both results remain in Recover and execute zero dataflow/slice actions.
Normalized requests, captured-source projections, guard, target and composition
proofs match the frozen 075602 inputs exactly. A separate finite oracle over
those frozen inputs matches the entire typed edge set, visited/decoded/pending,
provenance, obligations and frame-qualified edges; agreement is not inferred
from counts alone. The independent link check admits reached captured E8
`0x00007ff774404108` → child entry `0x00007ff77443d960`, with exact saved
continuation `0x00007ff77440410d`, under the recorded premises.

| Published artifact | Bytes | SHA-256 |
| --- | --- | --- |
| JSON | 112,984,262 | `0b46b1796e85c522088305da62ccf2b0d146a3ac36e4be8bfac7a65e26c2989e` |
| Text | 1,911,833 | `c46faf829b9b6b9b18bb36a5b91b03fe3a86137f287e86f9cc3b428640235aa4` |
| DOT | 1,684,053 | `c46705fe04e5a63f06259e8d0d65f117a4d3f29cc96c4ae5e7ecefaa9ab0bd5e` |

Structural publication binding:
`229e9248025f1470110b652c92ea370131cee2bf4fe72484a8dee8cb4c39db18`.
The JSON contains 222,830 dictionary entries. Public saved replay with helpers
and runtime absent reproduces all three output byte streams and independently
observes zero dataflow/slice metrics. `decode` proves consistency under the
declared capture/lifting premises; `decode_expected` additionally requires a
publication binding retained independently of the untrusted report.

The run measured 103.99 seconds and 1,885,696 KiB peak RSS. These observations
are not a performance gate, a new latency guarantee or a replacement-backend
qualification.

## Preserved gaps and scope

| Frame | Typed boundaries |
| --- | --- |
| 1, caller | 29 checked exception exits, 535 opaque call-context boundaries, one unresolved guard. |
| 0, callee | 10 checked exception exits, 25 opaque call-context boundaries, eight unknown call targets, two unknown indirect targets. |

The caller unresolved guard is the final guarded load at
`0x00007ff7744035c9`; its failed final endpoint is not evidence of an observed
architectural fault there. Callee indirect sites `0x00007ff77443da0e` and
`0x00007ff77443e200` remain unknown. Checked exception exits end the accepted
local normal-completion scope; handler/debugger resumption remains outside it.
Opaque call boundaries retain context without traversing callee interiors.
Drained recovery is independent of these semantic/control gaps and establishes
neither an executed path nor semantic completeness.

## Reproduction and retained evidence

Use the exact [finite corpus policy](corpus-policy.json), matching capture and
qualified helper/runtime inventory from the archive. The new mode needs no
native-core completion executable:

```sh
target/structure-build/release/ariadne-minidump original.dmp \
  --frame-structure 1:0 --thread-id 23668 \
  --frame-structure-limits evidence/Ariadne/frame-structure/20261016/corpus-policy.json \
  --assume-windows-call-entry --resolve-indirect-targets \
  --decoder-reference target/ariadne-llvm-mc \
  --bap-helper target/ariadne-bap-lift --bap-runtime tmp/bap-setup/stable \
  --output-dir frame-structure-output
```

The archive manifest supplies each original command, source/tool identity and
artifact path. Keep source, replay and mutation build directories isolated.
Retained earlier failures explain the correction history; only the final
corrected-source receipts support this completion. Future source/helper changes
need fresh affected validation or complete identity-verified retained evidence.
