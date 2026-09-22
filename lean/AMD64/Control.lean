import AMD64.IntegerExecution
import AMD64.Memory
import AMD64.ConcreteMemory

namespace AMD64.Control

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics

noncomputable section
open scoped Classical

abbrev Address := Bits 64

structure FallthroughEvidence where
  instructionLength : Nat
  nextRIP : Address

def truncateIP (address : Address) (width : Nat) : Address := fun bit =>
  if bit.val < width then address bit else false

def FallthroughEvidence.Valid (before : CPUState) (ipWidth : Nat)
    (evidence : FallthroughEvidence) : Prop :=
  1 ≤ evidence.instructionLength ∧ evidence.instructionLength ≤ 15 ∧
  ipWidth ∈ [16, 32, 64] ∧
  evidence.nextRIP = truncateIP
    (addAddress before.rip (addressOfNat evidence.instructionLength)) ipWidth

def relativeTarget (fallthrough : Address) (displacement : AMD64.Operands.ImmediateRef)
    (operandWidth : Nat) : Address :=
  truncateIP (addAddress fallthrough displacement.value) operandWidth

def RelativeReady (displacement : AMD64.Operands.ImmediateRef) (operandWidth : Nat) : Prop :=
  displacement.Valid ∧ displacement.extension = AMD64.Operands.ImmediateExtension.sign ∧
  displacement.semanticWidth = operandWidth ∧
  displacement.encodedWidth ∈ [8, 16, 32] ∧ operandWidth ∈ [16, 32, 64]

def conditionFromStatus (condition : Condition) (flags : ArithmeticFlags) : Bool :=
  AMD64.IntegerSemantics.conditionHolds condition flags

def conditionHolds (condition : Condition) (state : CPUState) : Bool :=
  conditionFromStatus condition (AMD64.IntegerSemantics.projectStatusFlags state.rflags)

def countView : AddressSize -> AMD64.GPRView
  | .bits16 => .low16 | .bits32 => .low32 | .bits64 => .full64

def countIsZero (state : CPUState) (addressSize : AddressSize) : Bool :=
  AMD64.IntegerSemantics.isZero
    (AMD64.readView (state.gprValue .rcx) (countView addressSize)) addressSize.width

structure BranchPlan where
  taken : Bool
  fallthrough : Address
  target : Address
  nextRIP : Address

def planJcc (condition : Condition) (state : CPUState)
    (fallthrough : Address) (displacement : AMD64.Operands.ImmediateRef)
    (operandWidth : Nat) : BranchPlan :=
  let target := relativeTarget fallthrough displacement operandWidth
  let taken := conditionHolds condition state
  { taken, fallthrough, target, nextRIP := if taken then target else fallthrough }

noncomputable def checkedJccPlan (condition : Condition) (state : CPUState)
    (fallthrough : FallthroughEvidence) (displacement : AMD64.Operands.ImmediateRef)
    (operandWidth : Nat) : Option BranchPlan :=
  if fallthrough.Valid state operandWidth ∧ RelativeReady displacement operandWidth then
    some (planJcc condition state fallthrough.nextRIP displacement operandWidth)
  else none

def planJrCXZ (state : CPUState) (fallthrough : Address)
    (displacement : AMD64.Operands.ImmediateRef) (operandWidth : Nat)
    (addressSize : AddressSize) : BranchPlan :=
  let target := relativeTarget fallthrough displacement operandWidth
  let taken := countIsZero state addressSize
  { taken, fallthrough, target, nextRIP := if taken then target else fallthrough }

inductive LoopCondition where
  | loop | equal | notEqual
  deriving DecidableEq, Repr

def countRegister (addressSize : AddressSize) : AMD64.Operands.GPRRef :=
  { index := GPR.rcx.toFin, view := countView addressSize }

def decrementCount (state : CPUState) (addressSize : AddressSize) : CPUState :=
  let register := countRegister addressSize
  let before := AMD64.IntegerExecution.readGPR state register
  let after := AMD64.IntegerSemantics.subWord before AMD64.IntegerSemantics.one false
    addressSize.width
  AMD64.IntegerExecution.writeGPR state register after

def loopTaken (condition : LoopCondition) (state : CPUState)
    (addressSize : AddressSize) : Bool :=
  let nonzero := !countIsZero state addressSize
  nonzero && match condition with
    | .loop => true | .equal => state.rflags.zf | .notEqual => !state.rflags.zf

def planLoop (condition : LoopCondition) (before : CPUState) (fallthrough : Address)
    (displacement : AMD64.Operands.ImmediateRef) (operandWidth : Nat)
    (addressSize : AddressSize) : CPUState × BranchPlan :=
  let afterCount := decrementCount before addressSize
  let target := relativeTarget fallthrough displacement operandWidth
  let taken := loopTaken condition afterCount addressSize
  let plan := BranchPlan.mk taken fallthrough target
    (if taken then target else fallthrough)
  (afterCount, plan)

