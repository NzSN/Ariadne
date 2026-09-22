------------------------- MODULE AMD64PageWalk -------------------------
EXTENDS AMD64ConcreteMemory

\* Explicit page-walk certificates for AMD64 page-translation variants.
\*
\* A certificate contains the entries fetched from physical page-table
\* memory and the carry evidence for every table-base + scaled-index address.
\* Validation recomputes indices from the full-width linear address, checks
\* the table chain, checks the raw entry bits, and derives the effective map.
\* It is not an opaque page-lookup callback.
\*
\* Authority: AMD APM Volume 2 revision 3.45 sections 5.2-5.6,
\* especially PDF pages 195-232. Variant status and the deliberately open
\* reserved-bit cases are documented in docs/amd64-page-walk.md.

\* @typeAlias: amd64PageWalkConfig = {variant: Str, root: $amd64Address,
\*   physicalBits: Int, nxe: Bool, cet: Bool, oneGiB: Bool};
\* @typeAlias: amd64PageEntry = {level: Str, physical: $amd64Address,
\*   raw: $amd64Address};
\* @typeAlias: amd64PageTableCell = {physical: $amd64Address,
\*   raw: $amd64Address, bytes: Seq($amd64Byte), available: Bool,
\*   byteAddresses: Seq($amd64Address), byteCarries: Seq($amd64Carry)};
\* @typeAlias: amd64WalkCertificate = {entries: Seq($amd64PageEntry),
\*   carries: Seq($amd64Carry)};
\* @typeAlias: amd64ADUpdate = {position: Int, physical: $amd64Address,
\*   setAccessed: Bool, setDirty: Bool};
\* @typeAlias: amd64WalkFault = {kind: Str, failedLevel: Str,
\*   failedPhysical: $amd64Address, errorCode: $amd64PageFaultCode,
\*   updates: Set($amd64ADUpdate)};

WalkVariants == {"long4", "long5", "pae", "legacy"}
WalkLevels == {"pml5", "pml4", "pdpt", "pd", "pt"}

\* @type: $amd64PageWalkConfig => Bool;
WalkConfigWellFormed(config) ==
  /\ config.variant \in WalkVariants
  /\ config.physicalBits \in 32..52
  /\ AddressWellFormed(config.root)
  /\ \A bit \in 1..12 : ~config.root[bit]
  /\ (config.variant = "legacy" => config.physicalBits = 32 /\ ~config.nxe)

\* Raw entries use the manual bit numbering shifted by one for TLA+ maps.
\* @type: $amd64PageEntry => Bool;
EntryPresent(entry) == entry.raw[1]
\* @type: $amd64PageEntry => Bool;
EntryWritable(entry) == entry.raw[2]
\* @type: $amd64PageEntry => Bool;
EntryUser(entry) == entry.raw[3]
\* @type: $amd64PageEntry => Bool;
EntryAccessed(entry) == entry.raw[6]
\* @type: $amd64PageEntry => Bool;
EntryDirty(entry) == entry.raw[7]
\* @type: $amd64PageEntry => Bool;
EntryLarge(entry) == entry.raw[8]
\* @type: $amd64PageEntry => Bool;
EntryNX(entry) == entry.raw[64]

\* @type: (Str, Int) => Seq(Str);
ExpectedLevels(variant, pageBits) ==
  CASE variant = "long4" /\ pageBits = 12 -> <<"pml4", "pdpt", "pd", "pt">>
    [] variant = "long4" /\ pageBits = 21 -> <<"pml4", "pdpt", "pd">>
    [] variant = "long4" /\ pageBits = 30 -> <<"pml4", "pdpt">>
    [] variant = "long5" /\ pageBits = 12 -> <<"pml5", "pml4", "pdpt", "pd", "pt">>
    [] variant = "long5" /\ pageBits = 21 -> <<"pml5", "pml4", "pdpt", "pd">>
    [] variant = "long5" /\ pageBits = 30 -> <<"pml5", "pml4", "pdpt">>
    [] variant = "pae" /\ pageBits = 12 -> <<"pdpt", "pd", "pt">>
    [] variant = "pae" /\ pageBits = 21 -> <<"pdpt", "pd">>
    [] variant = "legacy" /\ pageBits = 12 -> <<"pd", "pt">>
    [] variant = "legacy" /\ pageBits = 22 -> <<"pd">>
    [] OTHER -> <<>>

