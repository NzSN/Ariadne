import AMD64.ArchitecturalState
import Std

/-!
Full-width AMD64 address, access, page-protection, and byte-state foundation.

Authority: AMD Volume 1 revision 3.25 sections 2.1, 2.2 and 3.8; AMD
Volume 2 revision 3.45 sections 4.3-4.13, 5.1-5.10, 7 and 8.2.

Addresses remain `Fin 64 -> Bool`, matching the canonical CPU storage. The
TLA+ source uses one-based Boolean maps and an explicit carry certificate;
this typed transcription computes the same ripple-carry result directly.

`PageMap` is a constrained, non-overlapping effective translation map. It is
not a model of CR3-rooted page walks, A/D-bit updates, TLBs, nested paging, or
all reserved-bit checks. `MemoryState` is the architectural byte projection,
not the D1 concurrency or ordering model. Those erased details remain named
coverage obligations in `Specs/AMD64/system-dependencies.json`.
-/

namespace AMD64.MemoryModel

open AMD64.Arch

noncomputable section

open scoped Classical

local instance addressDecidableEq : DecidableEq (Bits 64) :=
  Classical.typeDecidableEq _

abbrev Address := Bits 64
abbrev PhysicalAddress := Bits 64
abbrev Byte := Bits 8

def zeroAddress : Address := Bits.zero

inductive AddressSize where
  | bits16
  | bits32
  | bits64
  deriving DecidableEq, Repr

def AddressSize.width : AddressSize -> Nat
  | .bits16 => 16
  | .bits32 => 32
  | .bits64 => 64

/-- Legal address-size pairs before I2 binds the actual 67h prefix. -/
def addressSizePermitted (mode : OperatingMode) (defaultWidth : Nat)
    (size : AddressSize) : Prop :=
  match mode with
  | .long64 => defaultWidth = 64 ∧ (size = .bits32 ∨ size = .bits64)
  | .compatibility | .protectedMode =>
      (defaultWidth = 16 ∨ defaultWidth = 32) ∧
      (size = .bits16 ∨ size = .bits32)
  | .real | .virtual8086 =>
      defaultWidth = 16 ∧ (size = .bits16 ∨ size = .bits32)

/-- Truncate to the chosen address size, then zero-extend to 64 bits. -/
def effectiveOffset (raw : Address) (size : AddressSize) : Address := fun bit =>
  if bit.val < size.width then raw bit else false

def truncateWidth (raw : Address) (width : Nat) : Address := fun bit =>
  if bit.val < width then raw bit else false

theorem effectiveOffset_high_zero (raw : Address) (size : AddressSize)
    (bit : Fin 64) (high : size.width ≤ bit.val) :
    effectiveOffset raw size bit = false := by
  simp [effectiveOffset, show ¬ bit.val < size.width by omega]

theorem long64_forbids_16 : ¬ addressSizePermitted .long64 64 .bits16 := by
  simp [addressSizePermitted]

def xor3 (a b carry : Bool) : Bool := (a != b) != carry

def majority (a b carry : Bool) : Bool :=
  (a && b) || (a && carry) || (b && carry)

/-- Carry entering bit `index`; bit zero has no incoming carry. -/
def carryAt (left right : Address) : Nat -> Bool
  | 0 => false
  | index + 1 =>
      if h : index < 64 then
        majority (left ⟨index, h⟩) (right ⟨index, h⟩) (carryAt left right index)
      else false

/-- Full modulo-2^64 ripple-carry addition without host-sized integers. -/
def addAddress (left right : Address) : Address := fun bit =>
  xor3 (left bit) (right bit) (carryAt left right bit.val)

/-- Segment-base addition followed by the mode's linear-address width. -/
def linearAddress (mode : OperatingMode) (base effective : Address) : Address :=
  let sum := addAddress base effective
  match mode with
  | .long64 => sum
  | .compatibility | .protectedMode | .real | .virtual8086 =>
      truncateWidth sum 32

theorem protected_linear_high_zero (base effective : Address) (bit : Fin 64)
    (high : 32 ≤ bit.val) :
    linearAddress .protectedMode base effective bit = false := by
  simp [linearAddress, truncateWidth, show ¬ bit.val < 32 by omega]

