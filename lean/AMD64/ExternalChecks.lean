import AMD64.External

namespace AMD64.External.Checks

open AMD64.IntegerSemantics
open AMD64.Arch

example : adjustedAAA 0x00FA true = 0x0200 := by decide
example : adjustedAAS 0x0000 true = 0xFE0A := by decide

example : unsignedValue (movMaskPD (fun bit => bit.val = 63 ∨ bit.val = 127)) 2 = 3 := by
  decide

example : unsignedValue (movMaskPS (fun bit => bit.val ∈ [31, 95])) 4 = 5 := by
  decide

example : crc32cBytes [] 0x12345678 = 0x12345678 := rfl

example (profile : ProcessorProfile) (cpu : CPUState)
    (destination : Fin 16) (source : Fin 32) (unsupported : profile.sse = false) :
    ExecuteMOVMSKPS profile destination source cpu (.fault .ud) := by
  simp [ExecuteMOVMSKPS, unsupported]

example (profile : ProcessorProfile) (cpu : CPUState)
    (destination : Fin 16) (source : Fin 32) (noOS : profile.osfxsr = false) :
    ExecuteMOVMSKPD profile destination source cpu (.fault .ud) := by
  simp [ExecuteMOVMSKPD, noOS]

example (profile : ProcessorProfile) (cpu : CPUState) (which : BaseRegister)
    (destination : Fin 16) (available : FSGSAvailable profile cpu = true) :
    ExecuteReadBase profile which destination 8 cpu
      (.modelingUnavailable "invalid base-read width") := by
  simp [ExecuteReadBase, available]

example (architecture : ArchitectureProfile) (profile : ProcessorProfile)
    (cpu : CPUState) (which : BaseRegister) (source : IWord)
    (available : FSGSAvailable profile cpu = true) :
    ExecuteWriteBase architecture profile which source 8 cpu
      (.modelingUnavailable "invalid base-write width") := by
  simp [ExecuteWriteBase, available]

end AMD64.External.Checks