\* @type: (Str, Str) => Int;
IndexLowBit(variant, level) ==
  CASE level = "pml5" -> 49
    [] level = "pml4" -> 40
    [] level = "pdpt" -> 31
    [] level = "pd" /\ variant = "legacy" -> 23
    [] level = "pd" -> 22
    [] level = "pt" -> 13
    [] OTHER -> 1

\* @type: (Str, Str) => Int;
IndexWidth(variant, level) ==
  IF variant = "legacy" THEN 10
  ELSE IF variant = "pae" /\ level = "pdpt" THEN 2 ELSE 9

\* @type: Str => Int;
EntryShift(variant) == IF variant = "legacy" THEN 2 ELSE 3

\* Scaled page-table index: 4-byte entries in non-PAE legacy paging and
\* 8-byte entries in PAE/long mode.
\* @type: ($amd64Address, Str, Str) => $amd64Address;
IndexDisplacement(linear, variant, level) ==
  LET low == IndexLowBit(variant, level)
      width == IndexWidth(variant, level)
      shift == EntryShift(variant)
  IN [bit \in AddressBits |->
       IF shift < bit /\ bit <= shift + width
       THEN linear[low + bit - shift - 1] ELSE FALSE]

\* @type: ($amd64PageWalkConfig, $amd64PageEntry) => $amd64Address;
EntryBase(config, entry) ==
  [bit \in AddressBits |->
    IF 12 < bit /\ bit <= config.physicalBits THEN entry.raw[bit] ELSE FALSE]

\* @type: ($amd64PageWalkConfig, $amd64PageEntry, Int) => $amd64Address;
LeafBase(config, entry, pageBits) ==
  [bit \in AddressBits |->
    IF pageBits < bit /\ bit <= config.physicalBits THEN entry.raw[bit] ELSE FALSE]

\* @type: ($amd64PageWalkConfig, Str, $amd64PageEntry) => Bool;
NXEffective(config, level, entry) ==
  IF config.variant = "legacy" \/ (config.variant = "pae" /\ level = "pdpt")
  THEN FALSE ELSE EntryNX(entry)

\* Common reserved-bit checks that are derivable uniformly from the raw word.
\* Variant-specific available/PAT/global encodings not named here remain open.
\* @type: ($amd64PageWalkConfig, $amd64PageEntry, Int, Bool) => Bool;
EntryReserved(config, entry, pageBits, isLeaf) ==
  \/ (~config.nxe /\ EntryNX(entry) /\
       ~(config.variant = "legacy" \/
         (config.variant = "pae" /\ entry.level = "pdpt")))
  \/ \E bit \in (config.physicalBits + 1)..52 : entry.raw[bit]
  \/ (~isLeaf /\ EntryLarge(entry))
  \/ (isLeaf /\ pageBits = 12 /\ EntryLarge(entry))
  \/ (isLeaf /\ pageBits > 12 /\ ~EntryLarge(entry))
  \/ (isLeaf /\ pageBits > 12 /\ \E bit \in 13..pageBits : entry.raw[bit])
  \/ (pageBits = 30 /\ ~config.oneGiB)
  \/ (config.variant = "pae" /\ entry.level = "pdpt" /\
       \E bit \in {2, 3, 6, 7, 8, 9, 64} : entry.raw[bit])
  \/ (config.variant = "legacy" /\ \E bit \in 33..64 : entry.raw[bit])

\* @type: Str => Int;
EntryByteCount(variant) == IF variant = "legacy" THEN 4 ELSE 8

