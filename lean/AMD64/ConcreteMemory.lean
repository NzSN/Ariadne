import AMD64.Memory
import Std

/-!
Concrete architectural memory and captured-analysis refinement.

`AMD64.MemoryModel.ConcreteMemory` is a total function from every modeled
64-bit physical-address carrier to an architectural byte. `MemoryState` stays
a finite captured projection whose absent addresses are unavailable knowledge.
No theorem interprets an unavailable captured byte as zero, a page fault, or
an impossible architectural state.
-/

namespace AMD64.ConcreteMemory

open AMD64.Arch
open AMD64.MemoryModel

noncomputable section
open scoped Classical

local instance addressDecidableEq : DecidableEq Address :=
  Classical.typeDecidableEq _

structure Store where
  physicalBits : Nat
  bytes : MemoryModel.ConcreteMemory

def Store.Valid (store : Store) : Prop :=
  1 ≤ store.physicalBits ∧ store.physicalBits ≤ 64

def physicalAddressValid (store : Store) (physical : PhysicalAddress) : Prop :=
  store.Valid ∧ ∀ bit : Fin 64, store.physicalBits ≤ bit.val -> physical bit = false

def Store.read (store : Store) (physical : PhysicalAddress) : Byte :=
  store.bytes.byteAt physical

def Store.write (store : Store) (physical : PhysicalAddress) (value : Byte) : Store :=
  { store with bytes := { byteAt := fun queried =>
      if queried = physical then value else store.read queried } }

@[simp] theorem read_write_same (store : Store) (physical : PhysicalAddress)
    (value : Byte) : (store.write physical value).read physical = value := by
  simp [Store.write, Store.read]

theorem read_write_other (store : Store) (written queried : PhysicalAddress)
    (value : Byte) (different : queried ≠ written) :
    (store.write written value).read queried = store.read queried := by
  simp [Store.write, Store.read, different]

theorem write_frame (store : Store) (written : PhysicalAddress) (value : Byte) :
    ∀ queried, queried = written ∨
      (store.write written value).read queried = store.read queried := by
  intro queried
  by_cases same : queried = written
  · exact Or.inl same
  · exact Or.inr (read_write_other store written queried value same)

theorem write_preserves_valid_at_address (store : Store) (physical : PhysicalAddress)
    (value : Byte) (validAddress : physicalAddressValid store physical) :
    (store.write physical value).Valid := validAddress.1

/-- Captured bytes constrain concrete bytes only on the captured domain. -/
def RefinesCaptured (concrete : Store) (captured : MemoryState) : Prop :=
  concrete.Valid ∧ captured.Valid ∧
  ∀ physical ∈ captured.captured,
    physicalAddressValid concrete physical ∧
    captured.readByte physical = .available (concrete.read physical)

theorem write_uncaptured_preserves_refinement (concrete : Store)
    (captured : MemoryState) (physical : PhysicalAddress) (value : Byte)
    (refines : RefinesCaptured concrete captured)
    (validAddress : physicalAddressValid concrete physical)
    (missing : physical ∉ captured.captured) :
    RefinesCaptured (concrete.write physical value) captured := by
  refine ⟨validAddress.1, refines.2.1, ?_⟩
  intro queried member
  have different : queried ≠ physical := by
    intro equal
    subst queried
    exact missing member
  constructor
  · exact ⟨validAddress.1, refines.2.2 queried member |>.1.2⟩
  · rw [read_write_other concrete physical queried value different]
    exact (refines.2.2 queried member).2

@[simp] theorem captured_read_after_write_same (captured : MemoryState)
    (physical : PhysicalAddress) (value : Byte) :
    (captured.writeByte physical value).readByte physical = .available value := by
  simp [MemoryState.writeByte, MemoryState.readByte]

private theorem find_filter_other (cells : List ByteCell)
    (written queried : PhysicalAddress) (different : queried ≠ written) :
    cells.find? (fun cell => !decide (cell.physical = written) &&
        decide (cell.physical = queried)) =
      cells.find? (fun cell => decide (cell.physical = queried)) := by
  congr 1
  funext cell
  by_cases atQueried : cell.physical = queried
  · subst queried
    simp [different]
  · simp [atQueried]

theorem captured_read_after_write_other (captured : MemoryState)
    (written queried : PhysicalAddress) (value : Byte) (different : queried ≠ written) :
    (captured.writeByte written value).readByte queried = captured.readByte queried := by
  simp only [MemoryState.writeByte, MemoryState.readByte]
  have headDifferent : written ≠ queried := Ne.symm different
  simp only [List.find?_cons]
  simp [headDifferent]
  rw [find_filter_other captured.cells written queried different]

/--
Writing a concrete byte and recording the same captured byte preserves every
previously captured equality. `afterValid` is stated separately because the
list-backed snapshot representation owns its uniqueness proof.
-/
theorem snapshot_write_refines (concrete : Store) (captured : MemoryState)
    (physical : PhysicalAddress) (value : Byte)
    (before : RefinesCaptured concrete captured)
    (validAddress : physicalAddressValid concrete physical)
    (afterValid : (captured.writeByte physical value).Valid) :
    RefinesCaptured (concrete.write physical value)
      (captured.writeByte physical value) := by
  constructor
  · exact validAddress.1
  constructor
  · exact afterValid
  · intro queried member
    by_cases same : queried = physical
    · subst queried
      constructor
      · exact validAddress
      · simp [captured_read_after_write_same, read_write_same]
    · rw [captured_read_after_write_other captured physical queried value same]
      rw [read_write_other concrete physical queried value same]
      constructor
      · exact (before.2.2 queried (by
          have domain : (captured.writeByte physical value).captured =
              if physical ∈ captured.captured then captured.captured
              else physical :: captured.captured := rfl
          rw [domain] at member
          split at member
          · exact member
          · simp only [List.mem_cons] at member
            exact member.resolve_left same)).1
      apply (before.2.2 queried ?_).2
      have domain : (captured.writeByte physical value).captured =
          if physical ∈ captured.captured then captured.captured
          else physical :: captured.captured := rfl
      rw [domain] at member
      split at member
      · exact member
      · simp only [List.mem_cons] at member
        exact member.resolve_left same

structure ConcreteMachineState where
  cpu : CPUState
  memory : Store

def ConcreteMachineState.Valid (profile : ArchitectureProfile)
    (state : ConcreteMachineState) : Prop :=
  ValidCPUState profile state.cpu ∧ state.memory.Valid ∧
  state.memory.physicalBits = profile.physicalAddressBits

theorem concrete_machine_projects_cpu (profile : ArchitectureProfile)
    (state : ConcreteMachineState) (valid : state.Valid profile) :
    ValidCPUState profile state.cpu := valid.1

end
end AMD64.ConcreteMemory
