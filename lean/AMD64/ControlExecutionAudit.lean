import Lean
import AMD64.ControlExecution

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.Control.Execution.enterLevel_lt,
    ``AMD64.Control.Execution.pushaProgram_length,
    ``AMD64.Control.Execution.popaProgram_length,
    ``AMD64.Control.Execution.enter_rejects_raw_level_over_byte,
    ``AMD64.Control.Execution.Source.enter_level_correspondence,
    ``AMD64.Control.Execution.Source.enter_indices_correspondence,
    ``AMD64.Control.Execution.Source.enter_copy_program_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required control-execution theorem is missing: {name}"
  let mut declarations := 0
  let mut theorems := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.Control.Execution).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 control execution axiom audit passed: {declarations} declarations, {theorems} theorems"
