import AMD64.RegisterViews
import Std

/-!
Typed application-visible AMD64 CPU state.

Authority: AMD APM Volume 1, publication 24592 revision 3.25 (May 2026),
especially sections 1.2, 2.1.2, 2.5, 3.1, 4.2, 4.13.1, 4.13.3,
5.4.1, and 6.2. Volume 2 supplies the effective segment-cache interpretation
needed by application instructions; page tables, control registers, and memory
belong to the separate memory/protection model.

The model deliberately separates:

* `ArchitectureProfile`: implementation capabilities and width parameters;
* `CPUState`: concrete architectural register values and execution context;
* `CPUStateKnowledge`: what an adapter happens to know about those values.

The vector, MMX, and x87 views below are computed from canonical storage.
There is no independent XMM/YMM or MMX bank that could disagree with its
owner. `ValidCPUState` constrains reserved bits and mode/segment consistency;
instruction-specific writable masks and upper-bit clearing are transition
obligations, not state validity conditions.
-/

namespace AMD64.Arch

/-- Width-indexed little-endian bit sequence; index zero is the least-significant bit. -/
abbrev Bits (width : Nat) := Fin width → Bool

def Bits.zero : Bits width := fun _ => false

def Bits.low (outputWidth : Nat) (value : Bits inputWidth)
    (_bounds : outputWidth ≤ inputWidth) : Bits outputWidth :=
  fun bit => value ⟨bit.val, by omega⟩

def Bits.replaceLow (before : Bits storageWidth) (value : Bits valueWidth)
    (_bounds : valueWidth ≤ storageWidth) : Bits storageWidth :=
  fun bit => if h : bit.val < valueWidth then value ⟨bit.val, h⟩ else before bit

theorem Bits.low_replaceLow (before : Bits storageWidth) (value : Bits valueWidth)
    (_bounds : valueWidth ≤ storageWidth) :
    Bits.low valueWidth (Bits.replaceLow before value _bounds) _bounds = value := by
  funext bit
  simp [Bits.low, Bits.replaceLow]

theorem Bits.replaceLow_preserves_upper (before : Bits storageWidth)
    (value : Bits valueWidth) (bounds : valueWidth ≤ storageWidth)
    (bit : Fin storageWidth) (upper : valueWidth ≤ bit.val) :
    Bits.replaceLow before value bounds bit = before bit := by
  simp [Bits.replaceLow, show ¬ bit.val < valueWidth by omega]

/-- Architecturally distinct execution modes relevant to application code. -/
inductive OperatingMode where
  | real
  | protectedMode
  | virtual8086
  | compatibility
  | long64
  deriving DecidableEq, Repr

/-- Profile capabilities are implementation facts, never unknown CPU bytes. -/
structure Capabilities where
  longMode : Bool
  x87 : Bool
  mmx : Bool
  sse : Bool
  avx : Bool
  avx512 : Bool
  mxcsrMisalignedMask : Bool
  deriving DecidableEq, Repr

/-- Parameters fixed for one modeled processor implementation. -/
structure ArchitectureProfile where
  capabilities : Capabilities
  physicalAddressBits : Nat
  linearAddressBits : Nat
  deriving DecidableEq, Repr

/-- Width dependencies between extensions and architectural address bounds. -/
def ValidProfile (profile : ArchitectureProfile) : Prop :=
  32 ≤ profile.physicalAddressBits ∧
  profile.physicalAddressBits ≤ 64 ∧
  32 ≤ profile.linearAddressBits ∧
  profile.linearAddressBits ≤ 64 ∧
  (profile.capabilities.avx512 → profile.capabilities.avx) ∧
  (profile.capabilities.avx → profile.capabilities.sse) ∧
  (profile.capabilities.mmx → profile.capabilities.x87)

def ModeSupported (profile : ArchitectureProfile) : OperatingMode → Prop
  | .compatibility | .long64 => profile.capabilities.longMode
  | _ => True

