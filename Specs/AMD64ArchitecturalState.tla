------------------- MODULE AMD64ArchitecturalState -------------------
EXTENDS Integers, FiniteSets, AMD64RegisterViews

\* Authoritative CPU-state vocabulary for the AMD64 expansion.
\*
\* Authority: AMD APM Volume 1, 24592 revision 3.25 (May 2026),
\* sections 1.2, 2.1.2, 2.5, 3.1, 4.2, 4.13.1, 4.13.3, 5.4.1,
\* and 6.2. Required effective segment context is further specified by Volume 2.
\*
\* This module preserves application-visible CPU storage, profile capabilities,
\* execution mode, CPL, and effective segment caches. Memory bytes, paging,
\* control registers, I/O permissions, and event delivery are owned by the
\* memory/protection layer and are not represented by an opaque substitute.
\*
\* ArchitectureProfile, CPUState, and AnalysisKnowledge are distinct domains.
\* Only the first two are defined here. Unknown capture data must be represented
\* by the analysis layer; it is never encoded as a special architectural bit.

Modes == {"real", "protected", "virtual8086", "compatibility", "long64"}

\* All bit-vector positions are one-based, matching AMD64RegisterViews.
\* @typeAlias: amd64Bits = Int -> Bool;
\* @typeAlias: amd64Capabilities = {longMode: Bool, x87: Bool, mmx: Bool,
\*   sse: Bool, avx: Bool, avx512: Bool, mxcsrMisalignedMask: Bool};
\* @typeAlias: amd64Profile = {capabilities: $amd64Capabilities,
\*   physicalAddressBits: Int, linearAddressBits: Int};
\* @typeAlias: amd64EnabledFeatures = {x87Enabled: Bool, sseEnabled: Bool,
\*   avxEnabled: Bool, avx512Enabled: Bool};
\* @typeAlias: amd64Context = {mode: Str, cpl: Int,
\*   features: $amd64EnabledFeatures};
\* @typeAlias: amd64Segment = {selector: $amd64Bits, base: $amd64Bits,
\*   limit: $amd64Bits, present: Bool, dpl: Int, readable: Bool,
\*   writable: Bool, executable: Bool, conforming: Bool, expandDown: Bool, defaultBig: Bool,
\*   longMode: Bool, unusable: Bool};
\* @typeAlias: amd64Segments = {cs: $amd64Segment, ss: $amd64Segment,
\*   ds: $amd64Segment, es: $amd64Segment, fs: $amd64Segment,
\*   gs: $amd64Segment};
\* @typeAlias: amd64RFlags = {cf: Bool, fixed1: Bool, pf: Bool,
\*   reserved3: Bool, af: Bool, reserved5: Bool, zf: Bool, sf: Bool,
\*   tf: Bool, interruptEnable: Bool, df: Bool, of: Bool, iopl: $amd64Bits,
\*   nestedTask: Bool, reserved15: Bool, resume: Bool, virtual8086: Bool,
\*   ac: Bool, virtualInterrupt: Bool, virtualInterruptPending: Bool,
\*   id: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: amd64X87Status = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   stackFault: Bool, errorSummary: Bool, c0: Bool, c1: Bool, c2: Bool,
\*   top: Int, c3: Bool, busy: Bool};
\* @typeAlias: amd64X87Control = {invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, reserved6: Bool, reserved7: Bool,
\*   precisionControl: Str, roundingControl: Str, infinityControl: Bool,
\*   reservedHigh: $amd64Bits};
\* @typeAlias: amd64X87Pointer = {kind: Str, selector: $amd64Bits,
\*   offset64: $amd64Bits, offset32: $amd64Bits, linear32: $amd64Bits};
\* @typeAlias: amd64X87 = {physical: Int -> $amd64Bits, tags: Int -> Str,
\*   status: $amd64X87Status, control: $amd64X87Control,
\*   lastInstruction: $amd64X87Pointer, lastData: $amd64X87Pointer,
\*   lastOpcode: $amd64Bits};
\* @typeAlias: amd64MXCSR = {invalid: Bool, denormal: Bool,
\*   zeroDivide: Bool, overflow: Bool, underflow: Bool, precision: Bool,
\*   denormalsAreZero: Bool, invalidMask: Bool, denormalMask: Bool,
\*   zeroDivideMask: Bool, overflowMask: Bool, underflowMask: Bool,
\*   precisionMask: Bool, roundingControl: Str, flushToZero: Bool,
\*   reserved16: Bool, misalignedMask: Bool, reservedHigh: $amd64Bits};
\* @typeAlias: amd64CPUState = {gpr: Int -> $amd64Bits, rip: $amd64Bits,
\*   rflags: $amd64RFlags, segments: $amd64Segments, x87: $amd64X87,
\*   vectors: Int -> $amd64Bits, kMask: Int -> $amd64Bits,
\*   mxcsr: $amd64MXCSR, execution: $amd64Context};

