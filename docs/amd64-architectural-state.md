# AMD64 architectural CPU state

Status: S1 source routing and the S2 CPU-local representation foundation are
implemented. This document describes their exact boundary. It does not claim
complete AMD64 instruction semantics, memory/protection semantics, or a proved
translation of arbitrary TLA+ into Lean.

## Purpose and module boundary

`Specs/AMD64ArchitecturalState.tla` is the authoritative vocabulary for
application-visible CPU state. `lean/AMD64/ArchitecturalState.lean` is its
machine-checked typed formalization. The modules own:

- processor state-bank capabilities and address-width parameters;
- current application execution mode, CPL, and derived feature enablement;
- canonical GPR storage and the current instruction pointer;
- every rFLAGS position, including fixed, reserved, and system-visible bits;
- segment selectors and the effective hidden descriptor values used by
  application accesses;
- x87 physical registers, stack mapping, tags, control, status, pointers, and
  last opcode;
- MMX views of shared x87 physical storage;
- canonical ZMM storage with XMM and YMM views, K masks, and MXCSR;
- CPU-local validity and alias invariants; and
- a separate analysis-knowledge type whose unknown bits are not CPU values.

Memory bytes, page maps, memory attributes, control registers, I/O permissions,
fault delivery, and observable memory or I/O events belong to the memory and
exception modules. The later composed machine state is a product of this
`CPUState`, real memory/protection state, and execution environment. This module
does not insert a memory token or callback in place of those components.

The pinned authority is AMD APM Volume 1, publication 24592 revision 3.25,
May 2026, SHA-256
`aed9236b718ae86cdb49f7d628f4ebb1a4bdce1a012df6cf6aad6735776c8a38`.
Required segment and enablement dependencies are completed by the pinned
Volume 2 model. PDF page numbers below are one-based PDF pages, not printed
manual page labels.

## Concrete source review

`Specs/AMD64/volume1-review.json` contains exactly the 298 numbered Volume 1
sections. Each row records its pinned ID, page, title, review depth, and one of
three roles:

- `architectural-obligation` for state, context, alias, capability, or validity;
- `instruction-behavior-obligation` for forms, transitions, exceptions, and
  save/restore effects; or
- `informational` for history, editorial text, and performance guidance that
  does not close a semantic obligation.

Classification routes work. It is not implementation evidence. Umbrella
sections are marked `umbrella-routed-to-descendants`. Architectural leaves
without a CPU field remain `open-cross-workstream-routing`. Rows backed only by
the bookmark title say `bookmark-role-reviewed`; state-bearing rows whose prose
was reconciled with the field inventory say `targeted-prose-reviewed`.

Volume 1 chapters 4 through 6 summarize many SIMD, MMX, and x87 instructions
whose detailed references are outside the accepted Volume 3 general-purpose
instruction target. Those rows are marked
`outside-volume3-gp-execution-scope`. They supply shared register, alias,
save/restore, feature, and exception-context constraints; they do not silently
expand the target to all instructions in Volumes 4 and 5.

`Specs/AMD64/state-fields.json` contains the field-level result. Stable IDs
begin with `STATE.`. Each row links source sections, canonical ownership,
profile guards, validity constraints, TLA+ operators, Lean declarations and
theorems, validation commands, and remaining obligations. A checked predicate
does not close an instruction transition.

The principal source evidence is:

| State | Volume 1 source | PDF page | Reconciled fact |
| --- | --- | ---: | --- |
| Modes | 1.2 through 1.2.4 | 44–46 | Real, protected, virtual-8086, compatibility, and 64-bit execution contexts |
| Memory and segments | 2.1 through 2.2 | 47–56 | Bytes, segment context, linear/canonical address constraints, and address formation are distinct |
| GPR and IP | 3.1.1, 3.1.2, 3.1.5 | 62, 64, 74 | Overlapping integer views, mode-dependent availability, and explicit IP storage |
| rFLAGS | 3.1.4 | 72 | Application flags plus fixed, reserved, and system-visible positions |
| Vector and MXCSR | 4.2.1, 4.2.2 | 151, 153 | XMM/YMM/ZMM overlap, K registers, MXCSR fields, reserved MBZ positions |
| AVX512 | 4.13.1, 4.13.3 | 273, 274 | 32 canonical 512-bit registers and eight 64-bit mask registers |
| MMX | 5.4.1, 5.12 | 284, 316 | MMX is the low 64-bit view of physical x87 storage; instruction execution also changes x87 metadata |
| x87 registers | 6.2.1 through 6.2.6 | 325–335 | Eight physical 80-bit registers, TOP mapping, status, control, tags, pointers, and opcode |

