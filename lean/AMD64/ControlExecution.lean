import AMD64.Control
import AMD64.MachineAccess
import AMD64.SystemState

/-!
Paired control-stack execution layer.

The pure order and CPU projection definitions transcribe
`Specs/AMD64ControlExecution.tla`. The concrete ENTER executor uses the existing
verified address resolver while the shared `AMD64.MachineAccess` interface is
being integrated. Fault outcomes retain entry and tentative machines without
asserting that tentative memory writes commit architecturally.

Authority: AMD APM Volume 3 revision 3.38 pages 224-225, 262, 327-329,
332-334, and 339-343; Volume 2 revision 3.45 pages 306-308.
-/

namespace AMD64.Control.Execution

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.ConcreteMemory
open AMD64.MachineAccess

noncomputable section
open scoped Classical

inductive StackMicroKind where
  | pushRegister | popRegister | discardPop
  | pushOldRBP | readFrame | pushFrame | pushFramePointer
  | finalAccessCheck
  deriving DecidableEq, Repr

structure StackMicroOp where
  kind : StackMicroKind
  index : Nat
  register : String
  deriving DecidableEq, Repr

def enterLevel (rawLevel : Nat) : Nat := rawLevel % 32

def enterCopyIndices (rawLevel : Nat) : List Nat :=
  (List.range (enterLevel rawLevel - 1)).map (· + 1)

def enterCopyProgram (rawLevel : Nat) : List StackMicroOp :=
  (enterCopyIndices rawLevel).flatMap fun index =>
    [{ kind := .readFrame, index, register := "" },
     { kind := .pushFrame, index, register := "" }]

def enterProgram (rawLevel : Nat) : List StackMicroOp :=
  [{ kind := .pushOldRBP, index := 0, register := "rbp" }] ++
  enterCopyProgram rawLevel ++
  (if enterLevel rawLevel > 0 then
    [{ kind := .pushFramePointer, index := enterLevel rawLevel, register := "rsp" }]
   else []) ++
  [{ kind := .finalAccessCheck, index := 0, register := "" }]

def pushaProgram : List StackMicroOp :=
  ["rax", "rcx", "rdx", "rbx", "original-rsp", "rbp", "rsi", "rdi"].mapIdx
    fun index register => { kind := .pushRegister, index := index + 1, register }

def popaProgram : List StackMicroOp :=
  ["rdi", "rsi", "rbp", "discard-rsp", "rbx", "rdx", "rcx", "rax"].mapIdx
    fun index register => {
      kind := if register = "discard-rsp" then .discardPop else .popRegister
      index := index + 1, register }

theorem enterLevel_lt (rawLevel : Nat) : enterLevel rawLevel < 32 := by
  exact Nat.mod_lt rawLevel (by decide)

@[simp] theorem pushaProgram_length : pushaProgram.length = 8 := by decide
@[simp] theorem popaProgram_length : popaProgram.length = 8 := by decide

def unavailablePlan : EffectPlan := {
  writes := [], commitPolicy := .instructionSpecific, committed := 0 }

noncomputable def executePushBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (value : AMD64.Control.Address)
    (operandWidth : Nat) (memoryType : AMD64.MemoryTypes.Resolution) : BodyResult :=
  match planStackPush before.cpu value operandWidth with
  | none => BodyResult.mk .modelingUnavailable before unavailablePlan []
  | some plan =>
      let request : SpanRequest := { address := plan.request, memoryType }
      match resolveSpan profile config pages before.cpu request with
      | .faultCandidates faults =>
          BodyResult.mk .faultCandidates before unavailablePlan faults
      | .resolved span =>
          match planWrites before.memory span
              (addressBytes plan.value plan.request.byteCount) with
          | none => BodyResult.mk .modelingUnavailable before unavailablePlan []
          | some writes =>
              let effectPlan : EffectPlan := {
                writes, commitPolicy := .bodyAll, committed := writes.length }
              let afterCPU := commitStackPointer before.cpu plan.newRSP
              BodyResult.mk .bodyApplied
                { cpu := afterCPU, memory := applyCommittedPrefix before.memory effectPlan }
                effectPlan []