@[simp] theorem decrementCount_frames_rip (state : CPUState) (addressSize : AddressSize) :
    (decrementCount state addressSize).rip = state.rip := rfl

@[simp] theorem decrementCount_frames_flags (state : CPUState) (addressSize : AddressSize) :
    (decrementCount state addressSize).rflags = state.rflags := rfl

inductive NearTarget where
  | relative (displacement : AMD64.Operands.ImmediateRef)
  | register (register : AMD64.Operands.GPRRef)
  | memory (address : AMD64.Operands.AddressExpr) (width : Nat)

inductive NearTargetResult where
  | resolved (target : Address)
  | memoryResolutionRequired
  | invalidPayload

def resolveNearTarget (state : CPUState) (fallthrough : Address)
    (operandWidth : Nat) : NearTarget -> NearTargetResult
  | .relative displacement =>
      if RelativeReady displacement operandWidth then
        .resolved (relativeTarget fallthrough displacement operandWidth)
      else .invalidPayload
  | .register register =>
      if register.width = operandWidth then
        .resolved (truncateIP (AMD64.IntegerExecution.readGPR state register) operandWidth)
      else .invalidPayload
  | .memory _ _ => .memoryResolutionRequired

def targetWithinCurrentCode (profile : ArchitectureProfile) (state : CPUState)
    (target : Address) : Prop :=
  if state.execution.mode = .long64 then canonical target profile.linearAddressBits
  else unsignedLE target (fun bit =>
    if h : bit.val < 32 then state.segments.cs.cache.limit ⟨bit.val, h⟩ else false)

def retireTo (state : CPUState) (target : Address) : CPUState := { state with rip := target }

@[simp] theorem retireTo_rip (state : CPUState) (target : Address) :
    (retireTo state target).rip = target := rfl

@[simp] theorem retireTo_gpr (state : CPUState) (target : Address) :
    (retireTo state target).gpr = state.gpr := rfl

inductive RetireOutcome where
  | retired (state : CPUState)
  | generalProtection
  | modelingUnavailable

def retireBranch (profile : ArchitectureProfile) (bodyState : CPUState)
    (plan : BranchPlan) : RetireOutcome :=
  if targetWithinCurrentCode profile bodyState plan.nextRIP then
    .retired (retireTo bodyState plan.nextRIP)
  else .generalProtection

def composeBody (profile : ArchitectureProfile) (before : CPUState)
    (body : AMD64.IntegerExecution.Outcome) (plan : BranchPlan) : RetireOutcome :=
  match body with
  | .bodyApplied state =>
      if state.rip = before.rip then retireBranch profile state plan else .modelingUnavailable
  | _ => .modelingUnavailable

def negateAddress (address : Address) : Address :=
  addAddress (fun bit => !address bit) (addressOfNat 1)

def subtractAddress (left right : Address) : Address := addAddress left (negateAddress right)

def stackAddressSize (state : CPUState) : AddressSize :=
  if state.execution.mode = .long64 then .bits64
  else if state.segments.ss.cache.defaultBig then .bits32 else .bits16

def stackOperandWidthPermitted (state : CPUState) (operandWidth : Nat) : Bool :=
  operandWidth ∈ [16, 32, 64] &&
    !(state.execution.mode = .long64 && operandWidth = 32) &&
    !((state.execution.mode ≠ .long64) && operandWidth = 64)

theorem long64_stack_address_size (state : CPUState)
    (mode : state.execution.mode = .long64) : stackAddressSize state = .bits64 := by
  simp [stackAddressSize, mode]

structure StackPushPlan where
  width : Nat
  oldRSP : Address
  newRSP : Address
  value : Address
  request : AddressRequest

def planNearCallPush (state : CPUState) (fallthrough : Address)
    (operandWidth : Nat) : Option StackPushPlan :=
  if stackOperandWidthPermitted state operandWidth then
    let byteCount := operandWidth / 8
    let addressSize := stackAddressSize state
    let oldRSP := state.gprValue .rsp
    let newRSP := effectiveOffset (subtractAddress oldRSP (addressOfNat byteCount)) addressSize
    let writeAccess : AccessKindInfo := { kind := .write }
    let request : AddressRequest := {
      rawEffective := newRSP, addressSize := addressSize, segment := .ss,
      access := writeAccess, byteCount := byteCount
    }
    some (StackPushPlan.mk operandWidth oldRSP newRSP
      (truncateIP fallthrough operandWidth) request)
  else none

def byteOfAddress (value : Address) (index : Nat) : Byte := fun bit =>
  if h : index * 8 + bit.val < 64 then value ⟨index * 8 + bit.val, h⟩ else false

def addressBytes (value : Address) (byteCount : Nat) : List Byte :=
  (List.range byteCount).map (byteOfAddress value)

