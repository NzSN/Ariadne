import AMD64.UnsupportedChecks
import Lean

/- Audit public declarations and every declaration originating in the focused
   Unsupported modules. The module-origin and private-name checks ensure that
   private regression helpers cannot hide forbidden axioms. -/
open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.Unsupported.fallback_adds_no_concrete_facts,
    ``AMD64.Unsupported.fallback_loses_dependent_facts,
    ``AMD64.Unsupported.untrusted_fallback_loses_all_mutable_facts,
    ``AMD64.Unsupported.fallback_preserves_validity,
    ``AMD64.Unsupported.fallback_has_no_architectural_outcome,
    ``AMD64.Unsupported.fallback_control_is_unresolved,
    ``AMD64.Unsupported.unknown_fallback_discards_all_concrete_facts,
    ``AMD64.Unsupported.unknown_fallback_discards_all_undefined_locations,
    ``AMD64.Unsupported.unknown_fallback_tracks_all_observed_locations,
    ``AMD64.Unsupported.unknown_fallback_adds_no_concrete_facts,
    ``AMD64.Unsupported.unknown_fallback_preserves_validity,
    ``AMD64.Unsupported.unknown_fallback_has_no_architectural_outcome,
    ``AMD64.Unsupported.unknown_fallback_control_is_unresolved,
    ``AMD64.Unsupported.undefined_is_not_unsupported]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required Unsupported theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    let projectModule := match environment.getModuleIdxFor? name with
      | some index =>
          let moduleName := environment.header.moduleNames[index]!
          moduleName == `AMD64.Unsupported || moduleName == `AMD64.UnsupportedChecks
      | none => false
    let privateProjectName := name.toString.startsWith "_private.AMD64." ||
      (name.toString.startsWith "_private." && name.toString.contains ".AMD64.")
    if (`AMD64.Unsupported).isPrefixOf name || projectModule || privateProjectName then
      declarations := declarations + 1
      if info matches .thmInfo _ then
        theorems := theorems + 1
      for dependency in (← collectAxioms name) do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 Unsupported axiom audit passed: {declarations} declarations, {theorems} theorems; allowlist: {allowed}"
