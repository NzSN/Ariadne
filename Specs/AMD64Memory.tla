-------------------------- MODULE AMD64Memory --------------------------
EXTENDS Integers, FiniteSets, Sequences

\* Full-width address and access foundation for the AMD64 expansion.
\*
\* This module deliberately represents addresses as Boolean vectors rather
\* than TLC integers. TLC must never be asked to hold an arbitrary 64-bit
\* architectural value in its host integer representation. Addition is a
\* relation checked with an explicit carry certificate. The certificate is
\* evidence for one deterministic ripple-carry computation, not an
\* environment callback or a choice of an arbitrary result.
\*
\* PageMap is the effective result of a page walk. It is explicit and must be
\* non-overlapping, but it does not yet model CR3-rooted walks, Accessed/Dirty
\* writes, TLBs, or every reserved-bit rule. Those boundaries are recorded in
\* Specs/AMD64/system-dependencies.json and docs/amd64-memory-exceptions.md.
\*
\* Authority: AMD APM Volume 1 revision 3.25 sections 2.1, 2.2 and 3.8;
\* Volume 2 revision 3.45 sections 4.3-4.13, 5.1-5.10, 7 and 8.2.

\* @typeAlias: amd64Address = Int -> Bool;
\* @typeAlias: amd64Byte = Int -> Bool;
\* @typeAlias: amd64Carry = Int -> Bool;
\* @typeAlias: amd64Segment = {base: $amd64Address, limit: $amd64Address,
\*   present: Bool, readable: Bool, writable: Bool, executable: Bool,
\*   conforming: Bool, expandDown: Bool, defaultBig: Bool,
\*   unusable: Bool, dpl: Int, rpl: Int};
\* @typeAlias: amd64Access = {kind: Str, stack: Bool,
\*   implicitSupervisor: Bool, shadow: Bool};
\* @typeAlias: amd64Page = {linearTag: $amd64Address,
\*   physicalTag: $amd64Address, offsetBits: Int, present: Bool,
\*   writable: Bool, user: Bool, executable: Bool, reserved: Bool,
\*   shadowStack: Bool, protectionKey: Int};
\* @typeAlias: amd64SystemConfig = {virtualBits: Int, paging: Bool,
\*   a20Enabled: Bool, cr0AM: Bool, cr0WP: Bool, cr4PAE: Bool,
\*   cr4SMEP: Bool, cr4SMAP: Bool, cr4PKE: Bool, cr4CET: Bool,
\*   eferNXE: Bool, iopl: Int,
\*   pkruAD: Int -> Bool, pkruWD: Int -> Bool};
\* @typeAlias: amd64PageFaultCode = {present: Bool, write: Bool,
\*   user: Bool, reserved: Bool, instruction: Bool, instructionDefined: Bool,
\*   protectionKey: Bool, shadowStack: Bool, shadowStackDefined: Bool};
\* @typeAlias: amd64Fault = {stage: Int, vector: Str, reason: Str,
\*   errorCode: $amd64PageFaultCode, linear: $amd64Address};
\* @typeAlias: amd64ByteCell = {physical: $amd64Address, value: $amd64Byte};
\* @typeAlias: amd64MemoryEvent = {kind: Str, linear: $amd64Address,
\*   physical: $amd64Address, size: Int, value: Seq($amd64Byte)};
\* @typeAlias: amd64ReadResult = {kind: Str, value: $amd64Byte};

AddressBits == 1..64
ByteBits == 1..8

\* @type: $amd64Address;
ZeroAddress == [bit \in AddressBits |-> FALSE]

\* @type: $amd64PageFaultCode;
NoPageFaultCode == [present |-> FALSE, write |-> FALSE, user |-> FALSE,
  reserved |-> FALSE, instruction |-> FALSE, instructionDefined |-> FALSE,
  protectionKey |-> FALSE, shadowStack |-> FALSE, shadowStackDefined |-> FALSE]

\* @type: $amd64Address => Bool;
AddressWellFormed(address) ==
  DOMAIN address = AddressBits /\ \A bit \in AddressBits : address[bit] \in BOOLEAN

