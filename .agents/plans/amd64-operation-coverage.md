# AMD64 operation coverage program

## Context and follow-up

**Status.** Resumed at the user's request on 2026-10-23 from the
[stopped checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request).
The [resume record](../../CHECKPOINTS.md#2026-10-23--amd64-guard-replay-and-composed-fixture-resumed)
records source fixes, the approved native continuation and remaining gates. Instruction
inventory, broader semantics and advanced producer integration remain partial.
The [Basic candidate follow-up](../../CHECKPOINTS.md#2026-10-23--current-basic-v9-candidate-compatibility-checked)
passes three native tests under an isolated candidate pin; production adoption
and historical identity remain separate.
The [plain REP and accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting)
adds a separately selected v12 three-form dependency contract and executable
full-coverage obligations. The [source/domain findings](../../docs/Ariadne/amd64-coverage-design.md#101-source-corpus-execution-c1)
adds a five-volume candidate corpus, partial geometry recovery and finite v2/v3
legal-domain/binding registries; their full C1–C4 exits remain open. S4/Q0 remain partial.
The [memory-string successors](../../docs/Ariadne/amd64-coverage-design.md#104-default-address-memory-rep-execution-r1)
add finite v13/v14 plain dependency scopes with separate source and qualification
gates; the R1 source boundary passes 416 native parity instances and 259 refusal
controls. The AMD-specific v15 successor adds canonical address-32 forms and
passes its local gates; its changed native payload is awaiting specific approval.
Full coverage is the target, not an achieved result. Implementation proceeds on both
machine-instruction semantics and Windows unwind operations. A representative
family survey is not an exhaustive instruction-form inventory.

**Why this document exists.** The [BAP semantic design](../../docs/Ariadne/bap-analysis-core-design.md#amd64-operation-coverage-program)
and [frame investigation design](../../docs/Ariadne/investigation-design.md#amd64-unwind-coverage-program)
currently expose finite admission and unwind profiles. The user requested a
plan followed by implementation to close operation coverage across AMD64.
The [coverage completion design](../../docs/Ariadne/amd64-coverage-design.md)
owns the source, legal-domain, authoritative-binding and remaining REP
architecture and its dated finite implementation findings; this plan owns stage
execution.

**What this document establishes.** One execution ledger coordinates two
separately testable tracks. It defines the meaning of support, implementation
order, compatibility boundaries and the gates required before claiming full
coverage. Existing designs remain the canonical contract owners.

**Where to go next.** Read the [plain REP/accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting),
[coverage completion design](../../docs/Ariadne/amd64-coverage-design.md),
[test matrix](../../tests/README.md),
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
| S1 | Expand S0 into a pinned exhaustive legal-form denominator across the declared AMD64 manuals/extensions; independent inventory completeness check. | Partial: five-volume candidate corpus, all 2,657 historical gap dispositions and 56-point AMD legal/binding registry; seven source-conflict records, source authority, constraints and full grammar remain open |
| S2 | Close missing producer lifts in a reviewed BAP source build; pin and validate the replacement producer and retain existing semantic compatibility. | Partial: finite advanced/Basic candidate checks, frozen LODS producer and separate AMD address-size producer pass their scoped checks; Basic adoption, historical identity and other producer gaps remain open |
| S3 | Extend typed transport, state banks/aliases and width handling for all required SIMD, mask, x87, control/system and extended registers. | Partial finite v10/v11 FP-control state and coarsened data projection; wider banks/widths remain pending |
| S4 | Implement exact prefix distinctions and bounded loop summaries; preserve zero-iteration paths, conditional writes, faults and resource stops. | Partial: R1's 28 default-address tuples pass at their recorded native boundary; AMD v15 adds 28 canonical address-32 tuples with local gates passing. Current native v15, wider prefixes, proof consumers and partial faults remain open |
| S5 | Implement and qualify remaining floating-point, system, exception and special-operation contracts with explicit mode/environment premises. | Pending |
| U0 | Preserve old v1/v2 receipts and add a separate new replay profile with conventional opcode tests. | Passed finite v4 tests, preserving v1/v2/v3 replay |
| U1 | Complete near/far saved-vector operations and validated saved-register ordering, bounds, alignment and budget behavior. | Passed selected synthetic and Windows reference cases |
| U2 | Implement machine-frame restoration and exact interrupted-PC provenance; prevent ordinary-call/alignment inference across exceptional transitions. | Passed both machine-frame layouts, null interrupted PC and consumer regressions |
| U3 | Implement handler/chained metadata and partial-prologue execution with bounded chain/cycle and frame-establishment checks. | Passed selected metadata-v1 cases; chained operation restrictions remain explicit |
| U4 | Implement documented epilog suffixes and Windows metadata v2 descriptors, with independent reference comparison. | Implemented finite v1/v2 scope: 53 focused tests and 103 Windows comparisons pass; sparse capture and malformed terminal contexts have separate controls |
| U5 | Implement Windows v3/APX descriptor and extended-context support as its own versioned profile; do not reinterpret earlier formats. | Pending: extended-context/canonical-frame layouts and working V3 reference not admitted |
| Q0 | Current-source native rebuild, independent per-operation expectations, Rust/native parity where applicable, focused mutations and models, capture and root regression checks. | Partial: R1 records 416 native parity instances and 259 controls. Current v15 local gates and four compiled mutants pass; its fresh native handoff/parity/refusal gate is pending approval. Broader qualification remains open |
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
FP-control, NOP, data-path-join and mandatory-count admission work. At that stop,
REP remained refused; its independent numeric oracle was not production admission. The
separately pinned advanced producer and versioned guard/target/refinement
integration are saved with a failing native matrix and incomplete count replay,
compatibility and mutation gates. Earlier ledger statuses are historical stage
exits; none of S1, broader S2–S5 or Q1 is closed by this stopped snapshot.

### Resume: guard replay and composed fixture

2026-10-23: resumed from `3024fcb`. The empty guard report is reproducible with
the packaged producer and CLD, without the source flag extension or native core.
It is a `guard-closure-round-limit` stop: combined discovery advances the epoch
on source/control changes, exceeding the default eight epochs. The advanced
table fixture now explicitly selects 64 epochs and requires its MOVAPS guard.
A separate actual-BAP/LLVM test checks both the default stopped result and the
selected-budget aligned result. Production defaults and expected targets stay
unchanged; empty reports remain valid stopped products.

Saved guard replay now recovers opcode identity for the eighteen byte-exact
mandatory-count forms already admitted under v10/v11. Previously its generic
`typed-transfer` opcode caused a count/bytes mismatch and lost RSP facts. Both
transfer derivation and coverage replay use the same scoped byte matcher. A
portable regression checks all eighteen forms, old-profile refusal and hostile
saved bytes; a fresh-BIL test checks their actual lifts and saved guard replay.
An additional native integration test composes counts, CLC, MOVAPS and a rooted
table with independent target expectations, full-state parity and saved replay;
all eighteen forms now pass that actual native gate. A further downstream bug
was exposed by it: composition's original-control replay used the default
projection. Advanced sources now retain their declared profile there; legacy
sources keep the previous path. The separate portable composition regression
covers the same eighteen byte forms and altered-prefix/old-profile refusals.

The unused default-profile wrapper is now test-only, and two test mutations
replace boxed contents without allocating replacement boxes. Two stale guard
mutation selectors are repaired, and count-replay/composition-profile mutants
are added. All eight selectors are unique. Their optimized Rust campaigns
detect eight mutants through nine named assertion rejections after passing
controls, with independent source/build trees, restored source and unchanged
observers. Seven qualify before the final observer-diagnostic refinement;
the composition-profile case qualifies after a standard-assertion rerun.
Production/checker sources remain frozen across these runs. The initial custom
panic message, startup failures and interrupted serial attempt are uncredited.

The local Cargo cache is `target/mbt-cargo-home`; the lockfile records the
current sibling MirrorRust package version `0.1.0` in place of stale `1.0.0`.
Packaged BAP loading was restored with libtinfo5. The exact LLVM 20.1.2 library
and its libxml2 ABI dependency were extracted into ignored local work; no newer
LLVM version was substituted. Fresh numeric oracles pass 4,020 count and 720
repeated-string comparisons. REP production admission remains refused under
these v10/v11 profiles; the later plain v12 continuation is separate.

The original SDK was located on `win10` at
`/home/jlc/ariadne-p4-20261010/work/Repos/Ariadne/target/bap-core-sdk`.
Its lock and both public dependency archive hashes match the current pins.
Direct execution in the outer WSL distribution fails its tool/libc checks.
The approved continuation instead reuses the original compatible isolated
userspace; the unchanged SDK inventory and project/term/storage smoke pass.
The current source/test bundle was transferred with approval and mounted
read-only. Git history, generated evidence and the real Windows archive were
excluded. Build, replay and mutation outputs remain disposable.

Two independent advanced producer builds are byte-identical under that SDK.
Their identity differs from the saved advanced pin, so only the advanced
runtime lock is explicitly updated to the reproduced manifest/executable.
The Basic v9 builder and lock remain immutable. Its exact old runtime is not
available; a mismatching fresh Basic build is rejected, and positive v9
producer compatibility under the historical pin remains unexercised. The
candidate check below separately exercises the available Basic build.

After source freeze and helper rebuild, all eight advanced tests pass: the
eighteen count compositions and seven remaining guard/target/writer/codec
tests. Legacy v7/v8 capture controls pass with one detected native dependency
mutant. Current proof compatibility passes 88 controls and nine compiled
checker mutants, with actual reader-produced v8 load/terminal wires and
saved legacy/current proof units. The retired legacy driver's evidence path
is replaced by the maintained small byte/BIL fixture and checked by policy.

Generated native replay matches 168 core and 162 finite-stateflow observations;
both wrong-digest controls reject with zero dispatch. Predicate oracles pass,
and restored installed model-tool assets permit Apalache typechecking and all
58 TLC configurations to pass safety/expected outcomes/fair termination. No
TLA+ model body was changed. This does not establish universal refinement or
ISA correctness. Inventory legality gaps, general REP consumer contracts,
broader S2–S5, U5, real-capture/timing/release qualification and Q1 remain open.

Final local validation passes 424 default Rust tests (145 ignored), 64 core-only
tests (22 ignored), strict Clippy, 46 BAP Python controls, 251 general Python
controls, layout and navigation. Required root format/default/core-only/Clippy
checks pass under the existing read-only MirrorRust snapshot workflow; only
the copied `tests/protocol.rs` is formatted. The sibling checkout stays
unchanged. Direct root formatting against that original sibling still reports
its existing style differences. Core-only normal dependencies stay empty.
Fresh count effects, eighteen actual guard replays and the two-budget packaged
table control retain their separate exercised scopes.

### Current Basic v9 candidate check

2026-10-23, source `faf75f7`: the follow-up tests the available Basic runtime
under the v9 contract. The [canonical candidate contract](../../docs/Ariadne/bap-analysis-core-design.md#current-basic-v9-candidate-compatibility)
records its manifest/executable identities and the
[checkpoint](../../CHECKPOINTS.md#2026-10-23--current-basic-v9-candidate-compatibility-checked)
records the result.

1. Verify the current shared inputs: 647 source/test/native and Cargo files
   match the checkout. The unrelated real Windows archive is not transferred.
2. Run the three existing native v9 tests against each available bundle with
   the unchanged Basic lock. Both Basic and advanced bundles are rejected at
   the manifest hash check before semantic dispatch, as required.
3. Compare their actual typed BIL for F5/F8/F9/FD on Windows and Linux. All eight
   cases agree apart from the separately bound build IDs.
4. Copy the current sources to disposable work, change only the copied Basic
   pin to the genuine current Basic manifest/executable, and run
   `bap::source_extension::tests::native_` with default features and
   `--ignored --test-threads=1`. All three tests pass: four flags/unchanged corpus,
   forbidden composed modes/tamper poisoning, and synthetic Windows/Linux
   capture/native parity with opaque-site and target-resolution refusal checks.
5. Restore the copied lock and verify the original source identity, production
   lock and candidate artifacts are unchanged. Reports, logs and copied trees
   remain ignored run products.

This establishes the candidate's tested Basic v9 behavior under its own pin.
It does not adopt that pin or reproduce the historical artifact. A separate
explicit Basic pin review is the adoption step; historical identity still needs
the original artifact or a matching build. Wider S2–S5/U5/Q1 and real-capture,
timing and release gates remain open.

### Resume: plain REP and coverage accounting

2026-10-23, baseline `e44ce2b`: process the remaining REP/full AMD64 item with
the [canonical v12/accounting contract](../../docs/Ariadne/bap-analysis-core-design.md#plain-repeated-string-profile-and-coverage-accounting).
This stage is partial S4/Q0 work. It does not close S1, wider S2–S5 or Q1.

1. Add explicit `Config::with_repeated_strings(dir)` and environment mode
   `repeated-strings`, binding the unchanged pinned advanced flag bundle to
   plain `bap-bit-provenance-v12`. Preserve packaged/default, Basic v9 and
   advanced v10/v11 interpretations and pins.
2. Admit only `F3 A4`, `F3 AA` and `F3 A6` with exactly one top-level typed
   loop, preserved definite virtual bindings and no external control, RIP
   writes, special semantics, nested loops or extra loops. Retain zero-iteration
   origins and possible body writes through a dependency fixed point. Weak
   `memory:any` writes never kill all old memory origins. Keep 262,144 work
   steps and 4,096 fixed-point rounds as explicit `Resource` failure limits.
3. Mark loop memory addresses unknown and iteration-dependent; havoc target
   and native-transfer architectural/virtual outputs written by loops. Refuse
   guard, target and memory-refinement proof modes before helper dispatch,
   including zero-root requests. Native transports and direct proof entry
   points recognize the exact colon-delimited v12 token from overall
   `semantic_profile` or site projection, including empty/all-null site
   collections, across all nine proof transports. Recovery separately refuses
   empty domains. Plain saved captures trust validated
   reader-supplied normalized effects bound to v12 captured bytes, profile and
   query evidence. They do not independently replay raw REP BIL/effect
   semantics; the capture trust boundary is unchanged. This introduces no hardware
   partial-fault or general REP acceptance.
4. Add [coverage accounting](../../tools/amd64_coverage.py) with symbolic-form,
   manual-row, transcription-gap and exact-byte domains kept separate.
   Candidate associations bind exact form/case/bytes and input identities but
   establish no authoritative legality or complete template expansion. Rebind
   optional surveys to current source/native observations and recompute their
   classifications. Strict mode writes a deterministic worklist and exits
   nonzero for any unmet full-coverage gate.

Completed finite validation at this record:

- Eight portable projection tests, six consumer tests and the early proof-mode
  refusal test pass. Actual BIL covers six Windows/Linux form/target pairs,
  54 altered-prefix controls and refusal under v10/v11.
- Before final native identity-boundary hardening, three plain REP native
  integration tests pass, including 24 Windows/Linux sequences, full
  native/Rust state equality and hostile saved-capture controls; all eight
  existing advanced regressions pass at that source boundary. The final rebuilt
  helper passes 41 compiled direct controls and 54 framed-dispatch controls,
  95 total, superseding the earlier nine-control run. Its three plain REP native
  tests and one positive old-advanced composition/tampering regression also
  pass. This is a compatibility recheck, not a ninth distinct advanced test.
  All 14 source hashes bound by the final native helper match the checkout.
- Fresh numeric equations pass 720 comparisons. Current root checks pass 439
  default Rust tests (149 ignored), 64 core-only tests (22 ignored), strict
  all-feature/all-target Clippy, formatting and Rust layout (213 sources).
  All four optimized Rust mutants are detected by exact named assertions after
  passing controls, with selected observers/SUT sources restored and campaign
  source stability verified. They completed before final native proof-policy
  hardening; their Rust SUT and selected observers remain byte-identical. The
  later native policy is checked separately by the 95 controls, three plain REP
  tests and positive old-advanced proof recheck against the final helper.
- The completed 171-case v12 native survey records 57 supported projections,
  eight conservative unknowns, 75 missing producer lifts, 28 unsupported
  control/semantics, two encoding disagreements and one query error. All nine
  independent expectations match. PUSHFQ (`9C`) reproduces `BIL AST budget
  exceeded` with direct fresh lifting. The initial all-decoder-EOF local attempt
  lacked the exact library path and earns no semantic credit; the completed
  rerun uses unchanged LLVM 20.1.2 and its matching libxml2 library.
- Fifteen new accounting controls and 31 existing AMD64 inventory/manual/survey
  controls pass. Actual pinned XED accounting reports 10,994 templates,
  10,569 long-mode candidates and 425 exclusions, with all candidates lacking
  authoritative form-to-byte bindings. Fresh byte accounting reports 57
  supported, eight opaque and 106 missing cases; strict mode returns 2 as
  intended. Pinned manual-denominator fields retain 4,118 rows and 2,657 gaps
  even when accepted manual products are omitted.
- The three public pinned PDFs reproduce outline/content/counts and retain
  2,657 gaps. `pdftotext` 26.01 changes the full-layout hash, so unchanged
  strict manual pins reject regenerated outputs. No hash or source pin is
  relaxed. Official-download byte identity for Volumes 4/5, source-row legality
  and exact concrete-domain coverage remain unresolved.

The first default-suite attempt found an old negative test using newly assigned
v12 as an unknown profile; that control now uses unassigned sentinel v999. The
existing guard deadline passes its serial rerun under contention. The initial
mutation attempt was interrupted to correct that fixture and receives no
completed-campaign credit; the later completed four-mutant campaign supplies
its own result. Neither failed default attempt is credited as a
passing gate; the complete final suite supplies its own result. All reports,
transcripts, copied sources, raw
logs and generated build products remain ignored disposable work. Full AMD64
support remains false until every legal form and its exercised concrete domain
satisfy the completion contract; finite REP success supplies no overall coverage
percentage or full acceptance.

### Coverage completion design stages

2026-10-23: the [canonical completion design](../../docs/Ariadne/amd64-coverage-design.md#9-delivery-sequence-and-stop-rules)
specifies the remaining architecture. These execution slices of S1–S5/Q0–Q1
now include the finite C1–C4 work and completed R1 tuple gate recorded below;
C1–C4 retain their broader open exits.
The design's initial publication supplied no runtime/source/encoding qualification;
its later executable findings have their own scopes. Windows unwind stages
remain separate under their existing owner.

| Slice | Program stage | Concrete exit | Status |
| --- | --- | --- | --- |
| C1 — Source scope | S1 | Freeze vendor/publication/extension and mode scope; resolve official Vol4/5 identities or explicitly adopt a reviewed replacement corpus/toolchain. | Partial: candidate v2 reproduces all five volumes; fresh official V1–3 bytes match. V4/5 HTTP 404, reviewed adoption and extension/global-rule audits remain open. |
| C2 — Transcription | S1 | Account for selected global rules/appendices and every source region; give each old gap a source-backed disposition with geometry/continuation/footnote ownership. | Historical backlog accounted: 2,657 source-backed dispositions, zero unassigned and seven explicit source-conflict records. All 4,128 pages/11 required region clauses accounted. C2 remains partial for source conflicts, diagram constraints, global rules, footnotes and continuation ownership. |
| C3 — Legal domains | S1 | Reviewed legal-form grammar and bidirectional manual/XED dispositions, including AMD forms absent from XED and feature-dependent aliases. | Partial: v3 memory-REP domain enumerates 56 canonical AMD points from 516 source anchors. Vendor denominator, XED reconciliation and wider grammar remain open. |
| C4 — Binding checker | S1/Q0 | Separate authoritative schema; checked domain totality, overlaps and dispatch; solver unknowns and unbound required domains remain open. | Partial: v3 validates 111 fresh profile observations; supported counts are 3/24/28/56 for v12–v15. v15 completes this finite plain-dependency domain; all 10,569 full symbolic-domain bindings remain open. |
| R1 — Memory REP | S2/S4 | Review recipes and fresh BIL for the remaining default-address memory-string tuples; qualify a successor profile while freezing v12. The 28-tuple planning matrix is not an encoding denominator. | Complete for the finite 28-tuple scope: v13/v14 producer/oracle/transport gates, 416 native parity instances, 259 native refusal controls and compatibility regressions pass. Full encoding, fault and proof-consumer coverage remain separate. |
| R2 — Address/prefix variants | S3/S4 | Source-backed address-size, segment and prefix domains with zero-count/upper-lane/width/wrap controls. | Partial implementation: AMD v15 covers 28 default and 28 canonical address-32 tuples; 178,080 oracle comparisons and 448 local capture instances pass. New native qualification awaits source-handoff approval; segment/redundant/reordered prefix domains remain open. |
| R3 — Proof consumers | S4/Q0 | Versioned guard/target/refinement/composition capabilities, outcome premises, direct/native replay and refusal controls for empty/all-null domains. | Proposed; open |
| R4 — I/O and faults | S3/S5 | Explicit external I/O state, privilege and partial-completion/restart contracts with independent controls; no normal-only oracle substitution. | Proposed; open |
| A1 — Architecture families | S2–S5 | Close producer/transport/state/projection/control/consumer gaps by legal-form domain, with implementation rules and independently exercised partitions. | Proposed; open |
| Q1 — Scoped full coverage | Q1 | Required source/domain, implementation, consumer and current validation obligations all close for the frozen scope; proof/environmental limits remain stated. | Pending |

Continue the remaining C1/C2 source audit and the pending R2 native gate. Keep missing legal
authority distinct from a missing producer lift or an unavailable test runtime.
Do not enable generic F2/F3/While admission or populate mnemonic-only bindings
as a substitute for these exits. Source/tool migrations retain old locks and
receive explicit versioned review; generated transcriptions and run products
stay outside maintained source.


### Source and domain execution: C1–C4

2026-10-23: this executes the [canonical source/domain design](../../docs/Ariadne/amd64-coverage-design.md#101-source-corpus-execution-c1)
while preserving v1 source locks and candidate accounting. Generated PDFs,
transcriptions, observations and reports remain ignored run products.

1. **C1 candidate source corpus.** Freeze candidate AMD long-64 application and
   privileged/system scope with all five APM volumes and five architectural
   subsets. The new source-corpus tool pins publication/PDF identities,
   extractor sources, `pdftotext` 26.01.0, MuPDF 1.27.0, Python 3.14.4,
   89 runtime-library identities, options, locale and schemas. Fresh publisher
   V1/V2/V3 downloads match exact existing pins. Indexed official V4 r3.26 and
   V5 r3.16 content endpoints return HTTP 404; archive-byte equivalence remains
   unverified. Fresh reproduction/check covers all five volumes. Fourteen
   controls pass. Scope/extension review, supplementary publications, global
   rules and versioned migration review remain open; candidate adoption is
   never inferred from equal normalized hashes or a passing products check.
2. **C2 geometry and source ownership.** The first 2026-10-23 pass gave
   1,726 dispositions/931 unresolved; the next added 350. The historical-gap
   completion pass adds the remaining 581: 145 Vol3, 269 Vol4 and 167 Vol5.
   Fresh extraction/check preserves every original ID, ordinal, object and
   source address, with all earlier dispositions unchanged. Current totals
   are 159/1,987/511 dispositions and zero unassigned records. Seven Vol4
   records explicitly retain source conflicts; no intended encoding correction
   is invented. Grouped CMOV/SETcc cells, literal fragments, heading overlays,
   word-box splitting and repeated-line assignments have narrowly bounded
   rules. Material records retain unparsed constraints. Actual fixtures and
   adversarial controls cover all these rules, including omitted/duplicated
   source occurrences and foreign column material. The generic parser's
   refusal controls remain separately exercised.
   Geometry and region products bind the nine-module extraction dependency
   closure; editing a recovery helper invalidates both finite binding registries.
   All five volumes' 4,128 pages and eleven required region clauses pass
   region enumeration/checking. Complete constraint parsing, source conflicts,
   footnotes and all 33 cross-page continuation candidates remain open.
   [Canonical C2 findings](../../docs/Ariadne/amd64-coverage-design.md#102-geometry-and-source-region-execution-c2)
   distinguish `oldGapBacklogClosed` from the still-false C2/source-completeness
   gates. Continue those wider audits, not a deleted or renumbered backlog.
3. **C3/C4 finite legal-domain pilot.** Versioned legal-form/profile-binding
   fixtures enumerate 24 canonical F3 MOVS/STOS/CMPS byte/environment points,
   with three supported and 21 explicit unsupported points for v12 plain
   dependencies. Twenty-four controls check holes, domain narrowing, overlaps,
   unknown grammar/budgets, malformed provenance and stale bindings. Initial
   source-bound producer observations pass 720 independent comparisons and
   the exact-lift Rust admission observer. After source freeze, the final
   historical-gap campaign reseals thirty-nine implementation identities, obtains fresh BIL and
   reruns the oracle/Rust observer; `check --require-bindings` passes. Further
   bound source changes require that fresh campaign again. Full
   source grammar, bidirectional XED reconciliation and implementation remain
   open, and the pilot establishes no vendor-wide coverage percentage.

The historical-gap continuation passes 61 geometry controls, thirteen original
extraction controls, 145 BAP Python tests and 328 tooling tests. Both finite
binding campaigns are rerun with actual BAP and Rust observers after source
freeze: v2 binds 39 implementation sources and v3 binds 61, including all three
volume helpers. The v3 domain remains 56 points/111 profile observations.
The current reading view is refreshed; the preceding 581-gap view is preserved
as a distinct archive version. Record this scoped result in `CHECKPOINTS.md`
and commit/push the continuation under the user's publication instruction.

Run a fresh `tools/amd64_source_corpus.py reproduce` campaign before
`check-products --require-all`; checking a stored product set does not rerun
PDF extraction. Geometry and source-region checks reconstruct their supplied
inputs and retain that fresh extraction premise. Consult the canonical dated
findings for the exact scope and limits. Continue unresolved source audits
independently of REP implementation; do not delete old obligations or relax
source/tool identity checks to produce a passing gate.

### Memory REP execution: R1

2026-10-23: the [successor profile contract](../../docs/Ariadne/amd64-coverage-design.md#104-default-address-memory-rep-execution-r1)
records the 24-form v13 and 28-form v14 default-address scopes. v12 stays frozen.
Two independent LODS builds match; the separate new lock binds actual BAP source
and runtime identity. Source gates pass 4 new typed forms, 38 negative prefix
neighbors, 4 trailing sequences and 10 unchanged baseline observations.
Independent normal-completion equations pass 43,200 comparisons for 24 original
producer forms and 14,400 for 4 source-built LODS forms. Five source controls,
twelve portable transport controls and one actual 4-form/two-target Rust
projection test pass. The user approved the prepared source-only transfer and
the fresh native campaign below closes R1's finite gate. Wider proof-consumer
capabilities remain with R3. No commit or push is requested for this execution.

The local captured-input matrices pass 192 v13 and 224 v14 instances across
OS/count/DF combinations, checking roots/seeds, normalized effects, weak writes,
memory gaps, origins and investigation binding. Final serial default tests pass
457/155 ignored, core-only 64/22, with strict Clippy, format, layout and links.
An initial concurrent run hit an existing guard deadline and receives no credit.
All four optimized compiled loop mutants are detected by named assertions after
passing unchanged controls, with current source identities, isolated builds,
restored SUTs and unchanged observers verified. All 81 BAP Python controls and
304 tooling controls also pass. The separately exercised native campaign passes
all 416 parity instances and 259 direct/protocol refusal controls after a fresh
source-verified build. The v12 saved-capture and old advanced-composition
positive/tampering regressions pass with that same helper.

### Address-size assessment: R2

2026-10-23: the [canonical address-size findings](../../docs/Ariadne/amd64-coverage-design.md#105-address-size-assessment-r2)
record 504 fresh BAP/LLVM observations. All 28 canonical address-32 forms agree
on decoded extent; only four MOVS lifts are nonempty, and those use incorrect
64-bit count/pointers. Thirty-two bounded counterexamples cover low-32 zero
count, high pointer bits and both wrap directions. Three equation controls pass.
Seven hostile prefix families remain raw observations, not admissions. R2 needs
a separately versioned BAP source correction; current profiles stay frozen.

<a id="native-memory-rep-qualification-pending-source-approval"></a>

### Native memory REP qualification

**Completed finite gate, 2026-10-23.** The user explicitly approved the prepared
source-only transfer and native qualification, resolving the earlier automatic
approval-review rejection. The isolated destination is
`/home/jlc/ariadne-rep-20261023`; the payload contains no captures, Git history
or historical evidence. All results below are scoped to the verified sources
and finite fixtures; C1–C4, R2–R4, A1 and Q1 retain their separate exits.

The ordered gates executed were:

1. Verified `target/rep-native-handoff/memory-policy.tar.gz` SHA256
   `6a78e471959a549506ede02e0d47e9e5e0a488fb81f947727cd1933763ff1e0c`
   and every current file in `memory-policy-manifest.json`. The archive contains
   25 current native source/control files. All thirteen existing bound
   Rust/model/legacy inputs also matched before installation.
2. Transferred and unpacked the archive into the isolated `inputs/Ariadne`.
   The original SDK and producer pins remain unchanged. `run.sh` supplies the
   compatible environment; SDK inventory verification passes.
3. Built and checked the fresh native helper inside that launcher:

   ```sh
   python3 native/bap-core/build.py --output target/rep-core-memory-current
   python3 tests/bap/rep_transfer_native_controls.py --native-dir target/rep-core-memory-current --output target/rep-memory-native-controls
   ```

   All 97 direct and 162 framed controls pass, with current source, runner,
   driver, helper and manifest hashes verified. Outputs remain ignored run
   products. Future campaigns require fresh output directories.
4. Retrieved the helper, manifest and bounded control report. All fourteen
   native source identities, the SDK lock and seventeen SDK/compiler/model/
   engine fields match the checkout and pinned SDK. This explicit source audit
   supplements runtime manifest/ready consistency and the runner's four-source
   policy check. The helper SHA256 is
   `b01c3bf697eb53c355c88716b4ee41a0010809bd71c501fbb3ac9be86698a7bf`.
5. Selected the new helper with `ARIADNE_BAP_CORE_DIR`, the advanced flag
   bundle with `ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION`, and the independently
   pinned LODS bundle with `ARIADNE_BAP_LODS_SOURCE_EXTENSION`. Run
   `cargo test --offline --locked --lib memory_rep_recipe_matrix_preserves_roots_effects_and_origins -- --ignored --test-threads=1`.
   This common substring selects both `native_memory_rep_recipe_matrix` and
   `native_lods_memory_rep_recipe_matrix`; the former prefix alone misses v14.
   Both tests pass: all 192 v13 and 224 v14 tuple instances across sixteen
   synthetic capture queries have complete Rust/native state equality and
   every existing effects/origin/query assertion. The v12 saved-capture and
   advanced-composition positive/tampering regressions also pass.
6. Rechecked source/helper identities after execution and updated the canonical
   design, checkpoint and HTML archive. This completes finite R1, without
   closing source/full-domain, address-size, fault or proof-consumer coverage.

### AMD address-size implementation and bindings: R2 / C3–C4

2026-10-23: the [v15 contract](../../docs/Ariadne/amd64-coverage-design.md#107-amd-address-size-rep-implementation-r2)
and [expanded bindings](../../docs/Ariadne/amd64-coverage-design.md#108-expanded-source-to-consumer-bindings-c3c4)
record the next finite slice. R1's prior native results retain their source
boundary; the current v15 native policy needs the fresh gate below.

- Two independent AMD producer builds match manifest
  `815fc8842899d05f6db51aa53cf21b4c82fd50fdae42200b43df4e6735cf48d4`
  and executable `e834c5e9e25a4b2f93de448a01326482493a93430ea1ce43428289b2685c727e`.
  The new pin covers four default LODS and 28 canonical address-32 sequences.
  Four incorrect nonempty MOVS lifts are replaced under explicit selection;
  all 28 default-address behaviors are preserved.
- AMD Ryzen 9 7950X and Intel Core 5 220H probes expose different zero-count
  upper-lane behavior. v15 binds an AMD premise and records it per address-32
  site; an AMD64 target label does not establish CPU vendor. Both hosts confirm
  contiguous element access across 4 GiB followed by 32-bit index wrapping.
- The independent oracle passes 178,080 comparisons and 15 runtime refusals;
  fifteen portable oracle controls and fifteen transport tests pass. The latter
  include 64 actual form/target cases. All 448 local capture instances pass with
  high count/index bits, exact premises, effects, origins, roots and memory gaps.
- The separate v3 registry has 56 points and 516 source anchors. Fresh producer
  queries and Rust admission validate 111 profile observations, with supported
  counts 3/24/28/56 for v12–v15. All 47 checker controls and the refreshed v2
  campaign pass. All 10,569 candidate full-domain bindings remain open.
- Current root gates pass 472 default Rust tests/159 ignored, 64 core-only/22
  ignored, Clippy, format, layout, 107 BAP Python and 327 tooling controls.
  Four optimized loop mutants are detected after passing unchanged controls;
  source restoration, observer identity and the frozen source inventory verify.

### Native AMD address-size qualification: pending approval

Automatic approval review rejected the changed v15 source/control payload,
stating that prior approval covered the earlier handoff. Specific approval has
been requested for the same isolated `win10` destination and native tests.
Local qualification above is complete; the native gates remain unexercised.

1. After approval, verify `target/rep-native-handoff/address-policy.tar.gz`
   SHA256 `ac080543a2951b6606e87d63d3085f6f5df9d2c829553182443b970cfdae2440`
   and `address-policy-manifest.json` against all 25 current files. Transfer
   this source-only payload to `/home/jlc/ariadne-rep-20261023` and verify/install
   with `verify_install_address.py`; no captures or history are included.
2. Through the compatible `run.sh`, run
   `python3 native/bap-core/build.py --output target/rep-core-address-current`,
   then `python3 tests/bap/rep_transfer_native_controls.py --native-dir target/rep-core-address-current --output target/rep-address-native-controls`.
   Require 125 direct plus 216 framed controls, 341 total.
3. Retrieve the new helper, manifest and report into ignored work. Audit all
   fourteen native sources, SDK lock and seventeen SDK/compiler/model/engine
   fields against current inputs; manifest/ready consistency alone is insufficient.
4. Select that helper with `ARIADNE_BAP_CORE_DIR`, the advanced flag bundle and
   `ARIADNE_BAP_REP_ADDRESS_SOURCE_EXTENSION=target/rep-address-build-a01/runtime`.
   With pinned BAP/LLVM dependencies, run
   `cargo test --offline --locked --lib native_amd_address_memory_rep_recipe_matrix_preserves_roots_effects_and_origins -- --ignored --test-threads=1`.
   Require 448 native/Rust parity instances and recheck v12 saved-capture plus
   old advanced-composition positive/tampering compatibility with the same helper.
5. Verify final source/artifact stability and update the canonical/checkpoint/
   archive results. Wider prefix/segment and full AMD64 gates remain separate.