\* @type: Int => Set(Int -> Bool);
BitVector(width) == [1..width -> BOOLEAN]

\* @type: (Int, (Int -> Bool)) => (Int -> Bool);
LowBits(width, value) == [bit \in 1..width |-> value[bit]]

\* ArchitectureProfile records state-bank implementation facts, not mutable CPU
\* values and not the full CPUID/form-feature universe of Volume 3. The form
\* layer composes its own requirements with these bank capabilities.
\* @type: $amd64Capabilities => Bool;
CapabilitiesWellFormed(capabilities) ==
  /\ (capabilities.avx512 => capabilities.avx)
  /\ (capabilities.avx => capabilities.sse)
  /\ (capabilities.mmx => capabilities.x87)

\* @type: $amd64Profile => Bool;
ProfileWellFormed(profile) ==
  /\ CapabilitiesWellFormed(profile.capabilities)
  /\ profile.physicalAddressBits \in 32..64
  /\ profile.linearAddressBits \in 32..64

\* @type: ($amd64Profile, Str) => Bool;
ModeSupported(profile, mode) ==
  mode \in Modes /\ (mode \in {"compatibility", "long64"} => profile.capabilities.longMode)

GPRWidths == {8, 16, 32, 64}
GPRNames == {"rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
             "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"}
\* Canonical identity order shared by explicit and implicit operands.
\* @type: Str => Int;
GPRIndex(name) ==
  CASE name = "rax" -> 0 [] name = "rcx" -> 1
    [] name = "rdx" -> 2 [] name = "rbx" -> 3
    [] name = "rsp" -> 4 [] name = "rbp" -> 5
    [] name = "rsi" -> 6 [] name = "rdi" -> 7
    [] name = "r8" -> 8 [] name = "r9" -> 9
    [] name = "r10" -> 10 [] name = "r11" -> 11
    [] name = "r12" -> 12 [] name = "r13" -> 13
    [] name = "r14" -> 14 [] OTHER -> 15
\* @type: ($amd64CPUState, Str) => (Int -> Bool);
ReadNamedGPR(state, name) == state.gpr[GPRIndex(name)]
RAX(state) == ReadNamedGPR(state, "rax")
RCX(state) == ReadNamedGPR(state, "rcx")
RDX(state) == ReadNamedGPR(state, "rdx")
RBX(state) == ReadNamedGPR(state, "rbx")
RSP(state) == ReadNamedGPR(state, "rsp")
RBP(state) == ReadNamedGPR(state, "rbp")
RSI(state) == ReadNamedGPR(state, "rsi")
RDI(state) == ReadNamedGPR(state, "rdi")
R8(state) == ReadNamedGPR(state, "r8")
R9(state) == ReadNamedGPR(state, "r9")
R10(state) == ReadNamedGPR(state, "r10")
R11(state) == ReadNamedGPR(state, "r11")
R12(state) == ReadNamedGPR(state, "r12")
R13(state) == ReadNamedGPR(state, "r13")
R14(state) == ReadNamedGPR(state, "r14")
R15(state) == ReadNamedGPR(state, "r15")
\* @type: ($amd64Context, Int) => Bool;
GPRRegisterAvailable(context, register) ==
  register \in 0..15 /\ (register < 8 \/ context.mode = "long64")
\* @type: ($amd64Context, Int) => Bool;
GPRWidthAvailable(context, width) ==
  width \in GPRWidths /\ (width = 64 => context.mode = "long64")
\* Default CS width only. Individual control transfers can override it.
\* @type: ($amd64Segments, Str) => Int;
DefaultInstructionPointerWidth(segments, mode) ==
  IF mode = "long64" THEN 64
  ELSE IF mode \in {"protected", "compatibility"} /\ segments.cs.defaultBig
       THEN 32 ELSE 16

\* The selector is exact 16-bit storage. RPL, TI and index are derived views.
\* @type: (Int -> Bool) => (Int -> Bool);
SelectorRPL(selector) == LowBits(2, selector)
\* @type: (Int -> Bool) => Bool;
SelectorTI(selector) == selector[3]
\* @type: (Int -> Bool) => (Int -> Bool);
SelectorIndex(selector) == [bit \in 1..13 |-> selector[bit + 3]]