theorem compatibility_linear_high_zero (base effective : Address) (bit : Fin 64)
    (high : 32 ≤ bit.val) :
    linearAddress .compatibility base effective bit = false := by
  simp [linearAddress, truncateWidth, show ¬ bit.val < 32 by omega]

private theorem carryAt_zero (index : Nat) :
    carryAt zeroAddress zeroAddress index = false := by
  induction index with
  | zero => rfl
  | succ index _ =>
      simp [carryAt, zeroAddress, Bits.zero, majority]

@[simp] theorem add_zero_zero : addAddress zeroAddress zeroAddress = zeroAddress := by
  funext bit
  change xor3 false false (carryAt zeroAddress zeroAddress bit.val) = false
  rw [carryAt_zero]
  rfl

/-- Embed a finite byte/count displacement in a full-width address. -/
def addressOfNat (value : Nat) : Address := fun bit => value.testBit bit.val

/-- Canonicality for a profile-selected implemented linear-address width. -/
def canonical (address : Address) (virtualBits : Nat) : Prop :=
  1 ≤ virtualBits ∧ virtualBits ≤ 64 ∧
  ∃ sign : Fin 64, sign.val + 1 = virtualBits ∧
    ∀ bit : Fin 64, virtualBits ≤ bit.val -> address bit = address sign

theorem zero_canonical (virtualBits : Nat) (low : 1 ≤ virtualBits)
    (high : virtualBits ≤ 64) : canonical zeroAddress virtualBits := by
  constructor
  · exact low
  constructor
  · exact high
  · let sign : Fin 64 := ⟨virtualBits - 1, by omega⟩
    refine ⟨sign, ?_, ?_⟩
    · simp [sign]
      omega
    intro bit _
    rfl

inductive SegmentReg where
  | cs | ss | ds | es | fs | gs
  deriving DecidableEq, Repr

def segmentRegister (state : CPUState) : SegmentReg -> SegmentRegister
  | .cs => state.segments.cs
  | .ss => state.segments.ss
  | .ds => state.segments.ds
  | .es => state.segments.es
  | .fs => state.segments.fs
  | .gs => state.segments.gs

/-- 64-bit mode suppresses ordinary DS/ES/SS bases; FS/GS remain effective. -/
def effectiveSegmentBase (mode : OperatingMode) (name : SegmentReg)
    (segment : SegmentRegister) : Address :=
  if mode = .long64 ∧ name ≠ .fs ∧ name ≠ .gs then zeroAddress
  else segment.cache.base

@[simp] theorem long64_ds_base_zero (segment : SegmentRegister) :
    effectiveSegmentBase .long64 .ds segment = zeroAddress := by
  simp [effectiveSegmentBase]

@[simp] theorem long64_fs_base (segment : SegmentRegister) :
    effectiveSegmentBase .long64 .fs segment = segment.cache.base := by
  simp [effectiveSegmentBase]

inductive AccessKind where
  | fetch | read | write | readWrite
  deriving DecidableEq, Repr

structure AccessKindInfo where
  kind : AccessKind
  implicitSupervisor : Bool := false
  shadowStack : Bool := false
  deriving DecidableEq, Repr

def AccessKind.isWrite : AccessKind -> Bool
  | .write | .readWrite => true
  | _ => false

def AccessKind.isFetch : AccessKind -> Bool
  | .fetch => true
  | _ => false

/-- Permission checks for an already-loaded effective segment cache. -/
private def compareAddress (left right : Address) : Nat -> Ordering
  | 0 => .eq
  | index + 1 =>
      if h : index < 64 then
        if left ⟨index, h⟩ = right ⟨index, h⟩ then
          compareAddress left right index
        else if left ⟨index, h⟩ then .gt else .lt
      else compareAddress left right index

def unsignedLE (left right : Address) : Bool :=
  compareAddress left right 64 != .gt

