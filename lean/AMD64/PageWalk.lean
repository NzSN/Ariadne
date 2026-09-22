import AMD64.ConcreteMemory
import Std

/-!
Explicit AMD64 page-walk certificates and executable validators.

Authority: AMD Volume 2 revision 3.45 sections 5.2-5.6, PDF pages 195-232.
The validator recomputes every physical entry address from the full-width
linear address and prior entry base. `tableMemory` is an explicit list of raw
physical page-table cells, not an environment lookup callback.

The common raw-bit checks cover long-mode four/five-level, PAE, and non-PAE
legacy paths. Variant-specific reserved/available/PAT/global encodings that are
not yet represented remain listed in `docs/amd64-page-walk.md`; the presence of
a path shape does not close that variant's full architectural coverage.
-/

namespace AMD64.PageWalk

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory

abbrev RawEntry := Bits 64

inductive Variant where
  | long4 | long5 | pae | legacy
  deriving DecidableEq, Repr

inductive Level where
  | pml5 | pml4 | pdpt | pd | pt
  deriving DecidableEq, Repr

structure Config where
  variant : Variant
  root : PhysicalAddress
  physicalBits : Nat
  nxe : Bool
  cet : Bool
  oneGiB : Bool

def Config.Valid (config : Config) : Prop :=
  32 ≤ config.physicalBits ∧ config.physicalBits ≤ 52 ∧
  (∀ bit : Fin 64, bit.val < 12 -> config.root bit = false) ∧
  (config.variant = .legacy -> config.physicalBits = 32 ∧ config.nxe = false)

structure Entry where
  level : Level
  physical : PhysicalAddress
  raw : RawEntry

structure TableCell where
  physical : PhysicalAddress
  raw : RawEntry
  bytes : List Byte
  available : Bool

structure Certificate where
  entries : List Entry

def Entry.present (entry : Entry) : Bool := entry.raw ⟨0, by omega⟩
def Entry.writable (entry : Entry) : Bool := entry.raw ⟨1, by omega⟩
def Entry.user (entry : Entry) : Bool := entry.raw ⟨2, by omega⟩
def Entry.accessed (entry : Entry) : Bool := entry.raw ⟨5, by omega⟩
def Entry.dirty (entry : Entry) : Bool := entry.raw ⟨6, by omega⟩
def Entry.large (entry : Entry) : Bool := entry.raw ⟨7, by omega⟩
def Entry.nx (entry : Entry) : Bool := entry.raw ⟨63, by omega⟩

def expectedLevels (variant : Variant) (pageBits : Nat) : List Level :=
  match variant, pageBits with
  | .long4, 12 => [.pml4, .pdpt, .pd, .pt]
  | .long4, 21 => [.pml4, .pdpt, .pd]
  | .long4, 30 => [.pml4, .pdpt]
  | .long5, 12 => [.pml5, .pml4, .pdpt, .pd, .pt]
  | .long5, 21 => [.pml5, .pml4, .pdpt, .pd]
  | .long5, 30 => [.pml5, .pml4, .pdpt]
  | .pae, 12 => [.pdpt, .pd, .pt]
  | .pae, 21 => [.pdpt, .pd]
  | .legacy, 12 => [.pd, .pt]
  | .legacy, 22 => [.pd]
  | _, _ => []

theorem long4_4k_depth : (expectedLevels .long4 12).length = 4 := rfl
theorem long5_4k_depth : (expectedLevels .long5 12).length = 5 := rfl
theorem pae_4k_depth : (expectedLevels .pae 12).length = 3 := rfl
theorem legacy_4k_depth : (expectedLevels .legacy 12).length = 2 := rfl

def indexLowBit (variant : Variant) : Level -> Nat
  | .pml5 => 48
  | .pml4 => 39
  | .pdpt => 30
  | .pd => if variant = .legacy then 22 else 21
  | .pt => 12

def indexWidth (variant : Variant) (level : Level) : Nat :=
  if variant = .legacy then 10
  else if variant = .pae ∧ level = .pdpt then 2 else 9

