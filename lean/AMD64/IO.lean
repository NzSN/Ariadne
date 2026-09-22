import AMD64.ArchitecturalState
import AMD64.Memory
import AMD64.Exceptions
import AMD64.IntegerSemantics
import Std

/-!
Port-I/O permission, device-environment, and strongly ordered event contracts.

Authority: AMD APM Volume 1 revision 3.25 sections 3.8.1-3.8.3; Volume 2
revision 3.45 section 12.2.4; Volume 3 revision 3.38 IN/OUT/INS/OUTS entries.

The environment is an explicit list of valid rules over direction, base port,
width, data, and byte-transaction order. It cannot mutate CPU state. Missing
rules and capture gaps are modeling-unavailable boundaries, not zeros/faults.
-/

namespace AMD64.IO

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics

inductive Width where
  | byte | word | dword
  deriving DecidableEq, Repr

def Width.bytes : Width -> Nat
  | .byte => 1 | .word => 2 | .dword => 4

def Width.bits (width : Width) : Nat := width.bytes * 8

inductive Direction where
  | input | output
  deriving DecidableEq, Repr

structure PortRequest where
  direction : Direction
  base : Fin 65536
  width : Width
  /-- Empty for input; exact least-significant-first bytes for output. -/
  writeData : List Byte
  sequence : Nat

def PortRequest.portSpan (request : PortRequest) : List Nat :=
  (List.range request.width.bytes).map (request.base.val + ·)

def PortRequest.withinBoundary (request : PortRequest) : Prop :=
  request.base.val + request.width.bytes ≤ 65536

def PortRequest.aligned (request : PortRequest) : Prop :=
  request.base.val % request.width.bytes = 0

def PortRequest.ValidShape (request : PortRequest) : Prop :=
  match request.direction with
  | .input => request.writeData = []
  | .output => request.writeData.length = request.width.bytes

def portFromImmediate (immediate : Fin 256) : Fin 65536 :=
  ⟨immediate.val, by omega⟩

/-- DX contributes exactly its low 16-bit unsigned value. -/
def portFromDX (cpu : CPUState) : Fin 65536 :=
  Fin.ofNat 65536 (unsignedValue cpu.rdx 16)

def accumulatorBytes (cpu : CPUState) (width : Width) : List Byte :=
  (List.range width.bytes).map fun byteIndex bit =>
    getBit cpu.rax (byteIndex * 8 + bit.val)

theorem accumulatorBytes_length (cpu : CPUState) (width : Width) :
    (accumulatorBytes cpu width).length = width.bytes := by
  simp [accumulatorBytes]

def inputBytesToWord (bytes : List Byte) : IWord := fun bit =>
  match bytes[bit.val / 8]? with
  | some byte => byte ⟨bit.val % 8, Nat.mod_lt _ (by decide)⟩
  | none => false

/-- AL/AX preserve upper bits; EAX clears 63:32 only in 64-bit mode. -/
def InputAccumulatorWriteAllowed (cpu : CPUState) (width : Width)
    (data : List Byte) (afterRAX : IWord) : Prop :=
  data.length = width.bytes ∧
  ∀ bit : Fin 64,
    if bit.val < width.bits then afterRAX bit = inputBytesToWord data bit
    else if cpu.execution.mode = .long64 ∧ width = .dword then afterRAX bit = false
    else if cpu.execution.mode = .long64 ∨ bit.val < 32 then afterRAX bit = cpu.rax bit
    else True

def inputRequestDX (cpu : CPUState) (width : Width) (sequence : Nat) : PortRequest := {
  direction := .input, base := portFromDX cpu, width, writeData := [], sequence
}

def inputRequestImmediate (immediate : Fin 256) (width : Width)
    (sequence : Nat) : PortRequest := {
  direction := .input, base := portFromImmediate immediate, width,
  writeData := [], sequence
}

def outputRequestDX (cpu : CPUState) (width : Width) (sequence : Nat) : PortRequest := {
  direction := .output, base := portFromDX cpu, width,
  writeData := accumulatorBytes cpu width, sequence
}

def outputRequestImmediate (cpu : CPUState) (immediate : Fin 256) (width : Width)
    (sequence : Nat) : PortRequest := {
  direction := .output, base := portFromImmediate immediate, width,
  writeData := accumulatorBytes cpu width, sequence
}

theorem direct_requests_have_valid_shape (cpu : CPUState) (immediate : Fin 256)
    (width : Width) (sequence : Nat) :
    (inputRequestDX cpu width sequence).ValidShape ∧
    (inputRequestImmediate immediate width sequence).ValidShape ∧
    (outputRequestDX cpu width sequence).ValidShape ∧
    (outputRequestImmediate cpu immediate width sequence).ValidShape := by
  simp [PortRequest.ValidShape, inputRequestDX, inputRequestImmediate,
    outputRequestDX, outputRequestImmediate, accumulatorBytes_length]