def segmentPermits (mode : OperatingMode) (cpl : Fin 4) (name : SegmentReg)
    (access : AccessKind) (segment : SegmentRegister)
    (effectiveStart effectiveEnd : Address) : Bool :=
  if mode = .long64 then true
  else if segment.unusable || !segment.cache.present then false
  else
    let rpl :=
      (if segment.selector.raw ⟨1, by omega⟩ then 2 else 0) +
      (if segment.selector.raw ⟨0, by omega⟩ then 1 else 0)
    let privilege :=
      if name = .ss then
        decide (cpl.val = rpl ∧ cpl = segment.cache.dpl)
      else if name = .cs then true
      else decide (max cpl.val rpl ≤ segment.cache.dpl.val)
    let accessType := match access with
      | .fetch => segment.cache.executable
      | .write | .readWrite => segment.cache.writable
      | .read => segment.cache.readable || !segment.cache.executable
    let bounds :=
      if segment.cache.expandDown then
        !unsignedLE effectiveStart (fun bit =>
          if h : bit.val < 32 then segment.cache.limit ⟨bit.val, h⟩ else false) &&
        (if segment.cache.defaultBig then decide
          (∀ bit : Fin 64, 32 ≤ bit.val -> effectiveEnd bit = false)
         else decide
          (∀ bit : Fin 64, 16 ≤ bit.val -> effectiveEnd bit = false))
      else unsignedLE effectiveEnd (fun bit =>
        if h : bit.val < 32 then segment.cache.limit ⟨bit.val, h⟩ else false)
    privilege && accessType && bounds

inductive MemoryType where
  | uncacheable | writeCombining | writeThrough | writeProtected
  | writeBack | uncached
  deriving DecidableEq, Repr

structure ProtectionKeyRights where
  accessDisable : Bool := false
  writeDisable : Bool := false
  deriving DecidableEq, Repr

/-- System-owned controls consumed by application instruction accesses. -/
structure SystemConfig where
  paging : Bool
  a20Enabled : Bool
  cr0AM : Bool
  cr0WP : Bool
  cr4PAE : Bool
  cr4SMEP : Bool
  cr4SMAP : Bool
  cr4PKE : Bool
  cr4CET : Bool
  eferNXE : Bool
  pkru : Fin 16 -> ProtectionKeyRights
  deniedIOPorts : Fin 65536 -> Bool

/-- A20 is a physical-address transformation after real/v8086 linear formation. -/
def a20Physical (config : SystemConfig) (mode : OperatingMode)
    (linear : Address) : PhysicalAddress := fun bit =>
  if (mode = .real ∨ mode = .virtual8086) ∧ !config.a20Enabled ∧ bit.val = 20
  then false else linear bit

theorem a20_disabled_clears_bit20 (config : SystemConfig) (linear : Address)
    (disabled : config.a20Enabled = false) :
    a20Physical config .real linear ⟨20, by omega⟩ = false := by
  simp [a20Physical, disabled]

theorem a20_enabled_preserves (config : SystemConfig) (mode : OperatingMode)
    (linear : Address) (enabled : config.a20Enabled = true) :
    a20Physical config mode linear = linear := by
  funext bit
  simp [a20Physical, enabled]

structure PageMapping where
  linearTag : Address
  physicalTag : PhysicalAddress
  offsetBits : Nat
  present : Bool
  writable : Bool
  user : Bool
  executable : Bool
  reserved : Bool
  shadowStack : Bool
  protectionKey : Fin 16
  memoryType : Option MemoryType

def PageMapping.Valid (page : PageMapping) : Prop :=
  (page.offsetBits = 12 ∨ page.offsetBits = 21 ∨ page.offsetBits = 22 ∨
    page.offsetBits = 30) ∧
  ∀ bit : Fin 64, bit.val < page.offsetBits ->
    page.linearTag bit = false ∧ page.physicalTag bit = false

def PageMapping.Matches (page : PageMapping) (linear : Address) : Prop :=
  ∀ bit : Fin 64, page.offsetBits ≤ bit.val -> linear bit = page.linearTag bit

/-- Prefix replacement preserves the page offset and supplies the frame tag. -/
def PageMapping.translate (page : PageMapping) (linear : Address) : PhysicalAddress :=
  fun bit => if bit.val < page.offsetBits then linear bit else page.physicalTag bit

theorem translate_preserves_offset (page : PageMapping) (linear : Address)
    (bit : Fin 64) (offset : bit.val < page.offsetBits) :
    page.translate linear bit = linear bit := by
  simp [PageMapping.translate, offset]

abbrev PageMap := List PageMapping

