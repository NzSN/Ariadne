import Lean
import AMD64.IntegerExecution

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.IntegerExecution.writeGPR_other,
    ``AMD64.IntegerExecution.writeGPR_frames_rip,
    ``AMD64.IntegerExecution.writeStatus_frames_gpr,
    ``AMD64.IntegerExecution.writeStatus_frames_df,
    ``AMD64.IntegerExecution.mov_frames_flags,
    ``AMD64.IntegerExecution.not_frames_flags,
    ``AMD64.IntegerExecution.fallthrough_sets_rip,
    ``AMD64.IntegerExecution.fallthrough_frames_gpr,
    ``AMD64.IntegerExecution.fallthrough_frames_rflags]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required integer execution theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.IntegerExecution).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 integer execution axiom audit passed: {declarations} declarations, {theorems} theorems"
