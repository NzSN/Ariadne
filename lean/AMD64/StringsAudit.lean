import AMD64.Strings
import Lean

/-! Isolated axiom audit for the C4 string/repetition foundation. -/

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.Strings.address32_long64_zeroes_high,
    ``AMD64.Strings.address16_preserves_observable_mid,
    ``AMD64.Strings.comparison_zf_matches_control,
    ``AMD64.Strings.apply_control_rcx,
    ``AMD64.Strings.movs_stage_order,
    ``AMD64.Strings.ins_stage_order,
    ``AMD64.Strings.outs_stage_order,
    ``AMD64.Strings.access_fault_keeps_effect_and_iteration_counts_independent,
    ``AMD64.Strings.Source.shouldContinue_correspondence,
    ``AMD64.Strings.Source.firstStage_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required string theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.Strings).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 strings axiom audit passed: {declarations} declarations, {theorems} theorems"
