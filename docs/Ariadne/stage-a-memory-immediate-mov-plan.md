# Stage A implementation plan: memory-immediate MOV effects

Prepared 2026-09-28 against `a9dc41a`. **Plan only:** no implementation,
coverage-ledger promotion or instruction-step acceptance is claimed. This
expands [Stage A of the remaining plan](remaining-implementation-plan.md).
The scope is two exact LLVM MC 20.1.2 forms, `MOV32mi` and `MOV64mi32`, used
by the two retained AMD64 Windows/Linux minidump fixtures.

## Outcome and boundary

After this stage, both fixtures should decode their faulting instruction, keep
captured-byte and operand evidence, and expose conservative address-register
uses plus a possible write to the existing `memory:any` alias cell. This
unblocks a seed at the crash IP; it does **not** establish a predecessor slice
from an earlier entry (Stage B), prove the faulting store committed, deliver a
synchronous-fault transition, or certify a complete AMD64 instruction step.

The [source inventory](../../Specs/AMD64/forms.json) associates the relevant
memory alternatives with `AMD64-F-0502` (`MOV reg/mem32, imm32`) and
`AMD64-F-0503` (`MOV reg/mem64, imm32`), both derived from Volume 3 PDF page
283. The matching [`ram-data` case records](../../Specs/AMD64/user64-coverage.json)
are still planned/pending. Neither belongs to the active 49-case
`register-core` milestone. The pinned manual revision is
[AMD Volume 3, revision 3.38](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB).

| Candidate | Observed first bytes / target | Reviewed effect to establish |
| --- | --- | --- |
| Linux `linux_null_dereference.dmp` | `MOV32mi` at exception RIP `0x401f26` | Address inputs; imm32 store of 32 bits; `memory:any` may-write, no whole-memory kill |
| Windows `write_av_non_canonical.dmp` | `MOV64mi32` at exception RIP `0x7ff738721331` | Address inputs; imm32-to-64-bit extension verified against source; `memory:any` may-write, no whole-memory kill |

Those are **candidate facts to review**, not a declaration that every encoding
of these names is supported. The dump SHA-256 values and current zero-decoded
baseline are pinned in [the minidump validation record](minidump-validation.md).

## 0. Freeze evidence and resolve the source discrepancy

1. Recheck HEAD, the untracked work, the two dump hashes, the input reader's
   selected 15-byte prefixes and both native target profiles. Record the exact
   LLVM opcode, byte length, ordered raw operand tags, memory tuple and
   immediate value at each RIP. Keep current rejected/unknown behavior as the
   baseline; do not edit the decoder merely to make the rule match.
2. Obtain the exact cached AMD Volume 3 revision from
   `Specs/AMD64/manuals.lock.json` using the inventory tool. Verify byte count
   and SHA-256 before reading PDF page 283 and relevant encoding/64-bit-mode
   prose. The PDFs and matching LLVM 20.1.2 headers may need to be restored to
   `/tmp`; their absence is a source/tool prerequisite failure, not a rule test
   result. Check the native opcode/operand tuple against the pinned LLVM build.
3. Record separate decisions for `C7 /0 id` memory versus register encoding,
   32/64-bit access width, the encoded imm32, semantic extension, address-size
   overrides, REX.W, segment/prefix constraints, implicit resources, flags,
   synchronous faults and what normal continuation can assume.
4. Resolve an existing representation question **before** binding the source
   form to Rust effects: the table-reconciled `AMD64-F-0503` record currently
   lists its imm32 as semantic-width 32 with extension `none`, whereas the
   proposed 64-bit store involves extension of that immediate. Decide whether
   the source-form record is intentionally describing only encoding and leaves
   extension to the instruction body, or whether the form needs a reviewed
   correction. Document the interpretation and its source page. If metadata
   actually needs correction, use the existing form-review/hash-migration
   workflow; do not silently rewrite generated inventory or imply the
   `ram-data` case has been accepted.

Exit: a short source/LLVM/fixture matrix with exact admitted byte/profile
shapes and open assumptions. Do not treat a decoder descriptor `mayStore` flag
or an opcode suffix as proof of architectural effects.

## 1. Add two positive effect-rule bindings

Owner: `src/effects/rules.rs`, `src/effects/forms.txt` and the effect rule
matrix. No changes to `src/engine.rs`, `src/model.rs`, `Specs/Ariadne.tla`,
byte-provider precedence, or the public location catalogue are planned.

Add exactly the two observed LLVM opcode identities to the sorted allowlist,
then match **exactly six** ordered operands: the established five-field memory
address tuple followed by one immediate. Reuse the current `memory()`
normalizer and `imm()` validation. Require an actual memory destination,
reviewed width/profile/prefix conditions and a valid 32-bit encoded payload.
Do not confuse these with the existing `MOV32ri`/`MOV64ri32` register forms,
`MOV32mr`/`MOV64mr` register-source stores, a generic `MOV*` prefix match, or
other `C7` ModRM forms. Retain the existing refusal of unsupported LOCK,
REP, segment overrides and malformed/duplicate prefixes unless source review
establishes a separately checked alternative.

The expected projection for a successful, reviewed **normal continuation** is:

```text
kind       = ordinary, with checked next-VA fallthrough
uses       = bytes of address base/index registers actually read
may_defs   = {"memory:any"}
must_defs  = {}
flags      = no newly asserted flag write (only after source review)
operands   = normalized Memory(... access_width=32|64), Immediate(encoded_width=32, ...)
```