def PageMap.Valid (pages : PageMap) : Prop :=
  (∀ page ∈ pages, page.Valid) ∧
  ∀ left ∈ pages, ∀ right ∈ pages, left ≠ right ->
    ¬ ∃ address, left.Matches address ∧ right.Matches address

def PageMap.resolve (pages : PageMap) (linear : Address) : Option PageMapping :=
  pages.find? fun page => decide (page.Matches linear)

structure PageFaultError where
  present : Bool
  write : Bool
  user : Bool
  reserved : Bool
  instruction : Bool
  instructionDefined : Bool
  protectionKey : Bool
  shadowStack : Bool
  shadowStackDefined : Bool
  deriving DecidableEq, Repr

def PageMapping.permits (config : SystemConfig) (cpl : Fin 4)
    (rflagsAC : Bool) (access : AccessKindInfo) (page : PageMapping) : Bool :=
  let supervisor := cpl.val < 3
  let rights := config.pkru page.protectionKey
  let write := access.kind.isWrite
  let fetch := access.kind.isFetch
  let pkruDenied := config.cr4PKE && page.user && !fetch &&
    (rights.accessDisable || (write && rights.writeDisable &&
      (!supervisor || config.cr0WP)))
  let smepDenied := config.cr4SMEP && supervisor && page.user && fetch
  let smapDenied := config.cr4SMAP && page.user && !fetch &&
    !access.shadowStack &&
    (access.implicitSupervisor || (supervisor && !rflagsAC))
  let writeDenied := write && !page.writable &&
    (!supervisor || config.cr0WP) && !access.shadowStack
  let userDenied := cpl.val = 3 && !page.user
  let nxDenied := fetch && config.eferNXE && !page.executable
  let shadowDenied := (access.shadowStack != page.shadowStack) &&
    (access.shadowStack || (page.shadowStack && write))
  page.present && !page.reserved && !pkruDenied && !smepDenied &&
    !smapDenied && !writeDenied && !userDenied && !nxDenied && !shadowDenied

def pageFaultError (config : SystemConfig) (cpl : Fin 4)
    (access : AccessKindInfo) (page : PageMapping) : PageFaultError :=
  let rights := config.pkru page.protectionKey
  let supervisor := cpl.val < 3
  let instructionDefined := config.eferNXE && config.cr4PAE
  let shadowStackDefined := config.cr4CET
  { present := page.present
    write := access.kind.isWrite
    user := cpl.val = 3
    reserved := page.reserved
    instruction := instructionDefined && access.kind.isFetch
    instructionDefined
    protectionKey := config.cr4PKE && page.user && !access.kind.isFetch &&
      (rights.accessDisable || (access.kind.isWrite && rights.writeDisable &&
        (!supervisor || config.cr0WP)))
    shadowStack := shadowStackDefined && access.shadowStack
    shadowStackDefined }

inductive AccessFault where
  | generalProtection
  | stack
  | page (linear : Address) (code : PageFaultError)
  | alignment

inductive ResolutionError where
  | invalidAddressSize
  | invalidByteCount
  | unsupportedA20PagingInteraction
  | fault (cause : AccessFault)

structure AddressRequest where
  rawEffective : Address
  addressSize : AddressSize
  segment : SegmentReg
  access : AccessKindInfo
  byteCount : Nat
  alignmentBits : Nat := 0

structure ResolvedByte where
  linear : Address
  physical : PhysicalAddress
  page : Option PageMapping

structure ResolvedAccess where
  effective : Address
  linear : Address
  bytes : List ResolvedByte
  request : AddressRequest

def aligned (linear : Address) (alignmentBits : Nat) : Prop :=
  alignmentBits ≤ 6 ∧
  ∀ bit : Fin 64, bit.val < alignmentBits -> linear bit = false

def alignmentFault (config : SystemConfig) (state : CPUState)
    (linear : Address) (alignmentBits : Nat) : Prop :=
  config.cr0AM = true ∧ state.rflags.ac = true ∧
  state.execution.cpl.val = 3 ∧ ¬ aligned linear alignmentBits

def spanCanonical (span : List Address) (virtualBits : Nat) : Prop :=
  ∀ address ∈ span, canonical address virtualBits