noncomputable def executePopBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) : BodyResult × Option AMD64.Control.Address :=
  match planNearRetPop before.cpu operandWidth with
  | none => (BodyResult.mk .modelingUnavailable before unavailablePlan [], none)
  | some plan =>
      let request : SpanRequest := { address := plan.request, memoryType }
      match resolveSpan profile config pages before.cpu request with
      | .faultCandidates faults =>
          (BodyResult.mk .faultCandidates before unavailablePlan faults, none)
      | .resolved span =>
          let bytes := AMD64.MachineAccess.read before.memory span
          let value := truncateIP (addressOfBytes bytes) operandWidth
          let effectPlan : EffectPlan := {
            writes := [], commitPolicy := .bodyAll, committed := 0 }
          let afterCPU := commitStackPointer before.cpu plan.poppedRSP
          (BodyResult.mk .bodyApplied { before with cpu := afterCPU }
            effectPlan [], some value)

noncomputable def executePopGPRBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (destination : AMD64.Operands.GPRRef)
    (operandWidth : Nat) (memoryType : AMD64.MemoryTypes.Resolution) : BodyResult :=
  if destination.width ≠ operandWidth then
    BodyResult.mk .modelingUnavailable before unavailablePlan []
  else
    let (body, value) := executePopBody profile config pages before operandWidth memoryType
    match body.disposition, value with
    | .bodyApplied, some popped =>
        { body with state := { body.state with cpu :=
            (AMD64.IntegerExecution.writeGPR body.state.cpu destination popped) } }
    | _, _ => body

inductive VirtualFlagGuard where
  | allowed | generalProtection
  deriving DecidableEq, Repr

def virtualFlagGuard (cpu : CPUState) (operandWidth : Nat) (cr4VME : Bool) :
    VirtualFlagGuard :=
  if virtualLowIOPL cpu then
    if operandWidth = 16 ∧ cr4VME then .allowed else .generalProtection
  else .allowed

def pushedFlagsWord (cpu : CPUState) (operandWidth : Nat) (cr4VME : Bool) :
    AMD64.Control.Address :=
  let ordinary := flagImage cpu
  if virtualLowIOPL cpu ∧ operandWidth = 16 ∧ cr4VME then fun bit =>
    if bit.val = 9 then cpu.rflags.virtualInterrupt
    else if bit.val = 12 ∨ bit.val = 13 then true
    else ordinary bit
  else ordinary

def virtualPopFlagsFault (cpu : CPUState) (popped : AMD64.Control.Address)
    (operandWidth : Nat) (cr4VME : Bool) : Bool :=
  virtualLowIOPL cpu && operandWidth = 16 && cr4VME &&
    (popped ⟨8, by omega⟩ ||
      (popped ⟨9, by omega⟩ && cpu.rflags.virtualInterruptPending))

def applyPoppedFlagsWithVME (cpu : CPUState) (popped : AMD64.Control.Address)
    (operandWidth : Nat) (cr4VME : Bool) : CPUState :=
  if virtualLowIOPL cpu ∧ operandWidth = 16 ∧ cr4VME then
    let ordinary := flagsAfterPop cpu popped operandWidth
    { cpu with rflags := { ordinary with
        interruptEnable := cpu.rflags.interruptEnable
        iopl := cpu.rflags.iopl
        virtualInterrupt := popped ⟨9, by omega⟩ } }
  else { cpu with rflags := flagsAfterPop cpu popped operandWidth }

inductive FlagBodyOutcome where
  | body (result : BodyResult)
  | generalProtection (entry : MachineState) (tentative : Option MachineState)

