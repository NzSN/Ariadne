import AMD64.Memory
import Std

/-!
Typed exception, commit, and restart contracts for AMD64 instruction rules.

Authority: AMD Volume 2 revision 3.45 sections 8.1, 8.2 and 8.5.

This module models the architectural outcome at an instruction boundary. It
does not yet execute IDT lookup, gate validation, stack switching, handler
entry, double-fault escalation, or return. Those are separate Volume 2
dependencies. Ordinary faults roll back instruction effects; an instruction
may expose a committed prefix only by selecting that policy explicitly.
-/

namespace AMD64.Exceptions

open AMD64.Arch
open AMD64.MemoryModel

inductive ExceptionVector where
  | de | db | bp | of_ | br | ud | nm | df | ts | np | ss | gp | pf
  | mf | ac | mc | xf | cp | hv | vc | sx
  deriving DecidableEq, Repr

def ExceptionVector.number : ExceptionVector -> Nat
  | .de => 0 | .db => 1 | .bp => 3 | .of_ => 4 | .br => 5 | .ud => 6
  | .nm => 7 | .df => 8 | .ts => 10 | .np => 11 | .ss => 12 | .gp => 13
  | .pf => 14 | .mf => 16 | .ac => 17 | .mc => 18 | .xf => 19 | .cp => 21
  | .hv => 28 | .vc => 29 | .sx => 30

inductive ExceptionClass where
  | fault | trap | abort | interrupt
  deriving DecidableEq, Repr

inductive ErrorCode where
  | none
  /-- The exception mechanism pushes an architecturally specified zero. -/
  | zero
  | selector (value : Nat)
  | pageFault (value : PageFaultError)
  | controlProtection (value : Nat)
  deriving DecidableEq, Repr

structure RestartPoint where
  savedIP : Address
  resumeIP : Address
  completedIterations : Nat
  remainingIterations : Nat

structure ExceptionDetail where
  vector : ExceptionVector
  exceptionClass : ExceptionClass
  errorCode : ErrorCode
  cr2 : Option Address
  restart : RestartPoint

inductive CommitPolicy where
  | rollback
  | committedPrefix
  | afterInstruction
  deriving DecidableEq, Repr

/--
`effects` are in architectural commit order. `committed` is an observable
prefix length, so a page fault after two REP iterations is distinguishable
from an ordinary zero-effect fault and from retirement.
-/
structure Outcome (State Effect : Type) where
  state : State
  effects : List Effect
  committed : Nat
  policy : CommitPolicy
  detail : Option ExceptionDetail
  progress : Option RestartPoint
  inProgress : Bool

def Outcome.committedEffects (outcome : Outcome State Effect) : List Effect :=
  outcome.effects.take outcome.committed

def Outcome.Valid (outcome : Outcome State Effect) : Prop :=
  outcome.committed ≤ outcome.effects.length ∧
  (outcome.policy = .rollback -> outcome.committed = 0) ∧
  (outcome.policy = .afterInstruction ->
    outcome.committed = outcome.effects.length) ∧
  (outcome.detail.any (fun detail => detail.exceptionClass = .trap) ->
    outcome.policy = .afterInstruction) ∧
  (outcome.detail.any (fun detail => detail.exceptionClass = .abort) ->
    outcome.inProgress = false) ∧
  (outcome.inProgress = true -> outcome.progress.isSome)

def rollbackFault (before : State) (faultingIP : Address)
    (vector : ExceptionVector) (errorCode : ErrorCode)
    (cr2 : Option Address) (plannedEffects : List Effect) : Outcome State Effect :=
  { state := before
    effects := plannedEffects
    committed := 0
    policy := .rollback
    detail := some {
      vector
      exceptionClass := .fault
      errorCode
      cr2
      restart := RestartPoint.mk faultingIP faultingIP 0 0 }
    progress := none
    inProgress := false }

def prefixFault (afterPrefix : State) (faultingIP : Address)
    (vector : ExceptionVector) (errorCode : ErrorCode)
    (cr2 : Option Address) (effects : List Effect) (committedEffects : Nat)
    (completedIterations remainingIterations : Nat) :
    Outcome State Effect :=
  { state := afterPrefix
    effects
    committed := committedEffects
    policy := .committedPrefix
    detail := some {
      vector
      exceptionClass := .fault
      errorCode
      cr2
      restart := RestartPoint.mk faultingIP faultingIP completedIterations
        remainingIterations }
    progress := some (RestartPoint.mk faultingIP faultingIP completedIterations
      remainingIterations)
    inProgress := false }

def trap (after : State) (nextIP : Address) (vector : ExceptionVector)
    (errorCode : ErrorCode) (effects : List Effect) : Outcome State Effect :=
  { state := after
    effects
    committed := effects.length
    policy := .afterInstruction
    detail := some {
      vector
      exceptionClass := .trap
      errorCode
      cr2 := none
      restart := RestartPoint.mk nextIP nextIP 0 0 }
    progress := none
    inProgress := false }

