# Ariadne documentation

## Context and follow-up

**Status.** Compact feature documentation, consolidated on 2026-10-11.

**Why this document exists.** The [project overview](../../README.md) introduces
snapshot-based machine-code investigation. This index locates each feature's
single document, including its usage, design, source review and qualification
history.

**What this document establishes.** Feature documents own their contracts and
supporting narrative. [Plans](../../Plans/README.md) own execution stages;
[checkpoints](../../CHECKPOINTS.md) own chronology; immutable evidence stays in
[evidence/Ariadne](../../evidence/Ariadne/README.md).

**Where to go next.**

- [Terminology convention](../terminology.md) — canonical repository vocabulary
  and the distinctions between analysis, evidence and acceptance claims.
- [Architecture and development](architecture.md) — pipeline, analysis concepts,
  source layout, build checks and historical tool compatibility.
- [Input](file-reader-design.md) — reader API, CLI setup and captured-case evidence.
- [BAP integration](bap-analysis-core-design.md) — semantic/native setup,
  projection, analysis, source review and qualification.
- [Investigation](investigation-design.md) — possible-origin questions and their
  binding, reporting and completeness contracts.
- [Documentation map](../documentation-map.md) — models, plans and related guides.

**What remains unresolved.** Address-wrap remains proposed. Memory-provenance
refinement has source implementation and finite probes; full model, mutation
and Scanner qualification remain pending. A retained passing result applies to its recorded source/tool/corpus
identities; consolidating its description supplies no new runtime qualification.

## Canonical designs

| Feature | Read | Contents |
| --- | --- | --- |
| Architecture and development | [Architecture](architecture.md) | Process ownership, analysis equations, learning references, source layout and development checks. |
| Captured input | [File readers](file-reader-design.md) | Reader API, CLI, immutable capture evidence, independent entries and retained real cases. |
| Captured indirect control targets | [Indirect-target resolution](indirect-target-resolution.md) | Implemented opt-in pointer-slot/table resolver and review corrections, conditional completeness and bounded discovery. Portable/root checks pass; pinned native/mutation qualification and CLI timing remain open. |
| Instruction semantics and native analysis | [BAP integration](bap-analysis-core-design.md) | Setup, lift/projection/admission and analysis contracts, source review, replay and qualification history. |
| Fault-address dependencies | [Investigation](investigation-design.md) | Bound completed analysis, possible origins, explanation API, validation history and the bounded frame-path implementation and its finite qualification scope. |
| Fault-time zero address | [Zero-address assessment](zero-address-design.md) | Predicate, admission, CLI, source review and controlled-capture qualification. |
| Fault-time zero base plus displacement | [Zero-base-offset assessment](zero-base-offset-design.md) | Decoded/BAP agreement, result contract, source review and qualification. |
| Fault-time address wrap | [Address-wrap assessment](address-wrap-design.md) | Selected design; model, implementation and qualification pending. |
| Memory provenance | [Memory refinement](memory-provenance-refinement.md) | Implemented bounded writer assessment and backward scalar inference; full qualification pending. |
| Rendering and minidump reports | [Result rendering](result-rendering.md) | Text/DOT/JSON, schema, examples and presentation history. |
| Typed replay and separate IR/stateflow paths | [Typed replay](typed-replay-design.md) | Generated ports, IR CLI, result schemas, replay and finite validation. |
| Workload performance | [Performance](workload-performance-design.md) | Benchmark usage, investigation optimizations, fixed budgets and dated measurements. |
| Legacy effects and decode reference | [Operand effects](operand-effects-design.md) | LLVM decode protocol, historical effect rules, source reviews and retired candidates. |
| Assurance | [Semantic assurance](semantic-assurance.md) | Trusted-lifter boundary, proof limits, practical priorities and retirement policy. |

The separate [core stateflow design](../machine-state-design.md),
[Rust implementation guide](../implementation.md), [formal models](../../Specs/README.md)
and [replay procedures](../../mbt/README.md) explain their own repository-wide
contracts. The feature documents above link directly to applicable plans and
raw qualification records.

## Maintaining the compact structure

Extend the owning feature document for usage, design decisions, contracts,
source-review findings and dated validation summaries. Keep distinct features
separate; use sections and direct section links for stages of the same feature.
Retain source/tool/corpus identities, failed results and successor boundaries
when summarizing older campaigns. Preserve raw evidence bytes and inventories.

When absorbing a page, preserve its unique contracts, remove the old file and
redirect live references. Historical inventories keep their original paths and
hashes; Git retains those document revisions. Every feature document maintains
its Context and follow-up section and direct implementation-plan links. Run
`python3 tools/check_doc_links.py` after navigation changes.
