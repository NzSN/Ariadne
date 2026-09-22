# AMD64 foundation validation, 2026-09-22

This record covers source pinning/enumeration and the 64-bit-mode GPR storage
kernel. It does not certify complete instruction forms, all architectural state,
hardware conformance or whole-module TLA+/Lean equivalence.

## Source evidence

All three PDFs in [the lock](../Specs/AMD64/manuals.lock.json) were downloaded
from AMD's public document API, checked as PDFs, hashed and inspected for their
publication/revision on the cover page. Cached files are in
`/tmp/ariadne-amd-sources`; the lock contains reproducible download URLs.

Re-extraction with `pdfminer.six` 20260107 into
`/tmp/ariadne-amd-reextracted` produced byte-identical `instruction-source.json`
and `source-sections.json` files (`diff -q` succeeded for both).

Source enumeration: 154 Volume 3 general-purpose reference entries and 931
candidate mnemonic-table rows. Section enumeration: 298 numbered sections from
Volume 1, 773 from Volume 2, and 71 numbered sections/appendices from Volume 3.
The last count excludes unnumbered individual instruction bookmarks, which are
accounted for separately by the general-purpose reference inventory.

SHL is an alias reference with no separate instruction table. Sixty-six candidate
rows lack a same-line opcode because of PDF layout. All forms and sections are
still pending semantic review; no extraction result is marked implemented.

## Positive checks

```sh
AMD64_MANUAL_CACHE=/tmp/ariadne-amd-sources bash Specs/check-amd64-foundation.sh
python3 -m unittest discover -s tools -p 'test_amd64_inventory.py'
```

Foundation artifacts: `/tmp/ariadne-amd64-foundation.DdEkqRdu`.

| Gate | Observed result |
| --- | --- |
| PDF hashes and inventory integrity | Passed |
| Inventory regression tests | Eight passed after adding the source-plus-coverage deletion regression |
| Reviewed TLA+/Lean source hashes | Matched |
| Lean 4.33.1 `lake build` | Passed, no external packages |
| Lean namespace axiom audit | Passed: 96 declarations and 54 theorem declarations, including generated declarations and nine required primary theorems |
| Apalache 0.62.2 typechecking | All three new TLA+ modules passed |
| TLC 2.19, revision 5a47802 | Safety passed; two distinct fixture states, three generated states |
| Apalache symbolic fixture | No error through depth one, with unconstrained full 64-bit input/payload words and all five views |
| Source extraction reproducibility | Both JSON diffs empty |
| Markdown links and whitespace | Checked |

The original combined log includes seven inventory tests; the eighth test was
added and run with the same source artifacts afterward. Semantic sources and
proof definitions did not change after the combined gate passed.

The finite TLA+ fixture checks 11 basis/boundary words, five views and all
input/payload pairs. The symbolic fixture is a bounded SMT check. Lean proves
the listed helper properties universally; it does not turn the bounded checker
result into a whole-ISA theorem.

The first sandboxed TLC attempt could not open its local RMI listener. The
successful rerun used the required local socket permission. This environmental
failure was not counted as a semantic test failure or as a successful check.

## Negative checks

```sh
python3 tools/check_amd64_mutations.py
```

Mutation artifacts: `/tmp/ariadne-amd64-mutations-etp7q3e0`.

| Deliberate defect | Required rejection observed |
| --- | --- |
| TLA+ dword write preserves upper half | `Safety` invariant violation |
| TLA+ high-byte view starts at bit zero | `Safety` invariant violation |
| Lean typed dword write preserves upper half | Proof elaboration failure |
| Unused unproved project axiom | Namespace axiom-audit rejection |

All mutations lived in temporary copies. Tool launch errors, parser failures and
socket failures are not accepted by the mutation harness as semantic rejection.

The inventory regressions also reject a changed PDF, an HTML response pretending
to be a PDF, deleted instruction/state coverage rows, jointly deleted source and
coverage entries, and a completion claim without evidence. Same-page alias
references remain distinct.

## Remaining gates

`python3 tools/amd64_inventory.py check --require-complete` is expected to fail:
the full architectural coverage work is open. No native instruction evaluator,
hardware differential harness, complete machine-state formalization, verified
TLA+ translator or full-instruction Lean correspondence was delivered by this
foundation milestone. Existing Rust analyzer code and the old register-only
instruction evaluator were not changed.

## Scoped user64 gate checkpoint

