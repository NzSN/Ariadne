# BAP v3 admission resume record

## Context and follow-up

**Status.** P4 source/fixture, Rust release-runtime and native-default tiers
are accepted on the [user-selected Windows replacement](real-capture-repin-79938.md).
The user excluded the remaining historical real-Linux clauses in the
[acceptance decision](../../evidence/Ariadne/bap-admission/p4-acceptance-20261010.json).
The restored private SDK and completion transport pass remote checks. Heavy local
work remains stopped. Earlier paragraphs retain the failures and missing Linux
pin observed before replacement; they are historical continuation records.

**Why this document exists.** The [committed checkpoint](bap-admission-checkpoint.md)
specified resuming qualification, rather than repeating P0–P3 implementation.
Its ignored build and capture paths were not all present in this environment.

**What this document establishes.** Recovered prerequisites, fresh results, the
self-move mutation repair, external capture provenance and remaining blockers.
The [resume evidence](../../evidence/Ariadne/bap-admission/resume-20261010/report.json)
records actual commands, tool identities and the scope of each result.
The later [remote evidence](../../evidence/Ariadne/bap-admission/remote-20261010/report.json)
and [verified archive manifest](../../evidence/Ariadne/bap-admission/remote-20261010/evidence-manifest.json)
bind the available tiers and unmet clauses before replacement.
The [documentation follow-up](../../evidence/Ariadne/bap-admission/remote-20261010/documentation-follow-up.json)
records the later guide-only update; all qualified code/fixture hashes still match.

**Where to go next.**

- [Selected real-capture replacement](real-capture-repin-79938.md) — current
  aggregate, native parity, new baseline and fixed-budget qualification.
