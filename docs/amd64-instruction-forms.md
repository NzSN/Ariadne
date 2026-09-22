# AMD64 instruction-form catalogue and legality boundary

This workstream turns Volume 3 table evidence into stable form identities and
defines how decoded instructions are checked against reviewed architectural
constraints. It does not claim complete instruction semantics.

## Current reviewed boundary

The catalogue contains all 931 table rows associated with all 154 General-
Purpose Instruction Reference entries in AMD publication 24594 revision 3.38.
Each row has a stable ID from `AMD64-F-0001` through `AMD64-F-0931`. A form can
belong to more than one reference entry: XLAT and XLATB retain separate entry
identities while sharing their two source forms, and the standalone SHL entry
redirects to the SHL forms under SAL SHL.

All 931 source table forms are table-reconciled. Thirty-two source forms and
one explicit register-only variant are semantic-reviewed; 166 more have partial
semantic fields. A row's
existence never makes a form legal, implemented, or supported. The current
staged review covers concrete fields in these twelve
entries: ADC, ADCX, ADD, ADOX, AND, ANDN, CMP, OR, SBB, SUB, TEST, and XOR. Four NOP
forms also record their no-access operands and preservation of all non-IP state;
prefix aliases and fetch/next-IP binding remain open. For the integer forms the
catalogue records explicit operand access, implicit CF reads, mode and feature
facts, CPL, operand width, conditional LOCK behavior, flag effects, and the
manual's exception set. Their remaining prefix, mode/address cross-product,
exception-priority, Volume 1 binding, and Volume 2 dependency obligations keep
them pending.

Twenty DEC/INC/NEG/NOT forms now incorporate the reviewed unary supplement.
The generator verifies each form's source row, spelling, opcode, width and full
operand alternatives before merging its mode, access and flag facts. These
remain partial: register bodies are bound, while memory/LOCK composition and
the remaining shared review are open. Embedded-register INC/DEC opcodes remain
restricted to legacy modes, where their bytes are instructions rather than REX.

The closed source forms are the 8/16/32/64 accumulator-immediate encodings of
ADD/AND/CMP/OR/SUB/TEST/XOR and MOV reg8/16/32/64,imm. The register-only
`AMD64-F-0503-R` variant records MOV r64,imm32 sign extension while its original
reg/mem table form remains pending. These reviewed source rows contain only
register/immediate operands, so closure does not
narrow a `reg/mem` row while hiding its memory alternative. Their reusable TLA+
and Lean constraints live in `AMD64InstructionFormsCore.tla` and
`AMD64/InstructionFormsCore.lean`. Every memory-bearing form remains open.

The source table needed named repairs before it could be normalized:

- CMOVcc merges each opcode vertically across its 16-, 32-, and 64-bit rows.
- SETcc merges opcodes across synonym groups.
- VEX and XOP tables split one encoding across several columns. LLWPCB has no
  same-line opcode cell in the bootstrap extraction.
- MONITORX and MWAITX opcode extraction included description text.
- Three IMUL rows and one MOV row split an operand onto another layout line.

The generator names and tests each repair. It also preserves the original row
ID and PDF page, so normalization can be audited against the pinned PDF.

## Artifact schema

`Specs/AMD64/forms.json` is generated deterministically by
`tools/amd64_forms.py`. Every form records:

- stable form ID and all owning entry IDs;
- PDF revision, page, entry title, and source-row identity;
- source spelling, aliases, repaired encoding text, encoding family, ModRM and
  immediate evidence;
- ordered explicit operands, their allowed concrete kinds, widths, access, and
  encoding status;
- implicit operands;
- mode, feature, CPL, operand-size, address-size, and prefix constraints;
- reads, writes, preserved and undefined outputs, exceptions, and dependencies;
- review level, evidence, repairs, open obligations, and implementation status.

Unknown data uses `knowledge: "unknown"`; an empty allowlist under that tag does
not mean unrestricted. Partially reviewed facts use `knowledge: "partial"` and
retain a specific obligation. Only `review.level: "semantic-reviewed"` with
`review.status: "reviewed"` and no open obligations can enter the architectural
validator. Implementation status is separate.

`Specs/AMD64/instruction-review.json` provides the entry view: source pages,
candidate rows, stable forms, redirects, reviewed fields, open obligations,
and module/evidence links for every reference entry.

## Decoded instruction-shape API

The authoritative TLA+ API is in `Specs/AMD64InstructionForms.tla`. Its typed
Lean counterpart is `lean/AMD64/InstructionForms.lean` under namespace
`AMD64.Forms`.

