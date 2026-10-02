# Stage A source and decoder review: memory-immediate MOV

Reviewed 2026-09-28 for the [Stage A implementation plan](../../Plans/completed/stage-a-memory-immediate-mov-plan.md).
This review authorizes only a conservative normal-continuation analyzer effect
for two decoded AMD64 memory forms. It is not a complete instruction-step proof.

## Pinned source and exact observations

- AMD Volume 3, publication 24594 revision 3.38, SHA-256
  `e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee`,
  PDF pages 282–284 ([publisher landing page](https://docs.amd.com/v/u/en-US/24594_3.38_APM_Vol3_PUB)).
- AMD Volume 2, publication 24593 revision 3.45, SHA-256
  `7257d41d3584822edb7934e2c630c7d3865eea30c0ab95b8de4e546088d5ea9a`,
  PDF page 93 for long-mode REX and operand-size precedence.
- Both PDFs were fetched through `tools/amd64_inventory.py fetch`, verified
  against `Specs/AMD64/manuals.lock.json`, and independently hash-checked.
- The native helper was rebuilt against exact LLVM 20.1.2 headers; its binary
  SHA-256 for this review is
  `dca617ca3e4ad50aef0f795b7793b73a6dae10cf04eebd695b030f8ba82ac7b7`.
  The Ubuntu `llvm-20-dev` archive hash matched the previously recorded
  `e4b5cbfe19826dfb35ff3c2c33d4e3a9e8327de49ad5b7b4b780abb3f6d07b74`.

| Pinned fixture | Captured prefix at exception RIP | Exact LLVM 20.1.2 observation |
| --- | --- | --- |
| Linux `linux_null_dereference.dmp`, SHA-256 `1d82d1d98bb46fb9aa3498fce733e724e9b501824f8b8a36de22066d6d4bca33` | `0x401f26`: `c70005000000...` | `MOV32mi`, length 6; memory tuple base `RAX`, scale 1, no index, displacement 0; immediate 5 |
| Windows `write_av_non_canonical.dmp`, SHA-256 `7012f0b943f5eacf681bcb29fc2766b75b87da1664280eaadc5dfa024f0a3abf` | `0x7ff738721331`: `48c7040841414141...` | `MOV64mi32`, length 8; memory tuple base `RAX`, scale 1, index `RCX`, displacement 0; immediate `0x41414141` |

The native descriptor reports a possible store and no implicit register list
for these exact rows. That descriptor is an encoding observation; the effects
below are justified separately against the AMD MOV entry. The registry keeps
exact opcode names plus six-operand memory/immediate shape checks, not a blanket
MOV-mnemonic rule. Both Windows and Linux LLVM target profiles are exercised
by the native integration tests.

## Interpretation at the analyzer seam

AMD Volume 3 shows the immediate-memory forms as `C7 /0 id`: a 32-bit immediate
is stored into a 32-bit destination for `MOV32mi`; a **signed** 32-bit immediate
is extended to the 64-bit destination for `MOV64mi32`. Volume 3 reports no
rFLAGS changes for MOV and lists possible faults for memory operands. Volume
2 establishes that REX.W selects 64-bit operation size and takes precedence
over a legacy 66h operand-size prefix. A 67h address-size override changes
address-register views; the existing normalizer reads the selected 32- or
64-bit GPR cells. FS/GS and other unreviewed prefixes are not admitted by this
rule. An explicitly constructed incompatible raw opcode/REX.W pair is rejected.

The source memory alternative reads base/index registers to form the address
and takes its stored value from the encoded immediate. It does not require the
old contents of the target memory as an input. The implementation projects a
successful normal-continuation store to `may_defs = {memory:any}` and
`must_defs = {}`. Since `memory:any` denotes all tracked memory, writing four
or eight concrete bytes does not replace that whole abstract location. The
fixed analyzer's ordinary fallthrough is possible local control flow, not an
assertion that the captured faulting store committed, retired or reached the
following instruction. No exception priority, restart state or actual crash
history is inferred here.

## Source-form representation decision

`Specs/AMD64/forms.json` retains `AMD64-F-0502` and `AMD64-F-0503` as
**table-reconciled** records with pending semantic review. `F-0503` currently
records its imm32 as semantic width 32 with extension `none`. The sibling
reviewed register-only variant `AMD64-F-0503-R` records encoded width 32,
semantic width 64 and sign extension. Volume 3's prose confirms the signed
64-bit result also for the memory alternative. Therefore the generic
`F-0503` row is not a completed executable-payload constraint for that
alternative. The Rust effect rule normalizes it as `encoded_width=32`,
`semantic_width=64`, `sign_extend=true` directly from the reviewed source and
pinned decoder shape; it does **not** pass through the formal form validator.

No generated inventory row or profile case digest was silently changed. A
future form-specific validation binding must review/correct or split that
source-form record through the existing forms/profile hash migration before
accepting its `ram-data` case. Both `ram-data:AMD64-F-0502` and
`ram-data:AMD64-F-0503` remain pending, with zero semantic cases. The active
`register-core` gate remains unchanged. This is an explicit correspondence
boundary, not a claim that the form-catalogue discrepancy is closed.
