# Priority 3 implementation plan: investigator presentation and examples

## Context and follow-up

**Status.** Completed plan, archived; acceptance is limited to the recorded scope.

**Why this document exists.** [Motivating design](../../docs/Ariadne/priority-3-investigator-presentation-design.md) defines the problem and contract this plan implements.

**What this document establishes.** The presentation delivery adds the instruction overview and Linux/Windows examples and records unchanged JSON/DOT semantics for the exercised case.

**Where to go next.**

- [Delivery and follow-up](../../docs/Ariadne/priority-3-presentation-validation.md) — records what was exercised and which limits remain.
- [Active plan index](../README.md) — prevents completed steps from being mistaken for pending work.

**What remains unresolved.** The implementation steps below are archived, not a current task list. These results apply to the recorded sources, backend and workload. They do not qualify the current checkout without fresh or exact-source-verified evidence. This resolves the scoped readability work, not new investigation capabilities.

For the wider context, see the optional [documentation map](../../docs/documentation-map.md).

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Plan dated **2026-09-29** for practical priority 3 in the
[assurance queue](../../docs/Ariadne/practical-assurance-priorities.md). It executes the
[Priority 3 design](../../docs/Ariadne/priority-3-investigator-presentation-design.md) on the
delivered [Stage C report layer](../../docs/Ariadne/stage-c-report-schema.md). No analyzer,
decoder, effect or JSON v1 semantics change is authorized by this plan.
The text overview and examples are
[delivered with source-bound validation](../../docs/Ariadne/priority-3-presentation-validation.md).

## 1. Freeze the current report contract

Run both pinned Stage B Windows/Linux CLI cases and the hash-checked Priority 1
Chromium case. Retain report identities and cross-format graph, slice and issue
counts. Record the current text, DOT and JSON output hashes before changing the
text presentation. Preserve the existing output-directory publication rules.

## 2. Add the scan view

In `src/input/report.rs`, render an Instruction overview from the frozen
`FilePreparedAnalysis` and `AnalysisResult`. Format typed operands and source
spans without parsing LLVM's printed assembly or reconstructing bytes from a
companion image. Show rule quality, slice membership, issues and a possible
input-origin count. Keep raw per-site JSON evidence and the full core text
after the overview, so no fact is lost. Leave DOT graph structure and JSON v1
schema unchanged.

## 3. Validate and publish examples

Extend focused CLI tests for the overview on Windows and Linux, including
high VAs, missing/opaque sites, source offsets, origin counts and faulting
memory operands. Compare all three formats against the same JSON identity and
edge/obligation sets. Parse DOT with Graphviz where available. Exercise
malformed options, missing decoder, resource limits and output I/O failure;
none may publish a misleading complete report.

Add a short release guide under `docs/Ariadne/` with exact commands for the
two pinned Stage B fixtures and a separately labeled external real-capture
replay. Keep the current minidump-only scope and explicit uncertainty language.
Run input tests, formatting, Clippy, the native CLI gate and the Priority 1
checker with stable source hashes. Retain a dated validation record stating
which output formats changed and which machine contracts did not.
