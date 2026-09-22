import AMD64.ArchitecturalState
import Std

/-!
Raw system-control state and source-grounded execution guards.

Authority: AMD APM Volume 2 revision 3.45, PDF pages 105-117 and 123
(CR0/CR4), 408-409 (SSE enablement), and 420-421 (XCR0); LWP XCR0 bit 62
is also specified on PDF pages 539 and 555.  Capability support, OS enablement,
task-switched state, and pending exceptions remain distinct inputs.
-/

namespace AMD64.SystemState

open AMD64.Arch

structure CR0 where
  pe : Bool
  mp : Bool
  em : Bool
  ts : Bool
  wp : Bool
  am : Bool
  deriving DecidableEq, Repr

structure CR4 where
  vme : Bool
  tsd : Bool
  osfxsr : Bool
  osxmmexcpt : Bool
  fsgsbase : Bool
  osxsave : Bool
  deriving DecidableEq, Repr

structure XCR0 where
  enabled : Fin 64 -> Bool

def XCR0.x87 (value : XCR0) : Bool := value.enabled ⟨0, by omega⟩
def XCR0.sse (value : XCR0) : Bool := value.enabled ⟨1, by omega⟩
def XCR0.ymm (value : XCR0) : Bool := value.enabled ⟨2, by omega⟩
def XCR0.opmask (value : XCR0) : Bool := value.enabled ⟨5, by omega⟩
def XCR0.zmmHigh256 (value : XCR0) : Bool := value.enabled ⟨6, by omega⟩
def XCR0.high16Zmm (value : XCR0) : Bool := value.enabled ⟨7, by omega⟩
def XCR0.mpk (value : XCR0) : Bool := value.enabled ⟨9, by omega⟩
def XCR0.lwp (value : XCR0) : Bool := value.enabled ⟨62, by omega⟩

def xfeatureDefined (bit : Fin 64) : Bool :=
  bit.val ∈ [0, 1, 2, 5, 6, 7, 9, 62]

structure XFeatureProfile where
  supported : Fin 64 -> Bool

def XCR0.validB (profile : XFeatureProfile) (value : XCR0) : Bool :=
  (List.range 64).all (fun index =>
    let bit := Fin.ofNat 64 index
    !value.enabled bit || profile.supported bit) &&
  (List.range 64).all (fun index =>
    let bit := Fin.ofNat 64 index
    xfeatureDefined bit || !value.enabled bit) &&
  value.x87 &&
  (!value.ymm || value.sse) &&
  (!(value.opmask || value.zmmHigh256 || value.high16Zmm) ||
    (value.opmask && value.zmmHigh256 && value.high16Zmm && value.ymm && value.sse))

def XCR0.Valid (profile : XFeatureProfile) (value : XCR0) : Prop :=
  value.validB profile = true

structure FeatureProfile where
  x87 : Bool
  mmx : Bool
  sse : Bool
  avx : Bool
  avx512 : Bool
  xsave : Bool
  fsgsbase : Bool
  rdpru : Bool
  lwp : Bool
  deriving DecidableEq, Repr

def FeatureProfile.Valid (profile : FeatureProfile) : Prop :=
  (profile.mmx -> profile.x87) ∧
  (profile.avx -> profile.sse ∧ profile.xsave) ∧
  (profile.avx512 -> profile.avx)

structure MSRState where
  hwcrCpuidUserDisable : Bool
  tscAux : Bits 64
  mperf : Bits 64
  aperf : Bits 64
  lwpCfg : Bits 64
  lwpCbAddress : Bits 64

structure State where
  cr0 : CR0
  cr4 : CR4
  xcr0 : XCR0
  msr : MSRState
  inSMM : Bool
  x87ExceptionPending : Bool

inductive GuardResult where
  | allowed
  | ud
  | nm
  | mf
  | gp
  | modelingUnavailable
  deriving DecidableEq, Repr