\* @type: ($amd64Address, Int) => $amd64Byte;
RawEntryByte(raw, index) ==
  [bit \in ByteBits |-> raw[(index - 1) * 8 + bit]]

\* @type: (Str, $amd64Address) => Seq($amd64Byte);
RawEntryBytes(variant, raw) ==
  IF variant = "legacy"
  THEN <<RawEntryByte(raw, 1), RawEntryByte(raw, 2),
         RawEntryByte(raw, 3), RawEntryByte(raw, 4)>>
  ELSE <<RawEntryByte(raw, 1), RawEntryByte(raw, 2),
         RawEntryByte(raw, 3), RawEntryByte(raw, 4),
         RawEntryByte(raw, 5), RawEntryByte(raw, 6),
         RawEntryByte(raw, 7), RawEntryByte(raw, 8)>>

\* Page-table evidence is explicit little-endian memory data. An unavailable
\* captured word cannot validate a certificate and is never changed into #PF.
\* @type: ($amd64PageWalkConfig, Set($amd64PageTableCell), $amd64PageEntry) => Bool;
EntryFetched(config, tableMemory, entry) ==
  \E cell \in tableMemory :
    /\ cell.physical = entry.physical
    /\ cell.available
    /\ cell.raw = entry.raw
    /\ cell.bytes = RawEntryBytes(config.variant, entry.raw)

\* @type: ($amd64ConcreteMemory, $amd64PageWalkConfig,
\*   Set($amd64PageTableCell), $amd64PageEntry) => Bool;
EntryBackedByConcrete(concrete, config, tableMemory, entry) ==
  \E cell \in tableMemory :
    /\ cell.physical = entry.physical
    /\ cell.available
    /\ cell.raw = entry.raw
    /\ cell.bytes = RawEntryBytes(config.variant, entry.raw)
    /\ ConcreteBytesAt(concrete, entry.physical, cell.bytes,
                       cell.byteAddresses, cell.byteCarries)

\* @type: ($amd64PageWalkConfig, $amd64WalkCertificate, Int) => $amd64Address;
TableBaseAt(config, certificate, position) ==
  IF position = 1 THEN config.root
  ELSE EntryBase(config, certificate.entries[position - 1])

\* @type: ($amd64PageWalkConfig, $amd64Address, Set($amd64PageTableCell),
\*   $amd64WalkCertificate, Int) => Bool;
CertificateEntryValid(config, linear, tableMemory, certificate, position) ==
  LET entry == certificate.entries[position]
  IN /\ position \in 1..Len(certificate.entries)
     /\ entry.level \in WalkLevels
     /\ EntryFetched(config, tableMemory, entry)
     /\ WordAddWithCarry(TableBaseAt(config, certificate, position),
          IndexDisplacement(linear, config.variant, entry.level),
          entry.physical, certificate.carries[position])

\* @type: ($amd64PageWalkConfig, $amd64Address, Int,
\*   Set($amd64PageTableCell), $amd64WalkCertificate) => Bool;
SuccessfulWalk(config, linear, pageBits, tableMemory, certificate) ==
  LET levels == ExpectedLevels(config.variant, pageBits)
  IN /\ WalkConfigWellFormed(config)
     /\ levels /= <<>>
     /\ Len(certificate.entries) = Len(levels)
     /\ Len(certificate.carries) = Len(levels)
     /\ \A position \in 1..Len(levels) :
          LET entry == certificate.entries[position]
              isLeaf == position = Len(levels)
          IN /\ entry.level = levels[position]
             /\ CertificateEntryValid(config, linear, tableMemory,
                                      certificate, position)
             /\ EntryPresent(entry)
             /\ ~EntryReserved(config, entry, pageBits, isLeaf)

\* @type: ($amd64ConcreteMemory, $amd64PageWalkConfig, $amd64Address, Int,
\*   Set($amd64PageTableCell), $amd64WalkCertificate) => Bool;
SuccessfulWalkConcrete(concrete, config, linear, pageBits,
                       tableMemory, certificate) ==
  /\ SuccessfulWalk(config, linear, pageBits, tableMemory, certificate)
  /\ \A position \in 1..Len(certificate.entries) :
       EntryBackedByConcrete(concrete, config, tableMemory,
                             certificate.entries[position])