The immediate profile gate is independent of the full-manual closure gate.
The canonical `amd64-user64-v1` profile digest is
`5c07adb4b1391d5b2ec29348b208789c2469b2728afd700f27cd3a90bef078cf`.
Its schema-v2 progress file binds all 277 targets to complete source-form
digests. The current report records 49 paired register-core bodies, zero
verified cases and all 277 cases unsupported. A paired body is not an accepted
instruction step.

The accepted `unsupported-analysis-fallback` foundation is limited to
`UnknownInstructionFallback`. It takes no caller trust/effect inputs, removes
all observed concrete and architectural-undefined facts, preserves evidence
gaps, and supplies no retirement, fault, successful transition or successor.
The selective helper is not accepted. The coverage ledger pins the exact TLA+
and Lean source hashes and the profile digest.

Fresh focused checks on 2026-09-22 produced:

- Both fallback TLA+ modules passed Apalache 0.62.2 Snowcat typechecking.
- TLC 2.19 completed the focused fallback fixture with 3 generated states, 2
  distinct states, depth 2 and no error. The first restricted-sandbox attempt
  could not open TLC's local RMI listener; the permitted rerun passed.
- Lean 4.33.1 built `AMD64.Unsupported` and `AMD64.UnsupportedChecks`. The
  focused audit covered 316 declarations and 94 theorems using only `propext`,
  `Quot.sound` and `Classical.choice`.
- All 50 AMD64 Python integrity/profile/acceptance tests passed.
- `python3 tools/amd64_inventory.py check` passed with zero accepted
  full-manual instruction entries.

`python3 tools/amd64_profile.py check --require-milestone register-core` is
intentionally failing because the 49 cases still have open instruction-step
obligations. `python3 tools/amd64_inventory.py check --require-complete` remains
the separate intentionally failing full-manual gate. The suite source-stability
snapshot includes `coverage.json`, so accepted evidence cannot change during a
run without invalidating that run.

## Delegated continuation checkpoints

The earlier `general-purpose-gpt` workstreams produced the component handoffs
below. Broad expansion is now deferred. Their isolated gates do not supersede
the integrated gate or close the architectural coverage ledger.

| Workstream checkpoint | Evidence / scope |
| --- | --- |
| CPU state | 124 field rows and 298 section classifications; CPU-local representation/alias/mode/reset checks passed; partial validity and delegated state remain |
| Forms and operands | 931 reconciled table forms, 8 source-reviewed non-memory forms, 163 partially reviewed forms; shape/payload/identity checks passed; remaining forms open |
| Integer kernels | `/tmp/ariadne-amd64-integer.xz0Nwgm9`: seven TLA+ modules typed, finite integer/flag-adapter fixtures passed; Lean definitions, directed checks and axiom audit passed |
| Memory/exception projection | `/tmp/ariadne-amd64-memory.q78Eq27W`: typing, TLC and Lean passed after source-sensitive review corrections |
| Common page walks | `/tmp/ariadne-amd64-pagewalk.wNx91Sno`: typing, TLC and Lean passed, including PAE participation, byte-backed evidence and legacy4MiB mapping composition; remaining variants/attributes explicit |
| String control | Seven entries/52 table forms inventoried; count/pointer/DF/repeat controls checked; memory movement and I/O integration are later work |
| Old-subset oracle | `AMD64LegacyProjectionChecks.tla` checks 1,296 operand/width/operation combinations against the unchanged old evaluator |

Parent review returned issues before acceptance, including FCW reset bits,
operand identities/widths and malformed LOCK totality, mode-string erasure,
ANDN/rotate/shift flags, signed zero/double-width division, canonical spans,
legacy linear wrapping, A20 behavior, PFEC definedness, PAE permissions/A-D
participation, and independent effect/iteration counts. Fixing a checker error
does not by itself establish the instruction's manual-level semantics.

Early integrated runs exposed real proof/typing failures that isolated gates
missed (a missing fixture variable annotation and non-decidable proof goals).
Some later attempts stopped on deliberately changing form artifacts. They were
not counted as passing integrated verification. Use `Specs/check-amd64.sh` for
the current complete component result and `--require-complete` for the separate
coverage requirement.

A separate parent experiment attempted fully symbolic old/new kernel equality
over arbitrary 64-bit operands. Apalache typechecked it but could not check the
old evaluator's variable integer ranges (`Expected a constant integer range`,
at `CarryInto`). This is a checker limitation, not an invariant counterexample
or a universal correspondence proof. The experiment and logs remain outside
the repository at `/tmp/ariadne-amd64-legacy-symbolic-v2`; the finite oracle and
the existing symbolic register-view checks remain the supported gates.

### Stable multi-agent checkpoint

