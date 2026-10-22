# AMD64 operation coverage program

## Context and follow-up

**Status.** Stopped at the user's request on 2026-10-22, after partial work on
instruction inventory, broader semantics and advanced producer integration. The
[stopped checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request)
is the current resume boundary. Full coverage is the target, not an achieved result. Initial implementation proceeds on both
machine-instruction semantics and Windows unwind operations. A representative
family survey is not an exhaustive instruction-form inventory.

**Why this document exists.** The [BAP semantic design](../../docs/Ariadne/bap-analysis-core-design.md#amd64-operation-coverage-program)
and [frame investigation design](../../docs/Ariadne/investigation-design.md#amd64-unwind-coverage-program)
currently expose finite admission and unwind profiles. The user requested a
plan followed by implementation to close operation coverage across AMD64.

**What this document establishes.** One execution ledger coordinates two
separately testable tracks. It defines the meaning of support, implementation
order, compatibility boundaries and the gates required before claiming full
coverage. Existing designs remain the canonical contract owners.

**Where to go next.** Read the [test matrix](../../tests/README.md),
[BAP trust boundary](../../docs/Ariadne/semantic-assurance.md), and the two design
sections above before implementing a stage.

**What remains unresolved.** The pinned BAP producer has missing lifts; the
current projection excludes architectural state and control constructs. Windows
unwind metadata versions and exceptional transitions also need separate work.
No unknown, unexercised or merely decoded operation counts as semantic coverage.

## Completion contract

An operation is supported when legal forms under its declared architecture and
execution-mode premises have implemented control, use, possible-write and
definite-write behavior, or implemented unwind transitions, with independent
executable expectations. Runtime/environment values may legitimately remain
unknown; an unimplemented operation must not be relabeled supported by giving
it generic unknown effects. Illegal/reserved encodings require explicit
rejection and negative tests; they are not missing legal operations.

The coverage denominator must be a versioned authoritative operation/form
inventory, not discovered instructions in a sample capture or a list of opcode
spellings. It must distinguish 64-bit forms, operand/address widths, prefixes,
architectural extensions, privilege/mode premises and aliases. The target
includes general/system instructions, x87/MMX, SIMD/vector/mask state, atomics,
string/repeated operations and newer published extension families. Compatibility
or 16-bit-only forms are recorded as mode-inapplicable rather than counted as
64-bit implementation successes. AMD and Intel extension differences stay
explicit. Windows unwind metadata v1/v2 and published v3/APX are separate rows.

Primary references:

- [AMD architecture manuals](https://www.amd.com/en/search/documentation/hub.html) —
  authoritative versioned instruction forms and architectural state; pin exact
  revisions before claiming an exhaustive denominator.
- [AMD Volume 3 revision 3.37](https://docs.amd.com/v/u/en-US/24594_3.37) — initial
  general/system reference, not the complete SIMD/x87/extension denominator.
- [Microsoft x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64?view=msvc-170) —
  conventional unwind operations, ordering and chained metadata.
- [Microsoft unwind v3/APX](https://learn.microsoft.com/en-us/cpp/build/x64-unwind-information-v3?view=msvc-170) —
  separately versioned descriptor format; Ariadne replay profile v3 must not
  be confused with this Windows metadata version.

This program expands implementation coverage. It does not revive the retired
independent instruction-step proof project or replace trusted BAP lifting with
automatic LLVM semantic fallback. A changed lifter is a new pinned dependency
that needs qualification. Analysis-level formal contracts remain active.

## Baseline

Source baseline: `9184c4ce9fcd775295735927e9b13b2997c07e77`.
Fresh initial checks: default Rust 362 passed/129 ignored, core-only 64/22,
251 Python controls, formatting, all-feature/all-target Clippy, layout and local
documentation links pass on Rust 1.96. No edits were present at that boundary.
The installed native analysis helper fails current source identity validation;
its files exist, but this is not a current native qualification.

Machine semantics currently use projection profile v6 with GPR/RIP, seven flags,
memory and XMM/YMM0–15, bounded at 256 bits. General loops, specials, exceptions,
several prefixes and missing upstream lifts remain outside supported admission.
The unwind parser accepts ordinary-body Windows metadata v1 with flags zero;
its Ariadne profile v2 adds captured SAVE_XMM128 bytes but has no dedicated
operation-specific regressions at the baseline.

## Stage ledger

| Stage | Work and exit | Status |
| --- | --- | --- |
| C0 | Link canonical contracts and define separate instruction/unwind coverage, gaps and compatibility. | Passed: linked contracts and plan navigation |
| S0 | Executable family survey using actual instruction bytes; probe actual BAP lifting and Ariadne projection, preserve distinct outcomes and exact source/tool identities. | Passed finite survey: 49 families / 170 byte cases; not S1 completeness |
| S1 | Expand S0 into a pinned exhaustive legal-form denominator across the declared AMD64 manuals/extensions; independent inventory completeness check. | Pending |
| S2 | Close missing producer lifts in a reviewed BAP source build; pin and validate the replacement producer and retain existing semantic compatibility. | Partial: four plain flag forms integrated as explicit v9 opt-in; native/corpus/replay controls pass; all other producer gaps remain open |
| S3 | Extend typed transport, state banks/aliases and width handling for all required SIMD, mask, x87, control/system and extended registers. | Pending |
| S4 | Implement exact prefix distinctions and bounded loop summaries; preserve zero-iteration paths, conditional writes, faults and resource stops. | Pending |
| S5 | Implement and qualify remaining floating-point, system, exception and special-operation contracts with explicit mode/environment premises. | Pending |
| U0 | Preserve old v1/v2 receipts and add a separate new replay profile with conventional opcode tests. | Passed finite v4 tests, preserving v1/v2/v3 replay |
| U1 | Complete near/far saved-vector operations and validated saved-register ordering, bounds, alignment and budget behavior. | Passed selected synthetic and Windows reference cases |
| U2 | Implement machine-frame restoration and exact interrupted-PC provenance; prevent ordinary-call/alignment inference across exceptional transitions. | Passed both machine-frame layouts, null interrupted PC and consumer regressions |
| U3 | Implement handler/chained metadata and partial-prologue execution with bounded chain/cycle and frame-establishment checks. | Passed selected metadata-v1 cases; chained operation restrictions remain explicit |
| U4 | Implement documented epilog suffixes and Windows metadata v2 descriptors, with independent reference comparison. | Implemented finite v1/v2 scope: 53 focused tests and 103 Windows comparisons pass; sparse capture and malformed terminal contexts have separate controls |
| U5 | Implement Windows v3/APX descriptor and extended-context support as its own versioned profile; do not reinterpret earlier formats. | Pending: extended-context/canonical-frame layouts and working V3 reference not admitted |
| Q0 | Current-source native rebuild, independent per-operation expectations, Rust/native parity where applicable, focused mutations and models, capture and root regression checks. | Partial: checks below pass for delivered slices; complete ISA/model/capture/timing/release campaign not performed |
| Q1 | Every legal inventory row supported and exercised; all stage exits complete; document exact operation/form denominator and remaining environmental premises. | Pending |

Stages may run in parallel when their source ownership does not overlap.
Passing an earlier stage never closes S1/S2/S3/S4/S5/U4/U5/Q1 by implication.

## Machine-semantics implementation

1. Add a data-only catalogue in `tests/bap/fixtures/amd64-semantics/`, a public
   native test that calls the actual BAP preparation API, and a Python driver.
   Inventory-only mode records unexercised rows. Live mode records decode/lift,
   actual projected effects and explicit unsupported reasons separately.
2. Require catalogue uniqueness, real byte strings, architecture/mode/family
   identity and independent effect expectations where available. A decoded or
   projected instruction alone does not prove ISA-correct semantics. Freeze
   representative negative/missing-producer cases as well as positive examples.
3. Use the survey to identify producer gaps before changing admission. Review
   and patch the BAP lifter or select a qualified successor; Ariadne must not
   synthesize instruction effects from LLVM opcode names to conceal missing BIL.
4. Version changes to producer/admission semantics. Preserve replay of old
   profiles. Expand architectural state and control semantics with explicit
   alias, exceptional-completion and must-definition rules before admitting
   new families. Unknown producer constructs remain visible until implemented.
5. Each family stage adds actual-byte expectations, malformed controls and
   source-bound native comparisons. Expand the catalogue into exact legal forms
   before any overall percentage or full-coverage statement is published.

## Unwind implementation

The new Ariadne replay profile preserves the v1/v2 algorithms and exact read
sequences when replaying their saved products. New successful frames record
whether their transition to the older frame is a normal return or a machine
frame. The optional field is omitted for old profiles, preserving old serialized
bytes and hashes. A machine frame restores exact RIP/RSP; it must not use the
ordinary return-PC-minus-one lookup or manufacture an active CALL witness.

Conventional legal operation inventory: PUSH_NONVOL, both ALLOC_LARGE forms,
ALLOC_SMALL, SET_FPREG, SAVE_NONVOL/FAR, SAVE_XMM128/FAR, PUSH_MACHFRAME with and
without error code. Windows v2 EPILOG is a separate format stage; reserved
SPARE_CODE stays rejected. CLR Unix SET_FPREG_LARGE is not silently treated as
a Windows operation. Windows v3 WOD descriptors require their own inventory.

Handlers are opaque data; reading their metadata never executes a handler or
establishes exception resumption. Chained records require bounded, cycle-checked
captured traversal and valid register/allocation relationships. Partial
prologues apply only operations completed at the captured instruction boundary.
Epilog interpretation consumes captured instruction bytes and admits only
documented validated forms. Missing code/stack bytes stop with an explicit gap.

Machine-frame stack switches may be represented only to the extent supported
by captured stack evidence. Frame/path consumers must preserve exceptional or
unavailable-call boundaries rather than treat such frames as normal ancestry.
Vector save evidence is not a fabricated captured vector register context.

## Validation and source ownership

- Runtime: `src/investigation/frame_unwind.rs`, `src/input/frame_paths.rs`,
  affected frame/path consumers; machine admission/transport in `src/bap/` and
  `native/bap/` only after matching producer work.
- Tests: independent synthetic captures under `tests/input/`, instruction bytes
  and projection probes under `tests/bap/`; validation tools under `tools/`.
- Positive/negative unwind tests cover every legal code/info/register boundary,
  offsets, truncation, alignment, budgets, partial prologues, chains/cycles,
  epilogs, machine layouts and same-capture old/new profile replay.
- Compare applicable unwind cases against an independent Windows
  `RtlVirtualUnwind` harness; synthetic Rust tests are not credited as that tier.
- Use existing independent BIL oracles, native/core replay and focused mutants
  for semantics. Isolate probe/replay/mutation builds below separate `target/`
  directories. Do not publish generated reports or copied runtimes in source.
- Run affected tests, formatting, default/core-only Cargo tests, strict
  all-feature/all-target Clippy, layout and documentation-link checks after
  integration. Native helpers, model tools and actual captures remain explicit
  prerequisites of their selected tests.

## Execution log

2026-10-22: baseline analysis completed; two-track coverage program started.
Initial parallel work owns the actual BAP survey, unwind implementation,
independent unwind fixtures and exceptional-transition consumers separately.
No full-coverage or native qualification claim is made at program creation.

2026-10-22, first finite implementation boundary: Ariadne unwind profile v3
passes 37 focused input tests and 79 fresh Windows RtlVirtualUnwind comparisons
with stable sources. The stage-v3 default suite passes 389 tests (131 ignored).
The first 78-case run matched values but failed source stability and remains a
failed run; a separate RET-immediate comparison exposed a real SP mismatch,
fixed before the successful 79-case run. These are finite adapter results.

The actual production semantic survey observes 44 projected cases, 8 conservative
unknowns, 79 missing lifts, 33 unsupported control/semantic cases, 2 unsupported
state cases, 2 decode disagreements and 2 query errors. Five independent effect
expectations pass. Seven source-producer controls and the actual baseline/patched
BAP experiment prove CLC/STC/CMC/STD gap closure on the four exact plain forms
plus CLD: 20 flag input combinations and 30 observations per executable. The
pilot is not production integration and does not close full S2. The SDK and
packaged runtime are unchanged. A fresh native analysis helper was rebuilt,
with the previous binary/manifest backed up under ignored target storage.

### Integrated execution boundary

The initial finite stages have been implemented and tested. **The full AMD64
objective is not complete.** S1, wider S2, S3–S5, U5 and Q1 remain open; no
representative survey or conservative unknown result closes those exits.

- Fresh Ariadne unwind profile v4 supports conventional Windows metadata v1/v2
  operations, bounded handler/chained records, partial prologues, explicit
  machine transitions and metadata-selected epilogs. Saved v1/v2/v3 replay
  remains separate. Fifty-three focused tests pass, including sparse capture and
  malformed terminal-PC controls. All 103 complete-image synthetic Windows
  RtlVirtualUnwind comparisons pass with stable sources. Sparse capture tests
  are Rust-only, not native sparse-input qualification.
- Source-built BAP CLC/STC/CMC/STD support is an explicit opt-in v9 producer path.
  Two independent builds reproduce the pinned executable/manifest. Eight Rust
  controls include actual native transport, Windows/Linux capture parity,
  tampering and saved-mode refusals; four direct native validator controls and
  sixteen Python producer/survey controls pass. Fifty-seven unaffected cases
  retain their effects under the changed opt-in identity. Guards, target
  resolution and memory refinement are explicitly excluded for v9, including
  their saved/native admission boundaries.
- The final 171-encoding/49-family survey has 44 projected and 80 missing lifts
  by default, versus 48 projected and 76 missing lifts with the extension.
  Exactly the four selected flags change status; all nine independent expected
  effects pass with the extension. Default missing flag expectations remain
  failed. Other unknown, unsupported, disagreement and query-error categories
  remain unchanged. This is not an exhaustive legal-form inventory.
- On Rust 1.96, default tests pass 410 with 134 ignored; core-only passes 64 with
  22 ignored. Strict all-feature/all-target Clippy, formatting, layout and
  navigation pass. Three property tests pass 384 configured unwind cases; 251
  general Python controls pass. One compiled current-body guessed-stack-slot
  mutant is detected by the allocation/save observer. Six existing mutation
  selectors are unique; the entire six-mutant campaign was not rerun.
- The mutation experiment first failed to compile because the isolated-copy
  helper omitted the alignment model. That attempt earns no mutation credit.
  The helper now includes all required model/native compile-time inputs; the
  fresh mutant compiles and fails for the intended behavioral assertion. New
  native compile-time inputs also participate in source inventories.

Windows V3/APX has a separate public preview format. The current reader and
minidump dependency retain only the legacy AMD64 context; authoritative APX
context/canonical-frame layouts and a working independent reference remain
unmet prerequisites. A base-only V3 capability attempt errored in an isolated
Windows reference process and grants no support credit; it does not establish a
complete diagnosis of OS V3 availability. No guessed layout was admitted.

All generated observations, failed attempts, binaries, copied mutation sources
and backups remain under ignored target/ or temporary storage. The maintained
files are implementations, fixtures, executable controls and dependency pins.

Final address-boundary review added checked construction for runtime-table and
chained virtual addresses, plus the legacy unwind-code pointer. Three new tests
exercise explicit refusal at the half-open endpoint at 2^64 through saved-chain
replay. They separately retain the current minidump reader's omitted-module
result and reject a manually supplied module premise during live rebinding.
The final current-source Windows matrix still passes all 103 bounded-image cases;
these high-address and sparse-input tests are Rust-only. The final source also
passes the selected compiled stack-slot mutation, 384 generated unwind cases,
410 default Rust tests, 64 core-only tests and strict root checks.


### User-requested stop: items 1–3

2026-10-22: implementation and native campaigns stopped before completion.
The [checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request)
records the exact source/test boundary and failures; resume only when requested.
S1 now has reproducible pinned XED templates and AMD manual transcriptions with
explicit unresolved extraction/legality gaps. S3/S4 have finite v10/v11
FP-control, NOP, data-path-join and mandatory-count admission work. REP remains
refused; its independent numeric oracle is not production admission. The
separately pinned advanced producer and versioned guard/target/refinement
integration are saved with a failing native matrix and incomplete count replay,
compatibility and mutation gates. Earlier ledger statuses are historical stage
exits; none of S1, broader S2–S5 or Q1 is closed by this stopped snapshot.
