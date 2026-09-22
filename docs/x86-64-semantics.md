# Executable x86-64 instruction semantics

Status: a checked TLA+ specification, not a Rust implementation or binary decoder.
The new [module](../Specs/AriadneX86_64Semantics.tla) computes outcomes from decoded
instructions and register/flag values. `StateSteps` is no longer a hand-authored
input when using its bridge to `AriadneMachineState`.

The [accepted AMD64 expansion](amd64-semantics-design.md) covers the full
general-purpose instruction reference and application-visible state, with a
Lean formalization. Its [source inventory and first foundation](../Specs/AMD64/README.md)
are separate from the register-only evaluator documented here. The wider scope
is a delivery target, not a claim that this module already implements it.

`Execute` is the instruction semantics interface; finite catalogue binding is
the seam to the existing propagation module. Neither module owns instruction
discovery.

## Supported scope

This is an initial **register/immediate subset in 64-bit mode**, not the entire
x86-64 ISA. The supported forms are:

| Instruction | Forms / behavior modeled |
| --- | --- |
| `MOV` | 32/64-bit GPR destination; same-width register or immediate source |
| `ADD`, `SUB` | Same operand forms, modulo operand width; six arithmetic flags |
| `CMP` | Subtraction flags without a destination write |
| `AND`, `OR`, `XOR` | Same operand forms; result flags and nondeterministic undefined AF |
| `TEST` | AND flags without a destination write |
| `NOP` | No state changes; decoded fallthrough |
| `JMP` | Direct near jump to a supplied resolved target |
| `Jcc` | All 16 flag-condition classes; taken or fallthrough edge |
| `UD2` | Terminal `faulted` outcome representing #UD before handler delivery |

Unsupported forms include 8/16-bit operands, memory operands, indirect jumps,
calls/returns, stack operations, shifts, multiplication/division, carry-input
arithmetic, SIMD/x87, system operations, and APX variants. Unsupported execution
returns an empty **modeled** outcome set, not proof of impossible execution and
not a no-op. `Supported` is separate; `CompleteSitesFor` excludes these sites,
causing `AriadneMachineState` to report `incomplete-semantics`.

Assumptions: a trusted decoder has validated the actual encoding, instruction
length, operand form, and prefixes in 64-bit mode. Records do not encode LOCK,
REP, APX, or malformed-prefix behavior. Instruction fetch, page permissions,
noncanonical-target faults, debug traps, interrupts, concurrency, memory, and
exception delivery are outside this projected machine. Only successfully
fetched, valid instructions under these environment assumptions are covered.
Do not read semantic completeness as whole-hardware exception completeness.

## State and instruction interface

```text
Execute(instruction, beforeState) -> set of outcomes

beforeState = {
  gpr:   {rax, rbx, ..., r15} -> 64-bit word,
  flags: {cf, pf, af, zf, sf, of} -> Boolean
}

outcome = {state, dst, kind, status}
```

Words are functions from `1..64` to Boolean, with bit 1 least significant.
Arithmetic uses carry look-ahead over bits, never a host integer containing
`2^64`. TLC can therefore execute genuine 64-bit wraparound and sign-bit cases
without reducing the architecture to a toy word width. `WordFromBytes` accepts
eight bytes indexed `1..8`, least-significant byte first; callers must supply
values in `0..255`.

`StateWellFormed` validates all 16 GPRs and six flags. These are **exact projected
states**. Missing/unknown register values must not be silently replaced with
zero. Multiple possible input states must be represented separately. The
projection does not describe memory, other RFLAGS bits, or the complete CPU.

`InstructionWellFormed` validates the normalized record shape:

| Field | Meaning |
| --- | --- |
| `op` | Lowercase operation name; conditional branches use `jcc` |
| `width` | Data operand width; supported data forms use 32 or 64, control forms use 0 |
| `dst` | Canonical 64-bit register owner, such as `rax` even for EAX |
| `source`, `sourceReg` | `reg` with canonical owner, `imm`, or an unsupported form |
| `immediate` | 64-bit word after decoder normalization |
| `next`, `target` | Decoded fallthrough and resolved direct target addresses |
| `condition` | One of `o/no/b/ae/e/ne/be/a/s/ns/p/np/l/ge/le/g` for `jcc`; empty otherwise |

Unused operand/register/condition fields use empty strings, and unused words or
addresses may use zero. For a 32-bit immediate, bits 33..64 must be zero. For
64-bit arithmetic/logical forms, the immediate must already be sign-extended
from imm32 (which also covers a sign-extended imm8). `MOV r64,imm64` permits any
word. Invalid combinations are unsupported; the model does not reconstruct
opcode bytes or validate the actual encoded immediate length.

A 32-bit register write zeroes the upper half of its 64-bit owner; a compare or
test does not write that owner. AF after a logical instruction has both Boolean
outcomes. Correlations are retained by calculating each entire output from the
same entire input; for example `xor eax,eax` produces zero even when analyzing
several different possible initial RAX values. Branches preserve register/flag
values and do not refine a per-location abstract set in violation of the old
frame contract. These rules follow the Intel references below.

`dst` is the next instruction address, not a general register. Thus RIP is the
coordinate of an instruction/state pair. A terminal outcome uses `dst=0` and
`kind=""` as unused sentinels; neither becomes a CFG edge. `UD2` retains the
pre-delivery register/flag values, with the faulting site supplied by the
terminal-transition record. It does not execute an exception handler.