\* @type: $amd64Byte => Bool;
ByteWellFormed(byte) ==
  DOMAIN byte = ByteBits /\ \A bit \in ByteBits : byte[bit] \in BOOLEAN

\* @type: (Bool, Bool, Bool) => Bool;
Xor3(a, b, carry) == (a /= b) /= carry

\* @type: (Bool, Bool, Bool) => Bool;
Majority(a, b, carry) == (a /\ b) \/ (a /\ carry) \/ (b /\ carry)

\* Full modulo-2^64 addition. `carry[1]` is the input carry and
\* `carry[65]` is the discarded overflow bit.
\* @type: ($amd64Address, $amd64Address, $amd64Address, $amd64Carry) => Bool;
WordAddWithCarry(left, right, sum, carry) ==
  /\ AddressWellFormed(left) /\ AddressWellFormed(right)
  /\ AddressWellFormed(sum)
  /\ DOMAIN carry = 1..65
  /\ carry[1] = FALSE
  /\ \A bit \in AddressBits :
       /\ sum[bit] = Xor3(left[bit], right[bit], carry[bit])
       /\ carry[bit + 1] = Majority(left[bit], right[bit], carry[bit])

\* Address-size truncation happens before segment-base addition. Compatibility
\* mode zero-extends 16/32-bit results; the 64-bit submode permits 64 or 32
\* bits and zero-extends the latter. It never permits 16-bit addressing. The
\* form layer chooses the correct default/67h-override pair.
\* @type: ($amd64Address, Int) => $amd64Address;
EffectiveOffset(raw, addressSize) ==
  [bit \in AddressBits |-> IF bit <= addressSize THEN raw[bit] ELSE FALSE]

\* Segmentation adds the base at full carry precision, then applies the
\* submode's linear-address width. The explicit raw sum and carry are checked
\* evidence; they are not selected by an environment oracle.
\* @type: (Str, $amd64Address, $amd64Address, $amd64Address,
\*   $amd64Carry, $amd64Address) => Bool;
SegmentLinearWithCarry(mode, base, effective, rawSum, carry, linear) ==
  /\ WordAddWithCarry(base, effective, rawSum, carry)
  /\ linear = CASE mode = "long64" -> rawSum
       [] mode \in {"compatibility", "protected"} -> EffectiveOffset(rawSum, 32)
       [] mode \in {"real", "virtual8086"} -> EffectiveOffset(rawSum, 32)
       [] OTHER -> ZeroAddress

\* A20 masking is a physical-address step, not linear-address formation.
\* @type: ($amd64SystemConfig, Str, $amd64Address) => $amd64Address;
ApplyA20(config, mode, linear) ==
  [bit \in AddressBits |->
    IF mode \in {"real", "virtual8086"} /\ ~config.a20Enabled /\ bit = 21
    THEN FALSE ELSE linear[bit]]

\* `defaultAddressSize` is derived by the architectural-state layer from the
\* current mode and CS.D/CS.L. I2 must bind whether prefix 67h selected the
\* alternate member; this predicate rejects impossible submode/size pairs.
\* @type: (Str, Int, Int) => Bool;
AddressSizePermitted(mode, defaultAddressSize, addressSize) ==
  CASE mode = "long64" -> defaultAddressSize = 64 /\ addressSize \in {32, 64}
    [] mode = "compatibility" ->
         defaultAddressSize \in {16, 32} /\ addressSize \in {16, 32}
    [] mode = "protected" ->
         defaultAddressSize \in {16, 32} /\ addressSize \in {16, 32}
    [] mode \in {"real", "virtual8086"} ->
         defaultAddressSize = 16 /\ addressSize \in {16, 32}
    [] OTHER -> FALSE

\* @type: ($amd64Address, Int) => Bool;
Canonical(address, virtualBits) ==
  /\ virtualBits \in 1..64
  /\ \A bit \in (virtualBits + 1)..64 : address[bit] = address[virtualBits]

