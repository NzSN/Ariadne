# Pinned BAP shift typing and evaluation

## Context and follow-up

**Status.** Source research for the BAP source revision used by Ariadne's pinned toolchain. This records source-defined behavior; it is not a runtime qualification or a claim that the shipped binaries were built from these sources.

**Why this document exists.** Shift expressions can have differently sized data and count operands, and the count's signedness and overshift behavior affect Ariadne's typed semantic projection.

**What this document establishes.** The exact archived source revision defines LSHIFT/RSHIFT/ARSHIFT typing and bitvector evaluation as described below. The source archive hash agrees between the production toolchain lock and the local SDK source inventory.

**Where to go next.** See [the BAP backend usage guide](../../../../docs/Ariadne/bap-analysis-core-design.md#backend-usage) for Ariadne's adapter boundary and the production toolchain identity in [`native/bap/toolchain.lock.json`](../../../../native/bap/toolchain.lock.json). Parent implementation work should update Ariadne's typed evaluator and tests independently of this source finding.

**What remains unresolved.** Source identity does not show that the production CLI, shared library, or plugins were compiled from this archive. Runtime behavior and Ariadne projection behavior require their own binary-bound qualification.

## Source identity and provenance

The production [toolchain lock](../../../../native/bap/toolchain.lock.json) records CLI `2.5.0-alpha+baa9022`, library `2.5.0-alpha`, a source revision reference `baa9022`, and source archive SHA-256 `b0f28f00e78958f671d84de918f36be8b068ea2ec4459dc72c6f7fe3a0ecf428`. Its note explicitly says asset labels and reported fingerprints differ and limits qualification to the locked asset hashes.

The separate [SDK source lock](../../../../native/bap-core/sdk.lock.json) resolves `baa9022` to commit `baa902209ee4be975bdd8db7d1160b0a0ec2831f`, gives the official codeload URL for that commit, and records the same archive SHA-256. The archive is present at `tmp/bap-setup/bap-source.tar.gz`; its measured SHA-256 is `b0f28f00e78958f671d84de918f36be8b068ea2ec4459dc72c6f7fe3a0ecf428`, matching both locks. I compared each source file reviewed below byte-for-byte by SHA-256 against its member in that archive; all four matched:

| Source path | SHA-256 |
|---|---|
| `lib/bap_types/bap_exp.ml` | `a3f60eca94c83690314b04e869f4dd86564facc697fd7d6a21b9f61cab60aa43` |
| `lib/bap_types/bap_bitvector.ml` | `c7cc314db472c8335e38fc9abc973fcf58ec671623ca7acb71d3cabda0e3ba87` |
| `lib/bitvec/bitvec.ml` | `df542ffd20e032233a6cc3d150b347df603291357b30e398aed6a68f9d8bd46e` |
| `lib/bitvec/bitvec.mli` | `ba04c1a1987337eef41f928bac9dd5473c18d599c5c1bf88dcf71acbc4f426e6` |

The local `target/bap-core-sdk/repository-source.json` also associates that source archive digest with the SDK's extracted repository snapshot digest (`a5eeecf4923b0e6feb34ae6a6fd6f4c4a5c1738256f53a44b5c7dd8116262dea`). The direct archive-member comparisons, rather than this metadata alone, establish that the reviewed local files match the locked archive.

This establishes source archive identity, not binary build provenance: the local SDK is a separate source build, and the production lock records asset hashes rather than a reproducible build attestation linking those binaries to this source tree. The GitHub links below use the full locked commit, not the mutable release tag.

## Verified behavior

### Typing permits mixed operand widths

`Bap_exp.Type.binop` routes all three shifts to `shift`. That helper rejects memory and unknown types, requires immediate operands, and returns the left operand's type unchanged. It does not require the count width to equal the data width and does not inspect a signedness property for the count. BIL's generic `BinOp` carries expressions, and its operator declarations document the operation/fill behavior.

References: [`bap_exp.ml` type inference, `binop` and `shift`](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bap_types/bap_exp.ml#L182-L224), [`bap_bil.ml` operators and expression form](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bap_types/bap_bil.ml#L21-L80).

### Count is interpreted as a nonnegative unsigned bitvector payload

Bitvec documents and enforces normalized values as nonnegative `Z` values. `Bap_bitvector.Packed.lift2` extracts both payloads and passes them to the primitive while applying the result modulo the *first* operand's width. `Bap_exp.Apply.binop` directly dispatches shifts to the bitvector operators without signed conversion; signed conversion is used explicitly for signed division/comparison elsewhere. Therefore the shift count is the count operand's unsigned payload, even if a legacy `Bap_bitvector` value has its signed metadata bit set. For ARSHIFT, sign fill comes from the data payload's most significant bit, not its legacy signed metadata flag.

References: [`bitvec.ml` representation invariant and normalization](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bitvec/bitvec.ml#L1-L59), [`bap_bitvector.ml` payload lifting](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bap_types/bap_bitvector.ml#L104-L123), [`bap_exp.ml` operator dispatch](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bap_types/bap_exp.ml#L129-L169).

### Overshift threshold and fills

The implementation computes the data width as `Z.numbits m`, where `m` is the data operand's bitvector modulus, and takes the overshift branch when the unsigned count `n` is **greater than or equal to that width**. This is the threshold `count >= data_width`, including equality.

- LSHIFT returns zero on overshift. In bounds, it shifts left, introduces zero bits at the low end, and normalizes to the data width.
- RSHIFT returns zero on overshift. In bounds, it shifts right, introduces zero bits at the high end, and normalizes to the data width.
- ARSHIFT checks the data operand's most significant bit. On overshift it returns all ones when that bit is one, otherwise zero. In bounds it shifts right and fills the vacated high bits with ones when the sign bit is one.

References: [`bitvec.ml` threshold and all three implementations](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bitvec/bitvec.ml#L225-L254), [`bitvec.mli` API comments](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib/bitvec/bitvec.mli#L217-L233), [`test_bitvector.ml` examples](https://github.com/BinaryAnalysisPlatform/bap/blob/baa902209ee4be975bdd8db7d1160b0a0ec2831f/lib_test/bap_types/test_bitvector.ml#L245-L253).

The `.mli` comment describes the overshift condition as `y >= m`, but `m` in that module is a modulus, not a width. The implementation is definitive and compares `y` against `Z.numbits m`, i.e. the data width. The test examples cover the three operation kinds but do not by themselves exercise the exact-width boundary or mixed-width operands.

## Version and confidence notes

The source context is commit `baa902209ee4be975bdd8db7d1160b0a0ec2831f`, reached by a hash-locked archive whose short revision matches the production lock's reported CLI suffix. The production asset label `v2.5.0` must not be treated as proof that the runtime binaries are a clean stable-tag build; Ariadne's own README and toolchain lock explicitly distinguish the release label from reported build fingerprints.

Confidence is high for the behavior defined by this exact source revision. Confidence that a particular production binary exhibits precisely these source semantics is limited by the missing source-to-binary build attestation. No runtime probes or builds were run for this research note.

## Ariadne co-update map (proposed; not implemented or qualified)

The current [next-blocker record](../../guard-admission/20261014/next-blocker-widths.json) identifies `bil[3].value.rhs`, operator 11, with a 128-bit left operand and 8-bit right operand. The corresponding [captured BIL](../../guard-admission/20261014/artifacts/next-blocker-bil.json) shows the count expression is an 8-bit multiplication of virtual `#12582910` by `0x20:8u`; the outer shift rule is the immediate typed-admission blocker. The artifact itself bounds this finding to the projection/admission boundary and does not establish architectural behavior, execution history, or cause.

### Required for typed admission and default/guard parity

- [`src/bap/admission.rs`](../../../../src/bap/admission.rs#L223-L239) currently applies `same(l, r)` to every binary operator. A shift-specific typing rule should preserve both scalar checks, allow independent data/count widths only for the three shift operators, and return the left width. The existing equality rule should remain for other operators.
- [`src/bap/projection.rs`](../../../../src/bap/projection.rs#L374-L449) rejects all unequal widths before dispatch. Its shift branch handles only constant counts, and a constant count is cast to host `usize` before there is an explicit `count >= data_width` path. The source-backed semantics require an unsigned count comparison against the left width before host conversion, with zero-fill/sign-fill overshift behavior. For nonconstant counts, the conservative result must retain dependencies from both data and count rather than silently discarding the count.
- [`native/bap-core/guard.ml`](../../../../native/bap-core/guard.ml#L391-L397) has the corresponding `equal_type` gate. It needs the same shift-only left-width typing rule to keep native guard and Rust admission aligned. [`typed_site` and `relation`](../../../../native/bap-core/guard.ml#L476-L482) and [the relation fallback](../../../../native/bap-core/guard.ml#L557-L568) show that untyped sites already yield TOP; after a shift becomes well-typed, [`expression`](../../../../native/bap-core/guard.ml#L483-L507) still maps unhandled expressions to TOP. Thus RSP expressions involving shifts can remain conservatively TOP until a separate evaluator enhancement is justified.

### Optional precision paths

- [`src/bap/target_resolution.rs`](../../../../src/bap/target_resolution.rs#L213-L253) currently makes unequal-width binary terms unknown and has 64-bit-host shift cases. If address-expression resolution is expanded to mixed-width shifts, its captured-expression evaluator in [`native/bap-core/capture.ml`](../../../../native/bap-core/capture.ml#L85-L106) must receive a matching update. These paths serve indirect-target resolution and are not required to admit the current guard case.
- [`src/bap/address.rs`](../../../../src/bap/address.rs#L129-L142) preserves input dependencies but returns explicit `address-width-mismatch` unknown for unequal widths. That conservative behavior can remain until the address resolver supports the new expression.
- [`src/bap/refinement.rs`](../../../../src/bap/refinement.rs#L143-L178) restricts transfer expressions to equal-width 64-bit values and only handles its listed operations. Shift expressions can continue to become `unsupported-transfer-width` or `unsupported-transfer-operation` unknowns; widening this transfer domain is optional.

### Oracle, identity, and evidence boundaries

[`tools/check_bap_admission_oracle.py`](../../../../tools/check_bap_admission_oracle.py#L31-L41) already masks results to the left operand's width, and `Value` stores each input modulo its declared width, so a count payload is nonnegative/unsigned. Its shift lambdas currently call Python shifts directly. New tests should branch on `count >= lhs_width` before performing a host shift, both to encode the BAP overshift rules and to avoid constructing enormous Python integers for large counts.

The producer identifiers currently distinguish default projection v4 and guard producer v5 in [`src/bap/mod.rs`](../../../../src/bap/mod.rs#L12-L19), [`src/bap/guard_admission.rs`](../../../../src/bap/guard_admission.rs#L11-L18), and [`src/bap/prepare.rs`](../../../../src/bap/prepare.rs#L250-L255). Proposed identities are v6 for the default projection and v7 for guard producer, preserving historical v4/v5 records. This is a versioning proposal, not an implemented decision. If the change is strictly a typing/evaluation rule and does not alter serialized fields, existing capture/report schema versions can remain unchanged; the profile identity must still distinguish the semantic rule. Qualification should bind the new profiles and cover unequal widths, all three operators, exact-width and above-width counts, signed metadata on count/data, and unknown variable-count dependencies. No such qualification is claimed here.