def entryShift (variant : Variant) : Nat :=
  if variant = .legacy then 2 else 3

def addressBit (address : Address) (index : Nat) : Bool :=
  if h : index < 64 then address ⟨index, h⟩ else false

/-- The selected page-table index multiplied by the entry byte size. -/
def indexDisplacement (linear : Address) (variant : Variant)
    (level : Level) : Address := fun bit =>
  let low := indexLowBit variant level
  let width := indexWidth variant level
  let shift := entryShift variant
  if _h : shift ≤ bit.val ∧ bit.val < shift + width then
    addressBit linear (low + bit.val - shift)
  else false

theorem indexDisplacement_below_shift_zero (linear : Address) (variant : Variant)
    (level : Level) (bit : Fin 64) (below : bit.val < entryShift variant) :
    indexDisplacement linear variant level bit = false := by
  simp [indexDisplacement, show ¬ entryShift variant ≤ bit.val by omega]

def entryBase (config : Config) (entry : Entry) : PhysicalAddress := fun bit =>
  if 12 ≤ bit.val ∧ bit.val < config.physicalBits then entry.raw bit else false

def leafBase (config : Config) (entry : Entry) (pageBits : Nat) : PhysicalAddress :=
  fun bit => if pageBits ≤ bit.val ∧ bit.val < config.physicalBits
    then entry.raw bit else false

theorem entryBase_aligned (config : Config) (entry : Entry) (bit : Fin 64)
    (low : bit.val < 12) : entryBase config entry bit = false := by
  simp [entryBase, show ¬ 12 ≤ bit.val by omega]

def nxEffective (config : Config) (entry : Entry) : Bool :=
  if config.variant = .legacy ∨
      (config.variant = .pae ∧ entry.level = .pdpt) then false
  else entry.nx

private def anyBit (start stop : Nat) (value : RawEntry) : Bool :=
  (List.range (stop - start)).any fun offset =>
    if h : start + offset < 64 then value ⟨start + offset, h⟩ else false

/-- Common reserved checks shared by the supported walk shapes. -/
def entryReserved (config : Config) (entry : Entry) (pageBits : Nat)
    (isLeaf : Bool) : Bool :=
  let nxReserved := !config.nxe && entry.nx &&
    !(config.variant = .legacy ||
      (config.variant = .pae && entry.level = .pdpt))
  let highPhysical := anyBit config.physicalBits 52 entry.raw
  let illegalIntermediatePS := !isLeaf && entry.large
  let wrongLeafPS := isLeaf &&
    ((pageBits = 12 && entry.large) || (pageBits > 12 && !entry.large))
  let misalignedLarge := isLeaf && pageBits > 12 && anyBit 12 pageBits entry.raw
  let unsupportedOneGiB := pageBits = 30 && !config.oneGiB
  let paePDPTReserved := config.variant = .pae && entry.level = .pdpt &&
    (entry.raw ⟨1, by omega⟩ || entry.raw ⟨2, by omega⟩ ||
      entry.raw ⟨5, by omega⟩ || entry.raw ⟨6, by omega⟩ ||
      entry.raw ⟨7, by omega⟩ || entry.raw ⟨8, by omega⟩ || entry.nx)
  let legacyHigh := config.variant = .legacy && anyBit 32 64 entry.raw
  nxReserved || highPhysical || illegalIntermediatePS || wrongLeafPS ||
    misalignedLarge || unsupportedOneGiB || paePDPTReserved || legacyHigh

def addressBEq (left right : Address) : Bool :=
  (List.range 64).all fun index =>
    addressBit left index == addressBit right index

theorem addressBEq_self (address : Address) : addressBEq address address = true := by
  simp [addressBEq]

def entryByteCount (variant : Variant) : Nat :=
  if variant = .legacy then 4 else 8

def rawEntryBytes (variant : Variant) (raw : RawEntry) : List Byte :=
  (List.range (entryByteCount variant)).map fun byteIndex => fun bit =>
    addressBit raw (byteIndex * 8 + bit.val)