\* In 64-bit mode DS/ES/SS bases are zero and their limits/attributes are
\* ignored for ordinary data references. FS and GS retain their bases.
\* @type: (Str, Str, $amd64Segment) => $amd64Address;
EffectiveSegmentBase(mode, segmentName, segment) ==
  IF mode = "long64" /\ segmentName \notin {"fs", "gs"}
  THEN ZeroAddress ELSE segment.base

\* @type: ($amd64Address, $amd64Address) => Bool;
UnsignedLE(left, right) ==
  left = right \/ \E decisive \in AddressBits :
    /\ ~left[decisive] /\ right[decisive]
    /\ \A high \in (decisive + 1)..64 : left[high] = right[high]

\* This access predicate concerns an already-loaded effective segment cache
\* and the complete effective-offset span. Descriptor-load and far-control-
\* transfer checks are separate dependencies.
\* @type: (Str, Int, Str, $amd64Segment, $amd64Access,
\*   $amd64Address, $amd64Address) => Bool;
SegmentPermits(mode, cpl, segmentName, segment, access, effectiveStart, effectiveEnd) ==
  IF mode = "long64"
  THEN segmentName \in {"cs", "ss", "ds", "es", "fs", "gs"}
  ELSE /\ ~segment.unusable
       /\ segment.present
       /\ (~segment.conforming \/ segment.executable)
       /\ IF segmentName = "ss"
          THEN cpl = segment.rpl /\ cpl = segment.dpl
          ELSE IF segmentName = "cs" THEN TRUE
               ELSE IF cpl >= segment.rpl THEN cpl <= segment.dpl
                    ELSE segment.rpl <= segment.dpl
       /\ IF access.kind = "fetch" THEN segment.executable
          ELSE IF access.kind = "write" \/ access.kind = "readWrite"
               THEN segment.writable
               ELSE segment.readable \/ ~segment.executable
       /\ IF segment.expandDown
          THEN /\ ~UnsignedLE(effectiveStart, segment.limit)
               /\ IF segment.defaultBig THEN TRUE
                  ELSE \A bit \in 17..64 : ~effectiveEnd[bit]
          ELSE UnsignedLE(effectiveEnd, segment.limit)

\* @type: ($amd64Address, $amd64Page) => Bool;
MappingMatches(linear, page) ==
  /\ page.offsetBits \in {12, 21, 22, 30}
  /\ \A bit \in (page.offsetBits + 1)..64 : linear[bit] = page.linearTag[bit]

\* Page tags must be aligned and linear tags must not overlap. This makes the
\* mapping selected for an address unique without a CHOOSE oracle.
\* @type: Set($amd64Page) => Bool;
PageMapWellFormed(pageMap) ==
  /\ \A page \in pageMap :
       /\ AddressWellFormed(page.linearTag)
       /\ AddressWellFormed(page.physicalTag)
       /\ page.offsetBits \in {12, 21, 22, 30}
       /\ page.protectionKey \in 0..15
       /\ \A bit \in 1..page.offsetBits :
            ~page.linearTag[bit] /\ ~page.physicalTag[bit]
  /\ \A left, right \in pageMap :
       left /= right =>
         \E bit \in ((IF left.offsetBits >= right.offsetBits
                      THEN left.offsetBits ELSE right.offsetBits) + 1)..64 :
           left.linearTag[bit] /= right.linearTag[bit]

\* @type: ($amd64Address, $amd64Page, $amd64Address) => Bool;
TranslateAddress(linear, page, physical) ==
  /\ MappingMatches(linear, page)
  /\ physical = [bit \in AddressBits |->
       IF bit <= page.offsetBits THEN linear[bit] ELSE page.physicalTag[bit]]

\* @type: $amd64Access => Bool;
IsWrite(access) == access.kind \in {"write", "readWrite"}

\* @type: $amd64Access => Bool;
IsFetch(access) == access.kind = "fetch"

