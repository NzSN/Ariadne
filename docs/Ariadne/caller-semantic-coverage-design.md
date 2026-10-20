# Caller normal-flow coverage: exception exits and guarded MOVAPS loads

## Context and follow-up

**Status.** S0–S6 pass the declared original Windows AMD64 normal-flow and completed-caller profile. The [2026-10-19 qualification](../../evidence/Ariadne/caller-semantic-coverage/20261019/README.md) completes both frames with exact native/Rust states. October 15 budget-stopped and admission-only records retain their original scope.

**Why this document exists.** [Loop closure](guarded-target-resolution-design.md#dated-loop-delivery-and-publication-correction--2026-10-15) completes DA09/DADD but leaves 30 caller guard barriers: 27 INT3 sites, one UD2, one UD1 and one MOVAPS load. This is item 2 of the remaining-blocker inventory.

**What this document establishes.** Checked normal-flow terminal/load admission, versioned replay and bounded complete dataflow with lossless membership storage. BAP lifting remains trusted; LLVM supplies independent decode/control facts.

**Where to go next.** Read the [new qualification](../../evidence/Ariadne/caller-semantic-coverage/20261019/README.md), [S0–S6 ledger](../../.agents/plans/caller-semantic-coverage.md), [completion implementation](../implementation.md), [guard contract](justified-branch-pruning-design.md) and separately [qualified finite frame-path F4](../../evidence/Ariadne/frame-paths/20261020/README.md),
with its [execution ledger](../../.agents/plans/frame-path-enumeration.md).

**What remains unresolved.** The later MOVAPS load remains Unknown under the original premises; two callee indirect barriers remain. Finite frame-path F4 has separate source-bound qualification under a 32-node/two-visit path policy and retains partial coverage. Broader release/large-report qualification, executed history, root cause and universal refinement remain open. Completed dataflow is relative to the admitted graph.

## Reproduced facts

This section records the baseline RED result at `3176d44`. The implementation described below corrects those source-classification and recognition gaps; the later dump/qualification section records its bounded outcome without relabeling the baseline.

The unchanged source capsule is `5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee`. Remote probe `caller-barriers-20261015T060803` exercises public `Backend::prepare` and `FileSnapshot::prepare_with_bap_guard_admission` on four captured prefixes. It returns `selected_barriers_closed=false`, lists all four sites, and verifies that all 877 qualified files are unchanged. Earlier standalone-driver compilation failures receive no runtime credit.

Remote raw probe `raw-bap-20261015T061711` records the qualified helper's exact output. A diagnostic copy adds only the assembly getter; every other semantic field matches the qualified helper across nine queries. [Captured cases](../../tests/bap/fixtures/caller-coverage/dump-four-shapes.json) and [raw observations](../../tests/bap/fixtures/caller-coverage/raw-bap-observations.json) preserve provenance.

| Shape and representative VA | Exact observation | Cause to correct |
| --- | --- | --- |
| INT3, `0x00007ff77440b30d` | `cc`; BAP singleton `Exception(3)`; baseline LLVM labels INT instructions unsupported | Narrow reference classification and checked terminal admission were absent. |
| UD2, `0x00007ff77440b753` | `0f0b`; LLVM terminal; BAP opcode `TRAP`, two consumed bytes and empty BIL | The adapter rejects all Stops; an empty lift is not ordinary semantics. |
| UD1, `0x00007ff77440b0e0` | LLVM consumes `670fb94012`, length 5; BAP consumes `670fb9`, length 3, opcode `UD2B`, empty BIL | Pinned BAP treats `0fb9` as the older two-byte form. Removing `67` still gives the discrepancy. |
| MOVAPS load, `0x00007ff7744035c9` | `0f28b42440020000`; YMM6 merge/load128 followed by the alignment check and `Exception(13)` | The guard recognizer accepts only the `0f29` store form. |

All BAP control-property booleans are false for these four baseline shapes. The old coordinator labeled every Stop a barrier, while Rust/native guard replay independently rejected unreviewed exceptional BIL. The implementation corrects preparation, coverage replay and consumers together; reference-decoder classification alone was insufficient.

## Existing local scope and the new terminal certificate

`Ariadne.tla` already excludes exception/unwind execution and makes Return/Stop end local flow. A certificate means only:

```text
captured bytes and checked source facts establish a supported exception exit
normal_successors(site) = {}
exception-handler/debugger resumption is outside this local-normal-flow scope
```

It is not a premise that an exception handler never resumes. Query/profile/report identities must bind the explicit scope `local-normal-completion/v1`, and reports retain `exception-exit` and `exception-resumption-outside-local-scope`. They cannot turn normal-flow closure into whole-machine completeness or a historical no-path conclusion.

Intel specifies that UD instructions raise #UD and that legacy MOVAPS memory forms require 16-byte alignment. INT3 transfers to the interrupt/exception machinery. These architectural facts justify the narrow control/guard rules; they do not establish how this process handled an exception. [Intel Volume 2B, UD and MOVAPS](https://cdrdv2.intel.com/v1/dl/getContent/671241), [Intel Volume 2A, INT3](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf).

The private `terminal_control` module is shared by preparation and Rust replay. It receives the complete captured instruction span, original BAP AST and consumed bytes/status/opcode/properties, and independent decoder facts, then recognizes or independently validates a source-bound receipt. It cannot grant ordinary continuation or numerical/register effects.

First supported forms:

- INT3: exact `cc`, singleton BAP `Exception(3)`, matching one-byte source and reference facts. Other interrupts and prefixed forms remain unsupported.
- UD2: exact `0f0b`, matching two-byte `TRAP` observations, empty BIL and independently checked terminal reference facts. Empty BIL on another opcode remains unsupported.
- UD1: reviewed `0fb9 /r` encodings, optionally one `67` address-size prefix, with complete ModR/M, optional SIB and displacement validation. No other prefixes are admitted. The captured full span must match the reference decoder. Preserve the pinned BAP `UD2B` opcode-only consumed extent and its disagreement explicitly. This is a control-only certificate; never fabricate a BAP `Exception(6)` or globally waive consumed-byte agreement.

Every admitted terminal becomes a decodable, complete Stop with empty normal successor sets. Retain conservative all-location uses/may-defs, no must-defs, and unsupported exceptional effects. Keep original bytes, BIL and decoder observations unchanged. Only independently validated terminal receipts can remove a candidate coverage barrier; every unmatched Stop remains a barrier.

The native checker independently replays the byte/span/AST/control rule. It rejects forged ordinary Stops, mismatched source spans, additional BIL effects, conditional exceptions with a normal arm, unknown rules and missing/tampered scope. LLVM remains a decode/control reference and supplies no effects.

## Guarded MOVAPS load

The exact recognizer now supports a load operation. It matches the reviewed legacy RSP-relative `0f28` encoding, destination bank, preserved high 128 bits of that same YMM bank, and the 128-bit load from the address tested by the alignment predicate. It requires the exact empty aligned arm and singleton `Exception(13)` alternative; extra effects and other prefixes/vector families decline.

Candidate discovery may use an independently checked RSP/scalar identity over the candidate normal transition. It commits no vector or memory-read effect. Only an aligned verdict authorizes projection of the retained BAP normal AST; unknown/misaligned outcomes keep their current stop and residual. Coarse vector projection preserves old origins and introduces no vector must-defs. Page/protection and other ordinary-memory fault limits remain unchanged.

Keep the public `PendingGuard` shape where practical; use operation-specific receipt rules/digests so load/store evidence cannot be exchanged. The existing scalar target extractor already ignores YMM-only writes and the nonjump exception conditional. Avoid changing target-resolver/loop-checker source merely to support the load.

## Versioned contracts and compatibility

The [legacy sources and identities](../../tests/bap/fixtures/caller-coverage/legacy-manifest.json) were frozen before runtime edits. Explicit version policies retain the old store-only recognition, coverage and normal-selection contract. Old profiles do not authorize terminal evidence or load guards.

| Surface | Retained generation | New generation |
| --- | --- | --- |
| Guard report/profile/model | v1 / `bap-guard-admission-v1` / predicate v1 | v2 / `bap-guard-admission-v2` / predicate v2 |
| Guarded semantic producer | `bap-bit-provenance-v7` | `bap-bit-provenance-v8` |
| Native guard-only input | `captured-guarded-input/v1` | `captured-guarded-input/v2` |
| Combined native/composition | v1 and v2 | v3 |
| Guard-only minidump/explanation/frame | v3 / v2 / v2 | v6 / v5 / v5 |
| Combined minidump/explanation/frame | v4-v5 / v3-v4 / v3-v4 | v7 / v6 / v6 |

Default unguarded projection v6 and rooted target-only v1 retain their contract. Local target report v3/local-v2 and loop engine `afc1b4b…` remain unchanged if their source files remain unchanged.

New guard inputs carry one nonnull, tagged normal-flow evidence field containing the scope and sorted terminal receipts, even when the receipt list is empty. Legacy guard input must omit it entirely; explicit null and unsupported tags reject. Bind it to intent, candidate graph, epochs and final request. Never erase evidence or rebind old hashes to new rules.

Legacy guard checker/model identities are `076b8a3fb6f776e53ea99336854c1a793b8658874c153f4ddd2e32c54128ce7d` / `10e870b21691946cd7985ff7d33819a8a58e4fea202ae6d2e771214b997f5bc9`. Retained composition v2 identities are `605fb57d42e755b7fee75511f66e6ad864a16c303bbf5ffb5bad8855c7d05675` / `dd277b844376234cce199ecae9e7bc9eee04dfa69390d2320c2349b4f11b6cb4`. Keep composition v1's already-frozen path.

The new guard checker identity must bind both guard and terminal-checker sources. The new composition checker/model identities additionally bind the new guard contract. Native metadata advertises legacy and current pairs separately. Actual saved guard-only reports, 2026-10-14 combined reports and 2026-10-15 loop reports must replay under their original contracts after the upgrade.

## Source-review corrections

The implementation review corrected three separate admission seams:

- Rust/native guard recognition now agrees on candidate-control completeness. Incomplete current controls cannot borrow a checked pending normal relation.
- Saved frame validation requires guard evidence for guarded semantic profiles across legacy and current generations. Removing a legacy frame proof cannot downgrade the frame into an unguarded report.
- Native `legacy_guard` uses the frozen `Legacy_capture` dependency. New capture-profile additions cannot expand the legacy admission policy. Two dependency controls and one behavioral dependency-reversion mutant pass on the final source candidate.

Pending load/store preparation clears instruction effects and retains only the checked candidate scalar relation; no memory/vector effect is committed before alignment proof. Unknown alignment still produces a final stop. Terminal receipts and normal-flow scope are retained in the guarded source, paired input and versioned reports rather than inferred from a generic Stop.

## Dated implementation and dump outcome, 2026-10-15

This section preserves the October 15 outcome. The later
[S6 completion](#completed-caller-qualification-2026-10-19) closes its caller
budget/parity gate while retaining the stated alignment and target unknowns.

S0–S5 pass under their declared source/tool scope. The model checker passes all 58 predicate configurations; the independent oracle passes 71 declared cases, 12,752 complete UD1 extents and 8,944 truncation controls. The unchanged model/oracle sources support retained source-bound reuse in the final campaign. These checks do not assert a universal implementation or ISA proof.

Final source archive `c35459a19b1e2f5f139730bea6c119cfceff603207254b52d42effac68654a5f` contains 937 files. S5 record `qualification-20261015T075232Z-139849/qualification.json` passes with helper `d39df81c64c1fd832b88dd48652572234422d8d8840d277cbb83fb88e783e725`: format, 242 default tests, 46 core-only tests, Clippy, release build, nine native capture tests, 88 direct controls, 24 protocol controls, nine behavioral caller mutations, and the two legacy-capture controls/one dependency mutant above. Final native kernel/protocol/frame/composition/tool gates, 330 generated observations, three opaque controls and actual retained guard/combined report replay also pass. This closes S5, not the incomplete original caller-core gate.

The byte-identical original-dump probe `073143` ran on source archive `4a81b5c6b0439bcef53ab98c9c309c59ed0c4be16d522e5c2c691be653fe4f29` (935 files). It establishes:

| Observation | Recorded result |
| --- | --- |
| Original caller barriers | All 30 removed, with no replacement caller barrier. |
| Terminal evidence | 29 checked receipts: 27 INT3, one UD2 and one UD1; exact UD1 consumed-extent disagreement retained. |
| Entry and target invariants | Roots/premises unchanged; all nine original tables, 64 destinations and 51 formerly missing starts preserved; DA09/DADD remain complete with four targets each. |
| Initial MOVAPS at `0x00007ff7744033b3` | Aligned under the recorded normal-flow/entry premises; normal projection admitted. |
| Later load at `0x00007ff7744035c9` | Unknown; normal-or-alignment-fault residual and stop retained. |
| Caller recovery and Rust work | 9,600 attempted starts, 9,589 decoded, 11,321 edges; only `DecodeFailed` is the later load. Rust stops in dataflow at 1,000,000 actions after 554,409 ms, retaining 105,570,377 definition links. |
| Caller native | Accepts the new proofs, then hits its completion action budget after 374,754 ms. Completed caller state parity is unavailable. |
| Callee | 778 decoded, 895 edges, 1,304,602 definitions; completed native/Rust requests and full states match. Indirect barriers remain at `0x00007ff77443da0e` and `0x00007ff77443e200`. |
| Frame paths | NP10 unavailable, zero returned, `missing-frame-query` because the caller has no completed bound query; no no-path conclusion follows. |

The qualified final helper differs from that dump's helper through its frozen legacy-capture dependency and test/version metadata; current Rust/current native analysis routes are unchanged. Admission refresh `075602` passes on the final 937-file source: exact normalized requests and all three guard/target/composition proof reports equal `073143` for both frames. All 30 caller barriers remain removed, caller structural recovery completes with the same 9,589 decoded sites/11,321 edges, and the final helper accepts its proof input. Callee completed parity passes again. The refresh explicitly records `caller_completion_attempted=false` and `full_parity_claimed=false`; it does not repeat full caller completion or satisfy that gate. Keep its identity and scope separate from the earlier full run.

The selected semantic-coverage goal is observed, but S6's explicit requirement for full caller native/Rust completed-state comparison is not met. The plan stays active. Complete bounded caller dataflow and its parity gate before declaring full S6 acceptance; report the unknown load, callee indirect barriers and path availability independently.

## Formal and acceptance boundary

### S6 bounded completion continuation, 2026-10-19

The [S6 continuation ledger](../../.agents/plans/caller-semantic-coverage.md#s6-bounded-completion-continuation-2026-10-19)
addresses the completed-caller gate. Its finite qualification now passes;
the October 15 records retain their original outcome and source identities.

A remote descending-chain feedback case reproduces repeated address-order
propagation. An independent bit-membership observer computes the exact retained
caller fixed point: 9,589 decoded sites, 125,254 possible definition identities
and 141,301,903 reaching links. This exceeds the legacy completion decoder's
16-million expanded-link policy even after scheduling is improved.

The continuation preserves the core transfer equations and ordinary least-VA
`step`/named-action replay. Completion uses iterative reverse-postorder priorities
over decoded local edges, including summary edges and excluding call-only edges.
Every queued update is an enabled monotone propagation; the completed product
must equal the same least fixed point, including entry and possible-write origins.
An existing ordinary-action prefix can be completed without changing its premises.

Completed `DefinitionSet` values may share a sorted definition universe and
immutable membership words. Iteration, membership, equality and copy-on-write
mutation retain set meanings. The Rust bounded completion API refuses publication
on action, elapsed, universe or bitmap-workspace exhaustion. Unbounded legacy
completion retains a reference path when the compact workspace policy declines.
Core-only builds continue to use the standard library alone.

The native helper advertises `completion_codec = bitmap/v1`. The new completion
transaction selects that codec explicitly and retains batches of at most 64
charged actions, the one-million-action cap, 8 MiB response frames, checked
256 KiB pages and 256 MiB completed-envelope cap. Ordinary replay and legacy
completion transactions keep their previous contracts. Compact transactions
expose only progress and the sealed final envelope; mixing ordinary observation
operations into a compact transaction is rejected.

The final bitmap envelope binds a canonical, sorted definition universe,
interned membership strings and total address-to-set references. Each lowercase
hex character carries four membership bits from low to high; unused final bits
are zero. The host independently checks source/query/counters, dictionary identity
against decoded may-defs and entry facts, strict order, canonical strings, padding,
unique sets, references, domain and undecoded empty rows. It bounds one membership
plane to 33,554,432 words and the universe to one million definitions before
allocation. The legacy 16-million expanded-link policy remains unchanged; the
new representation avoids allocating one object per logical reaching link.

Acceptance requires exact Rust/native full-state equality on both retained
original requests, an independent per-row fixed-point check, prefix/replay and
hostile codec controls, applicable core/native/model/replay/mutation qualification,
and a byte-identical raw-dump admission refresh with explicit source differences.
The [source-bound qualification](../../evidence/Ariadne/caller-semantic-coverage/20261019/README.md) passes those named clauses. Later
load alignment, callee target gaps and the fresh raw-source guard-coverage
limitation retain separate outcomes. Finite frame-path admission/enumeration now
has the separately [qualified F4 successor](investigation-design.md#f4-post-s6-qualification);
it reuses the unchanged completed S6 requests and does not refresh S6 evidence.

Predicate-admission v2 was written before runtime implementation and distinguishes certified normal terminals, pending load/store guards and coverage barriers. It models stale epochs, invalid scope/evidence, late edges, forbidden terminal successors and unknown alignment. Existing core Stop semantics and target/loop premise interfaces remain authoritative and unchanged. Finite checks do not prove universal refinement or an inter-model coupling theorem.

The four-shape feedback is green in run `072748` without adding an RSP-alignment premise. Full acceptance requires all 30 original caller sites to stop being unresolved candidate barriers under the declared normal-flow contract, every original INT3 site to have checked terminal evidence, and no replacement unaccounted barrier. Preserve all nine original target sets, DA09/DADD completeness, entry roots and captured bytes. Re-run the byte-identical dump and both native/Rust full-state comparisons.

Report initial MOVAPS admission, the later MOVAPS-load verdict, new discovery, callee barriers and frame-path availability separately. A successful frame listing is not a prerequisite for this narrower semantic-coverage gate.

## Completed caller qualification, 2026-10-19

The [S6 evidence](../../evidence/Ariadne/caller-semantic-coverage/20261019/README.md) binds 1066 source/input files
to capsule `d1c705d04fb20c215601416911355d274aa0b3fec3fac3539f259d5917257cc6`. Saved requests and byte-identical raw-dump
preparation reproduce the original normalized inputs. Caller recovery contains
9,589 decoded sites/11,321 edges; callee recovery contains 778/895. Every
completed reaching row matches an independent finite observer. Native and Rust
requests and full states match for both frames. All 29 original terminal receipts
and the original target facts remain under the same premises.

The caller fixed point retains **141,301,903** reaching links and completes in
**91,175 actions**, within the existing million-action limit. The bitmap envelope
also remains below the unchanged 256 MiB completed-result cap. Every possible
definition and source premise is retained. Ordinary replay keeps its least-VA
schedule; completion uses RPO and shared exact membership.

The initial fresh retry selected stale LLVM helper `45dad913…`, reproducing the
small 9/769-node source and INT3 barriers. Rebuilding the current decoder yields
`6bb0005e…`, matching the original caller-qualified helper, and restores the full
source with zero caller candidate barriers. Earlier partial reports are preserved.

Root feature suites, Clippy, eight selected typechecks/113 finite configurations,
330 generated observations, 29 unique compiled mutations and 24 caller wire
controls pass their recorded tiers. The completed-prefix budget regression has
retained red/green checks. Failed drivers and preliminary repeats earn no final
mutation credit. This qualification covers the original empty-seed requests;
arbitrary large slices and report rendering retain separate release scope.