A decoded instruction shape retains its selected form ID, current mode, operand and
address sizes, all relevant prefixes, encoding family, REX/high-byte facts,
and ordered concrete operand shapes. Each operand shape retains kind, width,
source text, intended access, and evaluation order. A table spelling such as
`reg/mem64` becomes an allowed-kind set `{gpr, memory}` in a form constraint;
the decoder must resolve a particular instruction to one concrete alternative.
Width is checked independently from kind.

This is a legality projection, not an executable instruction AST. It retains
canonical operand identity but erases immediate values, relative targets, and
memory address expressions. `AMD64Operands.tla` and `AMD64/Operands.lean` now
provide executable operand payloads and their shape projection. Coupled validation
checks payload validity and encoding coherence before admitting the projected
shape. Instruction execution still needs a rule bound to each admitted form.

The Python artifact validator requires explicit profile operand/address sizes
and decoder prefix-conflict evidence. Missing evidence is undetermined; a size
excluded by the profile is a profile error, and conflicting prefixes have the
same undefined-encoding classification as TLA+ and Lean. CPL is recorded in the
catalogue but is not yet retained by the shared shape API. Currently closed
forms permit every CPL; restricted-CPL forms require a further CPU-state binding
before this API can establish their legality.

This retained order and access information is semantically necessary. For
example, the memory-source form of CMOVcc can report a memory exception even
when the condition is false. Passing form validation does not authorize later
execution code to skip operand evaluation.

The validator produces one of six outcomes:

| Outcome | Meaning |
| --- | --- |
| `validated` | A closed semantic review admits this normalized encoding |
| `architectural-invalid` | A reviewed instruction constraint is violated; the instruction rule determines the specified fault |
| `undefined-encoding` | The manual declares the encoding combination undefined, such as conflicting legacy prefixes |
| `normalization-error` | Decoder evidence contradicts its selected form, such as the wrong encoding family or operand shape |
| `profile-error` | The proposed current mode or size is absent from the supplied architecture profile |
| `undetermined` | Source review is incomplete; obligations explain what remains |

Downstream code must not translate every non-validated result to `#UD`.
Normalization and profile errors are model/adapter errors. Architectural
invalidity becomes an exception only through the reviewed instruction rule.

LOCK validation is conditional. A form must explicitly name a writable memory
destination index, and the decoded operand at that index must concretely be
memory. A `reg/mem` spelling alone does not admit LOCK. Encoding family,
ordered operand kind, and per-operand width are also checked. A high-byte
register combined with REX is treated as contradictory decoder evidence because
REX changes the selected byte register rather than encoding AH through DH.
REX evidence outside 64-bit mode is also contradictory: those byte values are
not REX prefixes there. The executable operand layer admits XMM8–15 with legacy
REX or VEX/XOP extension evidence in 64-bit mode. It rejects vector indices
16–31 for these encoding families; representing their architectural storage
does not establish an EVEX decoder or instruction binding.

Implementation availability is queried separately after validation. Changing
`missing` to `implemented` cannot affect legality; TLA+ checks this invariant
and Lean proves it for every form, decode, and profile.

## Abstraction boundary

The catalogue preserves every source entry and row identity, opcode text that
selects semantics, ordered operands, concrete decoder alternatives, widths,
mode/feature/prefix constraints when reviewed, exceptional outcomes, undefined
outputs, and cross-volume obligations.

It erases PDF typography, physical byte positions not needed after normalized
encoding evidence, prose wording after a fact has a source-linked structured
representation, and implementation-specific decoder data that cannot affect
architectural behavior. Raw byte decoding remains an adapter contract.

The legality machine preserves architecture/profile separation and the
difference between invalidity, undefined behavior, incomplete review, and
missing implementation. It does not execute operands, access memory, order
exceptions, mutate architectural state, or map a rejected form to an exception
vector. Those operations belong to the state, memory/exception, and execution
modules.

The Lean `Source` definition is a reviewed transcription of the TLA+ operator.
Its correspondence theorem proves equality with the typed Lean validator; it
does not parse TLA+ or prove that the transcription matches the TLA+ text.

## Checks

Regenerate and audit the JSON artifacts:

```sh
python3 tools/amd64_forms.py generate
python3 tools/amd64_forms.py check
python3 -m unittest discover -s tools -p 'test_amd64_forms.py' -v
```

Check the specification and proof file in isolation:

```sh
apalache-mc typecheck Specs/AMD64InstructionForms.tla
tlc -workers 1 -metadir /tmp/amd64-forms-tlc \
  -config AMD64InstructionForms.cfg AMD64InstructionFormsChecks.tla
(cd lean && lake env lean AMD64/InstructionForms.lean)
```

TLC opens a local RMI listener and may need sandbox permission. The fixture
checks pending-review rejection, concrete operand shapes and widths, encoding
family, conditional LOCK, REX/high-byte contradiction, mode/profile separation,
and implementation-status independence. The Python tests bind these policies
to the generated JSON schema and verify the named PDF-table repairs.