\* @type: ($amd64SystemConfig, Int, Bool, $amd64Page, $amd64Access) => Bool;
PagePermits(config, cpl, rflagsAC, page, access) ==
  LET supervisor == cpl < 3
      pkruDenied == config.cr4PKE /\ page.user /\ ~IsFetch(access) /\
        (config.pkruAD[page.protectionKey] \/
          (IsWrite(access) /\ config.pkruWD[page.protectionKey] /\
            (~supervisor \/ config.cr0WP)))
      smepDenied == config.cr4SMEP /\ supervisor /\ page.user /\ IsFetch(access)
      smapDenied == config.cr4SMAP /\ page.user /\ ~IsFetch(access) /\
        ~access.shadow /\ (access.implicitSupervisor \/ (supervisor /\ ~rflagsAC))
      writeDenied == IsWrite(access) /\ ~page.writable /\
        (~supervisor \/ config.cr0WP) /\ ~access.shadow
      userDenied == cpl = 3 /\ ~page.user
      nxDenied == IsFetch(access) /\ config.eferNXE /\ ~page.executable
      shadowDenied == (access.shadow /= page.shadowStack) /\
        (access.shadow \/ (page.shadowStack /\ IsWrite(access)))
  IN page.present /\ ~page.reserved /\ ~pkruDenied /\ ~smepDenied /\
     ~smapDenied /\ ~writeDenied /\ ~userDenied /\ ~nxDenied /\ ~shadowDenied

\* @type: ($amd64SystemConfig, Int, Bool, $amd64Page, $amd64Access) => $amd64PageFaultCode;
PageFaultError(config, cpl, rflagsAC, page, access) ==
  LET instructionDefined == config.eferNXE /\ config.cr4PAE
      shadowDefined == config.cr4CET
  IN [present |-> page.present,
   write |-> IsWrite(access),
   user |-> cpl = 3,
   reserved |-> page.reserved,
   instruction |-> instructionDefined /\ IsFetch(access),
   instructionDefined |-> instructionDefined,
   protectionKey |-> config.cr4PKE /\ page.user /\ ~IsFetch(access) /\
     (config.pkruAD[page.protectionKey] \/
       (IsWrite(access) /\ config.pkruWD[page.protectionKey] /\
         (cpl = 3 \/ config.cr0WP))),
   shadowStack |-> shadowDefined /\ access.shadow,
   shadowStackDefined |-> shadowDefined]

\* @type: ($amd64SystemConfig, Int, $amd64Access) => $amd64PageFaultCode;
MissingPageFaultError(config, cpl, access) ==
  LET instructionDefined == config.eferNXE /\ config.cr4PAE
      shadowDefined == config.cr4CET
  IN [present |-> FALSE, write |-> IsWrite(access), user |-> cpl = 3,
   reserved |-> FALSE,
   instruction |-> instructionDefined /\ IsFetch(access),
   instructionDefined |-> instructionDefined,
   protectionKey |-> FALSE,
   shadowStack |-> shadowDefined /\ access.shadow,
   shadowStackDefined |-> shadowDefined]

\* alignmentBits=0 means no ordinary alignment requirement. A value n means
\* a 2^n-byte boundary, checked directly from the low address bits.
\* @type: ($amd64Address, Int) => Bool;
Aligned(linear, alignmentBits) ==
  /\ alignmentBits \in 0..6
  /\ \A bit \in 1..alignmentBits : ~linear[bit]

\* @type: ($amd64SystemConfig, Int, Bool, $amd64Address, Int) => Bool;
AlignmentFault(config, cpl, rflagsAC, linear, alignmentBits) ==
  config.cr0AM /\ rflagsAC /\ cpl = 3 /\ ~Aligned(linear, alignmentBits)

