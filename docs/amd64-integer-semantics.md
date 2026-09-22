# AMD64 integer semantic kernels

Status: X1 kernel work in progress. These modules compute values and flag
domains. They do not complete any instruction form. The reviewed coverage
record is [integer-coverage.json](../Specs/AMD64/integer-coverage.json).

## Authority and boundary

The implementation was transcribed from the pinned AMD manuals: Volume 1
revision 3.25, sections 3.1.4 and 3.2, and the individual Volume 3 revision
3.38 chapter 3 entries listed in the coverage record. PDF page numbers are
one-based PDF pages. The old `AriadneX86_64Semantics.tla` subset remains a
private regression oracle and was not modified.

The TLA+ modules are authoritative:

| Module | Pure responsibility |
| --- | --- |
| `AMD64IntegerCore.tla` | 64-bit Boolean containers, widths, extensions, Boolean operations, carry/borrow, flags, byte and bit helpers |
| `AMD64IntegerArithmetic.tla` | arithmetic results, exact six-flag records, logical flag domains, ADX chains, compare/exchange values |
| `AMD64IntegerShiftBit.tla` | count masking, shifts, rotates, double shifts, scans, counts, extracts, deposit/extract |
| `AMD64IntegerMulDiv.tla` | column-carry products, multiplication flag domains, relational division |
| `AMD64IntegerStateAdapter.tla` | projection and framed updates between six status flags and complete rFLAGS, including DF |
| `AMD64IntegerExecution.tla` | validated register/immediate payload binding to CPU-state body effects |
| `AMD64IntegerChecks.tla` | independent directed boundary vectors |

Every word is a Boolean map over bits 1 through 64. An operation also receives
an architectural width from 8, 16, 32, or 64. Value results clear bits above
that width. `ValidUnaryInputs` and `ValidBinaryInputs` state the public domain;
invalid widths are not normalized to a nearby valid width.

The pure interface does not choose registers, read memory, extend encoded
immediates, validate a mode or prefix, perform storage writes, or deliver an
exception. Those effects belong to the form, state, memory and exception
layers. A kernel can therefore support the calculation used by an instruction
without completing that instruction.

The state adapter is the narrow exception to the value-only boundary: it maps
CF, PF, AF, ZF, SF and OF to the complete Volume 1 rFLAGS record, proves the
other rFLAGS fields are framed, and provides the DF update used by CLD/STD. It
still does not select or execute an instruction form.

## Reviewed execution binding

`AMD64IntegerExecution` and `AMD64.IntegerExecution` now connect executable
operand payloads to CPU state. The non-conditional dispatcher recognizes all
33 currently source-reviewed forms exported by `AMD64InstructionFormsCore`:
8-, 16-, 32- and 64-bit accumulator/immediate forms for ADD, AND, CMP, OR, SUB,
TEST and XOR; MOV register/immediate forms at those widths; and the reviewed
sign-extended imm32-to-r64 MOV variant. It
derives mode and default address size from the before-state, requires a valid
CPU state, validates the full operand payload against the reviewed form, reads
all operands from the pre-state, and then applies the kernel result.

The kernel result name is `body-applied`. It is not architectural retirement.
A separate `fallthrough-applied` relation updates RIP only when a certificate
ties the decoded length (1 through 15) and next IP to the body state's preserved
RIP. Addition wraps at the mode and CS-selected 16-, 32- or 64-bit instruction
pointer width. Fetch acceptance and synchronous/asynchronous event booleans are
explicitly named external assumptions; this adapter does not claim it checked
them or retired the instruction. Traps and exception delivery remain for their
dedicated boundary. Validation rejection is distinct from
`modeling-unavailable`. Unknown form bindings and unbound memory paths produce
the latter and cannot silently become #UD, a no-op, or an impossible step.

The conditional payload relation already checks 8-, 16-, 32- and 64-bit
register writes, high-byte writes, same-register snapshot reads and long-mode
32-bit zero extension. Volume 1 section 3.1.2.4 makes the upper 32 bits
undefined after a 32-bit operand in compatibility or legacy mode, so execution
uses a relation that fixes the low half and permits distinct high-half
candidates. A deterministic helper remains only as a fixture witness.

The integer form supplement source-reviews all 20 DEC, INC, NEG and NOT rows.
It preserves reg/mem alternatives and validates LOCK only for memory
destinations; opcode-embedded INC/DEC rows remain register-only and illegal in
long mode. Register bodies execute through real `OperandRef` payloads. Valid
memory instances return `modeling-unavailable` until translation, ordered
faults, concrete writes and atomic LOCK behavior are composed.

## Defined and undefined results

Exact arithmetic returns a value and all six arithmetic flags. Logical and
count-sensitive operations return a domain for each affected flag. A singleton
such as `{FALSE}` is exact, `{old}` preserves the incoming flag, and `BOOLEAN`
is an architecturally undefined Boolean. Undefined flags are independent only
where the manual permits each flag to be undefined.

Relational results use candidate predicates where the manual leaves a value
undefined. BSF and BSR are not such a case: for a zero source,
`BitScanAllowed` preserves the old destination and sets ZF; the other five
status flags remain independently undefined. The future CPU binding must take
this branch by skipping the destination write entirely. In particular, BSF or
BSR with a 32-bit destination and zero source must not perform an EAX-style
write that would clear the old high half of RAX. For SHLD or SHRD with a masked
count greater than the operand width,
`DoubleShiftAllowed` accepts any width-shaped destination and the permitted
undefined flags. These rules do not enumerate all 64-bit values and do not
replace undefined behavior with zero.

