# Fault-address investigation contracts

## Context and follow-up

**Status.** Current fault-address explanation contract.

**Why this document exists.** [Investigation design](investigation-layer-design.md) requires claims to preserve alternatives and missing evidence.

**What this document establishes.** The contract binds the exact prepared/completed query to captured evidence and defines typed observed, derived and unknown claims. Per-byte producer alternatives remain distinct from a concrete whole-pointer history.

**Where to go next.**

- [Module guide](modules/investigation.md) — shows binding and explanation entry points.
- [Current Windows re-pin](i4-windows-repin-validation.md) — exact active capture, independent inspection and measured timing failure.
- [Validation record](investigation-validation.md) — exercises identity, aliases, gaps and claim/report behavior.
- [Remaining questions](../../Plans/investigation-layer.md) — tracks full qualification and unimplemented higher-level capabilities.

**What remains unresolved.** The first fault-address question is implemented. Active Windows I4 correctness passes after the [98-instruction re-pin](i4-windows-repin-validation.md); the later [performance qualification](i4-performance-validation.md) meets the unchanged 2 s limit at 1,692.696 ms. Later hypothesis, object/source-context and cross-capture questions are planned, not delivered. Stronger conclusions require additional accepted lifetime, path or object evidence.

For the wider context, see the optional [documentation map](../documentation-map.md).

Implemented first delivery for [I0–I4](../../Plans/investigation-layer.md).
Schema: **`ariadne.fault-address-explanation/v1`**. The request is a captured
instruction VA and an explicit memory-access index in the prepared query.

The input adapter checks prepared request equality with a completed analyzer,
snapshot identity, recomputed query entries/seeds/limits digest, site/read byte
agreement and evidence domains. It includes helper/runtime/AST/projection hashes
in semantic-profile binding. The owned `BoundInvestigation` has read-only
identity access; it stores the exact request/state and normalized evidence.

Address-use evidence is extracted from admitted typed BIL. The currently
supported expression is modular 64-bit affine arithmetic over **before-instruction
GPR values**, with constant, base/index coefficients and signed displacement.
RIP-relative expressions use the captured instruction VA, not a crash-register
pre-state. Sequential BIL assignments resolve architectural/virtual temporaries.
Unsupported casts, nonlinear/conditional expressions or loaded-address values
retain explicit gaps. Address inputs exclude store payload inputs.

| Explanation field | Meaning |
| --- | --- |
| `identity`, `scope_id` | Snapshot/artifact/query/request/semantic-profile identity and canonical content digest. |
| `question` | Canonical instruction VA and memory-access index. |
| `status` | `explained`, `partial` or `unavailable`; `explained` cannot carry gaps or truncation. |
| `address` | Selected access role/width, bounded expression, address input cells and BIL attribution. |
| `origins` | Per-byte/location alternatives from the core reaching map before the queried instruction. |
| `evidence` | Captured bytes, semantic identity and contributor dump offsets, scoped to the investigation. |
| `facts`, `claims` | Typed assertions and content-addressed references. Possible producers/dependencies are always `derived_under_premises`. |
| `gaps`, `evidence_requirements` | Concrete unmet evidence/semantic requirements, including affected locations where known. |
| `assumptions`, `truncated` | Scope of claims and explicit exhaustion of explanation limits. |

Claim kinds are captured instruction, address inputs, possible origin, dependency
and uncertainty. There is no confirmed-root-cause or actual-execution assertion.
Captured bytes are `observed`; semantic dependencies are `derived_under_premises`;
unmet requirements are `unknown`. Serialization rejects duplicate/unknown fields,
noncanonical VAs/bitvectors, unsupported kinds, wrong content/scope IDs, dangling
references and impossible completeness/classification.

Default finite limits: 4,096 evidence records, 32,768 origin links, 8,192 visited
dependency nodes and 65,536 claims. Exhaustion marks the answer partial/truncated
and identifies the limit. These limits are not a scale qualification; large
record/render costs remain subject to workload measurements and input limits.

Zero is valid for each limit. An exhausted budget never relaxes reference or
identity validation: a producer is retained only with its origin fact and any
required instruction evidence. If the selected site's evidence cannot be kept,
the answer is `unavailable`, `truncated=true`, with no selected address or origins
and an explicit budget gap. When that evidence and a supported address are kept
but expansion is incomplete, the answer is `partial`, `truncated=true`.
Invalid question sites/access indices still fail independently of budgets.
The [correctness-fix plan](../../Plans/completed/investigation-correctness-fixes.md) describes
the boundary regressions and qualification repair.

The question adds its instruction to slice seeds, **never entry roots**. Examples:

```sh
target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 \
  --explain-fault-address 0x401006 --memory-access 0 \
  --explanation-only --format json
```

`--explanation-only` requires `--format` and no stateflow input. Ordinary report
modes retain the original report and add an explanation envelope/text section.
Output-directory mode stages original reports and `explanation.txt`,
`explanation.json` and `explanation.dot` together. DOT retains the full typed
explanation in its metadata comment as well as evidence/fact relationships.

A complete possible-origin explanation is not a historical trace or a proof
that an instruction retired. Mixed bytes do not establish one co-occurring
whole-pointer producer. Opaque-call alternatives and `memory:any` uncertainty
remain visible; no UAF/object lifetime or numerical confidence is inferred.

The first release measures binding, explanation and all-format rendering on
both platform fixtures, the controlled NOT chain and the retained 34-instruction
Linux case using one warm-up/five release repeats. Freeze an **incremental
phase median ceiling of 250 ms for that 34-instruction query** for I4 acceptance;
this is an explanation-layer budget separate from the preserved 2,000 ms
condition for the active real Windows query. The user-authorized
[replacement](i4-windows-repin-validation.md) retires the missing original Electron
artifact as an active obligation while preserving its historical records. The
Linux phase benchmark uses the Rust reference analysis; active Windows CLI
qualification verifies native BAP receipts and 98 decoded starts. Neither budget is a universal
worst-case bound.

The operational workload and acceptance records use
`ariadne.investigation-workload/v3` and
`ariadne.investigation-first-delivery/v2`. This does not change the explanation
schema above. The active case ID/digest, complete source/tool inventory and
qualification environment must match; older workload records cannot qualify the
replacement. Windows qualification is recomputed from identity-bound release
CLI **explanation-mode** samples, excluding warm-up, with at least five measured
repeats. Missing, malformed or over-budget measurements cannot grant full I4
acceptance; base-mode or phase-only timings cannot substitute.

`windows98Qualification` reports `unavailable`, `invalid`, `over-budget` or `met`,
plus the checked/valid flags, sample count, median and fixed budget. The aggregate
`fullI4RealCaptureAcceptance` additionally requires passing gates and source/tool
stability. The narrower `passed` field still describes the exercised implementation
and fixture/Linux tier. Legacy records lacking the required measurement evidence
cannot establish full Windows acceptance.
