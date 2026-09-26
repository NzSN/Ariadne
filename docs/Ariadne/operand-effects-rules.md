# Operand/effect rule matrix

Delivered 2026-09-26 for `user64-effects-v1.0`, LLVM MC 20.1.2.
The table lists **137 exact LLVM opcode identities**, not 137 accepted ISA
steps or 137 AMD user64 cases. Each entry additionally requires the shape,
register widths, prefix and address constraints in `src/effects/rules.rs`.
Names not in `src/effects/forms.txt` have unresolved control in the new path.

Sources: pinned AMD Volume 3 revision 3.38, SHA-256
`e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee`;
Volume 1 revision 3.25 (GPR aliases and 32-bit zero extension), SHA-256
`aed9236b718ae86cdb49f7d628f4ebb1a4bdce1a012df6cf6aad6735776c8a38`.
References use the stable IDs in [the source inventory](../../Specs/AMD64/instruction-source.json).

All rows are exercised with real decoded bytes by the frozen-matrix test.
The raw snapshots establish decoder layout compatibility. Independent effect,
slice and mutation tests establish the separately stated behavioral evidence;
a decoder snapshot is not a semantic oracle. The source review covers normal
long64 user-mode continuation, ordinary RAM and CET disabled. Fault/interrupt
paths and full instruction validity are not certified.

Flags: ADD/SUB/ADC/SBB/CMP replace CF/PF/AF/ZF/SF/OF; ADC/SBB also read CF.
INC/DEC preserve CF and replace the other five status flags. AND/OR/XOR/TEST
replace CF/OF/PF/ZF/SF, may-write undefined AF without killing its old origins.
MOV/LEA preserve tracked flags. Jcc selects OF, CF, ZF, CF+ZF, SF, PF, SF+OF,
or ZF+SF+OF for the eight condition pairs. Calls and RET remain opaque; CLC/STC
have only control review in this release. NOOP has empty effects.

The catalogue tracks GPR bytes, seven named flags, all memory as one may-alias
cell, and FP/vector/opmask application data/status as `state:other`. It does
not track RIP or system/debug/control state such as RF/TF/IF. Untracked state
must not be reported as preserved. Reviewed listed forms do not touch the
opaque FP/vector bank; opaque effects read/may-write it along with all other
locations. All writes to `memory:any` remain may-writes, never whole-memory kills.