\* @type: $amd64Segment => Bool;
SegmentRegisterWellFormed(segment) ==
  /\ segment.selector \in BitVector(16)
  /\ segment.base \in BitVector(64)
  /\ segment.limit \in BitVector(32)
  /\ segment.dpl \in 0..3
  /\ (segment.conforming => segment.executable)

SegmentNames == {"cs", "ss", "ds", "es", "fs", "gs"}

\* @type: $amd64Segments => Bool;
SegmentContextWellFormed(segments) ==
  /\ SegmentRegisterWellFormed(segments.cs)
  /\ SegmentRegisterWellFormed(segments.ss)
  /\ SegmentRegisterWellFormed(segments.ds)
  /\ SegmentRegisterWellFormed(segments.es)
  /\ SegmentRegisterWellFormed(segments.fs)
  /\ SegmentRegisterWellFormed(segments.gs)

\* @type: ($amd64Segments, Str) => Int;
DefaultAddressWidth(segments, mode) ==
  IF mode = "long64" THEN 64
  ELSE IF mode \in {"protected", "compatibility"} /\ segments.cs.defaultBig
       THEN 32 ELSE 16

RFlagsFields == {
  "cf", "fixed1", "pf", "reserved3", "af", "reserved5", "zf", "sf",
  "tf", "interruptEnable", "df", "of", "iopl", "nestedTask",
  "reserved15", "resume", "virtual8086", "ac", "virtualInterrupt",
  "virtualInterruptPending", "id", "reservedHigh"}

\* @type: $amd64RFlags => Bool;
RFlagsWellFormed(flags) ==
  /\ flags.iopl \in BitVector(2)
  /\ flags.reservedHigh \in BitVector(42)
  /\ flags.fixed1
  /\ ~flags.reserved3
  /\ ~flags.reserved5
  /\ ~flags.reserved15
  /\ \A bit \in 1..42 : ~flags.reservedHigh[bit]

X87Tags == {"valid", "zero", "special", "empty"}
X87Precisions == {"bits24", "reserved", "bits53", "bits64"}
RoundingModes == {"nearest", "down", "up", "towardZero"}

X87StatusFields == {
  "invalid", "denormal", "zeroDivide", "overflow", "underflow",
  "precision", "stackFault", "errorSummary", "c0", "c1", "c2", "top",
  "c3", "busy"}

\* @type: $amd64X87Status => Bool;
X87StatusWellFormed(status) ==
  status.top \in 0..7

X87ControlFields == {
  "invalidMask", "denormalMask", "zeroDivideMask", "overflowMask",
  "underflowMask", "precisionMask", "reserved6", "reserved7", "precisionControl",
  "roundingControl", "infinityControl", "reservedHigh"}

\* @type: $amd64X87Control => Bool;
X87ControlWellFormed(control) ==
  /\ control.precisionControl \in X87Precisions \ {"reserved"}
  /\ control.roundingControl \in RoundingModes
  /\ control.reservedHigh \in BitVector(3)

\* FINIT/FNINIT reset image 037Fh: bits 0..6 and 8..9 are one.
X87ControlInit == [
  invalidMask |-> TRUE, denormalMask |-> TRUE, zeroDivideMask |-> TRUE,
  overflowMask |-> TRUE, underflowMask |-> TRUE, precisionMask |-> TRUE,
  reserved6 |-> TRUE, reserved7 |-> FALSE, precisionControl |-> "bits64",
  roundingControl |-> "nearest", infinityControl |-> FALSE,
  reservedHigh |-> [bit \in 1..3 |-> FALSE]]

\* One common-shape record represents the three mode-dependent pointer images.
\* Unselected payload fields remain typed but have no semantic effect.
X87PointerKinds == {"offset64", "selectorOffset", "linear"}

\* @type: $amd64X87Pointer => Bool;
X87PointerWellFormed(pointer) ==
  /\ pointer.kind \in X87PointerKinds
  /\ pointer.selector \in BitVector(16)
  /\ pointer.offset64 \in BitVector(64)
  /\ pointer.offset32 \in BitVector(32)
  /\ pointer.linear32 \in BitVector(32)

X87StateFields == {
  "physical", "tags", "status", "control", "lastInstruction", "lastData",
  "lastOpcode"}

\* @type: $amd64X87 => Bool;
X87StateWellFormed(x87) ==
  /\ x87.physical \in [0..7 -> BitVector(80)]
  /\ x87.tags \in [0..7 -> X87Tags]
  /\ X87StatusWellFormed(x87.status)
  /\ X87ControlWellFormed(x87.control)
  /\ X87PointerWellFormed(x87.lastInstruction)
  /\ X87PointerWellFormed(x87.lastData)
  /\ x87.lastOpcode \in BitVector(11)

