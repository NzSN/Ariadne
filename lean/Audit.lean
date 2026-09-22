import Lean
import AMD64

/- Check project namespace declarations AND declarations originating in AMD64
   modules, including private helpers/examples and declarations outside the
   intended namespace. An unused project axiom also fails. This permits only
   Lean's ordinary logical foundation, not sorryAx/native proof shortcuts. -/
open Lean in
run_cmd do
  let environment ← getEnv
  let allowed : List Name := [``propext, ``Quot.sound, ``Classical.choice]
  let required : List Name := [
    ``AMD64.GPRView.bounds, ``AMD64.read_after_write,
    ``AMD64.preserves_outside, ``AMD64.dword_zero_extends,
    ``AMD64.qword_replaces, ``AMD64.Source.decode_encode,
    ``AMD64.Source.encode_decode, ``AMD64.Source.read_correspondence,
    ``AMD64.Source.write_correspondence]
  for name in required do
    unless (environment.find? name).any (fun info => info matches .thmInfo _) do
      throwError "Required foundation theorem is missing: {name}"
  let mut declarations : Nat := 0
  let mut theorems : Nat := 0
  for (name, info) in environment.constants.toList do
    let projectModule := match environment.getModuleIdxFor? name with
      | some index => (`AMD64).isPrefixOf environment.header.moduleNames[index]!
      | none => false
    let privateProjectName := name.toString.startsWith "_private.AMD64." ||
      (name.toString.startsWith "_private." && name.toString.contains ".AMD64.")
    if (`AMD64).isPrefixOf name || projectModule || privateProjectName then
      declarations := declarations + 1
      if info matches .thmInfo _ then
        theorems := theorems + 1
      let dependencies ← collectAxioms name
      for dependency in dependencies do
        unless dependency ∈ allowed do
          throwError "{name} depends on forbidden axiom {dependency}"
  logInfo m!"AMD64 axiom audit passed: {declarations} declarations, {theorems} theorems; allowlist: {allowed}"
