# Ariadne roadmap

Ariadne should produce useful, evidence-bounded control-flow and data-flow
results before the full AMD64 instruction set is modeled. Its long-term AMD64
coverage target remains in [the semantics design](docs/amd64-semantics-design.md).
The immediate formal deliverable remains the scoped
[64-bit user-mode profile](docs/amd64-user64.md). Neither a decoded instruction
nor a successful component check is, by itself, a verified instruction step.

## Current checkpoint

The Rust core already recovers a local instruction-level CFG, computes
may-reaching definitions, and builds a backward data slice from fixed,
adapter-supplied instruction summaries. An optional pinned LLVM MC adapter
decodes caller-provided byte spans and supplies conservative control-flow
summaries. `ByteSnapshot::prepare()` now adds structured operands and reviewed
normal-continuation effects for an explicit 137-opcode registry, with byte-level
GPR aliases, coarse memory and per-site gaps; see the
[delivery record](docs/Ariadne/operand-effects-validation.md). The [minidump package](input/README.md) now provides captured-memory input and
local-start discovery for Windows/Linux AMD64. PE/ELF image and ELF core readers
remain pending. The LLVM IR path and
abstract machine-state propagation are formal specifications without Rust
implementations.

The user64 profile targets 277 form/profile cases in three milestones:
`register-core` (49), `near-control-stack` (72), and `ram-data` (156). All 49
register-core cases have paired instruction bodies, but no case is accepted as
a complete instruction step. The conservative unknown-instruction fallback is
accepted for the pinned profile; all instruction cases remain unsupported.
See the [coverage report](Specs/AMD64/user64-coverage.json),
[validation record](docs/amd64-validation.md), and
[AMD64 task ledger](docs/amd64-semantics-tasks.md) for the exact evidence and
remaining obligations.

## Delivery path

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Input and decode | The pinned LLVM MC adapter and Windows/Linux minidump reader are delivered; PE/ELF images and ELF cores remain pending. Readers must provide one immutable address-space snapshot, VA mapping, and verified byte provenance. | The same known bytes decode consistently from binary and dump views; missing or conflicting bytes remain explicit. VAs are never confused with file offsets. |
| 2. Control-flow recovery | Translate decoded control transfers into the core's instruction kinds, direct targets, fallthroughs, calls, returns, and unresolved-edge obligations. | End-to-end binary and dump fixtures exercise direct branches, calls, returns, sparse bytes, and indirect branches. Every edge has source instruction evidence; unresolved targets are visible, not silently omitted. |
| 3. Conservative effects | Initial scoped rules and evidence are delivered; broader forms and precise aliasing remain. Supply `uses`, `may_defs`, and justified `must_defs` for the reaching-definitions and slicing core. Start with decoded operand and instruction metadata, then add reviewed rules for important register, flag, stack, and memory effects. | Slices retain every possible origin in representative crash paths. An unknown effect cannot become a definite overwrite, a no-op, or a known successor. Alias and call-summary assumptions are recorded. |
| 4. Verified precision | Close the existing `register-core` profile gate, then advance `near-control-stack` and `ram-data` case by case. Connect accepted semantics to effect summaries and, where justified, branch feasibility or indirect-target reasoning. | Each promoted case has source-bound TLA+ and Lean evidence for legality, payload, effects, frames, faults, instruction boundary, correspondence, and conservative analysis projection. The selected milestone gate passes. |
| 5. Investigator output | Expose annotated instructions, graph edges, slice origins, and unresolved obligations through a CLI and stable exports suitable for SVG rendering. | A crash-analysis fixture can be reproduced from a pinned snapshot, and each displayed conclusion links to its bytes, decoded instruction, and semantic evidence or uncertainty reason. |

Phases 1–3 provide a useful partial analyzer without waiting for complete AMD64
coverage. Phase 4 increases precision only where its evidence is accepted. The
formal work can advance alongside adapter work, but the adapter must not label
an unaccepted case as verified. The existing Rust core and its
[input contract](docs/implementation.md) remain the integration boundary.

## Scope and priority rules

- Prioritize instructions that appear on the control-flow and backward-slice
  paths of representative Chromium/Electron crashes. Direct control transfers,
  stack operations, common data movement, arithmetic, comparisons, and ordinary
  RAM accesses have immediate value; full-manual coverage stays on the roadmap.
- Use LLVM MC for decoding and available branch/operand metadata. Metadata is
  a starting point for conservative summaries, not proof of exact architectural
  effects. Keep indirect targets and uncertain memory aliases as obligations.
- Preserve the [unknown-instruction fallback](docs/amd64-user64.md#correctness-and-conservative-fallback):
  no invented successful step, architectural fault, definite write, or known
  successor. Distinguish unavailable captured data from an unsupported semantic
  rule and from an architecturally undefined result.
- Keep coverage claims separate: decoded and discovered instructions, useful
  analyzer output, paired semantic bodies, and verified instruction steps are
  different achievements. Do not infer whole-mnemonic or whole-ISA support from
  a passing fixture.

The next acceptance decision is the existing `register-core` gate. Its command,
evidence rules, and open obligations are defined in
[the user64 profile guide](docs/amd64-user64.md#progress-and-acceptance).
