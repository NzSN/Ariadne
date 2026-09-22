import AMD64.SystemState

namespace AMD64.SystemState.Checks

open AMD64.Arch

def profile : FeatureProfile := {
  x87 := true, mmx := true, sse := true, avx := true, avx512 := true,
  xsave := true, fsgsbase := true, rdpru := true, lwp := true }

def supported : XFeatureProfile := {
  supported := fun bit => bit.val ∈ [0, 1, 2, 5, 6, 7, 9, 62] }

def validXCR0 : XCR0 := { enabled := fun bit => bit.val ∈ [0, 1, 2, 5, 6, 7, 62] }

def zeroMSR : MSRState := {
  hwcrCpuidUserDisable := false
  tscAux := fun _ => false
  mperf := fun _ => false
  aperf := fun _ => false
  lwpCfg := fun _ => false
  lwpCbAddress := fun _ => false
}

def baseState : State := {
  cr0 := { pe := true, mp := true, em := false, ts := false, wp := true, am := true }
  cr4 := { vme := false, tsd := false, osfxsr := true, osxmmexcpt := true,
           fsgsbase := true, osxsave := true }
  xcr0 := validXCR0
  msr := zeroMSR
  inSMM := false
  x87ExceptionPending := false
}

example : validXCR0.validB supported = true := by decide
example : mediaGuard profile baseState .legacySSE = .allowed := by decide
example : mediaGuard profile { baseState with cr0 := { baseState.cr0 with ts := true } }
    .legacySSE = .nm := by decide
example : mediaGuard profile { baseState with cr4 := { baseState.cr4 with osfxsr := false } }
    .legacySSE = .ud := by decide
example : mediaGuard profile { baseState with cr0 := { baseState.cr0 with em := true } }
    .wait = .allowed := by decide
example : mediaGuard profile { baseState with cr0 := { baseState.cr0 with ts := true } }
    .wait = .nm := by decide
example : lwpGuard profile supported baseState .long64 = .allowed := by decide
example : lwpGuard profile supported { baseState with cr4 :=
    { baseState.cr4 with osxsave := false } } .long64 = .ud := by decide
example : fsgsbaseGuard profile baseState .protectedMode = .ud := by decide
example : rdpruGuard profile { baseState with cr4 :=
    { baseState.cr4 with tsd := true } } ⟨3, by decide⟩ = .ud := by decide

end AMD64.SystemState.Checks
