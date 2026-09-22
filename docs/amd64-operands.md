# AMD64 executable operands and form coupling

`AMD64Operands.tla` and `AMD64/Operands.lean` close the representation gap
between a decoded instruction payload and the legality-only shapes in the form
validator. The form layer remains responsible for architectural form
constraints. This layer supplies actual operand identity and values, checks
their internal encoding facts, and erases them to the form shape only after the
payload passes its own validity relation.

## Payloads

The Lean `AMD64.Operands.OperandRef` sum type represents:

- a GPR by canonical architectural index and storage view;
- a memory operand by an address expression and access width;
- an immediate by its exact 64-bit container, encoded width, semantic width,
  and none/zero/sign extension rule;
- a relative displacement and target width;
- an exact segment register;
- XMM/YMM/ZMM, MMX, and mask registers by canonical physical index;
- immediate and memory far pointers; and
- literal constants used by forms such as shift-by-one.

GPR indices follow `AMD64.Arch.GPR`: RAX=0, RCX=1, RDX=2, RBX=3, RSP=4,
RBP=5, RSI=6, RDI=7, and R8 through R15 use 8 through 15. A GPR view reuses
`AMD64.GPRView`; this module does not introduce another register bank.
High-byte views exist only for indices 0 through 3. A low-byte reference to
indices 4 through 7 requires extended byte-register syntax. Indices 8 through
15 require long64 plus the matching REX/VEX/XOP extension selection. Per-
operand `registerExtension` and `byteCode4To7` evidence is checked before shape
erasure, so AH cannot be silently reinterpreted as SPL and an extended register
cannot be accepted from an unset extension bit.

Encoded operands and implicit architectural resources are separate lists.
REX/high-byte rejection examines only encoded operands. An instruction such as
`DIV r/m8` may implicitly write AH while a REX prefix selects SIL or R8B as its
explicit divisor; that implicit AH write is a state effect, not a high-byte
register encoding. Implicit resources are payload-validated but are not erased
into the explicit form operand sequence.

Vector references use the canonical ZMM index from the state layer and its
XMM/YMM/ZMM availability predicates. MMX uses physical x87 register index 0
through 7; this module does not treat MMX as independent storage or turn the
raw low-64 write helper into instruction semantics. Segment references use
`AMD64.MemoryModel.SegmentReg` and ultimately select the corresponding
`SegmentContext` member.

## Address expressions

`AddressExpr` retains base and index GPR identities, their extension bits,
scale, signed displacement, encoded displacement width, optional segment
override, address size, and RIP-relative selection. Its validity predicate
uses the state layer's register availability and the memory layer's
`addressSizePermitted` with the current mode and effective CS default.

RIP-relative addressing is retained in long64 even when address size is 32.
The memory layer remains responsible for truncation/zero extension, segment-
base selection, canonicality, translation, permissions, alignment, and fault
priority. A later instruction binding constructs `AddressRequest` with the
form's access kind, byte count, and mandatory alignment. This module does not
duplicate those computations.

The TLA+ module contains a reviewed local transcription of
`AMD64Memory!AddressSizePermitted`. Snowcat currently cannot compose the state
and memory modules in one instance graph because each deliberately defines a
different `amd64Segment` structural alias. The transcription and this tooling
limitation are an explicit parent-owned correspondence obligation; they are not
an environment callback.

## Checked erasure

`ExecutableInstruction.erase` derives the legality shape. It preserves the
form ID, sizes, prefix and encoding-family evidence, ordered operands, access
intent, and evaluation order. It derives each operand's kind, width, and exact
identity. It also derives REX presence and whether any GPR payload uses a high-
byte view; callers cannot independently assert contradictory redundant facts.

Form operand constraints include an explicit set of allowed identities. `*` is
the only wildcard. Empty identity sets are incomplete data. A fixed AL form
therefore contains `gpr:0:low8`; BL (`gpr:3:low8`) fails normalization even
though kind and width agree. Immediate shapes separately preserve encoded
width, semantic width, and none/zero/sign extension. ADD r64,imm32 accepts only
sign extension; MOV r64,imm64 is a distinct no-extension form, and MOV
r64,imm32 uses the reviewed register-only sign-extension variant. The checks
also reject wrong widths, high-byte
plus REX, SPL without suitable extended byte syntax, inconsistent extension
bits, and malformed payloads before form validation.

Lean returns `CoupledValidationResult.invalidPayload` for payload or register-
encoding failures and otherwise wraps the form validator's six-way result.
TLA+ represents invalid payload as `normalization-error` with reason
`operand-payload-invalid`. Neither result is an architectural exception.

## Boundaries still open

The operand AST and shape coupling are implemented and checked, but full I2 is
still open. Form review must split or constrain table spellings such as
`reg/mem64` into their concrete architectural cases, bind CS default bits to
operand/address-size prefix selection, and close every prefix/feature/exception
obligation. Execution bindings must use the original payload after validation,
not reconstruct values from the erased shape.

Profile-dependent aliases also remain explicit. In particular, lack of LZCNT
or TZCNT support can select BSR or BSF semantics rather than uniformly causing
`#UD`; those forms carry a dedicated fallback-review obligation.

## Checks

```sh
apalache-mc typecheck Specs/AMD64Operands.tla
apalache-mc typecheck Specs/AMD64OperandsChecks.tla
tlc -workers 1 -metadir /tmp/amd64-operands-tlc \
  -config AMD64Operands.cfg AMD64OperandsChecks.tla
(cd lean && lake build AMD64.InstructionForms && lake env lean AMD64/Operands.lean)
```

The fixtures cover AL versus BL identity, low32 versus full64 width, AH with
REX, concrete shape erasure, and payload validation. Form and operand fixtures
are Snowcat-typed separately before TLC.
