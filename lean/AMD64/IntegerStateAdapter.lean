import AMD64.ArchitecturalState
import AMD64.IntegerSemantics

/-! Adapter between the pure integer status flags and complete architectural
rFLAGS. This is a state primitive, not an instruction step. -/

namespace AMD64.IntegerSemantics

open AMD64.Arch

def projectStatusFlags (flags : RFlags) : ArithmeticFlags :=
  { cf := flags.cf, pf := flags.pf, af := flags.af
    zf := flags.zf, sf := flags.sf, of := flags.of }

def applyStatusFlags (before : RFlags) (status : ArithmeticFlags) : RFlags :=
  { before with cf := status.cf, pf := status.pf, af := status.af
                zf := status.zf, sf := status.sf, of := status.of }

def setDirectionFlag (before : RFlags) (value : Bool) : RFlags :=
  { before with df := value }

theorem project_apply_status (before : RFlags) (status : ArithmeticFlags) :
    projectStatusFlags (applyStatusFlags before status) = status := by
  rfl

theorem apply_project_status (before : RFlags) :
    applyStatusFlags before (projectStatusFlags before) = before := by
  cases before <;> rfl

theorem apply_status_preserves_df (before : RFlags) (status : ArithmeticFlags) :
    (applyStatusFlags before status).df = before.df := by
  rfl

theorem set_direction_preserves_validity (before : RFlags) (value : Bool)
    (valid : before.Valid) : (setDirectionFlag before value).Valid := by
  exact valid

end AMD64.IntegerSemantics