inductive BoundaryDisposition where
  | supported
  | sourceUnspecified
  deriving DecidableEq, Repr

def PortRequest.boundaryDisposition (request : PortRequest) : BoundaryDisposition :=
  if request.base.val + request.width.bytes ≤ 65536
  then .supported else .sourceUnspecified

/-- Effective view of the TSS I/O bitmap read required for this instruction. -/
inductive PermissionSnapshot where
  | ready (covered denied : Nat -> Bool)
  | pageFault (linear : Address) (code : PageFaultError)
  | unavailable

inductive PermissionBitValue where
  | available (denied : Bool)
  | unavailable
  deriving DecidableEq, Repr

structure PermissionBitRead where
  port : Nat
  value : PermissionBitValue
  deriving DecidableEq, Repr

def PermissionBitValue.isAvailable : PermissionBitValue -> Bool
  | .available _ => true
  | .unavailable => false

def PermissionBitValue.isDenied : PermissionBitValue -> Bool
  | .available denied => denied
  | .unavailable => false

/-- Build the effective snapshot only from exactly the requested captured bits. -/
def permissionSnapshotFromReads (request : PortRequest)
    (reads : List PermissionBitRead) : PermissionSnapshot :=
  if decide ((reads.map (·.port)).Perm request.portSpan) &&
      reads.all (fun read => read.value.isAvailable) then
    .ready
      (fun port => reads.any fun read => read.port = port)
      (fun port => reads.any fun read => read.port = port && read.value.isDenied)
  else .unavailable

def PermissionSnapshot.Valid : PermissionSnapshot -> Prop
  | .ready covered denied =>
      (∀ port, covered port = true -> port < 65536) ∧
      (∀ port, denied port = true -> covered port = true)
  | .pageFault .. | .unavailable => True

inductive PermissionDecision where
  | allowed
  | generalProtection
  | pageFault (fault : AccessFault)
  | unavailable

def ioplValue (flags : RFlags) : Nat :=
  (if flags.iopl ⟨1, by omega⟩ then 2 else 0) +
  (if flags.iopl ⟨0, by omega⟩ then 1 else 0)

def bitmapRequired (cpu : CPUState) : Bool :=
  cpu.execution.mode == .virtual8086 || cpu.execution.cpl.val > ioplValue cpu.rflags

def permissionDecision (cpu : CPUState) (snapshot : PermissionSnapshot)
    (request : PortRequest) : PermissionDecision :=
  if !bitmapRequired cpu then .allowed
  else match snapshot with
  | .pageFault linear code => .pageFault (.page linear code)
  | .unavailable => .unavailable
  | .ready covered denied =>
      if request.portSpan.all fun port => covered port && !denied port
      then .allowed else .generalProtection

structure IOEvent where
  direction : Direction
  base : Fin 65536
  width : Width
  data : List Byte
  sequence : Nat
  stronglyOrdered : Bool
  /-- Byte offsets, not port addresses. Undefined order is an explicit permutation. -/
  transactionOrder : List Nat

structure DeviceRule where
  direction : Direction
  base : Fin 65536
  width : Width
  /-- Exact expected output bytes; empty for input rules. -/
  writeData : List Byte
  /-- Exact returned input bytes; empty for output rules. -/
  readData : List Byte
  transactionOrder : List Nat

def DeviceRule.Valid (rule : DeviceRule) : Prop :=
  (match rule.direction with
   | .input => rule.writeData = [] ∧ rule.readData.length = rule.width.bytes
   | .output => rule.writeData.length = rule.width.bytes ∧ rule.readData = []) ∧
  rule.transactionOrder.Perm (List.range rule.width.bytes) ∧
  (rule.base.val % rule.width.bytes = 0 ->
    rule.transactionOrder = List.range rule.width.bytes) ∧
  rule.base.val + rule.width.bytes ≤ 65536

def DeviceRule.Matches (rule : DeviceRule) (request : PortRequest) : Prop :=
  rule.direction = request.direction ∧ rule.base = request.base ∧
  rule.width = request.width ∧
  (request.direction = .output -> rule.writeData = request.writeData)

def DeviceRule.event (rule : DeviceRule) (request : PortRequest) : IOEvent := {
  direction := request.direction
  base := request.base
  width := request.width
  data := if request.direction = .input then rule.readData else request.writeData
  sequence := request.sequence
  stronglyOrdered := true
  transactionOrder := rule.transactionOrder
}

structure DeviceEnvironment where
  rules : List DeviceRule

/-- Explicit environment relation. Multiple matching rules express declared device nondeterminism. -/
def DeviceStep (environment : DeviceEnvironment) (request : PortRequest)
    (event : IOEvent) : Prop :=
  request.ValidShape ∧ request.withinBoundary ∧
  ∃ rule ∈ environment.rules, rule.Valid ∧ rule.Matches request ∧
    event = rule.event request