/-- Current architectural execution context owned by the CPU-state layer. -/
structure ExecutionContext where
  mode : OperatingMode
  cpl : Fin 4
  x87Enabled : Bool
  sseEnabled : Bool
  avxEnabled : Bool
  avx512Enabled : Bool
  deriving DecidableEq, Repr

def GPRRegisterAvailable (context : ExecutionContext) (register : Fin 16) : Prop :=
  register.val < 8 ∨ context.mode = .long64

/-- Canonical architectural identity order used by forms and implicit operands. -/
inductive GPR where
  | rax | rcx | rdx | rbx | rsp | rbp | rsi | rdi
  | r8 | r9 | r10 | r11 | r12 | r13 | r14 | r15
  deriving DecidableEq, Repr

def GPR.index : GPR -> Nat
  | .rax => 0 | .rcx => 1 | .rdx => 2 | .rbx => 3
  | .rsp => 4 | .rbp => 5 | .rsi => 6 | .rdi => 7
  | .r8 => 8 | .r9 => 9 | .r10 => 10 | .r11 => 11
  | .r12 => 12 | .r13 => 13 | .r14 => 14 | .r15 => 15

def GPR.toFin (register : GPR) : Fin 16 := ⟨register.index, by cases register <;> decide⟩

theorem GPR.toFin_injective : Function.Injective GPR.toFin := by
  intro left right equal
  cases left <;> cases right <;> simp_all [GPR.toFin, GPR.index]

inductive GPRWidth where
  | bits8Low
  | bits8High
  | bits16
  | bits32
  | bits64
  deriving DecidableEq, Repr

/-- Storage-view availability only; prefix/register-code legality belongs to forms. -/
def GPRWidthAvailable (context : ExecutionContext) : GPRWidth → Prop
  | .bits64 => context.mode = .long64
  | _ => True

/-- A segment selector is stored as the exact 16-bit architectural value. -/
structure SegmentSelector where
  raw : Bits 16

def SegmentSelector.rpl (selector : SegmentSelector) : Bits 2 :=
  Bits.low 2 selector.raw (by omega)

def SegmentSelector.tableIndicator (selector : SegmentSelector) : Bool :=
  selector.raw ⟨2, by omega⟩

def SegmentSelector.index (selector : SegmentSelector) : Bits 13 :=
  fun bit => selector.raw ⟨bit.val + 3, by omega⟩

/--
Effective hidden descriptor information used by application accesses.
System-table provenance stays in the protection model, while this cache records
the values that affect address formation and permission checks.
-/
structure SegmentCache where
  base : Bits 64
  limit : Bits 32
  present : Bool
  dpl : Fin 4
  readable : Bool
  writable : Bool
  executable : Bool
  conforming : Bool
  expandDown : Bool
  defaultBig : Bool
  longMode : Bool

structure SegmentRegister where
  selector : SegmentSelector
  cache : SegmentCache
  unusable : Bool

structure SegmentContext where
  cs : SegmentRegister
  ss : SegmentRegister
  ds : SegmentRegister
  es : SegmentRegister
  fs : SegmentRegister
  gs : SegmentRegister

def SegmentCache.Valid (cache : SegmentCache) : Prop :=
  cache.conforming → cache.executable

def SegmentContext.Valid (segments : SegmentContext) : Prop :=
  segments.cs.cache.Valid ∧ segments.ss.cache.Valid ∧
  segments.ds.cache.Valid ∧ segments.es.cache.Valid ∧
  segments.fs.cache.Valid ∧ segments.gs.cache.Valid

/-- Default address width from the current mode and effective CS attributes. -/
def defaultAddressWidth (segments : SegmentContext) : OperatingMode → Nat
  | .long64 => 64
  | .compatibility | .protectedMode => if segments.cs.cache.defaultBig then 32 else 16
  | .real | .virtual8086 => 16

