import Lean
import AMD64.IntegerMulDivExecutionChecks

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let mut declarations : Nat := 0
  for (name, _) in environment.constants.toList do
    if (`AMD64.IntegerMulDivExecution).isPrefixOf name then
      declarations := declarations + 1
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  unless declarations > 0 do throwError "mul/div execution declarations missing"
  logInfo m!"AMD64 mul/div Lean audit passed: {declarations} declarations"