@[simp] theorem addressBytes_length (value : Address) (byteCount : Nat) :
    (addressBytes value byteCount).length = byteCount := by
  simp [addressBytes]

def writeResolved (store : AMD64.ConcreteMemory.Store) (access : ResolvedAccess)
    (bytes : List Byte) : Option AMD64.ConcreteMemory.Store :=
  if access.bytes.length ≠ bytes.length then none
  else some ((access.bytes.zip bytes).foldl
    (fun current pair => current.write pair.1.physical pair.2) store)

def stackPointerRef (state : CPUState) : AMD64.Operands.GPRRef :=
  { index := GPR.rsp.toFin, view := match stackAddressSize state with
      | .bits16 => .low16 | .bits32 => .low32 | .bits64 => .full64 }

def commitStackPointer (state : CPUState) (value : Address) : CPUState :=
  AMD64.IntegerExecution.writeGPR state (stackPointerRef state) value

@[simp] theorem commitStackPointer_frames_rip (state : CPUState) (value : Address) :
    (commitStackPointer state value).rip = state.rip := rfl

@[simp] theorem commitStackPointer_frames_flags (state : CPUState) (value : Address) :
    (commitStackPointer state value).rflags = state.rflags := rfl

/--
An instruction pseudocode can update the ordinary stack before a later check,
but that order alone does not establish which effects exception delivery makes
architecturally visible.  Fault outcomes therefore retain the entry state and
label the internally produced state as tentative.
-/
structure TentativeStackEffect where
  before : AMD64.ConcreteMemory.ConcreteMachineState
  tentative : AMD64.ConcreteMemory.ConcreteMachineState