/-- Default CS instruction-pointer width; individual transfers can override it. -/
def defaultInstructionPointerWidth (segments : SegmentContext) : OperatingMode → Nat
  | .long64 => 64
  | .protectedMode | .compatibility => if segments.cs.cache.defaultBig then 32 else 16
  | .real | .virtual8086 => 16

/-- Every documented rFLAGS bit, including fixed/reserved positions. -/
structure RFlags where
  cf : Bool
  fixed1 : Bool
  pf : Bool
  reserved3 : Bool
  af : Bool
  reserved5 : Bool
  zf : Bool
  sf : Bool
  tf : Bool
  interruptEnable : Bool
  df : Bool
  of : Bool
  iopl : Bits 2
  nestedTask : Bool
  reserved15 : Bool
  resume : Bool
  virtual8086 : Bool
  ac : Bool
  virtualInterrupt : Bool
  virtualInterruptPending : Bool
  id : Bool
  reservedHigh : Bits 42

def RFlags.Valid (flags : RFlags) : Prop :=
  flags.fixed1 = true ∧
  flags.reserved3 = false ∧
  flags.reserved5 = false ∧
  flags.reserved15 = false ∧
  flags.reservedHigh = Bits.zero

def RFlags.low22 (flags : RFlags) : Bits 22 := fun bit =>
  match bit.val with
  | 0 => flags.cf
  | 1 => flags.fixed1
  | 2 => flags.pf
  | 3 => flags.reserved3
  | 4 => flags.af
  | 5 => flags.reserved5
  | 6 => flags.zf
  | 7 => flags.sf
  | 8 => flags.tf
  | 9 => flags.interruptEnable
  | 10 => flags.df
  | 11 => flags.of
  | 12 => flags.iopl ⟨0, by omega⟩
  | 13 => flags.iopl ⟨1, by omega⟩
  | 14 => flags.nestedTask
  | 15 => flags.reserved15
  | 16 => flags.resume
  | 17 => flags.virtual8086
  | 18 => flags.ac
  | 19 => flags.virtualInterrupt
  | 20 => flags.virtualInterruptPending
  | 21 => flags.id
  | _ => false

def RFlags.toBits (flags : RFlags) : Bits 64 := fun bit =>
  if h : bit.val < 22 then flags.low22 ⟨bit.val, h⟩
  else flags.reservedHigh ⟨bit.val - 22, by have := bit.isLt; omega⟩

theorem RFlags.valid_high_reserved_zero (flags : RFlags) (valid : flags.Valid)
    : flags.reservedHigh = Bits.zero := by
  exact valid.2.2.2.2

inductive X87Tag where
  | valid
  | zero
  | special
  | empty
  deriving DecidableEq, Repr

inductive X87Precision where
  | bits24
  | reserved
  | bits53
  | bits64
  deriving DecidableEq, Repr

inductive RoundingMode where
  | nearest
  | down
  | up
  | towardZero
  deriving DecidableEq, Repr

/-- The x87 status word with TOP represented by `Fin 8`. -/
structure X87Status where
  invalid : Bool
  denormal : Bool
  zeroDivide : Bool
  overflow : Bool
  underflow : Bool
  precision : Bool
  stackFault : Bool
  errorSummary : Bool
  c0 : Bool
  c1 : Bool
  c2 : Bool
  top : Fin 8
  c3 : Bool
  busy : Bool
  deriving DecidableEq, Repr

/-- x87 control word, with reserved fields retained for validity checking. -/
structure X87Control where
  invalidMask : Bool
  denormalMask : Bool
  zeroDivideMask : Bool
  overflowMask : Bool
  underflowMask : Bool
  precisionMask : Bool
  reserved6 : Bool
  reserved7 : Bool
  precisionControl : X87Precision
  roundingControl : RoundingMode
  infinityControl : Bool
  reservedHigh : Bits 3

def X87Control.Valid (control : X87Control) : Prop :=
  control.precisionControl ≠ .reserved

