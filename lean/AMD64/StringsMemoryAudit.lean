import AMD64.StringsMemory
import Lean

/-! Isolated axiom audit for the C4 memory-string binding. -/

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.StringsMemory.wordToBytes_length,
    ``AMD64.StringsMemory.bytesToWord_singleton_low,
    ``AMD64.StringsMemory.read_after_write_byte,
    ``AMD64.StringsMemory.fault_preserves_cpu_memory,
    ``AMD64.StringsMemory.unavailable_preserves_cpu_memory,
    ``AMD64.StringsMemory.ready_can_finish,
    ``AMD64.StringsMemory.non_accumulator_frames_rax,
    ``AMD64.StringsMemory.Source.bytesToWord_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required string-memory theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.StringsMemory).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 string-memory axiom audit passed: {declarations} declarations, {theorems} theorems"
