import AMD64.IOStrings
import Lean

/-! Isolated axiom audit for IO1 and its successful string bindings. -/

open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.IO.accumulatorBytes_length,
    ``AMD64.IO.direct_requests_have_valid_shape,
    ``AMD64.IO.privileged_bypasses_unavailable_bitmap,
    ``AMD64.IO.vm86_never_bypasses_bitmap,
    ``AMD64.IO.denied_port_causes_gp,
    ``AMD64.IO.device_event_is_strongly_ordered,
    ``AMD64.IO.direct_input_completed_writes_accumulator,
    ``AMD64.IO.direct_output_completed_frames_cpu,
    ``AMD64.IO.cross_boundary_has_no_device_step,
    ``AMD64.IO.gp_maps_to_gp_zero,
    ``AMD64.IO.Source.portSpan_correspondence,
    ``AMD64.IOStrings.outs_source_fault_frames_state,
    ``AMD64.IOStrings.ins_effect_order_on_success]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required IO theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    if (`AMD64.IO).isPrefixOf name || (`AMD64.IOStrings).isPrefixOf name then
      declarations := declarations + 1
      if info matches .thmInfo _ then theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 IO axiom audit passed: {declarations} declarations, {theorems} theorems"
