import AMD64.IO
import AMD64.IntegerExecution
import AMD64.Memory
import Std

/-!
Source-grounded instruction-body relations for the D2 execution lane.

The module keeps implementation data explicit: CPUID rows, entropy samples,
processor-register values, monitor wake causes, and LWP device operations are
environment records.  Missing environment evidence is `modelingUnavailable`;
it is never converted to zero, a fault, or an arbitrary CPU callback.
-/

namespace AMD64.External

open AMD64.Arch
open AMD64.MemoryModel
open AMD64.IntegerSemantics
open AMD64.IntegerExecution
open AMD64.Operands

inductive Fault where
  | ud | de | gp | pf (fault : AccessFault) | nm | mf

inductive Outcome where
  | bodyApplied (cpu : CPUState)
  | fault (kind : Fault)
  | modelingUnavailable (reason : String)

def low8 (word : IWord) : Nat := unsignedValue word 8
def high8 (word : IWord) : Nat := (unsignedValue word 16 / 256) % 256
def lowNibble (value : Nat) : Nat := value % 16
def axValue (ah al : Nat) : IWord := wordOfNat ((ah % 256) * 256 + (al % 256))

def adjustedAAA (beforeAX : Nat) (adjust : Bool) : Nat :=
  let adjusted := if adjust then (beforeAX + 0x106) % 0x10000 else beforeAX % 0x10000
  (adjusted / 256) * 256 + adjusted % 16

def adjustedAAS (beforeAX : Nat) (adjust : Bool) : Nat :=
  let adjusted := if adjust then (beforeAX + 0x10000 - 0x106) % 0x10000
                  else beforeAX % 0x10000
  (adjusted / 256) * 256 + adjusted % 16

def writeAX (cpu : CPUState) (value : IWord) : CPUState :=
  writeGPR cpu ⟨GPR.rax.toFin, .low16⟩ value

def writeLow (cpu : CPUState) (register : Fin 16) (width : Nat)
    (value : IWord) : CPUState :=
  match width with
  | 16 => writeGPR cpu ⟨register, .low16⟩ value
  | 32 => writeGPR cpu ⟨register, .low32⟩ value
  | 64 => writeGPR cpu ⟨register, .full64⟩ value
  | _ => cpu

structure DefinedFlags where
  cf : Option Bool := none
  pf : Option Bool := none
  af : Option Bool := none
  zf : Option Bool := none
  sf : Option Bool := none
  of : Option Bool := none

def optionPermits (constraint : Option Bool) (candidate : Bool) : Prop :=
  constraint = none ∨ constraint = some candidate

def FlagsAllowed (constraints : DefinedFlags) (candidate : RFlags) : Prop :=
  optionPermits constraints.cf candidate.cf ∧
  optionPermits constraints.pf candidate.pf ∧
  optionPermits constraints.af candidate.af ∧
  optionPermits constraints.zf candidate.zf ∧
  optionPermits constraints.sf candidate.sf ∧
  optionPermits constraints.of candidate.of

def statusFlags (value : Nat) : DefinedFlags := {
  pf := some (parityEven (wordOfNat value))
  zf := some (value % 256 = 0)
  sf := some (128 ≤ value % 256)
}

inductive DecimalKind where
  | aaa | aad | aam | aas | daa | das
  deriving DecidableEq, Repr

structure DecimalResult where
  ax : IWord
  flags : DefinedFlags

