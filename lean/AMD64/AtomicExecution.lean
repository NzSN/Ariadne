import AMD64.Atomic
import AMD64.MachineAccess
import Std

/-!
Typed execution and correspondence boundary for authoritative
`Specs/AMD64AtomicExecution.tla`.

`execute` is exactly the existing permission-checked Lean implementation.
MachineAccess projection reconstructs the tentative byte plan from the exact
resolved span and event. No operation here advances RIP or retires an
instruction.
-/

namespace AMD64.AtomicExecution

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory
open AMD64.Atomic
open AMD64.MachineAccess

noncomputable section

abbrev Instruction := AMD64.Atomic.MemoryInstruction
abbrev ExecutionOutcome := AMD64.Atomic.ExecutionOutcome

inductive Error where
  | atomic (cause : AMD64.Atomic.ExecutionError)
  | memoryTypeUnresolved

def execute (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (instruction : Instruction) (before : MachineState) :
    Except Error ExecutionOutcome :=
  match instruction.memoryType with
  | .resolved _ =>
      (AMD64.Atomic.executeMemory profile config pages instruction before).mapError .atomic
  | _ => .error .memoryTypeUnresolved

theorem execute_resolved_delegates (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (instruction : Instruction) (before : MachineState) :
    execute profile config pages { instruction with memoryType := .resolved .wb } before =
      (AMD64.Atomic.executeMemory profile config pages
        { instruction with memoryType := .resolved .wb } before).mapError .atomic := rfl

theorem execute_unresolved_is_unavailable (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (instruction : Instruction)
    (before : MachineState) :
    execute profile config pages
      { instruction with memoryType := .unknownConfiguration } before =
        .error .memoryTypeUnresolved := rfl

def effectPlan (before : MachineState) (outcome : ExecutionOutcome) :
    Option EffectPlan := do
  let span : ResolvedSpan := {
    access := outcome.resolved
    memoryType := outcome.event.memoryType
  }
  let writes <- MachineAccess.planWrites before.memory span outcome.event.after
  pure { writes, commitPolicy := .bodyAll, committed := writes.length }

def projectBody (before : MachineState) (outcome : ExecutionOutcome) :
    Option BodyResult := do
  let plan <- effectPlan before outcome
  pure {
    disposition := .bodyApplied
    state := outcome.state
    plan
    faults := []
  }

def BodyProjection (before : MachineState) (outcome : ExecutionOutcome)
    (result : BodyResult) : Prop :=
  projectBody before outcome = some result ∧
  MachineAccess.BodyApplied before outcome.state.cpu result.plan result

inductive Group7Vector where
  | gp | pf | ac
  deriving DecidableEq, Repr

structure Group7Candidate where
  id : Nat
  vector : Group7Vector
  byteIndex : Nat
  deriving DecidableEq, Repr

structure Group7Profile where
  known : Bool
  gpRank : Nat
  pfRank : Nat
  acRank : Nat

def Group7Profile.Valid (profile : Group7Profile) : Prop :=
  profile.known = false ∨
    (profile.gpRank < 3 ∧ profile.pfRank < 3 ∧ profile.acRank < 3 ∧
     profile.gpRank ≠ profile.pfRank ∧ profile.gpRank ≠ profile.acRank ∧
     profile.pfRank ≠ profile.acRank)

def rank (profile : Group7Profile) : Group7Vector -> Nat
  | .gp => profile.gpRank
  | .pf => profile.pfRank
  | .ac => profile.acRank

/-- Unknown profile keeps all same-group alternatives. A known implementation
profile supplies stable ranks and does not become a universal AMD rule. -/
def FaultSelected (profile : Group7Profile) (candidates : List Group7Candidate)
    (selected : Group7Candidate) : Prop :=
  selected ∈ candidates ∧ profile.Valid ∧
  (profile.known = false ∨ ∀ candidate ∈ candidates,
    rank profile selected.vector ≤ rank profile candidate.vector)

theorem unknown_profile_preserves_candidate (profile : Group7Profile)
    (candidates : List Group7Candidate) (selected : Group7Candidate)
    (unknown : profile.known = false) (member : selected ∈ candidates) :
    FaultSelected profile candidates selected := by
  exact ⟨member, Or.inl unknown, Or.inl unknown⟩

end
end AMD64.AtomicExecution