/-- FINIT/FNINIT reset image 037Fh from Volume 1 section 6.2.3. -/
def X87Control.init : X87Control := {
  invalidMask := true
  denormalMask := true
  zeroDivideMask := true
  overflowMask := true
  underflowMask := true
  precisionMask := true
  reserved6 := true
  reserved7 := false
  precisionControl := .bits64
  roundingControl := .nearest
  infinityControl := false
  reservedHigh := Bits.zero
}

def X87Control.low13 (control : X87Control) : Bits 13 := fun bit =>
  match bit.val with
  | 0 => control.invalidMask
  | 1 => control.denormalMask
  | 2 => control.zeroDivideMask
  | 3 => control.overflowMask
  | 4 => control.underflowMask
  | 5 => control.precisionMask
  | 6 => control.reserved6
  | 7 => control.reserved7
  | 8 => control.precisionControl == .bits53 ∨ control.precisionControl == .bits64
  | 9 => control.precisionControl == .bits64 ∨ control.precisionControl == .reserved
  | 10 => control.roundingControl == .down ∨ control.roundingControl == .towardZero
  | 11 => control.roundingControl == .up ∨ control.roundingControl == .towardZero
  | 12 => control.infinityControl
  | _ => false

def X87Control.toBits (control : X87Control) : Bits 16 := fun bit =>
  if h : bit.val < 13 then control.low13 ⟨bit.val, h⟩
  else control.reservedHigh ⟨bit.val - 13, by have := bit.isLt; omega⟩

theorem X87Control.init_matches_037f_fields :
    X87Control.init.invalidMask = true ∧
    X87Control.init.denormalMask = true ∧
    X87Control.init.zeroDivideMask = true ∧
    X87Control.init.overflowMask = true ∧
    X87Control.init.underflowMask = true ∧
    X87Control.init.precisionMask = true ∧
    X87Control.init.reserved6 = true ∧
    X87Control.init.reserved7 = false ∧
    X87Control.init.precisionControl = .bits64 ∧
    X87Control.init.roundingControl = .nearest ∧
    X87Control.init.infinityControl = false ∧
    X87Control.init.reservedHigh = Bits.zero := by
  exact ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Mode-sensitive software-visible encoding of the last x87 pointers. -/
inductive X87Pointer where
  | offset64 (offset : Bits 64)
  | selectorOffset (selector : Bits 16) (offset : Bits 32)
  | linear (address : Bits 32)

/-- Canonical x87 state; MMX aliases the low 64 bits of `physical`. -/
structure X87State where
  physical : Fin 8 → Bits 80
  tags : Fin 8 → X87Tag
  status : X87Status
  control : X87Control
  lastInstruction : X87Pointer
  lastData : X87Pointer
  lastOpcode : Bits 11

def X87State.st (state : X87State) (logical : Fin 8) : Bits 80 :=
  state.physical ⟨(state.status.top.val + logical.val) % 8, by omega⟩

def X87State.mmx (state : X87State) (register : Fin 8) : Bits 64 :=
  Bits.low 64 (state.physical register) (by omega)

theorem X87State.st_zero_is_top (state : X87State) :
    state.st ⟨0, by omega⟩ = state.physical state.status.top := by
  simp [X87State.st, Nat.mod_eq_of_lt state.status.top.isLt]

def updateAt [DecidableEq index] (values : index → value) (selected : index)
    (replacement : value) : index → value :=
  fun index => if index = selected then replacement else values index

@[simp] theorem updateAt_same [DecidableEq index] (values : index → value)
    (selected : index) (replacement : value) :
    updateAt values selected replacement selected = replacement := by
  simp [updateAt]

@[simp] theorem updateAt_other [DecidableEq index] (values : index → value)
    (selected other : index) (replacement : value) (different : other ≠ selected) :
    updateAt values selected replacement other = values other := by
  simp [updateAt, different]