structure OrderingContext where
  priorWritesComplete : Bool
  nextSequence : Nat
  deriving DecidableEq, Repr

def OrderingAllows (ordering : OrderingContext) (request : PortRequest) : Prop :=
  ordering.priorWritesComplete = true ∧ request.sequence = ordering.nextSequence

/-- Complete shared contract before an instruction-specific CPU/memory body step. -/
def IOTransferAllowed (cpu : CPUState) (snapshot : PermissionSnapshot)
    (ordering : OrderingContext) (environment : DeviceEnvironment)
    (request : PortRequest) (event : IOEvent) : Prop :=
  permissionDecision cpu snapshot request = .allowed ∧
  OrderingAllows ordering request ∧ DeviceStep environment request event

inductive TransferDisposition where
  | completed (event : IOEvent)
  | generalProtection
  | pageFault (fault : AccessFault)
  | permissionUnavailable
  | boundaryUnspecified
  | waitingForOrdering
  | deviceUnavailable

/-- Exhaustive shared pre-body disposition; completed events remain relational. -/
def TransferDispositionAllowed (cpu : CPUState) (snapshot : PermissionSnapshot)
    (ordering : OrderingContext) (environment : DeviceEnvironment)
    (request : PortRequest) (result : TransferDisposition) : Prop :=
  snapshot.Valid ∧ request.ValidShape ∧ match result with
  | .completed event => IOTransferAllowed cpu snapshot ordering environment request event
  | .generalProtection => permissionDecision cpu snapshot request = .generalProtection
  | .pageFault fault => permissionDecision cpu snapshot request = .pageFault fault
  | .permissionUnavailable => permissionDecision cpu snapshot request = .unavailable
  | .boundaryUnspecified => permissionDecision cpu snapshot request = .allowed ∧
      request.boundaryDisposition = .sourceUnspecified
  | .waitingForOrdering => permissionDecision cpu snapshot request = .allowed ∧
      request.boundaryDisposition = .supported ∧ ¬ OrderingAllows ordering request
  | .deviceUnavailable => permissionDecision cpu snapshot request = .allowed ∧
      request.boundaryDisposition = .supported ∧ OrderingAllows ordering request ∧
      ¬ ∃ event, DeviceStep environment request event

/-! Direct IN/OUT body binding.  The request constructor fixes the only two
architectural port sources, and a completed input event is related to an exact
AL/AX/EAX write.  Failure dispositions frame CPU state; unavailable capture is
therefore never interpreted as an input value. -/

inductive DirectPortSource where
  | immediate (value : Fin 256)
  | dx
  deriving DecidableEq, Repr

def DirectRequest (cpu : CPUState) (direction : Direction) (source : DirectPortSource)
    (width : Width) (sequence : Nat) : PortRequest :=
  match direction, source with
  | .input, .immediate value => inputRequestImmediate value width sequence
  | .input, .dx => inputRequestDX cpu width sequence
  | .output, .immediate value => outputRequestImmediate cpu value width sequence
  | .output, .dx => outputRequestDX cpu width sequence

inductive DirectOutcome where
  | bodyApplied (cpu : CPUState) (event : IOEvent)
  | generalProtection
  | pageFault (fault : AccessFault)
  | permissionUnavailable
  | boundaryUnspecified
  | waitingForOrdering
  | deviceUnavailable

def writeInputAccumulator (cpu : CPUState) (width : Width) (data : List Byte) : CPUState :=
  let value := inputBytesToWord data
  { cpu with gpr := fun register =>
      if register = GPR.rax.toFin then
        fun bit =>
          if bit.val < width.bits then value bit
          else if cpu.execution.mode = .long64 && width = .dword then false
          else cpu.rax bit
      else cpu.gpr register }

/-- Relational CPU write so legacy/compatibility bits 63:32 retain their
architecturally undefined range instead of being forced to a convenient
witness.  Every other CPU-owned field and GPR is framed. -/
def InputCPUWriteAllowed (before after : CPUState) (width : Width)
    (data : List Byte) : Prop :=
  InputAccumulatorWriteAllowed before width data after.rax ∧
  (∀ register, register ≠ GPR.rax.toFin -> after.gpr register = before.gpr register) ∧
  after.rip = before.rip ∧ after.rflags = before.rflags ∧
  after.segments = before.segments ∧ after.x87 = before.x87 ∧
  after.vectors = before.vectors ∧ after.kMask = before.kMask ∧
  after.mxcsr = before.mxcsr ∧ after.execution = before.execution

