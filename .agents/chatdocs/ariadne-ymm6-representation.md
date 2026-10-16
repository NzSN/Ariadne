# What “YMM6 representation” means in this dump

> **Archived chat document.** Restored on 2026-10-16 from the original conversation records. Statements such as “current”, “latest” and “fresh” refer to the original report date. Restoration does not rerun analysis or qualification.

**Update, 2026-10-13:** Ariadne now admits the finite XMM/YMM namespace under profile v4. The original refusal explanation below is historical; the captured MOVAPS still stops at its unmodeled alignment-exception branch. See the [fresh validation record](../../evidence/Ariadne/bap-vector-registers/20261013/report.md).

`YMM6` is the **256-bit architectural vector-register variable used by BAP's
intermediate representation**. For the instruction in this dump, BAP reads its
lower 128 bits to represent `XMM6`.

The captured instruction still performs a **128-bit / 16-byte store**. Seeing
`YMM6` in the lifted expression does not turn it into a 256-bit AVX instruction.

## XMM6 and YMM6 share register storage

`XMM6` names the lower 128 bits of `YMM6`. BAP can describe both widths using
one register variable and a bit selection:

```text
                    YMM6: 256 bits
             255                     128 127                       0
             +--------------------------+--------------------------+
             |       upper 128 bits     |       lower 128 bits     |
             +--------------------------+--------------------------+
                                          <------ XMM6 ---------->

XMM6 = YMM6[127:0]
```

The source register number is six; “6” does not select a vector element.
Intel's MOVAPS documentation distinguishes the legacy 128-bit XMM operation
from the 256-bit YMM forms. The legacy store copies 128 bits and requires a
16-byte-aligned memory destination. [Intel instruction reference, MOVAPS](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf#page=51).

## The exact instruction and BAP expression

In `dump_03958DA4FCA844A786262A1053`:

```asm
; VA 0x00007ff7744033b3
; bytes: 0f 29 b4 24 40 02 00 00
movaps [rsp+0x240], xmm6
```

Its data effect can be written as:

```text
address = RSP + 0x240
value   = low_128_bits(YMM6)
mem'    = store_128_bits_little_endian(mem, address, value)
```

This expression describes dependencies; it does not supply a concrete captured
value for `YMM6` or an earlier value of `RSP`.

The actual typed BAP JSON contains this source expression:

```json
{
  "kind": "cast",
  "op": 0,
  "width": 128,
  "arg": {
    "kind": "var",
    "var": {
      "name": "YMM6",
      "index": 0,
      "virtual": false,
      "width": 256,
      "type": "imm"
    }
  }
}
```

| Field | Meaning |
| --- | --- |
| `name: YMM6` | Architectural vector register six. |
| `width: 256` | The register variable is a 256-bit bit vector. |
| `virtual: false` | Architectural state, rather than a temporary invented during lifting. |
| `type: imm` | BAP's bit-vector type; it does not mean this register is a literal constant. |
| Cast `op: 0`, `width: 128` | `BAP_CAST_LOW`: select the lower 128 bits. |

The enclosing store has `width: 128`. The packaged C API defines cast opcode
zero as `BAP_CAST_LOW` in `bap.h` (historical local header: `tmp/bap-setup/stable/usr/local/include/bap.h:706`; this build artifact is not part of the archive).
Upstream BAP likewise maps 128-bit vector operands through
`bits2ymm128e`; this source is supporting context, while the reproduced AST
below is evidence for our pinned helper. [BAP x86 lifter](https://github.com/BinaryAnalysisPlatform/bap/blob/master/plugins/x86/x86_lifter.ml#L39-L68).

The full lift also includes an alignment condition that raises exception 13
(`#GP`) when `(RSP + 0x240) & 0xf` is nonzero. That exceptional behavior is part
of the lifted semantics; representing the instruction as a no-op would lose
both its memory write and its alignment exception.

## Why Ariadne rejects this representation

BAP successfully decodes and lifts the instruction. Ariadne's current typed
admission accepts architectural GPRs, `RIP`, selected flags and memory, but does
not admit a vector-register namespace such as `YMM6`. It encounters the nested
256-bit architectural variable and returns:

```text
unmodeled architectural namespace/type: YMM6
```

The current decision is in [admission.rs](../../src/bap/admission.rs#L69).
The subsequent dependency projection also has no vector-register location
mapping in [projection.rs](../../src/bap/projection.rs#L76).
Although the AST parser understands widths up to 256 bits, that does not
establish architectural vector support.

The failure is classified as `UnsupportedControl`, producing a conservative
stop in the admitted graph. This classification does not mean MOVAPS is a jump;
the reference decoder and BAP's instruction properties describe ordinary
control. It prevents continuation under semantics Ariadne has not admitted.
Consequently, caller discovery stops before reaching the active call needed
for frame-to-frame path enumeration.

Supporting this properly requires register aliases, vector dependency locations
and memory effects, together with the applicable exception/admission contract.
Allowing the name alone is insufficient. XMM unwind support is a separate
frame-recovery concern.

## Verification and further reading

On 2026-10-13, I lifted these exact eight bytes with the existing local helper,
without rebuilding or changing source. The helper SHA-256 matches the earlier
dump diagnostic:

```text
helper: 6d910bf619f6ece729e85e857b60d7a22953bb633a4a43ffd99c5a5919ecc1cf
BIL:    fe37ab3c15e9e498522eb0cf192ed93706ea1e2dcc7339a9305434adaa10757a
```

The canonical serialized BIL hash also exactly matches the diagnostic, verifying
the `YMM6 → low 128 bits → 128-bit store` representation above.

- [Reproduced typed BIL](ariadne-ymm6/movaps-bil.json).
- [Raw lift response](ariadne-ymm6/lift-response.jsonl).
- [Dump application report](../../evidence/Ariadne/frame-paths/dump03958-20261013/report.md).
- [Original instruction diagnostic](../../evidence/Ariadne/frame-paths/dump03958-20261013/blocker-instruction.json).


## Context and follow-up

**Status.** Restored historical chat explanation. The original text and its evidence scope remain dated.

**Why this document exists.** It preserves an explanation presented through `wslview`; the [chat-document convention](../../../skills/skills/productivity/chatdoc/SKILL.md) gives it a durable home.

**What this document establishes.** The body records the mechanism, observations and limits stated in that conversation.

**Where to go next.** The [chat report index](ariadne-reports-index.md) links related reports; the [assurance contract](../../docs/Ariadne/semantic-assurance.md) defines current responsibilities.

**What remains unresolved.** Restoration does not verify the report against the current implementation or refresh its original qualification.
