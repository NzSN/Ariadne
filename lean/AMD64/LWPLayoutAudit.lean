import AMD64.LWPLayout
import Lean

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [``AMD64.LWPLayout.captured_bytes_match_concrete]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required LWP layout theorem is missing: {name}"
  for (name, _) in environment.constants.toList do
    if (`AMD64.LWPLayout).isPrefixOf name then
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo "AMD64 LWP layout axiom audit passed"