- [P0–P4 plan and resume order](../../Plans/bap-projection-admission.md#resume-order)
  — preserve the completed campaign and qualify future source/tool changes.
- [Admission contract](bap-admission-contract.md) — preserve failure classes,
  conservative continuation and historical output identity checks.
- [Native helper guide](../../native/bap-core/README.md) — required SDK and
  source-bound helper checks before native parity or mutation credit.
- [Completion transport plan](../../Plans/bap-completion-pages.md) — bounded
  action batches and final-result pages for the newly reproduced response limit.
- [Investigation contracts](investigation-contracts.md) — query-bound possible
  dependencies, missing seeds and limits of historical inference.

**What remains unresolved.** The old Linux capture and six historical output
hashes remain unexercised; its platform coverage is not inherited by the Windows
replacement. Scanner retains explicit gaps, and PreParser still does not reach
the RSI consumer. No executed path, actor or bad-RSI cause is identified.

## Initial prerequisite recovery and environment gaps

The exact MirrorRust snapshot manifest was recovered from retained I4 evidence:
SHA-256 `a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`,
revision `08d189f18a76845dc15dd23b79424809ae27f406`. Its retained source bytes,
Git revision and active read-only dependency view were verified. The live sibling
checkout was not edited.

The initially available bridge had SHA-256
`80e32c1d21d447969beb99398008cf5a259e5cd10507524c8b2f639c5f0fe57c`.
Its different identity prevented reproduction of the historical report hashes.
Rebuilding the bridge from the current source against the existing pinned
packaged runtime reproduced the frozen P0 helper exactly:
`6d910bf619f6ece729e85e857b60d7a22953bb633a4a43ffd99c5a5919ecc1cf`.
That verified bridge was restored at `target/ariadne-bap-lift`. This did not
rebuild BAP or install an SDK. The first failed comparisons remain retained.

The retained SDK manifest and package export were recovered and hash-checked.
Comparison against the actual SDK found **6,134 matching files, 3,345 missing
files and 40 changed files**. Missing files include BAP libraries. The fresh
aggregate therefore fails its native SDK inventory gate; no stale native helper
or relaxed inventory is substituted. Native capture mutations remain unexercised.

The controlled Linux capture at `tmp/priority1/chromium-member-uaf.dmp`, the
documented header trees and the Breakpad capture corpus are also absent from
their qualification paths. Original raw captures remain external artifacts.

## Fresh checks and bounded migration

Default and core-only Cargo tests, formatting under the sealed dependency view,
all-feature/all-target Clippy and the Rust layout check pass. The independent
contract, six owned minidumps, 104 scalar BIL comparisons and profile-migration
negative controls pass. Eight installed-producer tests and the disagreement test
pass; native analysis/capture tests require the unavailable helper environment.

The frozen v2 revision `ebb2e534e8da339f498f20d0a9e1e0b8506a3bdd` was rebuilt
in its own target subtree after checking all five P0 source hashes. With the
verified P0 bridge, **18 historical output hashes** for the Linux, Windows and
NOT fixtures reproduce exactly. Their v3 outputs pass strict content-ID decoding
and the declared profile/derived-ID migration comparison. The controlled Linux
case's six outputs and native/reference comparisons remain pending. Earlier
comparisons under the different helper are diagnostic records, not acceptance.

Six owned captures also have one warmup and five Rust-reference phase samples,
including preparation, analysis, rendering, output sizes and explicit reader and
materialization limits. These measurements ran alongside compilation and have
no fixed-budget or native-parity credit. Complete owned-query and I4/I5
measurements still require a valid native environment.

## Mutation campaign and repair

The initial resumed campaign recognized the previously rejected prefix assertion
and rejected its first **18 mutants** through the intended tests. It stopped at
`partial-self-move-loses-definition`: the selected test passed, so the campaign
correctly refused sensitivity credit.

That mutant removed the `changed` predicate's partial-MOV case. V3 separately
enters the output path through `possible_destination`, and the definite-write
predicate still retained the partial-MOV justification. The old mutation no
longer removed the self-move definition it was intended to test.

The harness now removes the partial-MOV justification in the actual definite-write
predicate. The unchanged native producer test passes on the baseline and rejects
the compiled repaired mutant: expected `gpr:rax:0` is missing from `must_defs`.
The focused receipt binds the source inventory, unchanged observers, build log,
compiled test digest and exit 101. This is a focused repair check, not a passing
complete mutation campaign. Separate focused checks reject cross-snapshot reuse,
fabricated call preservation and swapped native extraction getters. The last
build succeeds and the binding validator rejects the malformed extraction;
build failure is not credited as sensitivity. The three native capture-validator
mutations remain unexercised without the source-bound native helper.

## External Electron capture and query attempts

The original was located in the prior external analysis workspace. Its size is
962,600,678 bytes and its SHA-256 matches the required
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`.
The existing exception-thread derivative has 571,636 bytes and SHA-256
`ed82b433501162828460ccbf067476e4683a52157372b27040f0269d2b3949c5`.

An independent binary parser verified all **50** derivative memory ranges against
the original, including agreement of overlapping original capture contributors.
Thread `0x5c74`, its stack, thread/exception contexts and retained module/system/
exception/MemoryInfo stream bytes match. The derivative has its own snapshot
identity and excludes unselected memory. Retained CDB root/consumer witnesses
were checked against the prior analysis manifest. No raw dump or customer source
is included in this evidence bundle.

| Rust-reference query | Observed result |
| --- | --- |
| Scanner root `0x7ff77443d960`, fault seed `0x7ff77443dd6e`, default limits | Diagnostic invocation timed out after 300 seconds; no result accepted. |
| Same Scanner root/seed, explicit 256-start limit | Fails with `materialization limit: instruction starts`; no partial report published. |
| PreParser root `0x7ff7744033a0`, RSI-consumer seed `0x7ff7744048a0`, explicit 256-start limit | Nine decoded starts and nine edges; stops at `MOVAPSmr` at `0x7ff7744033b3` with `unmodeled architectural namespace/type: YMM6`. Seed remains missing. |

The 300-second diagnostic process limit is not a BAP latency acceptance ceiling.
These attempts used the initially available bridge and the Rust reference;
completed native-default external results remain pending. No unsupported SIMD
state receives invented ordinary continuation or LLVM effect fallback.

## Resume prerequisites and order

This list records the earlier order before the Windows replacement and user
acceptance. Its Linux recovery/full-24 clauses are now excluded from required
P4 work. For current continuation, follow the
[accepted plan's resume order](../../Plans/bap-projection-admission.md#resume-order).

1. Reuse the isolated remote environment and sealed source/tool/dependency
   identities. Do not resume heavy local builds or analysis. Recover the Linux capture
   (SHA-256 `31481f3f080b0b165cc0d0c70f555f127f882556b34129055e80b082225a45c9`),
   matching headers and required capture corpus. Validate their actual identities.
2. Use the verified P0 bridge and sealed MirrorRust snapshot. The remote 25-case
   admission campaign, 330 native replay observations, 12 algorithm and eight
   boundary mutants pass. Refresh them only after changed source/tool identities.
3. Reproduce all 24 historical outputs and complete native/reference comparisons.
   Do not normalize differing helper, runtime, capture or claim hashes.
4. Rerun the full aggregate and Linux-dependent clauses with the recovered pin.
   Retain passing owned/I5a fixture and scoped Windows I4 measurements as their
   exercised tiers; do not relabel them as full acceptance.
5. Preserve the completed Scanner/PreParser queries and derivative proof.
   SIMD, indirect-target, call and memory gaps remain explicit. Broader consumer
   recovery or causal attribution requires its own additional evidence/work.
6. Seal new evidence and update the plan only to the tiers actually accepted.

## Later continuation: SDK restored, completion transport implemented

The private SDK inventory, smoke test and native helper build subsequently
passed. Matching LLVM development headers and the two upstream Breakpad captures
were recovered. The historical Mirrors compiler/mirror binary identities were
restored in an isolated source copy. These actions did not alter live sibling
checkouts or user OCaml switches.

Before the transport change, the repaired **25-case** producer/adapter/native
capture mutation campaign passed with stable sources and unchanged observers.
The native aggregate also passed its root/core-only tests, Clippy, layout,
documentation, 13 contract tests, native kernels, five native capture tests,
330 replay observations, 12 algorithm mutations and eight boundary mutations.
It failed its nested Stage 1 gate: old TLC flags, an outdated v2 report assertion,
a missing Breakpad path, a malformed-row test failure and the absent controlled
Linux capture. The first three prerequisite/assertion issues are repaired;
the malformed-row test passes targeted reruns but still needs a broad refresh.
These results remain in `target/bap-admission-completion-20261010/` and the
runner's referenced temporary campaign directories; they are not a sealed P4
delivery record.

Six owned captures passed native/reference CLI and phase/report parity. The
fixture-only I5a tier passed; its controlled-real-Windows acceptance flags remain
false. The Windows I4 diagnostic median was 2,502.747 ms against the unchanged
2,000 ms budget while other work was running. This is a retained budget failure,
not quiet performance qualification.

The native Scanner request failed with `response budget`, reproduced by a
20-node/1,000-location request in under one second. The native PreParser result
retains the same nine-start SIMD stop and missing consumer seed. The
[completion transport implementation](../../Plans/bap-completion-pages.md)
keeps the 8 MiB frame budget, runs at most 64 existing actions per exchange and
retrieves one immutable completed envelope through ordered 256 KiB pages.
Four native analysis tests, including exact large-result parity and ten hostile
page/lifecycle modes, passed before local heavy work stopped. Full qualification
and external-query attempts on these new sources are still pending.

Remote inspection found Ubuntu WSL2 on `windows-dev` with approximately 58 GiB
available memory. A task-private Ubuntu 24.04 rootfs is being prepared with
rootless bubblewrap because the host's Ubuntu 22.04 C runtime cannot run the
pinned tools. The approved source-only diff and ten named tool/manifest files
are transferred separately with hashes. No customer capture is in these
transfers. Build/model/mutation/large-analysis work must run remotely; only light
editing, inspection and checkpoint work continues locally.

## Remote continuation: available tiers qualified; Linux pin missing

The private Ubuntu 24.04 runtime on remote WSL2 restores the pinned SDK, LLVM
20.1.2, Graphviz, TLC, Apalache and framework dependencies. The SDK inventory,
project/term/storage smoke probe and two identical clean helper builds pass.
Only task-owned remote paths were changed; live sibling repositories and user
OCaml switches remain separate. The source-only transfers and named tool files
were hash-verified. Raw customer captures remain external.

Current-source root/default/core-only tests, Clippy, layout, documentation,
native analysis/capture/stateflow tests, 330 native replay observations, 12
algorithm mutants and eight boundary mutants pass. The 25 admission mutants
and eight-case TLA replay pass. Stage E and every minidump gate pass, including
active input/effects models and both exact upstream Breakpad captures. The full
aggregate retains `passed=false`: its sole remaining nested Stage 1 failure is
the missing controlled Linux workload. Source/tool identities are retained;
there is no full native-default acceptance claim.

Paging introduced a second sequence predicate, so the boundary mutation now
targets the original per-action predicate through its family context. The
unchanged bootstrap observer rejects the compiled mutant. Completion validation
also uses overflow-safe result counters and validates close offsets; the hostile
proxy now exercises twelve invalid page/lifecycle modes. A stale Windows test
expecting a whitelist stop at `33 c0` is replaced by exact self-XOR continuation,
all eight RAX-byte origin checks and the preserved undefined-AF diagnostic.

Six owned captures pass native/reference CLI and phase parity. Nine I5a fixture
cases meet their fixed contracts; controlled-real-Windows flags remain separate.
The quiet active Windows I4 query has one warmup and five measured samples,
98 decoded starts and its independent producer witness. Its median is
**480.236 ms**, meeting the unchanged **2,000 ms** limit. The Linux I4 phase
clause remains unexercised. Eighteen frozen v2 output hashes reproduce exactly;
native/reference and declared v3 profile migrations pass for those available
cases. Six outputs still require the absent Linux pin.

The original Electron capture already exists remotely and matches its required
hash. A new independent generator reproduces the exact 571,636-byte derivative
and verifies all 50 ranges, overlapping contributors, metadata and contexts.
Scanner completes natively in 16.546 seconds with **768 decoded starts, 895
edges and a 19-instruction slice**. All four requested forms are projected at
30 sites, with no fallback. Its answer is partial and not truncated: eight call,
two indirect-target and ten decode obligations remain alongside memory/flag
uncertainty. PreParser completes its bounded analysis with nine starts/nine
edges, the explicit SIMD stop and missing consumer seed; its answer is unavailable.

Six native Scanner phase samples and six native/reference PreParser samples
complete. Two complete Scanner Rust-reference samples produce the exact same
raw base-report hash as all native samples; the first takes 257.003 seconds.
The remaining long Rust repetitions were terminated after parity was established.
That interrupted six-repeat campaign is retained as incomplete, not accepted.
Native phase/render scope is base text/DOT/JSON; explanation CLI measurements
are recorded separately. No fixed-budget waiver or historical execution claim
follows from these results.

The [remote evidence manifest](../../evidence/Ariadne/bap-admission/remote-20261010/evidence-manifest.json)
verifies 2,959 archive members. Compression and member verification ran remotely;
local retrieval checks only bounded-memory archive/report hashes. Full P4 remains
unaccepted until the missing capture-dependent clauses are exercised.

## Later continuation: selected capture replaces the active missing workload

The user selected `dump_79938FAE443F4021A4F7B6C215`. Its independently inspected
Windows derivative supplies a 29-start/31-edge function, a reached fault seed
and a 10-site slice containing the earlier R8 producer. The
[replacement qualification](real-capture-repin-79938.md) closes the active
source/fixture, release-runtime, native-default, product and fixed-budget clauses
with a distinct six-output baseline. All 17 investigation gates pass.

The old record above remains false for its original corpus. Eighteen historical
hashes reproduce; the six missing Linux outputs and real-Linux capture tier stay
false. Earlier Scanner/PreParser evidence is retained only after matching its
120 Rust/native/manifest implementation hashes and native helper identity.
No complete interrupted Rust-repeat campaign is credited.