\* ST(i) maps through TOP onto physical storage. MMX aliases physical low bits.
\* @type: ($amd64X87, Int) => (Int -> Bool);
ReadST(x87, logical) == x87.physical[(x87.status.top + logical) % 8]
\* @type: ($amd64X87, Int) => (Int -> Bool);
ReadMMX(x87, register) == LowBits(64, x87.physical[register])

MXCSRFields == {
  "invalid", "denormal", "zeroDivide", "overflow", "underflow", "precision",
  "denormalsAreZero", "invalidMask", "denormalMask", "zeroDivideMask",
  "overflowMask", "underflowMask", "precisionMask", "roundingControl",
  "flushToZero", "reserved16", "misalignedMask", "reservedHigh"}

\* @type: ($amd64Profile, $amd64MXCSR) => Bool;
MXCSRWellFormed(profile, mxcsr) ==
  /\ mxcsr.roundingControl \in RoundingModes
  /\ mxcsr.reservedHigh \in BitVector(14)
  /\ ~mxcsr.reserved16
  /\ \A bit \in 1..14 : ~mxcsr.reservedHigh[bit]
  /\ (profile.capabilities.mxcsrMisalignedMask \/ ~mxcsr.misalignedMask)

\* ZMM is the only vector storage. XMM/YMM are low views of the same register.
\* @type: ((Int -> (Int -> Bool)), Int) => (Int -> Bool);
ReadXMM(vectors, register) == LowBits(128, vectors[register])
\* @type: ((Int -> (Int -> Bool)), Int) => (Int -> Bool);
ReadYMM(vectors, register) == LowBits(256, vectors[register])

\* @type: ($amd64Profile, $amd64Context, Int) => Bool;
VectorRegisterAvailable(profile, context, register) ==
  /\ profile.capabilities.sse
  /\ register \in 0..31
  /\ CASE register < 8 -> TRUE
       [] register < 16 -> context.mode = "long64"
       [] OTHER -> profile.capabilities.avx512 /\ context.mode = "long64"

VectorWidths == {128, 256, 512}
\* @type: ($amd64Profile, Int) => Bool;
VectorWidthAvailable(profile, width) ==
  /\ width \in VectorWidths
  /\ CASE width = 128 -> profile.capabilities.sse
       [] width = 256 -> profile.capabilities.avx
       [] OTHER -> profile.capabilities.avx512

\* @type: $amd64Profile => Bool;
MaskRegisterAvailable(profile) == profile.capabilities.avx512

CPUStateFields == {
  "gpr", "rip", "rflags", "segments", "x87", "vectors", "kMask", "mxcsr",
  "execution"}

\* @type: ($amd64Profile, $amd64CPUState) => Bool;
CPUStateWellFormed(profile, state) ==
  /\ ProfileWellFormed(profile)
  /\ state.gpr \in [0..15 -> [1..64 -> BOOLEAN]]
  /\ state.rip \in BitVector(64)
  /\ RFlagsWellFormed(state.rflags)
  /\ SegmentContextWellFormed(state.segments)
  /\ X87StateWellFormed(state.x87)
  /\ state.vectors \in [0..31 -> BitVector(512)]
  /\ state.kMask \in [0..7 -> BitVector(64)]
  /\ MXCSRWellFormed(profile, state.mxcsr)
  /\ ModeSupported(profile, state.execution.mode)
  /\ state.execution.cpl \in 0..3
  /\ (state.execution.features.x87Enabled => profile.capabilities.x87)
  /\ (state.execution.features.sseEnabled => profile.capabilities.sse)
  /\ (state.execution.features.avxEnabled =>
        state.execution.features.sseEnabled /\ profile.capabilities.avx)
  /\ (state.execution.features.avx512Enabled =>
        state.execution.features.avxEnabled /\ profile.capabilities.avx512)
  /\ (state.execution.mode = "real" => state.execution.cpl = 0)
  /\ (state.execution.mode = "virtual8086" => state.execution.cpl = 3)
  /\ state.rflags.virtual8086 = (state.execution.mode = "virtual8086")
  /\ state.segments.cs.present
  /\ ~state.segments.cs.unusable
  /\ state.segments.cs.executable
  /\ (state.execution.mode = "long64") = state.segments.cs.longMode
  /\ (state.segments.cs.longMode => ~state.segments.cs.defaultBig)

\* Important boundary: this validity predicate intentionally does not require
\* inactive registers to be zero. Mode and feature guards control addressability,
\* while storage survives mode changes. Nor does validity encode instruction-
\* specific flag write masks or legacy/extended vector upper-bit behavior.

=====================================================================