\* Legacy PAE PDPTEs select a directory and do not contribute R/W or U/S.
\* @type: ($amd64PageWalkConfig, $amd64PageEntry) => Bool;
EntryWritableEffective(config, entry) ==
  IF config.variant = "pae" /\ entry.level = "pdpt" THEN TRUE
  ELSE EntryWritable(entry)
\* @type: ($amd64PageWalkConfig, $amd64PageEntry) => Bool;
EntryUserEffective(config, entry) ==
  IF config.variant = "pae" /\ entry.level = "pdpt" THEN TRUE
  ELSE EntryUser(entry)
\* @type: ($amd64PageWalkConfig, Seq($amd64PageEntry)) => Bool;
CombinedWritable(config, entries) ==
  \A position \in 1..Len(entries) : EntryWritableEffective(config, entries[position])
\* @type: ($amd64PageWalkConfig, Seq($amd64PageEntry)) => Bool;
CombinedUser(config, entries) ==
  \A position \in 1..Len(entries) : EntryUserEffective(config, entries[position])
\* @type: ($amd64PageWalkConfig, Seq($amd64PageEntry)) => Bool;
CombinedNX(config, entries) ==
  \E position \in 1..Len(entries) :
    NXEffective(config, entries[position].level, entries[position])

\* @type: $amd64PageEntry => Int;
LeafProtectionKey(entry) ==
  (IF entry.raw[60] THEN 1 ELSE 0) +
  (IF entry.raw[61] THEN 2 ELSE 0) +
  (IF entry.raw[62] THEN 4 ELSE 0) +
  (IF entry.raw[63] THEN 8 ELSE 0)

\* @type: ($amd64PageWalkConfig, $amd64Address, Int,
\*   $amd64WalkCertificate) => $amd64Page;
DerivedPage(config, linear, pageBits, certificate) ==
  LET leaf == certificate.entries[Len(certificate.entries)]
  IN [linearTag |-> [bit \in AddressBits |->
        IF bit <= pageBits THEN FALSE ELSE linear[bit]],
      physicalTag |-> LeafBase(config, leaf, pageBits),
      offsetBits |-> pageBits,
      present |-> TRUE,
      writable |-> CombinedWritable(config, certificate.entries),
      user |-> CombinedUser(config, certificate.entries),
      executable |-> ~CombinedNX(config, certificate.entries),
      reserved |-> FALSE,
      shadowStack |-> FALSE,
      protectionKey |-> LeafProtectionKey(leaf)]

\* A successful walk sets A on every traversed entry. D is non-speculative and
\* is requested only for the leaf after page protection allowed the write.
\* @type: ($amd64PageWalkConfig, $amd64WalkCertificate, Bool) => Set($amd64ADUpdate);
SuccessfulADUpdates(config, certificate, allowedWrite) ==
  {[position |-> position,
    physical |-> certificate.entries[position].physical,
    setAccessed |-> TRUE,
    setDirty |-> allowedWrite /\ position = Len(certificate.entries)] :
      position \in {candidate \in 1..Len(certificate.entries) :
        ~(config.variant = "pae" /\
          certificate.entries[candidate].level = "pdpt")}}

