import AMD64.Monitor
import AMD64.IntegerExecutionChecks

namespace AMD64.Monitor.Checks

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.MemoryTypes
open AMD64.IntegerExecution.Checks

def config : SystemConfig := {
  paging := false, a20Enabled := true, cr0AM := false, cr0WP := true,
  cr4PAE := true, cr4SMEP := false, cr4SMAP := false,
  cr4PKE := false, cr4CET := false, eferNXE := true,
  pkru := fun _ => {}, deniedIOPorts := fun _ => false }

def cpu : CPUState := stateWithRax Bits.zero
def monitorRange (target : Address) : Range := { bytes := [target] }
def profile : Profile := {
  monitorx := true, interruptBreak := true,
  minimumLineBytes := 1, maximumLineBytes := 1,
  rangeFor := monitorRange }
def idle : State := { range := none, pending := false }
def armed : State := { range := some (monitorRange Bits.zero), pending := true }

example : (request cpu .bits64 .ds (.resolved .wb)).address.byteCount = 1 := rfl

def wbSpan : AMD64.MachineAccess.ResolvedSpan := {
  access := {
    effective := Bits.zero, linear := Bits.zero,
    bytes := [{ linear := Bits.zero, physical := Bits.zero, page := none }],
    request := (request cpu .bits64 .ds (.resolved .wb)).address }
  memoryType := .resolved .wb }

def ucSpan : AMD64.MachineAccess.ResolvedSpan := { wbSpan with memoryType := .resolved .uc }

example : bindResolved profile cpu idle wbSpan = .armed cpu armed wbSpan := by
  classical
  simp [bindResolved, profile, monitorRange, Range.Valid, wbSpan, idle, armed]

example : bindResolved profile cpu idle ucSpan =
    .sourceUnspecified cpu idle (monitorRange Bits.zero) := by
  classical
  simp [bindResolved, profile, monitorRange, Range.Valid, ucSpan, wbSpan, idle]

def nmi : WakeObservation := { cause := .nmi }
example : wakeAllowed profile cpu armed nmi := by
  simp [wakeAllowed, nmi]

def unsupported : Profile := { profile with monitorx := false }
example : ExecuteMWAITX unsupported cpu armed none =
    .fault .ud cpu armed := by
  classical
  simp [ExecuteMWAITX, unsupported, profile]

end AMD64.Monitor.Checks
