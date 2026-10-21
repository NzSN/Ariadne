# Ariadne terminology convention

## Context and follow-up

**Status.** Canonical repository-wide terminology convention, established on
2026-10-11 after scanning the documentation corpus. Definitions describe the
scope of each concept; dated results and proposed features retain their own
status. This is a documentation change, not new runtime qualification.

**Why this document exists.** The [project overview](../README.md) describes
snapshot-based machine-code investigation. The [architecture](Ariadne/architecture.md)
and [formal-model guide](../Specs/README.md) distinguish several analysis paths,
while analysis contracts and retained evidence sometimes share words such as
state, provenance, backend, complete and verified. Those words need explicit
scope to keep claims interpretable.

**What this document establishes.** Preferred English terms, their meanings,
source/API correspondences, required qualifiers and wording to avoid across
documentation, reviews and report explanations. It supplies one vocabulary
without changing existing identifiers, schemas or feature contracts.

**Where to go next.**

- [Core contract](../Specs/README.md#shared-machine-contract) and
  [Rust correspondence](implementation.md#correspondence-with-the-specification)
  — authoritative modeled behavior and its implementation mapping.
- [Input contract](Ariadne/file-reader-design.md#address-space-and-read-contract)
  and [BAP projection](Ariadne/bap-analysis-core-design.md#projection)
  — byte trust, instruction evidence and semantic scope.
- [Investigation contract](Ariadne/investigation-design.md#evidence-and-claims)
  and [assurance boundary](Ariadne/semantic-assurance.md#active-responsibility)
  — interpretation of answers and the limits of validation.
- [Documentation index](Ariadne/README.md) — canonical feature owners;
  [documentation network](documentation-map.md) — navigation and maintenance.

**What remains unresolved.** A vocabulary cannot prove adapter facts, coherent
capture, actual execution, precise aliases, a root cause or universal refinement.
Address-wrap and memory-refinement terminology describes their selected designs;
partial working-tree implementations do not establish integration or acceptance.
Historical records keep their original wording and identities.

Current validation follows the [executable test matrix](../tests/README.md). Dated run
results below are historical; their Git links do not establish a current pass.
Former qualification-archive retention/publication clauses are retired;
current validation uses executable tests and disposable run products.

## How to apply this convention

Use the canonical terms below in new or revised prose. A shorter form is allowed
after its scope has been established in the same section. Avoided wording is
unsuitable when it substitutes for the defined concept; it can still be quoted
when discussing a different concept or an original historical record.

1. **Name the analysis family.** Distinguish machine-code recovery/dataflow/slicing,
   abstract stateflow, directly supplied LLVM IR analysis and retired ISA execution.
2. **Name the role of a backend, state, address, origin or trace.** These words
   alone do not identify one repository concept.
3. **Keep observations and derivations separate.** Say *possible* for origins and
   dependencies, and *under premises* for semantic and numeric conclusions.
4. **Qualify completeness and support.** Name the request, profile, field, corpus
   or acceptance tier. A completed calculation can still have unresolved gaps.
5. **Keep wire/API spellings exact.** Prose uses “may-definition” and
   “must-definition”; Rust uses `may_defs`/`must_defs`, TLA+ uses
   `mayDefs`/`mustDefs`, and each schema retains its own existing spelling.
6. **Keep status separate from meaning.** Use *implemented*, *proposed*,
   *historical* and *retired* explicitly. Defining a term does not deliver a feature.
7. **Qualify verification.** Name the object, method and scope: verifier-accepted
   IR, model-checked instance, replay-matched corpus or a named proved lemma.
   Avoid unqualified “verified Ariadne” or “proved correct.”

TLA+ is authoritative for the modeled analysis contract. Feature documents own
adapter, investigation and publication contracts; source and tests establish
what is implemented and exercised. This convention governs wording. If a
definition exposes a source/contract mismatch, record and resolve that mismatch
at its owner rather than silently changing a schema or weakening a contract.

Preferred project description:

> Ariadne analyzes one immutable snapshot to recover local control flow,
> compute possible value origins and explain captured fault-address dependencies
> under explicit evidence and semantic premises.

Lookup: [input identities](#snapshot-input-and-identity),
[semantics/effects](#preparation-semantics-and-effects),
[core graph/origins](#core-recovery-graph-and-value-origins),
[investigation answers](#investigation-evidence-and-answers),
[fault-time arithmetic](#fault-time-address-assessments),
[memory refinement](#memory-refinement-and-backward-numerical-reasoning),
[stateflow/IR](#separate-abstract-stateflow-and-supplied-ir-paths) and
[qualification](#validation-qualification-and-delivery-claims).

## Names, abbreviations and identifier spelling

| Term | Convention |
| --- | --- |
| **Ariadne** | Project name. `ariadne-analysis` is the Cargo package; `ariadne` is the Rust library. Preserve executable names such as `ariadne-minidump` and `ariadne-ir`. |
| **AMD64** | Preferred architecture name for the supported Windows/Linux machine-code profiles. Use **x86-64** when naming an existing document, tool or target. Unqualified **x86** does not assert a 64-bit profile. |
| **VA**, **EA**, **GPR**, **CFG**, **AV** | Virtual address, effective address, general-purpose register, control-flow graph and access violation. Expand on first use in a standalone document. |
| **BAP**, **BIL**, **BIR** | Binary Analysis Platform; its instruction-level expressions/statements; its program/subroutine/block/definition/phi/jump representation. BIL and BIR are separate representations. |
| **LLVM MC**, **LLVM IR** | LLVM machine-code decoding infrastructure and LLVM intermediate representation. A BAP decoder using LLVM does not produce LLVM IR. |
| **MBT**, **SUT** | Model-based testing and system under test. Name the actual analyzer/helper exercised by a campaign. |

Use uppercase architectural register names in prose and assembly: `RAX`, `EAX`,
`AL`, `RIP`, `ZF`. Preserve lowercase canonical cells such as `gpr:rax:0` and
`flag:zf`. Use exact names for enums, schema IDs, profile IDs, tool fingerprints
and retained artifact paths; do not normalize their case or punctuation.

Machine VA fields in the strict reports/native protocol use `0x` plus exactly
16 lowercase hexadecimal digits, for example `0x0000000140001000`. This format
does not make another field, such as a dump offset or a bitvector, a VA. State
widths and units explicitly: `access_width` is a bit count in the address-use
contract, while an access-span length is a byte count.

## Snapshot, input and identity

Owner: [file-reader design](Ariadne/file-reader-design.md#immutable-storage-and-identity).
Correspondences: [input types](../src/input/mod.rs),
[byte reads](../src/input/address_space.rs),
[materialization](../src/input/materialize.rs) and [core request](../src/model.rs).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Artifact** | The exact owned bytes of an input file or supplied external record. An artifact SHA-256 identifies those bytes; a filename, PID, module name or timestamp does not substitute for it. |
| **Immutable snapshot** | The fixed analysis view of owned bytes under a declared mapping/input profile. The delivered minidump view uses one capture artifact; immutability does not prove the captured process was temporally coherent. |
| **Snapshot identity** | Identity of that view. The delivered minidump identity is `minidump-captured-amd64-v1:<artifact-sha256>`; the core's general `snapshot_id` is an opaque nonempty identifier. |
| **Captured bytes** | Bytes actually recorded in the capture and available unambiguously at the requested VA. Avoid “process memory” when only captured knowledge is available. |
| **Semantic virtual address (VA)** | Address in the snapshot's process/machine address space. Rust `Address` is `u64`; the TLA+ address domain permits nonnegative integers. A VA is never a file offset or compact graph ID. |
| **Instruction identity** | Snapshot identity plus instruction VA. Equal VAs in different snapshots identify different sites. |
| **File offset** | Byte position in the immutable artifact. A minidump field named RVA is a dump-file offset; a PE image RVA is relative to the selected image base. Qualify **RVA** by format. |
| **Capture contributor** | A stream/descriptor and artifact-offset witness supplying bytes for a VA range. Equal overlapping bytes retain all contributors. |
| **Byte-source provenance** | Whether successfully decoded input came from capture or explicitly admitted file bytes. Core `provenance` is this relation; it is distinct from value origins. |
| **Byte-read prefix** | Longest unambiguous contiguous prefix at a requested VA, bounded by the requested length. A 15-byte request does not assert a 15-byte instruction. |
| **Capture hole** | Absence of captured bytes needed by a read. Missing capture is neither a zero byte nor proof of an architectural page fault. |
| **Capture conflict** | Disagreeing contributors for the same captured byte. Preserve the conflict; stream order cannot select a winner. |
| **Module metadata** | Captured module ranges/names/identifiers used as context or match evidence. A module range alone supplies no runtime instruction bytes. |
| **Companion artifact / entry witness** | An independently matched PE, PDB, symbol or other artifact used to justify an entry or identity. State the matching evidence and its role. It does not fill a capture hole. |
| **Trusted file fallback** | The general core's explicit authorization to use file-backed bytes for a dump site (`trusted_fallback`). The production minidump reader remains capture-only. Avoid “automatic fallback.” |
| **Analysis query** | Explicit entry points, slice seeds and applicable preparation choices selecting an analysis within a snapshot. Changing a query does not change the snapshot bytes. |
| **Query identity / request fingerprint** | Digest of the relevant canonical input for its owning contract. Investigation `query_id`, `request_sha256` and native-core `query` have different roles; do not interchange them. |
| **Semantic/preparation identity** | Tool, target, AST, projection and catalogue identities binding the supplied instruction facts. It is separate from artifact and snapshot identity. |
| **Scope identity** | Content-bound identity of a particular question/result and its premises/evidence. Preserve the owning schema's `scope_id` rules. |
| **Session identity** | Fresh native orchestration token for one process/request lifecycle. A session token is neither a snapshot identity, BIR TID nor machine VA. |

## Preparation, semantics and effects

Owners: [BAP admission](Ariadne/bap-analysis-core-design.md#admission-order-and-identity),
[location model](Ariadne/operand-effects-design.md#canonical-location-model) and
[assurance](Ariadne/semantic-assurance.md#active-responsibility).
Correspondences: [effect evidence](../src/effects.rs),
[location catalogue](../src/effects/locations.rs),
[typed admission](../src/bap/admission.rs) and [effect contract](../Specs/AriadneEffects.tla).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Preparation / materialization** | Reading, entry-driven local-start discovery, decoding/lifting, admission and evidence construction that freeze a finite request before analysis. Preparation is not a completed recovery/dataflow result. |
| **Decode facts / decode reference** | Instruction bytes, length, operands and control facts independently supplied by LLVM MC. They do not supply production uses/definitions. |
| **Lifting / semantic backend** | Conversion of exact captured instruction bytes into instruction semantics. Pinned BAP supplies production minidump semantics. |
| **BAP lifting helper** | The isolated C++ host of the pinned BAP runtime and typed BIL transport (`native/bap`). Distinguish it from the OCaml analysis helper. |
| **Typed BIL AST** | Structured expressions/statements with explicit types, widths, variables and operations. Pretty assembly or pretty BIL is diagnostic text, not the admitted semantic representation. |
| **Projection** | Ariadne's conservative conversion of admitted BIL into control summaries, tracked effects and address-use evidence. The active producer profile is `bap-bit-provenance-v3`; “v3” here does not name the BAP library release. |
| **Capability admission** | Validation of typed BIL constructs, namespace, widths, bindings, prefixes and compatible decoded facts. An opcode name or a test-corpus row alone is not permission to admit a lift. |
| **Mnemonic / decoded form / opcode name** | Assembly spelling, concrete encoding/operand form, and tool-specific decoded identifier. Qualify the last two by tool/profile; `MOV64mi32` is not coverage of every `MOV` instruction. |
| **Normalized instruction summary** | Frozen `Instruction` facts: kind, continuations, targets, target completeness, uses, may-definitions and must-definitions. Accuracy of supplied facts remains a premise beyond shape validation. |
| **Conservative effect projection** | Uses/may-definitions cover possible represented dependencies/writes, and must-definitions assert only justified replacements under admitted outcomes. Overapproximation admits extra candidates; it does not supply exact per-output dependencies or architectural execution acceptance. |
| **Effect quality** | Evidence category such as reviewed, externally lifted, opaque or unavailable (`EffectQuality`). It is separate from semantic status, claim classification and assessment conclusion. |
| **Tracked location / cell** | One disjoint abstract location used for effects and origins. “Location” here is not a source-code line, file offset or arbitrary memory address. |
| **GPR byte cell** | One byte of a canonical 64-bit GPR bank, such as `gpr:rax:0`. `RAX`, `EAX`, `AX`, `AL` and `AH` are overlapping views of these cells, not independent locations. |
| **Flag cell** | One tracked flag: CF, PF, AF, ZF, SF, OF or DF. Other architectural flags are outside this provenance catalogue. |
| **Unknown-memory cell** | `memory:any`, the coarse location overlapping all possible memory accesses. It is not a concrete byte, heap object or disjoint “other memory” region. |
| **Other-state cell** | `state:other`, the coarse FP/vector/opmask application data/status location. Its presence does not establish precise SIMD/x87 semantics or preserved system state. |
| **Use** | A tracked input dependency in the instruction's aggregate `uses` set. It can include conservative alternatives; it is not proof of an actual runtime read of every listed location. |
| **May-definition / possible write** | A location possibly written; `may_defs` generates an instruction-origin candidate while retaining earlier origins unless a must-definition kills them. |
| **Must-definition / definite replacement** | Justified replacement of a location on every admitted alternative; `must_defs` is a subset of `may_defs`. It permits killing earlier origins and does not require a different numeric value. |
| **Kill** | Removal of prior definition origins for justified must-defined locations. A possible write or generic unknown output cannot justify a kill. |
| **Weak memory update** | A store may-defines `memory:any` without killing that whole cell. This alias abstraction is separate from architectural **weak memory ordering** in retired ISA research. |
| **Opaque effects** | All tracked locations are uses and may-definitions, with no must-definitions, when precise effects are unavailable. State control certainty separately. |
| **Opaque ordinary continuation** | `opaque-ordinary`: validated ordinary, data-only behavior with unknown effects retains structural continuation plus conservative effects and a gap. It does not mean the data semantics are fully supported. |
| **Unsupported semantics / conservative stop** | An explicit semantic limitation. Unsupported control, guarded prefixes or unmodeled architectural state can stop recovery at that site; data-only opacity can continue under its separate admission rule. |
| **Malformed input / operational failure** | Invalid AST, failed transport/identity validation or resource exhaustion that aborts the query under the owning contract. Distinguish these from an admitted site-level semantic disagreement/stop; consult the admission decision matrix. |
| **Unknown value / architectural undefined result** | Unknown means available knowledge cannot determine the value. Architectural undefinedness is a separately reviewed semantic property; a generic BIL unknown does not establish it. |
| **Address-use evidence** | Selected load/store role, width, expression, address-input cells and BIL attribution. Store payload inputs are distinct from address inputs. |
| **Decoded address receipt** | Independently checked encoded base/index/scale/displacement facts bound to bytes, LLVM record and tool identity (`DecodedAddressReference`). It supplies roles, not an LLVM effect fallback. |

**Backend must be qualified.** The semantic backend is BAP; the minidump CLI's
default analysis backend is native OCaml/BAP, with explicit Rust reference
selection. Choosing Rust analysis does not switch minidump semantics to LLVM.
Use **LLVM decode reference**, **BAP semantic backend**, **native BAP analysis
backend** and **Rust reference analysis backend** accordingly. “Native” alone
does not identify whether lifting, analysis or Windows capture is intended.
Production effects describe represented normal continuation under their admitted
environment. A definition origin does not establish that a write committed at
fault time or that exception/partial-progress semantics were modeled.

## Core recovery, graph and value origins

Owners: [core model](../Specs/Ariadne.tla),
[Rust implementation](implementation.md#preserved-behavior) and
[architecture concepts](Ariadne/architecture.md#analysis-concepts).
Correspondences: [model types](../src/model.rs), [engine](../src/engine.rs) and
[analysis views](../src/analysis_view.rs).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Entry point / recovery root** | Explicit VA from which local discovery begins. A captured exception RIP becomes a root only if the caller chooses it; it is not automatically a function entry. |
| **Slice seed** | Requested instruction selecting a backward slice. A seed does not become a recovery root. |
| **Local recovery** | Entry-driven discovery following the model's local edge kinds. “Local” is a traversal policy, not a claim that the whole function or program was recovered. |
| **Instruction start / site / machine CFG node** | A candidate or admitted instruction VA in one snapshot. State whether it was merely supplied, visited or successfully decoded. |
| **Visited site / decoded site** | Visited means recovery attempted the site, including failures; decoded means the core accepted it using the supplied byte/decode facts. Neither label alone proves full architectural semantics. |
| **Structural control-flow edge** | Typed `(src, dst, kind)` relation supplied by decoded control/summary facts. It is a possible transition, not an observed executed transfer. |
| **Local edge** | `next`, `taken`, `fallthrough`, `jump`, `indirect` or `summary`. These drive discovery and reaching-definition propagation. |
| **Call edge / call graph** | Visible callee reference with kind `call`. It does not queue a callee or propagate local reaching definitions through that edge. |
| **Summary edge / opaque call summary** | Local possible continuation around a call, carrying conservative caller-visible effects. Target resolution or ABI names do not establish callee preservation or actual return. |
| **Target completeness** | Supplied assertion that an indirect jump/call target set is complete for its contract: Rust `Instruction.complete`, native `targets_complete`. It is distinct from stateflow `complete_sites`. |
| **Recovery obligation** | Core unresolved unavailable/decode-failed/indirect-target/call-target fact. Preparation and explanation gaps are broader and are not all stored in this enum. |
| **Definition origin** | Tagged `(location, site, origin)` candidate, with origin kind `entry` or `instruction`. It identifies a static origin, not a concrete value or loop iteration. |
| **Entry origin** | Value potentially present when entering at a supplied root. It is distinct from an instruction origin at the same VA and is not a slice producer node. |
| **Instruction origin / possible producer** | A site that may define a tracked location. Say “possible producer” in debugging prose; avoid “the writer” without stronger evidence. |
| **May-reaching definitions / reaching origins** | Possible definitions reaching a location **before** an instruction under the frozen local graph and summaries. They preserve alternatives at joins and loops. |
| **Possible data dependency** | Relation from an instruction's uses to its reaching instruction origins. An aggregate use set can overapproximate dependencies for a particular output byte. |
| **Backward data slice** | Decoded seeds and recursively included instruction producers of their uses, computed after the reaching fixed point. It is not an executed trace, path-sensitive pointer reconstruction or root-cause proof. |
| **Analysis state** | Mutable algorithm bookkeeping: phase, worklists, decoded sites, graph, obligations, reaching relation and slice. It is distinct from an architectural CPU state or abstract valuation. |
| **Analysis action / step** | One enabled modeled transition. Rust chooses the lowest eligible VA where the model allows a choice. A replay action is not a CPU instruction execution. |
| **Fixed point** | Stable dataflow/stateflow relation under the supplied transfer rules. It says nothing by itself about byte fidelity or semantic completeness. |
| **Analysis completion** | Reaching `done` after the family's required phases. Unresolved obligations and partial explanations can remain. |
| **Recovery scope closed** | Core `scope_closed()`: `done` and no core recovery obligations, relative to the request/traversal policy. It does not certify all seeds, all effects or all real program paths. |
| **Missing slice seed** | Requested seed absent from the decoded set (`missing_slice_seeds`). Inspect it separately even when recovery is closed. |
| **Analysis view / completed analysis** | `AnalysisView` exposes admitted request/state read-only; `CompletedAnalysis` retains a completed request/result for binding. Binding checks completion; the trait alone does not assert it. |
| **BIR attribution / TID** | BAP term identity and its validated association with a snapshot/site. Multiple TIDs can share a VA; keep machine identities and the typed parallel-edge relation separate. |

Use **byte-source provenance**, **value origins**, **possible memory-writer
origins** or **BIR attribution** rather than unqualified “provenance” when more
than one relation is in view. A text/DOT CFG edge is a control edge; it does not
become a producer/use edge merely because reaching origins appear beside it.
An unavailable provenance sentinel at an unvisited rendered node means **no
successful decode recorded**, not an independently established capture hole.

## Investigation evidence and answers

Owner: [investigation contract](Ariadne/investigation-design.md#binding-and-result-contract).
Correspondences: [question/result types](../src/investigation/model.rs) and
[binding validation](../src/investigation/validate.rs).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Fault-address question** | One instruction VA and explicit memory-access index in a bound completed query (`FaultAddressQuestion`). It is narrower than “why did the process crash?” |
| **Fault-address explanation** | Possible origins of the selected access's address inputs, with facts, claims, premises and gaps. It reuses completed core analysis. |
| **Bound investigation** | Validated association of exact request/state, snapshot, query and instruction evidence (`BoundInvestigation`). Equal snapshot IDs alone are insufficient to join unrelated query results. |
| **Evidence record** | An identity- and source-bound captured observation or explicitly admitted artifact. Current first-question evidence is instruction/projection evidence; later questions have separate evidence contracts. |
| **Analysis fact** | Derived graph, effect, address or origin fact bound to its producer, projection, query and premises. It is not a captured observation. |
| **Claim / premise** | Question-specific assertion and the assumptions on which it depends. Stable evidence/fact references make the claim auditable, not automatically true of past execution. |
| **Alternative** | A candidate explanation not eliminated by admitted evidence. Independently merged byte origins need not co-occur as one pointer or feasible path. |
| **Captured frame chain / register evidence** | Reader-bound `CapturedFrameChain` under the finite Windows AMD64 unwind profile. Top-frame context values are observed; caller register values are derived under stack-slot and unwind/ABI premises, with validity/provenance retained. It does not supply complete historical machine states. |
| **Frame identity / frame index** | A validated activation in one snapshot/thread/frame chain. Index 0 is the innermost captured frame; larger indices are older callers. An index is not an instruction VA, and recursive activations remain distinct. |
| **Bounded frame-path question / listed path** | Implemented finite-profile [frame-to-frame query](Ariadne/investigation-design.md#bounded-frame-to-frame-path-listing), with `N >= M >= 0` and fewer than positive `NP` retained paths. A listed path is a structural alternative under explicit frame, graph and feasibility premises, possibly containing opaque summary steps; it is not an observed executed trace. |
| **Represented corridor** | Stage 5.2 forward/reverse reachability intersection in the declared activation-qualified graph. Unknown continuations outside it can reconnect; absence is only graph-relative. See the [design](Ariadne/investigation-design.md#structural-corridors-and-cycle-summaries). |
| **Structural SCC / condensation** | Stage 5.2 maximal mutually reachable component and quotient DAG of represented edges. Cyclic membership supplies no iteration count, data invariant, termination or feasibility proof. Original members, typed edges and frontiers remain available. |
| **Example route** | Stage 5.2 loop-free structural witness between validated anchors: one shortest represented route and optionally selected alternatives under a strict positive NP bound and separate work limits. It is not exhaustive path enumeration or executed history. |
| **Frame question scope** | section-5 investigation scope binding one snapshot/source revision, activation range, selected point/access/edge, semantic profile, context/instance quantification and premises. A selector does not become a recovery root. See the [design](Ariadne/frame-question-investigation-design.md#identity-premises-and-model-scope). |
| **Model witness / refutation** | checked feasibility evidence within an explicit supported model and quantified scope. A witness satisfies its admitted relations; a refutation needs sound semantics and complete claimed-context coverage. Abstract nonemptiness alone is unknown, and neither result supplies executed history. |
| **Question bottleneck** | A specific unfinished premise or analysis obligation blocking a selected frame question, with a dependency and concrete work/evidence requirement. Its scheduling priority is neither path probability nor a proof that other frontiers are irrelevant. |
| **Source revision** | immutable successor of a bound structural source, retaining snapshot/roots/activation range and explicit parent/evidence identity. New edges invalidate dependent old-epoch negative/closure claims until checked again; revision is not in-place mutation. |
| **Gap** | Missing, conflicting, unsupported or incomplete evidence/semantics limiting an answer. Identify the affected site/location and reason where known. |
| **Evidence requirement** | Concrete observation, artifact or semantic refinement needed to strengthen or distinguish an answer. Avoid a generic “more information needed” when the missing premise can be named. |
| **Truncation** | Expansion or retention limited by the answer budget (`truncated`). It is separate from semantic uncertainty; retained references must remain valid. |
| **Executed history / root cause** | Actual past transitions or a causal explanation of the crash. A snapshot-based possible-dependency result does not establish either. |

Keep these result dimensions independent:

| Dimension | Exact vocabulary | Interpretation |
| --- | --- | --- |
| Explanation **status** | `explained`, `partial`, `unavailable` | `explained` has no gaps/truncation within the admitted question; `partial` retains usable address evidence with unresolved work; `unavailable` lacks the evidence needed for a usable selected address. None asserts a root cause. |
| Claim **classification** | `observed`, `derived_under_premises`, `unknown` | Captured observations, conditional derivations, or unmet requirements. Possible producers/dependencies use `derived_under_premises`. |
| Numeric **assessment conclusion** | `consistent_with_evidence`, `refuted_under_premises`, `unknown` | Conditional outcome for one admitted hypothesis. These are separate assessment values, not extra first-question classifications. |
| Numerical **precision** | `Exact`, `Constrained`, `Unknown` | Refinement vocabulary about possible bitvector values; it is separate from all three existing report dimensions above. |

“Explained” does not mean “every producer executed.” “Consistent with evidence”
does not mean “confirmed cause.” “Unknown” never means false, impossible or zero.
Do not add numeric confidence without a separate justified contract.

## Fault-time address assessments

Owners: [zero address](Ariadne/zero-address-design.md#evidence-and-admission),
[zero base plus displacement](Ariadne/zero-base-offset-design.md#selected-question)
and [address wrap](Ariadne/address-wrap-design.md#exact-selected-question).
Correspondences: [captured fault fields](../src/input/fault_context.rs),
[sealed fault context](../src/investigation/fault_context.rs) and
[decoded receipt](../src/llvm_mc/address_reference.rs).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Exception instruction address / exception RIP** | Captured instruction location associated with the exception context. The legacy minidump metadata `reported_address` refers to the exception location, not the inaccessible data byte. |
| **Reported inaccessible-data address** | Exception parameter describing a byte associated with the failed read/write. Distinguish it from the instruction VA and the computed access start. |
| **Captured register observation** | Register value supported by the selected exception-context validity group and source spans. Raw zero bytes with absent validity are missing evidence. |
| **Fault-time context premise** | Assumption that the admitted exception context describes the selected instruction before its ordinary memory access and is contemporaneous with the bytes. Field agreement alone does not prove hardware origin or temporal coherence. |
| **Effective address (EA) / access start** | Modular address-expression result for the selected access. Address inputs are before-instruction values; RIP-relative expressions use the instruction site's address information. |
| **Access span** | Byte range beginning at EA with the selected access width. The reported inaccessible byte may be later within that range, rather than equal to EA. |
| **Encoded base / signed displacement** | Distinct decoded operand roles. A modular BIL constant does not recover a displacement's signed encoding; an arbitrary affine term is not automatically the encoded base. |
| **Zero-address assessment (I5a)** | Admitted fault-time predicate `EA == 0`, meaning the access **starts** at zero. Avoid “null-pointer diagnosis.” |
| **Zero-base-plus-displacement assessment (I5b)** | Admitted no-index predicate `B == 0` and `D != 0` for the encoded base and signed displacement. “Zero-base-offset” remains in existing API/schema/path names. |
| **Fault-time address-wrap assessment (I5c; design)** | Integer `T = unsigned(B) + signed(D)` leaves `[0, 2^64)` before modular reduction. The selected design does not assess an earlier arithmetic instruction or source-language overflow. |
| **Address calculation wrap / access-span wrap** | Wrap of the base-plus-displacement sum and wrap of the byte-range end are different predicates. A small EA or carry from adding a displacement bit pattern is not the I5c predicate. |
| **Assessment admission profile** | Exact supported instruction/context/range/prefix conditions required for a definite conclusion. The lower-range cutoff in the first profiles is a design restriction, not a discovered canonical-address configuration. |

For I5a/I5b, an unknown producer history can coexist with a definite conditional
fault-time assessment. A refuted zero-address hypothesis does not refute zero
base plus nonzero displacement. A zero EA does not establish a zero base.
State the assessed predicate and retained premises in each result explanation.

## Memory refinement and backward numerical reasoning

Owner: [memory-provenance refinement design](Ariadne/memory-provenance-refinement.md).
These terms describe that design's scoped refinement contract. Draft helper
exports do not establish a qualified reader-bound refinement pipeline or extend
the strict fault-address explanation schema.

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Memory-origin candidate / possible memory writer** | Entry-memory or instruction origin admitted by the coarse `memory:any` model. It is not evidence that a store touched the selected load's bytes. |
| **Alias uncertainty** | Unresolved overlap between accesses. The existing `unknown-memory-alias` label can also arise from conservative all-location dependencies; it does not always identify a load/store at that site. |
| **Access-pair assessment** | Scoped comparison of load/store ranges using admitted address/value relations: disjoint, overlapping or unknown. Overlap alone does not establish the last writer or actual execution. |
| **Justified equal-base relation** | Evidence/semantic relation that compared accesses use the same base value within the stated scope. Register-name equality or a repeated static definition site is insufficient across loops. |
| **Numerical value fact / instance scope** | Bitvector fact at a program point with explicit path/value-instance premises. The scope is justified or left unresolved; it is not an invented dynamic iteration ID. |
| **Backward preimage** | Set of predecessors compatible with a supplied transfer relation and later constraint. It is relational reasoning, not generally a unique inverse or reverse execution. |
| **Exact / Constrained / Unknown** | One compatible bitvector; multiple values with a useful predicate/known bits/relation; or no useful numerical constraint. All are relative to declared premises. |
| **Expansion boundary / conflict** | Reason further numerical expansion stops, or inconsistency of admitted relations/constraints. A boundary preserves established facts; an empty preimage is a conflict, not an ordinary unknown. |
| **Information erasure** | An admitted relation removes useful information about the requested earlier value. Keep it separate from unsupported semantics, missing memory history, unresolved control and exhausted budgets. |
| **Transfer receipt / refinement sidecar** | bounded, identity-bound typed relations retained during successful preparation. An AST hash or effect set alone does not reconstruct those relations. |
| **Candidate exclusion within scope** | Justified omission from a separate question-specific assessment. It does not delete the original core origin, rewrite the CFG or permit a must-definition of `memory:any`. |

Unknown memory continues to overlap any precise region. “Stack access” does not
make an access disjoint from another register-based access. Stop only the
affected numerical expansion; preserve independent facts, provenance alternatives
and established constraints when a boundary or budget is reached.

## Separate abstract-stateflow and supplied-IR paths

Owners: [stateflow design](machine-state-design.md#6-observations-and-interpretation)
and [typed replay/IR contracts](Ariadne/typed-replay-design.md#result-families).
Correspondences: [machine stateflow](../src/machine_state.rs),
[LLVM IR analysis](../src/llvm_ir.rs), [stateflow model](../Specs/AriadneMachineState.tla)
and [IR model](../Specs/AriadneLLVMIR.tla).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Abstract stateflow** | Propagation of caller-supplied finite state transitions over a frozen recovered local CFG. Avoid “crash replay” or “symbolic execution” when only these supplied relations are propagated. |
| **Abstract state / valuation** | Catalogue record mapping locations to nonempty abstract value sets plus running/terminal status. It is distinct from the recovery algorithm's `AnalysisState`. |
| **State identity / catalogue** | Snapshot-scoped state ID interpreted within its retained catalogue. Equal valuations can have distinct IDs/transitions; independently built catalogues need separate namespacing/binding. |
| **Before-state set** | State IDs possibly present before a node. An empty set means not reached by the supplied model, not a missing register value. |
| **Supplied semantics / complete site** | Trusted transition relation and local assertion of completeness (`complete_sites`). They are not inferred from crash registers or control-target completeness. |
| **Frame preservation** | Supplied transitions preserve valuations outside the source site's may-definitions. A must-definition need not change an abstract value or independently kill state IDs. |
| **Incomplete-semantics obligation** | Derived for every stateflow site outside `complete_sites`, including unreached sites. It is separate from caller-supplied adapter obligations and core recovery obligations. |
| **Feasible edge** | Structural edge with a reached running-transition witness under the supplied stateflow model. It is not an observed executed branch. |
| **Model-relative infeasible edge** | At completion, an unwitnessed edge from a reached, locally complete source under the supplied relation. API `provably_infeasible_edges` and TLA+ `ProvablyInfeasibleEdges` retain their spellings; prose states the model-relative limit. |
| **Unknown-feasibility edge / not-reached node** | Remaining structural edge, or node with an empty completed before-state set. Incomplete upstream semantics prevent a concrete-unreachability inference. |
| **Terminal outcome** | Supplied `faulted`, `returned` or `stopped` alternative reached within stateflow. It is not a new captured hardware event. |
| **Recovery handoff** | Frozen recovered nodes/local edges/effects plus separately supplied semantic inputs. Full recovery context retains call edges, provenance, missing seeds and obligations. |
| **Directly supplied LLVM IR** | Owned `.ll`/`.bc` artifact parsed and verifier-accepted by the pinned LLVM helper for a selected function. It is not IR reconstructed from the dump or BAP's BIR. |
| **IR identity** | Artifact/module/function-scoped block, instruction, value or callee ID. It is not a machine VA or a crash-time register identity. |
| **IR block CFG / SSA and phi dependencies** | Terminator-derived control edges between IR blocks and producer relations between IR values/instructions, including phi alternatives. These relations do not identify an executed machine-code predecessor. |
| **IR dependency predecessor** | SSA/phi producer or conservatively supplied memory predecessor. The all-writer memory relation retains alias uncertainty rather than proving exact store/load correspondence. |
| **IR verification** | LLVM well-formedness checking of the exact supplied IR. It does not prove machine/IR correspondence, alias precision or program correctness. |

Stateflow classifies the structural graph without deleting edges. Its three edge
classes partition the supplied local edges; call-only edges remain separately
visible in recovery context. Avoid **pruned CFG**, **impossible branch** and
**unreachable in the real program** for these model-relative observations.

## Validation, qualification and delivery claims

Owners: [assurance boundary](Ariadne/semantic-assurance.md),
[evidence guide](../tests/README.md), [replay guide](../mbt/README.md)
and [performance contract](Ariadne/workload-performance-design.md#workload-set-and-measurement-layers).

| Canonical term | Meaning and required distinction |
| --- | --- |
| **Source review** | Inspection of exact source/API/manual facts. It does not imply that the installed helper or a capture campaign exercised those facts. |
| **Fresh test/check** | Execution during the named validation run against identified current sources/tools. State omitted or ignored native prerequisites separately. |
| **Retained source-bound evidence** | Stored result with source/tool/artifact/query identities. Current applicability requires verifying the complete relevant inventory or rerunning affected checks. |
| **Historical evidence** | Result interpreted at its recorded date/revision/scope. Preserve original paths, hashes, pass flags and limitations even when a successor changes acceptance scope. |
| **Fixture / synthetic workload** | Controlled input constructed for conformance or scaling. A generated minidump fixture is not evidence of a real captured crash. |
| **Controlled capture / external capture** | Actual capture from an owned controlled program, or an externally supplied crash artifact. Identify the producer, bytes and matching/query evidence; the two corpora are not interchangeable. |
| **Corpus / coverage** | Named finite set of exercised cases and clauses. Count exact forms/encodings/observations explicitly; mnemonic counts or form inventories alone do not establish supported coverage. |
| **Oracle / expected observation** | Independently established expected behavior, often generated by the authoritative TLA+ actions or a separate arithmetic calculation. It must not be fabricated from the SUT result. |
| **Model trace / replay observation** | Sequence of model actions and compared actual analyzer states. Replay is a conformance check, not recovery of the captured program's executed history. |
| **Mutation sensitivity** | Demonstrated rejection of deliberate real-engine or boundary faults through the unchanged observer. A passing mutation campaign remains finite evidence. |
| **Model checking / bounded checking** | Property checking over the named model instance or bound. Always name that instance/bound; avoid an unqualified universal proof claim. |
| **Refinement proof / correspondence proof** | Mechanically established relation between representations/transitions over its stated scope. Universal compiled-Rust refinement remains an open boundary; tests do not supply that proof. |
| **Trusted dependency** | Pinned external semantics relied upon under an explicit boundary, currently BAP lifting. “Trusted” describes a premise, not independently proved AMD64/hardware correctness. |
| **Qualification tier / acceptance gate** | Defined clauses for a particular source/fixture, native/helper, controlled-capture, performance or product scope. A partial tier does not satisfy a full gate. |
| **Accepted within scope** | Recorded satisfaction/acceptance of the declared clauses and exclusions. A later selected-scope decision does not rewrite an earlier failed aggregate flag. |
| **Unexercised prerequisite / excluded clause** | Required but unavailable test input/runtime, or a clause explicitly removed from an accepted scope. Neither is a passing check. |
| **Default adoption / release qualification** | Production path selection and separately qualified packaged delivery. Native-default finite-corpus acceptance alone does not establish packaged cross-platform release qualification. |
| **Frozen query / workload identity** | Exact artifact, entries, seeds, limits, semantic/helper identities and measured output mode, with source/host/settings recorded. Comparisons must preserve the applicable identity. |
| **End-to-end CLI latency / phase timing** | Full prebuilt-CLI execution versus a named internal phase measurement. Keep startup/publication scope, host, warm-up, repetitions, medians and aggregation method explicit. |
| **Timing budget / unlimited timing policy** | Acceptance threshold for the named contract, or an explicitly waived timing cap for another scope. BAP's unlimited policy does not waive fixed investigation budgets. |
| **Limit outcome / transport completion** | Recorded time, size, action or output-budget boundary, or validated receipt of all result pages. Paging completion does not improve analysis precision or permit publication of an incomplete core result. |

Preferred claim pattern:

> On DATE, CHECK exercised BACKEND against CORPUS/QUERY with SOURCE/TOOL
> identities. TIER passed; LIMITS, EXCLUSIONS and UNEXERCISED prerequisites remain.

For a retained result, replace “freshly passed” with “retained result applies
after complete identity verification,” and say whether verification was actually
performed. Report budgets using their measured statistic, such as median
end-to-end latency or sum of phase medians; these are different measurements.

## Disambiguation examples

| Avoid as an unqualified claim | Use instead |
| --- | --- |
| “The fault address is `0x…`.” | “The exception instruction VA is `0x…`; the reported inaccessible-data byte is `0x…`; the computed access start is `0x…` under PROFILE.” |
| “Switch to the LLVM backend.” | Name **LLVM decode reference** or **directly supplied LLVM IR analysis** if intended; the Rust analysis selector retains BAP minidump semantics. |
| “The graph proves the branch ran.” | “The structural taken edge is recovered; no executed branch is established.” |
| “This store wrote the pointer.” | “This site is a possible origin through `memory:any`; exact overlap and execution remain unresolved.” |
| “Recovery is complete.” | “Recovery scope is closed for QUERY; missing seeds and preparation/effect gaps are reported separately.” |
| “The pointer is null.” | “The selected access starts at zero under the I5a premises,” or “the encoded base is zero with a nonzero displacement under I5b.” |
| “The value is unknown, so analysis stops.” | “Numerical expansion for this value stops at REASON; existing constraints and provenance alternatives remain.” |
| “This edge is impossible.” | “The edge is model-relative infeasible under the supplied stateflow relation and completeness assertions.” |
| “Replay passed, so Rust is verified.” | “Finite model replay matched the observed Rust transitions for CORPUS; universal refinement remains open.” |
| “Stage 2 / v3 / profile / native passed.” | Name **BAP integration Stage 2**, **projection `bap-bit-provenance-v3`**, the exact profile and the specific helper/backend/tier. |
| “The retired ISA work is complete.” | “The independent ISA track is retired; its historical proof/coverage boundaries remain unresolved.” |

Stage labels are scoped identifiers. **BAP integration Stage 1/Stage 2**,
**Stage E typed replay**, **investigation I4/I5a/I5b/I5c** and
**retired ISA Stage D** denote different work. S/P/A/B/W stage numbers and
version numbers must retain their owning plan, schema or profile when ambiguous.

## Documentation scan and maintenance

The 2026-10-11 scan covered all **86 existing Markdown documents** in the source
checkout, including the in-progress memory-refinement design and plan. It also
scanned the **15 plain-text report/decode artifacts** and the separate
`src/effects/forms.txt` form registry for emitted spellings. Build output,
scratch `tmp/`, Git internals and archived binary payloads are outside the prose
corpus. This document is additional to those 86 documents.

These counts describe the original terminology scan. The later ISA cleanup
removed `Specs/AMD64/README.md`; its inventory is now an archive reference,
as recorded in the [removal policy](Ariadne/semantic-assurance.md#dependency-audit-and-retained-references).

| Scanned group | Markdown documents | Reading purpose |
| --- | ---: | --- |
| Root: README, roadmap, checkpoints, repository instructions | 4 | Product intent, invariants and current/historical scope. |
| `.agents/plans/`, including completed plans | 28 | Stage vocabulary, acceptance clauses and unresolved work. |
| `Specs/` guides | 2 | Active modeled contracts and retired ISA inventory. |
| `docs/Ariadne/` | 14 | Feature-specific inputs, effects, questions, reports and qualification. |
| Other `docs/` | 31 | Core/stateflow contracts, navigation and retired architecture research. |
| `evidence/Ariadne/` guide | 1 | Retained evidence identities and claim boundaries. |
| `lean/` guide | 1 | Retired component proof vocabulary. |
| `mbt/` guides | 2 | Generated replay, oracle/observer ownership and finite scope. |
| `native/` guides | 3 | Lifting/analysis helpers and controlled Windows capture. |

Definitions were cross-checked against the linked current model, request,
effect, input, investigation, stateflow and IR sources. The scan identified
overloaded terms and made the choices above; it did not reinterpret historical
pass flags or rerun their qualification campaigns. The [documentation catalogue](documentation-map.md#document-catalogue)
provides the individual document entries.

When introducing a domain term:

1. Check this vocabulary and the owning feature contract; reuse an existing
   concept where its meaning matches.
2. Define the new term here with its scope, preferred spelling, source/API
   correspondence and distinction from the closest existing term.
3. Add contract detail to its canonical feature document and link any execution
   plan there. Update maintained prose when its meaning changes; preserve raw
   historical evidence and schema compatibility.
4. Run `python3 tools/check_doc_links.py` and review the wording for unsupported
   completeness, execution-history, proof or release claims.
