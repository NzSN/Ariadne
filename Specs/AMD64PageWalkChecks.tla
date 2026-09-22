-------------------- MODULE AMD64PageWalkChecks --------------------
EXTENDS AMD64PageWalk

Zeros == [bit \in AddressBits |-> FALSE]
ZeroByte == [bit \in ByteBits |-> FALSE]
ZeroCarry == [bit \in 1..65 |-> FALSE]

\* @type: Seq($amd64Address);
ByteAddresses4 == <<SmallOffset(0), SmallOffset(1), SmallOffset(2), SmallOffset(3)>>
\* @type: Seq($amd64Address);
ByteAddresses8 == <<SmallOffset(0), SmallOffset(1), SmallOffset(2), SmallOffset(3),
  SmallOffset(4), SmallOffset(5), SmallOffset(6), SmallOffset(7)>>
\* @type: Seq($amd64Carry);
ByteCarries4 == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>
\* @type: Seq($amd64Carry);
ByteCarries8 == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry,
  ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>

Raw(present, writable, user, accessed, dirty, large, nx) ==
  [bit \in AddressBits |->
    CASE bit = 1 -> present
      [] bit = 2 -> writable
      [] bit = 3 -> user
      [] bit = 6 -> accessed
      [] bit = 7 -> dirty
      [] bit = 8 -> large
      [] bit = 64 -> nx
      [] OTHER -> FALSE]

TableEntry(level, raw) == [level |-> level, physical |-> Zeros, raw |-> raw]
TableCell(variant, raw) == [physical |-> Zeros, raw |-> raw,
  bytes |-> RawEntryBytes(variant, raw), available |-> TRUE,
  byteAddresses |-> IF variant = "legacy" THEN ByteAddresses4 ELSE ByteAddresses8,
  byteCarries |-> IF variant = "legacy" THEN ByteCarries4 ELSE ByteCarries8]
UnavailableCell(variant, raw) == [TableCell(variant, raw) EXCEPT !.available = FALSE]

ConcreteFor(variant, raw) ==
  LET bytes == RawEntryBytes(variant, raw)
      addresses == IF variant = "legacy" THEN ByteAddresses4 ELSE ByteAddresses8
  IN [physicalBits |-> 52, defaultByte |-> ZeroByte,
      overrides |-> {[physical |-> addresses[index], value |-> bytes[index]] :
        index \in {candidate \in 1..Len(bytes) : bytes[candidate] /= ZeroByte}}]

NormalRaw == Raw(TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE)
LargeRaw == Raw(TRUE, TRUE, TRUE, FALSE, FALSE, TRUE, FALSE)
AbsentRaw == Raw(FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE)
NXRaw == Raw(TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, TRUE)
PAEPDPTRaw == Raw(TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE)
WriteAccess == [kind |-> "write", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]
FetchAccess == [kind |-> "fetch", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]

Long4 == [variant |-> "long4", root |-> Zeros, physicalBits |-> 52,
  nxe |-> TRUE, cet |-> FALSE, oneGiB |-> TRUE]
Long5 == [Long4 EXCEPT !.variant = "long5"]
PAE == [Long4 EXCEPT !.variant = "pae", !.oneGiB = FALSE]
Legacy == [Long4 EXCEPT !.variant = "legacy", !.physicalBits = 32,
  !.nxe = FALSE, !.oneGiB = FALSE]

\* @type: Seq($amd64PageEntry);
Long4Entries == <<TableEntry("pml4", NormalRaw),
  TableEntry("pdpt", NormalRaw), TableEntry("pd", NormalRaw),
  TableEntry("pt", NormalRaw)>>
\* @type: Seq($amd64Carry);
Long4Carries == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>
Long4Certificate == [entries |-> Long4Entries, carries |-> Long4Carries]
Long4Memory == {TableCell("long4", NormalRaw)}
PAEMemory == {TableCell("pae", PAEPDPTRaw), TableCell("pae", NormalRaw)}
LegacyMemory == {TableCell("legacy", NormalRaw)}