def resolveByte (config : SystemConfig) (state : CPUState) (pages : PageMap)
    (access : AccessKindInfo) (linear : Address) :
    Except AccessFault ResolvedByte :=
  if config.paging then
    match pages.resolve linear with
    | none => .error (.page linear
        (PageFaultError.mk false access.kind.isWrite
          (state.execution.cpl.val = 3) false
          (config.eferNXE && config.cr4PAE && access.kind.isFetch)
          (config.eferNXE && config.cr4PAE) false
          (config.cr4CET && access.shadowStack) config.cr4CET))
    | some page =>
        if page.permits config state.execution.cpl state.rflags.ac access then
          .ok { linear, physical := page.translate linear, page := some page }
        else .error (.page linear (pageFaultError config state.execution.cpl access page))
  else .ok (ResolvedByte.mk linear
    (a20Physical config state.execution.mode linear) none)

private def resolveBytes (config : SystemConfig) (state : CPUState)
    (pages : PageMap) (access : AccessKindInfo) :
    List Address -> Except AccessFault (List ResolvedByte)
  | [] => .ok []
  | linear :: rest => do
      let byte <- resolveByte config state pages access linear
      let tail <- resolveBytes config state pages access rest
      pure (byte :: tail)

/--
Resolve all bytes in ascending address order. Page faults are detected before
ordinary #AC. Per-form mandatory-alignment #GP and access suppression belong to
the instruction rule and do not use this ordinary alignment predicate.
-/
def resolveAccess (profile : ArchitectureProfile) (config : SystemConfig)
    (state : CPUState) (pages : PageMap) (request : AddressRequest) :
    Except ResolutionError ResolvedAccess := do
  let defaultWidth := defaultAddressWidth state.segments state.execution.mode
  if ¬ addressSizePermitted state.execution.mode defaultWidth request.addressSize then
    throw .invalidAddressSize
  if request.byteCount = 0 then throw .invalidByteCount
  if state.execution.mode ∈ [.real, .virtual8086] && config.paging &&
      !config.a20Enabled then
    throw .unsupportedA20PagingInteraction
  let segment := segmentRegister state request.segment
  let effective := effectiveOffset request.rawEffective request.addressSize
  let effectiveAt (offset : Nat) := effectiveOffset
    (addAddress effective (addressOfNat offset)) request.addressSize
  let effectiveEnd := effectiveAt (request.byteCount - 1)
  if !segmentPermits state.execution.mode state.execution.cpl request.segment
      request.access.kind segment effective effectiveEnd then
    throw (.fault (if request.segment = .ss then .stack else .generalProtection))
  let segmentBase := effectiveSegmentBase state.execution.mode request.segment segment
  let linearAt (offset : Nat) := linearAddress state.execution.mode segmentBase
    (effectiveAt offset)
  let linear := linearAt 0
  let linearSpan := (List.range request.byteCount).map linearAt
  if state.execution.mode = .long64 ∧
      ¬ spanCanonical linearSpan profile.linearAddressBits then
    throw (.fault (if request.segment = .ss then .stack else .generalProtection))
  let bytes <- (resolveBytes config state pages request.access linearSpan).mapError .fault
  if alignmentFault config state linear request.alignmentBits then
    throw (.fault .alignment)
  pure { effective, linear, bytes, request }

structure ByteCell where
  physical : PhysicalAddress
  value : Byte

structure MemoryState where
  cells : List ByteCell
  captured : List PhysicalAddress

/-- Total architectural bytes over the modeled physical-address domain. -/
structure ConcreteMemory where
  byteAt : PhysicalAddress -> Byte

def MemoryState.Valid (memory : MemoryState) : Prop :=
  (memory.cells.Pairwise fun left right => left.physical ≠ right.physical) ∧
  (memory.captured.Pairwise (· ≠ ·)) ∧
  (∀ cell ∈ memory.cells, cell.physical ∈ memory.captured) ∧
  (∀ physical ∈ memory.captured, ∃ cell ∈ memory.cells, cell.physical = physical)

inductive MemoryReadResult where
  | available (value : Byte)
  | unavailable

def MemoryState.readByte (memory : MemoryState) (physical : PhysicalAddress) :
    MemoryReadResult :=
  match memory.cells.find? fun cell => decide (cell.physical = physical) with
  | some cell => .available cell.value
  | none => .unavailable

