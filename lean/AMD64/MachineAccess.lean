import AMD64.ConcreteMemory
import AMD64.MemoryTypes
import Std

/-!
Canonical CPU plus concrete-memory access boundary.

Address resolution delegates to `MemoryModel.resolveAccess`; no opaque
translation result is accepted. Captured `MemoryState` is intentionally absent
from `MachineState`. An analysis adapter may separately prove that a captured
snapshot supports the resolved physical span.
-/

namespace AMD64.MachineAccess

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory

noncomputable section
open scoped Classical

abbrev MachineState := ConcreteMachineState

structure SpanRequest where
  address : AddressRequest
  memoryType : AMD64.MemoryTypes.Resolution

structure ResolvedSpan where
  access : ResolvedAccess
  memoryType : AMD64.MemoryTypes.Resolution

structure IndexedFault where
  index : Nat
  error : ResolutionError

inductive Resolution where
  | resolved (span : ResolvedSpan)
  | faultCandidates (faults : List IndexedFault)

private local instance addressDecidableEq : DecidableEq Address :=
  Classical.typeDecidableEq _

def requestedLinearSpan (cpu : CPUState) (request : AddressRequest) : List Address :=
  let effective := effectiveOffset request.rawEffective request.addressSize
  let segment := segmentRegister cpu request.segment
  let segmentBase := effectiveSegmentBase cpu.execution.mode request.segment segment
  (List.range request.byteCount).map fun offset =>
    let byteEffective := effectiveOffset
      (addAddress effective (addressOfNat offset)) request.addressSize
    linearAddress cpu.execution.mode segmentBase byteEffective

def faultIndex (cpu : CPUState) (request : AddressRequest) : ResolutionError -> Nat
  | .fault (.page linear _) =>
      (requestedLinearSpan cpu request).findIdx (· = linear)
  | _ => 0

/-- Existing address, segmentation, paging, protection and ordinary-alignment
resolution remains the sole constructor of a successful span. -/
def resolveSpan (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (cpu : CPUState) (request : SpanRequest) : Resolution :=
  match resolveAccess profile config cpu pages request.address with
  | .ok access => .resolved { access, memoryType := request.memoryType }
  | .error error => .faultCandidates [{ index := faultIndex cpu request.address error, error }]

theorem resolveSpan_delegates_success (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (cpu : CPUState)
    (request : SpanRequest) (access : ResolvedAccess)
    (resolved : resolveAccess profile config cpu pages request.address = .ok access) :
    resolveSpan profile config pages cpu request =
      .resolved { access, memoryType := request.memoryType } := by
  simp [resolveSpan, resolved]

theorem resolveSpan_delegates_fault (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (cpu : CPUState)
    (request : SpanRequest) (error : ResolutionError)
    (failed : resolveAccess profile config cpu pages request.address = .error error) :
    resolveSpan profile config pages cpu request =
      .faultCandidates [{ index := faultIndex cpu request.address error, error }] := by
  simp [resolveSpan, failed]

def physicalBytes (span : ResolvedSpan) : List PhysicalAddress :=
  span.access.bytes.map (·.physical)

def linearBytes (span : ResolvedSpan) : List Address :=
  span.access.bytes.map (·.linear)

/-- Concrete architectural read in the exact resolved byte order. -/
def read (memory : Store) (span : ResolvedSpan) : List Byte :=
  span.access.bytes.map fun byte => memory.read byte.physical

structure ByteEffect where
  index : Nat
  physical : PhysicalAddress
  before : Byte
  after : Byte

inductive CommitPolicy where
  | rollback
  | committedPrefix
  | bodyAll
  | instructionSpecific
  deriving DecidableEq, Repr

structure EffectPlan where
  writes : List ByteEffect
  commitPolicy : CommitPolicy
  committed : Nat

def EffectPlan.Valid (plan : EffectPlan) : Prop :=
  plan.committed ≤ plan.writes.length ∧
  (plan.commitPolicy = .rollback -> plan.committed = 0) ∧
  (plan.commitPolicy = .bodyAll -> plan.committed = plan.writes.length) ∧
  (plan.writes.Pairwise fun left right => left.index ≠ right.index) ∧
  (plan.writes.Pairwise fun left right => left.physical ≠ right.physical)

/-- Construct tentative byte effects without choosing how many commit. -/
def planWrites (memory : Store) (span : ResolvedSpan)
    (bytes : List Byte) : Option (List ByteEffect) :=
  if span.access.bytes.length ≠ bytes.length then none
  else some ((span.access.bytes.zip bytes).zipIdx.map fun pair =>
    { index := pair.2
      physical := pair.1.1.physical
      before := memory.read pair.1.1.physical
      after := pair.1.2 })

def applyEffects (memory : Store) (effects : List ByteEffect) : Store :=
  effects.foldl (fun current effect =>
    current.write effect.physical effect.after) memory

/-- Apply only the instruction-selected committed prefix. This operator does
not decide rollback, partial progress, or retirement. -/
def applyCommittedPrefix (memory : Store) (plan : EffectPlan) : Store :=
  applyEffects memory (plan.writes.take plan.committed)

theorem rollback_preserves_memory (memory : Store) (writes : List ByteEffect) :
    applyCommittedPrefix memory { writes, commitPolicy := .rollback, committed := 0 } =
      memory := by
  rfl

theorem body_all_applies_every_effect (memory : Store) (writes : List ByteEffect) :
    applyCommittedPrefix memory
      { writes, commitPolicy := .bodyAll, committed := writes.length } =
      applyEffects memory writes := by
  simp [applyCommittedPrefix]

inductive BodyDisposition where
  | bodyApplied
  | faultCandidates
  | modelingUnavailable
  deriving DecidableEq, Repr

structure BodyResult where
  disposition : BodyDisposition
  state : MachineState
  plan : EffectPlan
  faults : List IndexedFault

/-- Body application frames the canonical composition but performs no fetch,
RIP advance, asynchronous-event selection, or retirement. -/
def BodyApplied (before : MachineState) (afterCPU : CPUState)
    (plan : EffectPlan) (result : BodyResult) : Prop :=
  plan.Valid ∧ result.disposition = .bodyApplied ∧ result.faults = [] ∧
  result.plan = plan ∧ result.state.cpu = afterCPU ∧
  result.state.memory = applyCommittedPrefix before.memory plan

end
end AMD64.MachineAccess
