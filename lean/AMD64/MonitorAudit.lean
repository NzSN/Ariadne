import AMD64.Monitor
import Lean

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.Monitor.monitor_request_is_one_byte,
    ``AMD64.Monitor.wait_frames_cpu_on_wake]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required Monitor theorem is missing: {name}"
  for (name, _) in environment.constants.toList do
    if (`AMD64.Monitor).isPrefixOf name then
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo "AMD64 Monitor axiom audit passed"
