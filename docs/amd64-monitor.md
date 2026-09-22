# AMD64 MONITORX and MWAITX

The paired model is in `Specs/AMD64Monitor.tla` and
`lean/AMD64/Monitor.lean`. Its authority is AMD APM Volume 3 revision 3.38:
MONITORX on PDF pages 280-281, MWAITX on pages 310-311, and CPUID function 5
monitor-line and extension enumeration on page 675.

MONITORX constructs a real one-byte `MachineAccess` read request from rAX, the
decoded address size, and DS or a decoded segment override. MachineAccess owns
segment, canonicality, paging, protection, and fault derivation. The byte value
is not read because MONITORX requires the access checks but does not consume the
data. The caller supplies an explicit effective memory-type resolution produced
by the shared memory-type model; the instruction never assumes WB.

For WB memory, the processor profile supplies a fixed range function. Every
resulting range must contain the resolved linear byte, contain no duplicate
addresses, and have a size within CPUID Fn5's minimum and maximum. A matching
committed store clears the pending range. For a resolved non-WB type, the APM
says entering the pending state is not guaranteed, so the result remains
`sourceUnspecified`. Undefined or unavailable memory typing is
modeling-unavailable.

MWAITX leaves architectural CPU state unchanged. ECX bits 31:2 are rejected;
ECX bit 0 requires IBE support, and bit 1 enables the EBX Software-P0-clock
timeout when EBX is nonzero. Wake observations are limited to a committed
overlapping store, timer expiry, interrupt eligibility, NMI, SMI, INIT, RESET,
or a far transfer. The observation supplies a cause, not a replacement state.

Validation:

```sh
cd Specs
apalache-mc typecheck AMD64MonitorChecks.tla
tlc -deadlock -cleanup -config AMD64Monitor.cfg AMD64MonitorChecks.tla
cd ../lean
lake build AMD64.Monitor
lake env lean AMD64/MonitorChecks.lean
lake env lean AMD64/MonitorAudit.lean
```
