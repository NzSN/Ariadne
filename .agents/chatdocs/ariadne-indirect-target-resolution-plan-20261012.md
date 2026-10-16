# Captured indirect target resolver implementation plan

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

## Context and follow-up

**Status.** R0–R6 are pending. This plan was written on 2026-10-12; it does not
authorize or claim completed runtime implementation. The existing dump
inspection is a motivating target oracle, not resolver qualification.

**Why this document exists.** The [canonical design](../../docs/Ariadne/indirect-target-resolution.md)
defines how captured pointer slots and bounded relative tables can supply
indirect CFG targets while preserving snapshot identity and unresolved cases.
Implementation needs a model, evidence validation and discovery integration
before augmented graphs can be accepted by either core backend.

**What this document establishes.** Stage ownership, dependencies, compatibility
constraints, acceptance gates and the evidence required for the initial profile.

**Where to go next.**

- [Semantic contract](../../docs/Ariadne/indirect-target-resolution.md#semantic-contract)
  — target candidates, conditional completeness and captured-memory premises.
- [Formal-model guide](../../Specs/README.md) — authoritative models and separate
  conformance/replay evidence; complete R0 before runtime edits.
- [Input preparation](../../docs/Ariadne/file-reader-design.md#public-interface) and
  [BAP backend usage](../../docs/Ariadne/bap-analysis-core-design.md#backend-usage)
  — existing capture, helper and native/Rust execution contracts.
- [Motivating capture](../../docs/Ariadne/indirect-target-resolution.md#motivating-windows-capture)
  — exact original artifact, 58 entries, 45 destinations and retained limits.

**What remains unresolved.** There is no implemented resolver, resolver model,
enabled CLI or qualification campaign. Budgets and timing ceilings must be
frozen in R0. General indirect calls, mutable dispatch data, broad value-set
analysis and execution-history reconstruction remain outside the first profile.

## Delivery scope and constraints

Deliver opt-in resolution for AMD64 near jumps through an established constant
pointer slot or a bounded signed-32 table-relative expression. BAP supplies
admitted semantics; LLVM MC independently checks decode/control facts. No
automatic LLVM effects fallback, live process reads or module-file byte filling.

All targets, receipts and source spans belong to one immutable snapshot. Use
machine-width arithmetic for target expressions and checked storage mapping for
reads. Maintain explicit holes/conflicts, unknown incoming states and unsupported
transfers. Caller-supplied entry points remain roots; slice seeds remain selectors.
Calls retain their existing summary/effect policy.

The first enabled profile explicitly declares `FrozenCapturedControlData`.
Completeness is relative to this premise and the covered incoming-state scope.
Readable or read-only metadata alone cannot establish historical stability.
Known targets with missing code remain edges and unavailable endpoints.

Keep disabled mode compatible with current preparation and reports. Version
enabled query/semantic/receipt/capture contracts. Core-only builds must continue
to activate no external crate dependencies. Heavy SDK, model, mutation and real
capture qualification use the established remote environment and separate
task-owned build directories.

## Stages and acceptance gates

| Stage | Owner and work | Required exit |
| --- | --- | --- |
| R0 — freeze contract and oracle | Canonical design, proposed `Specs/AriadneTargetResolution.tla`, finite configurations/checker and independent fixtures under `tests/bap/fixtures/`. | Model bounded reads, index/value facts, unknown residuals, certificate invalidation and conditional completeness. Freeze supported BIL forms, default budgets, report/profile versions and timing criteria before runtime edits. |
| R1 — extract semantic evidence | Proposed `src/bap/target_resolution.rs`, existing BAP AST/admission/projection and address evidence. | Admitted width-correct pointer/table/guard expressions; definition and clobber witnesses; explicit unsupported outcomes. Production recognition must not scrape printed assembly or share oracle enumeration logic. |
| R2 — evaluate captured control data | Resolver and `src/input/address_space.rs`, through the existing reader API. | Exact little-endian pointer and signed-32 enumeration, deduplication, all contributor spans and conservative partial outcomes. Prove finite coverage conditions; retain known targets even when target code is absent. |
| R3 — integrate discovery | `src/input/materialize.rs` and prepared-analysis identity/evidence ownership. | New targets schedule local instruction reads; expanded incoming edges trigger fact/certificate revalidation. Bounded convergence or explicit partial stops, unchanged roots/seeds and frozen output only after final validation. |
| R4 — validate native admission | `src/bap/core_adapter.rs`, `core_protocol.rs`, native `capture.ml`, profile/handshake and product tests. | Strict identity/receipt/target coverage validation; forged, stale and cross-snapshot receipts rejected. Native and Rust consume the same augmented request. Preserve call-versus-summary policy and incomplete-target obligations. |
| R5 — expose the product | Input/investigation reports and `src/bin/ariadne-minidump.rs`, proposed `--resolve-indirect-targets`. | Explicit memory premise, versioned enabled reports, all target evidence and residual gaps; disabled-mode regression. A resolved table alone must not change a still-partial explanation to explained. |
| R6 — qualify the extension | Root checks, finite oracle/model/replay tests, isolated real-code mutations and the external Windows capture. | Source/tool/artifact-bound acceptance for the declared finite profile, native/Rust parity, fixed R0 budgets and independently inspected real-capture targets. Record unexercised prerequisites and historical evidence separately. |

Proceed in stage order. R1/R2 may reuse existing reader and BIL structures, but
R3 cannot promote an incomplete prototype into the core's trusted target input.
R4/R5 must complete before calling the mode a supported product capability.

## R0 contract freeze

Review the existing [target certificate](../../Specs/Ariadne.tla), not just the Rust
field layout. The proposed resolver model must separate discovered candidates,
remaining unknown alternatives and validated exhaustive coverage. Its required
property is containment of all admitted target values when `complete = true`,
not exact feasible-path reconstruction.

Freeze independent cases before implementation: a constant pointer, positive
and negative relative offsets, duplicates, default branch, nonzero lower index
bound, 32-bit index wrap, 64-bit target wrap, missing/partial/conflicting entries,
readable data with missing target code, a bypassed guard, a redefined base/index,
an opaque clobber and a newly discovered incoming edge invalidating coverage.
Include malformed and cross-snapshot receipt cases and every zero/exhausted
budget. Define separately bounded table entries, targets, read/evidence bytes,
value alternatives, transfers, revisits, graph growth and cooperative time.

TLA+ remains authoritative for the modeled contract. Parse/typecheck the new
model, explore finite safety and fair termination cases, and preserve existing
core/input/effects scenarios. Finite exploration, replay and mutations are
separate evidence; none is a universal ISA or Rust refinement proof.

## R1 and R2 semantic and read implementation

Expose only admitted transfer evidence needed by the selected forms. Retain
instruction VA/bytes, BIL/helper/projection identities, operand widths and
register-definition bindings. Conditional constraints belong to graph edges;
both structural edges remain. Treat unsupported outputs and opaque effects as
unknown, never as preserving a value without proof.

Evaluate through immutable captured reads. A table entry needs all four bytes;
a pointer slot needs all eight. Compose fragments according to the existing
reader contract. Preserve agreeing overlaps and reject arbitrary selection of
conflicting bytes. Sign extension, endianness and modulo arithmetic require
independent expected values. Unknown table contents retain an unresolved
alternative unless the enabled captured-memory premise is bound and visible.

## R3 discovery and coverage validation

Maintain separate instruction and resolution worklists. Add candidate indirect
edges and their endpoints to the finite request domain, then materialize newly
reachable local starts. Revisit value facts when predecessors change. A final
certificate must cover every admitted incoming route to its dispatch; a new
bypass, clobber or unmodeled route downgrades coverage.

Do not certify a guard solely on the initially recovered graph, or let a target
edge justify its own premise. Record unresolved frontier states and unsupported
incoming transfers. On resolver exhaustion, retain proven candidates and
unknown residuals under the selected partial-result contract. Existing ordinary
preparation bounds retain their existing failure behavior.

Freeze all instruction/target facts before native/Rust core initialization.
Reaching definitions and slicing run against the expanded frozen graph;
previous graphs/results and query identities remain historical artifacts.

## R4 and R5 evidence and product integration

Native capture admission currently receives trusted normalized facts and bounded
instruction-prefix records. Table reads and completeness receipts need their
own versioned validation path, rather than being squeezed into those site records.
Bind covered graph/value revisions, premises, table read spans, arithmetic and
target sets; a matching hash alone is not a coverage proof.

Keep the enabled CLI opt-in through qualification. Display whether the target
set is complete within its declared scope or still has additional possibilities.
Propagate all remaining gaps into investigation status. Preserve disabled-mode
output and old strict schema decoding; enabled identities must include resolver
version, memory policy and limits. A production mode cannot depend on the
temporary diagnostic frontend used in the motivating dump inspection.

## R6 qualification procedure

Run affected portable tests and applicable root checks after behavior changes:

```sh
cargo fmt --all -- --check
cargo test --offline --locked
cargo test --offline --locked --no-default-features
cargo clippy --offline --locked --all-features --all-targets -- -D warnings
python3 tools/check_rust_layout.py
python3 tools/check_doc_links.py
```

Follow the linked module/model guides for native helpers, ignored tests,
generated replay and mutations. Define the new resolver checker in R0; its
future path is not an already available qualification command. Keep model,
replay and mutation build outputs separate. Use a read-only dependency snapshot
when required by the existing BAP qualification workflow.

Mutate real production seams: wrong signedness/endian/base/scale, ignored guard,
lost incoming alternative, ignored clobber, stale completeness, dropped missing
entry, filtered unavailable target, skipped identity/premise validation and
seed-as-root discovery. Each selected mutant needs an independently expected
observable failure, not a test that mirrors the production helper.

For `dump_048B10C302A4460D8A1FC75088`, retain the original SHA-256, all table
contributors and the 58-entry/45-target oracle. Establish a supported large-input
execution path explicitly: the current CLI's 256 MiB cap rejects the 1.31 GB
artifact. A controlled library caller with declared `OpenLimits` can exercise
the original; any reduced capture must retain original/derivative identities,
byte correspondence, query/entry premises and its narrower scope. Decide the
production size-limit/API path before claiming CLI support for this artifact.

The enabled query must expose the 45 witnessed indirect edges and preserve
additional unknowns unless final coverage is justified. Expect new discovered
instructions, edges and dependencies; do not require the old 329/388/15 counts
to remain unchanged. Compare native/Rust normalized requests and final results,
inspect new gaps, and retain the incoming-RDX boundary and unrelated unsupported
controls. The external inspection alone cannot supply Linux or general-table
coverage, executed-path evidence or root-cause attribution.

Write new qualification receipts under `evidence/Ariadne/indirect-target-resolution/`.
Retain exact sources, BAP/runtime/helper/decoder/native-build identities, platform,
input/query hashes, limits, mode/premises, phase timings and named corpus clauses.
Measure R0's fixed resource/performance criteria on both focused fixtures and
the expanded real query. Earlier backend timing does not qualify this extension.

## Completion checklist

- R0 contract, budgets, schemas, independent oracle and model gates frozen.
- R1/R2 admitted expressions and captured target enumeration pass positive and
  negative cases without losing unresolved alternatives.
- R3 discovery closes or stops conservatively; final coverage is revalidated.
- R4 native/Rust admission and results agree; hostile receipts are rejected.
- R5 enabled product is explicit and evidence-bound; disabled mode remains compatible.
- R6 model/replay/mutation/native/external-capture clauses are individually
  recorded, with no missing tier relabeled as passed.

All checklist items remain pending. Documentation delivery changes none of
these acceptance states.