\* @type: Seq($amd64PageEntry);
Long5Entries == <<TableEntry("pml5", NormalRaw),
  TableEntry("pml4", NormalRaw), TableEntry("pdpt", NormalRaw),
  TableEntry("pd", NormalRaw), TableEntry("pt", NormalRaw)>>
\* @type: Seq($amd64Carry);
Long5Carries == <<ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry, ZeroCarry>>
Long5Certificate == [entries |-> Long5Entries, carries |-> Long5Carries]

\* @type: Seq($amd64PageEntry);
PAEEntries == <<TableEntry("pdpt", PAEPDPTRaw), TableEntry("pd", NormalRaw),
  TableEntry("pt", NormalRaw)>>
\* @type: Seq($amd64Carry);
PAECarries == <<ZeroCarry, ZeroCarry, ZeroCarry>>
PAECertificate == [entries |-> PAEEntries, carries |-> PAECarries]

\* @type: Seq($amd64PageEntry);
LegacyEntries == <<TableEntry("pd", NormalRaw), TableEntry("pt", NormalRaw)>>
\* @type: Seq($amd64Carry);
LegacyCarries == <<ZeroCarry, ZeroCarry>>
LegacyCertificate == [entries |-> LegacyEntries, carries |-> LegacyCarries]

\* @type: Seq($amd64PageEntry);
Long4OneGiBEntries == <<TableEntry("pml4", NormalRaw),
  TableEntry("pdpt", LargeRaw)>>
\* @type: Seq($amd64Carry);
TwoCarries == <<ZeroCarry, ZeroCarry>>
Long4OneGiBCertificate == [entries |-> Long4OneGiBEntries, carries |-> TwoCarries]

\* @type: Seq($amd64PageEntry);
Long4TwoMiBEntries == <<TableEntry("pml4", NormalRaw),
  TableEntry("pdpt", NormalRaw), TableEntry("pd", LargeRaw)>>
Long4TwoMiBCertificate == [entries |-> Long4TwoMiBEntries, carries |-> PAECarries]

\* @type: Seq($amd64PageEntry);
LegacyFourMiBEntries == <<TableEntry("pd", LargeRaw)>>
\* @type: Seq($amd64Carry);
OneCarry == <<ZeroCarry>>
LegacyFourMiBCertificate == [entries |-> LegacyFourMiBEntries, carries |-> OneCarry]

\* @type: Seq($amd64PageEntry);
AbsentEntries == <<TableEntry("pml4", NormalRaw),
  TableEntry("pdpt", NormalRaw), TableEntry("pd", AbsentRaw)>>
AbsentCertificate == [entries |-> AbsentEntries, carries |-> PAECarries]

\* @type: Seq($amd64PageEntry);
NXEntries == <<TableEntry("pml4", NXRaw)>>
NXCertificate == [entries |-> NXEntries, carries |-> OneCarry]

SuccessfulVariants ==
  /\ SuccessfulWalk(Long4, Zeros, 12, Long4Memory, Long4Certificate)
  /\ SuccessfulWalkConcrete(ConcreteFor("long4", NormalRaw), Long4,
       Zeros, 12, Long4Memory, Long4Certificate)
  /\ SuccessfulWalk(Long5, Zeros, 12, Long4Memory, Long5Certificate)
  /\ SuccessfulWalk(PAE, Zeros, 12, PAEMemory, PAECertificate)
  /\ SuccessfulWalk(Legacy, Zeros, 12, LegacyMemory, LegacyCertificate)
  /\ DerivedPage(Long4, Zeros, 12, Long4Certificate).writable
  /\ DerivedPage(Long4, Zeros, 12, Long4Certificate).user
  /\ DerivedPage(Long4, Zeros, 12, Long4Certificate).executable
  /\ DerivedPage(Long4, Zeros, 12, Long4Certificate).offsetBits = 12
  /\ DerivedPage(PAE, Zeros, 12, PAECertificate).writable
  /\ DerivedPage(PAE, Zeros, 12, PAECertificate).user