inductive StackPushOutcome where
  | pushed (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | invalidPayload

def planStackPush (state : CPUState) (value : Address) (operandWidth : Nat) :
    Option StackPushPlan :=
  if stackOperandWidthPermitted state operandWidth then
    let byteCount := operandWidth / 8
    let addressSize := stackAddressSize state
    let oldRSP := state.gprValue .rsp
    let newRSP := effectiveOffset (subtractAddress oldRSP (addressOfNat byteCount)) addressSize
    let writeAccess : AccessKindInfo := { kind := .write }
    let request : AddressRequest := {
      rawEffective := newRSP, addressSize := addressSize, segment := .ss,
      access := writeAccess, byteCount := byteCount
    }
    some (StackPushPlan.mk operandWidth oldRSP newRSP
      (truncateIP value operandWidth) request)
  else none

noncomputable def executeStackPush (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (value : Address) (operandWidth : Nat) : StackPushOutcome :=
  match planStackPush before.cpu value operandWidth with
  | none => .invalidPayload
  | some plan =>
      match resolveAccess profile config before.cpu pages plan.request with
      | .error error => .stackFault error
      | .ok resolved =>
          match writeResolved before.memory resolved
              (addressBytes plan.value plan.request.byteCount) with
          | none => .invalidPayload
          | some memory => .pushed {
              cpu := commitStackPointer before.cpu plan.newRSP, memory := memory }

inductive PushOutcome where
  | bodyApplied (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | invalidPayload

noncomputable def executePushGPR (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (source : AMD64.Operands.GPRRef) (operandWidth : Nat) : PushOutcome :=
  if source.width ≠ operandWidth then .invalidPayload
  else match executeStackPush profile config pages before
      (AMD64.IntegerExecution.readGPR before.cpu source) operandWidth with
    | .pushed state => .bodyApplied state
    | .stackFault error => .stackFault error
    | .invalidPayload => .invalidPayload

noncomputable def executePushImmediate (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (source : AMD64.Operands.ImmediateRef) (operandWidth : Nat) : PushOutcome :=
  if ¬source.Valid ∨ source.semanticWidth ≠ operandWidth then .invalidPayload
  else match executeStackPush profile config pages before source.value operandWidth with
    | .pushed state => .bodyApplied state
    | .stackFault error => .stackFault error
    | .invalidPayload => .invalidPayload

inductive NearCallOutcome where
  | retired (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | targetFault (effect : TentativeStackEffect)
  | targetMemoryResolutionRequired
  | controlProtectionBindingRequired
  | invalidPayload

noncomputable def executeNearCall (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (fallthrough : FallthroughEvidence) (targetOperand : NearTarget) (operandWidth : Nat) :
    NearCallOutcome :=
  if config.cr4CET then .controlProtectionBindingRequired
  else if ¬ fallthrough.Valid before.cpu operandWidth then .invalidPayload
  else match resolveNearTarget before.cpu fallthrough.nextRIP operandWidth targetOperand,
      planNearCallPush before.cpu fallthrough.nextRIP operandWidth with
  | .memoryResolutionRequired, _ => .targetMemoryResolutionRequired
  | .invalidPayload, _ | _, none => .invalidPayload
  | .resolved target, some plan =>
      match resolveAccess profile config before.cpu pages plan.request with
      | .error error => .stackFault error
      | .ok resolved =>
          match writeResolved before.memory resolved
              (addressBytes plan.value plan.request.byteCount) with
          | none => .invalidPayload
          | some memory =>
              let pushedCPU := commitStackPointer before.cpu plan.newRSP
              let pushed : AMD64.ConcreteMemory.ConcreteMachineState :=
                { cpu := pushedCPU, memory := memory }
              if targetWithinCurrentCode profile pushedCPU target then
                .retired { pushed with cpu := retireTo pushedCPU target }
              else .targetFault { before := before, tentative := pushed }

def readResolved (store : AMD64.ConcreteMemory.Store) (access : ResolvedAccess) :
    List Byte := access.bytes.map fun byte => store.read byte.physical

def addressOfBytes (bytes : List Byte) : Address := fun bit =>
  match bytes[bit.val / 8]? with
  | some byte => byte ⟨bit.val % 8, by omega⟩
  | none => false

structure StackPopPlan where
  width : Nat
  oldRSP : Address
  poppedRSP : Address
  request : AddressRequest

def planNearRetPop (state : CPUState) (operandWidth : Nat) : Option StackPopPlan :=
  if stackOperandWidthPermitted state operandWidth then
    let byteCount := operandWidth / 8
    let addressSize := stackAddressSize state
    let oldRSP := state.gprValue .rsp
    let poppedRSP := effectiveOffset (addAddress oldRSP (addressOfNat byteCount)) addressSize
    let readAccess : AccessKindInfo := { kind := .read }
    let request := AddressRequest.mk oldRSP addressSize .ss readAccess byteCount 0
    some (StackPopPlan.mk operandWidth oldRSP poppedRSP request)
  else none

inductive StackPopOutcome where
  | popped (value : Address) (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | invalidPayload

noncomputable def executeStackPop (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : StackPopOutcome :=
  match planNearRetPop before.cpu operandWidth with
  | none => .invalidPayload
  | some plan =>
      match resolveAccess profile config before.cpu pages plan.request with
      | .error error => .stackFault error
      | .ok resolved =>
          let value := truncateIP (addressOfBytes (readResolved before.memory resolved)) operandWidth
          .popped value { before with cpu := commitStackPointer before.cpu plan.poppedRSP }

noncomputable def executePopGPR (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (destination : AMD64.Operands.GPRRef) (operandWidth : Nat) : PushOutcome :=
  if destination.width ≠ operandWidth then .invalidPayload
  else match executeStackPop profile config pages before operandWidth with
    | .popped value state => .bodyApplied {
        state with cpu := AMD64.IntegerExecution.writeGPR state.cpu destination value }
    | .stackFault error => .stackFault error
    | .invalidPayload => .invalidPayload

def ioplValue (flags : RFlags) : Nat :=
  (if flags.iopl ⟨0, by omega⟩ then 1 else 0) +
  (if flags.iopl ⟨1, by omega⟩ then 2 else 0)

def flagStackWidthPermitted (state : CPUState) (operandWidth : Nat) : Bool :=
  stackOperandWidthPermitted state operandWidth

def flagImage (state : CPUState) : Address := fun bit =>
  if bit.val = 16 then false
  else if bit.val = 17 ∧ state.execution.mode ∈ [.real, .virtual8086] then false
  else state.rflags.toBits bit

@[simp] theorem flagImage_clears_resume (state : CPUState) :
    flagImage state ⟨16, by omega⟩ = false := by simp [flagImage]

def selectedFlagBit (before : Bool) (value : Address) (width index : Nat) : Bool :=
  if h : index < width ∧ index < 64 then value ⟨index, h.2⟩ else before

def flagsAfterPop (state : CPUState) (value : Address) (operandWidth : Nat) : RFlags :=
  let before := state.rflags
  let load := selectedFlagBit
  let protectedLike := state.execution.mode ∈ [.protectedMode, .compatibility, .long64]
  let canWriteIOPL := state.execution.mode = .real ∨
    (protectedLike ∧ state.execution.cpl.val = 0)
  let canWriteIF := state.execution.mode = .real ∨ state.execution.mode = .virtual8086 ∨
    (protectedLike ∧ state.execution.cpl.val ≤ ioplValue before)
  { cf := load before.cf value operandWidth 0
    fixed1 := true
    pf := load before.pf value operandWidth 2
    reserved3 := false
    af := load before.af value operandWidth 4
    reserved5 := false
    zf := load before.zf value operandWidth 6
    sf := load before.sf value operandWidth 7
    tf := load before.tf value operandWidth 8
    interruptEnable := if canWriteIF then load before.interruptEnable value operandWidth 9
      else before.interruptEnable
    df := load before.df value operandWidth 10
    of := load before.of value operandWidth 11
    iopl := fun bit => if canWriteIOPL then
      load (before.iopl bit) value operandWidth (12 + bit.val) else before.iopl bit
    nestedTask := load before.nestedTask value operandWidth 14
    reserved15 := false
    resume := false
    virtual8086 := before.virtual8086
    ac := load before.ac value operandWidth 18
    virtualInterrupt := before.virtualInterrupt
    virtualInterruptPending := before.virtualInterruptPending
    id := load before.id value operandWidth 21
    reservedHigh := Bits.zero }

@[simp] theorem flagsAfterPop_clears_resume (state : CPUState) (value : Address)
    (operandWidth : Nat) : (flagsAfterPop state value operandWidth).resume = false := rfl

theorem flagsAfterPop_valid (state : CPUState) (value : Address) (operandWidth : Nat) :
    (flagsAfterPop state value operandWidth).Valid := by
  exact ⟨rfl, rfl, rfl, rfl, rfl⟩

inductive FlagStackOutcome where
  | bodyApplied (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | generalProtection
  | configurationBindingRequired
  | invalidPayload

def virtualLowIOPL (state : CPUState) : Bool :=
  state.execution.mode = .virtual8086 && ioplValue state.rflags < 3

noncomputable def executePushFlags (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : FlagStackOutcome :=
  if !flagStackWidthPermitted before.cpu operandWidth then .invalidPayload
  else if virtualLowIOPL before.cpu && operandWidth ≠ 16 then .generalProtection
  else if virtualLowIOPL before.cpu then .configurationBindingRequired
  else match executeStackPush profile config pages before (flagImage before.cpu) operandWidth with
    | .pushed state => .bodyApplied state
    | .stackFault error => .stackFault error
    | .invalidPayload => .invalidPayload

noncomputable def executePopFlags (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : FlagStackOutcome :=
  if !flagStackWidthPermitted before.cpu operandWidth then .invalidPayload
  else if virtualLowIOPL before.cpu && operandWidth ≠ 16 then .generalProtection
  else if virtualLowIOPL before.cpu then .configurationBindingRequired
  else match executeStackPop profile config pages before operandWidth with
    | .popped value state => .bodyApplied {
        state with cpu := { state.cpu with
          rflags := flagsAfterPop before.cpu value operandWidth } }
    | .stackFault error => .stackFault error
    | .invalidPayload => .invalidPayload

def basePointerRef (operandWidth : Nat) : Option AMD64.Operands.GPRRef :=
  match operandWidth with
  | 16 => some { index := GPR.rbp.toFin, view := .low16 }
  | 32 => some { index := GPR.rbp.toFin, view := .low32 }
  | 64 => some { index := GPR.rbp.toFin, view := .full64 }
  | _ => none

inductive EnterOutcome where
  | bodyApplied (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | initialPushFault (error : ResolutionError)
  | finalStackCheckFault (effect : TentativeStackEffect) (error : ResolutionError)
  | nestedLevelBindingRequired
  | invalidPayload

noncomputable def executeEnter (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth allocationBytes nestingLevel : Nat) : EnterOutcome :=
  if 255 < nestingLevel then .invalidPayload
  else if nestingLevel % 32 ≠ 0 then .nestedLevelBindingRequired
  else if 65535 < allocationBytes then .invalidPayload
  else match basePointerRef operandWidth with
  | none => .invalidPayload
  | some bp =>
      if before.cpu.execution.mode = .long64 ∧ operandWidth = 32 then .invalidPayload
      else match executeStackPush profile config pages before
          (AMD64.IntegerExecution.readGPR before.cpu bp) operandWidth with
      | .stackFault error => .initialPushFault error
      | .invalidPayload => .invalidPayload
      | .pushed pushed =>
          let framePointer := pushed.cpu.gprValue .rsp
          let finalRSP := effectiveOffset
            (subtractAddress framePointer (addressOfNat allocationBytes))
            (stackAddressSize pushed.cpu)
          let request : AddressRequest := {
            rawEffective := finalRSP, addressSize := stackAddressSize pushed.cpu,
            segment := .ss, access := { kind := .write }, byteCount := operandWidth / 8
          }
          match resolveAccess profile config pushed.cpu pages request with
          | .error error => .finalStackCheckFault
              { before := before, tentative := pushed } error
          | .ok _ =>
              let withStack := commitStackPointer pushed.cpu finalRSP
              let withFrame := AMD64.IntegerExecution.writeGPR withStack bp framePointer
              .bodyApplied { pushed with cpu := withFrame }

inductive LeaveOutcome where
  | bodyApplied (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (effect : TentativeStackEffect) (error : ResolutionError)
  | invalidPayload

noncomputable def executeLeave (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : LeaveOutcome :=
  match basePointerRef operandWidth with
  | none => .invalidPayload
  | some bp =>
      if before.cpu.execution.mode = .long64 ∧ operandWidth = 32 then .invalidPayload
      else
        let frameAddress := effectiveOffset (before.cpu.gprValue .rbp)
          (stackAddressSize before.cpu)
        let staged : AMD64.ConcreteMemory.ConcreteMachineState :=
          { before with cpu := commitStackPointer before.cpu frameAddress }
        match executeStackPop profile config pages staged operandWidth with
        | .popped value state => .bodyApplied {
            state with cpu := AMD64.IntegerExecution.writeGPR state.cpu bp value }
        | .stackFault error => .stackFault
            { before := before, tentative := staged } error
        | .invalidPayload => .invalidPayload

inductive MultiStackOutcome where
  | bodyApplied (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (effect : TentativeStackEffect) (error : ResolutionError)
  | invalidPayload

noncomputable def executePushSequence (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : AMD64.ConcreteMemory.ConcreteMachineState)
    (values : List Address) (operandWidth : Nat) : MultiStackOutcome :=
  match values with
  | [] => .bodyApplied current
  | value :: rest =>
      match executeStackPush profile config pages current value operandWidth with
      | .pushed next => executePushSequence profile config pages entry next rest operandWidth
      | .stackFault error => .stackFault
          { before := entry, tentative := current } error
      | .invalidPayload => .invalidPayload
termination_by values.length

def legacyGPRRef (register : GPR) (operandWidth : Nat) : Option AMD64.Operands.GPRRef :=
  match operandWidth with
  | 16 => some { index := register.toFin, view := .low16 }
  | 32 => some { index := register.toFin, view := .low32 }
  | _ => none

noncomputable def executePusha (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : MultiStackOutcome :=
  if before.cpu.execution.mode = .long64 then .invalidPayload
  else match legacyGPRRef .rax operandWidth, legacyGPRRef .rcx operandWidth,
      legacyGPRRef .rdx operandWidth, legacyGPRRef .rbx operandWidth,
      legacyGPRRef .rsp operandWidth, legacyGPRRef .rbp operandWidth,
      legacyGPRRef .rsi operandWidth, legacyGPRRef .rdi operandWidth with
  | some ax, some cx, some dx, some bx, some sp, some bp, some si, some di =>
      let values := [ax, cx, dx, bx, sp, bp, si, di].map
        (AMD64.IntegerExecution.readGPR before.cpu)
      executePushSequence profile config pages before before values operandWidth
  | _, _, _, _, _, _, _, _ => .invalidPayload

noncomputable def executePopSequence (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (entry current : AMD64.ConcreteMemory.ConcreteMachineState)
    (destinations : List (Option AMD64.Operands.GPRRef))
    (operandWidth : Nat) : MultiStackOutcome :=
  match destinations with
  | [] => .bodyApplied current
  | destination :: rest =>
      match executeStackPop profile config pages current operandWidth with
      | .popped value popped =>
          let next := match destination with
            | none => popped
            | some register => { popped with cpu :=
                AMD64.IntegerExecution.writeGPR popped.cpu register value }
          executePopSequence profile config pages entry next rest operandWidth
      | .stackFault error => .stackFault
          { before := entry, tentative := current } error
      | .invalidPayload => .invalidPayload
termination_by destinations.length

noncomputable def executePopa (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth : Nat) : MultiStackOutcome :=
  if before.cpu.execution.mode = .long64 then .invalidPayload
  else match legacyGPRRef .rdi operandWidth, legacyGPRRef .rsi operandWidth,
      legacyGPRRef .rbp operandWidth, legacyGPRRef .rbx operandWidth,
      legacyGPRRef .rdx operandWidth, legacyGPRRef .rcx operandWidth,
      legacyGPRRef .rax operandWidth with
  | some di, some si, some bp, some bx, some dx, some cx, some ax =>
      executePopSequence profile config pages before before
        [some di, some si, some bp, none, some bx, some dx, some cx, some ax]
        operandWidth
  | _, _, _, _, _, _, _ => .invalidPayload

def selectorAddress (selector : SegmentSelector) : Address := fun bit =>
  if h : bit.val < 16 then selector.raw ⟨bit.val, h⟩ else false

def selectorFromAddress (value : Address) : SegmentSelector :=
  { raw := fun bit => value ⟨bit.val, by omega⟩ }

def realSegmentBase (selector : SegmentSelector) : Address := fun bit =>
  if h : 4 ≤ bit.val ∧ bit.val < 20 then selector.raw ⟨bit.val - 4, by omega⟩ else false

def realCodeSegment (selector : SegmentSelector) : SegmentRegister := {
  selector := selector
  cache := {
    base := realSegmentBase selector, limit := fun bit => bit.val < 16,
    present := true, dpl := ⟨0, by omega⟩, readable := true, writable := false,
    executable := true, conforming := false, expandDown := false,
    defaultBig := false, longMode := false
  }
  unusable := false
}

def commitRealFarTarget (state : CPUState) (selector : SegmentSelector)
    (target : Address) : CPUState :=
  { state with rip := target, segments := {
      state.segments with cs := realCodeSegment selector } }

inductive FarTransferOutcome where
  | retired (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (effect : TentativeStackEffect) (error : ResolutionError)
  | targetFault (effect : TentativeStackEffect)
  | descriptorBindingRequired
  | invalidPayload

def realOrVirtualMode (state : CPUState) : Bool :=
  state.execution.mode ∈ [.real, .virtual8086]

noncomputable def executeFarJump (profile : ArchitectureProfile)
    (before : AMD64.ConcreteMemory.ConcreteMachineState) (selector : SegmentSelector)
    (offset : Address) (operandWidth : Nat) : FarTransferOutcome :=
  if !realOrVirtualMode before.cpu then .descriptorBindingRequired
  else if !(operandWidth ∈ [16, 32]) then .invalidPayload
  else
    let target := truncateIP offset operandWidth
    if targetWithinCurrentCode profile before.cpu target then
      .retired { before with cpu := commitRealFarTarget before.cpu selector target }
    else .targetFault { before := before, tentative := before }

noncomputable def executeFarCall (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (fallthrough : FallthroughEvidence) (selector : SegmentSelector)
    (offset : Address) (operandWidth : Nat) : FarTransferOutcome :=
  if !realOrVirtualMode before.cpu then .descriptorBindingRequired
  else if !(operandWidth ∈ [16, 32]) ∨ ¬fallthrough.Valid before.cpu operandWidth then
    .invalidPayload
  else
    match executeStackPush profile config pages before
        (selectorAddress before.cpu.segments.cs.selector) operandWidth with
    | .stackFault error => .stackFault { before := before, tentative := before } error
    | .invalidPayload => .invalidPayload
    | .pushed afterCS =>
        match executeStackPush profile config pages afterCS fallthrough.nextRIP operandWidth with
        | .stackFault error => .stackFault
            { before := before, tentative := afterCS } error
        | .invalidPayload => .invalidPayload
        | .pushed afterRIP =>
            let target := truncateIP offset operandWidth
            if targetWithinCurrentCode profile afterRIP.cpu target then
              .retired { afterRIP with cpu :=
                (commitRealFarTarget afterRIP.cpu selector target) }
            else .targetFault { before := before, tentative := afterRIP }

noncomputable def executeFarRet (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth cleanupBytes : Nat) : FarTransferOutcome :=
  if !realOrVirtualMode before.cpu then .descriptorBindingRequired
  else if !(operandWidth ∈ [16, 32]) ∨ 65535 < cleanupBytes then .invalidPayload
  else match executeStackPop profile config pages before operandWidth with
  | .stackFault error => .stackFault { before := before, tentative := before } error
  | .invalidPayload => .invalidPayload
  | .popped target afterRIP =>
      match executeStackPop profile config pages afterRIP operandWidth with
      | .stackFault error => .stackFault
          { before := before, tentative := afterRIP } error
      | .invalidPayload => .invalidPayload
      | .popped selectorValue afterCS =>
          if targetWithinCurrentCode profile afterCS.cpu target then
            let cleanedRSP := effectiveOffset
              (addAddress (afterCS.cpu.gprValue .rsp) (addressOfNat cleanupBytes))
              (stackAddressSize afterCS.cpu)
            let cleaned := commitStackPointer afterCS.cpu cleanedRSP
            .retired { afterCS with cpu := (commitRealFarTarget cleaned
              (selectorFromAddress selectorValue) target) }
          else .targetFault { before := before, tentative := afterCS }

inductive SegmentLoadDestination where
  | ds | es | fs | gs | ss
  deriving DecidableEq, Repr

structure AssumedSegmentProjection where
  selector : SegmentSelector
  loaded : SegmentRegister
  tableLimitAssumed : Bool
  typeAssumed : Bool
  privilegeAssumed : Bool
  presentAssumed : Bool

def AssumedSegmentProjection.AssumptionsRecorded
    (projection : AssumedSegmentProjection) : Prop :=
  projection.loaded.selector = projection.selector ∧ projection.tableLimitAssumed ∧
  projection.typeAssumed ∧ projection.privilegeAssumed ∧ projection.presentAssumed

def commitSegmentLoad (state : CPUState) (destination : SegmentLoadDestination)
    (loaded : SegmentRegister) : CPUState :=
  { state with segments := match destination with
    | .ds => { state.segments with ds := loaded }
    | .es => { state.segments with es := loaded }
    | .fs => { state.segments with fs := loaded }
    | .gs => { state.segments with gs := loaded }
    | .ss => { state.segments with ss := loaded } }

inductive SegmentLoadOutcome where
  | bodyAppliedUnderAssumption (state : CPUState)
  | assumedProjectionRequired
  | assumptionRejected

/-! This is an explicitly assumed projection, not descriptor validation.  It
does not close any segment-load form until raw table bytes, bounds, type,
privilege, and presence are derived by the protection model. -/
noncomputable def applyAssumedSegmentProjection (state : CPUState)
    (destination : SegmentLoadDestination) (selector : SegmentSelector)
    (projection : Option AssumedSegmentProjection) : SegmentLoadOutcome :=
  match projection with
  | none => .assumedProjectionRequired
  | some assumed =>
      if assumed.selector = selector ∧ assumed.AssumptionsRecorded then
        .bodyAppliedUnderAssumption (commitSegmentLoad state destination assumed.loaded)
      else .assumptionRejected

inductive UndefinedOpcode where
  | ud0 | ud1 | ud2
  deriving DecidableEq, Repr

inductive UndefinedOpcodeOutcome where
  | invalidOpcodeFault

def executeUndefinedOpcode (_ : UndefinedOpcode) : UndefinedOpcodeOutcome :=
  .invalidOpcodeFault

theorem undefined_opcode_faults (opcode : UndefinedOpcode) :
    executeUndefinedOpcode opcode = .invalidOpcodeFault := rfl

inductive NearRetOutcome where
  | retired (state : AMD64.ConcreteMemory.ConcreteMachineState)
  | stackFault (error : ResolutionError)
  | targetFault (effect : TentativeStackEffect)
  | controlProtectionBindingRequired
  | invalidPayload

noncomputable def executeNearRet (profile : ArchitectureProfile) (config : SystemConfig)
    (pages : PageMap) (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth cleanupBytes : Nat) : NearRetOutcome :=
  if config.cr4CET then .controlProtectionBindingRequired
  else if 65535 < cleanupBytes then .invalidPayload
  else match planNearRetPop before.cpu operandWidth with
  | none => .invalidPayload
  | some plan =>
      match resolveAccess profile config before.cpu pages plan.request with
      | .error error => .stackFault error
      | .ok resolved =>
          let target := truncateIP (addressOfBytes (readResolved before.memory resolved)) operandWidth
          let poppedCPU := commitStackPointer before.cpu plan.poppedRSP
          let popped : AMD64.ConcreteMemory.ConcreteMachineState :=
            { cpu := poppedCPU, memory := before.memory }
          if targetWithinCurrentCode profile poppedCPU target then
            let finalRSP := effectiveOffset
              (addAddress plan.poppedRSP (addressOfNat cleanupBytes)) (stackAddressSize poppedCPU)
            let cleanedCPU := commitStackPointer poppedCPU finalRSP
            .retired { popped with cpu := retireTo cleanedCPU target }
          else .targetFault { before := before, tentative := popped }

theorem near_call_cet_requires_binding (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap)
    (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (fallthrough : FallthroughEvidence) (target : NearTarget) (operandWidth : Nat)
    (enabled : config.cr4CET = true) :
    executeNearCall profile config pages before fallthrough target operandWidth =
      .controlProtectionBindingRequired := by
  simp [executeNearCall, enabled]

theorem near_ret_cet_requires_binding (profile : ArchitectureProfile)
    (config : SystemConfig) (pages : PageMap)
    (before : AMD64.ConcreteMemory.ConcreteMachineState)
    (operandWidth cleanupBytes : Nat) (enabled : config.cr4CET = true) :
    executeNearRet profile config pages before operandWidth cleanupBytes =
      .controlProtectionBindingRequired := by
  simp [executeNearRet, enabled]

namespace Source

/-! Reviewed transcription of the TLA+ condition and truncation operators.
This is the same explicit source boundary used by the other AMD64 modules; it
does not claim a parsed or verified translation of arbitrary TLA+. -/

def conditionFromStatus (condition : Condition) (flags : ArithmeticFlags) : Bool :=
  match condition with
  | .o => flags.of | .no => !flags.of | .b => flags.cf | .ae => !flags.cf
  | .e => flags.zf | .ne => !flags.zf | .be => flags.cf || flags.zf
  | .a => !flags.cf && !flags.zf | .s => flags.sf | .ns => !flags.sf
  | .p => flags.pf | .np => !flags.pf | .l => Bool.xor flags.sf flags.of
  | .ge => flags.sf == flags.of | .le => flags.zf || Bool.xor flags.sf flags.of
  | .g => !flags.zf && flags.sf == flags.of

def truncateIP (address : Address) (width : Nat) : Address := fun bit =>
  if bit.val < width then address bit else false

theorem condition_correspondence (condition : Condition) (flags : ArithmeticFlags) :
    AMD64.Control.conditionFromStatus condition flags = conditionFromStatus condition flags := by
  cases condition <;> rfl

theorem truncate_correspondence (address : Address) (width : Nat) :
    AMD64.Control.truncateIP address width = truncateIP address width := by rfl

end Source

end
end AMD64.Control