def byteBit (byte : Byte) (index : Nat) : Bool :=
  if h : index < 8 then byte ⟨index, h⟩ else false

def bytesBEq (left right : List Byte) : Bool :=
  left.length = right.length &&
  (left.zip right).all fun pair =>
    (List.range 8).all fun index =>
      byteBit pair.1 index == byteBit pair.2 index

def concreteEntryBytesMatch (concrete : Store) (variant : Variant)
    (entry : Entry) : Bool :=
  (rawEntryBytes variant entry.raw).zipIdx.all fun pair =>
    bytesBEq [pair.1] [concrete.read
      (addAddress entry.physical (addressOfNat pair.2))]

def entryFetched (config : Config) (concrete : Store)
    (memory : List TableCell) (entry : Entry) : Bool :=
  memory.any fun cell => cell.available &&
    addressBEq cell.physical entry.physical && addressBEq cell.raw entry.raw &&
    bytesBEq cell.bytes (rawEntryBytes config.variant entry.raw) &&
    concreteEntryBytesMatch concrete config.variant entry

def entryWritableEffective (config : Config) (entry : Entry) : Bool :=
  if config.variant = .pae ∧ entry.level = .pdpt then true else entry.writable

def entryUserEffective (config : Config) (entry : Entry) : Bool :=
  if config.variant = .pae ∧ entry.level = .pdpt then true else entry.user

def combinedWritable (config : Config) (entries : List Entry) : Bool :=
  entries.all (entryWritableEffective config)

def combinedUser (config : Config) (entries : List Entry) : Bool :=
  entries.all (entryUserEffective config)

def combinedNX (config : Config) (entries : List Entry) : Bool :=
  entries.any (nxEffective config)

def protectionKey (entry : Entry) : Fin 16 :=
  Fin.ofNat 16 ((if entry.raw ⟨59, by omega⟩ then 1 else 0) +
    (if entry.raw ⟨60, by omega⟩ then 2 else 0) +
    (if entry.raw ⟨61, by omega⟩ then 4 else 0) +
    (if entry.raw ⟨62, by omega⟩ then 8 else 0))

def derivedPage (config : Config) (linear : Address) (pageBits : Nat)
    (entries : List Entry) : Option PageMapping := do
  let leaf <- entries.getLast?
  pure {
    linearTag := fun bit => if bit.val < pageBits then false else linear bit
    physicalTag := leafBase config leaf pageBits
    offsetBits := pageBits
    present := true
    writable := combinedWritable config entries
    user := combinedUser config entries
    executable := !combinedNX config entries
    reserved := false
    shadowStack := false
    protectionKey := protectionKey leaf
    memoryType := none }

theorem derivedPage_offset (config : Config) (linear : Address) (pageBits : Nat)
    (entries : List Entry) (page : PageMapping)
    (derived : derivedPage config linear pageBits entries = some page) :
    page.offsetBits = pageBits := by
  cases last : entries.getLast? with
  | none => simp [derivedPage, last] at derived
  | some leaf =>
      simp [derivedPage, last] at derived
      cases derived
      rfl

theorem derivedPage_memory_type_unresolved (config : Config) (linear : Address)
    (pageBits : Nat) (entries : List Entry) (page : PageMapping)
    (derived : derivedPage config linear pageBits entries = some page) :
    page.memoryType = none := by
  cases last : entries.getLast? with
  | none => simp [derivedPage, last] at derived
  | some leaf =>
      simp [derivedPage, last] at derived
      cases derived
      rfl

structure ADUpdate where
  position : Nat
  physical : PhysicalAddress
  setAccessed : Bool
  setDirty : Bool

def successfulADUpdates (config : Config) (entries : List Entry)
    (allowedWrite : Bool) : List ADUpdate :=
  entries.zipIdx.filterMap fun pair =>
    if config.variant = .pae ∧ pair.1.level = .pdpt then none
    else some (ADUpdate.mk (pair.2 + 1) pair.1.physical true
      (allowedWrite && pair.2 + 1 = entries.length))

