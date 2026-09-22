import Lean
import AMD64.IntegerStateAdapter

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.IntegerSemantics.truncate_inside,
    ``AMD64.IntegerSemantics.truncate_outside,
    ``AMD64.IntegerSemantics.zeroExtend_source,
    ``AMD64.IntegerSemantics.bitModify_selected,
    ``AMD64.IntegerSemantics.unsignedDivide_by_zero,
    ``AMD64.IntegerSemantics.adcx_preserves_overflow,
    ``AMD64.IntegerSemantics.adox_preserves_carry,
    ``AMD64.IntegerSemantics.adx_value,
    ``AMD64.IntegerSemantics.project_apply_status,
    ``AMD64.IntegerSemantics.apply_project_status,
    ``AMD64.IntegerSemantics.apply_status_preserves_df,
    ``AMD64.IntegerSemantics.set_direction_preserves_validity,
    ``AMD64.IntegerSemantics.Source.truncate_correspondence,
    ``AMD64.IntegerSemantics.Source.addWord_correspondence,
    ``AMD64.IntegerSemantics.Source.zeroExtend_correspondence,
    ``AMD64.IntegerSemantics.Source.signExtend_correspondence,
    ``AMD64.IntegerSemantics.Source.notWord_correspondence,
    ``AMD64.IntegerSemantics.Source.logicWord_correspondence,
    ``AMD64.IntegerSemantics.Source.bitModify_correspondence,
    ``AMD64.IntegerSemantics.Source.maskedCount_correspondence,
    ``AMD64.IntegerSemantics.Source.shiftValue_correspondence,
    ``AMD64.IntegerSemantics.Source.rotateValue_correspondence,
    ``AMD64.IntegerSemantics.Source.adxResult_correspondence,
    ``AMD64.IntegerSemantics.Source.bitScanEffects_correspondence,
    ``AMD64.IntegerSemantics.Source.bitTestEffects_correspondence,
    ``AMD64.IntegerSemantics.Source.bextrEffects_correspondence,
    ``AMD64.IntegerSemantics.Source.bzhiEffects_correspondence,
    ``AMD64.IntegerSemantics.Source.countEffects_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required integer theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.IntegerSemantics).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 integer axiom audit passed: {declarations} declarations, {theorems} theorems"