def MemoryState.writeByte (memory : MemoryState) (physical : PhysicalAddress)
    (value : Byte) : MemoryState :=
  { cells := { physical, value } :: memory.cells.filter
      (fun cell => decide (cell.physical ≠ physical))
    captured := if physical ∈ memory.captured then memory.captured
      else physical :: memory.captured }

def MemoryState.read (memory : MemoryState) (access : ResolvedAccess) :
    List MemoryReadResult :=
  access.bytes.map fun byte => memory.readByte byte.physical

/-- Bytes are supplied least-significant first, matching AMD little endian. -/
def MemoryState.write (memory : MemoryState) (access : ResolvedAccess)
    (value : List Byte) : Option MemoryState :=
  if access.bytes.length ≠ value.length then none
  else some ((access.bytes.zip value).foldl
    (fun current entry => current.writeByte entry.1.physical entry.2) memory)

theorem absent_byte_is_unavailable (memory : MemoryState) (physical : PhysicalAddress)
    (absent : ∀ cell ∈ memory.cells, cell.physical ≠ physical) :
    memory.readByte physical = .unavailable := by
  have missing : memory.cells.find? (fun cell => decide (cell.physical = physical)) =
      none := by
    apply List.find?_eq_none.mpr
    intro cell member
    simp [absent cell member]
  simp [MemoryState.readByte, missing]

inductive MemoryEventKind where
  | read | write | readModifyWrite | instructionFetch | ioRead | ioWrite
  deriving DecidableEq, Repr

structure MemoryEvent where
  kind : MemoryEventKind
  linear : Option Address
  physical : Option PhysicalAddress
  size : Nat
  value : List Byte
  memoryType : Option MemoryType

def ioPermitted (state : CPUState) (config : SystemConfig)
    (port : Fin 65536) : Bool :=
  let iopl := (if state.rflags.iopl ⟨1, by omega⟩ then 2 else 0) +
              (if state.rflags.iopl ⟨0, by omega⟩ then 1 else 0)
  state.execution.cpl.val ≤ iopl || !config.deniedIOPorts port

namespace Source

/-!
Reviewed one-based transcription of the address representation and
`EffectiveOffset` operator in `Specs/AMD64Memory.tla`. These theorems establish
correspondence to that transcription, not to a parsed TLA+ module.
-/

abbrev Index := { n : Nat // 1 ≤ n ∧ n ≤ 64 }
abbrev Address := Index -> Bool

def toIndex (bit : Fin 64) : Index := ⟨bit.val + 1, by omega⟩
def fromIndex (bit : Index) : Fin 64 := ⟨bit.val - 1, by have := bit.property; omega⟩

def encode (address : AMD64.MemoryModel.Address) : Address :=
  fun bit => address (fromIndex bit)

def decode (address : Address) : AMD64.MemoryModel.Address :=
  fun bit => address (toIndex bit)

theorem decode_encode (address : AMD64.MemoryModel.Address) :
    decode (encode address) = address := by
  funext bit
  simp [decode, encode, toIndex, fromIndex]

theorem encode_decode (address : Address) : encode (decode address) = address := by
  funext bit
  simp only [encode, decode]
  congr 1
  apply Subtype.ext
  simp only [toIndex, fromIndex]
  have := bit.property
  omega

def effectiveOffset (raw : Address) (size : AddressSize) : Address :=
  fun bit => if bit.val ≤ size.width then raw bit else false

theorem effectiveOffset_correspondence (raw : AMD64.MemoryModel.Address)
    (size : AddressSize) :
    encode (AMD64.MemoryModel.effectiveOffset raw size) =
      effectiveOffset (encode raw) size := by
  funext bit
  have bounds := bit.property
  simp only [encode, AMD64.MemoryModel.effectiveOffset, effectiveOffset]
  by_cases h : bit.val ≤ size.width
  · have translated : (fromIndex bit).val < size.width := by
      simp only [fromIndex]
      omega
    simp [h, translated]
  · have translated : ¬ (fromIndex bit).val < size.width := by
      simp only [fromIndex]
      omega
    simp [h, translated]

end Source

end
end AMD64.MemoryModel
