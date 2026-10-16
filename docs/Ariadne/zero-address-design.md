# Zero-address assessment design

## Context and follow-up

**Status.** Implemented for the finite Windows AMD64 scalar-MOV profile. The
2026-10-03 working tree and design baseline `c9eb4c5` are historical checkpoints.
Historical source/fixture qualification passes; the retained
native refresh qualifies both source/fixture and
controlled Windows tiers under its pinned dependency snapshot. Scope is
Windows AMD64 scalar MOV access violations; Linux and other hypotheses are deferred.

**Why this document exists.** The [first investigation question](investigation-design.md)
explains possible producers but does not evaluate a fault-time address. A useful
next question is whether the selected access starts at zero. Answering it needs
valid captured operands, not guesses from producer alternatives or missing
registers.

**What this document establishes.** One precise hypothesis, a bounded admission
profile, evidence requirements, allowed conclusions and independent acceptance
cases. It explains how the question can use the existing analysis without
reconstructing an executed path or implementing another ISA model.

**Where to go next.**

- [Native-default qualification plan](../../.agents/plans/completed/i5a-native-qualification.md)
  refreshes phase measurements, backend identities and controlled Windows
  acceptance after Stage 2 adoption.
- [I5a implementation plan](../../.agents/plans/completed/i5a-zero-address.md) sequences admission
  review, exception evidence, assessment, reports and qualification for this
  Windows zero-address question and records its delivery status.