/-!
Raw alias-storage update only. A real MMX instruction additionally changes the
x87 high 16 bits, TOP, and tags as specified by Volume 1 section 5.12. That
transition belongs to the instruction relation and must not be inferred here.
-/
def X87State.writeMMXStorageLow (state : X87State) (register : Fin 8)
    (value : Bits 64) : X87State :=
  { state with
    physical := updateAt state.physical register
      (Bits.replaceLow (state.physical register) value (by omega)) }

theorem X87State.read_write_mmx_storage_low_same (state : X87State) (register : Fin 8)
    (value : Bits 64) : (state.writeMMXStorageLow register value).mmx register = value := by
  simp [X87State.writeMMXStorageLow, X87State.mmx, Bits.low_replaceLow]

theorem X87State.write_mmx_storage_low_preserves_high (state : X87State)
    (register : Fin 8) (value : Bits 64) (bit : Fin 80) (high : 64 ≤ bit.val) :
    (state.writeMMXStorageLow register value).physical register bit = state.physical register bit := by
  simp [X87State.writeMMXStorageLow, Bits.replaceLow_preserves_upper, high]

/-- MXCSR fields from Volume 1 section 4.2.2, including reserved MBZ bits. -/
structure MXCSR where
  invalid : Bool
  denormal : Bool
  zeroDivide : Bool
  overflow : Bool
  underflow : Bool
  precision : Bool
  denormalsAreZero : Bool
  invalidMask : Bool
  denormalMask : Bool
  zeroDivideMask : Bool
  overflowMask : Bool
  underflowMask : Bool
  precisionMask : Bool
  roundingControl : RoundingMode
  flushToZero : Bool
  reserved16 : Bool
  misalignedMask : Bool
  reservedHigh : Bits 14

def MXCSR.Valid (profile : ArchitectureProfile) (mxcsr : MXCSR) : Prop :=
  mxcsr.reserved16 = false ∧
  mxcsr.reservedHigh = Bits.zero ∧
  (profile.capabilities.mxcsrMisalignedMask ∨ mxcsr.misalignedMask = false)

/-- Canonical AVX512-width vector storage. XMM and YMM are low-bit views. -/
abbrev VectorBank := Fin 32 → Bits 512
abbrev MaskBank := Fin 8 → Bits 64

def readXMM (vectors : VectorBank) (register : Fin 32) : Bits 128 :=
  Bits.low 128 (vectors register) (by omega)

def readYMM (vectors : VectorBank) (register : Fin 32) : Bits 256 :=
  Bits.low 256 (vectors register) (by omega)

def writeVectorLow (vectors : VectorBank) (register : Fin 32)
    (value : Bits width) (bounds : width ≤ 512) : VectorBank :=
  updateAt vectors register (Bits.replaceLow (vectors register) value bounds)

theorem readXMM_writeXMM_same (vectors : VectorBank) (register : Fin 32)
    (value : Bits 128) :
    readXMM (writeVectorLow vectors register value (by omega)) register = value := by
  simp [readXMM, writeVectorLow, Bits.low_replaceLow]

theorem readYMM_writeYMM_same (vectors : VectorBank) (register : Fin 32)
    (value : Bits 256) :
    readYMM (writeVectorLow vectors register value (by omega)) register = value := by
  simp [readYMM, writeVectorLow, Bits.low_replaceLow]

def VectorRegisterAvailable (profile : ArchitectureProfile) (context : ExecutionContext)
    (register : Fin 32) : Prop :=
  profile.capabilities.sse ∧
  if register.val < 8 then True
  else if register.val < 16 then context.mode = .long64
  else profile.capabilities.avx512 ∧ context.mode = .long64

inductive VectorWidth where
  | bits128
  | bits256
  | bits512
  deriving DecidableEq, Repr

def VectorWidthAvailable (profile : ArchitectureProfile) : VectorWidth → Prop
  | .bits128 => profile.capabilities.sse
  | .bits256 => profile.capabilities.avx
  | .bits512 => profile.capabilities.avx512