The frozen checkpoint passed the integrated component suite. Artifacts are in
`/tmp/ariadne-amd64-suite.ub69kGyk`; `resumed-summary.json` and
`resumed-source-snapshot.json` record the completed checks and exact input
hashes. The run resumed after an I4 record-annotation mismatch was fixed in
`AMD64IntegerExecution.tla`. Twelve already-passed typechecks were reused only
after verifying that their conservative dependency closures had unchanged
hashes; the other 21 module typechecks ran afresh. All Lean source hashes stayed
unchanged, so the successful combined build/audit remained applicable.

- All 33 expansion TLA+ modules typechecked.
- All 14 TLC configurations completed without errors.
- The full-width register-view symbolic check passed at depth one.
- All 22 discovered Lean modules built; the combined audit checked 5,254
  declarations and 1,601 theorem declarations, including generated/private
  declarations. Only the standard logical axiom allowlist was used. These
  declaration counts are not instruction-coverage counts.
- Thirty Python integrity/acceptance/form tests passed.
- Four original mutation gates passed again at
  `/tmp/ariadne-amd64-mutations-y5qt_vyt`.
- An additional unused **private** project axiom was rejected at
  `/tmp/ariadne-amd64-private-audit-2csg0ezr`, validating the expanded audit's
  module-origin/private-declaration coverage.
- The checked source hashes stayed stable during the resumed suite.

The checkpoint contains 931 original table forms and one provenance-linked
register-only variant (`AMD64-F-0503-R`); the original reg/mem form is retained.
There are 33 semantically reviewed forms and 142 partially reviewed forms.
The original eight-form dispatcher applies instruction bodies; it does not yet
perform architectural RIP retirement, fetch or post-instruction event delivery.
String-memory execution likewise reports body application, not retirement.

Full coverage is **not** achieved: no complete general-purpose reference entry
is certified in the acceptance ledger. Control transfers, retirement/event
composition, remaining forms, device I/O, atomic/ordering behavior, exceptional
delivery, and remaining proof/profile dependencies still require work. The
task assignments remain explicit in `amd64-semantics-tasks.md`.

### Continued execution and ordering checkpoint

The corrected stable run is `/tmp/ariadne-amd64-suite-corrected`.
`summary.json` records every fresh/reused check and its dependency closure;
`source-snapshot.json` records the exact source hashes. `checked-sources.tar.gz`
preserves those checked sources before later implementation work.

The initial run `/tmp/ariadne-amd64-suite.tdPbXfDw` completed its checks but was
rejected by the source-stability gate: the BSF/BSR zero-source correction and
coverage metadata changed during the run. The corrected run rebuilt every
Lean module and reran the combined audit. It reran both affected TLA module
typechecks and the integer TLC fixture. The other 48 typechecks and 21 TLC
fixtures were reused only after conservative transitive dependency hashes
matched. The symbolic register-view check ran afresh. The corrected run's
source hashes remained stable throughout.

- 50 TLA+ module typechecks passed.
- 22 TLC configurations passed.
- The full-width register-view symbolic check passed at depth one.
- All 38 discovered Lean modules built, including fixtures/audits. The combined
  audit checked 8,384 declarations and 2,412 theorem declarations against only
  `propext`, `Quot.sound`, and `Classical.choice`. Counts include generated and
  private declarations and are not instruction coverage counts.
- 32 Python tests and the source/form/state/string/I/O integrity checks passed.
- Cached PDFs still match the pinned manual hashes.

The source catalogue retains all 931 original forms plus the register-only MOV
variant, with 33 fully reviewed and 166 partially reviewed forms. The unary
supplement adds 20 register-body bindings without excluding legal memory
alternatives. BSF/BSR zero-source results now preserve the old destination;
non-ZF status flags remain undefined. Fallthrough verifies instruction length
and mode/CS-selected IP wrapping, while fetch/event handling remains assumed.

New work includes stack and flag projections with larger Lean CPU prototypes,
permission-resolved atomic adapters, direct device I/O, paired external bodies,
and a bounded WB/WC ordering/publication relation. The external lane records
21 of its 27 entries with paired CPU relations; its six LWP/monitor wrappers
remain partial. Control pairing records explicitly identify authoritative TLA
body gaps. The ordering relation does not establish global coherence or a total
locked-operation order.

These are component checks, not full-coverage acceptance. The ledger still
certifies zero complete instruction entries. Source/form closure, remaining
paired CPU/memory transitions, raw system-state binding, exception delivery,
coherence, profiles and correspondence obligations remain open. BZHI also has
a documented unresolved source interpretation in the integer semantics guide.
