# Semantic assurance and retirement of independent ISA proofs

## Context and follow-up

**Status.** Current scope decision: BAP is trusted and independent ISA proofs are retired.

**Why this document exists.** [BAP assessment](bap-core-refactor-assessment.md) separates external semantics from ownership of analysis correctness.

**What this document establishes.** The decision retires independent AMD64 instruction-step proofs and makes pinned BAP lifting an explicit trusted dependency. Ariadne still owns transport, projection, analysis and evidence validation.

**Where to go next.**

- [Projection contract](bap-semantic-backend-design.md) — defines the boundary Ariadne still validates.
- [Open backend work](../../Plans/bap-integration.md) — preserves Windows qualification and unstarted core migration.
- [Rust proof boundary](stage-f-proof-and-performance.md) — remains open independently of ISA retirement.

**What remains unresolved.** Full original-Windows qualification is still open. The BAP analysis-core replacement has not started; neither selecting BAP nor passing a fixture closes those requirements. The universal Rust refinement boundary remains open; retired ISA obligations were not discharged.

For the wider context, see the optional [documentation map](../documentation-map.md).

Decision: **2026-10-02**, approved by the user. Ariadne retires its independent
AMD64 instruction-step project, including the user64 milestones, Stage D, Lean
ISA proofs and full-manual coverage objective. Retirement changes project scope;
it does not mark the former proof obligations as satisfied.

Ariadne relies on a pinned BAP lifter for AMD64 instruction semantics and
validates its own semantic projection and analysis. Results remain conditional
on supported lifting behavior and captured evidence.

## Active responsibility

The selected backend uses BAP's legacy x86 lifter and typed BIL. A formal
semantics for BIL does not itself prove that every AMD64 lift matches hardware.
The pinned helper/runtime identities and supported projection scope remain part
of the [backend contract](bap-semantic-backend-design.md).

Ariadne owns validation of the helper protocol, exact bytes and identities,
typed AST transport, register aliases, uses/may-defs/must-defs projection,
conservative memory and call behavior, analysis algorithms and evidence-bound
reports. Unsupported operations retain explicit gaps. Corpus tests, independent
decode/control checks, model replay and actual mutation sensitivity remain active.

The CFG, reaching-definition, slicing, abstract-stateflow, supplied-IR and
effects specifications remain active. The Rust implementations and their
finite replay checks remain model-relative evidence; a universal refinement
proof is a separate open boundary. This decision adds no execution-history or
root-cause guarantee.

## Dependency audit and retained references

The production Rust analysis and BAP paths do not execute the independent
AMD64 TLA+/Lean library. The active orchestration scripts nevertheless invoked
the register-core profile gate: `check_b_f_progress.py`, `check_stage_e.py` and
`check_bap_semantics.py`. Those calls and their pass/fail dependencies are removed.
New reports replace `registerCoreAcceptance` with an explicit
`instructionStepTrack` retirement status. Stage E and BAP qualification
reports advance to schema v2 for this field change; historical JSON files retain
their original fields and bytes. The B/C/E/F report remains unversioned.

The effects gate still binds `Specs/AMD64/manuals.lock.json` as source-review
provenance. Keep that lockfile. ISA-only TLA/config files and retired research
tools are excluded from the active effects/progress source inventories where
they were included through broad globs.

Retired research remains in place to preserve historical source paths, links,
coverage ledgers and evidence interpretation:

- `Specs/AMD64*.tla`, `Specs/AMD64*.cfg` and `Specs/AMD64/`.
- `lean/`, `Specs/check-amd64*.sh`, `tools/*amd64*.py` and `tools/check_stage_d*.py`.
- Initial `AriadneX86_64Semantics` instruction-rule research and its fixtures.
- AMD64 reference documents and machine-readable Stage D evidence. Obsolete
  Stage D plan/status Markdown has been removed; Git retains the original text.

These files are reference material, not an active backlog or release requirement.
Their old checks may be run explicitly for historical research; active product
gates must not depend on their success or expected failure. Git also preserves
the pre-retirement state at `2ba80a9`.

## Qualification limits preserved

The original pinned Windows capture and its workload condition remain required
for full BAP Stage 1 and investigation qualification. Retiring ISA proofs does
not waive those clauses, admit additional opcode forms, qualify BAP-owned
analysis-core replacement, or refresh old source-bound validation records.

The [roadmap](../../ROADMAP.md),
[agent instructions](../../AGENTS.md) and
[assurance priorities](practical-assurance-priorities.md) describe active scope.

## Retirement validation

`python3 -m unittest discover -s tools -p test_active_qualification.py -v`
passes three tests. Controlled subprocess fixtures exercise all three runners
without ISA files, gate failures, source-hash changes and both outcomes of the
Windows workload condition: eleven runner executions in total. An inventory
check confirms that effects qualification retains the analysis specifications
and manual provenance while excluding retired ISA models.

The Rust layout check and documentation link/diff checks also pass. These are
focused orchestration and documentation checks, not fresh native execution,
model replay, mutation campaigns or release qualification. Production Rust,
native helper code, formal model bodies and retained JSON evidence are unchanged.