| LLVM opcode / rule suffix | Example bytes at VA 4096 | Disposition | AMD Volume 3 source |
| --- | --- | --- | --- |
| `ADC16ri` | `6681d30101` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC16ri8` | `6683d3ff` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC16rr` | `6611d8` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC32ri` | `81d301010101` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC32ri8` | `83d3ff` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC32rr` | `11d8` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC64ri32` | `4881d301010101` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC64ri8` | `4883d3ff` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC64rr` | `4811d8` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC8ri` | `80d301` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADC8rr` | `10d8` | Reviewed normal-continuation effects | V3-GP-005, PDF 127–128 |
| `ADD16ri` | `6681c30101` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD16ri8` | `6683c3ff` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD16rr` | `6601d8` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD32ri` | `81c301010101` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD32ri8` | `83c3ff` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD32rr` | `01d8` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD64ri32` | `4881c301010101` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD64ri8` | `4883c3ff` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD64rr` | `4801d8` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD8ri` | `80c301` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `ADD8rr` | `00d8` | Reviewed normal-continuation effects | V3-GP-007, PDF 131–132 |
| `AND16ri` | `6681e30101` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND16ri8` | `6683e3ff` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND16rr` | `6621d8` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND32ri` | `81e301010101` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND32ri8` | `83e3ff` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND32rr` | `21d8` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND64ri32` | `4881e301010101` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND64ri8` | `4883e3ff` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND64rr` | `4821d8` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND8ri` | `80e301` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `AND8rr` | `20d8` | Reviewed normal-continuation effects | V3-GP-009, PDF 135–136 |
| `CALL64m` | `ff10` | Opaque effects; reviewed control | V3-GP-032, PDF 178–180 |
| `CALL64pcrel32` | `e802000000` | Opaque effects; reviewed control | V3-GP-032, PDF 178–180 |
| `CALL64r` | `ffd0` | Opaque effects; reviewed control | V3-GP-032, PDF 178–180 |
| `CLC` | `f8` | Opaque effects; reviewed control | V3-GP-036, PDF 190–190 |
| `CMP16ri` | `6681fb0101` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP16ri8` | `6683fbff` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP16rr` | `6639d8` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP32ri` | `81fb01010101` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP32ri8` | `83fbff` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP32rr` | `39d8` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP64ri32` | `4881fb01010101` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP64ri8` | `4883fbff` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP64rr` | `4839d8` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP8ri` | `80fb01` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `CMP8rr` | `38d8` | Reviewed normal-continuation effects | V3-GP-044, PDF 204–206 |
| `DEC16r` | `66ffc8` | Reviewed normal-continuation effects | V3-GP-052, PDF 220–221 |
| `DEC32r` | `ffc8` | Reviewed normal-continuation effects | V3-GP-052, PDF 220–221 |
| `DEC64r` | `48ffc8` | Reviewed normal-continuation effects | V3-GP-052, PDF 220–221 |
| `DEC8r` | `fec8` | Reviewed normal-continuation effects | V3-GP-052, PDF 220–221 |
| `INC16r` | `66ffc0` | Reviewed normal-continuation effects | V3-GP-058, PDF 232–233 |
| `INC32r` | `ffc0` | Reviewed normal-continuation effects | V3-GP-058, PDF 232–233 |
| `INC64r` | `48ffc0` | Reviewed normal-continuation effects | V3-GP-058, PDF 232–233 |
| `INC8r` | `fec0` | Reviewed normal-continuation effects | V3-GP-058, PDF 232–233 |
| `JCC_1` | `7502` | Reviewed normal-continuation effects | V3-GP-062, PDF 245–248 |
| `JCC_4` | `0f8502000000` | Reviewed normal-continuation effects | V3-GP-062, PDF 245–248 |
| `JMP64m` | `ff20` | Reviewed normal-continuation effects | V3-GP-064, PDF 250–251 |
| `JMP64r` | `ffe0` | Reviewed normal-continuation effects | V3-GP-064, PDF 250–251 |
| `JMP_1` | `eb02` | Reviewed normal-continuation effects | V3-GP-064, PDF 250–251 |
| `JMP_4` | `e902000000` | Reviewed normal-continuation effects | V3-GP-064, PDF 250–251 |
| `LEA16r` | `668d4308` | Reviewed normal-continuation effects | V3-GP-068, PDF 260–261 |
| `LEA64_32r` | `8d4308` | Reviewed normal-continuation effects | V3-GP-068, PDF 260–261 |
| `LEA64r` | `488d4308` | Reviewed normal-continuation effects | V3-GP-068, PDF 260–261 |
| `MOV16mr` | `66894308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV16ri` | `66b80100` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV16rm` | `668b4308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV16rr` | `6689d8` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV32mr` | `894308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV32ri` | `b801000000` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV32rm` | `8b4308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV32rr` | `89d8` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV64mr` | `48894308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV64ri` | `48b80100000000000000` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV64ri32` | `48c7c0ffffffff` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV64rm` | `488b4308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV64rr` | `4889d8` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV8mr` | `884308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV8ri` | `b001` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV8rm` | `8a4308` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `MOV8rr` | `88d8` | Reviewed normal-continuation effects | V3-GP-080, PDF 282–284 |
| `NOOP` | `90` | Reviewed normal-continuation effects | V3-GP-096, PDF 314–314 |
| `OR16ri` | `6681cb0101` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR16ri8` | `6683cbff` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR16rr` | `6609d8` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR32ri` | `81cb01010101` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR32ri8` | `83cbff` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR32rr` | `09d8` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR64ri32` | `4881cb01010101` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR64ri8` | `4883cbff` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR64rr` | `4809d8` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR8ri` | `80cb01` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `OR8rr` | `08d8` | Reviewed normal-continuation effects | V3-GP-098, PDF 316–318 |
| `RET64` | `c3` | Opaque effects; reviewed control | V3-GP-120, PDF 353–354 |
| `SBB16ri` | `6681db0101` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB16ri8` | `6683dbff` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB16rr` | `6619d8` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB32ri` | `81db01010101` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB32ri8` | `83dbff` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB32rr` | `19d8` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB64ri32` | `4881db01010101` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB64ri8` | `4883dbff` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB64rr` | `4819d8` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB8ri` | `80db01` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `SBB8rr` | `18d8` | Reviewed normal-continuation effects | V3-GP-129, PDF 374–375 |
| `STC` | `f9` | Opaque effects; reviewed control | V3-GP-140, PDF 394–394 |
| `SUB16ri` | `6681eb0101` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB16ri8` | `6683ebff` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB16rr` | `6629d8` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB32ri` | `81eb01010101` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB32ri8` | `83ebff` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB32rr` | `29d8` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB64ri32` | `4881eb01010101` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB64ri8` | `4883ebff` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB64rr` | `4829d8` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB8ri` | `80eb01` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `SUB8rr` | `28d8` | Reviewed normal-continuation effects | V3-GP-143, PDF 398–399 |
| `TEST16ri` | `66f7c30101` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST16rr` | `6685d8` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST32ri` | `f7c301010101` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST32rr` | `85d8` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST64ri32` | `48f7c301010101` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST64rr` | `4885d8` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST8ri` | `f6c301` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `TEST8rr` | `84d8` | Reviewed normal-continuation effects | V3-GP-145, PDF 402–403 |
| `XOR16ri` | `6681f30101` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR16ri8` | `6683f3ff` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR16rr` | `6631d8` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR32ri` | `81f301010101` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR32ri8` | `83f3ff` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR32rr` | `31d8` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR64ri32` | `4881f301010101` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR64ri8` | `4883f3ff` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR64rr` | `4831d8` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR8ri` | `80f301` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
| `XOR8rr` | `30d8` | Reviewed normal-continuation effects | V3-GP-154, PDF 415–418 |