noncomputable def executePushFlagsBody (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (before : MachineState)
    (operandWidth : Nat) (cr4VME : Bool)
    (memoryType : AMD64.MemoryTypes.Resolution) : FlagBodyOutcome :=
  match virtualFlagGuard before.cpu operandWidth cr4VME with
  | .generalProtection => .generalProtection before none
  | .allowed => .body (executePushBody profile config pages before
      (pushedFlagsWord before.cpu operandWidth cr4VME) operandWidth memoryType)

noncomputable def executePopFlagsBody (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (before : MachineState)
    (operandWidth : Nat) (cr4VME : Bool)
    (memoryType : AMD64.MemoryTypes.Resolution) : FlagBodyOutcome :=
  match virtualFlagGuard before.cpu operandWidth cr4VME with
  | .generalProtection => .generalProtection before none
  | .allowed =>
      let (body, value) := executePopBody profile config pages before operandWidth memoryType
      match body.disposition, value with
      | .bodyApplied, some popped =>
          if virtualPopFlagsFault before.cpu popped operandWidth cr4VME then
            .generalProtection before (some body.state)
          else .body { body with state := { body.state with cpu :=
            (applyPoppedFlagsWithVME body.state.cpu popped operandWidth cr4VME) } }
      | _, _ => .body body

inductive OrderedStackPhase where
  | pusha | popa
  deriving DecidableEq, Repr

inductive OrderedBodyOutcome where
  | bodyApplied (state : MachineState) (steps : List BodyResult)
  | tentativeFault (entry tentative : MachineState) (failure : BodyResult)
      (phase : OrderedStackPhase) (index : Nat) (completed : List BodyResult)
  | modelingUnavailable (entry tentative : MachineState)
      (phase : OrderedStackPhase) (index : Nat) (completed : List BodyResult)

noncomputable def executePushBodies (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : MachineState)
    (values : List AMD64.Control.Address) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) (index : Nat := 1)
    (completed : List BodyResult := []) : OrderedBodyOutcome :=
  match values with
  | [] => .bodyApplied current completed
  | value :: rest =>
      let body := executePushBody profile config pages current value operandWidth memoryType
      match body.disposition with
      | .bodyApplied => executePushBodies profile config pages entry body.state rest
          operandWidth memoryType (index + 1) (completed ++ [body])
      | .faultCandidates => .tentativeFault entry current body .pusha index completed
      | .modelingUnavailable => .modelingUnavailable entry current .pusha index completed
termination_by values.length

noncomputable def executePushaBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) : OrderedBodyOutcome :=
  if before.cpu.execution.mode = .long64 then
    .modelingUnavailable before before .pusha 0 []
  else match legacyGPRRef .rax operandWidth, legacyGPRRef .rcx operandWidth,
      legacyGPRRef .rdx operandWidth, legacyGPRRef .rbx operandWidth,
      legacyGPRRef .rsp operandWidth, legacyGPRRef .rbp operandWidth,
      legacyGPRRef .rsi operandWidth, legacyGPRRef .rdi operandWidth with
  | some ax, some cx, some dx, some bx, some sp, some bp, some si, some di =>
      let values := [ax, cx, dx, bx, sp, bp, si, di].map
        (AMD64.IntegerExecution.readGPR before.cpu)
      executePushBodies profile config pages before before values operandWidth memoryType
  | _, _, _, _, _, _, _, _ => .modelingUnavailable before before .pusha 0 []

noncomputable def executePopBodies (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : MachineState)
    (destinations : List (Option AMD64.Operands.GPRRef)) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) (index : Nat := 1)
    (completed : List BodyResult := []) : OrderedBodyOutcome :=
  match destinations with
  | [] => .bodyApplied current completed
  | destination :: rest =>
      let (pop, value) := executePopBody profile config pages current operandWidth memoryType
      match pop.disposition, value with
      | .bodyApplied, some popped =>
          let body := match destination with
            | none => pop
            | some register => { pop with state := { pop.state with cpu :=
                (AMD64.IntegerExecution.writeGPR pop.state.cpu register popped) } }
          executePopBodies profile config pages entry body.state rest operandWidth
            memoryType (index + 1) (completed ++ [body])
      | .faultCandidates, _ => .tentativeFault entry current pop .popa index completed
      | _, _ => .modelingUnavailable entry current .popa index completed
termination_by destinations.length

