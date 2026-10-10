# Active real-capture replacement: translated-frame iterator

## Context and follow-up

**Status.** User-selected replacement qualified remotely and P4 accepted by
the user on 2026-10-10. The
[acceptance decision](../../evidence/Ariadne/bap-admission/p4-acceptance-20261010.json)
excludes the remaining historical real-Linux clauses and preserves their original
flags. No required P4 work remains in the accepted scope.
Independent capture/entry inspection, current P4 source/fixture and native-default
gates, repeatable product parity and fixed I4/I5 budgets pass. The
[qualification record](../../evidence/Ariadne/real-capture-repin-79938/report.json)
and [verified manifest](../../evidence/Ariadne/real-capture-repin-79938/evidence-manifest.json)
bind their exact sources, tools, capture and scope.

**Why this document exists.** The [prior resume](bap-admission-resume.md) was blocked
by the missing original Linux workload. The [entry/evidence design](priority-1-real-capture-design.md)
permits an independently anchored Windows or Linux real capture.

**What this document establishes.** A distinct Windows capture-only workload,
with explicit scope and preserved original Linux history. Its [manifest](../../evidence/Ariadne/real-capture-workload-case.json)
and [inspection](../../evidence/Ariadne/real-capture-repin-79938/inspection.json)
bind the original, derivative, matched PE/PDB, entry and producer.

**Where to go next.**

- [P4 re-pin stage plan](../../Plans/real-capture-repin-79938.md) — activation,
  new output baseline and remote qualification gates.
- [Investigation contracts](investigation-contracts.md) — possible dependencies
  and captured fault observations retain distinct meanings.
- [Historical Linux case](priority-1-real-capture-validation.md) — older artifact,
  six-output baseline and original Linux-specific acceptance remain historical.

**What remains unresolved.** This Windows case supplies no real-Linux coverage.
The original Linux six hashes remain unverified and excluded from accepted P4.
A partial explanation does not identify a previous executed path or the actor
that produced the bad register. The historical full-24 oracle remains false;
the replacement has its own six-output baseline. Acceptance is scoped to the
recorded finite corpus and does not qualify a packaged release.

## Selected case and bounded query

Original [DumpLedger capture](https://192.168.150.219:4080/dumps/dump_79938FAE443F4021A4F7B6C215):
1,690,277,882 bytes, SHA-256
`342084c90b6e361ab94fb91a920f871581eba970810f99384d5dce00ee6d7353`.
It is Windows AMD64, exception thread `0x97f4`. The raw file remains in the
remote vault. The HTTP API requires authentication; the existing vault was read
through authenticated SSH. No service or symbol-store writes are required.

The matched PE has timestamp `0x6a87c949`, image size `0x0d708000`, SHA-256
`b537ad7b96136655b6cf640bd5a715a62a132dde6196acc925bf739164a1be3b`.
Its PDB GUID/age is `A7877FFB-94F2-DB3E-4C4C-44205044422E`/1. Fresh CDB output
names the function entry at `0x00007ff63cba6c50`; its 94 captured bytes match the
PE. The leaf function has no `.fnent` entry; the matched private PDB symbol and
forward disassembly supply the independent boundary witness.

The 516,256-byte derivative has SHA-256
`0333e29bfed1608ac877395d191642947aacc58dd81d0b786e0fd0df1a131f90`.
Its four selected ranges retain the function, exception-thread stack, iterator
map and first values. Every selected original contributor agrees. Module/system/
exception/MemoryInfo metadata and both contexts match; the original thread
context differs from the exception context and is not used as the fault context.
The derivative clears the full-memory declaration and has its own identity.

The fault instruction is `45 8a 10` (`mov r10b,[r8]`), observed with `R8=1`.
The earlier captured `4c 8b 41 08` at entry+3 loads R8 from `[RCX+8]`.
Initial native and Rust analyses both recover 29 starts, 31 edges, the same
10-site slice and all seeds. They retain the initial load among possible
producers. The answer is partial because memory aliases and entry origins remain
unknown. The register/iterator disagreement is a snapshot observation, not an
execution history or identified cause.

## Remote qualification and reproducibility

All 20 native-core gates, Stage 1/Stage E/input/effects/model checks, 330 native
replay observations, 12 algorithm mutations, eight boundary mutations and
25 admission mutations pass. One warmup and five measured product runs per
backend preserve the selected query and producer. Default BAP, explicit BAP and
Rust-reference outputs agree exactly after validating/removing only the native
backend receipt.

The [output record](../../evidence/Ariadne/real-capture-repin-79938/profile-migration-report.json)
reproduces 18 frozen v2 fixture hashes and validates their declared v3 migration.
The replacement establishes six fresh v3 hashes; all 24 current output
comparisons pass. The six historical real-Linux hashes remain unexercised.

The [timing record](../../evidence/Ariadne/real-capture-repin-79938/phase-budget-report.json)
meets the unchanged 250 ms binding/explanation/render budget with a sum of
phase medians of **2.870 ms**. This excludes preparation and core analysis.
The selected capture's native explanation CLI median is **354.018 ms**.
The independent Windows-98 case has a **475.664 ms** CLI median against its
unchanged **2,000 ms** budget. Nine I5a fixtures and six owned native/reference captures retain
their separate finite qualification scopes. All 17 investigation gates pass;
Stage E and timing reuse is accepted only after fresh source/tool/dependency checks.

The [inspection generator](../../evidence/Ariadne/real-capture-repin-79938/inspection-generator.py)
and [CDB script](../../evidence/Ariadne/real-capture-repin-79938/entry-witness-script.sh)
retain the independent witness recipe. The original, matched companions and
derivative stay remote. In the private runtime, the derivative is
`tmp/real-capture/dump79938-scoped.dmp`; elsewhere set
`ARIADNE_REAL_CAPTURE_DUMP` to bytes matching the active manifest.

Archive compression and member verification ran remotely. Local retrieval uses
bounded streaming hashes. The prior Scanner/PreParser results retain verified
implementation/helper identities; no new complete Scanner Rust-repeat credit
is claimed. The generic runner's external-tier flag remains false because that
clause is recorded separately; it does not override the joined scope record.

The [documentation follow-up](../../evidence/Ariadne/real-capture-repin-79938/documentation-follow-up.json)
binds the later guide/status edits separately from the frozen runtime campaign.
All qualified implementation and fixture hashes still match.

The [post-acceptance documentation refresh](../../evidence/Ariadne/bap-admission/p4-documentation-followup-20261010.json)
binds the current README, guides and historical successor links to the unchanged
accepted implementation and evidence. Earlier documentation receipts retain
their original hashes.