def MaskRegisterAvailable (profile : ArchitectureProfile) : Prop :=
  profile.capabilities.avx512

theorem avx512_implies_sse (profile : ArchitectureProfile)
    (valid : ValidProfile profile) (hasAVX512 : profile.capabilities.avx512) :
    profile.capabilities.sse := by
  rcases valid with ⟨_, _, _, _, avx512ToAvx, avxToSse, _⟩
  exact avxToSse (avx512ToAvx hasAVX512)

/-- Complete CPU-owned application-visible state; memory is composed elsewhere. -/
structure CPUState where
  gpr : Fin 16 → AMD64.Word
  rip : Bits 64
  rflags : RFlags
  segments : SegmentContext
  x87 : X87State
  vectors : VectorBank
  kMask : MaskBank
  mxcsr : MXCSR
  execution : ExecutionContext

def CPUState.gprValue (state : CPUState) (register : GPR) : AMD64.Word :=
  state.gpr register.toFin

def CPUState.rax (state : CPUState) := state.gprValue .rax
def CPUState.rcx (state : CPUState) := state.gprValue .rcx
def CPUState.rdx (state : CPUState) := state.gprValue .rdx
def CPUState.rbx (state : CPUState) := state.gprValue .rbx
def CPUState.rsp (state : CPUState) := state.gprValue .rsp
def CPUState.rbp (state : CPUState) := state.gprValue .rbp
def CPUState.rsi (state : CPUState) := state.gprValue .rsi
def CPUState.rdi (state : CPUState) := state.gprValue .rdi
def CPUState.r8 (state : CPUState) := state.gprValue .r8
def CPUState.r9 (state : CPUState) := state.gprValue .r9
def CPUState.r10 (state : CPUState) := state.gprValue .r10
def CPUState.r11 (state : CPUState) := state.gprValue .r11
def CPUState.r12 (state : CPUState) := state.gprValue .r12
def CPUState.r13 (state : CPUState) := state.gprValue .r13
def CPUState.r14 (state : CPUState) := state.gprValue .r14
def CPUState.r15 (state : CPUState) := state.gprValue .r15

@[simp] theorem CPUState.rcx_is_index_one (state : CPUState) :
    state.rcx = state.gpr ⟨1, by omega⟩ := rfl

@[simp] theorem CPUState.rsi_is_index_six (state : CPUState) :
    state.rsi = state.gpr ⟨6, by omega⟩ := rfl

@[simp] theorem CPUState.rdi_is_index_seven (state : CPUState) :
    state.rdi = state.gpr ⟨7, by omega⟩ := rfl

/-- Cross-field constraints, separate from transition-specific write rules. -/
def ValidCPUState (profile : ArchitectureProfile) (state : CPUState) : Prop :=
  ValidProfile profile ∧
  ModeSupported profile state.execution.mode ∧
  state.rflags.Valid ∧
  state.x87.control.Valid ∧
  state.mxcsr.Valid profile ∧
  state.segments.Valid ∧
  (state.execution.x87Enabled → profile.capabilities.x87) ∧
  (state.execution.sseEnabled → profile.capabilities.sse) ∧
  (state.execution.avxEnabled → state.execution.sseEnabled ∧ profile.capabilities.avx) ∧
  (state.execution.avx512Enabled → state.execution.avxEnabled ∧ profile.capabilities.avx512) ∧
  (state.execution.mode = .real → state.execution.cpl.val = 0) ∧
  (state.execution.mode = .virtual8086 → state.execution.cpl.val = 3) ∧
  (state.rflags.virtual8086 = true ↔ state.execution.mode = .virtual8086) ∧
  state.segments.cs.cache.present = true ∧
  state.segments.cs.unusable = false ∧
  state.segments.cs.cache.executable = true ∧
  (state.execution.mode = .long64 ↔ state.segments.cs.cache.longMode = true) ∧
  (state.segments.cs.cache.longMode = true → state.segments.cs.cache.defaultBig = false)

