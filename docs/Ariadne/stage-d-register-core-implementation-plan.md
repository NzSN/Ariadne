# Stage D implementation plan: source-bound register-core acceptance

Prepared **2026-09-29** from the [AMD64 semantics design](../amd64-semantics-design.md)
and the scoped [user64 design](../amd64-user64.md). **Plan only:** it adds no
accepted instruction case and changes no form, profile, proof or coverage
ledger. The [current audit](stage-d-acceptance-audit.md) reports 49 paired
`register-core` bodies, **0/49 verified instruction steps**, and an accepted
no-trust unknown-instruction fallback. The broader
[remaining implementation plan](remaining-implementation-plan.md#d--close-the-scoped-amd64-semantics-gate-separately)
places this work in Stage D.

Execution began 2026-09-29. The [first-case progress record](stage-d-progress.md)
contains D0 and bounded D1–D3 evidence; D4–D6 and all 49 accepted cases remain
open. The opening paragraph preserves the plan's original preparation state.
The later [assurance priority decision](practical-assurance-priorities.md)
places this complete 49-case campaign in the **long-term formal research
track**. Its acceptance criteria remain intact; they do not gate practical
minidump investigation or source-reviewed conservative effects.

## Deliverable and boundary

Close the exact 49 form/profile cases of the active `register-core` milestone
in `amd64-user64-v1`, one case at a time, until both required milestone gates
pass on stable sources. A verified case is a complete instruction boundary:
validated decoded payload and state, successful architectural transition or
specified synchronous fault, all affected and framed state, next RIP or restart
state, matching TLA+/Lean semantics, and a conservative Ariadne projection.
A paired instruction body, a Rust effect summary, a parser result or a passing
component check alone is not that deliverable.

The 72 `near-control-stack` and 156 `ram-data` cases follow as separately
gated profile milestones. Stage A's `MOV32mi` and `MOV64mi32` analyzer rules
are `ram-data` candidates and do not count toward the first 49. This plan does
not add a Rust ISA executor, claim whole-manual coverage, or change the
minidump-only reader scope. Runtime use of accepted formal cases requires a
later, separately checked decoder/payload binding.

## Authority and starting inventory

- `Specs/AMD64/manuals.lock.json` pins AMD Volumes 1–3. Review each case
  against the locked manual bytes, not a floating online edition.
- `Specs/AMD64/forms.json` is the source-form catalogue;
  `Specs/AMD64/user64-profile.json` fixes mode, CPL, operand projection,
  required obligations and milestone membership. The current profile digest
  is `5c07adb4b1391d5b2ec29348b208789c2469b2728afd700f27cd3a90bef078cf`.
- `Specs/AMD64/user64-coverage.json` contains all 277 targeted progress rows
  and each `source_form_sha256`. `Specs/AMD64/coverage.json` holds semantic
  cases, recursively cited foundations/dependencies and source-hashed
  validation records. It currently has **zero** semantic-case entries.
- `tools/amd64_profile.py` derives a case hash from the complete source form,
  projected operands and progress row; it checks that cited accepted semantic
  evidence covers all eight required obligations. The acceptance mechanism's
  synthetic schema tests in `tools/test_amd64_profile.py` are examples of
  record shape, **not** architectural proof evidence.

Do not edit profile/form hashes or turn a `pending` record into `accepted` to
make a gate pass. Any reviewed source-form or profile migration invalidates
the old case digest and requires re-review and fresh evidence.

## Execution sequence

| Step | Work and owner files | Exit evidence |
| --- | --- | --- |
| D0. Freeze baseline | Run `python3 tools/amd64_inventory.py check`, `python3 tools/amd64_forms.py check`, `python3 tools/amd64_profile.py report --json` and default `check`; record locked PDF, form, profile, case and TLA/Lean source hashes. Keep unrelated working-tree edits out of the acceptance snapshot. | 49 exact `register-core` targets, 0 accepted initially, fallback accepted; any unavailable source/checker is recorded as unavailable, never as a pass. |
| D1. Close one candidate's source and payload | Start with `register-core:AMD64-F-0503-R` (`MOV reg64, imm32`), current source-form SHA-256 `d45a228c0720624d73a267ced2b728de85f0058ef94601f61e459329f8fbaa29`. Review the register-only `C7 /0 id` alternative, ModRM, REX.W and allowed/forbidden prefixes, encoded imm32, signed 64-bit value, destination identity, decoded length and profile guards. Reconcile the catalogue's table-evidence `rex.w_required=false` with the reviewed `rex-w` requirement before accepting a binding. Use pinned LLVM MC observations as cross-checks, not as sole ISA authority. | A case-specific source review and positive/negative decoded-payload fixtures; malformed shape, wrong width, memory alternative, illegal LOCK and unreviewed prefixes cannot be silently admitted. |
| D2. Compose a complete instruction step | In the relevant `Specs/AMD64*.tla` rules and checked fixtures, bind the reviewed form to validated CPU state, register write/alias behavior, rFLAGS and all untouched-state frames. Compose successful fetch, resolved synchronous events, fault priority, commit/restart and correct next RIP; a rejected decoded input is distinct from architectural #UD. Preserve the profile's asynchronous boundary assumptions. Mirror the exact contract in `lean/AMD64/*.lean` and state the TLA+/Lean correspondence mapping. | Executable TLA+ cases and Lean proofs cover success and each in-scope fault/undefined alternative, including negative cases. A body result with unchanged RIP does not satisfy the exit condition. |
| D3. Prove conservative analysis projection | Relate every possible architectural outcome to the existing `uses`, `may_defs`, justified `must_defs`, flag/alias cells and uncertainty policy. For a successful `MOV reg64, imm32`, check the sign-extended payload and full register destination; for faults and unsupported inputs, do not invent a successful write or successor. Keep the accepted `UnknownInstructionFallback` for any unclosed alternative. | TLA+/Lean projection statement and counterexamples/mutations for omitted sign extension, incorrect frame/flags, wrong next RIP, invented fault commit and overly strong analyzer kills. |
| D4. Bind evidence and promote one case | After D1–D3 pass, add source-hashed `validation_records` and an accepted `semantic_cases` entry in `Specs/AMD64/coverage.json`: TLA typecheck, executable TLC/Apalache, Lean build and axiom audit, checked rule paths/symbols, closed obligations, accepted dependencies/foundations, profile ID/digest and exact case digest. Then cite that entry from the matching row in `user64-coverage.json` and clear only obligations actually proved. | Default profile check reports **1/49** verified; a deliberately stale source/case hash, missing proof kind, unaccepted dependency or open obligation is rejected. The `--require-milestone register-core` gate still fails at 1/49. |
| D5. Scale across the remaining 48 | Group work by source-reviewed MOV, arithmetic, logic, comparison and unary families, but review every exact form/width/profile case. Reuse proved lemmas only with an explicit per-case instantiation and source/case hash. Prioritize pending form reviews before their instruction-step proofs. Maintain paired-body and accepted-case counts separately. | Every row has its own reviewed payload/boundary/projection evidence; no whole-mnemonic status or copied hash stands in for a case. |
| D6. Qualify the milestone | Run the full source-stable formal suite and both required `register-core` gates. Archive commands, versions, source hashes, positive/negative results and the 49 case IDs in a Stage D validation record. | **49/49** verified with no open required obligation; both milestone commands exit zero on the same checked source snapshot. |

The first candidate is a starting order, not advance acceptance. If its source
metadata or boundary has an unresolved discrepancy, record that gap and keep
the case unsupported until resolved. A different fully reviewed register-core
case may be used as the first end-to-end template without changing the
49-case exit criterion.

## Eight required obligations for every accepted case

| Obligation in `user64-profile.json` | Evidence that must be case-bound |
| --- | --- |
| `decoded-form-legality` | Exact form and profile guards, including mode/CPL/feature/prefix alternatives and architectural invalidity. |
| `operand-payload-binding` | Concrete register/immediate identity, encoded versus semantic width, sign/zero extension and instruction length. |
| `state-validity` | Well-formed pre/post architectural state and all required environmental assumptions. |
| `effects-flags-and-frames` | Values, register aliases, flags/undefinedness, and unchanged state banks. |
| `fault-and-commit-behavior` | Possible faults, priority, partial completion and restart/commit policy. |
| `instruction-boundary` | Fetch, composed outcome, next RIP or fault restart state; no body-only retirement claim. |
| `tla-lean-correspondence` | Named authoritative TLA+ rule and Lean definition/theorems tied to the same profile case. |
| `conservative-analysis-projection` | Sound Ariadne effects/control/unknown projection across every accepted alternative. |

## Gate discipline and release record

After each code or source-ledger change, run focused TLA+/Lean checks,
case-specific positive and negative fixtures, and case-specific semantic
mutations. An intended invariant/proof failure counts as a mutant rejection;
tool launch, parser, timeout or socket failures do not. Retain the old
register-only regressions and run the default `bash Specs/check-amd64.sh`
suite after integration. Its source snapshot must remain byte-stable across
inventory/forms/profile checks, Lean build and axiom audit, TLA+ typechecks,
TLC fixtures and Python integrity tests. The existing
`tools/check_amd64_mutations.py` covers register-view foundations only;
extend negative controls for the first accepted instruction step rather than
claiming those four existing mutants cover it.

During D1–D5, `python3 tools/amd64_profile.py check --require-milestone
register-core` is expected to report pending. Only after all 49 case records
close may these commands be reported as passing acceptance:

```sh
python3 tools/amd64_profile.py check --require-milestone register-core
bash Specs/check-amd64.sh --require-milestone register-core
```

Record the final evidence in `docs/Ariadne/stage-d-validation.md` (and a
machine-readable source-hash report) without overwriting the current
[0/49 audit](stage-d-acceptance-audit.md). The full-manual
`--require-complete` inventory gate is a separate roadmap decision. Formal
milestone acceptance will not by itself certify a compiled Rust ISA executor
or a production decoder-to-form binding.