def DecimalCompute (kind : DecimalKind) (before : CPUState) (base : Nat) :
    Option DecimalResult :=
  let al := low8 before.rax
  let ah := high8 before.rax
  match kind with
  | .aaa =>
      let adjust := 9 < lowNibble al || before.rflags.af
      let adjustedAX := adjustedAAA (unsignedValue before.rax 16) adjust
      some { ax := wordOfNat adjustedAX,
             flags := { cf := some adjust, af := some adjust } }
  | .aas =>
      let adjust := 9 < lowNibble al || before.rflags.af
      let adjustedAX := adjustedAAS (unsignedValue before.rax 16) adjust
      some { ax := wordOfNat adjustedAX,
             flags := { cf := some adjust, af := some adjust } }
  | .aad =>
      let result := (base * ah + al) % 256
      some { ax := axValue 0 result, flags := statusFlags result }
  | .aam =>
      if base = 0 then none else
        let result := al % base
        some { ax := axValue (al / base) result, flags := statusFlags result }
  | .daa =>
      let lowAdjust := 9 < lowNibble al || before.rflags.af
      let highAdjust := 153 < al || before.rflags.cf
      let afterLow := if lowAdjust then al + 6 else al
      let result := (afterLow + if highAdjust then 96 else 0) % 256
      let baseFlags := statusFlags result
      some { ax := axValue ah result
             flags := { baseFlags with
               af := some (before.rflags.af || lowAdjust)
               cf := some (before.rflags.cf || highAdjust) } }
  | .das =>
      let lowAdjust := 9 < lowNibble al || before.rflags.af
      let highAdjust := 153 < al || before.rflags.cf
      let afterLow := if lowAdjust then al + 250 else al
      let result := (afterLow + if highAdjust then 160 else 0) % 256
      let baseFlags := statusFlags result
      some { ax := axValue ah result
             flags := { baseFlags with
               af := some (before.rflags.af || lowAdjust)
               cf := some (before.rflags.cf || highAdjust) } }

def ExecuteDecimal (kind : DecimalKind) (base : Nat) (before : CPUState)
    (outcome : Outcome) : Prop :=
  if before.execution.mode = .long64 then outcome = .fault .ud
  else match DecimalCompute kind before base with
  | none => kind = .aam ∧ base = 0 ∧ outcome = .fault .de
  | some result => ∃ flags,
      FlagsAllowed result.flags (applyStatusFlags before.rflags flags) ∧
      outcome = .bodyApplied
        { writeAX before result.ax with rflags := applyStatusFlags before.rflags flags }

/-! CPUID is a query against a fixed processor profile. -/
structure CPUIDRow where
  function : Nat
  subfunction : Nat
  eax : IWord
  ebx : IWord
  ecx : IWord
  edx : IWord

structure ProcessorProfile where
  cpuidSupported : Bool
  cpuidUserDisable : Bool
  rows : List CPUIDRow
  crc32 : Bool
  emulateFP : Bool
  taskSwitched : Bool
  pendingX87Exception : Bool
  rdrand : Bool
  rdseed : Bool
  rdpru : Bool
  rdpid : Bool
  fsgsbase : Bool
  fsgsbaseEnabled : Bool
  monitorx : Bool
  monitorInterruptBreak : Bool
  lwp : Bool
  sse : Bool
  sse2 : Bool
  mmx : Bool
  osfxsr : Bool

def CPUIDRow.Matches (row : CPUIDRow) (function subfunction : Nat) : Prop :=
  row.function = function ∧ row.subfunction = subfunction

def applyCPUIDRow (cpu : CPUState) (row : CPUIDRow) : CPUState :=
  let eax := writeLow cpu GPR.rax.toFin 32 row.eax
  let ebx := writeLow eax GPR.rbx.toFin 32 row.ebx
  let ecx := writeLow ebx GPR.rcx.toFin 32 row.ecx
  writeLow ecx GPR.rdx.toFin 32 row.edx

def ExecuteCPUID (profile : ProcessorProfile) (cpu : CPUState)
    (outcome : Outcome) : Prop :=
  if !profile.cpuidSupported then outcome = .fault .ud
  else if profile.cpuidUserDisable && cpu.execution.cpl.val > 0 then outcome = .fault .gp
  else let function := unsignedValue cpu.rax 32
       let subfunction := unsignedValue cpu.rcx 32
       match profile.rows.find? fun row => row.function == function && row.subfunction == subfunction with
       | none => outcome = .modelingUnavailable "CPUID row absent from processor profile"
       | some row => outcome = .bodyApplied (applyCPUIDRow cpu row)

/-! CRC32 uses the reflected Castagnoli polynomial 82F63B78h. -/
def crc32cBit (value : Nat) : Nat :=
  if value % 2 = 1 then Nat.xor (value / 2) 0x82F63B78 else value / 2

def crc32cByte : Nat -> Nat -> Nat
  | 0, value => value
  | fuel + 1, value => crc32cByte fuel (crc32cBit value)

