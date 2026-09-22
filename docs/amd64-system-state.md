# AMD64 raw system controls and execution guards

`Specs/AMD64SystemState.tla` and `lean/AMD64/SystemState.lean` pair the raw
system controls needed by instruction-entry semantics. They do not replace the
application-visible CPU state. A complete machine composes `CPUState`, memory,
and this system-owned state.

The source baseline is AMD APM Volume 2 revision 3.45. CR0 and CR4 are from
PDF pages 105-117 and 123. Legacy and extended SSE enablement is from PDF pages
408-409. XCR0 layout and legality is from PDF pages 420-421. LWP use of XCR0
bit 62 is also stated on PDF pages 539 and 555.

The modeled CR0 fields are PE, MP, EM, TS, WP, and AM. The modeled CR4 fields
are VME, TSD, OSFXSR, OSXMMEXCPT, FSGSBASE, and OSXSAVE. XCR0 retains the full
64-bit enabled set and checks it against a separate processor-supported mask.
Defined state components are x87 bit 0, SSE bit 1, YMM bit 2, opmask bit 5,
ZMM high-256 bit 6, high-16 ZMM bit 7, MPK bit 9, and LWP bit 62.

XCR0 validity requires x87, requires SSE when YMM is enabled, and treats the
three AVX-512 state components as all-or-none with SSE and YMM. Reserved bits
must be clear and every enabled bit must be enumerated by the processor profile.

Instruction guards retain distinct causes:

- WAIT/FWAIT ignores CR0.EM and raises #NM exactly when CR0.MP and CR0.TS are
  both set.
- x87 uses #NM for EM or TS.
- MMX/media uses #UD for EM, #NM for TS, and retains pending #MF separately.
- legacy SSE uses #UD when unsupported, EM is set, or OSFXSR is clear; TS maps
  to #NM.
- AVX and AVX-512 additionally require OSXSAVE and the matching valid XCR0
  components.
- OSXMMEXCPT controls delivery of an unmasked SIMD exception; it is not an
  ordinary prerequisite for integer SIMD instructions.
- FSGSBASE requires long mode, processor support, and CR4.FSGSBASE.
- RDPRU uses CR4.TSD and CPL. LWP requires XSAVE support, CR4.OSXSAVE, valid
  XCR0 bit 62, and a protected execution mode.

`contextProjection` connects the older execution-context booleans to concrete
profile and control state. CR0.EM and CR0.TS stay outside that projection so
entry rules can report #UD and #NM precisely instead of losing their cause in a
single enablement Boolean.

Validation:

```sh
cd Specs
apalache-mc typecheck AMD64SystemStateChecks.tla
tlc -deadlock -cleanup -config AMD64SystemState.cfg AMD64SystemStateChecks.tla
cd ../lean
lake build AMD64.SystemState
lake env lean AMD64/SystemStateChecks.lean
lake env lean AMD64/SystemStateAudit.lean
```