noncomputable def executePopaBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) : OrderedBodyOutcome :=
  if before.cpu.execution.mode = .long64 then
    .modelingUnavailable before before .popa 0 []
  else match legacyGPRRef .rdi operandWidth, legacyGPRRef .rsi operandWidth,
      legacyGPRRef .rbp operandWidth, legacyGPRRef .rbx operandWidth,
      legacyGPRRef .rdx operandWidth, legacyGPRRef .rcx operandWidth,
      legacyGPRRef .rax operandWidth with
  | some di, some si, some bp, some bx, some dx, some cx, some ax =>
      executePopBodies profile config pages before before
        [some di, some si, some bp, none, some bx, some dx, some cx, some ax]
        operandWidth memoryType
  | _, _, _, _, _, _, _ => .modelingUnavailable before before .popa 0 []

inductive LeaveBodyOutcome where
  | bodyApplied (result : BodyResult)
  | tentativeFault (entry tentative : MachineState) (failure : BodyResult)
  | modelingUnavailable (entry : MachineState)

noncomputable def executeLeaveBody (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : MachineState) (operandWidth : Nat)
    (memoryType : AMD64.MemoryTypes.Resolution) : LeaveBodyOutcome :=
  match basePointerRef operandWidth with
  | none => .modelingUnavailable before
  | some bp =>
      if before.cpu.execution.mode = .long64 ∧ operandWidth = 32 then
        .modelingUnavailable before
      else
        let frameAddress := effectiveOffset (before.cpu.gprValue .rbp)
          (stackAddressSize before.cpu)
        let staged : MachineState :=
          { before with cpu := commitStackPointer before.cpu frameAddress }
        let body := executePopGPRBody profile config pages staged bp operandWidth memoryType
        match body.disposition with
        | .bodyApplied => .bodyApplied body
        | .faultCandidates => .tentativeFault before staged body
        | .modelingUnavailable => .modelingUnavailable before

inductive EnterFaultPhase where
  | initialPush | copyRead | copyPush | framePointerPush | finalAccessCheck
  deriving DecidableEq, Repr

structure TentativeEnterEffect where
  entry : ConcreteMachineState
  tentative : ConcreteMachineState

inductive PairedEnterOutcome where
  | bodyApplied (state : ConcreteMachineState)
  | tentativeFault (effect : TentativeEnterEffect) (error : ResolutionError)
      (phase : EnterFaultPhase) (index : Nat)
  | invalidPayload

def enterFrameReadAddress (state : CPUState) (oldRBP : AMD64.Control.Address)
    (operandWidth index : Nat) : AMD64.Control.Address :=
  let byteCount := operandWidth / 8
  effectiveOffset
    (subtractAddress oldRBP (addressOfNat (index * byteCount)))
    (stackAddressSize state)

def enterFrameReadRequest (state : CPUState) (oldRBP : AMD64.Control.Address)
    (operandWidth index : Nat) : AddressRequest := {
  rawEffective := enterFrameReadAddress state oldRBP operandWidth index
  addressSize := stackAddressSize state
  segment := .ss
  access := { kind := .read }
  byteCount := operandWidth / 8
}

noncomputable def executeEnterCopies (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : ConcreteMachineState)
    (oldRBP : AMD64.Control.Address) (operandWidth : Nat)
    (indices : List Nat) : PairedEnterOutcome :=
  match indices with
  | [] => .bodyApplied current
  | index :: rest =>
      let request := enterFrameReadRequest current.cpu oldRBP operandWidth index
      match resolveAccess profile config current.cpu pages request with
      | .error error => .tentativeFault { entry, tentative := current }
          error .copyRead index
      | .ok resolved =>
          let value := addressOfBytes (readResolved current.memory resolved)
          match executeStackPush profile config pages current value operandWidth with
          | .pushed next => executeEnterCopies profile config pages entry next
              oldRBP operandWidth rest
          | .stackFault error => .tentativeFault { entry, tentative := current }
              error .copyPush index
          | .invalidPayload => .invalidPayload
termination_by indices.length