`UsesOf`, `MustDefsOf`, and `MayDefsOf` derive the old normalized effect summaries.
Making AF undefined overwrites prior AF knowledge and is included in the write
set. Unsupported forms conservatively use/may-write all projected locations,
claim no definite writes, and have no supplied semantic transitions.

## Composition with state propagation

The existing [propagation module](../Specs/AriadneMachineState.tla) remains
unchanged. The new module supplies:

| New operator | Existing input |
| --- | --- |
| `RunningSteps(instructions, catalogue, statuses, edges)` | `StateSteps` |
| `TerminalSteps(instructions, catalogue, statuses)` | `TerminalTransitions` |
| `CompleteSitesFor(instructions, catalogue, statuses, edges)` | `CompleteSites` |
| `ValuationFor(catalogue, names)` | `Valuation` |
| `UsesOf` / `MustDefsOf` / `MayDefsOf` per instruction | Instruction effects |

The bridge is an exact-state specialization of the old finite abstract-state
catalogue. Each supplied ID names one projected register/flag state plus its
status. Register values have injective string names for the old reporting
interface; `CatalogueWellFormed` checks that those names cover the catalogue.
The names do not determine execution. Duplicate IDs with the same values/status
are allowed and all matching IDs are retained.

Before binding, callers must validate the catalogue, every instruction record,
and the composed `AriadneMachineState!InputContract` (including node domains,
edges, entry states, and snapshot identity). `Execute` itself requires a
well-formed input state. The integration fixture checks all these contracts.

Completeness requires every computed outcome for **every supplied running ID**
to have a matching result ID; running outcomes also require their exact
`(source, destination, kind)` edge. Missing states, terminal IDs, edges, or edge
kinds remove the site's completeness certificate. The partial bridge still
reports represented transitions and leaves an explicit obligation.

These obligations matter globally: missing upstream outcomes can prevent
downstream states from being reached. As in the original model, "unreachable"
and "infeasible" remain relative to supplied entry states, represented semantics,
and environment assumptions. Local completeness does not repair upstream gaps.

The evaluator can calculate a state not already in the catalogue. An eventual
Rust implementation can evaluate and intern states on demand; this finite
bridge does not implement such interning, widening, symbolic states, or an
efficient abstract interpreter. It also cannot add newly computed targets to
the frozen structural CFG. No claim is made that all concrete program states
have been enumerated.

## Executed checks

Run from the repository root:

```sh
bash Specs/check-x86-64.sh
```

The script typechecks the three new modules with Apalache and runs five TLC
configurations. It saves logs and checker artifacts in a fresh directory under
`/tmp` (or `TMPDIR`). The existing `check-apalache.sh` also discovers the new
modules for typechecking, but does not run these new fixtures as SMT checks.

The semantic checks include 512 small arithmetic input/operation combinations,
32/64-bit unsigned wrap and signed overflow boundaries, 32-bit zero-extension,
extended and same-register operands, unchanged registers after CMP/TEST,
immediate differences and sign extension, both undefined AF outcomes, and all
16 branch conditions over all 64 assignments of the six flags. They also check
frames, unsupported forms, duplicate IDs, missing AF alternatives, terminal
coverage, and edge-kind identity.

The integration fixture derives its transition tables using `Execute` for
`MOV EAX,5; CMP EAX,5; JE target; UD2; target: UD2`. It checks final states,
feasibility, retained structural edges, obligations, and terminal outcomes.
Separate scenarios remove a required state or edge, or substitute unsupported
`INC`; each must finish with partial results and no unjustified edge pruning.

Initial verification on 2026-09-19 used Apalache 0.61.0 (build `831d473`) and TLC
revision `1476e7f`. The semantic fixture and four integration scenarios passed;
the integration scenarios visited respectively 5, 3, 2, and 4 distinct states
(complete, unsupported, missing-state, missing-edge), including fair termination.
These are finite model checks, not a proof against hardware or a Rust MBT run.

An additional isolated mutation run rejected four deliberately broken rules by
`Safety` invariant violations: preserving the upper half on `MOV r32`, reversing
subtraction carry/borrow, forcing undefined AF to false, and certifying a site
despite a missing result state. The repository rules and test expectations were
not changed by that run. Main check artifacts were saved at
`/tmp/ariadne-x86-64.giThypiv`; mutation logs at
`/tmp/ariadne-x86-mutations.5eV5xyK9`.

## Primary references

Instruction knowledge is based on Intel's manuals, with model restrictions stated
above. No instruction pseudocode has been copied into the module.

- [Intel SDM Volume 1](https://cdrdv2.intel.com/v1/dl/getContent/671436), revision
  092, section 3.4.1.1: register widths and the upper-half effect of 32-bit writes.
- [Intel SDM Volume 2A](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf):
  `ADD`, `AND`, `CMP`, `Jcc`, and `JMP` entries, including flag conditions and
  normalized immediate sign extension. This URL returned revision 060 (2016).
- [Intel SDM Volume 2B](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf):
  `MOV`, `NOP`, `OR`, `SUB`, `TEST`, and `UD2` entries. The logical-result flags
  and undefined AF are modeled separately from arithmetic carry/overflow.
- [Intel SDM download index](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
  lists current manuals. The subset excludes newer instruction extensions;
  these checks do not certify a complete processor revision or all encodings.