LargePages ==
  /\ SuccessfulWalk(Long4, Zeros, 30,
                        {TableCell("long4", NormalRaw), TableCell("long4", LargeRaw)},
                        Long4OneGiBCertificate)
     /\ SuccessfulWalk(Long4, Zeros, 21,
                        {TableCell("long4", NormalRaw), TableCell("long4", LargeRaw)},
                        Long4TwoMiBCertificate)
     /\ SuccessfulWalk(Legacy, Zeros, 22, {TableCell("legacy", LargeRaw)},
                        LegacyFourMiBCertificate)
     /\ PageMapWellFormed({DerivedPage(Legacy, Zeros, 22,
                                       LegacyFourMiBCertificate)})
     /\ MappingMatches(Zeros, DerivedPage(Legacy, Zeros, 22,
                                          LegacyFourMiBCertificate))
     /\ TranslateAddress(Zeros, DerivedPage(Legacy, Zeros, 22,
                                            LegacyFourMiBCertificate), Zeros)

UnavailableContract == ~SuccessfulWalk(Long4, Zeros, 12,
  {UnavailableCell("long4", NormalRaw)}, Long4Certificate)

\* @type: Seq($amd64PageEntry);
FirstAbsentEntries == <<TableEntry("pml4", AbsentRaw)>>
FirstAbsentCertificate == [entries |-> FirstAbsentEntries, carries |-> OneCarry]
FirstAbsentMemory == {TableCell("long4", AbsentRaw)}
ConcreteFirstAbsent == ConcreteFor("long4", AbsentRaw)

MissingContract ==
  /\ FailedWalkConcrete(ConcreteFirstAbsent, Long4, Zeros, 12,
          FirstAbsentMemory, FirstAbsentCertificate, 1, "not-present")
     /\ FailedWalkAt(Long4, Zeros, 12,
          {TableCell("long4", NormalRaw), TableCell("long4", AbsentRaw)},
          AbsentCertificate, 3, "not-present")
     /\ FailedADUpdates(Long4, AbsentCertificate, 3) =
          {[position |-> position, physical |-> Zeros,
            setAccessed |-> TRUE, setDirty |-> FALSE] : position \in 1..2}
     /\ ~FailedWalkFault(Long4, AbsentCertificate, 3, "not-present", 3,
                         WriteAccess).errorCode.present
     /\ FailedWalkFault(Long4, AbsentCertificate, 3, "not-present", 3,
                        WriteAccess).errorCode.write
     /\ FailedWalkFault(Long4, AbsentCertificate, 3, "not-present", 3,
                        WriteAccess).errorCode.user

ReservedContract ==
  LET nxeOff == [Long4 EXCEPT !.nxe = FALSE]
  IN /\ FailedWalkAt(nxeOff, Zeros, 12,
          {TableCell("long4", NormalRaw), TableCell("long4", NXRaw)},
          NXCertificate, 1, "reserved")
     /\ FailedWalkFault(nxeOff, NXCertificate, 1, "reserved", 0,
                        FetchAccess).errorCode.reserved
     /\ ~FailedWalkFault(nxeOff, NXCertificate, 1, "reserved", 0,
                         FetchAccess).errorCode.instructionDefined
     /\ ~FailedWalkFault(nxeOff, NXCertificate, 1, "reserved", 0,
                         FetchAccess).errorCode.instruction

FailureContracts == UnavailableContract /\ MissingContract /\ ReservedContract

SideEffectContracts ==
  LET updates == SuccessfulADUpdates(Long4, Long4Certificate, TRUE)
      paeReadUpdates == SuccessfulADUpdates(PAE, PAECertificate, FALSE)
  IN /\ [position |-> 4, physical |-> Zeros,
          setAccessed |-> TRUE, setDirty |-> TRUE] \in updates
     /\ Cardinality(updates) = 4
     /\ Cardinality(paeReadUpdates) = 2
     /\ \A update \in paeReadUpdates : ~update.setDirty

VARIABLE
  \* @type: Bool;
  checked

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ SuccessfulVariants /\ LargePages /\
          FailureContracts /\ SideEffectContracts

======================================================================