Shift and rotate counts keep two values distinct:

- `masked = rawCount % 32`, or `% 64` for a 64-bit operand.
- `effective = masked % width` for ROL/ROR, or `% (width + 1)` for RCL/RCR.

The effective count selects the rotated value. The masked count selects whether
flags are preserved, defined for a one-bit operation, or undefined. Thus an
8-bit ROL by 8 leaves the value unchanged but still writes CF and leaves OF
undefined; an 8-bit ROL by 9 rotates the value by one but OF is still undefined.
The same rule handles a full 9-bit carry-ring RCL.

AMD's SAL/SHL, SHR and SAR entries describe CF as the last bit shifted out.
After more than the operand width, logical shifts therefore produce CF zero and
SAR produces the original sign bit. This follows the pinned AMD text and does
not import a different vendor's undefined-CF rule.

BMI/count flag domains are instruction-specific. BEXTR clears CF/OF and leaves
SF/AF/PF undefined; BZHI defines CF/SF/ZF, clears OF and leaves AF/PF undefined;
LZCNT/TZCNT define CF/ZF and leave the other four status flags undefined;
POPCNT clears the other five status flags and sets ZF exactly when its source is
zero. ADCX and ADOX update only CF or OF respectively, with Lean proofs that the
other carry chain is preserved.

## Arithmetic and division

`CarryInto` is carry look-ahead over Boolean bits. Addition, subtraction,
carry, borrow, auxiliary carry and signed overflow never convert the whole word
to a TLC integer. INC and DEC replace the five documented status flags and
preserve incoming CF. ADCX and ADOX update only their selected carry chain.

Multiplication uses per-column partial-product counts and small carry integers.
No term evaluates a 64-bit word as a host integer. Unsigned division is a
relation over candidate quotient and remainder:

```text
quotient * divisor + remainder = dividend
remainder < divisor
```

The multiplication inside that relation is the same column kernel. A zero
divisor or a high dividend half at least as large as the divisor produces
`divideError`; successful DIV fixes a unique width-sized quotient and
remainder. Signed division takes the complete double-width dividend, derives
its magnitude without host-sized arithmetic, preserves the dividend sign on a
nonzero remainder, permits zero without a negative sign requirement, and uses
an exact product threshold to classify signed quotient overflow.

The Lean definitions use `Nat` and `Int` encodings for multiply and divide.
Their directed vectors are checked, but a general proof equating those
definitions with TLA+'s column representation remains open. The coverage file
records this separately from compiled definitions and finite tests.

## Lean proof boundary

`AMD64/IntegerSemantics.lean` contains typed operations and a reviewed `Source`
namespace. Correspondence theorems currently cover truncation, zero and sign
extension, Boolean negation and logic, addition values, bit modification,
count masking, shifts and rotates. They prove equality with the reviewed Lean
transcription. They do not prove that the transcription was generated from or
is identical to the TLA+ source text. Manual review and source hashes remain the
trust boundary.

General representation proofs cover in-range and out-of-range truncation,
zero-extension, selected bit modification and a zero-divisor divide error.
Directed examples exercise arithmetic flags, masked count boundaries, relational
undefined cases, bit counts and deposits, multiplication, successful division,
zero division and quotient overflow. Zero-source BSF/BSR checks accept the
preserved destination and reject a changed candidate. No proof uses `sorry`, a
project axiom, or `native_decide`.

## Validation

Run the isolated gate from the repository root:

```sh
bash Specs/check-amd64-integer.sh
```

It validates the coverage JSON, compiles the two Lean modules, runs their axiom
audit, Snowcat-typechecks every integer TLA+ module, and runs TLC over the
directed fixture. TLC may need permission to open its local worker listener in
a restricted sandbox.

The fixture covers 8-bit carry and borrow boundaries, signed minimum negation,
ANDN's undefined PF, masked shift and rotate counts 8 and 9, a full carry-ring
rotation, two distinct accepted SHLD undefined destinations, zero-source
bit-scan destination preservation and changed-candidate rejection, PDEP/PEXT, a full 8-by-8 product,
and unsigned divide success and error outcomes. Lean also checks negative signed
division and the minimum-value divided by minus one overflow case.

No full instruction entry is complete. Remaining work includes general flag,
TBM/BMI and multiply/divide correspondence, legacy decimal operations, and every form,
storage, memory, feature, prefix and exception binding listed in the coverage
record.

### Open BZHI source interpretation

The pinned Volume 3 revision 3.38, PDF page 176, describes both clearing bits
`[op_size-1:index]` and clamping an oversized index to `op_size-1`. Taken
literally together, those statements clear the top bit for an oversized index.
The current kernel instead retains all source bits in that case and sets CF.
The earlier [official revision 3.37](https://docs.amd.com/api/khub/documents/j44LvPXzuuXgM0WyHKQfeQ/content)
contains the same wording; that comparison does not resolve the discrepancy.
BZHI form acceptance remains blocked on a documented source interpretation or
erratum. The current kernel must not be presented as a closed transcription of
that paragraph, and another vendor's behavior cannot silently settle AMD scope.