## Concrete representation

### Profile and current context

`ArchitectureProfile` records state-bank capabilities and physical/linear
address widths. Its seven booleans are not a complete CPUID feature model for
every Volume 3 form. The instruction-form layer composes its own form-feature
requirements with this profile.

`ExecutionContext` records the current mode, CPL, and four derived enablement
facts for x87, SSE, AVX, and AVX512. These are concrete context values, not
capabilities. `ValidCPUState` requires every enabled bank to have its profile
capability and requires the extension dependency chain. The composed machine
must additionally prove that these booleans agree with CR0, CR4, and XCR0;
those system registers belong to the memory/protection workstream.

The CPU-local cross-field rules include:

- real mode implies CPL 0;
- virtual-8086 mode implies CPL 3;
- the rFLAGS VM bit is set exactly in the virtual-8086 state;
- compatibility and 64-bit modes require long-mode capability;
- current CS is present, usable, and executable;
- CS.L agrees with 64-bit mode; and
- CS.L set implies CS.D clear.

### Integer state and instruction pointer

The one physical GPR bank contains sixteen 64-bit words. Low byte, high byte,
word, dword, and qword values are views of this bank. The existing
`AMD64RegisterViews` kernel supplies the read and 64-bit-mode write laws. State
availability and encoding legality remain separate: for example, physical
high-byte storage exists even when a REX encoding cannot name it.

The shared identity order is RAX, RCX, RDX, RBX, RSP, RBP, RSI, RDI, then R8
through R15 at indices 0 through 15. Lean and TLA+ expose named accessors and
checked mappings so explicit operands and string implicit registers cannot use
different numeric conventions.

The canonical IP store is 64 bits. `defaultInstructionPointerWidth` derives
the default 16, 32, or 64-bit CS view from mode and CS.D. It is deliberately
named *default*: an individual control-transfer rule can select another operand
or target width. A mode-only helper would lose this distinction and is absent.

### rFLAGS

`RFlags` gives each documented position a name. Application flags are CF, PF,
AF, ZF, SF, DF, and OF. TF, IF, IOPL, NT, RF, VM, AC, VIF, VIP, and ID are
retained because application instructions can observe, preserve, or attempt to
write them under mode and privilege rules.

Validity fixes bit 1 to one and bits 3, 5, 15, and 63:22 to zero. Instruction
write masks, undefined flag results, and privilege-dependent write suppression
are transition rules, not representational validity.

### Segments

Each of CS, SS, DS, ES, FS, and GS contains one exact 16-bit selector plus an
effective cache:

- 64-bit base;
- effective byte limit;
- present and unusable state;
- DPL;
- readable, writable, executable, and conforming-code attributes;
- expand-down, default-big, and long-mode attributes.

Selector RPL, table-indicator, and index are derived views. The effective byte
limit intentionally absorbs descriptor granularity expansion; the raw G bit is
system descriptor state, not a second application-visible limit. The descriptor
accessed bit and any memory write that sets it remain in the protection/memory
model. FS and GS bases remain available in 64-bit mode. The application of
ordinary CS, SS, DS, and ES bases or limits is mode-sensitive and belongs to
address/access rules.

The local predicate enforces `conforming` only for executable segments. Full
descriptor type, privilege, null selector, load, and access checks remain an
explicit Volume 2 obligation in the memory module.

### x87 and MMX

The canonical x87 store has eight physical 80-bit registers. Logical `ST(i)` is
physical register `(TOP + i) modulo 8`. The two-bit tag for each physical
register is one of valid, zero, special, or empty.

The status record represents all 16 status-word bits: six exception flags,
stack fault, exception summary, C0 through C3, TOP, and busy. TOP uses `Fin 8`
in Lean, making out-of-range values unrepresentable.