def crc32cBytes : List Nat -> Nat -> Nat
  | [], crc => crc
  | byte :: rest, crc => crc32cBytes rest (crc32cByte 8 (Nat.xor crc byte))

def sourceBytes (source : IWord) (width : Nat) : List Nat :=
  (List.range (width / 8)).map fun index => (unsignedValue source width / 2 ^ (8 * index)) % 256

def CRC32Result (accumulator source : IWord) (sourceWidth : Nat) : IWord :=
  wordOfNat (crc32cBytes (sourceBytes source sourceWidth) (unsignedValue accumulator 32))

def ExecuteCRC32 (profile : ProcessorProfile) (destination : Fin 16)
    (destinationWidth sourceWidth : Nat) (source : IWord)
    (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.crc32 then outcome = .fault .ud
  else destinationWidth ∈ [32, 64] ∧ sourceWidth ∈ [8, 16, 32, 64] ∧
    ((destinationWidth = 32 ∧ sourceWidth ∈ [8, 16, 32]) ∨
     (destinationWidth = 64 ∧ sourceWidth ∈ [8, 64])) ∧
    outcome = .bodyApplied (writeLow before destination destinationWidth
      (CRC32Result (before.gpr destination) source sourceWidth))

/-! Entropy instructions consume one environment sample.  An invalid RDRAND
sample still carries the hardware-returned but unusable value; RDSEED failure is
constrained to zero by the instruction reference. -/
inductive EntropyKind where | rdrand | rdseed deriving DecidableEq, Repr

structure EntropySample where
  kind : EntropyKind
  width : Nat
  valid : Bool
  value : IWord
  provenance : String

def entropySampleValid (sample : EntropySample) : Prop :=
  sample.width ∈ [16, 32, 64] ∧ sample.provenance ≠ "" ∧
  (sample.kind = .rdseed ∧ !sample.valid -> unsignedValue sample.value sample.width = 0)

def entropyFlags (before : RFlags) (valid : Bool) : RFlags :=
  { before with cf := valid, of := false, sf := false, zf := false
                af := false, pf := false }

def ExecuteEntropy (profile : ProcessorProfile) (kind : EntropyKind)
    (destination : Fin 16) (width : Nat) (sample : Option EntropySample)
    (before : CPUState) (outcome : Outcome) : Prop :=
  let supported := if kind = .rdrand then profile.rdrand else profile.rdseed
  if !supported then outcome = .fault .ud
  else match sample with
  | none => outcome = .modelingUnavailable "entropy sample unavailable"
  | some observed => observed.kind = kind ∧ observed.width = width ∧
      entropySampleValid observed ∧
      outcome = .bodyApplied
        { writeLow before destination width observed.value with
          rflags := entropyFlags before.rflags observed.valid }

/-! Media moves use the canonical vector and x87/MMX alias banks. -/
def zeroExtended128 (value : IWord) (width : Nat) : Bits 128 := fun bit =>
  if h : bit.val < width ∧ bit.val < 64 then value ⟨bit.val, h.2⟩ else false

def writeXMMScalar (cpu : CPUState) (destination : Fin 32)
    (value : IWord) (width : Nat) : CPUState :=
  { cpu with vectors := (writeVectorLow cpu.vectors destination
      (zeroExtended128 value width) (by omega)) }

def writeMMXScalarAllowed (before after : CPUState) (destination : Fin 8)
    (value : IWord) (width : Nat) : Prop :=
  after.gpr = before.gpr ∧ after.vectors = before.vectors ∧
  after.rflags = before.rflags ∧ after.rip = before.rip ∧
  after.x87.status = { before.x87.status with top := ⟨0, by omega⟩ } ∧
  (∀ register, after.x87.tags register = .valid) ∧
  (∀ bit : Fin 80, after.x87.physical destination bit =
    if h : bit.val < width ∧ bit.val < 64 then value ⟨bit.val, h.2⟩
    else if bit.val < 64 then false else true) ∧
  (∀ register, register ≠ destination ->
    after.x87.physical register = before.x87.physical register) ∧
  after.x87.control = before.x87.control ∧
  after.x87.lastInstruction = before.x87.lastInstruction ∧
  after.x87.lastData = before.x87.lastData ∧
  after.x87.lastOpcode = before.x87.lastOpcode ∧
  after.kMask = before.kMask ∧ after.mxcsr = before.mxcsr ∧
  after.segments = before.segments ∧ after.execution = before.execution

def movMaskPD (source : Bits 128) : IWord := fun bit =>
  if bit.val = 0 then source ⟨63, by omega⟩
  else if bit.val = 1 then source ⟨127, by omega⟩ else false

def movMaskPS (source : Bits 128) : IWord := fun bit =>
  if bit.val = 0 then source ⟨31, by omega⟩
  else if bit.val = 1 then source ⟨63, by omega⟩
  else if bit.val = 2 then source ⟨95, by omega⟩
  else if bit.val = 3 then source ⟨127, by omega⟩ else false

def ExecuteMOVDToXMM (profile : ProcessorProfile) (destination : Fin 32)
    (source : IWord) (width : Nat) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.sse2 then outcome = .fault .ud
  else if profile.emulateFP then outcome = .fault .ud
  else if !profile.osfxsr then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if !before.execution.sseEnabled then
    outcome = .modelingUnavailable "SSE execution enablement binding unavailable"
  else if destination.val ≥ (if before.execution.mode = .long64 then 16 else 8) then
    outcome = .fault .ud
  else width ∈ [32, 64] ∧
    outcome = .bodyApplied (writeXMMScalar before destination source width)

def ExecuteMOVDFromXMM (profile : ProcessorProfile) (destination : Fin 16)
    (source : Fin 32) (width : Nat) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.sse2 then outcome = .fault .ud
  else if profile.emulateFP then outcome = .fault .ud
  else if !profile.osfxsr then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if !before.execution.sseEnabled then
    outcome = .modelingUnavailable "SSE execution enablement binding unavailable"
  else if source.val ≥ (if before.execution.mode = .long64 then 16 else 8) then
    outcome = .fault .ud
  else width ∈ [32, 64] ∧
    outcome = .bodyApplied (writeLow before destination width
      (fun bit => before.vectors source ⟨bit.val, by omega⟩))

def ExecuteMOVDToMMX (profile : ProcessorProfile) (destination : Fin 8)
    (source : IWord) (width : Nat) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.mmx || profile.emulateFP then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if profile.pendingX87Exception then outcome = .fault .mf
  else width ∈ [32, 64] ∧ ∃ after,
    writeMMXScalarAllowed before after destination source width ∧
    outcome = .bodyApplied after

def ExecuteMOVDFromMMX (profile : ProcessorProfile) (destination : Fin 16)
    (source : Fin 8) (width : Nat) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.mmx || profile.emulateFP then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if profile.pendingX87Exception then outcome = .fault .mf
  else width ∈ [32, 64] ∧
    outcome = .bodyApplied (writeLow before destination width
      (fun bit => before.x87.mmx source bit))

def ExecuteMOVMSKPD (profile : ProcessorProfile) (destination : Fin 16)
    (source : Fin 32) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.sse2 || profile.emulateFP || !profile.osfxsr then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if !before.execution.sseEnabled then
    outcome = .modelingUnavailable "SSE execution enablement binding unavailable"
  else if source.val ≥ (if before.execution.mode = .long64 then 16 else 8) then
    outcome = .fault .ud
  else outcome = .bodyApplied (writeLow before destination 32
    (movMaskPD (readXMM before.vectors source)))

def ExecuteMOVMSKPS (profile : ProcessorProfile) (destination : Fin 16)
    (source : Fin 32) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.sse || profile.emulateFP || !profile.osfxsr then outcome = .fault .ud
  else if profile.taskSwitched then outcome = .fault .nm
  else if !before.execution.sseEnabled then
    outcome = .modelingUnavailable "SSE execution enablement binding unavailable"
  else if source.val ≥ (if before.execution.mode = .long64 then 16 else 8) then
    outcome = .fault .ud
  else outcome = .bodyApplied (writeLow before destination 32
    (movMaskPS (readXMM before.vectors source)))

/-! FS/GS base instructions operate on the segment-cache bases already owned
by CPUState.  Feature/enable and long-mode gates precede the body effect. -/
inductive BaseRegister where | fs | gs deriving DecidableEq, Repr

def segmentBase (cpu : CPUState) : BaseRegister -> IWord
  | .fs => cpu.segments.fs.cache.base
  | .gs => cpu.segments.gs.cache.base

def writeSegmentBase (cpu : CPUState) (which : BaseRegister) (value : IWord) : CPUState :=
  match which with
  | .fs => { cpu with segments := { cpu.segments with fs :=
      { cpu.segments.fs with cache := { cpu.segments.fs.cache with base := value } } } }
  | .gs => { cpu with segments := { cpu.segments with gs :=
      { cpu.segments.gs with cache := { cpu.segments.gs.cache with base := value } } } }

def FSGSAvailable (profile : ProcessorProfile) (cpu : CPUState) : Bool :=
  profile.fsgsbase && profile.fsgsbaseEnabled && cpu.execution.mode == .long64

def ExecuteReadBase (profile : ProcessorProfile) (which : BaseRegister)
    (destination : Fin 16) (width : Nat) (before : CPUState) (outcome : Outcome) : Prop :=
  if !FSGSAvailable profile before then outcome = .fault .ud
  else if width ∉ [32, 64] then outcome = .modelingUnavailable "invalid base-read width"
  else outcome = .bodyApplied (writeLow before destination width (segmentBase before which))

def ExecuteWriteBase (architecture : ArchitectureProfile) (profile : ProcessorProfile)
    (which : BaseRegister) (source : IWord) (width : Nat)
    (before : CPUState) (outcome : Outcome) : Prop :=
  if !FSGSAvailable profile before then outcome = .fault .ud
  else if width ∉ [32, 64] then outcome = .modelingUnavailable "invalid base-write width"
  else let value := if width = 32 then fun bit => bit.val < 32 && source bit else source
       (canonical value architecture.linearAddressBits ∧
          outcome = .bodyApplied (writeSegmentBase before which value)) ∨
       (¬ canonical value architecture.linearAddressBits ∧ outcome = .fault .gp)

structure ProcessorRegisters where
  tscAux : IWord
  mperf : IWord
  aperf : IWord
  maxRdpruIndex : Nat

def ExecuteRDPID (profile : ProcessorProfile) (registers : ProcessorRegisters)
    (destination : Fin 16) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.rdpid then outcome = .fault .ud
  else let width := if before.execution.mode = .long64 then 64 else 32
       outcome = .bodyApplied (writeLow before destination width registers.tscAux)

def ExecuteRDPRU (profile : ProcessorProfile) (registers : ProcessorRegisters)
    (tsd : Bool) (before : CPUState) (outcome : Outcome) : Prop :=
  if !profile.rdpru || (tsd && before.execution.cpl.val > 0) then outcome = .fault .ud
  else let index := unsignedValue before.rcx 32
       let value := if index = 0 then registers.mperf else if index = 1 then registers.aperf
                    else wordOfNat 0
       let low := writeLow before GPR.rax.toFin 32 value
       let high := writeLow low GPR.rdx.toFin 32 (wordOfNat (unsignedValue value 64 / 2^32))
       outcome = .bodyApplied high

inductive WakeCause where
  | matchingStore | timerExpired | interrupt | nmi | smi | init | reset | farTransfer
  deriving DecidableEq, Repr

structure MonitorState where
  armed : Bool
  linearBase : IWord
  byteCount : Nat
  pending : Bool

def ArmMonitor (profile : ProcessorProfile) (linear : IWord) (byteCount : Nat)
    (ecx : Nat) (before : MonitorState) : MonitorState ⊕ Fault :=
  if !profile.monitorx then .inr .ud
  else if ecx ≠ 0 then .inr .gp
  else .inl { armed := true, linearBase := linear, byteCount,
              pending := true }

structure WaitObservation where
  cause : WakeCause
  elapsedP0Clocks : Nat
  matchingStoreObserved : Bool

def WaitAllowed (profile : ProcessorProfile) (monitor : MonitorState)
    (eax ecx ebx : Nat) (observation : WaitObservation) : Prop :=
  profile.monitorx ∧ ecx / 4 = 0 ∧
  (ecx % 2 = 0 ∨ profile.monitorInterruptBreak) ∧
  (ecx % 4 < 2 -> observation.cause ≠ .timerExpired) ∧
  (ecx % 4 ≥ 2 -> ebx = 0 ∨ observation.elapsedP0Clocks ≤ ebx) ∧
  (observation.cause = .matchingStore -> monitor.armed ∧ observation.matchingStoreObserved)

inductive MonitorOutcome where
  | armed (cpu : CPUState) (monitor : MonitorState)
  | woke (cpu : CPUState) (monitor : MonitorState) (observation : WaitObservation)
  | fault (kind : Fault)
  | modelingUnavailable (reason : String)

def ExecuteMONITORX (profile : ProcessorProfile) (linear : IWord) (byteCount : Nat)
    (addressReadSucceeded : Bool) (beforeCPU : CPUState) (before : MonitorState)
    (outcome : MonitorOutcome) : Prop :=
  if !profile.monitorx then outcome = .fault .ud
  else if unsignedValue beforeCPU.rcx 32 ≠ 0 then outcome = .fault .gp
  else if !addressReadSucceeded then
    outcome = .modelingUnavailable "MONITORX one-byte address resolution required"
  else outcome = .armed beforeCPU {
    armed := true, linearBase := linear, byteCount := byteCount, pending := true }

def ExecuteMWAITX (profile : ProcessorProfile) (beforeCPU : CPUState)
    (before : MonitorState) (observation : Option WaitObservation)
    (outcome : MonitorOutcome) : Prop :=
  if !profile.monitorx then outcome = .fault .ud
  else if unsignedValue beforeCPU.rcx 32 / 4 ≠ 0 then outcome = .fault .gp
  else match observation with
  | none => outcome = .modelingUnavailable "MWAITX wake observation unavailable"
  | some observed =>
      WaitAllowed profile before (unsignedValue beforeCPU.rax 32)
        (unsignedValue beforeCPU.rcx 32) (unsignedValue beforeCPU.rbx 32) observed ∧
      outcome = .woke beforeCPU { before with pending := false } observed

/-! LWP is retained as an explicit state/environment protocol.  It is not
classified complete: validation, old-control-block flush, ring-buffer write,
and counter transitions must each be witnessed by an environment operation. -/
inductive LWPMode where | continuous | synchronized deriving DecidableEq, Repr

structure LWPState where
  enabled : Bool
  controlBlockLinear : IWord
  ringHead : Nat
  ringTail : Nat
  ringBytes : Nat
  missedEvents : Nat
  valueCounter : Int
  valueInterval : Nat
  valueEventEnabled : Bool
  mode : LWPMode

inductive LWPOperation where
  | flushOld | validateNew | disable | insert (eventId : Nat)
  deriving DecidableEq, Repr

structure LWPEnvironmentStep where
  operation : LWPOperation
  before : LWPState
  after : LWPState
  memoryEffects : List String
  resultFault : Option Fault

def LWPEnvironmentStep.Valid (step : LWPEnvironmentStep) : Prop :=
  step.memoryEffects.all (· ≠ "") ∧
  match step.operation with
  | .disable => !step.after.enabled ∧ step.after.controlBlockLinear = wordOfNat 0
  | .insert eventId => eventId ∈ [1, 255] ∧ step.before.enabled
  | .flushOld => step.before.enabled
  | .validateNew => step.after.enabled

inductive LWPOutcome where
  | bodyApplied (cpu : CPUState) (state : LWPState) (memoryEffects : List String)
  | fault (kind : Fault) (state : LWPState) (memoryEffects : List String)
  | modelingUnavailable (reason : String)

def ExecuteLLWPCB (profile : ProcessorProfile) (protectedMode : Bool)
    (requestedAddress : IWord) (beforeCPU : CPUState) (before : LWPState)
    (steps : List LWPEnvironmentStep) (outcome : LWPOutcome) : Prop :=
  if !profile.lwp || !protectedMode then outcome = .fault .ud before []
  else if unsignedValue requestedAddress 64 = 0 then
    ∃ step ∈ steps, step.operation = .disable ∧ step.before = before ∧ step.Valid ∧
      outcome = .bodyApplied beforeCPU step.after step.memoryEffects
  else ∃ step ∈ steps, step.operation = .validateNew ∧ step.before = before ∧
      step.after.controlBlockLinear = requestedAddress ∧ step.Valid ∧
      match step.resultFault with
      | some fault => outcome = .fault fault step.after step.memoryEffects
      | none => outcome = .bodyApplied beforeCPU step.after step.memoryEffects

def ExecuteLWPINS (profile : ProcessorProfile) (protectedMode : Bool)
    (beforeCPU : CPUState) (before : LWPState) (steps : List LWPEnvironmentStep)
    (outcome : LWPOutcome) : Prop :=
  if !profile.lwp || !protectedMode then outcome = .fault .ud before []
  else if !before.enabled then
    outcome = .bodyApplied { beforeCPU with rflags := { beforeCPU.rflags with cf := false } }
      before []
  else ∃ step ∈ steps, step.operation = .insert 255 ∧ step.before = before ∧ step.Valid ∧
    outcome = match step.resultFault with
      | some fault => .fault fault step.after step.memoryEffects
      | none => .bodyApplied
          { beforeCPU with rflags := { beforeCPU.rflags with
              cf := step.after.mode = .synchronized ∧ step.after.ringHead = before.ringHead } }
          step.after step.memoryEffects

def ExecuteLWPVAL (profile : ProcessorProfile) (protectedMode : Bool)
    (beforeCPU : CPUState) (before : LWPState) (steps : List LWPEnvironmentStep)
    (outcome : LWPOutcome) : Prop :=
  if !profile.lwp || !protectedMode then outcome = .fault .ud before []
  else if !before.enabled || !before.valueEventEnabled then
    outcome = .bodyApplied beforeCPU before []
  else if 0 ≤ before.valueCounter - 1 then
    outcome = .bodyApplied beforeCPU { before with valueCounter := before.valueCounter - 1 } []
  else ∃ step ∈ steps, step.operation = .insert 1 ∧ step.before = before ∧ step.Valid ∧
    outcome = match step.resultFault with
      | some fault => .fault fault step.after step.memoryEffects
      | none => .bodyApplied beforeCPU step.after step.memoryEffects

def ExecuteSLWPCB (profile : ProcessorProfile) (protectedMode : Bool)
    (destination : Fin 16) (width : Nat) (dsBase : IWord)
    (beforeCPU : CPUState) (before : LWPState) (steps : List LWPEnvironmentStep)
    (outcome : LWPOutcome) : Prop :=
  if !profile.lwp || !protectedMode then outcome = .fault .ud before []
  else if !before.enabled then
    outcome = .bodyApplied (writeLow beforeCPU destination width (wordOfNat 0)) before []
  else ∃ step ∈ steps, step.operation = .flushOld ∧ step.before = before ∧ step.Valid ∧
    let effective := wordOfNat ((unsignedValue before.controlBlockLinear 64 + 2^64 -
      unsignedValue dsBase 64) % 2^64)
    outcome = match step.resultFault with
      | some fault => .fault fault step.after step.memoryEffects
      | none => .bodyApplied (writeLow beforeCPU destination width effective)
          step.after step.memoryEffects

def ExecuteNOP (before : CPUState) (outcome : Outcome) : Prop :=
  outcome = .bodyApplied before

def ExecutePAUSE (before : CPUState) (pauseRecognized : Bool)
    (outcome : Outcome) : Prop :=
  pauseRecognized ∧ outcome = .bodyApplied before

theorem decimal_long_mode_ud (kind : DecimalKind) (base : Nat) (cpu : CPUState)
    (mode : cpu.execution.mode = .long64) :
    ExecuteDecimal kind base cpu (.fault .ud) := by
  simp [ExecuteDecimal, mode]

theorem rdseed_failure_is_zero (sample : EntropySample)
    (kind : sample.kind = .rdseed) (invalid : sample.valid = false)
    (valid : entropySampleValid sample) :
    unsignedValue sample.value sample.width = 0 := by
  exact valid.2.2 ⟨kind, by simp [invalid]⟩

theorem nop_frames_cpu (cpu : CPUState) : ExecuteNOP cpu (.bodyApplied cpu) := rfl

end AMD64.External