noncomputable def finishEnter (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : ConcreteMachineState)
    (framePointer : AMD64.Control.Address) (bp : AMD64.Operands.GPRRef)
    (operandWidth allocationBytes : Nat) : PairedEnterOutcome :=
  let finalRSP := effectiveOffset
    (subtractAddress (current.cpu.gprValue .rsp) (addressOfNat allocationBytes))
    (stackAddressSize current.cpu)
  let request : AddressRequest := {
    rawEffective := finalRSP
    addressSize := stackAddressSize current.cpu
    segment := .ss
    access := { kind := .write }
    byteCount := operandWidth / 8
  }
  match resolveAccess profile config current.cpu pages request with
  | .error error => .tentativeFault { entry, tentative := current }
      error .finalAccessCheck 0
  | .ok _ =>
      let withStack := commitStackPointer current.cpu finalRSP
      let withFrame := AMD64.IntegerExecution.writeGPR withStack bp framePointer
      .bodyApplied { current with cpu := withFrame }

noncomputable def executeEnterFull (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry : ConcreteMachineState)
    (operandWidth allocationBytes rawLevel : Nat) : PairedEnterOutcome :=
  if rawLevel > 255 ∨ allocationBytes > 65535 ∨
      !stackOperandWidthPermitted entry.cpu operandWidth then .invalidPayload
  else match basePointerRef operandWidth with
  | none => .invalidPayload
  | some bp =>
      let oldRBP := AMD64.IntegerExecution.readGPR entry.cpu bp
      match executeStackPush profile config pages entry oldRBP operandWidth with
      | .stackFault error => .tentativeFault { entry, tentative := entry }
          error .initialPush 0
      | .invalidPayload => .invalidPayload
      | .pushed afterOldRBP =>
          let framePointer := afterOldRBP.cpu.gprValue .rsp
          match executeEnterCopies profile config pages entry afterOldRBP oldRBP
              operandWidth (enterCopyIndices rawLevel) with
          | .tentativeFault effect error phase index =>
              .tentativeFault effect error phase index
          | .invalidPayload => .invalidPayload
          | .bodyApplied afterCopies =>
              if enterLevel rawLevel = 0 then
                finishEnter profile config pages entry afterCopies framePointer bp
                  operandWidth allocationBytes
              else match executeStackPush profile config pages afterCopies
                  framePointer operandWidth with
              | .stackFault error => .tentativeFault
                  { entry, tentative := afterCopies } error .framePointerPush
                  (enterLevel rawLevel)
              | .invalidPayload => .invalidPayload
              | .pushed afterFramePointer =>
                  finishEnter profile config pages entry afterFramePointer
                    framePointer bp operandWidth allocationBytes

theorem enter_rejects_raw_level_over_byte (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap) (entry : ConcreteMachineState)
    (operandWidth allocationBytes rawLevel : Nat) (tooWide : 255 < rawLevel) :
    executeEnterFull profile config pages entry operandWidth allocationBytes rawLevel =
      .invalidPayload := by
  simp [executeEnterFull, tooWide]

namespace Source

def enterLevel (rawLevel : Nat) : Nat := rawLevel % 32

def enterCopyIndices (rawLevel : Nat) : List Nat :=
  (List.range (enterLevel rawLevel - 1)).map (· + 1)

def enterCopyProgram (rawLevel : Nat) : List StackMicroOp :=
  (enterCopyIndices rawLevel).flatMap fun index =>
    [{ kind := .readFrame, index, register := "" },
     { kind := .pushFrame, index, register := "" }]

theorem enter_level_correspondence (rawLevel : Nat) :
    AMD64.Control.Execution.enterLevel rawLevel = enterLevel rawLevel := rfl

theorem enter_indices_correspondence (rawLevel : Nat) :
    AMD64.Control.Execution.enterCopyIndices rawLevel = enterCopyIndices rawLevel := rfl

theorem enter_copy_program_correspondence (rawLevel : Nat) :
    AMD64.Control.Execution.enterCopyProgram rawLevel = enterCopyProgram rawLevel := rfl

end Source

end
end AMD64.Control.Execution