The control record represents all 16 FCW bits. Bits 6, 7, and 15:13 remain
explicit reserved storage because Volume 1 calls them reserved without giving
a universal arbitrary-load readback value. The PC encoding `01` is rejected.
The checked FINIT/FNINIT constructor has the exact 037Fh field image: exception
masks and bit 6 set, bit 7 clear, 64-bit precision, round-to-nearest, obsolete
infinity control clear, and bits 15:13 clear. This reset fact does not invent a
general write policy for reserved bits.

Last instruction and data pointers are tagged by the encoding that produced
them: 64-bit offset, selector plus offset, or real/virtual-8086 linear image.
They are historical x87 environment state. Validity does not force their tag to
match the *current* mode because a later mode transition does not retroactively
change the last-pointer representation.

MMXn is a derived low-64-bit view of physical FPRn. The Lean helper named
`writeMMXStorageLow` proves only the raw storage alias law. It is intentionally
not an architectural MMX instruction transition. Volume 1 section 5.12 also
changes the high 16 bits, TOP, and tags when executing 64-bit media
instructions; later instruction rules must implement those effects.

### Vector, mask, and MXCSR state

The single vector bank has 32 canonical 512-bit ZMM values. XMM is the low 128
bits and YMM is the low 256 bits of the same value. There are no independent
writable XMM or YMM copies. Register-number and width availability are explicit:
SSE enables 128-bit state use, AVX enables 256-bit use, AVX512 enables 512-bit
use, registers 8 through 15 require 64-bit mode, and registers 16 through 31
also require AVX512.

The K bank contains eight 64-bit registers. K0 is real storage even though
EVEX.aaa value zero means writemasking is disabled for an instruction.

MXCSR records all exception flags and masks, DAZ, rounding, FZ, the optional
misaligned-exception mask, bit 16, and bits 31:18. Bit 16 and bits 31:18 are
required zero. MM must be clear when the profile does not define it.

### Analysis knowledge

`CPUStateKnowledge` maps captured bits to `known(value)` or `unknown`. It is not
part of `CPUState`. A missing dump byte therefore cannot become architectural
zero, a nondeterministic CPU value, or a sentinel bit pattern.

## Concrete invariants

The type system establishes vector widths, bank cardinalities, TOP/CPL ranges,
tag alternatives, rounding alternatives, and pointer-shape alternatives.
Constructors plus `ValidCPUState` establish reserved-bit, feature dependency,
mode/CPL, VM flag, CS, and segment conforming invariants.

Instruction relations must preserve those invariants while applying their own
write masks and exceptional commit policy. This foundation does not yet prove a
single preservation theorem for every Volume 3 instruction because those
relations do not yet all exist.

## Representative alias trace

Consider an x87 state with TOP equal to 3 and physical FPR3 whose low 64 bits
are all one:

1. `ReadST(x87, 0)` computes physical index `(3 + 0) modulo 8`, so it returns
   all 80 bits of FPR3.
2. `ReadMMX(x87, 3)` selects the same physical FPR3 and returns its low 64 bits.
3. `writeMMXStorageLow(x87, 3, value)` replaces only those low 64 storage bits.
4. The alias theorem proves that reading MMX3 from that raw updated store
   returns `value`; a separate frame theorem proves the raw helper preserved
   bits 79:64.
5. An architectural MMX instruction cannot stop at step 4. Its relation must
   also apply the section 5.12 high-bit, TOP, and tag effects.

This trace exposes the abstraction boundary between a canonical storage/view
law and a complete instruction transition.

## First abstraction boundary

The model preserves exact CPU-visible bits, aliases, mode, CPL, bank
capabilities, current enablement, effective segment context, and the distinctions
between profile, concrete state, and analysis knowledge.

It erases microarchitectural physical register renaming, caches, pipelines,
speculation, internal one-bit x87 tag optimizations, and descriptor-cache
implementation layout. It also erases the raw descriptor granularity bit after
computing the effective byte limit.

## Minimal abstract machine

The CPU-local machine state is:

