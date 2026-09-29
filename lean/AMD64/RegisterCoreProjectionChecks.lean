import Std

/-!
Finite Lean transcription of the AriadneEffects normal/fault projection for
MOV reg64, imm32. The selected RAX bank has eight disjoint byte cells. This
checks the abstract soundness rule; the source-form-to-cell correspondence is
still a separate Stage D obligation.
-/

namespace AMD64.RegisterCoreProjectionChecks

inductive Cell where
  | rax (byte : Fin 8)
  | zf
  | memory
  deriving DecidableEq, Repr

structure Effect where
  reads : List Cell
  writes : List Cell
  replaced : List Cell
  deriving DecidableEq, Repr

def raxCells : List Cell :=
  [.rax 0, .rax 1, .rax 2, .rax 3, .rax 4, .rax 5, .rax 6, .rax 7]

def normalWrite : Effect :=
  { reads := [], writes := raxCells, replaced := raxCells }

def rollbackFault : Effect :=
  { reads := [], writes := [], replaced := [] }

def subset (left right : List Cell) : Bool := left.all right.contains

def sound (outcomes : List Effect) (uses mayDefs mustDefs : List Cell) : Bool :=
  !outcomes.isEmpty && outcomes.all fun transition =>
    subset transition.reads uses &&
    subset transition.writes mayDefs &&
    subset mustDefs transition.replaced &&
    subset transition.replaced transition.writes

theorem normal_continuation_sound :
    sound [normalWrite] [] raxCells raxCells = true := by
  decide

theorem mixed_fault_sound_without_must_def :
    sound [normalWrite, rollbackFault] [] raxCells [] = true := by
  decide

theorem mixed_fault_cannot_kill_rax :
    sound [normalWrite, rollbackFault] [] raxCells raxCells = false := by
  decide

end AMD64.RegisterCoreProjectionChecks