theorem valid_cpu_mode_supported (profile : ArchitectureProfile) (state : CPUState)
    (valid : ValidCPUState profile state) : ModeSupported profile state.execution.mode :=
  valid.2.1

theorem valid_cpu_cs_executable (profile : ArchitectureProfile) (state : CPUState)
    (valid : ValidCPUState profile state) : state.segments.cs.cache.executable = true :=
  by
    rcases valid with ⟨_, _, _, _, _, _, _, _, _, _, _, _, _, _, _, executable, _, _⟩
    exact executable

theorem valid_real_mode_cpl_zero (profile : ArchitectureProfile) (state : CPUState)
    (valid : ValidCPUState profile state) (mode : state.execution.mode = .real) :
    state.execution.cpl.val = 0 := by
  exact valid.2.2.2.2.2.2.2.2.2.2.1 mode

theorem valid_vm86_flag_agrees_with_mode (profile : ArchitectureProfile) (state : CPUState)
    (valid : ValidCPUState profile state) :
    state.rflags.virtual8086 = true ↔ state.execution.mode = .virtual8086 := by
  exact valid.2.2.2.2.2.2.2.2.2.2.2.2.1

/-- Knowledge belongs to analysis, not to the concrete machine domain. -/
inductive KnownBit where
  | known (value : Bool)
  | unknown
  deriving DecidableEq, Repr

abbrev KnownBits (width : Nat) := Fin width → KnownBit

structure CPUStateKnowledge where
  gpr : Fin 16 → KnownBits 64
  rip : KnownBits 64
  rflags : KnownBits 64
  x87Physical : Fin 8 → KnownBits 80
  vectors : Fin 32 → KnownBits 512
  kMask : Fin 8 → KnownBits 64

def knowBits (value : Bits width) : KnownBits width := fun bit => .known (value bit)

theorem knowBits_never_unknown (value : Bits width) (bit : Fin width) :
    knowBits value bit ≠ .unknown := by simp [knowBits]

namespace Source

/-!
Reviewed one-based transcription boundary for the width-indexed `LowBits`
operator in `Specs/AMD64ArchitecturalState.tla`. This proves the index shift and
alias view correspondence inside Lean. It does not parse TLA+ or prove that the
Lean transcription was generated from the source text.
-/

abbrev Index (width : Nat) := { index : Nat // 1 ≤ index ∧ index ≤ width }
abbrev Bits (width : Nat) := Index width → Bool

def toIndex (bit : Fin width) : Index width := ⟨bit.val + 1, by omega⟩
def fromIndex (bit : Index width) : Fin width :=
  ⟨bit.val - 1, by have := bit.property; omega⟩

def encode (value : AMD64.Arch.Bits width) : Bits width := fun bit =>
  value (fromIndex bit)

def decode (value : Bits width) : AMD64.Arch.Bits width := fun bit =>
  value (toIndex bit)

theorem decode_encode (value : AMD64.Arch.Bits width) :
    decode (encode value) = value := by
  funext bit
  simp [decode, encode, toIndex, fromIndex]

theorem encode_decode (value : Bits width) : encode (decode value) = value := by
  funext bit
  simp only [encode, decode]
  congr 1
  apply Subtype.ext
  simp only [toIndex, fromIndex]
  have := bit.property
  omega

/-- Direct one-based transcription of TLA+ `LowBits`. -/
def low (outputWidth : Nat) (value : Bits inputWidth)
    (_bounds : outputWidth ≤ inputWidth) : Bits outputWidth := fun bit =>
  value ⟨bit.val, by have := bit.property; omega⟩

theorem low_correspondence (value : AMD64.Arch.Bits inputWidth)
    (bounds : outputWidth ≤ inputWidth) :
    encode (AMD64.Arch.Bits.low outputWidth value bounds) =
      low outputWidth (encode value) bounds := by
  funext bit
  simp only [encode, AMD64.Arch.Bits.low, low]
  rfl

end Source

end AMD64.Arch