inductive MediaClass where
  | wait
  | x87
  | mmx
  | legacySSE
  | avx
  | avx512
  deriving DecidableEq, Repr

def avxStateEnabled (state : State) : Bool :=
  state.cr4.osfxsr && state.cr4.osxsave &&
  state.xcr0.x87 && state.xcr0.sse && state.xcr0.ymm

def avx512StateEnabled (state : State) : Bool :=
  avxStateEnabled state && state.xcr0.opmask &&
  state.xcr0.zmmHigh256 && state.xcr0.high16Zmm

/-- Instruction-entry guard. WAIT deliberately ignores CR0.EM. -/
def mediaGuard (profile : FeatureProfile) (state : State) : MediaClass -> GuardResult
  | .wait => if state.cr0.mp && state.cr0.ts then .nm else .allowed
  | .x87 =>
      if !profile.x87 then .ud
      else if state.cr0.em || state.cr0.ts then .nm
      else .allowed
  | .mmx =>
      if !profile.mmx || state.cr0.em then .ud
      else if state.cr0.ts then .nm
      else if state.x87ExceptionPending then .mf
      else .allowed
  | .legacySSE =>
      if !profile.sse || state.cr0.em || !state.cr4.osfxsr then .ud
      else if state.cr0.ts then .nm
      else .allowed
  | .avx =>
      if !profile.avx || state.cr0.em || !avxStateEnabled state then .ud
      else if state.cr0.ts then .nm
      else .allowed
  | .avx512 =>
      if !profile.avx512 || state.cr0.em || !avx512StateEnabled state then .ud
      else if state.cr0.ts then .nm
      else .allowed

def simdExceptionGuard (state : State) (unmasked : Bool) : GuardResult :=
  if unmasked && !state.cr4.osxmmexcpt then .ud else .allowed

def contextProjection (profile : FeatureProfile) (state : State)
    (context : ExecutionContext) : Prop :=
  context.x87Enabled = profile.x87 ∧
  context.sseEnabled = (profile.sse && state.cr4.osfxsr) ∧
  context.avxEnabled = (profile.avx && avxStateEnabled state) ∧
  context.avx512Enabled = (profile.avx512 && avx512StateEnabled state)

def fsgsbaseGuard (profile : FeatureProfile) (state : State)
    (mode : OperatingMode) : GuardResult :=
  if mode != .long64 || !profile.fsgsbase || !state.cr4.fsgsbase then .ud
  else .allowed

def rdpruGuard (profile : FeatureProfile) (state : State) (cpl : Fin 4) : GuardResult :=
  if !profile.rdpru || (state.cr4.tsd && cpl.val > 0) then .ud else .allowed

def lwpGuard (profile : FeatureProfile) (xfeatures : XFeatureProfile)
    (state : State) (mode : OperatingMode) : GuardResult :=
  if !profile.lwp || !profile.xsave then .ud
  else if !state.cr4.osxsave then .ud
  else if !state.xcr0.validB xfeatures then .gp
  else if !state.xcr0.lwp then .ud
  else if mode = .real || mode = .virtual8086 then .ud
  else .allowed

theorem wait_ignores_em (profile : FeatureProfile) (state : State) :
    mediaGuard profile { state with cr0 := { state.cr0 with em := true } } .wait =
    mediaGuard profile { state with cr0 := { state.cr0 with em := false } } .wait := by
  simp [mediaGuard]

theorem wait_nm_iff_mp_ts (profile : FeatureProfile) (state : State) :
    mediaGuard profile state .wait = .nm ↔
      state.cr0.mp = true ∧ state.cr0.ts = true := by
  simp [mediaGuard, Bool.and_eq_true]

theorem legacy_sse_osfxsr_zero_ud (profile : FeatureProfile) (state : State)
    (disabled : state.cr4.osfxsr = false) :
    mediaGuard profile state .legacySSE = .ud := by
  simp [mediaGuard, disabled]

end AMD64.SystemState
