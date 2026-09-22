import AMD64.AtomicExecution
import AMD64.IntegerExecutionChecks

namespace AMD64.AtomicExecution.Checks

open AMD64.Arch
open AMD64.Atomic
open AMD64.AtomicExecution
open AMD64.IntegerExecution
open AMD64.IntegerExecution.Checks
open AMD64.Operands
open AMD64.ConcreteMemory
open AMD64.MemoryTypes
open AMD64.IntegerSemantics

def highByteCPU : CPUState :=
  stateWithRax (fun bit => bit.val = 8)

theorem high8_exchange_write_targets_bits_8_through_15 :
    (writeGPR highByteCPU ⟨GPR.rax.toFin, .high8⟩ zero).rax ⟨8, by omega⟩ = false ∧
    (writeGPR highByteCPU ⟨GPR.rax.toFin, .high8⟩ zero).rax ⟨0, by omega⟩ =
      highByteCPU.rax ⟨0, by omega⟩ := by
  constructor <;> rfl

theorem low32_failure_write_zero_extends (before value : AMD64.Word) (bit : Fin 64)
    (upper : 32 ≤ bit.val) :
    writeViewForMode .long64 before value .low32 bit = false := by
  exact AMD64.dword_zero_extends before value bit upper

def pairCPU : CPUState := {
  stateWithRax (wordOfNat 1) with
  gpr := fun register =>
    if register = GPR.rax.toFin then wordOfNat 1
    else if register = GPR.rdx.toFin then wordOfNat 2
    else zero
}

theorem block_expected_pair_is_low_then_high :
    (pairRegisterBytes pairCPU .rax .rdx 64).length = 16 := by
  decide

theorem block_failure_updates_expected_pair_and_zf_only
    (observed : List MemoryModel.Byte) :
    (withZF (writeExpectedPair pairCPU 64 observed) false).rflags.zf = false ∧
    (withZF (writeExpectedPair pairCPU 64 observed) false).rflags.cf = pairCPU.rflags.cf := by
  constructor <;> rfl

def zeroStore : Store := {
  physicalBits := 52
  bytes := { byteAt := fun _ _ => false }
}

theorem cmpxchg_without_lock_remains_non_atomic
    (physical : MemoryModel.PhysicalAddress) :
    (compareExchange zeroStore physical (wordOfNat 1) (wordOfNat 2) 8 false
      (.unknownConfiguration)).event.atomic = false :=
  cmpxchg_without_lock_is_not_atomic zeroStore physical (wordOfNat 1)
    (wordOfNat 2) 8 .unknownConfiguration

def gpCandidate : Group7Candidate := ⟨1, .gp, 1⟩
def pfCandidate : Group7Candidate := ⟨2, .pf, 2⟩
def acCandidate : Group7Candidate := ⟨3, .ac, 1⟩
def candidates := [gpCandidate, pfCandidate, acCandidate]
def unknownProfile : Group7Profile := ⟨false, 0, 1, 2⟩
def gpFirst : Group7Profile := ⟨true, 0, 1, 2⟩
def pfFirst : Group7Profile := ⟨true, 1, 0, 2⟩

theorem unknown_group7_preserves_gp_pf_ac :
    FaultSelected unknownProfile candidates gpCandidate ∧
    FaultSelected unknownProfile candidates pfCandidate ∧
    FaultSelected unknownProfile candidates acCandidate := by
  simp [FaultSelected, Group7Profile.Valid, unknownProfile, candidates,
    gpCandidate, pfCandidate, acCandidate]

theorem known_group7_profile_is_stable :
    FaultSelected gpFirst candidates gpCandidate ∧
    ¬ FaultSelected gpFirst candidates pfCandidate ∧
    FaultSelected pfFirst candidates pfCandidate ∧
    ¬ FaultSelected pfFirst candidates gpCandidate := by
  simp [FaultSelected, Group7Profile.Valid, rank, gpFirst, pfFirst,
    candidates, gpCandidate, pfCandidate, acCandidate]

end AMD64.AtomicExecution.Checks
