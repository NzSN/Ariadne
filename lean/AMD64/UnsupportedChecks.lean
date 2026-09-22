import AMD64.Unsupported

namespace AMD64.Unsupported.Checks

def rax : Location := ⟨.register, "rax"⟩
def zf : Location := ⟨.flag, "zf"⟩
def memory : Location := ⟨.memory, "[rdi]"⟩
def rip : Location := ⟨.control, "rip"⟩

def before : Knowledge := {
  concreteFacts := [⟨rax, "1"⟩, ⟨zf, "true"⟩, ⟨memory, "42"⟩, ⟨rip, "4096"⟩]
  undefinedLocations := []
  observationGaps := []
}

def dependent : List Location := [rax, zf, memory, rip]
def untrusted : EffectSummary := {
  mayAffect := []
  trusted := false
  dependencyClosed := false }
def fallback := UnsupportedFallback before dependent untrusted
def emptyCallerFallback := UnsupportedFallback before [] untrusted
def unknown := UnknownInstructionFallback before

example : fallback.knowledge.concreteFacts = [] := by decide
example : fallback.retired = false := rfl
example : fallback.faultVector = none := rfl
example : fallback.successfulTransition = false := rfl
example : fallback.successors = [] ∧ fallback.successorsComplete = false := by decide
example : emptyCallerFallback.knowledge.concreteFacts = [] := by decide
example : unknown.knowledge.concreteFacts = [] := rfl
example : unknown.knowledge.undefinedLocations = [] := rfl
example : unknown.dependentLocations = [rip, memory, zf, rax] := by decide
example : unknown.retired = false := rfl
example : unknown.faultVector = none := rfl
example : unknown.successfulTransition = false := rfl
example : unknown.successors = [] ∧ unknown.successorsComplete = false := by decide

def selective : EffectSummary := {
  mayAffect := [rax, zf]
  trusted := true
  dependencyClosed := true }
def selectiveFallback := UnsupportedFallback before dependent selective
-- The trusted summary omits RIP and the caller supplies no extras. Control is
-- still derived from `before` and invalidated.
def selectiveOmittedControl := UnsupportedFallback before [] selective
example : selectiveFallback.knowledge.concreteFacts = [⟨memory, "42"⟩] := by decide
example : ⟨rip, "4096"⟩ ∉ selectiveFallback.knowledge.concreteFacts := by decide
example : selectiveOmittedControl.knowledge.concreteFacts = [⟨memory, "42"⟩] := by decide
example : ⟨rip, "4096"⟩ ∉ selectiveOmittedControl.knowledge.concreteFacts := by decide

def contradictory : Knowledge := {
  concreteFacts := [⟨rax, "1"⟩, ⟨rax, "2"⟩]
  undefinedLocations := []
  observationGaps := [] }
example : ¬contradictory.Valid := by
  intro valid
  rcases valid with ⟨unique, _, _, _⟩
  simp [contradictory] at unique

def capture := MissingCaptureFallback before [memory]
  (.missingMemoryBytes memory)
example : capture.kind = .evidenceGap := rfl
example : capture.knowledge.concreteFacts =
    [⟨rax, "1"⟩, ⟨zf, "true"⟩, ⟨rip, "4096"⟩] := by decide

def undefined := ArchitecturalUndefinedProjection before [zf] [4100] true
example : undefined.kind = .supportedArchitecturalUndefined := rfl
example : zf ∈ undefined.knowledge.undefinedLocations := by decide
example : ⟨zf, "true"⟩ ∉ undefined.knowledge.concreteFacts := by decide
example : undefined.successfulTransition = true := rfl

end AMD64.Unsupported.Checks
