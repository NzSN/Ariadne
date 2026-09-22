# AMD64 external and profile-dependent instructions

Status: paired TLA+/Lean CPU body relations exist for 21 of 27 assigned entries.
The four LWP entries and MONITORX/MWAITX have executable TLA environment
contracts plus Lean CPU wrappers, but no paired TLA CPU transition, so they
remain explicitly partial. Shared form acceptance remains open.

The authoritative executable definitions are `Specs/AMD64External.tla` and
`lean/AMD64/External.lean`. The coverage and per-form source constraints are in
`Specs/AMD64/external-coverage.json` and
`Specs/AMD64/external-form-supplement.json`. Direct IN/OUT uses the shared
permission and device contract in `AMD64IO`; it does not treat absent capture or
an absent device rule as zero or as an architectural fault.

Legacy decimal adjustment is illegal in long mode. AAM with a zero immediate
raises #DE. Undefined arithmetic flags are relational, while every non-status
rFLAGS field is framed from the input state. AAA and AAS update AX as a 16-bit
add/subtract of 106h before masking AL to its low nibble, including carry and
borrow edge cases outside valid BCD inputs.

CPUID reads exact rows from a fixed processor profile. An absent row is a model
capture gap. RDRAND and RDSEED consume provenance-bearing environment samples;
RDSEED failure is constrained to zero, while the AMD RDRAND entry only calls the
failure value invalid, so that value remains environment supplied. RDPID and
RDPRU similarly read explicit processor-register state.

MOVD writes the canonical vector or x87/MMX alias bank. XMM destinations zero
bits above the scalar through bit 127 and retain bits 511:128. MMX writes clear
TOP, mark all tags valid, and set bits 79:64 of the written physical register to
ones. Full execution relations gate features, OS enablement, task-switch state,
pending x87 exceptions, CR4.OSFXSR, and the legacy XMM register range.
MOVMSKPS gates on SSE; MOVMSKPD and XMM MOVD gate on SSE2. CR0.TS maps to #NM,
while missing OSFXSR support maps to #UD; an unresolved higher-level SSE
enablement projection remains modeling-unavailable rather than inventing one of
those faults.

MONITORX records an armed range only after its one-byte address access has been
validated. MWAITX accepts a named wake observation constrained by ECX extension
bits, timer bounds, and monitor state. LWP uses ordered environment steps for
old-state flush, new-block validation, ring insertion, and faults. Those entries
stay partial until the complete Volume 2 Chapter 13 control block and record
layout is connected to concrete memory.

Validation commands:

```sh
cd Specs
apalache-mc typecheck AMD64ExternalChecks.tla
tlc -deadlock -cleanup -config AMD64External.cfg AMD64ExternalChecks.tla
cd ../lean
lake env lean AMD64/External.lean
lake env lean AMD64/ExternalChecks.lean
lake env lean AMD64/ExternalAudit.lean
```