def ExecuteDirect (cpu : CPUState) (direction : Direction) (source : DirectPortSource)
    (width : Width) (sequence : Nat) (snapshot : PermissionSnapshot)
    (ordering : OrderingContext) (environment : DeviceEnvironment)
    (disposition : TransferDisposition) (outcome : DirectOutcome) : Prop :=
  let request := DirectRequest cpu direction source width sequence
  TransferDispositionAllowed cpu snapshot ordering environment request disposition ∧
  match disposition with
  | .completed event =>
      match direction with
      | .input => event.direction = .input ∧ event.data.length = width.bytes ∧
          ∃ after, InputCPUWriteAllowed cpu after width event.data ∧
            outcome = .bodyApplied after event
      | .output => event.direction = .output ∧ event.data = accumulatorBytes cpu width ∧
          outcome = .bodyApplied cpu event
  | .generalProtection => outcome = .generalProtection
  | .pageFault fault => outcome = .pageFault fault
  | .permissionUnavailable => outcome = .permissionUnavailable
  | .boundaryUnspecified => outcome = .boundaryUnspecified
  | .waitingForOrdering => outcome = .waitingForOrdering
  | .deviceUnavailable => outcome = .deviceUnavailable

theorem direct_input_completed_writes_accumulator (cpu : CPUState)
    (source : DirectPortSource) (width : Width) (sequence : Nat)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment) (event : IOEvent)
    (after : CPUState)
    (transfer : TransferDispositionAllowed cpu snapshot ordering environment
      (DirectRequest cpu .input source width sequence) (.completed event))
    (direction : event.direction = .input)
    (length : event.data.length = width.bytes)
    (write : InputCPUWriteAllowed cpu after width event.data) :
    ExecuteDirect cpu .input source width sequence snapshot ordering environment
      (.completed event) (.bodyApplied after event) := by
  simp [ExecuteDirect, direction, length]
  exact ⟨transfer, write⟩

theorem direct_output_completed_frames_cpu (cpu : CPUState)
    (source : DirectPortSource) (width : Width) (sequence : Nat)
    (snapshot : PermissionSnapshot) (ordering : OrderingContext)
    (environment : DeviceEnvironment) (event : IOEvent)
    (transfer : TransferDispositionAllowed cpu snapshot ordering environment
      (DirectRequest cpu .output source width sequence) (.completed event))
    (direction : event.direction = .output)
    (data : event.data = accumulatorBytes cpu width) :
    ExecuteDirect cpu .output source width sequence snapshot ordering environment
      (.completed event) (.bodyApplied cpu event) := by
  simp [ExecuteDirect, direction, data]
  exact transfer

def PermissionDecision.accessFault : PermissionDecision -> Option AccessFault
  | .generalProtection => some .generalProtection
  | .pageFault fault => some fault
  | _ => none

theorem gp_maps_to_gp_zero :
    (PermissionDecision.generalProtection.accessFault.map AMD64.Exceptions.ofAccessFault) =
      some (.gp, .selector 0, none) := rfl

theorem privileged_bypasses_unavailable_bitmap (cpu : CPUState) (request : PortRequest)
    (privileged : cpu.execution.mode ≠ .virtual8086)
    (level : cpu.execution.cpl.val ≤ ioplValue cpu.rflags) :
    permissionDecision cpu .unavailable request = .allowed := by
  simp [permissionDecision, bitmapRequired, privileged, show ¬cpu.execution.cpl.val >
    ioplValue cpu.rflags by omega]

theorem vm86_never_bypasses_bitmap (cpu : CPUState) (request : PortRequest)
    (vm86 : cpu.execution.mode = .virtual8086) :
    permissionDecision cpu .unavailable request = .unavailable := by
  simp [permissionDecision, bitmapRequired, vm86]

theorem denied_port_causes_gp (cpu : CPUState) (request : PortRequest)
    (required : bitmapRequired cpu = true)
    (covered denied : Nat -> Bool)
    (blocked : (request.portSpan.all fun port => covered port && !denied port) = false) :
    permissionDecision cpu (.ready covered denied) request = .generalProtection := by
  simp [permissionDecision, required, blocked]

theorem device_event_is_strongly_ordered (environment : DeviceEnvironment)
    (request : PortRequest) (event : IOEvent)
    (step : DeviceStep environment request event) : event.stronglyOrdered = true := by
  rcases step with ⟨_, _, rule, _, _, _, rfl⟩
  rfl

theorem cross_boundary_has_no_device_step (environment : DeviceEnvironment)
    (request : PortRequest) (event : IOEvent)
    (crosses : ¬ request.withinBoundary) :
    ¬ DeviceStep environment request event := by
  intro step
  exact crosses step.2.1

namespace Source

/-! Reviewed transcription boundary for permission triggering and port spans. -/

def portSpan (base bytes : Nat) : List Nat :=
  (List.range bytes).map (base + ·)

theorem portSpan_correspondence (request : PortRequest) :
    request.portSpan = Source.portSpan request.base.val request.width.bytes := rfl

end Source
end AMD64.IO
