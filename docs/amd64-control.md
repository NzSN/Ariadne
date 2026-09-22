# AMD64 control-transfer foundation

The control workstream owns the 21 General-Purpose Instruction Reference
entries assigned to C3. This milestone implements checked conditional
predicates, near-target formation, explicit next-RIP retirement, executable
ordinary-stack primitives, major PUSH/POP projections, and real/v8086 far
transfer paths. It does not claim that all 21 entries are complete.
Exact entry/form status is recorded in `Specs/AMD64/control-coverage.json`.

TLA+ is authoritative. In this workstream it currently supplies a control and
stack projection kernel: branch predicates and targets, address/IP wrapping,
stack access plans, flag-image masks, multi-register order, tentative-fault
labels, and undefined-opcode selection. Lean contains both reviewed
transcriptions of those helpers and a larger CPU/concrete-memory binding
prototype. A successful Lean body does not become authoritative instruction
semantics until a matching TLA+ transition exists and correspondence is
checked.

## TLA+ and Lean pairing boundary

`control-coverage.json.pairing_rows` gives all 21 entries their exact TLA and
Lean symbols plus the remaining authoritative TLA gap. The status terms mean:

- `helper-paired`: the named TLA kernel and Lean helper cover the same local
  calculation; form dispatch and whole-instruction transitions can remain open.
- `projection-to-cpu-prototype-partial`: TLA fixes a plan, mask, or order while
  Lean additionally executes CPU/memory state changes. The extra Lean body is
  a prototype, not paired full-body semantics.
- `lean-cpu-prototype-unpaired`: Lean has an instruction-family body with no
  instruction-specific TLA transition.
- `unpaired-assumed-projection`: Lean records an assumed state projection and
  performs no architectural validation.
- `unmodeled`: neither language has an instruction rule.

Jcc, JrCXZ, and LOOP currently have helper pairing. UD0/UD1/UD2 have paired
fault selection. Near CALL/JMP/RET, PUSH/POP, PUSHA/POPA, and PUSHF/POPF have
TLA projections plus larger Lean prototypes. Far CALL/JMP/RET and ENTER/LEAVE
have unpaired Lean bodies. INT and INTO are unmodeled. Segment loads retain only
an explicitly assumed Lean projection. None of these classifications claims a
fully paired instruction body.

## Checked near-control behavior

`AMD64Control.tla` and `AMD64/Control.lean` define all 16 Jcc predicates from
CF, PF, ZF, SF, and OF. Synonymous source mnemonics map to the same predicate
without losing their source entry/form identities. Jcc chooses between a
checked following-instruction address and a signed relative target. JrCXZ uses
CX, ECX, or RCX according to address size. LOOP/LOOPcc performs an exact
address-sized decrement through the canonical RCX views, preserves flags, and
selects the branch from the new count and ZF. A 32-bit ECX decrement in long64
zeroes upper RCX through the canonical dword-write rule; 16-bit and legacy
32-bit writes preserve storage outside their view. Final
form validation and fetch/fault retirement remain explicit binding obligations.

Relative targets use the following-instruction RIP, never the branch's own
address. The displacement payload must record its encoded width, semantic
width, and sign extension. Addition is full-width and the result is truncated
to the instruction operand width. Near indirect register targets are read from
the actual GPR/view payload and zero-extended by the register-view primitive.
Memory-indirect target reads remain open until their operand access and fault
ordering are bound through `AMD64.MemoryModel`.

The decoder supplies a byte length and following-instruction address as a
`FallthroughEvidence` certificate. The model checks a length of 1 through 15,
performs full-width addition, and truncates the result to the effective IP
width before comparing `nextRIP`. Thus a legacy fallthrough wraps at 16 or 32
bits instead of being treated as a universal 64-bit sum.

Target validation is mode-specific. Long64 requires a canonical target under
the architecture profile. Legacy modes compare the target offset with the
effective CS limit. A successful retirement changes RIP and frames GPRs and
flags. `composeBody` accepts the integer lane's `bodyApplied` outcome only when
that body preserved the pre-retirement RIP, then applies the control decision.

## Stack and near CALL/RET

Stack address size is 64 in long64 and otherwise follows SS.D/B (16 or 32).
Near CALL push width follows CALL operand size. Its plan computes the decremented
stack pointer, an SS write `AddressRequest`, and the truncated following-
instruction RIP value.

The generic Lean stack prototype paths resolve requests through
`MemoryModel.resolveAccess`, writes little-endian bytes to
`ConcreteMemory.Store`, and update the actual SP, ESP, or RSP view. Stack
arithmetic wraps at that address size. In long64, dword view writes retain the
canonical GPR rule that clears the upper half.

Volume 3 pages 178-180 order near CALL's ordinary push before the target check,
and pages 353-354 order near RET's ordinary pop before the target check. That
pseudocode order does not by itself prove what a restartable exception exposes
architecturally. `TentativeStackEffect` therefore carries both the instruction
entry state and the internally produced stack state. Fault outcomes label the
latter tentative; exception delivery must decide visibility. No pushed or
popped state is exported as the architectural fault state.