theorem read_walk_never_sets_dirty (config : Config) (entries : List Entry) :
    ∀ update ∈ successfulADUpdates config entries false, update.setDirty = false := by
  intro update member
  simp [successfulADUpdates] at member
  obtain ⟨entry, position, _, _, rfl⟩ := member
  rfl

inductive FaultKind where
  | notPresent | reserved
  deriving DecidableEq, Repr

structure WalkFault where
  kind : FaultKind
  failedLevel : Level
  failedPhysical : PhysicalAddress
  errorCode : PageFaultError
  updates : List ADUpdate

inductive Outcome where
  | success (mapping : PageMapping) (updates : List ADUpdate)
  | fault (detail : WalkFault)
  | invalidCertificate

private def walkAux (config : Config) (linear : Address) (pageBits : Nat)
    (concrete : Store) (memory : List TableCell) (write user fetch : Bool) :
    List Level -> List Entry -> PhysicalAddress -> List Entry -> List ADUpdate -> Outcome
  | [], [], _, visited, updates =>
      match derivedPage config linear pageBits visited.reverse with
      | some mapping => .success mapping updates.reverse
      | none => .invalidCertificate
  | level :: levels, entry :: entries, tableBase, visited, updates =>
      let expectedPhysical := addAddress tableBase
        (indexDisplacement linear config.variant level)
      if entry.level ≠ level || !entryFetched config concrete memory entry ||
          !addressBEq entry.physical expectedPhysical then .invalidCertificate
      else if !entry.present then
        .fault (WalkFault.mk .notPresent level entry.physical
          (PageFaultError.mk false write user false
            (config.nxe && config.variant ≠ .legacy && fetch)
            (config.nxe && config.variant ≠ .legacy) false
            (config.cet && false) config.cet)
          updates.reverse)
      else if entryReserved config entry pageBits levels.isEmpty then
        .fault (WalkFault.mk .reserved level entry.physical
          (PageFaultError.mk true write user true
            (config.nxe && config.variant ≠ .legacy && fetch)
            (config.nxe && config.variant ≠ .legacy) false
            (config.cet && false) config.cet)
          updates.reverse)
      else
        let update : ADUpdate := ADUpdate.mk (visited.length + 1)
          entry.physical true false
        let nextUpdates :=
          if config.variant = .pae ∧ entry.level = .pdpt then updates
          else update :: updates
        walkAux config linear pageBits concrete memory write user fetch levels entries
          (entryBase config entry) (entry :: visited) nextUpdates
  | _, _, _, _, _ => .invalidCertificate

def walk (config : Config) (linear : Address) (pageBits : Nat)
    (concrete : Store) (memory : List TableCell) (certificate : Certificate)
    (write user fetch : Bool) : Outcome :=
  let levels := expectedLevels config.variant pageBits
  if levels.isEmpty then .invalidCertificate
  else walkAux config linear pageBits concrete memory write user fetch levels
    certificate.entries config.root [] []

namespace Source

/-!
The definitions below are a reviewed typed transcription of the corresponding
TLA+ bit selectors. They do not constitute a verified parser for TLA+.
-/

def entryPresent (entry : Entry) : Bool := entry.raw ⟨0, by omega⟩
def entryWritable (entry : Entry) : Bool := entry.raw ⟨1, by omega⟩
def entryUser (entry : Entry) : Bool := entry.raw ⟨2, by omega⟩
def entryLarge (entry : Entry) : Bool := entry.raw ⟨7, by omega⟩
def entryNX (entry : Entry) : Bool := entry.raw ⟨63, by omega⟩

theorem entry_field_correspondence (entry : Entry) :
    Source.entryPresent entry = entry.present ∧
    Source.entryWritable entry = entry.writable ∧
    Source.entryUser entry = entry.user ∧
    Source.entryLarge entry = entry.large ∧
    Source.entryNX entry = entry.nx := by
  exact ⟨rfl, rfl, rfl, rfl, rfl⟩

end Source
end AMD64.PageWalk