- [Investigation stage plan, I5a](../../.agents/plans/investigation-layer.md#i5a--zero-address-consistency)
  places this design after the delivered first question and keeps active Windows
  I4 qualification separate.
- [Input module](file-reader-design.md#public-interface) describes the snapshot reader that retains
  the exception evidence.
- [Current investigation contracts](investigation-design.md) define the
  existing query identity, address expressions and conservative claim rules.
- [Semantic assurance](semantic-assurance.md) retains BAP as a trusted semantic
  provider; this design does not revive independent instruction-step proofs.

**What remains unresolved.** The native I5a successor
qualifies both controlled Windows captures under the unchanged criteria; the
earlier demo timing miss remains historical. The finite admitted forms do not
establish whole-ISA coverage. The [active I4 replacement](workload-performance-design.md#windows-investigation-replacement)
meets its fixed CLI budget in the later [performance qualification](workload-performance-design.md#native-investigation-qualification).
Broader hypotheses, executed history and root cause remain outside this profile.

The [documentation map](../documentation-map.md) is optional navigation.

## Selected question and claim

For one selected captured memory access, assess:

> Under the admitted exception-context and instruction-semantics premises, does
> this operand begin an access at virtual address zero?

The hypothesis is **effective address equals zero**, not “a null pointer caused
the crash.” For `[RAX + 8]` with observed `RAX = 0`, the effective address is eight:
that refutes this exact hypothesis but does not refute a null-derived access.
Conversely, modular arithmetic can produce zero from nonzero inputs, so a zero
result does not identify a null base or its origin.

The output explains the expression, observations used, computed value and
premises. Existing possible-producer explanations remain separate: a fault-time
register observation may be used at the selected exception instruction only,
never applied backward to earlier producers or branch decisions.

Windows is the first profile because it gives this design an explicit exception
parameter interpretation to qualify. This is a scope choice, not evidence that
the missing original Windows capture is now available. The existing Linux
investigation remains supported; interpreting its signal/context records for
this new question requires a separate admission profile and tests.

## Historical baseline and implemented extension

The following table describes the historical pre-implementation design baseline;
its missing fields were subsequently supplied by the reader-owned extension.

| Source fact at the design baseline | Consequence |
| --- | --- |
| [AddressExpression](../../src/effects/address.rs) represents modular 64-bit affine arithmetic over before-instruction GPR values. | Reuse the expression and its semantic identity; no assembly-text inference or second symbolic solver. |
| [BIL address extraction](../../src/bap/address.rs) resolves supported temporaries and RIP-relative constants at the captured VA. | Evaluate the retained expression directly; do not add instruction length or substitute a different RIP again. |
| [ExceptionInfo](../../src/input/mod.rs) stores thread ID, code, `reported_address` and a register map. | It is insufficient for I5a: preserve parameter count/values, flags, record/context provenance and validity evidence. |
| [Reader normalization](../../src/input/minidump.rs) copies `reported_address` from `exception_record.exception_address`. | This field is not a normalized inaccessible-data address. Its name or a zero value cannot establish the selected hypothesis. |
| The register reader honors AMD64 context validity groups rather than trusting every field in the raw struct. | Preserve that behavior and the evidence for each retained register. A raw zero with its validity group absent is missing data. |
| [Stage B fixtures](../../tests/input/fixtures/make_stage_b.py) set the CONTROL group, omit INTEGER validity and exception parameters, and store zero in the exception-address field. | Keep these fixtures unchanged as first-question regressions. They must yield unknown for I5a; add separate fixtures with the required evidence. |

The [reader-owned extension](../../src/input/fault_context.rs) now retains the
missing exception fields and provenance alongside the legacy metadata. The
[source review](#source-and-finite-admission-review) records its offsets/validity interpretation;
the old fixtures remain unknown-result regressions.

For Windows access violations, the exception record distinguishes its exception
location from the parameters describing operation kind and inaccessible data.
Parameter count determines which array entries are defined.
[Microsoft MINIDUMP_EXCEPTION reference](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception/).

The exception stream associates a thread identifier with a context descriptor;
the minidump writer's exception input describes the processor context at the
exception. Use that selected exception context, not a convenient thread-list
context or fallback register map.
[Exception stream](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_stream),
[writer exception information](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_exception_information).

These records can also be supplied for software-generated exceptions. Agreement
between fields does not independently prove hardware fault origin. Treat precise
fault-context interpretation as an explicit premise, never infer it from a
reserved flag or from the exception code alone.
[Microsoft EXCEPTION_RECORD reference](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_record).

## Evidence and admission

The reader retains exception/descriptor fields, defined parameters, context flags
and valid GPR/RIP/RFLAGS observations with artifact-relative offsets, lengths,
raw field bytes and SHA-256 identities. Record/context extents have separate
digests. RIP/RSP/RFLAGS require CONTROL; other GPRs require INTEGER. Thread-list
registers are never a fallback. These are captured observations, not proof of
hardware exception origin or temporal coherence.

Implemented profile ID: `windows-amd64-av-scalar-mov-v1`. A definite assessment needs
every applicable item below. Failure of an evidence prerequisite means unknown;
malformed structures and cross-query/snapshot substitutions remain errors.

1. The immutable snapshot is Windows AMD64. The selected exception stream and
   its context have unambiguous bounded source spans, matching artifact identity
   and one exception-thread association. Do not merge thread-list registers.
2. The exception code is access violation (`0xc0000005`), at least two parameters
   are defined, and the operation is read or write. Execute, in-page-error,
   breakpoint, chained/nested or unsupported exception profiles are out of scope.
   Exception flags must satisfy the supported non-chained profile.
3. Valid exception-context RIP equals the question's instruction VA, and the
   Windows exception-location field agrees. A disagreement is inconsistent
   evidence, not a refutation of the address hypothesis.
4. The instruction is reached/decoded in the bound completed query and its
   consumed captured bytes are unambiguous. Asking this question adds no root,
   reads no companion bytes and creates no alternate instruction stream.
5. BAP has admitted the site, and its address evidence contains one unconditional
   memory access with a supported 64-bit affine expression and no address gaps.
   The selected access's load/store role and bit width must match the reviewed
   instruction form; disagreement remains `form-access-disagreement`.
   The reviewed finite form set is `MOV32rm`, `MOV64rm`, `MOV32mr`, `MOV64mr`,
   `MOV32mi` and `MOV64mi32`; admission depends on exact-form review,
   prefix guards and independent cases. Names alone are not coverage evidence.
6. Exclude stack/control, string/repeated, atomic/locked, vector, segment-override,
   address-size-override and multiple-access instructions. The profile assumes
   flat 64-bit addressing and the supplied context describes the selected
   instruction before its ordinary memory access. No partial-progress or
   restart-state interpretation is introduced.
7. Every GPR term has a valid complete 64-bit observation from that exception
   context. Preserve register name/value, validity-group evidence and source
   location. A constant expression needs no unused GPRs, but still needs valid
   RIP and context association.
8. Evaluate the normalized expression modulo 2^64. For this first profile, admit
   only a nonwrapping access span wholly below `0x0000800000000000`; other ranges
   remain unknown instead of guessing a canonicality configuration. The reported
   inaccessible-data address must lie in that span, and its read/write kind must
   agree with the selected access. This is a consistency check, not a proof of
   memory permissions, retirement or hardware fault attribution.

The read/write/execute parameter meanings come from the
[Windows exception record contract](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_record).
The narrower instruction/range restrictions above are Ariadne design choices.

Missing data relevant to another predecessor does not automatically block this
numeric question. For example, an opaque earlier call can keep the producer
explanation partial while a valid fault-time register observation supports the
zero-address assessment. Keep the two claims and their premises distinguishable.

## Interface and identity

```text
input::investigation::bind_fault_context(prepared, completed_analyzer)
  -> BoundFaultContext
investigation::assess_zero_address(bound, FaultAddressQuestion, AssessmentLimits)
  -> ZeroAddressAssessment
```

Binding reuses exact prepared/analyzer identity checks. Reader-owned exception
observations are retained separately from the public legacy snapshot metadata;
changing that metadata after capture fails binding. The bound value owns its
analysis/context and exposes no mutation or arbitrary-register-map constructor.
The original analyzer and reports are unchanged by assessment.

Schema: `ariadne.zero-address-assessment/v1`.
Profile: `windows-amd64-av-scalar-mov-v1`.
Scope binds snapshot/artifact/query/request/semantic identity, selected question,
the context digest and profile. Full context evidence must match its digest;
truncated inputs cannot support a definite conclusion.

Raw acquisition, field extraction and normalization stay in `src/input/`;
normalized evidence is also checked by the pure domain validator. The assessment
lives in `src/investigation/` and depends on normalized evidence and root model
types, not the input reader, BAP runtime or renderers. The interface consumes the
completed analysis; it starts no additional CFG/dataflow or path search.

Reported premises include that captured instruction bytes still describe the
exception instruction and that the selected context supplies its pre-access
values. Snapshot hashes and equal PCs do not independently prove temporal
coherence; known conflicting evidence prevents a definite assessment. Preserve
legacy metadata meaning, including `reported_address`.

## Result and limits

| Conclusion | Meaning |
| --- | --- |
| `consistent_with_evidence` | All premises/admission checks hold and the access starts at zero. |
| `refuted_under_premises` | All premises/admission checks hold and its start is nonzero. This does not rule out a zero base plus displacement. |
| `unknown` | Missing, unsupported, conflicting or budget-omitted evidence prevents the assessment. |

The result retains observations, instruction/address evidence, used register
names, the computed candidate and reported data address when justified, typed
claims, explicit premises and per-gap evidence requirements. A computed candidate
may remain diagnostic when subsequent span/data-address consistency fails; the
conclusion is still unknown. Unadmitted context/form evidence produces no numeric
fact. No result asserts null-pointer causation, lifetime or a predecessor path.

Default limits are 32 evidence records and 32 claims. Source extents, individual
field observations and the selected instruction count as evidence records. Zero
and exhausted limits produce unknown/truncated answers with valid references.
Question-site/access-index errors remain errors independently of budgets.

Strict decoding rejects duplicate/unknown fields, noncanonical values, invalid
source spans/bytes/digests, wrong identities, dangling or altered claim records,
missing premises and conclusions inconsistent with recomputed admission and
arithmetic. This checks internal evidence consistency, not authenticity of an
arbitrary externally supplied minidump. The first explanation's v1 schema remains
independent.

Evaluation uses the existing maximum of 16 affine terms. No result applies
fault-time observations backward to producers or branch choices. The separate
conclusion values do not extend `Classification` in
`ariadne.fault-address-explanation/v1`: arithmetic and conclusions remain derived
under premises, while captured fields are observations.

## CLI and publication

```sh
target/release/ariadne-minidump tests/input/fixtures/i5a/zero-store.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 401000 \
  --assess-zero-address 401000 --memory-access 0 \
  --assessment-only --format json
```

For a bundle, replace `--assessment-only --format json` with
`--output-dir NEW_DIR`. The original three reports and
`zero-address-assessment.{txt,json,dot}` are staged and published together.
Existing output paths are rejected. Unknown is a valid published answer;
invalid options, binding, schema or infrastructure failures produce no complete
bundle. The question adds a seed, never a discovery root.

Assessment and explanation question flags are mutually exclusive in this first
CLI delivery. Assessment cannot be combined with stateflow. Assessment-only mode
requires `--format`; combined directory mode requires a new output directory.
Library callers can separately obtain producer and numeric results for the same
bound query.

## Independent acceptance cases

| Case | Expected assessment |
| --- | --- |
| Valid Windows read/write fixture, matching RIP/exception location, valid required GPRs, zero evaluated address and coherent data-address parameter | Consistent with this zero-start hypothesis. |
| Same profile, nonzero evaluated address and coherent parameter | Refuted under premises, with the computed value retained. |
| `RAX=0`, displacement eight, reported inaccessible byte within the resulting span | Refuted for zero-start only; no claim that null-derived access is ruled out. |
| Nonzero terms whose modular sum is zero | Consistent; no assertion that a base register was null. |
| Indexed or RIP-relative admitted form | Matches an independently computed expression; no extra RIP/length adjustment. |
| Raw register bytes are zero but the required validity group is absent | Unknown, not a zero observation. Existing Stage B fixtures remain in this category. |
| Missing parameter array, insufficient parameter count, unavailable context or unsupported platform/exception kind | Unknown with the specific requirement. |
| Different thread-list context supplies the desired value | Unknown; no fallback or merge into exception context. |
| RIP/site, exception-location, access-kind or data-span disagreement | Unknown with the conflicting observations; no false refutation. |
| Different snapshot/query or tampered observation source/identity | Binding/validation error. |
| Unsupported prefix, cast, multi-access/conditional operand, address range or restart profile | Unknown; no arithmetic or state guess. |
| Unrelated upstream entry/call gap but all fault-site prerequisites hold | A bounded numeric conclusion may coexist with a partial producer explanation. |
| Required evidence omitted by a limit | Unknown and truncated; all retained references remain valid. |

Use new fixtures with independently listed raw context flags, exception fields,
bytes and expected arithmetic. Test through the same binding/assessment interface
as callers; the oracle must not call the implementation's evaluator or merely
compare against BAP-generated expected values. Preserve existing fixture bytes
and first-question outputs. Mutations must catch zero-filling invalid registers,
using the exception-location field as a data address, substituting another
context, dropping index/displacement, misapplying RIP, bypassing admission and
promoting unknown evidence to a definite conclusion.

Source/fixture conformance and a controlled real Windows capture are separate
qualification tiers. A real case needs independently established exception-site,
context and access evidence. Zero-address captures do not qualify the independent
first-question Windows query. Its original Electron artifact was later retired as an active obligation
by the [explicit replacement](workload-performance-design.md#windows-investigation-replacement); each retained
record keeps its own scope. Existing Linux evidence does not qualify this
Windows-specific numeric profile.

## Qualification entry points

```sh
python3 tests/input/fixtures/make_i5a.py --check
cargo test --offline --locked --release --test input_i5a -- --include-ignored
python3 tools/check_i5a.py
```

Native checks require the pinned BAP/LLVM helpers and Graphviz. The
[fixture measurement contract](../../tests/input/fixtures/i5a/performance.json)
freezes one warm-up/five repeats, a 10 ms combined phase median and a 1,500 ms
assessment-CLI median for its small synthetic workloads. These are separate from
the unchanged I4 timing conditions on its independently re-pinned case; they
make no universal scale claim.

The [implementation plan](../../.agents/plans/completed/i5a-zero-address.md) records the delivered
H0–H5 sequence: finite form/context review, captured evidence, six-form assessment,
reports and independently reported qualification tiers. The original
[source/fixture result](#historical-source-and-fixture-qualification) and demo timing miss are historical;
the [native qualification](#native-qualification) is their passing
controlled-Windows successor under its pinned setup. Those records do not
qualify arbitrary later source/tool/dependency changes.

## Source and finite admission review

The 2026-10-03 pre-implementation review used root-lockfile
`minidump`/`minidump-common` 0.26.1, the
[pinned BAP toolchain](../../native/bap/toolchain.lock.json) and LLVM MC 20.1.2
as independent decoded-fact reference. Reviewed little-endian field layouts are:

| Record | Fields and relative byte offsets |
| --- | --- |
| 168-byte exception stream | Thread ID 0 (u32), code 8 (u32), flags 12 (u32), chained record 16 (u64), exception location 24 (u64), parameter count 32 (u32), up to fifteen u64 parameters starting at 40, context byte size 160 and artifact RVA 164. |
| AMD64 context | Flags 48 (u32), RFLAGS 68 (u32), GPRs RAX through R15 at 120–240 in struct order, RIP 248 (u64). CONTROL bit 0 permits RIP/RSP/RFLAGS; INTEGER bit 1 permits other GPRs; the AMD64 architecture flag is required. |

Context-descriptor RVAs are artifact offsets, not semantic VAs. Reader range/count
checks precede interpretation; raw zero bytes cannot override validity flags.
The first AV parameter supplies operation, the second inaccessible data; neither
is the exception-location field. Exception-stream context remains separate from
thread-list context, and hardware/pre-access interpretation stays a premise.

The [independent generator](../../tests/input/fixtures/make_i5a.py) and
[41-case manifest](../../tests/input/fixtures/i5a/manifest.json) specify exact
bytes, context and Python-integer arithmetic modulo 2^64 without calling the
Rust evaluator or treating BAP output as the oracle. Six MOV forms cover
base/index/scale, signed displacement, modular cancellation and RIP-relative
addresses. For the RIP-zero oracle, `48 8b 05 f9 ef bf ff` at `0x401000` has
next IP `0x401007` and displacement `-0x401007`, yielding zero. The ordinary RIP
case uses next IP plus eight; the normalized constant is never adjusted again.

Negative controls include missing/invalid required groups and parameters,
unused-register independence, CONTROL-only RSP/RIP, another context, mismatched
site/kind/data span, unsupported platform/prefix/stack form/range, span wrap,
conditional/multiple accesses and unreviewed projections. Existing Stage B
fixtures remain unchanged and yield unknown. Reader tests separately reject
malformed extents/counts. All definite decisions still require form/access
role and width agreement under the admission contract above.

A normal two-parameter context contributes eight exception/descriptor fields,
two parameters, context flags and eighteen register observations. Record/context
extents plus one instruction bring the total to 32 evidence records. Twenty-nine
field observations, one instruction observation, one numeric fact and a conclusion
fit 32 claims. Extra parameters or tighter caller limits may produce unknown and
truncation; the count is not a general latency bound.

## Historical source and fixture qualification

These retained campaigns have distinct sources, backends and acceptance scope.
No new runtime qualification was run for this document consolidation.

| Date / record | Result and scope | Open clause or successor |
| --- | --- | --- |
| 2026-10-03, [v1 source/fixture record](../../evidence/Ariadne/i5a-validation.json) | 12 gates, 171 stable source hashes, all 41 synthetic cases and 16 actual implementation mutants pass; 24 legacy CLI outputs stay byte-exact. | Controlled Windows was unexercised. The historical backend measurements do not qualify the later native default. |
| 2026-10-03, [controlled demo](../../evidence/Ariadne/crashpad-demo-validation.json) | Both captures and independent zero-address answers pass; phase medians meet 10 ms. | CLI medians 1,820.299/1,824.496 ms exceed 1,500 ms; controlled acceptance remains false. |
| Initial native refresh, [progress record](../../evidence/Ariadne/i5a-native-progress/progress.json) | Nine fixture timing cases and sixteen mutants pass, but source/fixture is 12/14 and investigation 16/17. | Concurrent MirrorRust formatting/source identity changes invalidate aggregate qualification. Failed flags are retained. |
| 2026-10-05, [native fixture](../../evidence/Ariadne/i5a-native-fixture-validation.json) and [controlled record](../../evidence/Ariadne/i5a-native-controlled-validation.json) | All 14 fixture, 17 investigation and refreshed 20 native-core gates pass under the selected read-only dependency snapshot; both controlled modes meet unchanged budgets. | Covers the recorded Linux-hosted analysis of Windows-origin captures, not arbitrary later source or a packaged cross-platform release. |

The original run exercised eleven I5a tests with `--include-ignored`: eight
without native prerequisites and three covering native preparation with Rust
analysis, CLI/Graphviz publication and unchanged legacy fixtures. Fifty-six
budget combinations, strict report/query/metadata tampering controls and all
formats pass. The sixteen actual mutants cover admission, exception-location
substitution, dropped displacement/index scale, double-applied RIP, prefix/range
bypasses, invalid-register zero filling, thread fallback, unknown promotion,
classification, missing premises, query binding and both output limits. Compile
failure or timeout receives no sensitivity credit.

Its nested 17-gate investigation, 12-gate Stage E and 11-gate minidump runs retain
their own scope. The Stage E run repeated 64 complete traces and 326 observations
over sixteen stateflow and sixteen LLVM IR cases, detecting fifteen mutants.
The first-question Linux phase total was 170.853 ms; original-Windows acceptance
was unavailable and is not supplied by these numeric fixtures.

The pilot (0.990 ms phase / 791.923 ms CLI) remains diagnostic. In the original
nine qualified fixture workloads, combined phase medians ranged 0.859–1.795 ms
and assessment CLI medians 754.883–1,179.540 ms against 10/1,500 ms. The v1 record
retains all per-case values, 90 measured CLI samples and 45 measured phase samples
plus warm-ups, hashes and peak RSS (at most 84,196 KiB). Timing variation does not
establish a speedup. The [historical manifest](../../evidence/Ariadne/i5a-evidence-manifest.json)
and [archive](../../evidence/Ariadne/i5a-evidence.tar.gz) retain 1,610 files,
including 334 source files across combined inventories, original/nested records,
logs, synthetic dumps, reports and comparison baselines. Real captures remain
external; archive verification applies to that recorded snapshot.

## Controlled Windows capture

The original demo uses the clean `crashpad-nzsn` revision
`7a884c25c84c46352fc6f16ef0a798ece2b77e84`, links `client:client`, synchronously
starts its matching handler, disables database uploads and supplies no upload
URL. It records an independent null-write witness before the separate fault
function. The [demo guide](../../native/crashpad-demo/README.md) owns reproduction.
GN 2077/Ninja 1.8.2 built Windows x64 with pinned Clang 20, MSVC libraries
14.51.36231 and SDK 10.0.28000.0. The
[isolated preparation](../../native/crashpad-demo/README.md#isolated-source-preparation)
uses three mini_chromium compatibility headers and an x86/x64-only helper
adjustment without changing Crashpad capture logic. ARM64 generation fails
explicitly; repeated x64 GN generation was stable.

Both runs exit `0xc0000005`; missing-handler and invalid-mode controls exit before
the deliberate crash with no witness/dump. The database utility independently
confirms uploads disabled. The
[raw inspector](../../native/crashpad-demo/inspect_capture.py) checks structures,
process/context/exception fields, a 256-byte captured code range for holes and
conflicts, and module/PE agreement. Its independent tests cover both stream forms,
overlap consistency, invalid context/RIP/opcodes, truncation and exclusive output.

| Capture | Dump size / stream / full-memory flag | Historical phase / CLI median | Native successor phase / CLI median |
| --- | --- | --- | --- |
| Partial | 225,408 bytes; `MemoryList`; clear | 1.720 / 1,820.299 ms; CLI fails | 1.067 / 869.642 ms; passes |
| Full | 15,987,422 bytes; `Memory64List`; set | 1.625 / 1,824.496 ms; CLI fails | 1.032 / 873.537 ms; passes |

Both captures have matching exception RIP/site, fault RVA `0x3ae0`, bytes
`c7 01 05 00 00 00` (`mov dword ptr [rcx], 5`, followed by `ret`), RCX zero,
a four-byte write, operation write, inaccessible byte zero and context flags
`0x10001f`. Both results are `consistent_with_evidence`, EA zero and no assessment
gaps under admitted premises. Assessment preserves base-report bytes and both
DOT families parse with Graphviz. The historical CLI ranges were
1,742.791–1,853.441 ms partial and 1,804.609–2,056.832 ms full; neither passed its
frozen median criterion. The
[demo manifest](../../evidence/Ariadne/crashpad-demo-evidence-manifest.json)
binds exact build/capture/inspection/answer/timing evidence.

Raw inputs/executables were retained externally under
`tmp/crashpad-demo/20261003/{partial,full}/`; the original Windows build/database
path is recorded in the demo evidence. A full-memory flag does not establish
complete process memory. This two-instruction demo does not qualify the separate
98-start first-question Windows workload, original Electron artifact, native
Windows execution of Ariadne, general instruction coverage or root cause.

## Native qualification

The native phase benchmark consumes
`NativeAnalyzer::from_capture(...).complete()` through `AnalysisView`.
Recovery is outside the incremental timer and inside full CLI timing. Rows bind
native manifest/build, captured profile, artifact/snapshot, report query,
distinct native-protocol query and assessment digest. Default/explicit BAP output
comparison occurs outside timed samples. No production analysis/performance patch
was needed to meet the unchanged one-warm-up/five-repeat 10/1,500 ms limits.

The retained native fixture record covers 216 source hashes, all 41 corpus cases
with completed native analysis, thirteen native contract controls, 28 controlled
capture controls and sixteen implementation mutants. Comparisons preserve 24
legacy Rust hashes, check 24 native/reference outputs and twelve exact explanation
outputs. Nine fixture CLI medians are 844.584–1,070.294 ms and native phases
0.590–1.059 ms. The controlled table above records passing partial/full assessment
medians; base CLI medians were 881.653 and 875.029 ms. Differences between modes
are not evidence of speedup.

`controlledWindowsCasePassed=true` belongs to the controlled record with stable
inputs/sources/tools. The fixture record separately keeps its controlled-case
flag false because it did not exercise those captures. Original-Windows I4
acceptance remains false; active replacement I4 was over budget at this checkpoint
and passed only in its later [performance campaign](workload-performance-design.md#native-investigation-qualification).
Fresh inspection files preserve original dump/executable/witness/producer-build
identities; nearby current demo sources do not replace historical producer hashes.

The dependency repair copies all non-ignored MirrorRust worktree inputs,
including compile resources, formats the copy and retains original/formatted
bytes. Linux bubblewrap mounts the selected snapshot read-only at the ordinary
dependency path; validation checks mount identity, manifest and file hashes.
Live checkout edits cannot change this view. The exercised manifest SHA-256 is
`f761168b8e9dfa6f8d30246199cb1fff95128449cb20ecb1c14fa2863cf60a56`, with recorded
base `afbb694bd847ad34dbfbbba75a05038653a350a1`; captured worktree bytes are not
claimed to equal a clean revision. The native-core record covers 632 Ariadne
sources and retains the dependency contents; all 190 qualification Python controls
passed in that campaign. Reuse across snapshot identities is rejected.

Failed [progress evidence](../../evidence/Ariadne/i5a-native-progress-evidence.tar.gz),
[pre-repin accepted history](../../evidence/Ariadne/i5a-native-history/2026-10-05-before-i4-repin/i5a-native-evidence-manifest.json)
and [earlier native-core adoption](../../evidence/Ariadne/bap-core-history/2026-10-04-adoption/bap-core-qualification.json)
retain their original identities and flags. The native successor qualifies only
the declared finite capture/fixture corpus under its snapshot and trusted BAP
lifting premises; no historical path, lifetime or universal refinement follows.

## Reproduction and retained evidence

Create a dependency snapshot and use its printed digest consistently:

```sh
python3 tools/with_mirrorrust_snapshot.py create \
  --output target/qualification-deps/mirrorrust-recheck
snapshot_sha256=REPLACE_WITH_PRINTED_SHA256
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/qualification-deps/mirrorrust-recheck \
  --sha256 "$snapshot_sha256" -- \
  python3 tools/check_bap_core.py --output target/bap-stage2-recheck
```

Use the same wrapper for `tools/check_investigation.py`, `tools/check_i5a.py`,
`native/crashpad-demo/assess.py` and evidence verification. Reuse requires complete
source/tool and qualification-environment identity matches. Pinned helpers/runtime,
SDK, Graphviz, model tooling and raw capture inputs are prerequisites; missing
inputs give no acceptance credit. The
[native qualification plan](../../.agents/plans/completed/i5a-native-qualification.md) owns this
refresh sequence and its fixed criteria.

`check_i5a.py` emits `ariadne.i5a-acceptance/v2` and runs fixture determinism,
format/default/core tests, all-feature and investigation-only Clippy, layout,
native corpus/CLI, mutation/output equivalence, measurements and full investigation
regression. Replay and mutation builds use separate root `target/` subdirectories;
retired instruction-step/Lean gates remain excluded. The
[controlled runner](../../native/crashpad-demo/assess.py) requires a passing v2
record through `--source-fixture-record`, separate fresh partial/full inspections
through `--inspection-dir` and a matching environment. Historical v1 or partial
12-of-14 records cannot qualify. The
[demo instructions](../../native/crashpad-demo/README.md#inspect-and-analyze)
cover the inspection and default/explicit-native checks.

The [native manifest](../../evidence/Ariadne/i5a-native-evidence-manifest.json)
and [archive](../../evidence/Ariadne/i5a-native-evidence.tar.gz) retain 1,969 entries
(27,059,376 bytes): source snapshots, producer records, logs, CSVs, bundles and
separate inspections, with original-path mapping. Every member and accepted
source/tool inventory was checked after retention. Raw real dump/executable bytes
remain external and hash-pinned; a later change requires a fresh identity check.
