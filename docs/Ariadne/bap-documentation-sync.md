# BAP documentation and implementation synchronization

## Context and follow-up

**Status.** Historical source-first documentation audit on 2026-10-09, before
the [v3 execution checkpoint](bap-admission-checkpoint.md). The inventory and
current-implementation table below describe that earlier v2 snapshot. Current BAP
ownership, CLI defaults, projection limits and retained qualification identities
are checked separately. This change updates documentation and adds an audit
receipt; it does not rerun native/model/mutation/workload qualification.

**Why this document exists.** The [integration ledger](../../Plans/bap-integration.md)
records completed Stage 1/Stage 2, but several BAP and consumer documents still
described the older I4 timing gap, experimental provider selection or incomplete
helper setup. Older standalone qualification files also differ from current
sources despite a later matching refresh nested in the I4 performance record.

**What this document establishes.** The current implemented boundary, corrected
documentation, exact reusable evidence and pending projection work. The
[audit receipt](../../evidence/Ariadne/bap-documentation-audit.json) inventories
every repository Markdown file mentioning BAP, including historical/retired
references, and records the source/tool/dependency/archive checks.

**Where to go next.**

- [Backend guide](modules/bap.md) and [input guide](modules/input.md) — current
  helper setup, library preparation and native-default CLI selection.
- [Projection design](bap-semantic-backend-design.md) and
  [binding review](bap-projection-source-review.md) — implemented admission,
  source attribution and finite producer expectations.
- [Native qualification guide](bap-core-qualification.md) and
  [I4 performance successor](i4-performance-validation.md) — original adoption,
  later refresh and independently fixed product budgets.
- [Projection admission plan](../../Plans/bap-projection-admission.md) — pending
  P0–P4 implementation and qualification; broader lifting is not delivered here.
- [Assurance boundary](semantic-assurance.md) — trusted lifting, active analysis
  models and retired architectural instruction-step proofs.

**What remains unresolved.** Generic BIL capability admission, the four observed
parser forms and ordinary opaque continuation remain pending. Finite retained
qualification does not establish universal lifter correctness, analysis
refinement, general latency, executed history, a crash root cause or a packaged
cross-platform release. Later source/tool/dependency changes require a new
complete identity check or fresh affected qualification.

See the [documentation map](../documentation-map.md) for wider navigation.

## Current implementation

| Boundary | Current owner and behavior | Source |
| --- | --- | --- |
| Capture | Rust reader preserves snapshot identity, captured-only bytes, holes/conflicts, entry roots and separate seeds. Executables supply no fallback bytes. | [Input materializer](../../src/input/materialize.rs) |
| Lifting | Pinned packaged BAP legacy x86 lifter in a C++ process; selected library/plugins and exact consumed bytes are validated. | [Lifter](../../native/bap/lift.cpp), [runtime configuration](../../src/bap/session.rs) |
| Decode reference | LLVM MC supplies independent length/control/operand facts. BAP preparation reuses one checked reference process per snapshot/target; standalone LLVM preparation remains one-shot. | [BAP preparation](../../src/bap/prepare.rs), [reference transport](../../src/llvm_mc/protocol.rs) |
| Projection | `bap-bit-provenance-v2` interprets typed BIL with byte GPR cells, flags, weak `memory:any`, separate possible/definite writes and explicit unknowns. A finite opcode whitelist and prefix guards still gate admission. | [Projection](../../src/bap/projection.rs) |
| Unsupported effects/control | Failed projection conservatively stops recovery with opaque evidence and an unsupported-control gap. It does not continue as an ordinary opaque instruction or use LLVM effect fallback. Calls/returns retain their separate opaque policy. | [Preparation stop policy](../../src/bap/prepare.rs) |
| Analysis | ABI 2 OCaml helper owns recovery, reaching definitions, slicing and finite supplied stateflow. Capture/normalized profiles and full incremental observations remain distinct. | [Recovery](../../native/bap-core/recovery.ml), [stateflow](../../native/bap-core/stateflow.ml), [capture admission](../../native/bap-core/capture.ml) |
| CLI and results | Native `bap` analysis is the default; `--analysis-backend rust` explicitly selects rollback while retaining BAP lifting. Rust validates native results and renders investigations through completed `AnalysisView` facts. Failed sessions have no automatic rollback. | [CLI](../../src/bin/ariadne-minidump.rs), [native facade](../../src/bap/core_adapter.rs) |
| Independent paths | Rust fixed-input analysis and directly supplied LLVM IR retain their own contracts. Analysis-level TLA+, replay and mutations stay active; ISA/Lean instruction-step research is retired. | [Implementation guide](../implementation.md), [model guide](../../Specs/README.md), [assurance decision](semantic-assurance.md) |

