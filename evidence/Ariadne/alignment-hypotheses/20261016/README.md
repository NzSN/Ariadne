# Explicit alignment hypotheses — qualified finite scope

## Context and follow-up

**Status.** H0–H5 pass the 2026-10-16 source-bound qualification within the
structural-only Windows AMD64 reviewed MOVAPS profile. The unchanged Stage 5.1
v1 evidence keeps its separate identity; the new v2 report is conditional.

**Why this document exists.** The [canonical contract](../../../../docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses)
and [execution ledger](../../../../.agents/plans/alignment-hypotheses.md) define
explicit point hypotheses without inventing roots or captured register facts.

**What this document establishes.** Finite model/oracle/runtime/mutation,
compatibility and named-dump/saved-replay acceptance for the conditional
product. BAP semantics remain trusted; this is not independent ISA proof.

**Where to go next.** Read [qualification](qualification.json),
[source inventory](source-manifest.json), [runtime inventory](runtime-source.json),
[corpus policy](corpus-policy.json), [dump comparison](dump-comparison.json) and
[publication verification](publication-verification.json). The
[manifest](manifest.json) records exact identities, including the
[raw evidence archive](evidence.tar.gz). The
[unconditional Stage 5.1 record](../../frame-structure/20261016/README.md) owns
the preserved v1 publication and its original scope.

**What remains unresolved.** The hypothesis does not establish alignment as an
observed fact, executed history, readable memory or an actually executed path.
Structural edges can compose into infeasible paths; no accumulated-path SAT/SMT
analysis is supplied. Caller S6, frame-path F4, full dataflow, target narrowing,
general instruction assumptions and performance qualification remain separate.

## Source and validation

Source capsule:
`34d078b4e3c94977620e72313111d40d52fae1978af05b0682d716d1bec5d556`
(1,060 files), baseline `4811d7de6f2b86319135a5f0a1a18c397a4cd4c2`.
The 725-file runtime inventory is unchanged during final qualification. The
post-collection documentation delta, including Specs/README.md prose, is
recorded separately; it does not replace the exercised source identity.
The retained archive contains 176 members, is 78,190,590 bytes and has SHA-256
`c27544b44b580f2fc4f790e2c0dd84ca207044481a2fccfb97fa7a943143cb44`.
The original remote manifest SHA-256 is
`bed32ffdbc42e65e6dc9e996ebcb4a25724f638ef6bdb7abc6f60aee12500326`;
[remote-manifest.json](remote-manifest.json) preserves that original receipt.
Pinned helpers remain unchanged from Stage 5.1. All heavy Cargo/native/model/
mutation/dump work runs in remote Windows WSL; final documentation navigation is
a separate local check against the maintained archive.

[Local documentation](local-doc-links.log) and [Rust layout](local-layout.log)
checks pass after publication. The [cleanup receipt](cleanup.json) records the
idle task build volume's unmount; its image is retained for reproducibility.

| Tier | Exercised result |
| --- | --- |
| Root validation | Format/Clippy pass; 298 default and 57 core-only tests pass, each including three doctests. Ordinary runs retain 108 / 22 ignored tests. |
| New kernel | Nine tests pass, including the independent 21-case runtime consumer. |
| Formal model / oracle | 25 finite configurations and 39 independent cases pass. |
| Compiled mutations | Six mutants have passing unmodified controls and are behaviorally rejected; compile or transport failures earn no credit. |
| New native capture controls | Two capture CLI tests and one conditional rehashed-codec capture test pass. |
| Compatibility | 38 named release native/capture/compatibility tests pass. This does not claim every ignored test was run. |
| Saved reports | Actual retained v1 replay is byte-identical. Standalone public v2 replay passes without native helper/runtime and preserves all three output streams and conditional scope. |
| Named dump | Baseline/conditional comparison preserves all original inputs/proofs and independently checks masked facts, final recovery and the selected normal edge. |

## Named-dump comparison

Capture `dump_03958DA4FCA844A786262A1053`, SHA-256
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`,
thread 23668, physical frames 1→0. Baseline run
`dump-baseline-20261016T094136` preserves the old qualified v1 publication and
binding `229e9248025f1470110b652c92ea370131cee2bf4fe72484a8dee8cb4c39db18`.
Conditional run `dump-conditional-20261016T094313` adds:

```text
--assume-frame-aligned 1:0x00007ff7744035c9
```

H says `(RSP + 0x240) mod 16 = 0` whenever that physical activation reaches
the reviewed MOVAPS load. It supplies no observed RSP or execution witness.
The captured bytes remain `0f28b42440020000`, original root remains
`0x00007ff7744033a0`, and the hypothesis is bound to its captured source,
decoder, original AST, query/activation and candidate epoch 609.

Hypothesis ID:
`96892f89380228b2c50c3bfff2bdd975aa1bd83ff013abfb1b8de8570884b903`.
The baseline verdict stays Unknown; conditional basis is Assumed with mask
`0x0001`. The normal edge 35c9→35d1 appears only under H. All original requests,
contexts, captured sources, guard/target/composition receipts, roots and target
facts remain unchanged as baseline inputs. No target precision under H is
claimed.

| Frame | Baseline visited / decoded / edges | Conditional visited / decoded / edges |
| --- | --- | --- |
| 1, caller | 9,590 / 9,589 / 11,321 | 9,600 / 9,600 / 11,331 |
| 0, callee | 778 / 778 / 895 | 778 / 778 / 895 |

Both products retain Recover phase and zero dataflow/slice work. An independent
explicit `(point, residue)` BFS checks 153,210 states under a 153,600-state cap
and 172,346 transfer evaluations, matching every incoming and masked fact.
This validates the finite residue product, not the feasibility of all composed
structural paths.

The caller keeps 565 boundaries: its unresolved guard is replaced by a newly
reached return's opaque context, giving 536 opaque call contexts and 29 checked
exceptional exits. The callee keeps 45 boundaries: two unknown indirect targets,
eight unknown call targets, 25 opaque contexts and 10 exceptional exits.
Handler/debugger resumption remains outside local normal-completion scope.

## Conditional publication

Schema `ariadne.frame-structure/v2`; producer
`rust-recovery-alignment-hypotheses/v1`; semantic backend BAP. The whole derived
report, participating maps/links and control provenance carry the retained H
IDs; captured byte provenance remains unchanged.

Structure binding:
`cfb480b259887fe4272afa6da5cf5a750aa5cf0c04216539cd61b2b5977b2564`.

| Format | Bytes | SHA-256 |
| --- | --- | --- |
| JSON | 116,283,519 | `7901eb7f4fd915082d742da9b7b4686ff2544bf969c18e9147cb9806cddb8bb8` |
| Text | 1,913,311 | `640bab558ac95242090a11d0044639e4ab5c01f11b839a16cf056da961a4ab85` |
| DOT | 1,686,066 | `59422ea1329eb574279f43da957aee11a3f1e7ee341f861152be7087eb2bbb3b` |

Public saved replay requires no native helper/runtime. `decode` establishes
self-contained consistency under capture/lifting premises; `decode_expected`
also checks a publication binding retained independently. Neither authenticates
H as an observed fact. The manifest and publication-verification sidecar bind
the archive and output bytes; no performance gate is claimed.
