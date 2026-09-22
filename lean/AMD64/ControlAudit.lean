import Lean
import AMD64.Control

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.Control.retireTo_rip, ``AMD64.Control.retireTo_gpr,
    ``AMD64.Control.long64_stack_address_size,
    ``AMD64.Control.decrementCount_frames_rip,
    ``AMD64.Control.decrementCount_frames_flags,
    ``AMD64.Control.addressBytes_length,
    ``AMD64.Control.commitStackPointer_frames_rip,
    ``AMD64.Control.commitStackPointer_frames_flags,
    ``AMD64.Control.flagImage_clears_resume,
    ``AMD64.Control.flagsAfterPop_clears_resume,
    ``AMD64.Control.flagsAfterPop_valid,
    ``AMD64.Control.undefined_opcode_faults,
    ``AMD64.Control.near_call_cet_requires_binding,
    ``AMD64.Control.near_ret_cet_requires_binding,
    ``AMD64.Control.Source.condition_correspondence,
    ``AMD64.Control.Source.truncate_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required control theorem is missing: {name}"
  let mut declarations := 0
  let mut theorems := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.Control).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 control axiom audit passed: {declarations} declarations, {theorems} theorems"
