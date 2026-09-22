# AMD64 source and coverage inventory

The immediate target is [the verified user64 subset](../../docs/amd64-user64.md),
starting with the 49-case `register-core` milestone. Its form/profile progress
and acceptance are independent of whole-manual completion. The retained
[long-term design](../../docs/amd64-semantics-design.md) targets all Volume 3
general-purpose instruction forms and all Volume 1 application-visible machine
state, including the necessary Volume 2 dependencies. TLA+ is authoritative;
Lean supplies a checked formalization with explicit correspondence boundaries.

## Delivered boundary

The source baseline is downloaded and pinned. Source enumeration contains 154
general-purpose reference entries, 931 candidate mnemonic-table rows, and all
298 numbered Volume 1 sections. **These are not counts of supported instructions
or reviewed architectural forms.** Whole-entry closure is a roadmap metric;
the immediate profile reports paired bodies and verified cases separately.
The previous register-only subset remains in
`AriadneX86_64Semantics.tla`.

The continuation adds CPU-local state representation (124 field obligations),
decoded-form shape validation, memory/exception contracts, and integer kernels
to the original GPR view foundation. The agents' component handoffs and open
dependencies are tracked in [the task list](../../docs/amd64-semantics-tasks.md).
Compiled types, table reconciliation and kernel tests do not establish complete
architectural state validity or full instruction execution. Executable operands,
page walks, strings and further instruction work are active follow-ups.

The last integrated stable checkpoint passed 50 TLA+ typechecks, 22 TLC fixtures,
the register-view symbolic check, the complete discovered Lean build/axiom audit
and 32 Python tests. That checkpoint has 33 source-reviewed forms and 166 partial forms;
these are distinct from full instruction-entry completion. One explicit
register-only variant supplements the 931 original table forms without removing
its reg/mem parent. See [the validation record](../../docs/amd64-validation.md)
for exact source hashes, artifacts, boundaries and remaining work.

## Files and provenance

| File | Role |
| --- | --- |
| `manuals.lock.json` | Exact AMD PDF URLs, revisions, byte lengths and SHA-256 hashes |
| `source-sections.json` | Numbered source sections from the three PDFs, with one-based PDF page numbers |
| `instruction-source.json` | Every Volume 3 chapter 3 reference entry and extracted table-row candidates |
| `coverage.json` | Open review and implementation obligations; separate from generated source metadata |
| `user64-profile.json`, `user64-coverage.json` | Immediate scoped milestones, exact operand projections, progress and profile-bound acceptance |
| `correspondence.lock.json` | Reviewed register-view TLA+/Lean file hashes and operator mapping |
| `work-assignments.json` | Deferred roadmap routing for every reference entry under the requested role; paths are logical lanes, not live sessions or acceptance |
| `state-fields.json`, `volume1-review.json` | CPU-state representation and source-section routing with explicit partial/delegated obligations |
| `forms.json`, `instruction-review.json` | Reconciled table forms and staged semantic review; no implicit promotion to ISA support |
| `system-dependencies.json`, `integer-coverage.json` | Component contracts, kernel coverage and remaining semantic/proof gaps |

The pinned editions, verified against their downloaded cover pages, are:

- [Volume 1, 24592 revision 3.25, May 2026](https://docs.amd.com/v/u/en-US/24592_3.25_APM_Vol1_PUB).
- [Volume 2, 24593 revision 3.45, July 2026](https://docs.amd.com/v/u/en-US/24593_3.45_APM_Vol2_PUB).
- [Volume 3, 24594 revision 3.38, July 2026](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB).

The lock records the exact content URLs. Older indexed AMD URLs returned 404;
the public document API resolved the new editions. A later URL or content
change is not automatically accepted. PDFs remain in a local cache and are not
redistributed in this repository.

Page numbers are **PDF pages**, starting at one, not the manual's printed page
labels. Instruction entries sharing a page (for example XLAT and XLATB) keep
distinct identities and can reference the same candidate rows. SHL has no own
mnemonic table: its reference page directs the reader to SAL SHL. Its row stays
open for alias review. Of the 931 candidate rows, 66 have no same-line opcode;
merged or multiline cells need manual reconciliation. A source row can also
describe multiple register/memory, width or condition-code forms.

The layout extractor does not read every behavioral paragraph, derive feature
requirements, or prove table completeness. All candidates are marked pending.
The next inventory task is reviewed form expansion and field-level state
coverage, including implicit resources and cross-volume behavior. The coverage
ledger now has an evidence-backed semantic-case schema. Closing an entry needs
reviewed forms, accepted cases, current source hashes, TLA+ checks, Lean build
and axiom-audit evidence, and no open dependencies. A helper proof cannot close
an instruction entry. The checker validates the consistency and freshness of a
reviewed claim; it cannot independently infer the correct interpretation of
every manual paragraph.

## Reproduce source extraction

`fetch` and `check` use only Python's standard library. Extraction requires
`pdfminer.six==20260107`, recorded in the generated files. Install it in an
isolated environment if it is not already available.

```sh
python3 tools/amd64_inventory.py fetch --cache /tmp/ariadne-amd-sources
python3 tools/amd64_inventory.py check --cache /tmp/ariadne-amd-sources
python3 tools/amd64_inventory.py extract \
  --cache /tmp/ariadne-amd-sources --output /tmp/ariadne-amd-reextracted
diff Specs/AMD64/source-sections.json /tmp/ariadne-amd-reextracted/source-sections.json
diff Specs/AMD64/instruction-source.json /tmp/ariadne-amd-reextracted/instruction-source.json
```

Without `--output`, extraction replaces only the two generated source files;
it does not reset review decisions in `coverage.json`. Before accepting a new
manual revision, review its source inventory diff and migrate coverage IDs.

The integrity gate can pass while architectural coverage is open:

```sh
python3 tools/amd64_inventory.py check
```

Report the immediate profile and check its first milestone with:

```sh
python3 tools/amd64_profile.py report
python3 tools/amd64_profile.py check --require-milestone register-core
```

The conservative default fallback foundation is accepted for the current
profile hash. That milestone remains pending until all 49 case obligations are
accepted. The separate full-manual roadmap gate also remains pending:

```sh
python3 tools/amd64_inventory.py check --require-complete
```

## Foundation checks

The full expansion component gate discovers every new TLA+ and Lean module:

```sh
bash Specs/check-amd64.sh
bash Specs/check-amd64.sh --require-milestone register-core
```

The second command requires scoped milestone closure. `--require-complete`
instead requests full-manual roadmap closure. The four named worker lanes are
restricted to the approved profile priorities, so use the task list
and checker output to distinguish stable handoffs from in-progress files.

The narrower original register-view gate is:

```sh
AMD64_MANUAL_CACHE=/tmp/ariadne-amd-sources bash Specs/check-amd64-foundation.sh
```

The script checks source integrity and regression tests, the reviewed
correspondence hashes, the pinned Lean build and axiom audit, all three new TLA+
modules' Snowcat types, finite TLC cases, and an Apalache symbolic fixture at
depth one over full 64-bit words. It writes logs to a fresh `/tmp` directory.
TLC requires permission to open its local RMI listener in restricted sandboxes.

The symbolic fixture must not be passed to TLC: its initial input domain is all
64-bit Boolean words. The finite fixture uses 11 boundary/basis words, five
views, and all 121 input/payload pairs. These are complementary checks.

The Lean theorems quantify over every word and view. Their source-side objects
are a reviewed Lean transcription with one-based indices. They do not prove
the correctness of a TLA+ parser or the complete AMD64 model. See the
[typed explanation](../../docs/amd64-typed-foundation.md) and
[Lean guide](../../lean/README.md).

Run the isolated negative checks with:

```sh
python3 tools/check_amd64_mutations.py
```

They require the correct Lean package to have been built first. Two TLA+
mutations must fail the semantic invariant (dword preservation and wrong
high-byte offset); removing Lean's dword zero-extension must fail a proof; and
an unused project axiom must fail the axiom audit. A checker launch, parser or
socket failure does not count as a successful rejection. Mutations and logs
stay in a fresh temporary directory.