The implemented corpus remains 41 exact BIL cases and 30 admitted forms. These
counts are finite exercised coverage; the Stage 1 checker still records them
explicitly. SUB64ri8, MOVZX32rm8, XOR64rr and CMP8mi are outside the production
whitelist. Nonempty BIL does not by itself admit them. The proposed v3 profile,
capability admission and conservative ordinary continuation belong to the
pending P0–P4 plan.

## Matching retained evidence

The latest matching aggregate is the
[2026-10-07 I4 performance record](../../evidence/Ariadne/i4-performance-qualification.json),
not the older standalone `bap-core-qualification.json`. Its nested record paths
are:

| Record | Path inside the I4 aggregate | Passing gates / source inventory |
| --- | --- | --- |
| Native Stage 2 | `records.regressions.records.native-core-stage-e-input-bap-regressions` | 20 / 712 |
| Stage 1 | Native-core record's `records.stage1-regression` | 17 / 255 |
| I5b regressions | `records.regressions` | 18 / 295 |
| I5a source/fixture regressions | I5b record's `records.i5a-regression` | 14 / 286 |

Stage 1's own `stage2Qualified=false` field limits that producer campaign's
scope. It does not override the separate native-core adoption decision.

The audit compares complete inventories using the current qualification tools,
checks installed helper manifests and their OCaml source receipts, verifies
every compiled Stage 1 runtime pin, and uses the selected read-only MirrorRust
view. The I4 aggregate's 12 installed tool hashes match. Its dependency manifest
digest is
`a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`.

The [accepted evidence archive](../../evidence/Ariadne/i4-performance-evidence.tar.gz)
and [manifest](../../evidence/Ariadne/i4-performance-evidence-manifest.json)
match their recorded digests; all 3,625 members are checked, including the exact
compressed nested archives. This is retained-byte and identity verification,
not fresh execution of their recorded gates. The
[audit receipt](../../evidence/Ariadne/bap-documentation-audit.json) records the
verification separately from the original campaign.

Older standalone Stage 1, removal, replacement, unlimited-policy, A0, OCaml and
native-core records remain unchanged historical snapshots. Their changed or
retired source paths are listed in the audit receipt; matching helper hashes
alone cannot make those inventories current. The native analysis design and
Stage 2 execution plan are part of the matching source inventory and retain
their accepted bytes. Their earlier proposal/candidate sequence is read with
the design's implemented ABI 2 section and the qualification guide's completed
adoption record.

## Corrections and remaining work

Current BAP guides, historical delivery follow-ups and consumer documentation
now distinguish the passing I4 performance successor from the earlier
over-budget re-pin. The exact controlled Windows I4 query records
**1,692.696 ms** against its unchanged **2,000 ms** CLI limit; the Linux reference
phase criterion records **182.924 ms** against **250 ms**. BAP's unlimited policy
does not waive either criterion or the separate I5a budgets. Historical timing
samples and failed flags retain their original meaning.

Provider/source-review wording identifies legacy as the implemented selection.
Foundation documentation separates its old Init/Visit bootstrap from the full
ABI 2 helper and names the delivered `ocamlfind ocamlopt` build instead of
undelivered Dune files. Current CLI setup includes the native analysis helper;
the input library example explicitly selects Rust rather than implying that
preparation alone chooses an analyzer. LLVM protocol documentation distinguishes
the reused production reference session from the standalone one-shot adapter.

The next BAP implementation work is [P0–P4](../../Plans/bap-projection-admission.md).
The existing native migration is completed. New admitted forms, recovery policy
or profile changes need independent expectations and fresh affected evidence;
they receive no qualification credit from this documentation audit.

## Verification scope

Run `python3 tools/check_doc_links.py` and `git diff --check` after documentation
changes. Corpus freshness uses
`python3 tests/bap/fixtures/make_corpus.py --check`; Rust layout uses
`python3 tools/check_rust_layout.py`. The audit receipt lists the checked
documents and exact retained identities. No Rust, OCaml, native lifter, formal
model, fixture or existing qualification-record bytes changed in this audit.

These checks passed: documentation navigation covers 133 connected documents
and 2,360 local links; the corpus generator matches all 41 BIL cases; the layout
check finds 107 Rust files under `src/` and `tests/`; `git diff --check` reports
no whitespace errors. The BAP-specific inventory contains 111 Markdown files.

For a new runtime campaign, follow the [native qualification reproduction](bap-core-qualification.md#reproduction)
and [I4 evidence/reproduction guide](i4-performance-validation.md#reproduction-and-retained-byte-verification)
under the sealed dependency wrapper. Source changes require those applicable
gates, rather than substituting a documentation check for qualification.
