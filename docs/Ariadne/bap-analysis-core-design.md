# BAP semantic and analysis integration

## Context and follow-up

**Status.** BAP is the sole production minidump semantic provider. Typed-BIL v3
capability admission, conservative ordinary continuation, native recovery,
reaching definitions, slicing, finite stateflow, generated replay and bounded
completion transport are implemented. The CLI selects native BAP analysis by
default and retains explicit Rust analysis rollback. P0–P4 admission is accepted
for the selected finite corpus, with the excluded historical real-Linux clauses
preserved in the [acceptance decision](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/p4-acceptance-20261010.json).
Implementation contracts, source/API review and source-bound qualification are
separate evidence; this consolidated design does not renew qualification.
The [vector admission extension](../../.agents/plans/completed/bap-vector-registers.md) implements
a finite XMM/YMM namespace under producer profile v4; its fresh validation is
separate from the accepted v3 records.
The current Basic v9 rebuild passes three native candidate tests under an
isolated pin; its production pin and missing historical identity remain unchanged.
The separately selected [plain v12 repeated-string stage](../../.agents/plans/amd64-operation-coverage.md#resume-plain-rep-and-coverage-accounting)
adds conservative dependency projection for three exact byte forms. Its proof
modes remain refused, and full instruction coverage remains open.

**Why this document exists.** The [effect design](operand-effects-design.md)
exposes the coverage and maintenance costs of local instruction rules. BAP
integration first introduced a pinned semantic provider, then moved actual
analysis computation into BAP-owned passes while preserving Ariadne's snapshot,
control, origin and reporting contracts. The integration plan records the
[semantic-provider stage](../../.agents/plans/completed/bap-integration.md#stage-1-bap-semantic-backend)
and [native-analysis stage](../../.agents/plans/completed/bap-integration.md#stage-2-bap-analysis-core)
as delivery steps of this design.

**What this document establishes.** One integration design covers native lifting,
typed projection and admission, immutable analysis requests, full observations,
BIR attribution, error semantics and correspondence to the authoritative TLA+
machines, together with setup, source review and the retained qualification
scopes. Contract validation does not prove an arbitrary lifter or pass correct.

**Where to go next.**

- [AMD64 operation coverage program](../../.agents/plans/amd64-operation-coverage.md) —
  active instruction-family inventory, producer-gap closure and architectural
  admission expansion; full instruction coverage remains an open stage exit.

- [AMD64 coverage completion design](amd64-coverage-design.md) — proposed
  source reconstruction, authoritative encoding-domain bindings and remaining
  REP/consumer expansion; this integration document retains implemented contracts.
- [Plain REP and accounting stage S4/Q0](../../.agents/plans/amd64-operation-coverage.md#resume-plain-rep-and-coverage-accounting) —
  exact v12 scope, consumer refusals, executable denominator accounting and
  remaining qualification gates.

- [Completed native request-budget plan](../../.agents/plans/completed/native-request-budget.md) records caller-selected inbound frames, paired capability checks and fresh native qualification.

- [BIL shift-count compatibility](bap-shift-count-design.md) — captured XORPS diagnosis, independent count widths and versioned correction.

- [Captured indirect-target resolution](indirect-target-resolution.md) and
  [R0–R6 plan](../../.agents/plans/indirect-target-resolution.md) — implemented BAP-based
  target expressions, completeness receipts and preparation integration.
- [Integration plan](../../.agents/plans/completed/bap-integration.md) and its
  [execution ledger](../../.agents/plans/completed/bap-integration.md#current-execution-ledger) —
  delivery order and retained semantic-provider/analysis-core decisions.
- [Projection admission plan](../../.agents/plans/completed/bap-projection-admission.md) — accepted
  P0–P4 scope, remote qualification, exclusions and nonblocking follow-ups.
- [Vector admission plan](../../.agents/plans/completed/bap-vector-registers.md) — finite XMM/YMM
  aliases, conservative aggregate-state projection and dated finite validation.
- [Justified branch pruning design](justified-branch-pruning-design.md) — proposed
  alignment premises, all-path receipts and proof-gated MOVAPS normal admission.
- [Bounded completion transport plan](../../.agents/plans/completed/bap-completion-pages.md) —
  action batches and paged final results within unchanged frame limits.
- [Native analysis implementation plan](../../.agents/plans/completed/bap-stage2-implementation.md) —
  delivered A1–A6 analysis and adoption work.
- [A0 implementation plan](../../.agents/plans/completed/bap-stage2-a0.md) and
  [OCaml foundation plan](../../.agents/plans/completed/bap-ocaml-qualification.md) — completed
  contract, SDK, helper-state and transport foundation.
- [Windows workload replacement plan](../../.agents/plans/completed/bap-windows-repin.md) —
  authorized replacement of the unavailable capture for active BAP S4/S5.
- [Completed BAP-only semantics plan](../../.agents/plans/completed/bap-only-semantics.md) —
  removal of the LLVM semantic fallback while retaining decoded-fact validation.
- [Native helper setup](../../native/bap/README.md) and
  [analysis SDK setup](../../native/bap-core/README.md) — pinned build and runtime
  prerequisites; [lifter source](../../native/bap/lift.cpp) and
  [projection source](../../src/bap/projection.rs) implement the reviewed boundary.
- [Retained native refresh](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/i4-performance-qualification.json),
  [OCaml foundation record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-ocaml-qualification.json) and
  [selected replacement qualification](file-reader-design.md#windows-replacement-capture-and-bounded-query) — separate
  source/tool/corpus decisions and adoption evidence.
- [Core model](../../Specs/Ariadne.tla),
  [effects model](../../Specs/AriadneEffects.tla),
  [stateflow model](../../Specs/AriadneMachineState.tla) and
  [Rust correspondence](../implementation.md) — authoritative modeled behavior
  and its separate reference implementation.

**What remains unresolved.** BAP lifting remains trusted under the
[semantic assurance decision](semantic-assurance.md); finite replay is not a
universal refinement or ISA-step proof. Packaged cross-platform release
qualification, richer BIR transformations, general memory-alias precision,
general indirect-target enumeration and historical execution reconstruction
remain outside this delivered contract. The [finite target resolver](indirect-target-resolution.md)
implements opt-in pointer-slot/table work and records its separate named-corpus
qualification, new capture profile and compact completion encoding. Prefix/system,
SIMD beyond the finite XMM/YMM extension, general x87 and unreviewed loop
semantics retain explicit unsupported outcomes. The advanced producer below
adds a finite FP-control namespace and separately versioned analysis integration. External Electron acceptance requires its exact
capture bytes. The selected replacement acceptance excludes historical
real-Linux coverage and its six output hashes; their unexercised/failed records
remain historical. BAP timing is unlimited, while investigation contracts keep
their separate fixed budgets. The evidence boundaries below retain those scopes;
the [documentation map](../documentation-map.md) connects the related work.

Current validation follows the [executable test matrix](../../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## Reading map

- [Setup and use](#backend-usage), then [reproduction](#reproduction) for qualified runs.
- [Projection](#projection) and [admission matrix](#decision-matrix) for semantic scope;
  [immutable inputs](#immutable-requests-and-finite-domains) and
  [native lifecycle](#versioned-interface-and-lifecycle) for the analysis contract.
- [Pinned source review](#pinned-projection-source-review) for provider/getter facts,
  kept distinct from [native qualification](#native-qualification).
- [Evidence boundaries](#evidence-boundaries), [delivery history](#bap-only-delivery),
  [admission repairs](#mutation-campaign-and-repair) and
  [latest accepted scope](#selected-replacement-acceptance) for dated decisions.

## Architectural rationale

The original 2026-10-01 assessment was a source/API review, with no BAP corpus
run. It recommended a bounded, pinned lifting experiment before core replacement;
subsequent implementation and qualification supersede that delivery decision.
The useful architectural distinctions remain:

| Capability or choice | Integration consequence |
| --- | --- |
| Raw-byte lifting through `bap mc`, `Memory.create`, `Disasm.of_mem` and a custom `Disasm.Driver.scan` | These APIs admit a captured-byte boundary but do not establish snapshot identity, sparse-hole handling or per-instruction evidence. Default root selection and the speculative driver can discover beyond known paths, so the integration supplies its own frozen, entry-driven instruction domain. |
| BIL, BIR and LLVM IR | BIL carries instruction expressions/statements; BIR provides program/subroutine/block/definition/phi/jump terms and optional SSA. An LLVM-backed BAP decoder does not produce LLVM IR. The [direct LLVM IR path](typed-replay-design.md#finite-corpus-and-claim-boundary) still accepts independently verified `.ll`/`.bc`; replacing it with BIR would require a different input and acceptance contract. |
| BIL dataflow and unknown values | BAP's documented constant-propagation and dead-virtual passes do not track memory locations. `Unknown`, `Special`, assignments and phi nodes do not establish complete effects, fault/commit behavior or definite replacement. Ariadne must project GPR bytes, individual flags, `memory:any` and `state:other` conservatively. |
| BIR control forms | Direct/indirect labels and call/goto/return/interrupt forms can carry distinctions but do not prove complete target enumeration or callee behavior. Local traversal follows summary edges; unresolved control and opaque effects remain obligations. Supplied finite stateflow needs its own trusted transition relation and terminal outcomes. |
| Keep only the earlier LLVM MC/Rust path | Preserves its own exercised contract but retains local-rule coverage and alias limits. The later BAP-only semantic decision superseded this option. |
| Isolated pinned helper | Supports strict machine-readable schema, byte identity, completeness and error boundaries. A diagnostic CLI dump is insufficient. Rust/OCaml FFI would additionally own runtime and ABI compatibility. |
| Native analysis ownership | Requires fresh graph, state, attribution, replay and report qualification; prior Rust measurements cannot qualify the replacement. The Rust engines remain independent reference/rollback implementations. |

The reviewed interfaces are documented in the [BAP README](https://github.com/BinaryAnalysisPlatform/bap),
[Memory API](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/Memory/index.html),
[disassembly API](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/Disasm/index.html),
[driver algorithm](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/Disasm/Driver/index.html),
[BIL API](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/Bil/index.html),
[BIR overview](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/index.html)
and [project/pass API](https://binaryanalysisplatform.github.io/bap/api/master/bap/Bap/Std/Project/index.html).
Public master API pages, including since-2.6.0 annotations, do not establish the
facilities of the pinned v2.5.0 artifacts. The earlier review recorded v2.5.0's
LLVM 13/14 compatibility notes and later source LLVM 16/17 fixes; compatibility
with Ariadne's independent LLVM MC 20.1.2 must be measured rather than inferred.
The runtime/source locks below bind the actual selected builds.

The [reader contract](file-reader-design.md) remains decisive: a module record
or matching executable cannot supply missing runtime instruction bytes or finish
a captured prefix. Changing loaders cannot remove that requirement. The original
assessment proposed a corpus covering aliases and zero extension,
defined/undefined flags, loads/stores, direct/indirect control, calls, unreadable
holes and fault candidates. It required future provenance and cost observations;
that assessment itself ran no corpus trial. Its adoption recommendation required
better supported coverage without unsound kills, constrained discovery and
explicit unsupported outcomes. Later qualification records provide their own
measured evidence.

## Selected native boundary

Host BAP's OCaml runtime in a separate C++ helper through the packaged typed
`bap-api` C interface. Rust never links OCaml or uses unsafe FFI. This changes
the helper's host language, not its semantic provider: all instruction lifts
come from BAP's x86 legacy lifter. The official v2.5.0 artifacts report
prerelease fingerprints; `native/bap/toolchain.lock.json` records actual
versions, source reference, plugin/library/header and archive hashes rather
than claiming clean stable-tag provenance.

Initialize only `llvm` and `x86` providers, with `--x86-lifter=legacy` passed
through the actual BAP configuration argv. This avoids unrelated symbolic
executor plugins. A fresh process owns one snapshot/target and one BAP
knowledge-base lifetime. Reuse it for bounded batches within that snapshot,
then terminate it; never reuse semantic caches across snapshots.

## Versioned stream

The native executable supports a version probe and a stream mode. Requests
are bounded ASCII lines: an initialization header with protocol version,
target (`windows-amd64` or `linux-amd64`) and SHA-256 snapshot token; then
`batch ID COUNT` followed by unique canonical full-width VA and captured hex
prefix rows (1–15 bytes). The helper sees no dump/executable paths and performs
one basic decode per requested site, without recursive discovery or synthetic
byte filling. A batch ends with a matching ID/count marker.

Responses are bounded JSON lines containing schema, batch/snapshot identity,
VA, status, length, exact consumed bytes, opcode and control-property facts,
and a recursively tagged BIL AST. Expressions preserve variable name, width,
virtual/architectural distinction, integer width/value, operation, child
expressions, load/store width and extraction/cast bounds. Statements preserve
move, branch, jump, exception, special and loop forms. Pretty BIL/assembly may
be diagnostic evidence; projection consumes only typed fields.

Rust validates identities, counts, duplicate/unknown fields, canonical addresses,
consumed bytes/length, AST depth/node/width limits, version and helper exit.
Timeout/transport/version failures invalidate the selected query before output.
Unavailable capture remains distinct from decoder/lifter failure. Retain
unsupported constructs and generic unknown values conservatively.

## Projection

### AMD64 operation coverage program

The [completion design](amd64-coverage-design.md) owns the proposed source-gap,
legal-form binding and wider REP architecture. Its
[execution stages](../../.agents/plans/amd64-operation-coverage.md#coverage-completion-design-stages)
separate those obligations from the finite implementation described here.

The user-requested [coverage program](../../.agents/plans/amd64-operation-coverage.md)
extends this design's production semantic boundary across AMD64 operations.
It separately tracks an executable family survey, a complete versioned legal-form
inventory, missing producer lifts, architectural-state/width expansion, prefix
and loop semantics, and exceptional/system operations. A representative survey
does not establish an exhaustive instruction denominator. The existing profile
v6 remains finite until individual changes are implemented and qualified.

Support means implemented control and dependency effects under declared
architectural premises, with independent executable expectations. Merely
decoding an instruction, receiving BIL, or emitting conservative unknown effects
for an unimplemented operation does not close its coverage row. Environmental
unknowns within implemented semantics remain explicit. BAP remains the trusted
semantic producer; missing upstream lifts require producer work and new pinning,
not an automatic LLVM effect fallback. Saved producer profiles retain their
original interpretation. The plan's S0–S5 and Q0–Q1 stages own implementation
and qualification; its unwind track belongs to the investigation design.

#### Explicit source-built flag extension

The first producer extension supplies actual upstream BAP BIL for the exact
unprefixed AMD64 bytes F8 (CLC), F9 (STC), F5 (CMC) and FD (STD). The pinned
packaged producer returns empty lifts for these forms. A maintained
[upstream patch](../../native/bap/source-coverage/flags.patch) extends its opcode
type, byte parser and lifter; a separate process built against the checked SDK
exports the resulting typed BIL. It does not load an SDK-built plugin into the
older packaged runtime, and it does not synthesize effects from LLVM opcode names.

The [build command](../../native/bap/source-coverage/build.py) verifies the source
archive, checks the original gaps, builds original/patched observers, checks
independent CF/DF equations and emits an isolated runtime. A checked-in
[dependency lock](../../native/bap/source-coverage/runtime.lock.json) binds the
reproducible manifest and executable. The [host boundary](../../src/bap/source_extension.rs)
also binds exact source, patch, SDK and query identities, bounds process output
and time, and rejects malformed, changed or out-of-scope responses. The backend
refuses reuse after a failed extension query and revalidates artifacts at finish.

Selection is explicit through `Config::with_source_extension` or
`ARIADNE_BAP_SOURCE_EXTENSION`. The default packaged path retains its existing
behavior and identities. The opt-in path uses projection profile
`bap-bit-provenance-v9` and a combined runtime identity; saved earlier profiles
retain their original interpretation. Extension use requires agreement between
the two decoders on an ordinary one-byte instruction and an empty base lift.
Prefix variants and all other missing lifts remain outside this extension.

```sh
python3 native/bap/source-coverage/build.py --output target/new-source-flags
ARIADNE_BAP_SOURCE_EXTENSION=target/new-source-flags/runtime \
  python3 tools/probe_amd64_semantics.py --native \
  --output target/new-source-flags-survey
ARIADNE_BAP_SOURCE_EXTENSION=target/new-source-flags/runtime \
ARIADNE_BAP_CORE_DIR=target/bap-core-native \
  cargo test --offline --locked --lib bap::source_extension::tests::native_ \
  -- --ignored --test-threads=1
```

The source/SDK lock qualifies a specific reproducible build; different artifacts
need explicit pin review and qualification. Ordinary preparation, recovery,
definitions and slicing are the initial integration scope. Guard admission,
target resolution and memory refinement are explicitly refused, including
zero-work requests and their saved/native replay boundaries, until their
operation-dependent proofs have separate qualification. This four-operation
extension does not establish general AMD64 coverage.

##### Current Basic v9 candidate compatibility

**Checked, 2026-10-23, at source `faf75f7`.** The
[checkpoint](../../CHECKPOINTS.md#2026-10-23--current-basic-v9-candidate-compatibility-checked)
and [candidate-check plan stage](../../.agents/plans/amd64-operation-coverage.md#current-basic-v9-candidate-check)
distinguish functional testing of the available Basic rebuild from reproducing
the missing historical producer. The current candidate has manifest SHA-256
`9cfd9760026352d98bd14ef42a12b4a6d39d56ae5f3957174062c482c372f8ac`
and executable SHA-256
`d0876132843e3a9ace0a6d5e6254f4da7f6a0e29024c575db16367fc7332f941`.
It retains the Basic v9 schema, four-operation scope and source/SDK bindings.
These hashes are candidate identifiers, not an adopted production pin.

All three existing [native source-extension tests](../../tests/bap/source_extension.rs)
pass against this candidate in a disposable source copy whose only source change
is an explicit candidate pin. The tests exercise actual four-flag BIL and the
unchanged corpus; refusal of guarded/target/refinement modes and tamper poisoning;
and synthetic Windows/Linux captures with full native/Rust state equality,
opaque-site binding and forbidden target-resolution replay. All 647 shared
source/test/native and Cargo files match the current checkout before that pin
change; the unrelated real Windows capture archive is excluded. The copied lock
is restored and both source trees are rechecked after the run.

The unchanged production Basic lock rejects both the current Basic candidate and
the advanced runtime at the manifest hash check before semantic dispatch. Direct
typed-BIL comparisons agree for the four flag bytes on both supported targets
(eight cases), apart from separately bound build IDs. This does not authorize
the advanced schema/profiles as Basic v9. Functional testing can use the current
Basic rebuild with its own explicit pin; adopting that pin needs separate review.
The original identity remains unreproduced, and no production lock is changed by
this check. Run products stay outside maintained source. Broader producer,
real-capture, performance and release qualification remain separate.

#### Pinned form inventory and advanced producer

**Resumed, 2026-10-23.** The [stopped checkpoint](../../CHECKPOINTS.md#2026-10-22--amd64-items-13-stopped-at-user-request)
records the saved partial implementation and failed native matrix. The
[resume record](../../CHECKPOINTS.md#2026-10-23--amd64-guard-replay-and-composed-fixture-resumed)
and [execution plan](../../.agents/plans/amd64-operation-coverage.md#resume-guard-replay-and-composed-fixture)
track the source fixes and approved native continuation. The advanced versions
below remain unqualified for general use. All eight finite advanced native
integration tests pass, including eighteen mandatory-count compositions; the
exact historical Basic v9 producer compatibility and remaining qualification
clauses stay open.
REP remains refused under v10/v11; the later [plain v12 stage](#plain-repeated-string-profile-and-coverage-accounting)
admits three reviewed forms under a separate dependency contract.

The [inventory extractor](../../tools/amd64_inventory.py) and its
[lock](../../tests/bap/fixtures/amd64-semantics/inventory.lock.json) enumerate
10,994 encoding templates from pinned Intel XED commit
`0bcb6237345c5066726dcc08b3d87928df3b5b26`: 10,569 have a long-mode candidate
and 425 are excluded by their mode constraints. The records retain raw encoding
patterns, operand forms, prefixes, extension/ISA sets, aliases and source
locations. These are symbolic templates, not all concrete byte strings and not
an assertion that every candidate is legal on every AMD processor. The
[AMD manual extractor](../../tools/amd64_manual_inventory.py) separately indexes
instruction sections and encoding tables; unmatched names, merged cells and
unparsed lines remain explicit. Name agreement with XED does not prove matching
encoding legality. S1 remains open until those gaps and vendor differences are
reconciled.

```sh
python3 tools/amd64_inventory.py fetch
python3 tools/amd64_inventory.py generate --output target/new-amd64-inventory
python3 tools/amd64_inventory.py check target/new-amd64-inventory/inventory.json
```

The separately pinned [advanced builder](../../native/bap/source-coverage/advanced_build.py)
and [runtime lock](../../native/bap/source-coverage/advanced.runtime.lock.json)
retain the four source-built flag forms while opening a separately versioned
analysis path. Select `Config::with_advanced_source_extension`, or set both
`ARIADNE_BAP_SOURCE_EXTENSION` and `ARIADNE_BAP_SOURCE_EXTENSION_MODE=advanced`.
An absent directory, unknown mode, Basic bundle in Advanced mode, or changed
artifact is rejected. The default packaged profile and Basic v9 interpretation
remain separate.

| Product | Advanced version and binding |
| --- | --- |
| Plain/guarded producer | `bap-bit-provenance-v10` / `bap-bit-provenance-v11`; exact combined runtime identity |
| Guard proof | Report/policy v3; `captured-guarded-input/v3` |
| Captured indirect target | Report schema v4; rooted policy v2 / local policy v3; `captured-indirect-targets/v2` |
| Guard/target composition | Report v4; `captured-guarded-targets/v4` |
| Memory refinement | Transfer receipt and assessment v2, bound to the advanced producer |

The native checker replays the selected profile's typed BIL and proof premises.
A producer-version string alone cannot authorize a saved report. Basic v9 keeps
its refusal of guarded, target and refinement modes. Explicit alignment
hypotheses retain their separate contract and are not enabled by selecting this
producer.

The new projection admits canonical `MXCSR:32` and `FPU_CONTROL:16` variables,
with possible dependencies/writes in `state:other`; those partial state updates
never kill all aggregate origins. It admits only the reviewed canonical 2–9 byte
NOP encodings as empty lifts, after exact BAP/LLVM byte and length agreement.
For data-only BIL, path merging unions possible origins under a 262,144-step
work bound, allowing the observed PSHUFB lift without erasing alternatives.
Control-bearing paths keep their separate limits. These changes do not admit
arbitrary x87, system, mask, ZMM or extended-register semantics.

The [bit-count oracle](../../tools/check_bap_bit_count_oracle.py) checks actual
BAP BIL against independent integer equations for eighteen POPCNT/LZCNT/TZCNT
forms: 16/32/64-bit register and memory operands. It checks numeric results,
defined flags, partial/zero-extended destinations and unaffected state; undefined
flags remain outside the numeric comparison. Its passing 4,020 comparisons do
not establish other operand/prefix forms or full ISA correctness.

Saved guard sources contain bytes and BIL rather than decoder opcode text.
Replay recovers only the exact reviewed count or canonical NOP opcode from
those bytes under the selected profile; other transfers keep generic typed
admission. This preserves count-independent RSP facts without granting generic
F3 permission. The composed table fixture explicitly selects a finite 64-epoch
guard budget: candidate discovery itself exceeds the default eight epochs.
A packaged-producer control verifies the default stopped report and the
selected-budget actual MOVAPS guard. No production budget was increased.
Composition's original-control checker also replays advanced sources with their
declared projection; its legacy path retains the previous interpretation. The
[portable composition regression](../../tests/bap/composition_unit.rs) covers all
eighteen count forms, altered-prefix rejection and old-profile refusal.

The 2026-10-23 approved native continuation restores the original compatible
isolated SDK userspace. Two independent advanced builds reproduce manifest
`1bd4a1dc59b9e71077ef6562d6104563ec9ee5dacf985c8e788a5cd62f92baaf`
and executable
`9ad0d7f247ddc67ea6f0eeeb5008e35b45a6d1361eda6c23f73e9057ad31110c`;
the explicit advanced lock now selects this source/SDK-bound candidate. The
previous saved advanced identity is not claimed reproduced. Basic v9's
immutable lock is unchanged, and a mismatching fresh Basic build remains
rejected. The [later Basic candidate check](#current-basic-v9-candidate-compatibility)
passes three native tests under an isolated candidate pin. Neither that result
nor the eight-test advanced matrix and numeric source controls
replace that historical producer compatibility gate or broader qualification.

The same continuation passes 88 native proof controls, ten compiled native
checker/dependency mutants, eight optimized Rust mutants (nine assertion
rejections after passing controls), 330 generated native core/stateflow
observations and wrong-digest rejection. Independent predicate oracles,
Apalache typechecking and 58 finite TLC configurations pass without changing
model bodies. Local validation passes 424 default/64 core-only Rust tests,
strict Clippy and root formatting under the read-only dependency-snapshot
workflow. These results have their named finite corpora; exact old-v9 producer,
broader architecture, actual-capture, timing and release clauses stay open.

The [repeated-string oracle](../../tools/check_bap_repeated_string_oracle.py)
compares the exact `F3 A4`, `F3 AA` and `F3 A6` BIL with sequential byte-copy,
byte-store and repeat-while-equal byte-comparison equations. Its 720 finite
comparisons include zero count, both directions, early mismatch, overlapping
buffers and pointer wrap, checking complete registers, flags and memory.
Hardware exception and partial-fault behavior are separate from this concrete
BIL comparison. The plain v12 profile below implements conservative projection
and loop-aware downstream transfers while refusing proof modes.

```sh
python3 native/bap/source-coverage/advanced_build.py --output target/new-source-advanced
python3 native/bap-core/build.py --output target/new-core-advanced
ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION=target/new-source-advanced/runtime \
ARIADNE_BAP_CORE_DIR=target/new-core-advanced \
  cargo test --offline --locked --lib source_extension_advanced \
  -- --ignored --test-threads=1
python3 tools/check_bap_bit_count_oracle.py --output target/new-bit-count/report.json
python3 tools/check_bap_repeated_string_oracle.py --output target/new-repeated-string/report.json
```

Two independent advanced producer builds reproduce their executable and
manifest. The [advanced integration tests](../../tests/input/source_extension_advanced.rs)
exercise actual source-produced flags in guarded stack arithmetic, captured
jump tables, call/alternate-root uncertainty and memory-writer analysis,
including native/reference equality and saved-proof tampering. Current results
and remaining stage exits are recorded in the
[execution plan](../../.agents/plans/amd64-operation-coverage.md). This finite
integration does not close full producer, architecture, real-capture, timing or
release qualification.

The [survey catalogue](../../tests/bap/fixtures/amd64-semantics/catalogue.json)
currently defines 49 family categories and 171 representative encodings, with
nine independent effect expectations. Its [runner](../../tools/probe_amd64_semantics.py)
distinguishes projected effects, unknown effects, missing producer lifts,
unsupported state/control, decode disagreement, query errors and unexercised
rows. A missing expected flag effect makes the baseline survey fail its coverage
expectation while preserving the measured reason; this does not turn a known
producer gap into a successful result. Full legal-form completeness remains S1.

##### Plain repeated-string profile and coverage accounting

**Finite S4/Q0 continuation, 2026-10-23, baseline `e44ce2b`.** The
[execution stage](../../.agents/plans/amd64-operation-coverage.md#resume-plain-rep-and-coverage-accounting)
records implementation and current validation. `Config::with_repeated_strings(dir)`
selects `bap-bit-provenance-v12` with the unchanged pinned advanced flag bundle.
Environment selection requires both `ARIADNE_BAP_SOURCE_EXTENSION=dir` and
`ARIADNE_BAP_SOURCE_EXTENSION_MODE=repeated-strings`. The packaged default,
Basic v9 and advanced v10/v11 profiles and pins keep their existing meanings.
An existing v10/v11 source is never replayed as v12.

Only exact long-mode `F3 A4` (REP MOVSB), `F3 AA` (REP STOSB) and `F3 A6`
(REPE CMPSB) are admitted by the new
[byte matcher](../../src/bap/repeated_strings.rs). Admission requires exactly
one top-level typed `While`; nested, sequential or conditionally entered loops,
external control, RIP assignments and special semantics are refused. Typed
virtual reads still require definite bindings. Other REP widths, prefixes and
string operations receive no permission from this selection.

The separately selected [memory-string successors](amd64-coverage-design.md#104-default-address-memory-rep-execution-r1)
extend plain dependencies under v13/v14. Their recipe, additional LODS producer,
source pins and current qualification remain with that canonical completion
design. They do not broaden this v12 contract or grant proof-consumer admission.

The [projection](../../src/bap/projection.rs) computes a zero-or-more-iteration
dependency closure, retaining the entry state at every join and repeating the
body until possible origins stabilize. This preserves initial origins and
loop-carried dependencies. Body writes are possible writes; they do not become
definite kills solely because the loop body assigns them. Stores weakly update
`memory:any` without killing its old origins. The existing 262,144-step work
budget and a 4,096-round dependency fixed-point cap produce explicit `Resource`
errors when exhausted; exhaustion cannot publish an incomplete projection.

Memory accesses inside the loop carry unknown iteration-dependent addresses;
first-iteration addresses cannot certify all accesses. Rust target-transfer and
native capture extraction havoc architectural and virtual loop outputs before
later scalar use. Guard, captured-target and memory-refinement preparation are
explicitly refused for v12, including requests with no entry points, before
helper/proof dispatch. Native dispatch and direct proof entry points recognize
the exact colon-delimited `bap-bit-provenance-v12` token in the overall
`semantic_profile` or a site's projection. Refusal therefore does not depend
on populated site rows: empty or all-null site collections still receive the
same profile refusal across all nine proof transports. This strengthens the
identity boundary; recovery separately rejects empty analysis domains.
Plain capture/replay accepts v12 using validated
reader-supplied normalized effects, bound to captured bytes, profile and query
evidence. It does not independently replay raw REP BIL/effect semantics; the
existing capture trust boundary is unchanged. Hostile saved captures are
rejected. This contract
does not qualify hardware partial faults, general REP, execution history or ISA
correctness. It supplies no concrete values for the loop's abstract outputs.

The following results record the v12-stage source boundary. The later
[memory-string native campaign](amd64-coverage-design.md#106-current-root-checks-and-remaining-qualification)
supersedes current-helper claims with 259 refusal controls, 416 v13/v14 parity
instances and positive v12/advanced compatibility checks; v12's contract stays
unchanged.

The v12-stage finite checks pass eight portable projection tests, six consumer tests
and the early proof-refusal test. Fresh actual BIL checks cover all three forms
on Windows and Linux, 54 altered-prefix controls and v10/v11 refusal. Before
the final native identity-boundary hardening, three plain REP native integration
tests pass, including 24 Windows/Linux sequences with native/Rust state equality
and saved-capture tampering; all eight existing advanced native regressions also
pass at that source boundary. The final rebuilt native helper passes 41 compiled
direct controls and 54 framed-dispatch controls, 95 in total, superseding the
earlier nine-control check. Its three plain REP integration tests and one positive
old-advanced composition/tampering regression also pass. The latter rechecks
compatibility and is not a ninth distinct advanced test. All 14 source hashes
bound by that final v12-stage native helper matched that recorded checkout.
The independent numeric
oracle passes 720 comparisons. Root checks at that boundary passed 439 default Rust tests
(149 ignored), 64 core-only tests (22 ignored), strict all-feature/all-target
Clippy, formatting and the 213-source Rust layout check. The earlier guard
deadline passes on its serial rerun. All four optimized Rust mutants are
detected by exact named assertions after passing controls; selected observers
and SUT sources are restored and the completed campaign records stable sources.
That campaign completed before the final native proof-policy hardening; its Rust
SUT and selected observers remain byte-identical. The later native policy is
checked separately by the 95 controls, three REP integration tests and positive
old-advanced proof recheck against the current helper.
The initial interrupted attempt to correct an old unknown-profile fixture to
sentinel v999 earns no completed-campaign credit. No result is inferred from
startup or an earlier profile's pass.

The completed current v12 native survey covers 171 byte cases: 57 supported
projections, eight conservative unknowns, 75 missing producer lifts, 28
unsupported-control/semantics outcomes, two encoding disagreements and one
query error. All nine independent expectations match. PUSHFQ (`9C`) reproduces
`BIL AST budget exceeded` with direct fresh lifting and stays a query error.
The first local survey's 171 decoder-EOF failures lacked the exact LLVM library
path and receive no semantic credit; the successful rerun uses the unchanged
LLVM 20.1.2 and matching libxml2 library path.

```sh
ARIADNE_BAP_ADVANCED_SOURCE_EXTENSION=target/new-source-advanced/runtime \
ARIADNE_BAP_CORE_DIR=target/new-core-advanced \
  cargo test --offline --locked --lib repeated_string_tests \
  -- --ignored --test-threads=1
python3 tests/bap/rep_transfer_native_controls.py \
  --native-dir target/new-core-advanced --output target/new-rep-native-controls
python3 tools/check_bap_repeated_string_oracle.py --output target/new-rep-oracle/report.json
python3 tools/check_repeated_string_mutations.py --help
```

The [coverage accountant](../../tools/amd64_coverage.py) validates the pinned
XED/manual extractor products and the exact catalogue; optional native surveys
are rebound to their observations, helper identity and current source before
classification is recomputed. It emits separate symbolic-form, manual-row,
transcription-gap and exact-byte worklists. Exact byte cases retain supported,
opaque, missing and unexercised outcomes. Candidate form/case associations must
name the exact form ID, case ID, bytes and inventory/catalogue identities; even
a supported associated sample establishes neither vendor legality nor exhaustive
coverage of that symbolic template. Names, old pass flags and aggregate counts
cannot close those obligations. Malformed, duplicate, changed or incomplete
bound inputs are rejected. `--require-full` writes the report and exits nonzero
while any full-coverage gate remains unmet.

The actual XED run reproduces 10,994 symbolic templates, 10,569 long-mode
candidates and 425 exclusions; all 10,569 candidates currently lack authoritative
form-to-byte bindings. Fifteen accounting controls and 31 existing inventory,
manual and survey controls pass. The three pinned public PDFs reproduce their
outline/content/counts, including 2,657 unresolved transcription gaps. The newer
`pdftotext` 26.01 layout hash differs from the historical full-text pin, so
strict manual validation rejects those regenerated products; the pins remain
unchanged. Accepted manual products are omitted from the current accounting
run and remain explicit obligations. Pinned-denominator fields still report
4,118 manual rows and 2,657 gaps, so omitted products cannot look gap-free.
With the fresh survey, accounting records 57 supported, eight opaque and 106
missing byte cases. Its `--require-full` exit is 2, as intended.
Official-download byte identity for Volumes 4/5, complete vendor legality,
concrete-domain expansion, wider S1/S2–S5 and Q1 remain open. Generated reports,
transcripts, raw logs and copied source trees remain disposable ignored output.

```sh
python3 tools/amd64_coverage.py --xed target/new-amd64-inventory/inventory.json \
  --output target/new-amd64-accounting --require-full
python3 -m unittest discover -s tools -p 'test_amd64_coverage.py'
```

Add repeated `--manual` paths only for products accepted under the unchanged
manual lock, and `--survey` only for a fresh current-source report. An omitted
input stays visibly missing or unexercised; this command cannot currently
establish full AMD64 acceptance.

Use a bounded abstract bit-provenance interpreter for supported BIL nodes.
Initial architectural bits refer to canonical GPR byte/flag cells and the
coarse `state:other` vector location; virtual
variables hold intermediate values and never become user locations. Constants,
extract/concat and casts preserve bit identity where justified. Supported
arithmetic produces new bits with conservatively collected input dependencies.
Track alternatives for conditional writes; combine possible effects while
requiring definite replacement on every alternative for `must_defs`.

Preserved original bits are not killed by whole-register IR assignment.
EAX zero-extension replaces upper RAX cells; partial AL/AH/AX writes preserve
untouched cells. Loads use `memory:any` plus address dependencies. Stores use
address/value dependencies, only may-define `memory:any`, and never must-kill
that alias cell. Unsupported operations, unknown outputs, unfamiliar state
and unresolved control retain gaps; calls retain opaque all-location effects.

The retained vector delivery used `bap-bit-provenance-v4`, extending v3 with the
[finite vector namespace](#vector-register-admission). Supported typed BIL,
architectural namespace, widths, virtual bindings, prefixes and compatible
control/operand facts replace generic opcode-name membership. The earlier v3
finite regression corpus has 58 exact cases and 37 projected forms, including
the four observed parser forms and paired short/long control encodings. These
are exercised cases, not a new exhaustive permission list or an ISA proof.

For the retained v3/v4 contract, LOCK, REP, segment/address-size overrides,
unmodeled architectural state and control/special/loop semantics remain explicit
exclusions. The exact `90` NOP
is the reviewed empty-BIL exception. Empty CLC remains unsupported despite its
known hardware effect. Malformed type/width/binding and resource failures abort
the query; unavailable/control-uncertain semantics stop conservatively.

When validated ordinary control and typed data-only BIL have unknown effects,
preparation retains the structural next edge, all tracked uses/may-defs, no
must-defs and `opaque-ordinary` / `unsupported-data-effects` diagnostics. Rust
and native capture admission validate that outcome; all-format reports retain
the gaps. No LLVM effect fallback is introduced. The [admission decision matrix](#decision-matrix) and
[historical-output migration](#historical-output-profile-migration) below freeze
the failure classes and profile transition. [P4 is accepted on the selected corpus](file-reader-design.md#windows-replacement-capture-and-bounded-query)
with source-bound root/native/model/mutation checks, exact parity and unchanged
fixed budgets. Historical real-Linux clauses are excluded; older aggregate
identities and failed flags are preserved.

LLVM MC remains the decoded control/operand reference. Admission requires
matching consumed bytes/length and compatible typed control facts. The
reference boundary constructs no reviewed uses/defs/rules and never calls the
legacy effect preparer. BAP alone supplies reads and replacements. Decoded
register operands bind MOV source/destination footprints, including AL/AH/AX
self-moves whose unchanged value still constitutes a definition. Control or
operand disagreement stops with opaque effects and no assumed fallthrough.
Generic unknowns keep conservative dependencies and cannot establish kills. Direct BIL jump
targets are checked against decoded successors where applicable. An empty
lift is not presumed a no-op; only a reviewed exact no-effect case can receive
that interpretation. Undefined architectural flags remain a separately reviewed
label rather than being inferred from a generic BIL unknown string.

The request validator freezes admitted summaries for the native-default
analysis helper and the independent Rust reference/rollback engine. Rust owns
capture preparation and transport/result validation; the native helper owns
production recovery, dataflow, slicing and supplied finite stateflow.
Report per-site semantic backend/build, AST identity, projection ruleset,
quality and disagreements separately from architectural ISA acceptance.
BAP is now the sole minidump provider by explicit user instruction. The
semantic selector is removed and `fallback` is always null. Fresh validation
qualifies each changed source tier. The active workload replacement has its own
capture and timing contract; default selection does not establish that result.

## Vector-register admission

The [V0–V2 vector admission plan](../../.agents/plans/completed/bap-vector-registers.md) selects
XMM0–15/YMM0–15, exact 128/256-bit widths, canonical YMM backing and low-half
XMM aliases. Vector effects use the existing coarse `state:other` location:
reads retain that dependency and writes may-define it, but never must-kill the
aggregate FP/vector/opmask state. Typed 128/256-bit memory effects retain address
and payload dependencies. This is producer profile `bap-bit-provenance-v4`;
earlier v3 qualification remains historical. General SIMD coverage,
ZMM/opmask state, XMM unwind recipes and
alignment-exception admission remain outside this finite extension.
The [predicate design](justified-branch-pruning-design.md) and
[caller normal-flow contract](caller-semantic-coverage-design.md) own checked
MOVAPS normal admission and its scoped qualification. The separate
[explicit alignment-hypothesis extension](investigation-design.md#explicit-alignment-hypotheses)
adds a [qualified structural-only opt-in](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/alignment-hypotheses/20261016/README.md).
Its additive BAP companion preserves the original guard proof and native input
profile; conditional v2 reports cannot be supplied as completed native analysis.

XMM aliases share a 256-bit YMM backing value within each BIL interpretation;
an XMM assignment preserves its high half, while a YMM assignment expresses
the producer's full-width write, including VEX zeroing when present. Separate
register banks remain distinct internally despite the shared public location.
Every vector write adds a possible definition of `state:other`, and no individual vector write
can establish its definite replacement. Reports retain
`vector-state-coarsened:state:other` as the precision limit.

The decoded destination must match its original protocol register token before
using a filtered public GPR operand. Vector operands are absent from that GPR
list; without this binding, a vector load could incorrectly mark its `RSP`
address base as a possible destination. Native regression and a dedicated mutant
cover this source-review repair. V4 scalar consumers and the strict profile
migration checker accept the declared profile without erasing effect changes.

On 2026-10-13, the [source-bound validation record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-vector-registers/20261013/report.md)
passes all applicable root checks in isolated remote WSL, nine pinned native
producer tests, disagreement checks, six native/capture parity tests, finite
frame-path native checking, model replay and six vector mutants with seven
intended assertion rejections. The native producer exercises SSE loads/stores
and register moves, plus VEX 128/256-bit register moves. Synthetic Windows/Linux
captures establish native/reference parity and preservation of entry origins.

The same Electron frame query remains unavailable after namespace admission:
the captured MOVAPS lift now stops on its explicit alignment-exception branch
(`unmodeled BIL control/special/loop semantics`), rather than `YMM6`. Its caller
graph still has nine nodes and lacks the active call anchor. This finite
extension does not qualify general SIMD, exception handling, XMM unwinding,
the full-dump enumeration gate or replacement-backend performance.

## Admission order and identity

1. Validate protocol identity, exact consumed bytes/length and typed AST budgets.
2. Require compatible independent decoded control and applicable prefixes.
3. Check architectural namespace, scalar/memory types, widths, extraction/cast
   bounds and virtual binding. Validate all alternatives before evaluation.
4. Interpret supported BIL capabilities without an opcode membership gate.
5. Bind instruction-specific obligations: decoded MOV footprints, conditional
   preservation, reviewed undefined flags and direct/indirect control targets.

The implemented producer profile is `bap-bit-provenance-v4`. Existing report envelopes
can carry it and the new `opaque-ordinary` semantic status without a schema
change. Query/semantic identities already bind projection profile and evidence.
I5a explicitly admits v3/v4 for its unchanged six scalar MOV forms; it must
continue rejecting opaque or unsupported semantics. Earlier v2 reports remain
historical and are never rewritten to obtain later-profile acceptance.

Opcode strings are descriptive metadata and may select a reviewed exceptional
obligation; they are not a generic permission list. The exact `90` NOP exception
remains byte-bound. Calls and returns retain the separate opaque all-location
policy rather than deriving callee behavior from their BIL.

## Decision matrix

| Input | Outcome |
| --- | --- |
| Valid supported BIL and compatible control/operands | Projected effects; unknown output values retain dependencies, possible writes and explicit gaps. |
| Valid ordinary control, known architectural namespace and typed data-only BIL with an unsupported scalar operation | `opaque-ordinary`; keep the decoded structural continuation, all tracked uses/may-defs, no must-defs and a data-effect gap. |
| Empty lift except exact `90` | Stop with an unavailable-semantics gap. |
| Unmodeled architectural state, RIP assignment, jump/exception/special uncertainty, unreviewed loop semantics or control disagreement | Stop; no ordinary continuation. Only the separately selected plain v12 three-form contract admits its reviewed loops. |
| Guarded LOCK/REP/segment/address-size semantics | Stop with a specific prefix gap. |
| Malformed AST/type/width, unbound virtual read or invalid extraction | Query failure; no incomplete result publication. |
| Operand or consumed-byte disagreement | Explicit disagreement stop; never opaque ordinary continuation. |
| AST/path/resource exhaustion | Query failure; an operational failure is not an unknown data-effect result. |

Both the ordinary classification and the absence of unmodeled control must be
established. LLVM classification alone cannot turn an empty, malformed or
control-bearing BIL program into fallthrough. A `Special` is not a pure scalar
operation. Unknown architectural namespaces remain excluded even if their
printed instruction looks ordinary.

## Effects and independent expectations

The [P0 freeze receipt](../../tests/bap/fixtures/admission/legacy-source.json)
binds the original projection sources, installed provider and independent
expectations, frozen before runtime edits on 2026-10-09. The
[independent contract](../../tests/bap/fixtures/admission/contract.json) and
[oracle](../../tests/bap/fixtures/admission/oracle.py) retain exact initial
encodings, byte-cell effects, access footprints and unbounded-integer flag
equations. The frozen contract covers the four observed forms and boundary encodings:
SUB64ri8 sign-extended immediate limits, MOVZX32rm8 REX/index/negative displacement,
distinct/self XOR64rr and CMP8mi byte boundaries. Python arithmetic computes
result/CF/OF/AF/PF/SF/ZF independently of Ariadne's provenance evaluator.
Self-XOR's numeric result is zero; a generic unknown AF still retains all
possible input origins and cannot establish a definite flag kill.

MOVZX memory addresses use the base/index/displacement and `memory:any`; a
32-bit destination replaces all eight destination bytes by zero extension.
CMP writes flags, not a GPR. Address-access evidence excludes store payload
dependencies. Stores never must-kill `memory:any`.

P2 paired real encodings include short/long Jcc/JMP and immediate arithmetic.
Generated BIL cases cover composition, typed scalar/memory distinctions and
conditional writes; opcode spoofing is not producer acceptance evidence.

## Core, native and report compatibility

The existing `Ariadne.tla` and effects contracts already admit an ordinary
summary with all uses/may-defs and empty must-defs. No new core action or transfer
rule is introduced. The producer must supply the structural next edge and retain
its preparation/semantic gap. Active model replay therefore remains required,
while an instruction-step ISA/Lean model is not revived.

Native capture admission must bind `opaque-ordinary` to the v3 profile, captured
bytes, ordinary normalized control, all-location possible effects and empty
definite writes. Rust report binding must reject mutated classifications or
effects. Text/JSON/DOT retain the semantic status and data-effect gap. Consumers
and explanations remain partial where an opaque predecessor is relevant.

A producer–opaque–consumer regression must retain both the earlier producer and
the opaque alternative. Native/reference comparison uses the same immutable
request and an available source-bound native helper. Failed builds/timeouts do
not count as mutation sensitivity or native parity.


## Historical-output profile migration

The existing pre-I5a byte oracle remains unchanged. A separate comparison first
builds the frozen pre-change sources in an isolated target directory and requires
all 24 historical output hashes to match that oracle. The v3 outputs then differ
only by the explicit projection-profile labels, the resulting semantic-profile
binding and content-addressed scope/evidence/fact/claim identifiers. All captured
bytes, operands, control, effects, graph/state/slice fields, address uses, claims,
premises and gaps must otherwise match. Native/reference comparisons remain
byte-exact after removing only validated native backend receipts.

The comparison record advances to `ariadne.i5a-cli-equivalence/v3` and reports
`legacyReportsUnchanged` separately from `projectionMigrationVerified`. It does
not relabel changed v3 bytes as the historical v2 outputs. Unsupported ordinary
continuation is tested on its new owned corpus, not normalized away in this
legacy comparison. Mutated effects, claims, capture/tool hashes or unresolved
references must fail the migration comparison.

## Ownership and implementation selection

Rust owns capture parsing, explicit byte trust policy, transport validation,
question construction and report validation. The BAP module owns its immutable
input, BIR attribution, typed graph relation and mutable analysis state. OCaml
passes must implement the actual transitions. Rust's existing `Analyzer` and
`machine_state::Analyzer` remain separate reference/rollback implementations.
Neither an observer nor a transport adapter may call the Rust solver to construct
the purported BAP state.

Native analysis runs in an isolated OCaml executable linked against
a pinned BAP SDK and run as one process per snapshot/query/family. Its `Project`
is constructed from an empty target plus explicitly admitted instruction terms;
default image loading, recursive discovery and speculative scans are forbidden.
The packaged Stage 1 C runtime is retained for lifting and capability probes.
The C header exposes terms/graphs, but lacks `Project.empty`/custom-input and
custom typed-storage constructors available in the reviewed OCaml interface.
It is not a sufficient SDK for this design's custom OCaml passes.

Do not load a plugin built by either installed OCaml compiler into the packaged
runtime without verified compiler/library compatibility. The isolated pinned SDK/executable now freezes source/compiler/library
identities and exercises startup, real Init/Visit state changes and process
cleanup. The [qualification record](#ocaml-foundation-qualification) separately decides
whether every required A0 gate passed before complete A1 recovery.
No user opam switch is modified by A0. The native capability probe is explicitly
not a production analysis helper or an OCaml-pass qualification.

## Immutable requests and finite domains

Two family names are fixed: `recovery` and `stateflow`. Supplied LLVM IR remains
its own existing analysis path. `snapshot` is the exact opaque nonempty snapshot
identity; `query` is a SHA-256 of canonical, length-delimited request data;
`session` is a fresh orchestration token, never a BIR TID or a machine address.
All wire addresses are lowercase, full-width `0x` plus 16 hexadecimal digits.
Map rows and sets have unique keys/elements; no narrowing to signed OCaml `int`.
Use unsigned 64-bit keys (or exact bitvectors with unsigned ordering) in the pass.
String state identifiers preserve distinct identities even for equal valuations.

Canonical query construction uses UTF-8 JSON with recursively sorted object
keys, no insignificant whitespace and unescaped Unicode. Validated set/map-row
arrays are sorted by their canonical JSON encodings; duplicate elements/keys
are rejected before hashing. Concatenate the domain separator
`ariadne.bap-core-query/v1` plus a zero byte, then the UTF-8 byte strings for
snapshot, family, input profile and canonical input, each preceded by its
unsigned 64-bit big-endian byte length. SHA-256 of those bytes is `query`.
This includes semantic evidence identities carried in the immutable input;
process paths and previous/expected results are not input fields. The Rust bootstrap caller constructs this query digest; the helper validates the
complete recovery payload and binds each exchange to the launch identities.

The initial replay profile is `normalized-fixed-input/v1`. It carries no finished
graph, reaching definitions, expected trace, cached observations or prior result.
Its full instruction domain is supplied as immutable premises, as in the model.
Production admission additionally requires the Stage 1 evidence for every site.
A1 may use a bounded reader bridge for lazy preparation; read exchanges are
transport events and cannot masquerade as model actions or mutate observations.
Candidate domains are frozen before model initialization. Extending them requires
a new request/session; A0 does not redefine the current fixed-input model.

| Family | Required immutable input / model constants |
| --- | --- |
| Recovery | `snapshot`, `addresses`, `locations`, `entry_points`, `slice_seeds`, `input_kind`, `captured`, `file_backed`, `trusted_fallback`, total `instructions` rows with `kind`, `fall`, `targets`, `targets_complete`, `uses`, `may_defs`, `must_defs`; `decodable` |
| Stateflow | `snapshot`, `nodes`, `entry_points`, `locations`, total `value_domain`, `state_ids`, total `valuation` and `state_status`, total `initial_states`, immutable typed `structural_edges`, total `uses`/`may_defs`/`must_defs`, `state_steps`, `terminal_transitions`, `complete_sites`, `adapter_obligations` |

Input validation preserves the exact `InputContract` of each model, including
nonempty domains where required, targets inside the finite universe, total maps,
`must_defs` contained in `may_defs`, continuation cardinalities, running entry
states, transition/frame consistency and terminal-outcome status. The core's
general file-fallback contract remains representable for reference replay;
the production minidump profile requires empty file-backed/trusted-fallback sets.
Byte evidence retains exact consumed bytes, VA, capture contributors and hashes;
holes/conflicts remain failed premises, never zero-filled or repaired from a PE.

## Versioned interface and lifecycle

The implemented stream is UTF-8 JSON Lines, schema `ariadne.bap-core/v1`, one request
and exactly one response at a time. Reject duplicate JSON keys, unknown fields,
nonfinite numbers, noncanonical identities and requests over the selected positive byte budget before admission. The default request budget and fixed response frame limit are 8 MiB; the configurable request contract is below.
The implementation must also enforce per-request node/edge/location/state/term
budgets before allocation. Both families have native admission. The production
`captured-fixed-input/v1` recovery profile wraps `normalized` premises and a
`capture` object containing snapshot, artifact/query digests, semantic profile
and a total site map. Site rows bind canonical VA, consumed bytes, captured
availability, semantic status/helper/runtime/AST/projection identities and reader
spans/contributors. Rust verifies the prepared query and reads; native admission
checks the capture-only profile and evidence coverage before creating terms.

Every request contains `schema`, `session`, `snapshot`, `query`, `family`,
monotonically increasing `sequence`, `operation` and `payload`. Every response
echoes the complete identity and sequence, with either typed success or error.
The success envelope includes `generation`, `action_index`, `changed` and the
complete family observation when requested. Protocol failures poison the session;
terminate/reap it and discard unpublished results. A rejected semantic action
leaves every state field, action index and generation unchanged.

| Operation | Effect and restrictions |
| --- | --- |
| `initialize` | Sequence zero only, admits one immutable family input and returns actual `Init` observation at action index zero. Reinitialization in an active process is rejected. |
| `advance` | Payload selects exactly one named model action and its address when applicable. Check phase, guard and deterministic selected address before changing state. Exactly one successful action increments the action index. |
| `observe` | Read-only serialization of current pass state; repeated reads are equal. It cannot advance, normalize away differences or consult expected/reference results. |
| `finish` | Returns an owned result only from `done`; it does not secretly execute remaining actions. Per-action replay retains this operation. |
| `reset` | Acknowledges shutdown and closes the helper process. A fresh process/session is required even for the same VA set; OCaml knowledge-base caches never cross snapshots. |
| `run-batch` | Recovery completion only: runs at most 64 existing scheduled actions and reports progress; the one-million-action limit remains. |
| `result-page` | Retrieves ordered hex pages of one immutable final envelope, at most 256 KiB decoded bytes each and 256 MiB total. No partial result is published. |
| `result-close` | Requires complete transfer, acknowledges the bound result and exits cleanly. The client validates identities, counters, checksum, final state and exit before publication. |

The runtime handshake must report helper/pass ABI, pinned SDK/compiler/library
identities, supported family/profile, implemented operations and limits. Negotiated
capabilities cannot advertise A2/A3 algorithms before their validation exists.
The transport sequence counts requests; the action index counts real model
actions. A trace hash or index alone does not prove that the observed state is
native: A4 replay and A5 mutations must exercise the actual pass implementation.

## Recovery state and transitions

The complete observation is the nine-field tuple in `Specs/Ariadne.tla`:
`phase`, `pending`, `visited`, `decoded`, total `provenance`, typed `edges`,
`obligations`, total `reaching`, and `slice`. Wire map rows use explicit address
keys, including empty values for every candidate. No field is inferred from a
previous response. A result additionally contains `snapshot` and
`missing_slice_seeds = slice_seeds - decoded`.

| Action | Guard, update and mapping |
| --- | --- |
| Init | `phase=recover`, `pending=EntryPoints`; empty visited/decoded/edges/obligations/slice; all provenance unavailable and all reaching sets empty. |
| Visit(a) | Least pending unsigned VA; mark visited/remove pending. Successful admission adds the instruction, byte source, all typed edges/obligations and only local successors excluding visited. Failure records unavailable/decode-failed without a node. Other fields unchanged. |
| FinishRecovery | Only when pending is empty; change phase to dataflow and freeze graph/byte facts. Internal indexes are invisible. |
| Propagate(a) | Least decoded VA with `Incoming(a)` not contained in `reaching[a]`; union its incoming facts into that row only. |
| FinishDataflow | Every decoded row satisfies its fixed-point equation; phase becomes slice, seeded by `SliceSeeds ∩ decoded`. |
| ExpandSlice | Add one dependency layer, simultaneously, from instruction origins reaching locations used at current slice members. |
| FinishSlice | Only at slice closure; phase becomes done. Outstanding obligations are retained in a completed partial analysis. |

`Out(a) = {d in reaching[a] : d.loc not in must_defs[a]} ∪ Gen(a)`.
`Incoming(a)` unions unknown entry origins at roots with `Out` from decoded
local predecessors. Calls retain their `call` edges, but only `summary` edges
carry local recovery/dataflow. A root with a back edge retains entry and loop
origins. Possible writes never remove old definitions. An entry origin is not
an instruction producer and does not grow the backward slice.

The specification permits any enabled action. The adapter implements the same
lowest-VA schedule as the Rust reference for comparable full traces. Asking for
another enabled address is a rejected action under this deterministic profile.
No action is enabled at done. Finish/observe remain read-only there.

## Stateflow state and transitions

The actual mutable tuple is `phase` and total `states_at`, initialized from the
total `InitialStates` map. The observation also serializes derived views:
immutable structural edges, feasible/provably-infeasible/unknown edges, reached
terminal transitions, not-reached nodes and obligations. Derive them directly
from the current OCaml state and fixed input, not from the Rust reference.

`Propagate(a)` chooses the least node whose incoming state IDs grow, unioning
initial IDs with `after` IDs from steps whose `before` ID reached their source.
`FinishStateflow` requires every node's equation to be equal and changes only
phase. Infeasible edges are empty before done; at done, absence is infeasible
only for a reached source in `CompleteSites`. All other absent structural edges
remain unknown. Structural edges are never deleted. Reached fault/return/stop
transitions remain terminal results, not ordinary successor states. Catalogue
IDs with equal valuations remain distinct and running-only propagation is kept.

## BIR attribution and graph preservation

Maintain an explicit registry keyed by session-local TID: term class, origin
kind, source instruction identity or null, generation and derivation parents.
Every machine-origin term maps to the exact snapshot/VA/consumed-byte evidence;
one instruction may own multiple BIR blocks/definitions/jumps. Phi/temporary or
helper-generated terms are `synthetic`, have no invented VA/bytes, and retain
parent attribution. An unavailable target is a typed graph endpoint, not an
invented BIR instruction. Native TID allocation order is not a replay observable.

The authoritative analysis edge relation is a set of `(src VA, dst VA, kind)`.
Several kinds may connect the same pair. Treat BAP's BIR CFG as a structural view
unless its parallel-edge semantics are independently proven equivalent. A call
and a summary, or taken and fallthrough edges, must never collapse into one fact.
No SSA conversion, block coalescing or dead-code elimination is enabled by default.
Any future transformation must preserve registry attribution and model observables.

The pinned native probe actually inserted two TID-graph edges with distinct
labels but identical endpoints: only one remained. It also observed immutable
graph versions with 0/1/2 nodes and full `0xfffffffffffffff0` address attribution.
These are capability observations, not model actions. The independent typed
edge relation is therefore required, rather than relying on this TID graph to
encode the model's parallel edge kinds.

## Acceptance boundaries

A0's executable envelope/attribution checks and native term/graph probe establish
contract and runtime-facility evidence only. They do not establish a migrated
solver. A1 implements reader-scoped recovery; A2 adds genuine origin/slice passes;
A3 adds finite stateflow; A4 binds real helper actions to generated replay; A5
tests mutations in those passes and connects reports; A6 qualifies adoption.
The already accepted unlimited timing policy still requires valid measured
workload evidence; older Rust results do not qualify the new implementation.

## Implemented ABI 2 wire details

The standalone helper advertises `recovery` and `stateflow` families and both
fixed-input profiles. Recovery supports all six model actions; stateflow supports
Propagate and FinishStateflow. `step` chooses one actual native enabled action;
its optional action name must match that selection. `advance` additionally
checks the supplied address. `observe`, `finish` and `reset` are read-only;
finish requires done and reset acknowledges before a clean process exit.
The default request and fixed response frame limits are 8 MiB; address, location and potential typed-edge sets are
bounded at 65,536 entries. JSON nesting is bounded at 64 levels.
Production recovery completion uses the batch/page extension above. Generated
per-action replay and stateflow retain their original observation path. The
transport checksum checks consistency; existing SHA-256 request/helper identities
retain their trust roles. Overflow, malformed pages and failed exits poison the
session without automatic Rust fallback.

## Configurable native request limit

The [T0–T4 execution plan](../../.agents/plans/completed/native-request-budget.md) implements the user-authorized configurable request limit, following the [G5 captured retry](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/guard-budget-configuration/20261014/README.md). Guard proof budgets and transport request budgets are independent; the larger captured report reached the previous fixed inbound 8 MiB limit.

`CoreConfig.max_request_bytes` defaults to 8 MiB and accepts caller-selected positive finite values without a default-based ceiling. The CLI option is `--bap-core-max-request-bytes N`. Host enforcement and native input reading both count the complete JSON line including its newline. Native launch receives a nondefault value through `--max-request-bytes DECIMAL`, parsed with checked unsigned-64 arithmetic. Zero, malformed and overflowing values are rejected. The chosen budget does not become an allocation reservation.

ABI 2 adds `configurable_request_bytes: true` and the default `max_request_bytes` to the source-bound build manifest's handshake. Runtime ready declares the exact effective request budget. The host validates that declaration against its chosen configuration and all retained build capabilities. Legacy helpers remain usable with the default; selecting a nondefault budget requires the new capability. Keep the immutable build manifest in backend identity and record the selected request budget separately. Transport configuration does not change semantic input/query digests or model actions.

Responses remain limited to 8 MiB through `MAX_FRAME` and the native outbound reader/writer contract. Completion paging, aggregate result budgets, JSON depth, normalized input constraints, proof validation and protocol poisoning retain their existing behavior. Raising request capacity does not justify incomplete candidate coverage or promise a successful full-dump path query. Exact boundary, capability, malformed-input and larger-request native controls qualify this extension separately from historical 8 MiB transport evidence.

Instruction map rows contain `address` plus the instruction fields above.
Provenance rows are `{address, source}`; reaching rows are
`{address, definitions}`. Both maps include every candidate, including empty
reaching sets. Definition rows carry `loc`, `site` and `origin`. The nine state fields remain separate from the response's
`attribution` rows. Generation is one for this one-process/one-query lifetime;
request sequence and model action index advance independently.

The OCaml record owns recovery state and its reader-scoped BAP project. A successful
Visit adds a block and subroutine term attributed to the admitted machine VA;
these are normalized-summary attribution terms, not a new instruction lift.
The program term has synthetic ancestry without an invented VA. Term addresses
and snapshot attributes are read back from BAP values. Captured-profile block
and subroutine terms also store and return the admitted capture-evidence row.
The Rust facade checks term uniqueness, decoded-site coverage, captured evidence,
synthetic ancestry and identity before exposing a completed result. A sealed
`AnalysisView` lets investigations and stateflow preparation reuse that result;
it does not construct or execute a Rust reference analyzer. No filename or image loader
is supplied to the helper. The packaged Stage 1 lifter remains separate.

The SDK uses OCaml 4.12.1 and the full BAP revision in
[`sdk.lock.json`](../../native/bap-core/sdk.lock.json), with a frozen opam export.
The source revision matches the selected Stage 1 source archive; binary/plugin
ABI equivalence to the packaged runtime is not claimed.

## Evidence boundaries

Source/API assessment, implementation checks and runtime qualification answer
separate questions. The sections below preserve their dated decisions and
original JSON/archive links; moving documentation does not refresh a source
inventory. The [initial integration record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-stage1-validation.json)
retains its missing original Windows capture. Later selected Windows P4 acceptance
excludes the remaining real-Linux clauses without changing their failed flags.
Default selection, unlimited timing and transport completion do not resolve
semantic/provenance gaps or qualify separate investigation budgets.

The earlier [finite-model delivery](typed-replay-design.md#finite-corpus-and-claim-boundary) recorded 32 cases,
64 complete traces, 326 observations and 15 mutant mismatches for its pinned
Rust models/adapters. Those records do not qualify a changed producer/native
solver. The [historical instruction-step ledger](https://github.com/NzSN/Ariadne/blob/01ae404e8c8556966e219118945082ff8e213f7e/Specs/AMD64/user64-coverage.json)
recorded an unclosed 0/49 gate with decoded-form, flags/frame, fault/commit,
instruction-boundary, TLA–Lean and projection obligations. The
[assurance decision](semantic-assurance.md) retired that ISA/Lean track;
analysis-level TLA+ replay and mutation checks remain active.

## Backend usage

`ariadne::bap` is the sole production minidump semantic adapter. Core-only Rust
builds activate no external dependencies and the library forbids unsafe code.
Follow the [lifter setup](../../native/bap/README.md) and
[isolated analysis SDK guide](../../native/bap-core/README.md); build the independent
MC reference with matching LLVM headers. The normal Linux-hosted setup is:

```sh
python3 native/bap/setup.py
bash native/bap/build.sh
bash native/llvm_mc/build.sh
python3 native/bap-core/setup-sdk.py
python3 native/bap-core/build.py --output target/bap-core-native
cargo build --offline --locked --release --manifest-path Cargo.toml
target/release/ariadne-minidump tests/input/fixtures/stage_b_linux.dmp \
  --decoder-reference target/ariadne-llvm-mc --entry 0x401000 --seed-exception-rip \
  --bap-helper target/ariadne-bap-lift --bap-runtime tmp/bap-setup/stable \
  --output-dir tmp/bap-example
```

| Setting | Meaning and precedence |
| --- | --- |
| `--bap-helper`, `--bap-runtime` | Override `ARIADNE_BAP_HELPER` and `BAP_RUNTIME_ROOT`, then repository build/extraction defaults. |
| `--analysis-backend bap` | Native default; `--bap-core-dir` overrides `ARIADNE_BAP_CORE_DIR`, otherwise `target/bap-core-native`. |
| `--analysis-backend rust` | Independent reference/rollback analysis using the same BAP semantics. Failure never selects it automatically. |
| `--decoder-reference` / `--decoder` | Independent LLVM decoded-fact checker; the latter remains an argument alias. Neither selects instruction semantics. |
| `--semantics-backend llvm\|bap` | Removed; rejected with an explicit diagnostic. The compatibility report field `fallback` is always null. |

Native base reports include a validated backend/build receipt; explanation-only
and assessment-only modes retain their schemas. Every attempted lift records
provider/helper/runtime/AST identities, projection, quality and gaps in text,
JSON and DOT. `external_lift` means exercised external semantics, not ISA-step
acceptance. Calls/returns remain opaque; ordinary data-only gaps and control
stops follow the decision matrix above.

`Backend::prepare` consumes captured batches. One backend belongs to one
snapshot/target and reuses one checked LLVM reference process; standalone LLVM
preparation remains one-shot. Runtime validation uses bounded streaming workers
to hash every pinned compiled file at construction and helper startup.
`Backend::finish` must require clean lifter and decoder exits before publication;
drop kills and reaps an abandoned process. A new backend creates a new knowledge
base. `Metrics` separates runtime validation, reference decoding, startup,
lift/transport validation and projection; benchmarks additionally time shutdown,
analysis and all report formats.

## Pinned projection source review

This is the historical source review and diagnostic evidence that motivated the
implemented walker. It is separate from finite corpus qualification. The selected
BAP source is `baa9022` (full SDK revision below); the installed library reports
`2.5.0-alpha` and CLI `2.5.0-alpha+baa9022`. The
[release header](https://github.com/BinaryAnalysisPlatform/bap/releases/tag/v2.5.0)
was extracted to `tmp/bap-setup/stable/usr/local/include/bap.h`.
The pinned [x86 option](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_main.ml)
defaults to `merge`; production explicitly selects `legacy`.
The [modern target fallback](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_targets.ml)
and [dispatcher](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_backend.ml),
and legacy `No_semantics` in
[x86_lifter.ml](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_lifter.ml),
can return `Ok []`. A successful decode with empty BIL therefore proves neither
no effect nor ordinary continuation. The modern
[MOV plugin](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_mov.ml)
and [x86-64 Lisp file](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/semantics/x86-64.lisp)
do not establish general instruction coverage.

Both mode probes used `bap_init2`, explicit `--x86-lifter`, only `llvm`/`x86`,
and `bap_disasm_basic_next` at `0x401000`:

| Diagnostic | Exact observations |
| --- | --- |
| Modern nonempty | `4889d8` MOV64rr, `88d8` MOV8rr AL, `88dc` MOV8rr AH, `b878563412` MOV32ri, `488b448b08` MOV64rm, `488903` MOV64mr. |
| Modern empty | `480fbec0` MOVSX, `0fb6c0` MOVZX, `4801d8` ADD, `4839d8` CMP, `4811d8` ADC, `480f45c3` CMOV, `488d4308` LEA, `50` PUSH, `58` POP, `7502` Jcc, `e800000000` direct CALL, `ffd0` indirect CALL, `c3` RET, `f00118` LOCK ADD, `f3a4` REP MOVSB. |
| Explicit legacy | Every preceding modern-negative form produced nonempty BIL; so did `48d1e0` SHL RAX,1, `48d3e8` SHR RAX,CL and `48f7d0` NOT RAX. Broader sample coverage did not prove correctness or authorize guarded forms. |

The pinned [AST](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/lib/bap_types/bap_bil.ml)
defines `Load(mem,idx,endian,size)`, `Store(mem,idx,value,endian,size)`,
`Let(var,definition,body)`, `Ite(condition,then,else)`, statement `If` and `While`.
Constructed-node probes against the matching header/library established:

| Tag | Observed C getters | Required traversal |
| --- | --- | --- |
| `LET` | `var` binder, `rhs` definition, `exp` body; `lhs` null | Bind scope; visit definition and body. |
| `ITE` | `exp` condition, `lhs` then, `rhs` else | Read condition; join alternatives. |
| `BINOP`, `CONCAT` | `lhs`, `rhs` | Visit both operands. |
| `UNOP`, `CAST`, `EXTRACT` | `exp` operand | Preserve justified bit ranges. |
| `STORE` | `mem`, `addr`, `rhs` payload; `exp` null | Visit address/data; preserve earlier memory origins. |
| Statement `IF` | `exp`, `true_stmts`, `false_stmts`; `stmts` null | Traverse both branches; `stmts` belongs to `WHILE`. |
| Statement `JMP` | `jmp` target; `exp` null | Read indirect target and retain control. |

Lifted CMOV/Jcc/SHL/CALL/RET/REP nodes confirmed `ITE`/`IF`/`JMP`/`WHILE`
accessors. Using `bap_exp_lhs` for `LET` or `bap_stmt_stmts` for `IF` loses
inputs. These are facts about this pinned binary, not every BAP release.

**EXTRACT uses swapped numeric getter positions in this packaged C ABI.**
The AST is `Extract(hi,lo,exp)` and the
[printer](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/lib/bap_types/bap_exp.ml)
prints `hi:lo[exp]`. Lifted `88dc` prints `63:16[RAX]` but returns
`hibit=16,lobit=63`; its `7:0[RAX]` child returns `hibit=0,lobit=7`.
Constructing `bap_exp_create_extract(8,15,var)` prints `15:8[var]` and reports
`hibit=8,lobit=15`; arguments `(15,8,var)` print invalid `8:15[var]`.
Use `actual_hi = bap_exp_extract_lobit(e)` and
`actual_lo = bap_exp_extract_hibit(e)`, then enforce
`0 <= actual_lo <= actual_hi < operand_width`. This is not endianness. Reject
invalid ranges or changed binding identity; never repair with `min/max`.
These ranges were observed by the historical diagnostic probes. The source
review recommended dedicated fixtures for both lifted ranges and the
constructed range; that recommendation alone does not establish regression
coverage of constructed nodes.

Alias rules in modern
[x86_tools_reg.ml](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_tools_reg.ml)
and legacy `assn_s` preserve untouched AL/AH/AX bytes and zero-extend EAX.
Independent original expectations were:

| Bytes | Expected effects |
| --- | --- |
| `4889d8` | Read all RBX bytes; replace all RAX bytes. |
| `88d8`, `88dc` | Read BL; replace RAX byte 0 or byte 1 respectively. |
| `b878563412` | Replace all RAX bytes, zeroing the upper four. |
| `488b448b08` | Read RBX/RCX address bytes and `memory:any`; replace all RAX bytes. |
| `488903` | Read RBX address/RAX payload; may-write memory with no memory must-kill. |

Unsigned and signed casts respectively zero-extend or depend on the sign bit.
Modern [memory construction](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_tools_mem.ml)
uses base, scaled index, displacement and applicable FS/GS base; the legacy
admitted address forms require independent review. Generic `Unknown`/`Special`
do not prove no effect. [Flag construction](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_tools_flags.ml)
and [bit-test semantics](https://github.com/BinaryAnalysisPlatform/bap/blob/baa9022/plugins/x86/x86_btx.ml)
show why a flag assignment alone does not establish a defined value.

Legacy observations retain these precise limits: MOVSX sampled
`RAX := extend:64[low:8[RAX]]`; MOVZX nested zero padding; ADD/CMP wrote
CF/OF/AF/PF/SF/ZF; ADC read CF, while INC/DEC preserve CF. LEA used no memory;
NOT wrote no flags. CMOVNE's `Ite(~ZF,RBX,RAX)` reads ZF and permits a write
without unconditional origin removal. Variable-count SHR reads RCX, preserves
flags at count zero and emits `Unknown[after-shift]` for AF and sometimes OF;
undefined-flag labels require reviewed forms. PUSH/POP use RSP/memory; Jcc is
an `If` containing `Jmp`; CALL pushes a return address but supplies no callee
summary; RET reads the stack target. LOCK ADD printed ordinary ADD BIL and REP
MOVSB contained `While`, so neither can bypass prefix/control guards.
`0f05` SYSCALL produced `Special call(syscall)`; `0fa2` CPUID wrote unknown
GPR values; `0f0b` UD2/TRAP had empty BIL. No concrete CPUID value or TRAP
fallthrough follows. These diagnostics supported later fixtures; current
admission still follows the explicit failure matrix.

## Reproduction

Native tests are ignored until the pinned lifter/reference/SDK are available;
qualification invokes them and treats missing prerequisites as failures. Existing
Graphviz, TLC, MirrorRust and required captured artifacts must match their pins.
The Linux qualification runner configures a local Graphviz bundle when present;
otherwise supply `ARIADNE_DOT` and its required library/plugin environment.
A Windows workload means a Windows-origin dump, not a Windows-hosted Ariadne run.

```sh
python3 native/bap-core/setup-sdk.py --check
python3 native/bap-core/build.py --output target/bap-core-native
cargo test --offline --locked --release --manifest-path Cargo.toml -- --include-ignored
python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --output /new/workload-directory
python3 tools/check_bap_core.py --output target/bap-stage2-recheck
```

The core checker builds a second clean helper, runs root/Clippy/native kernels,
capture/stateflow tests, replay, mutations and producer/Stage E regressions.
A native decision requires `passed`, `stage2Qualified`, `defaultNativeVerified`
and `sourcesStable` all true, plus a verified manifest binding its report.
Use new output directories and separate replay/mutation build trees. Source,
tool or dependency changes require fresh applicable checks; a matching binary
name does not suffice. Run aggregate and evidence verification under the recorded
[snapshot wrapper](../../tools/with_mirrorrust_snapshot.py):

```sh
python3 tools/with_mirrorrust_snapshot.py run \
  --snapshot target/i5b-dependency-snapshot \
  --sha256 a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854 -- \
  python3 tools/check_bap_admission.py --output target/bap-admission-new-run
```

The native archive retains exact dependency bytes in
`dependencies/mirrorrust-snapshot.json`; the live sibling checkout is separate.
For a matching copy of the controlled checksum pin or an explicitly reduced run:

```sh
ARIADNE_BAP_WINDOWS_DUMP=/absolute/path/to/replacement.dmp \
  python3 tools/check_bap_semantics.py
python3 tools/measure_bap.py --windows-dump /absolute/path/to/replacement.dmp \
  --output /new/explicit-workload-directory
python3 tools/measure_bap.py --skip-windows --output /new/implementation-directory
python3 tools/check_bap_semantics.py --workload-record /new/workload-directory/report.json
```

The default benchmark verifies and materializes the
[checksum input bundle](../../tests/input/fixtures/workloads/bap-windows-workload-case.json).
`ARIADNE_PRIORITY4_DUMP` no longer selects it; I4 has its own
`ARIADNE_I4_WINDOWS_DUMP` override. Skipped or malformed workload evidence cannot
satisfy full acceptance. Active P4's separately selected 29-start replacement
and excluded Linux clauses remain defined by its plan and acceptance decision.

## BAP-only delivery

The [2026-10-01 removal record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-only-removal-validation.json)
and [manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-only-removal-evidence-manifest.json)
retain 16/16 gates, 93 stable sources, 16 detected producer/adapter mutants
(including partial self-move definitions), and eight TLC cases/99 observations
comparing all nine fields. Its nested Stage E run passed 12 gates over 251
sources/artifacts. That release used Rust analysis and the v2 corpus of 41 exact
cases/30 admitted forms, including immediate stores, dword loads/stores and TEST.
Both Stage B inputs and NOT retained their producer slices. The real Linux query
had 34 starts, 45 edges, a 28-site slice and one obligation: 25 projected sites,
nine opaque calls/returns, one control disagreement and nine unattempted
references. [CLI samples](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-only-cli.csv) and
[phase samples](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-only-stage.csv) retain one warm-up,
five release repeats, spread, RSS and startup/reference/lift/projection/analysis/
render timings. These checks did not qualify the absent original Windows pin or
its former 2,000 ms condition. BAP default selection was separately authorized.

## Workload evidence repair

The 2026-10-03 R0–R2 repair fixed `measure_bap.py` reusing `before` for both the
source inventory and seed-definition list, which falsely marked stable Windows
runs unstable and serialized the wrong `sourceHashes` type. Separate
`source_hashes_before` and `seed_definitions` preserve both values.
Workload v2 retained raw warm-up/measured samples, one captured preparation per
decoded site and the independent address producer. The shared validator checked
artifact/query, target/release/provider, output hashes, counts, samples and
recomputed medians, rejecting old/malformed/nonfinite/negative evidence.
Aggregate v3 independently derived the result rather than trusting stored flags;
reuse required complete current source/tool inventories. Under its historical
inclusive 2,000 ms policy, absent/invalid/over-budget evidence could never satisfy
full exit even when implementation gates passed.

The [repair record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-windows-workload-validation.json)
and [238-entry manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-windows-workload-evidence-manifest.json)
retain 17/17 implementation gates and 177 stable sources:

| Tier | Historical exercised result |
| --- | --- |
| Controlled Python | 39 checks: 15 real producer-entry, 14 validator and 10 aggregate-entry tests, with native subprocess/evidence stubs. |
| Native | 41 byte cases/30 forms, helper/projection/transport/CLI/rendering checks. |
| Fresh model / mutations | Eight cases/99 nine-field states with 162 sources; all 16 intended mutations with 159 sources and unchanged observers. |
| Fresh workloads | Stage B Linux/Windows, NOT and real Linux; one warm-up/five repeats, phase samples, 167 sources and six tools. Medians 1,027.67 / 1,072.66 / 1,027.82 / 1,830.96 ms. |
| Reused Stage E | Twelve gates, all 315 source identities and native IR/MC/Graphviz hashes verified; not freshly run here. |
| Supplemental Windows | Controlled partial/full captures: two starts, one-site slice; phase medians 1,932.24 / 1,925.79 ms. These are separate from the original pin and I5a numeric phase. |

A missing Graphviz environment failed the initial aggregate; the harness adopted
Stage E's local-bundle configuration. After repair, native/controlled gates reran
and independently stable model/mutation/workload results were reused by identity.
The initial failure and source changes remain diagnostic evidence; raw customer
dumps/executables were excluded. The final original-corpus flags remain
`implementationGatesPassed=true`, `stage1ExitPassed=false`,
`stage2PrerequisiteSatisfied=false`, `defaultPromotionEligible=false`, Windows
status `unavailable`.
The [original pin](../../tests/input/fixtures/workloads/priority-4-real-capture-case.json) was
`f13d18cd-9ade-4eff-947c-15a649b636fa.dmp`, 2,028,400 bytes, SHA-256
`4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86`;
entry/seed/producer `0x7ff6451d52d0` / `0x7ff6451d530f` / `0x7ff6451d530b`.
The user confirmed its loss and authorized the replacement below.

## Windows workload replacement

The controlled `crashpad-windows-checksum-98-v1` is a real Windows AMD64 Crashpad
capture analyzed on Linux, not a manually edited dump or reconstruction of the
old crash. Its [recipe](../../native/crashpad-demo/README.md) and
[replacement plan](../../.agents/plans/completed/bap-windows-repin.md) freeze 98 starts: setup,
eight checksum rounds, indexed loop, conditional diamond, spill/reload and RCX
producer before a four-byte null write. All rounds feed the address computation.

| Bound item | Value |
| --- | --- |
| [Active checksum pin](../../tests/input/fixtures/workloads/bap-windows-workload-case.json) | [Input archive](../../tests/input/fixtures/workloads/windows-inputs.tar.gz): 399,636 bytes, 23 verified entries. |
| Partial dump | 217,936 bytes; SHA-256 `1bd80af7a739471a7026776bfb37cbbe5953d01ad122e7cf7db0392f84da0b0a`. |
| Entry / fault seed / RCX producer | `0x00007ff7382f4840` / `0x00007ff7382f49b4` / `0x00007ff7382f49b1`. |
| Function / handler | 379 bytes, 98 reviewed starts; Crashpad revision `7a884c25c84c46352fc6f16ef0a798ece2b77e84`. |

Pinned Clang/`llvm-ml`, Windows SDK/MSVC libraries and an isolated compatibility
setup built the process; uploads were disabled and the environment minimal.
Missing-handler/mode/profile controls exited before witness creation; the default
null-write profile also passed its independent inspector. The inspector checks
all captured function bytes against both the PE and byte oracle, branch targets,
four labels, input/checksum, PID/module and exception/context: a four-byte write
to zero with RAX/RCX zero. The PE supplies comparison only, never fallback bytes.

The [replacement record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-windows-repin-validation.json)
and [manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-windows-repin-evidence-manifest.json)
retain 17/17 implementation gates, 178 stable aggregate sources, 59 decision
controls, nine inspector controls, native integration and five fresh release
workloads. Result: 98 starts/99 edges/90-site slice/zero obligations, no missing
seed and all eight RCX origins at the independent producer. Model (162 sources),
16-mutant (159 sources) and 12-gate Stage E (315 sources) results were reused by
full source/applicable tool checks; the workload bound 168 sources/six tools.
The archive verifies 199 entries and the delivery's 192-source inventory.

Its then-active workload v3/aggregate v4 required median ≤2,000 ms. One warm-up
and five repeats measured 10,667.76 ms (10,408.02–10,821.89), so
`implementationGatesPassed=true` and `valid=true` coexisted with
`targetMet=false`, `stage1ExitPassed=false`, `stage2PrerequisiteSatisfied=false`.
Separate phase medians were reference 7,572.13 ms, startup 1,178.30 ms, Rust
analysis 69.61 ms and reports 397.33 ms; they are not an additive CLI decomposition.
Monotonic `perf_counter_ns` determined eligibility. Ancillary GNU `time` differed
by about 0.70/0.73 s on two samples; both readings still failed the budget.
The later policy changed acceptance, not these historical measurements.
Historical Priority 4 remained unchanged; I4 separately repinned this capture
and retained its own fixed budget.

## Unlimited timing policy

The user-authorized 2026-10-03 policy remains active for BAP workload qualification.
Workload `ariadne.bap-workloads/v4` requires
`windowsWorkloadTimingPolicy: unlimited` and `windowsWorkloadBudgetMs: null`;
aggregate `ariadne.bap-only-removal/v5` applies the same rule. Missing fields,
a numeric budget or infinity are rejected. Release measurements still need one
warm-up, at least five finite nonnegative raw samples and a matching recomputed
summary. Valid evidence reports status `unlimited`, `valid=true`, `targetMet=true`
while retaining its median. Invalid evidence or implementation failure still
blocks full exit; operational timeouts/resource limits remain separate.

The [policy record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-unlimited-validation.json) and
[manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-unlimited-evidence-manifest.json) retain
17 gates, 60 controls and 178 stable sources. Native integration/five workloads
reran; model/mutation/Stage E records were reused only after complete source/tool
checks. The new median was 3,111.33 ms with unchanged analysis binaries: no
optimization was claimed. Its `stage1ExitPassed=true`,
`stage2PrerequisiteSatisfied=true`, `stage2Started=false` are historical scopes.
The frozen dump/query/bundle remained unchanged. I4's 2,000 ms CLI ceiling and
I5a's 1,500 ms CLI/10 ms phase limits are separate and were not waived.

## A0 capability evidence

The first 2026-10-03 [A0 record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-stage2-a0-validation.json)
and [manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-stage2-a0-evidence-manifest.json) bind
15 contract/probe files and compiler/helper/header/library identities. At that
run the prerequisite's 178-source/tool inventory matched. Seven admission tests
covered envelopes/actions, identity/sequence, unsigned canonical addresses,
duplicate JSON keys, frame/nonfinite/overflow bounds, same-VA terms and invalid
synthetic/cyclic ancestry. They did not implement an analyzer.
Two fresh C++ probe processes observed identical high-VA `0xfffffffffffffff0`
round-trips, persistent TIDs, multiple terms for one VA, graph versions with
0/1/2 nodes, read-only observations, and an empty fresh graph. Two parallel labels
collapsed to one edge, requiring Ariadne's separate typed relation.
The exact C header lacked `bap_project_empty`, custom-input construction and a
sub-builder result accessor; extraction had zero `.cmi`/`.cmxa` SDK files.
`passed=true` covered these checks only: `a0ExitPassed=false`,
`stage2Started=true`, `stage2Qualified=false`, `implementedAlgorithms=[]`.
No nonexistent solver received replay/mutation credit.

## OCaml foundation qualification

The separate SDK uses OCaml 4.12.1 and BAP
`baa902209ee4be975bdd8db7d1160b0a0ec2831f`, with metadata/export pins distinct
from its installed inventory. It does not load plugins into or claim ABI
compatibility with the packaged lifter. Historical OQ0–OQ6 implemented validated
immutable recovery input, nine-field Init, unsigned-lowest Visit and real BAP
term attribution; the handshake exposed only `initialize`, `advance:Visit`,
`observe`, `reset`. Reset required a clean exit. There was no completion or
production-native selection at this foundation stage.

The [qualified foundation](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-ocaml-qualification.json)
and [327-entry manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-ocaml-evidence-manifest.json)
bind 199 stable sources, two equal helper builds/observations and seven actual
code mutations rejected by intended assertions. Six native test groups cover
ordinary/conditional/call/jump/self-loop/indirect/terminal input, missing/decode
failure, high addresses, captured/file provenance, non-root seeds, attribution,
rejected actions, fresh/concurrent sessions and process/identity/sequence faults.
Rust reference comparisons occur only in external tests. Refresh with
`python3 tools/check_bap_ocaml.py`; ignored native tests require `--ignored`.
Separate `sdkQualified`, `helperBuildQualified`, `nativeStateExchangeQualified`,
`transportLifecycleQualified`, `bootstrapMutationChecksPassed` and stability
compose `a0ExitPassed=true`; `stage2Qualified=false` remained correct.

The [earlier formatting-blocked record](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-ocaml-history/2026-10-03-format-blocked/bap-ocaml-qualification.json)
is preserved. After explicit user approval, only MirrorRust's
`tests/protocol.rs` was formatted with Rust 2021; fresh root/effects/minidump/
Stage E/producer/A0 checks then passed. The failed aggregate was not relabeled.

## Native qualification

Native A1–A6 qualification covers reader-scoped recovery/capture attribution,
origin/slice passes, finite stateflow/terminal classification, 12 recovery traces
with 168 observations and 32 stateflow traces with 162 observations. Wrong
query digests dispatch zero observations. Twelve native algorithm mutants must
produce real observation mismatches; boundary mutations are a separate tier.
Five historical workloads were Linux/Windows/NOT fixtures, 34-start Linux and
98-start Windows; each backend received one warm-up/five release measurements.
Text/JSON/DOT match after validating and removing only the native receipt.
Default output matches explicit BAP, while explicit Rust remains functional.

| Retained record | Scope |
| --- | --- |
| [2026-10-04 adoption](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-core-history/2026-10-04-adoption/bap-core-qualification.json) | Explicit-native candidate first passed 19 gates; adoption and its archive/manifest remain byte-identical in history. |
| [Pre-I4 refresh](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-core-history/2026-10-05-before-i4-repin/bap-core-qualification.json) | Original archive/manifest preserved before the I4 pin refresh. |
| [2026-10-05 standalone](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-core-qualification.json), [archive](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-core-evidence.tar.gz), [manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-core-evidence-manifest.json) | Twenty gates, 632 stable sources, 1,355 verified entries; 13 protocol/snapshot controls, two equal clean builds, native/capture/investigation/stateflow/root/Clippy and producer/Stage E regressions. Its inventory is historical. |
| [2026-10-07 I4 aggregate](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/i4-performance-qualification.json) | Newer 20-gate/712-source native refresh at `records.regressions.records.native-core-stage-e-input-bap-regressions`; its `records.stage1-regression` is the separate producer refresh. |

`artifacts/0/default-path-smoke-check.json` binds a successful no-backend-flag,
no-helper-directory-override invocation to the same final release executable
and both clean helper manifests. Product comparisons cover all five workloads
and three report formats. Nested producer timings explicitly select Rust and do
not establish native acceptance. Historical 2026-10-05 Rust/native medians (ms)
were Linux fixture 895.39/964.30, Windows fixture 921.57/957.16, NOT 900.27/964.70,
real Linux 1,566.21/2,248.97 and Windows 2,967.88/5,020.08. They establish no
current performance comparison; later preparation/transport changes have their
own evidence. This is Linux-hosted workspace qualification including Windows
captures, not packaged cross-platform release or universal refinement.
See the [evidence guide](../../tests/README.md) for archive interpretation.

## Documentation audit

The [2026-10-09 audit receipt](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-documentation-audit.json)
is a retained identity/documentation check, not fresh runtime qualification.
It inventoried 111 BAP-related Markdown files; navigation then covered 133
connected documents/2,360 links. The 41-case corpus and 107-file Rust layout
checks passed. At that pre-v3 snapshot, projection used a finite whitelist and
unsupported data stopped recovery; SUB64ri8/MOVZX32rm8/XOR64rr/CMP8mi were not
admitted. Current v3's 58 cases/37 forms and opaque ordinary continuation come
from the later campaign, not this audit.

The audit found matching nested native/producer/I5b/I5a records at the paths
above: respectively 20 gates/712 sources, 17/255, 18/295 and 14/286. Producer
`stage2Qualified=false` limits that campaign and does not override native adoption.
Twelve installed tool hashes and compiled provider pins matched; dependency
manifest was `a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`.
The [I4 archive](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/i4-performance-evidence.tar.gz) and
[manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/i4-performance-evidence-manifest.json) verified
all 3,625 members including exact compressed nested archives. Older standalone
inventories remained historical despite matching helper binaries.

Corrected guides named explicit legacy selection, the real `ocamlfind ocamlopt`
build instead of proposed Dune files, complete ABI 2 beyond Init/Visit, explicit
Rust selection in library examples and reused production LLVM sessions versus
one-shot standalone decoding. The then-current I4 result was 1,692.696 ms against
2,000 ms and Linux phase 182.924 ms against 250 ms; separate I5a budgets remained.
The audit changed no runtime/model/fixture/qualification-record bytes. Its checks
(`python3 tools/check_doc_links.py`, `git diff --check`,
`python3 tests/bap/fixtures/make_corpus.py --check`,
`python3 tools/check_rust_layout.py`) supplied documentation/corpus/layout evidence
only. Later source/profile changes need their own exact identity checks and
applicable qualification; this consolidated guide is not a frozen source record.

## Admission checkpoint

The [initial 2026-10-10 checkpoint](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/checkpoint.json)
retains P0–P3 delivery and **unaccepted P4**. The installed runtime/bridge and
isolated SDK were reused without rebuilding BAP or installing another SDK.
The four new forms had 13 boundary encodings on Linux/Windows, 104 independent
numeric/flag/zero-extension comparisons and 58 exact cases/37 projected forms.
CLC remained an empty-lift gap; repeated CMP BIL loads kept separate attribution
while matching one decoded byte-operand footprint. Opaque producer–consumer
checks retained both earlier and opaque origins and partial text/JSON/DOT gaps;
direct native tampering bypassed Rust prevalidation.

| Initial tier | Exercised result |
| --- | --- |
| Contract / admission | Frozen P0, four retained rejected queries, composition/hostile namespace/type/control/prefix/resource checks, eight producer tests and expanded protocol/disagreement controls. |
| Native / model | Five ignored capture/parity/report/tampering tests and stateflow CLI; 330 replay observations with zero wrong-digest dispatches; 12 algorithm and eight boundary mutants; eight model cases/99 nine-field states. |
| Root / decisions | Default/core-only/fmt/Clippy/layout checks (109 Rust files), 60 controlled producer/validator/aggregate tests. |
| Migration / workloads | Earlier focused comparison reproduced 24 v2 hashes and declared profile/ID changes; 98-start/99-edge/90-slice/zero-obligation Windows Rust median 657.39 ms under unlimited timing. This did not qualify native I4 budgets. |
| Acceptance | Complete admission mutation campaign and source-bound P4 refresh were not accepted here; later selected replacement supplied its own decision. |

The [plan execution ledger](../../.agents/plans/completed/bap-projection-admission.md#execution-ledger-2026-10-10)
and [resume order](../../.agents/plans/completed/bap-projection-admission.md#resume-order) distinguish
these historical checks from the later accepted scope. Failed run paths such as
`target/bap-admission-qualification-20261010` identify the original environment,
not a promise that temporary files persist.

## Mutation campaign and repair

The first extended mutant removed the prefix guard. The unchanged corpus failed
at the LOCK rejection (exit 101, successful compile), but its custom message was
only `"lock"`; the harness required literal `assertion`. The
[prefix failure log](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/prefix-mutation.log)
and checkpoint retain `NOT ACCEPTED`. The classifier was repaired for that exact
assertion without crediting build failure or timeout.
The resumed campaign then rejected its first 18 mutants and correctly stopped
when `partial-self-move-loses-definition` survived. It removed `changed`'s
partial-MOV case, but v3 still entered via `possible_destination` and the real
definite-write predicate retained the justification. The repaired mutation removes
that actual predicate case; the unchanged producer test rejects the compiled
mutant because `gpr:rax:0` is missing from `must_defs` (exit 101). The focused
receipt binds inventory, unchanged observers, build log and executable digest;
it alone is not full campaign acceptance.

Focused cross-snapshot, fabricated-call-preservation and swapped-extraction
mutants also failed their intended checks; the latter compiled successfully
before binding validation rejected the extraction. Initially three native
capture-validator mutations were unexercised for lack of SDK. After restoration,
the full 25-case producer/adapter/native-capture campaign passed with stable
sources/observers. Paging introduced a second sequence predicate, so the boundary
mutant was retargeted to the original per-action predicate through family context;
the unchanged bootstrap observer rejected it. Completion now checks overflow-safe
counters and close offsets, with twelve hostile page/lifecycle modes.
A stale Windows `33 c0` whitelist-stop test became exact self-XOR continuation,
all eight RAX origins and preserved undefined-AF checks. These were real test/
mutation repairs; earlier failed receipts remain failures.

## Admission resume

The [local resume report](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/resume-20261010/report.json),
[later remote report](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/remote-20261010/report.json),
[2,959-member manifest](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/remote-20261010/evidence-manifest.json)
and [documentation-only follow-up](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/remote-20261010/documentation-follow-up.json)
retain separate attempts and identities. Source-only transfers and ten named
tool/manifest files were hash-verified; customer captures stayed external.

| Prerequisite or attempt | Observed result and boundary |
| --- | --- |
| MirrorRust | Recovered manifest `a087ecfb136795d30f6c3861d9e4003f0ed9f457db2b17561f0417551bf97854`, revision `08d189f18a76845dc15dd23b79424809ae27f406`; verified source bytes/read-only view without editing the live sibling. |
| Lifter bridge | Initially `80e32c1d21d447969beb99398008cf5a259e5cd10507524c8b2f639c5f0fe57c`, which could not reproduce old hashes. Rebuilding only the bridge reproduced P0 `6d910bf619f6ece729e85e857b60d7a22953bb633a4a43ffd99c5a5919ecc1cf`; earlier mismatches remain diagnostic. |
| SDK initial inventory | 6,134 matching, 3,345 missing and 40 changed files, including absent BAP libraries; the native gate failed. No stale helper or relaxed inventory supplied acceptance. |
| Missing capture | Controlled Linux `tmp/priority1/chromium-member-uaf.dmp`, SHA-256 `31481f3f080b0b165cc0d0c70f555f127f882556b34129055e80b082225a45c9`, remained absent. Initially headers and Breakpad inputs were also missing. |
| Frozen output migration | Revision `ebb2e534e8da339f498f20d0a9e1e0b8506a3bdd`, all five P0 hashes verified, rebuilt in an isolated target tree. Verified bridge reproduced 18 Linux/Windows/NOT fixture hashes and strict v3 content-ID/profile migration; six real-Linux outputs remained missing. |
| Early owned measurements | Six captures, one warm-up/five Rust samples including phases/output sizes and explicit limits; concurrent compilation prevented fixed-budget/native-parity credit. |
| Restored native environment | SDK inventory/smoke/build, matching headers, two upstream Breakpad captures and historical Mirrors binaries recovered in isolated copies. Native root/Clippy/layout, 13 contracts, kernels, five capture tests, 330 observations, 12 algorithm/eight boundary mutants passed. Nested producer failure still exposed old TLC flags, stale v2 assertion, missing Breakpad path, malformed-row control and absent Linux capture. |
| Completion transport trigger | Scanner hit `response budget`, reproduced by 20 nodes/1,000 locations in under one second. Four native tests initially passed exact large-result parity and ten hostile modes; later controls expanded to twelve. Limits remained 8 MiB frames, 64 actions/batch and 256 KiB pages. |
| Early budget failure | Windows I4 median 2,502.747 ms exceeded 2,000 ms while other work ran. Fixture-only I5a passed with controlled-real flags false. Neither was full acceptance. |
| Remote qualification | Ubuntu 24.04 task-private rootfs via rootless bubblewrap on WSL2 (host 22.04 could not run pinned tools; about 58 GiB available). SDK, LLVM 20.1.2, Graphviz, TLC, Apalache/dependencies and two equal clean builds passed; no live sibling/user switch changes. |
| Remote available tiers | Root/default/core-only/Clippy/layout/docs/native/capture/stateflow; 330 replay observations, 12 algorithm/eight boundary/25 admission mutants and eight-case TLA replay passed. Stage E/minidump gates included both exact Breakpad captures. Aggregate retained `passed=false` solely for missing Linux workload. |
| Remote owned/I4/I5a | Six owned captures passed native/reference CLI and phase parity; nine I5a fixture cases met fixed contracts, with real-Windows flags separate. Quiet checksum I4 median 480.236 ms met 2,000 ms after one warm-up/five samples; Linux phase remained unexercised. |

Old TLC flags, the stale report assertion and Breakpad path were repaired; the
malformed-row control passed focused reruns and later broad remote refresh.
Pre-sealing results under `target/bap-admission-completion-20261010/` were not
credited as a sealed P4 delivery. Heavy campaigns moved remotely because the
initial local environment could not support them. Archive compression/member
verification ran remotely; local retrieval checked bounded-memory report/archive
hashes. The old report's failed aggregate remains bound to its original corpus.

### Scanner and PreParser captured queries

The original external Electron dump is 962,600,678 bytes, SHA-256
`9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab`.
The thread-`0x5c74` derivative is 571,636 bytes, SHA-256
`ed82b433501162828460ccbf067476e4683a52157372b27040f0269d2b3949c5`.
Independent binary parsing matched all 50 memory ranges and overlapping
contributors, stack/thread/exception contexts and module/system/exception/
MemoryInfo bytes. A later independent generator reproduced the exact derivative.
It has a distinct snapshot and omits unselected memory. Retained CDB roots and
consumer witnesses matched the prior manifest; raw dumps/customer sources were
not added to the evidence archive.

| Query or phase | Retained result |
| --- | --- |
| Scanner root `0x7ff77443d960`, fault `0x7ff77443dd6e`, early Rust/default limits | Diagnostic timeout at 300 s: no accepted output; that limit was not a BAP latency ceiling. |
| Scanner explicit 256-start bound | `materialization limit: instruction starts`; no partial report published. |
| PreParser root `0x7ff7744033a0`, consumer seed `0x7ff7744048a0` | Nine starts/nine edges; `MOVAPSmr` at `0x7ff7744033b3` stops with `unmodeled architectural namespace/type: YMM6`. Consumer remains missing and answer unavailable. |
| Completed native Scanner | 16.546 s, 768 starts/895 edges/19-site slice; four requested forms projected at 30 sites, no fallback. Partial, not truncated: eight call, two indirect-target and ten decode obligations plus memory/flag uncertainty. |
| Sampling and parity | Six native Scanner phase samples and six native/reference PreParser samples completed. Two complete Scanner Rust samples matched every native raw base-report hash; first took 257.003 s. Remaining long Rust repeats were terminated, so the interrupted six-repeat campaign remains incomplete. |

Native phase/render samples cover base text/DOT/JSON; explanation-CLI timings
are separate. No executed path, actor or cause of the bad RSI follows. Unsupported
SIMD never receives invented continuation. Selected replacement acceptance reused
Scanner/PreParser only after all 120 implementation/manifest hashes and the native
helper identity matched; it did not credit the interrupted Rust repetitions.

### Selected replacement acceptance

The later user-selected `dump_79938FAE443F4021A4F7B6C215` Windows derivative has
29 starts/31 edges, a reached fault seed and a ten-site slice containing the R8
producer. Its [qualification](file-reader-design.md#windows-replacement-capture-and-bounded-query) closes the active
source/fixture, Rust release-runtime, native-default, product and fixed-budget
clauses with a distinct six-output baseline; all 17 investigation gates pass.
The [2026-10-10 user decision](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/bap-admission/p4-acceptance-20261010.json)
accepts that scope and excludes remaining real-Linux clauses. Eighteen historical
hashes reproduce, while the six old Linux hashes/capture tier stay false or
unexercised. Optional full Scanner Rust repetitions and automatic external
evidence ingestion remain separate follow-ups. No required P4 work remains
within the accepted scope; universal lifting/refinement and release claims do
not follow.

## Proof-gated normal admission

The opt-in [MOVAPS guard design](justified-branch-pruning-design.md) and its
[G0–G4 plan](../../.agents/plans/completed/justified-branch-pruning.md) add producer
`bap-bit-provenance-v5` and native capture profile `captured-guarded-input/v1`.
The preparation coordinator freezes full candidate control and residue proof
evidence before selecting the reviewed normal BIL. Unknown, refuted and
budget-stopped guards retain explicit stops and residuals. V4 remains the default.

Native guard validation checks the actual premise instances, source/transfer
receipts, candidate predecessor coverage, selected ordinary successor/effects
and final normalized request identity. This is an analysis-level proof contract
under the pinned BAP trust boundary; general exception graphs remain outside
its scope. The canonical design owns usage, review corrections and dated
qualification results.

## Shift-count compatibility

[Independent BIL count widths](bap-shift-count-design.md) are implemented with
default producer v6 and guarded producer v7. Only BIL ARSHIFT/RSHIFT/LSHIFT
permit different immediate widths and retain the left result width. Counts are
full unsigned bitvectors with bounded overshift fill; other binary typing stays
strict. Provenance equality does not imply computed value equality. Existing
opaque summary effects keep rule v4, and historical v4/v5 identities remain
explicit. The canonical design records analysis, usage, review, qualification
and the original retry's subsequent guard-evidence limit.


## Request-budget validation, 2026-10-14

The [completed T0–T4 ledger](../../.agents/plans/completed/native-request-budget.md) and [source-bound qualification](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/native-request-budget/20261014/README.md) retain 686 matching source/tool/document hashes and 35 archived files. Fresh remote WSL checks pass: 191 default/46 core-only tests, format/Clippy/layout, 17 native kernels, nine capture and two frame-path tests, plus 14 Python contract controls. Five new transport tests exercise exact newline-inclusive host/direct-native bounds, malformed/overflow/full-unsigned launches, legacy compatibility, invalid capabilities/ready, child cleanup, unchanged response limits and a valid request above 8 MiB. Independent read-only review found no concrete issue. Model bodies remain unchanged and their retained G5 hashes are verified; no fresh model/mutation, release/performance or universal refinement campaign is credited.

The [original caller comparison](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/native-request-budget/20261014/artifacts/probe-expanded/preparation-outcome.json) initializes its 4,764-site capture and 9,001,701-byte guard report successfully with `max_request_bytes=33554432`; the default still rejects it with `core request oversized`. Responses remain bounded at 8 MiB. The report retains incomplete candidate coverage and unknown MOVAPS alignment. The retry performs native initialization only, so it does not qualify core/path results.

For a 32 MiB request budget, add `--bap-core-max-request-bytes 33554432` to the native CLI command, or set `CoreConfig.max_request_bytes = 32 * 1024 * 1024` before initialization. Guard evidence, discovery and frame recovery budgets remain independent and must describe the actual captured query. The immutable build identity remains source-bound; its runtime budget is separately negotiated and recorded.

## Source-bound caller completion, 2026-10-19

The [S6 contract](caller-semantic-coverage-design.md#s6-bounded-completion-continuation-2026-10-19)
and [qualified corpus](https://github.com/NzSN/Ariadne/blob/32fbda931177184f429eae37920a5d228d63e31f/evidence/Ariadne/caller-semantic-coverage/20261019/README.md)
add negotiated bitmap completion while preserving ordinary replay. Exact original
caller/callee inputs finish with full native/Rust state equality; all definition
rows have independent checks. RPO and shared exact sets retain every possible
origin. Branch feasibility, history and whole-machine completeness remain separate.

Prepare this corpus with a source-bound current LLVM helper. The current
`native/llvm_mc/build.sh` produces the `6bb0005e…` decoder used by qualification.
The earlier `45dad913…` helper leaves INT3 candidate barriers. Helper/runtime,
source and query identities remain separate from the completed-result codec.