For address-size 32, reads cover the 32-bit GPR views; for address-size 64,
they cover 64-bit views. RIP-relative addressing uses the checked next IP, not
an invented GPR dependency. An immediate store does not consume the old
contents of `memory:any`. The coarse `memory:any` cell represents **all**
tracked memory, so even a definite architectural write to a few bytes is only
a *may-write of that whole cell*. A faulting access might not retire: the
analysis-side ordinary edge is a possible normal continuation, never a claim
that the captured crashing execution performed the write or took that edge.

For `MOV64mi32`, the normalized immediate's encoded and semantic widths plus
extension rule must agree with the decision from step 0. Record a distinct,
source-linked rule ID for each admitted form. Keep unreviewed shapes on the
existing `UnsupportedControl`/opaque path; no broad mnemonic promotion.

Exit: `AnalysisRequest::validate()` accepts prepared exact-shape requests, and
existing legacy `ByteSnapshot::to_request()` behavior remains unchanged.

## 2. Test source interpretation through real native decoding

Owner: `tests/effects.rs`, `tests/fixtures/effects-v2.tsv`,
`input/tests/real_dumps.rs`, and focused input-native fixtures if needed.

- Extend the frozen decoder observations only with actual, reviewed LLVM output
  from both Windows and Linux profiles. A golden row detects a changed LLVM
  layout; independent hand-authored effect assertions establish meaning. If
  only the two proposed identities are admitted, the registry grows from 137
  to 139; report the observed exact count rather than hardcoding a coverage
  claim before checks.
- Exercise representative memory tuples: base only, base+index+scale,
  disp32, RIP-relative, and address-size 32/64 where source/legal encoding
  permits. Check imm32 `0`, positive values, high-bit-set/negative values and
  the 64-bit extension decision. Assert no memory **use**, no flag/other-bank
  write and no `memory:any` must-definition.
- Construct a path where an earlier GPR producer feeds the store's address.
  A backward slice seeded at the store must contain that producer and exclude
  an unrelated GPR write. Separately, a later memory load should retain both
  an earlier memory origin and this possible store origin. That second fixture
  tests a weak memory update; the faulting store itself must not claim it read
  old memory.
- Update the two real-dump tests from their current `decoded.is_empty()`
  expectation. Require the faulting RIP to be decoded, the captured byte/source
  evidence and exact operand/effect assertions, and absence of that RIP from
  `missing_slice_seeds`. Do **not** require a nontrivial preceding slice with
  the crash RIP as the sole entry; Stage B supplies an independently known
  earlier root. Any newly discovered later instruction, missing byte or
  unsupported form remains an honest gap.
- Check that the new **memory** rule rejects register destinations, an opcode
  with incompatible memory width, bad operand count/tags, and unreviewed
  prefixes. Existing reviewed `MOV*ri` register forms retain their own valid
  rule and successor. Invalid/unreviewed memory shapes must not gain a known
  successor. Conflicting or truncated captured bytes cannot trigger file
  fallback.

Negative controls must reject mechanical mistakes: omit base/index uses,
incorrectly use old memory for the immediate store, kill the entire memory
cell, forget imm32 extension, admit a register operand as memory, or claim a definite memory replacement.
Separately assert that reports/coverage never label this faulting instruction
as a proven successful/committed step. Reuse the existing observer and test
the actual decoded bytes; parser errors or compile failures do not count as
an effect mutation being caught.

## 3. Keep the formal projection and evidence gates honest

Owner: a focused check in `Specs/AriadneEffectsChecks.tla` or a new small
projection fixture, the existing acceptance scripts, and a new Stage A
validation note. The extra model check should express the concrete distinction
between a 32/64-bit finite memory write and a whole `memory:any` kill, and the
address-register-use projection. It checks the analyzer abstraction, **not** a
complete MOV instruction step or a decoder proof.

Re-run the source-bound root gate (`python3 tools/check_effects.py`) and the
minidump gate (`python3 tools/check_minidump.py` with the two external fixtures),
including Cargo tests, Clippy/format, real LLVM native fixtures, Apalache/TLC,
existing core MBT and all original plus new effect mutations. Review mutation
script anchors before changing `s.may_defs.insert("memory:any".into())` or
other strings: the original harness requires unique anchors, and a newly
identical line must not turn its failure into purported semantic rejection.
Keep the renderer and input package tests green without editing their model
oracles merely to absorb changed first-instruction behavior.

Freeze relevant source hashes before the integrated run and recheck after it.
Do not update the old 137-opcode validation report in place as though it had
validated the new source. Publish a separate `stage-a-validation.md` with exact
native profiles, fixture hashes, checker versions, actual mismatches and
remaining gaps. Classify absent PDF/header dependencies, inaccessible native
fixtures and timeouts as unavailable verification, not failed semantic
assertions or a passing Stage A gate.

## Completion condition and handoff

Stage A is complete only when **both** pinned real dumps decode their first
memory-immediate MOV, the prepared effects satisfy the reviewed constraints,
independent path/weak-update tests and negative controls pass, formal
projection fixtures pass, and all affected regressions pass against one stable
source snapshot. The result must still label possible paths and effects as
possible, with unresolved later instructions and actual fault delivery outside
this stage. Record changed files, exact accepted opcode IDs and hashes,
validated outputs and limitations. Leave `register-core` at 0/49 and the
`ram-data` cases unaccepted unless their separate source-bound instruction-step
gates are genuinely completed.

Handoff to [Stage B](remaining-implementation-plan.md#b--establish-a-useful-real-dump-backward-slice):
identify an earlier captured entry and test address-producer dependencies
through the decoded crash instruction. The reader remains minidump-only. No
commit or push is part of this plan-authoring task.
