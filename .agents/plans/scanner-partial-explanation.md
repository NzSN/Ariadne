# Scanner partial-explanation follow-up plan

## Context and follow-up

**Status.** Plan rendered on 2026-10-11 from
`/tmp/ariadne-scanner-partial-explanation.html` (title: “Why Scanner’s explanation
is partial”). The retained baseline and its 28 gap entries were checked against
the original JSON and member manifest. This document records no new Scanner run
or implementation acceptance in that original revision. The [2026-10-19 memory
qualification](../../evidence/Ariadne/frame-question/20261019/README.md) now closes
S1's selected candidate-table scope; S2–S4 remain pending.

**Why this document exists.** The [Scanner admission resume record](../../docs/Ariadne/bap-analysis-core-design.md#admission-resume)
shows that recovery now completes, while the [investigation contract](../../docs/Ariadne/investigation-design.md#binding-and-result-contract)
still assigns a partial answer when unresolved provenance, semantics or control
obligations remain. The HTML explains that distinction; this plan turns its
remaining gaps into evidence-bound work.

**What this document establishes.** The exact retained query, status rule,
complete gap inventory and ordered follow-up gates for this Scanner case.
The goal is to improve possible-origin explanations where evidence justifies
it and give explicit requirements for the remaining unknowns. Completion of
this work does not require an unsupported promotion to `explained`.

**Where to go next.**

- [Memory-refinement design](../../docs/Ariadne/memory-provenance-refinement.md) —
  focused explanation of the four real loads, conservative XOR diagnostic,
  candidate-writer assessment and backward scalar constraints.
- [Memory-refinement execution plan](memory-provenance-refinement.md) — M0–M4
  implementation and the qualified finite model/mutation/Scanner candidate-table scope.
- [Investigation design](../../docs/Ariadne/investigation-design.md) — canonical
  query, claim, gap, publication and evidence contracts for this follow-up.
- [Evidence guide](../../evidence/Ariadne/README.md) — source/tool identity checks,
  immutable historical records and fresh qualification boundaries.

**What remains unresolved.** The snapshot does not establish the executed path,
the actual memory writer or who produced the bad RSI value. Memory refinement
now has selected full-Scanner candidate-table qualification. The 20 retained
recovery obligations and earlier-provenance boundary still need individual review.
No historical-path, root-cause, universal-refinement or release qualification
is established by this plan.

## Retained query and evidence identity

The [remote Scanner record](../../evidence/Ariadne/bap-admission/remote-20261010/report.json)
binds the baseline to its capture, query and semantic profile. Its detailed
explanation is member `artifacts/0/external/scanner/explanation.json` of the
[retained archive](../../evidence/Ariadne/bap-admission/remote-20261010/evidence.tar.gz),
listed in the [member manifest](../../evidence/Ariadne/bap-admission/remote-20261010/evidence-manifest.json).

| Field | Retained value |
| --- | --- |
| Entry | `0x00007ff77443d960` |
| Fault seed / selected instruction | `0x00007ff77443dd6e` |
| Selected memory-access index | `0` |
| Capture SHA-256 | `ed82b433501162828460ccbf067476e4683a52157372b27040f0269d2b3949c5` |
| Query ID | `f25889d585743e6f91cd579ed7b20c19d4e938c339d3b8bdf425ed0321f039b0` |
| Request SHA-256 | `5479d593ddb4696938c5747986877e10b9f68dacb1584276eacec96c16a25582` |
| Explanation member SHA-256 | `f48ca41bd52bdd233cf115c19f14a9f73d04ac02d8aa155f8c77793a9959892a` |
| Recovered instruction starts | `768` |
| Edges | `895` |
| Slice instructions | `19` |
| Missing seeds | None |
| Explanation status | `partial` |
| Explanation truncation | `false` |

The historical semantic profile uses Windows AMD64, LLVM MC 20.1.2 as decode
reference, `bap-bit-provenance-v3` and
`gpr-bytes-status-df-memory-other-v1`; its full identity remains in the original
explanation. The source HTML SHA-256 is
`81bd4e1ee9c36a2419f4c9b44446b079b936799367e92d18479619339c776786`.
Inspection verifies the retained data; it does not qualify the current checkout
against the historical source/tool inventory.

## Why the completed query remains partial

The status rule is conservative: any retained gap makes an otherwise explained
answer partial. Explanation-budget exhaustion also makes that answer partial,
but this result records `truncated=false`.

```text
if status == Explained and (gaps are nonempty or truncated):
    status = Partial
```

[`bind_investigation()`](../../src/input/investigation.rs) collects every recovery
obligation from the completed query. The [explanation builder](../../src/investigation/explain.rs)
adds those gaps and assigns the final status. Recovery obligations outside the
selected dependency slice therefore still appear in the explanation. The
counts do not mean every listed site caused the fault.

| Gap | Count | Meaning |
| --- | --- | --- |
| Unknown memory aliases | 5 labels | Four loads use the shared `memory:any` abstraction. One register-only XOR receives this label through conservative undefined-AF dependencies. |
| Entry origin | 1 site | Some provenance reaches the Scanner entry; the query supplies no earlier origin. |
| Undefined flags | 2 diagnostics | XOR at `0x00007ff77443d97a` leaves AF undefined. `UndefinedFlags` and `unknown-output:AF is undefined after xor` preserve that uncertainty. |
| Call-target obligations | 8 | Call targets remain unresolved; callee effects are handled conservatively. |
| Indirect-target obligations | 2 | Indirect control-flow target sets remain unresolved. |
| Decode failures | 10 | Recovery cannot continue through those sites with admitted semantics. |
| Total | 28 entries | Eight provenance/semantic diagnostics and twenty recovery obligations. |

The four original opcode-admission blockers are resolved in the retained run:
all four requested forms project at 30 sites. The later completion transport
allows the Scanner query to finish. These deliveries do not discharge the
remaining explanation gaps. The result supplies possible dependencies under
its stated premises.

## Scope and preservation requirements

1. Reuse the completed, immutable analysis. Preserve capture/query identity,
   virtual addresses, captured-byte precedence and explicit holes/conflicts.
2. Keep entry roots and slice seeds distinct. An earlier-entry investigation
   requires justified evidence and its own query identity.
3. Preserve original explanations and evidence. Attach refined candidate views
   separately; unresolved writers, entry memory and unknown call effects remain
   possible alternatives.
4. Keep call edges visible and local analysis on summary edges. Review all
   recovery obligations even when a site is outside the selected slice.
5. Preserve the status contract. Diagnostic clarification, a smaller candidate
   set or a completed transport does not itself justify `explained`.
6. BAP supplies production semantics. Independent LLVM decode/control facts can
   help review a site; they do not supply an automatic effect fallback.
7. Distinguish crash-time observations, possible dependencies and executed
   history. A full-memory capture or incomplete frame-path list cannot identify
   an actual writer or exclude an unresolved candidate.

## Execution stages

| Stage | Current state | Exit evidence |
| --- | --- | --- |
| S0 — preserve the baseline | Retained-data inspection complete for this document. | HTML counts and all 28 gap pairs agree with the retained JSON; explanation bytes match the member-manifest hash. No fresh analysis credit. |
| S1 — clarify and assess memory provenance | Selected candidate-table scope passes remote M4 qualification, 2026-10-19. | All 12 original candidate keys preserved with explicit unresolved reasons, default report bytes unchanged and native/Rust assessments equal; source-bound evidence retained. |
| S2 — review control and decode obligations | Pending. | A disposition and evidence requirement for each of eight call, two indirect-target and ten decode obligations. |
| S3 — review entry-origin limits | Pending. | Explicit earlier-provenance boundary; any additional accepted evidence is bound to a separate query or supported input contract. |
| S4 — qualify and publish the follow-up | Pending. | Fresh source/tool-bound checks, exact-case outputs, complete gap disposition and an honestly assigned final status. |

### S0 — preserve the baseline

Keep the original query limits, semantic profile, gap order and evidence
identities available from the retained record. Record future source/tool hashes
separately rather than overwriting the original archive or its acceptance
decision. The baseline inspection in this change verifies counts, status,
truncation and the explanation-member digest; it does not revalidate every
historical source/tool hash against current sources.

### S1 — clarify and assess memory provenance

Continue the [existing M0–M4 plan](memory-provenance-refinement.md); this stage
does not start a replacement implementation. First distinguish the four real
loads from the XOR's conservative unknown-output dependency. Preserve undefined
AF and the original diagnostic even when a separate report clarifies its cause.
Any narrowing of instruction dependencies needs its own reviewed semantics and
regression evidence.

Qualify the complete candidate-writer assessment for the load at
`0x00007ff77443dd6a`. Bind each comparison to access identities, widths,
before-instruction expressions and justified value/path premises. Proven
disjointness may exclude only the covered candidate instances; overlap retains
a possible writer; unknown relations retain the candidate and their reason.
Register names, crash-time values or an incomplete path enumeration alone do
not establish an equal base across earlier executions.

Consume exact/constrained backward values only within the
[selected memory-refinement contract](../../docs/Ariadne/memory-provenance-refinement.md).
Unknown memory and opaque calls must still overlap any precise candidate range.
Model/mutation checks and the complete Scanner table remain required M4 exits.

### S2 — review control and decode obligations

Create a per-site audit covering all 20 retained recovery obligations. For each
site, record captured bytes and provenance, available BAP/independent decode
facts, the admitted control/effect boundary, relation to the selected dependency
slice and the exact missing evidence.

Distinguish unavailable/conflicting capture, failed decoding and unsupported
semantic/control projection when the evidence permits that distinction. Do not
assume that a `DecodeFailed` label means a new opcode implementation is needed.
Calls and indirect transfers require supported target/effect evidence; a
crash-time register is not automatically the value at an earlier transfer.

Any proposed semantic or recovery change must first extend the owning design
and model contract, then receive its own focused implementation and regression
gate. Preserve unchanged obligations explicitly. Slice relevance may clarify
presentation; it does not remove a query-wide gap under the existing schema.
The [captured indirect-target resolver design](../../docs/Ariadne/indirect-target-resolution.md)
and [R0–R6 plan](indirect-target-resolution.md) now implement and qualify that separate finite
extension for finite pointer/table forms. They do not resolve or qualify this
Scanner query's indirect sites by themselves.

### S3 — review entry-origin limits

Record the location-specific earlier-provenance requirements at
`0x00007ff77443d960`. Retain entry origins when the query supplies no earlier
producer. If independently anchored earlier entry or input evidence becomes
available, bind it to its own supported investigation and compare results with
the original query. Never use a dependency site or slice seed as an invented
discovery root.

### S4 — qualify and publish the follow-up

Run affected tests and the owning native/model/report gates after any behavior
change, including applicable root checks from [AGENTS.md](../../AGENTS.md). Use
separate replay/mutation build directories under `target/`. Follow the existing
memory plan's remote requirement for heavy model, mutation and full Scanner
work; keep unavailable prerequisites and failed attempts explicit.

Re-run the bound Scanner case with recorded source/helper/runtime/dependency
identities. If query or semantic identity changes, explain that change and
compare the new case separately. Publish original and refined outputs with a
disposition for every historical gap: retained, clarified, discharged under
specified evidence, or changed under a separately reviewed contract.

Recompute status using the original rule. A useful qualified result may still
be `partial`. Claim `explained` only when the supported answer has no gaps and
no truncation; neither status establishes an executed path or root cause.
Store new raw evidence under a distinct `evidence/Ariadne/` campaign directory
and update dated validation in the owning canonical design.

## Source ownership and validation

| Responsibility | Existing owner |
| --- | --- |
| Capture/query binding and recovery-gap collection | [Input investigation adapter](../../src/input/investigation.rs) |
| Dependency traversal, gap requirements and final status | [Explanation builder](../../src/investigation/explain.rs) |
| BIL projection and conservative unknown-output dependencies | [BAP projector](../../src/bap/projection.rs) |
| Candidate assessment, backward inference and separate reports | [Memory-refinement source ownership](memory-provenance-refinement.md#source-ownership) |
| Native semantics/recovery and qualification boundary | [BAP integration design](../../docs/Ariadne/bap-analysis-core-design.md) |

This documentation change requires retained-data consistency, local-link and
diff-hygiene checks. Later behavior changes require affected Rust tests plus
format/default/core-only/Clippy checks and the owning native/model gates. Missing
helpers, runtimes, remote access or capture artifacts remain unexercised
prerequisites. Accepted P4 evidence and finite memory probes do not automatically
qualify changed sources or a full Scanner refinement campaign.

## Exact retained gap entries

The following preserves all 28 entries in their recorded order. Addresses are
semantic virtual addresses, not file offsets or graph identifiers.

| Gap code | Instruction address |
| --- | --- |
| `unknown-memory-alias` | `0x00007ff77443dd6a` |
| `entry-origin` | `0x00007ff77443d960` |
| `UndefinedFlags` | `0x00007ff77443d97a` |
| `unknown-output:AF is undefined after xor` | `0x00007ff77443d97a` |
| `unknown-memory-alias` | `0x00007ff77443d97a` |
| `unknown-memory-alias` | `0x00007ff77443d973` |
| `unknown-memory-alias` | `0x00007ff77443d986` |
| `unknown-memory-alias` | `0x00007ff77443d98e` |
| `recovery:IndirectTargets` | `0x00007ff77443da0e` |
| `recovery:IndirectTargets` | `0x00007ff77443e200` |
| `recovery:CallTargets` | `0x00007ff77443ea73` |
| `recovery:CallTargets` | `0x00007ff77443f6ba` |
| `recovery:CallTargets` | `0x00007ff77443f73b` |
| `recovery:CallTargets` | `0x00007ff77443f796` |
| `recovery:CallTargets` | `0x00007ff774441063` |
| `recovery:DecodeFailed` | `0x00007ff77444133a` |
| `recovery:DecodeFailed` | `0x00007ff77444148d` |
| `recovery:DecodeFailed` | `0x00007ff7744414a8` |
| `recovery:DecodeFailed` | `0x00007ff774441540` |
| `recovery:DecodeFailed` | `0x00007ff77444154b` |
| `recovery:DecodeFailed` | `0x00007ff77444154e` |
| `recovery:CallTargets` | `0x00007ff7744415b7` |
| `recovery:DecodeFailed` | `0x00007ff774442569` |
| `recovery:DecodeFailed` | `0x00007ff77444256c` |
| `recovery:DecodeFailed` | `0x00007ff77444256f` |
| `recovery:DecodeFailed` | `0x00007ff774442572` |
| `recovery:CallTargets` | `0x00007ff7744425bf` |
| `recovery:CallTargets` | `0x00007ff7744425e5` |

## S1 qualification follow-up, 2026-10-19

The [remote section-5/M4 record](../../evidence/Ariadne/frame-question/20261019/README.md)
uses the same `ed82b433…` Scanner snapshot and selected DD6A load. Its complete
12-origin table matches the completed baseline reaching set. Entry memory,
eight pushes and three stores all remain unresolved with explicit scope/alias
reasons. The default report is byte-preserved and native/Rust assessments match.
This closes selected memory-candidate qualification while leaving S2's 20-site
control audit, S3's earlier-entry provenance and S4's combined follow-up open.
The original 28-gap explanation and its immutable qualification remain historical.