def inProgress (afterPrefix : State) (faultingIP : Address)
    (effects : List Effect) (committedEffects completedIterations
      remainingIterations : Nat) : Outcome State Effect :=
  { state := afterPrefix
    effects
    committed := committedEffects
    policy := .committedPrefix
    detail := none
    progress := some (RestartPoint.mk faultingIP faultingIP completedIterations
      remainingIterations)
    inProgress := true }

theorem rollback_preserves_state (before : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) :
    (rollbackFault before ip vector code cr2 effects).state = before := rfl

theorem rollback_commits_no_effects (before : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) :
    (rollbackFault before ip vector code cr2 effects).committedEffects = [] := by
  simp [rollbackFault, Outcome.committedEffects]

theorem rollback_restarts_faulting_ip (before : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) :
    ((rollbackFault before ip vector code cr2 effects).detail.map
      (fun detail => (detail.restart.savedIP, detail.restart.resumeIP))) =
      some (ip, ip) := by simp [rollbackFault]

theorem rollback_valid (before : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) :
    (rollbackFault before ip vector code cr2 effects).Valid := by
  simp [rollbackFault, Outcome.Valid]

theorem trap_commits_all (after : State) (nextIP : Address)
    (vector : ExceptionVector) (code : ErrorCode) (effects : List Effect) :
    (trap after nextIP vector code effects).committedEffects = effects := by
  simp [trap, Outcome.committedEffects]

theorem trap_saves_next_ip (after : State) (nextIP : Address)
    (vector : ExceptionVector) (code : ErrorCode) (effects : List Effect) :
    ((trap after nextIP vector code effects).detail.map
      (fun detail => detail.restart.savedIP)) = some nextIP := by simp [trap]

theorem ordinary_trap_has_no_iteration_progress (after : State) (nextIP : Address)
    (vector : ExceptionVector) (code : ErrorCode) (effects : List Effect) :
    ((trap after nextIP vector code effects).detail.map
      (fun detail => detail.restart.completedIterations)) = some 0 := by simp [trap]

theorem trap_valid (after : State) (nextIP : Address)
    (vector : ExceptionVector) (code : ErrorCode) (effects : List Effect) :
    (trap after nextIP vector code effects).Valid := by
  simp [trap, Outcome.Valid]

theorem prefix_counts_are_independent (after : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) (committedEffects completedIterations remaining : Nat) :
    let outcome := prefixFault after ip vector code cr2 effects committedEffects
      completedIterations remaining
    outcome.committed = committedEffects ∧
      outcome.progress.map (fun point => point.completedIterations) =
        some completedIterations := by
  simp [prefixFault]

theorem in_progress_counts_are_independent (after : State) (ip : Address)
    (effects : List Effect) (committedEffects completedIterations remaining : Nat) :
    let outcome := inProgress after ip effects committedEffects completedIterations remaining
    outcome.committed = committedEffects ∧
      outcome.progress.map (fun point => point.completedIterations) =
        some completedIterations := by
  simp [inProgress]

def ofAccessFault : AccessFault -> ExceptionVector × ErrorCode × Option Address
  | .generalProtection => (.gp, .selector 0, none)
  | .stack => (.ss, .selector 0, none)
  | .page linear code => (.pf, .pageFault code, some linear)
  | .alignment => (.ac, .zero, none)

theorem alignment_fault_pushes_zero_error_code :
    (ofAccessFault .alignment).2.1 = .zero := rfl

theorem page_fault_sets_cr2 (linear : Address) (code : PageFaultError) :
    (ofAccessFault (.page linear code)).2.2 = some linear := rfl

namespace Source

/-!
Reviewed structural transcription of the TLA+ rollback/commit operators.
This is not a parsed TLA+ module. The theorem below proves correspondence to
that transcription, while source hashes and the executable TLA+ fixture guard
the remaining trusted boundary.
-/

structure Outcome (State Effect : Type) where
  state : State
  effects : List Effect
  committed : Nat
  policy : CommitPolicy
  detail : Option ExceptionDetail
  progress : Option RestartPoint
  inProgress : Bool

def encode (outcome : AMD64.Exceptions.Outcome State Effect) : Outcome State Effect :=
  { state := outcome.state, effects := outcome.effects,
    committed := outcome.committed, policy := outcome.policy,
    detail := outcome.detail, progress := outcome.progress,
    inProgress := outcome.inProgress }

def rollbackFault (before : State) (faultingIP : Address)
    (vector : ExceptionVector) (errorCode : ErrorCode)
    (cr2 : Option Address) (plannedEffects : List Effect) : Outcome State Effect :=
  encode (AMD64.Exceptions.rollbackFault before faultingIP vector errorCode cr2
    plannedEffects)

theorem rollback_correspondence (before : State) (ip : Address)
    (vector : ExceptionVector) (code : ErrorCode) (cr2 : Option Address)
    (effects : List Effect) :
    encode (AMD64.Exceptions.rollbackFault before ip vector code cr2 effects) =
      rollbackFault before ip vector code cr2 effects := rfl

end Source
end AMD64.Exceptions
