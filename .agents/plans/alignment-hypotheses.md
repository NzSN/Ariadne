# Explicit alignment hypotheses for structural frame reports

## Context and follow-up

**Status.** H0–H5 are complete within the [2026-10-16 qualified scope](../../evidence/Ariadne/alignment-hypotheses/20261016/README.md).
Source capsule `34d078b4e3c94977620e72313111d40d52fae1978af05b0682d716d1bec5d556`
contains 1,060 files, based on `4811d7de6f2b86319135a5f0a1a18c397a4cd4c2`.
The working baseline preserves the separately qualified, uncommitted Stage
5.1 implementation and its original evidence identities.

**Why this document exists.** The [structural report](../../docs/Ariadne/investigation-design.md#structural-frame-report-before-dataflow)
retains an unknown MOVAPS alignment guard at caller `0x00007ff7744035c9`.
The user requests an explicit assumption allowing conditional normal execution.

**What this document establishes.** A conditional result, exact source/activation
ownership, an additive proof boundary, bounded validation and remote acceptance.

**Where to go next.** Read the [canonical hypothesis contract](../../docs/Ariadne/investigation-design.md#explicit-alignment-hypotheses),
[Stage 5.1 evidence](../../evidence/Ariadne/frame-structure/20261016/README.md)
and [predicate model](../../Specs/AriadnePredicateAdmission.tla). The
[retained qualification](../../evidence/Ariadne/alignment-hypotheses/20261016/README.md)
binds runtime, model, independent oracle, compiled mutations, compatibility and
named-dump/saved-replay results to their exact sources and finite scope.

**What remains unresolved.** Current native full analysis, exact executed paths,
general instruction assumptions and general SIMD admission are outside this
extension. Finite model/replay evidence does not prove universal refinement.

## H0: frozen contract

- CLI: repeatable `--assume-frame-aligned FRAME:VA`, only with `--frame-structure`.
  Example: `--assume-frame-aligned 1:0x00007ff7744035c9`. Reject duplicates,
  malformed values, selections outside the requested frame range, missing
  selected activations and sites absent from successfully sealed source evidence.
- Meaning: whenever this physical activation reaches this reviewed MOVAPS guard,
  its effective address is aligned to 16 bytes. This is an explicit hypothesis,
  not a captured observation, root, slice seed or assertion of execution.
- Bind each hypothesis to snapshot/artifact, chain/thread/frame activation,
  original root/query scope, instruction VA, captured bytes, original AST,
  recognized predicate/displacement, decoder receipt and candidate epoch.
- Keep the existing baseline request, source context, guard/target/composition
  receipts and original verdict. Add `src/bap/alignment_hypothesis.rs` and
  `Specs/AriadneAlignmentHypothesis.tla`; do not edit identity-hashed guard,
  terminal, composition or predicate-authority files for this extension.
- Derive a bounded conditional least fixed point over independently replayed
  original transfer receipts. At each selected point intersect incoming residue
  states with the effective-address alignment mask before propagation. A point
  never becomes a root. Loops apply the hypothesis on every modeled visit.
- Distinguish baseline verdict from conditional selection basis: proved under
  existing premises, assumed under hypothesis, unreachable under hypothesis,
  or unknown. Closed empty intersection blocks that conditional normal branch;
  it supplies no witness or global impossibility claim. Unfinished/open coverage
  retains unknown and cannot justify an alignment selection.
- Select only the existing reviewed MOVAPS normal BIL after source recognition,
  using `Backend::guard_normal_projection`. No arbitrary exception removal,
  new target or capture fallback is allowed.
- Keep target/composition proofs on their original owning candidate graph and
  independently replay them before conditional selection. The conditional
  product binds the original proofs, hypotheses, filtered facts, selections and
  final normalized request. No target narrowing under H is claimed; existing
  conservative target results remain valid under the restriction.
- Produce `ariadne.frame-structure/v2` only with a nonempty validated hypothesis
  collection; plain requests retain v1. Label the whole derived report and
  participating maps/links conditional on all retained hypothesis IDs. Preserve
  captured byte provenance. Strict v1 dispatch rejects conditional receipts.
- Saved replay requires no native helpers, verifies source/predicate/scope,
  independently recomputes the finite fixed point and final projection under
  trusted host caps, and rejects removed/changed/reassigned hypotheses even
  after rehashing. Work/budget exhaustion yields no trusted assumed edge.
- Use existing finite graph/proof/work/output policies, checked arithmetic and
  aggregate charging. The new hypothesis count is bounded by existing frame
  and graph/site policies. Keep the core std-only and old native routes explicit.

## Execution ledger

| Stage | Ownership and deliverable | Acceptance | Status |
| --- | --- | --- | --- |
| H0 | Parent: canonical contract and this plan, baseline inventory | Module interfaces and semantic exclusions frozen before runtime edits | Passed |
| H1 | Proof owner: new BAP companion module and focused tests; only BAP module export added | Source-bound hypotheses, finite masked least fixed point, baseline verdict retained, exact final request and replay validation | Passed |
| H2 | Integration owner: structural input/binding/reports/CLI and focused tests | Scoped option, independent capture validation, conditional v2 schema/identity/labels, v1 byte-compatible replay | Passed |
| H3 | Model owner: new companion model/configs/checker/oracle and behavioral mutation driver | Independent unknown/aligned/misaligned/unreached/open/loop/bypass/clobber/activation/tamper controls; no old authority/hash changes | Passed |
| H4 | Parent + independent reviewer: remote source snapshot and qualification | Affected tests; fmt/default/core/Clippy; reports/BAP feature controls; models/oracles/mutations; actual old v1 report and native/capture compatibility | Passed |
| H5 | Parent: named dump baseline/conditional runs, saved public API replay and documentation | Explicit H at frame1:35c9; original unknown retained; normal edge to35d1 only in conditional product; source/proof/root/target scope verified; exact remaining gaps and conditional graph retained | Passed |

All Cargo/native/model/mutation/dump work runs remotely in Windows WSL using
`r_windev`. Reuse only task-owned build storage with separate replay/mutation
subdirectories; verify source and helper hashes. Preserve old evidence bytes.
No implementation commit/push is included unless requested.

## Required independent cases

Unknown becomes assumed; already aligned remains proved; fully misaligned
incoming states make the conditional branch empty; an unvisited point is not
seeded; zero/open/exhausted analysis admits no normal edge; signed displacement;
multiple points; bypass merge; clobber and cyclic repeated visit; separate
recursive activations; absent captured source and unsupported predicate;
changed source bytes/AST/decoder/point/snapshot/query/epoch; removed H or
unconditional relabeling; saved v1 replay and unchanged no-H control sets;
all three conditional formats and standalone public API replay.

## Retained qualification — 2026-10-16

The [evidence bundle](../../evidence/Ariadne/alignment-hypotheses/20261016/README.md)
records H0–H5 completion on source capsule
`34d078b4e3c94977620e72313111d40d52fae1978af05b0682d716d1bec5d556`
(1,060 files), with 725 runtime-inventory files verified unchanged during the
remote campaign. Post-collection documentation reconciliation is recorded as a
documentation-only delta; it does not rewrite the exercised capsule identity.

Remote root checks pass formatting, Clippy, 298 default tests including three
doctests and 57 core-only tests including three doctests. The ordinary runs
retain 108 default / 22 core-only ignored tests. Nine new kernel tests include
the 21-case independent runtime-oracle consumer. The new model passes 25 finite
configurations; the independent oracle passes 39 cases. Six compiled mutants
are rejected with passing unmodified observers. Two capture CLI tests, one
conditional rehashed-codec capture test, 38 named release native/compatibility
tests, actual saved v1 replay and standalone saved v2 replay pass separately.
These named tiers are not a claim that every ignored test was exercised.

Named baseline `dump-baseline-20261016T094136` preserves the old qualified v1
output and binding exactly. Conditional run `dump-conditional-20261016T094313`
adds only H at frame 1 / `0x00007ff7744035c9`: baseline Unknown remains intact;
normal selection is Assumed under the 16-byte alignment hypothesis. The edge
to `0x00007ff7744035d1` appears only in the conditional product. Caller recovery
changes from 9,590 visited / 9,589 decoded / 11,321 edges to 9,600 / 9,600 /
11,331; callee 778 / 778 / 895 remains unchanged. All prefixes stay in Recover
with zero dataflow/slice actions.

All original request/context/source/guard/target/composition facts and roots
remain bound unchanged as baseline inputs. An independent explicit product BFS
checks 153,210 `(point, residue)` states under a 153,600-state cap and 172,346
transfer evaluations, matching all incoming and masked facts. Conditional graph
edges remain structural alternatives and can compose into infeasible paths;
this stage performs no accumulated-path-constraint SAT/SMT analysis.

Caller UnresolvedGuard is removed under H, while the newly reached return adds
an opaque call-context boundary: caller gap count stays 565, now 536 opaque
contexts and 29 exceptional exits. Callee retains 45 boundaries, including two
unknown indirect and eight unknown call targets. Full caller S6, frame-path F4,
target narrowing, exact history and performance qualification remain separate.