\* Common access candidates use stages 1=segment/canonical, 2=paging,
\* 3=ordinary alignment. A Volume 3 instruction rule must add or replace
\* candidates when it specifies a different priority or mandatory alignment.
\* @type: ($amd64SystemConfig, Str, Int, Bool, Str, $amd64Segment,
\*   $amd64Address, $amd64Address, Seq($amd64Address),
\*   Set($amd64Page), $amd64Access, Int) => Set($amd64Fault);
MemoryFaultCandidates(config, mode, cpl, rflagsAC, segmentName, segment,
                      effectiveStart, effectiveEnd, linearSpan,
                      pageMap, access, alignmentBits) ==
  LET linear == IF Len(linearSpan) = 0 THEN ZeroAddress ELSE Head(linearSpan)
      matches == {page \in pageMap : MappingMatches(linear, page)}
      addressVector == IF access.stack THEN "SS" ELSE "GP"
      addressFaults ==
        IF ~SegmentPermits(mode, cpl, segmentName, segment, access,
                           effectiveStart, effectiveEnd) \/
           (mode = "long64" /\
             \E index \in 1..Len(linearSpan) :
               ~Canonical(linearSpan[index], config.virtualBits))
        THEN {[stage |-> 1, vector |-> addressVector, reason |-> "address",
               errorCode |-> NoPageFaultCode, linear |-> linear]}
        ELSE {}
      pageFaults ==
        IF addressFaults /= {} \/ ~config.paging THEN {}
        ELSE IF matches = {}
             THEN {[stage |-> 2, vector |-> "PF", reason |-> "not-present",
                    errorCode |-> MissingPageFaultError(config, cpl, access),
                    linear |-> linear]}
             ELSE { [stage |-> 2, vector |-> "PF", reason |-> "page-protection",
                     errorCode |-> PageFaultError(config, cpl, rflagsAC, page, access),
                     linear |-> linear] :
                    page \in {candidate \in matches :
                      ~PagePermits(config, cpl, rflagsAC, candidate, access)} }
      alignmentFaults ==
        IF addressFaults = {} /\ pageFaults = {} /\
           AlignmentFault(config, cpl, rflagsAC, linear, alignmentBits)
        THEN {[stage |-> 3, vector |-> "AC", reason |-> "unaligned",
               errorCode |-> NoPageFaultCode, linear |-> linear]}
        ELSE {}
  IN addressFaults \cup pageFaults \cup alignmentFaults

\* Memory is a finite set of uniquely-addressed physical byte cells. This is
\* an architectural-value projection only; it does not define D1 ordering.
\* @type: Set($amd64ByteCell) => Bool;
MemoryWellFormed(memory) ==
  /\ \A cell \in memory :
       AddressWellFormed(cell.physical) /\ ByteWellFormed(cell.value)
  /\ \A left, right \in memory : left.physical = right.physical => left = right

\* CapturedMemoryWellFormed describes an analysis snapshot, not architectural
\* RAM. Every address declared captured has exactly one byte; an address
\* outside the domain is unavailable and never silently becomes zero/fault.
\* @type: (Set($amd64ByteCell), Set($amd64Address)) => Bool;
CapturedMemoryWellFormed(memory, captured) ==
  /\ MemoryWellFormed(memory)
  /\ \A cell \in memory : cell.physical \in captured
  /\ \A physical \in captured : \E cell \in memory : cell.physical = physical

\* @type: (Set($amd64ByteCell), $amd64Address, $amd64Byte) => Bool;
ReadByte(memory, physical, value) ==
  \E cell \in memory : cell.physical = physical /\ cell.value = value

\* @type: (Set($amd64ByteCell), Set($amd64Address), $amd64Address,
\*   $amd64ReadResult) => Bool;
ReadByteResult(memory, captured, physical, result) ==
  IF physical \in captured
  THEN result.kind = "available" /\ ReadByte(memory, physical, result.value)
  ELSE result = [kind |-> "unavailable",
                 value |-> [bit \in ByteBits |-> FALSE]]

\* @type: (Set($amd64ByteCell), $amd64Address, $amd64Byte, Set($amd64ByteCell)) => Bool;
WriteByte(memory, physical, value, after) ==
  after = {cell \in memory : cell.physical /= physical} \cup
          {[physical |-> physical, value |-> value]}

\* @type: (Set(Int), Int, Int, Int) => Bool;
IOPermitted(deniedPorts, cpl, iopl, port) ==
  /\ port \in 0..65535
  /\ (cpl <= iopl \/ port \notin deniedPorts)

==========================================================================
