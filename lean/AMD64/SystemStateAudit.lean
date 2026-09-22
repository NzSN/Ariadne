import AMD64.SystemState
import Lean

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.SystemState.wait_ignores_em,
    ``AMD64.SystemState.wait_nm_iff_mp_ts,
    ``AMD64.SystemState.legacy_sse_osfxsr_zero_ud]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required SystemState theorem is missing: {name}"
  for (name, _) in environment.constants.toList do
    if (`AMD64.SystemState).isPrefixOf name then
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo "AMD64 SystemState axiom audit passed"
