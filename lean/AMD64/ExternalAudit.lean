import AMD64.External
import Lean

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.External.decimal_long_mode_ud,
    ``AMD64.External.rdseed_failure_is_zero,
    ``AMD64.External.nop_frames_cpu]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required external theorem is missing: {name}"
  for (name, _) in environment.constants.toList do
    if (`AMD64.External).isPrefixOf name then
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo "AMD64 external axiom audit passed"