Near RET resolves and reads the SS stack span from concrete memory, reconstructs
the popped RIP, advances the tentative stack pointer, and then validates the target. The optional
imm16 cleanup is applied only after target validation, matching the manual's
ordering. CET-enabled returns remain `controlProtectionBindingRequired`; they
are not treated as ordinary returns or silently accepted.

CALL/RET memory effects are executable foundations rather than complete
instructions. Remaining work includes captured-memory refinement proofs,
shadow-stack reads/writes and #CP priority, fetch/retirement composition,
memory-indirect call targets, and final exception delivery.

## PUSH, POP, flags, and frame instructions

The PUSH body projection covers register and immediate sources. It reads
rSP before decrement when rSP is the source, validates immediate extension,
pre-decrements the address-sized stack view, resolves an SS write, and stores
the operand-sized little-endian value. POP covers GPR destinations and applies
the destination write after the automatic stack increment, including the POP
rSP alias case. Memory and segment source/destination forms remain separate
obligations because their effective-address and descriptor ordering differs.

PUSHA/PUSHAD snapshot all eight source values before the first write and use the
manual order AX, CX, DX, BX, original SP, BP, SI, DI. POPA/POPAD use DI, SI, BP,
discarded SP image, BX, DX, CX, AX. Both reject long64 and preserve every
intermediate state only as a tentative effect when a later access faults.

PUSHF clears RF in the stored image and also clears VM in real/v8086 images.
POPF always clears RF, preserves VIF/VIP/VM, applies the protected-mode CPL/IOPL
mask to IOPL and IF, and keeps reserved bits valid. The current shared system
configuration has no CR4.VME field. Low-IOPL virtual-8086 16-bit execution
therefore returns `configurationBindingRequired`; an illegal non-16-bit case
returns the architectural general-protection outcome.

ENTER level zero pushes old rBP, captures the post-push frame pointer,
subtracts the zero-extended imm16 allocation, and performs the specified final
SS write-access check without storing a byte. Nesting levels 1 through 31 remain
explicitly unavailable; the decoded imm8 is masked to five bits before this
classification. LEAVE copies address-sized rBP to rSP, resolves the SS
pop, and writes operand-sized rBP. Its pre-pop rSP change is tentative on a
fault until delivery semantics settle visibility.

The source-backed Lean-prototype projection inventory is
`Specs/AMD64/control-form-supplement.json`: 27 forms are bound to these paths,
with residuals recorded per binding. This supplement does not modify or
overstate the shared table-reconciled form catalogue. `lean-prototype-bound` in
that file means bound to a reviewed Lean projection; it does not mean paired
with a full authoritative TLA instruction body.

## Far transfers, segment loads, and undefined opcodes

Far CALL, JMP, and RET have executable real/v8086 paths. Far CALL pushes old CS
then following IP, far RET pops IP then CS, and successful transfers construct
the real-mode CS base as selector shifted left four. Later target faults retain
the stack work only as tentative effects. Protected/long-mode descriptor,
call-gate, task-switch, privilege, stack-switch, and CET paths return explicit
binding outcomes.

Segment-load scaffolding uses `AssumedSegmentProjection`: selector equality
and the assumptions that table-limit, type, privilege, and present checks have
already happened are recorded before the destination selector/cache changes.
Missing evidence is a distinct
`assumedProjectionRequired` outcome, not a fault and not an arbitrary target
callback. The projection accepts a loaded cache only under explicitly named
assumptions; it does not validate descriptors and does not close any segment
form. Raw GDT/LDT bytes, table bounds, type, CPL/RPL/DPL, and presence must be
derived by the protection model. Compound far-pointer memory reads and their
GPR writes also remain open.

UD0, UD1, and UD2 each produce the invalid-opcode fault outcome. The separate
exception-delivery transition is still open.

## Explicitly open C3 areas

- Protected/long-mode far-transfer descriptor, gate, task-switch, privilege,
  stack-switch, and CET behavior.
- INT/INTO delivery and return-frame relationships.
- ENTER nesting levels 1 through 31 and fault visibility.
- PUSH/POP memory and segment forms, virtual-8086 VME flag paths, and exact
  architectural partial completion.
- Segment-load compound memory reads and derivation of descriptor evidence from
  modeled GDT/LDT state.
- UD0/UD1/UD2 exception delivery after fault selection.
- CET shadow-stack/token operations and control-protection priority.

These remain visible as entry-specific obligations. No arbitrary environment
callback supplies a target, descriptor, stack value, or fault result.

## Validation

```sh
apalache-mc typecheck Specs/AMD64Control.tla
apalache-mc typecheck Specs/AMD64ControlChecks.tla
tlc -workers 1 -metadir /tmp/amd64-control-tlc \
  -config AMD64Control.cfg AMD64ControlChecks.tla
(cd lean && lake build AMD64.ControlChecks AMD64.ControlAudit)
```

The current fixtures cover all Jcc conditions, CX-width zero tests, target
truncation/frame laws, retirement frames, and long64/legacy stack-address-size
selection, stack-width legality, PUSHA/POPA order, protected flag-write rules,
tentative fault labeling, and all three undefined-opcode selections. The TLA+
arithmetic uses explicit carry certificates; the Lean model uses the checked
full-width memory/address primitives. `ControlAudit.lean` checks the owned
namespace for forbidden proof dependencies.
