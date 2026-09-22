import Lean
import AMD64.IntegerShiftExecutionChecks

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.IntegerShiftExecution).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  unless declarations > 0 do
    throwError "AMD64.IntegerShiftExecution declarations are missing"
  logInfo m!"AMD64 shift execution axiom audit passed: {declarations} declarations, {theorems} theorems"