\* A failed walk can expose A updates for the valid present prefix. The failing
\* entry and all later entries receive no A/D update from this walk. Protection
\* faults happen after a complete walk and therefore use SuccessfulADUpdates
\* with dirty=FALSE until an architectural write is allowed to commit.
\* @type: ($amd64PageWalkConfig, $amd64Address, Int,
\*   Set($amd64PageTableCell), $amd64WalkCertificate, Int, Str) => Bool;
FailedWalkAt(config, linear, pageBits, tableMemory, certificate,
             failedPosition, reason) ==
  LET levels == ExpectedLevels(config.variant, pageBits)
      failed == certificate.entries[failedPosition]
  IN /\ WalkConfigWellFormed(config)
     /\ Len(certificate.entries) = failedPosition
     /\ Len(certificate.carries) = failedPosition
     /\ failedPosition \in 1..Len(levels)
     /\ \A position \in 1..failedPosition :
          /\ certificate.entries[position].level = levels[position]
          /\ CertificateEntryValid(config, linear, tableMemory,
                                   certificate, position)
     /\ \A position \in 1..(failedPosition - 1) :
          /\ EntryPresent(certificate.entries[position])
          /\ ~EntryReserved(config, certificate.entries[position], pageBits,
                            position = Len(levels))
     /\ CASE reason = "not-present" -> ~EntryPresent(failed)
          [] reason = "reserved" -> EntryPresent(failed) /\
               EntryReserved(config, failed, pageBits,
                             failedPosition = Len(levels))
          [] OTHER -> FALSE

\* @type: ($amd64ConcreteMemory, $amd64PageWalkConfig, $amd64Address, Int,
\*   Set($amd64PageTableCell), $amd64WalkCertificate, Int, Str) => Bool;
FailedWalkConcrete(concrete, config, linear, pageBits, tableMemory,
                   certificate, failedPosition, reason) ==
  /\ FailedWalkAt(config, linear, pageBits, tableMemory, certificate,
                  failedPosition, reason)
  /\ \A position \in 1..failedPosition :
       EntryBackedByConcrete(concrete, config, tableMemory,
                             certificate.entries[position])

\* @type: ($amd64PageWalkConfig, $amd64WalkCertificate, Int) => Set($amd64ADUpdate);
FailedADUpdates(config, certificate, failedPosition) ==
  {[position |-> position,
    physical |-> certificate.entries[position].physical,
    setAccessed |-> TRUE, setDirty |-> FALSE] :
      position \in {candidate \in 1..(failedPosition - 1) :
        ~(config.variant = "pae" /\
          certificate.entries[candidate].level = "pdpt")}}

\* @type: ($amd64PageWalkConfig, Int, $amd64Access) => $amd64PageFaultCode;
ReservedWalkPageFaultError(config, cpl, access) ==
  LET pae == config.variant /= "legacy"
  IN [present |-> TRUE, write |-> IsWrite(access), user |-> cpl = 3,
   reserved |-> TRUE,
   instruction |-> config.nxe /\ pae /\ IsFetch(access),
   instructionDefined |-> config.nxe /\ pae,
   protectionKey |-> FALSE,
   shadowStack |-> config.cet /\ access.shadow,
   shadowStackDefined |-> config.cet]

\* @type: ($amd64PageWalkConfig, $amd64WalkCertificate, Int, Str, Int, $amd64Access) => $amd64WalkFault;
FailedWalkFault(config, certificate, failedPosition, reason, cpl, access) ==
  [kind |-> reason,
   failedLevel |-> certificate.entries[failedPosition].level,
   failedPhysical |-> certificate.entries[failedPosition].physical,
   errorCode |-> IF reason = "not-present"
                THEN LET memoryConfig ==
                  [virtualBits |-> 48, paging |-> TRUE, a20Enabled |-> TRUE,
                   cr0AM |-> FALSE, cr0WP |-> TRUE,
                   cr4PAE |-> config.variant /= "legacy",
                   cr4SMEP |-> FALSE, cr4SMAP |-> FALSE,
                   cr4PKE |-> FALSE, cr4CET |-> config.cet,
                   eferNXE |-> config.nxe, iopl |-> 0,
                   pkruAD |-> [key \in 0..15 |-> FALSE],
                   pkruWD |-> [key \in 0..15 |-> FALSE]]
                     IN MissingPageFaultError(memoryConfig, cpl, access)
                ELSE ReservedWalkPageFaultError(config, cpl, access),
   updates |-> FailedADUpdates(config, certificate, failedPosition)]

==========================================================================
