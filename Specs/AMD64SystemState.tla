----------------------- MODULE AMD64SystemState -----------------------
EXTENDS Integers, FiniteSets, AMD64ArchitecturalState

\* Raw system controls and typed instruction-entry guards.
\* Authority: AMD APM Volume 2 rev. 3.45 PDF pages 105-117, 123,
\* 408-409, 420-421, 539 and 555.

DefinedXFeatures == {0, 1, 2, 5, 6, 7, 9, 62}
MediaClasses == {"wait", "x87", "mmx", "legacySSE", "avx", "avx512"}
GuardResults == {"allowed", "UD", "NM", "MF", "GP", "modelingUnavailable"}

\* @typeAlias: systemCR0 = {pe: Bool, mp: Bool, em: Bool, ts: Bool,
\*   wp: Bool, am: Bool};
\* @typeAlias: systemCR4 = {vme: Bool, tsd: Bool, osfxsr: Bool,
\*   osxmmexcpt: Bool, fsgsbase: Bool, osxsave: Bool};
\* @typeAlias: systemXCR0 = {enabled: Set(Int)};
\* @typeAlias: systemXFeatureProfile = {supported: Set(Int)};
\* @typeAlias: systemFeatureProfile = {x87: Bool, mmx: Bool, sse: Bool,
\*   avx: Bool, avx512: Bool, xsave: Bool, fsgsbase: Bool,
\*   rdpru: Bool, lwp: Bool};
\* @typeAlias: systemMSR = {hwcrCpuidUserDisable: Bool,
\*   tscAux: $amd64Bits, mperf: $amd64Bits, aperf: $amd64Bits,
\*   lwpCfg: $amd64Bits, lwpCbAddress: $amd64Bits};
\* @typeAlias: amd64SystemState = {cr0: $systemCR0, cr4: $systemCR4,
\*   xcr0: $systemXCR0, msr: $systemMSR, inSMM: Bool,
\*   x87ExceptionPending: Bool};

\* @type: ($systemFeatureProfile) => Bool;
FeatureProfileWellFormed(profile) ==
  /\ (profile.mmx => profile.x87)
  /\ (profile.avx => profile.sse /\ profile.xsave)
  /\ (profile.avx512 => profile.avx)

\* XCR0[0] must remain set. YMM requires SSE. AVX-512 state bits 5:7
\* are all-or-none and require YMM/SSE. MPK and LWP are independent defined
\* states, but every enabled state must also be enumerated as supported.
\* @type: ($systemXFeatureProfile, $systemXCR0) => Bool;
XCR0WellFormed(profile, value) ==
  /\ value.enabled \subseteq profile.supported
  /\ value.enabled \subseteq DefinedXFeatures
  /\ 0 \in value.enabled
  /\ (2 \in value.enabled => 1 \in value.enabled)
  /\ (({5, 6, 7} \cap value.enabled # {}) =>
        /\ {5, 6, 7} \subseteq value.enabled
        /\ {1, 2} \subseteq value.enabled)

\* @type: $amd64SystemState => Bool;
AVXStateEnabled(state) ==
  /\ state.cr4.osfxsr /\ state.cr4.osxsave
  /\ {0, 1, 2} \subseteq state.xcr0.enabled

\* @type: $amd64SystemState => Bool;
AVX512StateEnabled(state) ==
  AVXStateEnabled(state) /\ {5, 6, 7} \subseteq state.xcr0.enabled

\* WAIT ignores EM and raises #NM exactly when MP and TS are both set.
\* @type: ($systemFeatureProfile, $amd64SystemState, Str) => Str;
MediaGuard(profile, state, mediaClass) ==
  CASE mediaClass = "wait" ->
         IF state.cr0.mp /\ state.cr0.ts THEN "NM" ELSE "allowed"
    [] mediaClass = "x87" ->
         IF ~profile.x87 THEN "UD"
         ELSE IF state.cr0.em \/ state.cr0.ts THEN "NM" ELSE "allowed"
    [] mediaClass = "mmx" ->
         IF ~profile.mmx \/ state.cr0.em THEN "UD"
         ELSE IF state.cr0.ts THEN "NM"
         ELSE IF state.x87ExceptionPending THEN "MF" ELSE "allowed"
    [] mediaClass = "legacySSE" ->
         IF ~profile.sse \/ state.cr0.em \/ ~state.cr4.osfxsr THEN "UD"
         ELSE IF state.cr0.ts THEN "NM" ELSE "allowed"
    [] mediaClass = "avx" ->
         IF ~profile.avx \/ state.cr0.em \/ ~AVXStateEnabled(state) THEN "UD"
         ELSE IF state.cr0.ts THEN "NM" ELSE "allowed"
    [] OTHER ->
         IF ~profile.avx512 \/ state.cr0.em \/ ~AVX512StateEnabled(state) THEN "UD"
         ELSE IF state.cr0.ts THEN "NM" ELSE "allowed"

\* @type: ($amd64SystemState, Bool) => Str;
SIMDExceptionGuard(state, unmasked) ==
  IF unmasked /\ ~state.cr4.osxmmexcpt THEN "UD" ELSE "allowed"

\* @type: ($systemFeatureProfile, $amd64SystemState,
\*   $amd64EnabledFeatures) => Bool;
ContextProjection(profile, state, features) ==
  /\ features.x87Enabled = profile.x87
  /\ features.sseEnabled = (profile.sse /\ state.cr4.osfxsr)
  /\ features.avxEnabled = (profile.avx /\ AVXStateEnabled(state))
  /\ features.avx512Enabled = (profile.avx512 /\ AVX512StateEnabled(state))

\* @type: ($systemFeatureProfile, $amd64SystemState, Str) => Str;
FSGSBaseGuard(profile, state, mode) ==
  IF mode # "long64" \/ ~profile.fsgsbase \/ ~state.cr4.fsgsbase
  THEN "UD" ELSE "allowed"

\* @type: ($systemFeatureProfile, $amd64SystemState, Int) => Str;
RDPRUGuard(profile, state, cpl) ==
  IF ~profile.rdpru \/ (state.cr4.tsd /\ cpl > 0) THEN "UD" ELSE "allowed"

\* @type: ($systemFeatureProfile, $systemXFeatureProfile,
\*   $amd64SystemState, Str) => Str;
LWPGuard(profile, xfeatures, state, mode) ==
  IF ~profile.lwp \/ ~profile.xsave \/ ~state.cr4.osxsave THEN "UD"
  ELSE IF ~XCR0WellFormed(xfeatures, state.xcr0) THEN "GP"
  ELSE IF 62 \notin state.xcr0.enabled THEN "UD"
  ELSE IF mode \in {"real", "virtual8086"} THEN "UD"
  ELSE "allowed"

=======================================================================
