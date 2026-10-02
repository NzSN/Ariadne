# Stage 1 follow-up: remove the LLVM semantic backend

> **Archived 2026-10-02: completed within its recorded scope.**
> This is a historical plan, not an active task list. Evidence remains tied
> to its original sources, backend and workload. See the [plan index](../README.md)
> for current work and separate qualification requirements.

Requested **2026-10-01** after the Stage 1 implementation.
Design: [BAP semantic backend](../../docs/Ariadne/bap-semantic-backend-design.md).

Make BAP the sole minidump semantic producer. Remove CLI backend selection,
the normal library's LLVM preparation branch, and the BAP adapter's legacy
semantic fallback. LLVM MC remains an independent byte/length/control reference;
the separate directly supplied LLVM IR analysis and historical effect-oracle
research are outside this removal. Rust continues to own the analysis core.

The user explicitly authorizes selecting BAP now. This overrides the earlier
LLVM-default rollout choice, while preserving the missing 98-instruction Windows
qualification and the 2,000 ms performance condition as unmet evidence. Default
selection does not turn partial qualification into a pass.

1. Add a decoded-facts-only MC boundary; production BAP code must not invoke
   the legacy effects preparer or read its uses/defs/rules.
2. Project the required captured store directly from BIL. Preserve opaque calls,
   weak memory, explicit unsupported/control gaps, aliases and query ownership.
   Replace legacy shape-dependent guards with decoded operand/control binding.
3. Route default CLI/library/examples/benchmarks through BAP, remove the semantic
   selector, and expose helper/runtime configuration independently from the
   decoder reference. Unsupported BIL must remain opaque or stopped explicitly,
   with no automatic LLVM semantic recovery.
4. Update independent expectations, malformed-input tests, producer mutations,
   all-state model replay, minidump/Stage E regressions and workload tooling.
   Keep historical records immutable and retain a fresh removal record.
5. Update current docs/checkpoints and verify design-to-plan links. Report
   unsupported scope and unavailable Windows evidence honestly. Commit/push
   remains a separate user action.

Implementation: delivered in the working tree. The
[current validation report](../../docs/Ariadne/bap-only-removal-validation.md)
and machine-readable record distinguish removal acceptance from the still
incomplete full Windows/Stage 1 qualification. LLVM's role is decoded-fact
validation and historical/supplied-IR research, with no production semantic
selection or fallback. The user has authorized committing this change; push remains a separate action.