```text
CPUState =
  gpr × rip × rflags × segments × x87 × vectors × kMask × mxcsr × execution
```

The later architectural machine is:

```text
MachineState = CPUState × MemoryState × SystemConfiguration × Environment
```

An instruction transition consumes a validated form and a before machine state,
emits an observable event or exception outcome, and relates it to an after
machine state. This file supplies the CPU component and validity judgment, not
the complete step relation.

## Abstract operations and reachability

The delivered operations are pure views, raw canonical-storage updates, and
validity predicates. Important operations include GPR reads/writes, low-bit
vector views, ST mapping, MMX low view, selector decomposition, default address
width, and register availability.

Representable CPU records are broader than reachable architectural states.
`ValidCPUState(profile,state)` excludes fixed/reserved rFLAGS violations, invalid
FCW precision encoding, MXCSR MBZ violations, inconsistent mode/CPL or VM flag,
unsupported enabled features, and invalid current CS context. It does not claim
that every remaining valid record is reachable from reset.

## Typed judgments

The formalization uses these judgments, expressed as checked predicates:

```text
ValidProfile(profile)
ModeSupported(profile, mode)
ValidCPUState(profile, state)
VectorRegisterAvailable(profile, context, register)
VectorWidthAvailable(profile, width)
```

They mean that the named value satisfies the CPU-local representation and
cross-field constraints. Full instruction legality also needs decoded-form,
system configuration, memory/protection, and instruction-family judgments.

## TLA+ and Lean correspondence

TLA+ bit-vector positions are one-based. Lean `Bits width` uses `Fin width` and
is zero-based. `AMD64.Arch.Source` defines the reviewed one-based transcription,
both encode/decode round trips, and a theorem that Lean low-bit views correspond
to TLA+ `LowBits`. The existing register-view module separately proves the GPR
read/write correspondence.

This is a reviewed transcription boundary. No TLA+ parser or checked general
translation is claimed. Source hashes and operator names detect drift; they do
not turn a theorem between two Lean functions into a theorem about arbitrary
TLA+ text.

## Final abstraction boundary and open obligations

The following remain open and visible in the JSON artifacts:

- memory bytes, attributes, paging, I/O, access events, and faults are delegated
  to M2 and are not represented here;
- effective segment context still needs the complete Volume 2 load, privilege,
  null/unusable, descriptor-type, and access relations;
- current feature enablement must be related to CR0, CR4, and XCR0 in the
  composed machine;
- FCW arbitrary-load reserved-bit readback/write behavior is not inferred from
  the 037Fh reset image;
- GPR high-byte prefix legality and form-specific register availability belong
  to decoded-form validation;
- MMX execution metadata effects, legacy versus extended vector upper-bit
  effects, flag write masks, x87 save images, and all instruction-specific
  transitions remain instruction-family work; and
- Volume 1 media/x87 summaries outside the accepted Volume 3 general-purpose
  instruction scope do not create a requirement to implement all Volume 4/5
  instructions.

## Validation

Section headings alone cannot discharge coverage. A prose review of Volume 1
section 4.12.4 (PDF pages 269–271) found WC ordering and coherence constraints
inside performance guidance. Its review row now routes those constraints to
`STATE.memory.attributes`, with fence/locked-operation composition still open.
Other bookmark-only classifications remain routing evidence rather than proof
that a section contains no architectural requirements.

The focused checks are:

```sh
python3 tools/check_amd64_state.py check
cd Specs
apalache-mc typecheck AMD64ArchitecturalStateChecks.tla
tlc -deadlock -cleanup -config AMD64ArchitecturalState.cfg AMD64ArchitecturalStateChecks.tla
cd ../lean
lake env lean AMD64/ArchitecturalState.lean
lake build
lake env lean Audit.lean
```

Apalache checks the explicit Snowcat record types. TLC checks a full-width
fixture with TOP/ST, MMX, vector alias, feature, segment-width, FCW reset, and
CPU validity assertions. Lean proves alias laws, raw-update frames, profile and
state facts, FCW reset fields, knowledge separation, one-based representation
round trips, and low-view correspondence. These checks support the CPU-state
foundation; they are not evidence of full instruction or machine-state
coverage.
