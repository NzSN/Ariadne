---------------- MODULE AMD64MemoryExceptionsChecks ----------------
EXTENDS AMD64Exceptions

Zeros == [bit \in AddressBits |-> FALSE]
LowOne == [bit \in AddressBits |-> bit = 1]
Bit13 == [bit \in AddressBits |-> bit = 13]
NonCanonical48 == [bit \in AddressBits |-> bit = 64]
ZeroByte == [bit \in ByteBits |-> FALSE]
OneByte == [bit \in ByteBits |-> bit = 1]
ZeroCarry == [bit \in 1..65 |-> FALSE]
AddOneCarry == [bit \in 1..65 |-> bit = 2]
LegacyBase == [bit \in AddressBits |-> bit \in 17..32]
LegacyOffset == [bit \in AddressBits |-> bit = 18]
LegacyRawSum == [bit \in AddressBits |-> bit \in {17, 33}]
LegacyLinear == [bit \in AddressBits |-> bit = 17]
LegacyWrapCarry == [bit \in 1..65 |-> bit \in 19..33]
RealBaseFFFF == [bit \in AddressBits |-> bit \in 5..20]
RealOffset10 == [bit \in AddressBits |-> bit = 5]
HMA100000 == [bit \in AddressBits |-> bit = 21]
RealHMACarry == [bit \in 1..65 |-> bit \in 6..21]

FlatSegment == [base |-> Zeros, limit |-> [bit \in AddressBits |-> TRUE],
  present |-> TRUE, readable |-> TRUE, writable |-> TRUE,
  executable |-> FALSE, conforming |-> FALSE,
  expandDown |-> FALSE, defaultBig |-> TRUE,
  unusable |-> FALSE,
  dpl |-> 3, rpl |-> 3]

ReadAccess == [kind |-> "read", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]
StackRead == [kind |-> "read", stack |-> TRUE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]
WriteAccess == [kind |-> "write", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]
FetchAccess == [kind |-> "fetch", stack |-> FALSE,
  implicitSupervisor |-> FALSE, shadow |-> FALSE]

BaseConfig == [virtualBits |-> 48, paging |-> TRUE,
  a20Enabled |-> TRUE, cr0AM |-> TRUE, cr0WP |-> TRUE, cr4PAE |-> TRUE,
  cr4SMEP |-> TRUE, cr4SMAP |-> TRUE, cr4PKE |-> TRUE, cr4CET |-> TRUE,
  eferNXE |-> TRUE,
  iopl |-> 0, pkruAD |-> [key \in 0..15 |-> FALSE],
  pkruWD |-> [key \in 0..15 |-> FALSE]]

UserPage == [linearTag |-> Zeros, physicalTag |-> Bit13,
  offsetBits |-> 12, present |-> TRUE, writable |-> TRUE,
  user |-> TRUE, executable |-> TRUE, reserved |-> FALSE,
  shadowStack |-> FALSE, protectionKey |-> 0]

SupervisorPage == [UserPage EXCEPT !.user = FALSE]
ReadOnlyPage == [UserPage EXCEPT !.writable = FALSE]
NXPage == [UserPage EXCEPT !.executable = FALSE]

ExpectedPhysicalOne == [bit \in AddressBits |-> bit \in {1, 13}]

AddressContracts ==
  /\ AddressWellFormed(Zeros) /\ AddressWellFormed(NonCanonical48)
  /\ AddressSizePermitted("long64", 64, 64)
  /\ AddressSizePermitted("long64", 64, 32)
  /\ ~AddressSizePermitted("long64", 64, 16)
  /\ AddressSizePermitted("compatibility", 32, 16)
  /\ Canonical(Zeros, 48)
  /\ ~Canonical(NonCanonical48, 48)
  /\ EffectiveOffset(NonCanonical48, 32) = Zeros
  /\ EffectiveSegmentBase("long64", "ds", [FlatSegment EXCEPT !.base = Bit13]) = Zeros
  /\ EffectiveSegmentBase("long64", "fs", [FlatSegment EXCEPT !.base = Bit13]) = Bit13
  /\ WordAddWithCarry(Zeros, Zeros, Zeros, ZeroCarry)
  /\ WordAddWithCarry(LowOne, LowOne, [bit \in AddressBits |-> bit = 2], AddOneCarry)
  /\ SegmentLinearWithCarry("protected", LegacyBase, LegacyOffset,
       LegacyRawSum, LegacyWrapCarry, LegacyLinear)
  /\ SegmentLinearWithCarry("real", RealBaseFFFF, RealOffset10,
       HMA100000, RealHMACarry, HMA100000)
  /\ ApplyA20(BaseConfig, "real", HMA100000) = HMA100000
  /\ ApplyA20([BaseConfig EXCEPT !.a20Enabled = FALSE],
              "real", HMA100000) = Zeros

TranslationContracts ==
  /\ MappingMatches(LowOne, UserPage)
  /\ PageMapWellFormed({UserPage})
  /\ ~PageMapWellFormed({UserPage, ReadOnlyPage})
  /\ TranslateAddress(LowOne, UserPage, ExpectedPhysicalOne)
  /\ PagePermits(BaseConfig, 3, FALSE, UserPage, ReadAccess)
  /\ ~PagePermits(BaseConfig, 3, FALSE, SupervisorPage, ReadAccess)
  /\ ~PagePermits(BaseConfig, 3, FALSE, ReadOnlyPage, WriteAccess)
  /\ ~PagePermits(BaseConfig, 0, FALSE, NXPage, FetchAccess)
  /\ PagePermits(BaseConfig, 0, TRUE, UserPage, ReadAccess)
  /\ ~PagePermits(BaseConfig, 0, FALSE, UserPage, ReadAccess)
  /\ PagePermits([BaseConfig EXCEPT !.pkruWD = [key \in 0..15 |-> key = 0]],
                  3, FALSE, UserPage, ReadAccess)
  /\ ~PageFaultError(
       [BaseConfig EXCEPT !.pkruWD = [key \in 0..15 |-> key = 0]],
       3, FALSE, UserPage, ReadAccess).protectionKey
  /\ PageFaultError(
       [BaseConfig EXCEPT !.pkruAD = [key \in 0..15 |-> key = 0]],
       3, FALSE, UserPage, ReadAccess).protectionKey

FaultContracts ==
  LET nonCanonical == MemoryFaultCandidates(BaseConfig, "long64", 3, FALSE,
        "ds", FlatSegment, NonCanonical48, NonCanonical48, <<NonCanonical48>>,
        {UserPage}, ReadAccess, 0)
      stackNonCanonical == MemoryFaultCandidates(BaseConfig, "long64", 3, FALSE,
        "ss", FlatSegment, NonCanonical48, NonCanonical48, <<NonCanonical48>>,
        {UserPage}, StackRead, 0)
      crossCanonical == MemoryFaultCandidates(BaseConfig, "long64", 3, FALSE,
        "ds", FlatSegment, Zeros, NonCanonical48, <<Zeros, NonCanonical48>>,
        {UserPage}, ReadAccess, 0)
      missingPage == MemoryFaultCandidates(BaseConfig, "long64", 3, FALSE,
        "ds", FlatSegment, Zeros, Zeros, <<Zeros>>, {}, ReadAccess, 0)
      missingWrite == MemoryFaultCandidates(BaseConfig, "long64", 3, FALSE,
        "ds", FlatSegment, Zeros, Zeros, <<Zeros>>, {}, WriteAccess, 0)
      unaligned == MemoryFaultCandidates([BaseConfig EXCEPT !.paging = FALSE],
        "long64", 3, TRUE, "ds", FlatSegment, LowOne, LowOne, <<LowOne>>,
        {}, ReadAccess, 1)
      limitFault == MemoryFaultCandidates([BaseConfig EXCEPT !.paging = FALSE],
        "protected", 3, FALSE, "ds", [FlatSegment EXCEPT !.limit = Zeros],
        LowOne, LowOne, <<LowOne>>, {}, ReadAccess, 0)
  IN /\ \E fault \in nonCanonical : fault.stage = 1 /\ fault.vector = "GP"
     /\ \E fault \in stackNonCanonical : fault.stage = 1 /\ fault.vector = "SS"
     /\ \E fault \in crossCanonical : fault.stage = 1 /\ fault.vector = "GP"
     /\ \E fault \in missingPage : fault.stage = 2 /\ fault.vector = "PF"
     /\ \E fault \in missingWrite :
          fault.errorCode.write /\ fault.errorCode.user /\ ~fault.errorCode.present
     /\ MissingPageFaultError(BaseConfig, 3, FetchAccess).instructionDefined
     /\ MissingPageFaultError(BaseConfig, 3, FetchAccess).instruction
     /\ ~MissingPageFaultError([BaseConfig EXCEPT !.cr4PAE = FALSE],
                                3, FetchAccess).instructionDefined
     /\ \E fault \in unaligned : fault.stage = 3 /\ fault.vector = "AC"
     /\ \E fault \in limitFault : fault.stage = 1 /\ fault.vector = "GP"
     /\ UniqueFaultCandidate(nonCanonical)
     /\ UniqueFaultCandidate(stackNonCanonical)
     /\ UniqueFaultCandidate(crossCanonical)
     /\ UniqueFaultCandidate(missingPage)
     /\ UniqueFaultCandidate(missingWrite)
     /\ UniqueFaultCandidate(unaligned)
     /\ UniqueFaultCandidate(limitFault)
     /\ CommonFaultPriority(nonCanonical \cup stackNonCanonical \cup crossCanonical \cup
                            missingPage \cup missingWrite \cup unaligned \cup
                            limitFault)

MemoryContracts ==
  LET before == {[physical |-> Zeros, value |-> ZeroByte]}
      after == {[physical |-> Zeros, value |-> OneByte]}
      captured == {Zeros}
      unavailable == [kind |-> "unavailable", value |-> ZeroByte]
  IN /\ MemoryWellFormed(before)
     /\ CapturedMemoryWellFormed(before, captured)
     /\ ReadByte(before, Zeros, ZeroByte)
     /\ ReadByteResult(before, captured, LowOne, unavailable)
     /\ WriteByte(before, Zeros, OneByte, after)
     /\ ReadByte(after, Zeros, OneByte)

EmptyRestart == [savedIP |-> Zeros, resumeIP |-> Zeros,
  completedIterations |-> 0, remainingIterations |-> 0]
GPException == [vector |-> "GP", class |-> "fault", errorCode |-> 0,
  hasErrorCode |-> TRUE, cr2 |-> Zeros, hasCR2 |-> FALSE,
  restart |-> EmptyRestart]
ACException == [vector |-> "AC", class |-> "fault", errorCode |-> 0,
  hasErrorCode |-> TRUE, cr2 |-> Zeros, hasCR2 |-> FALSE,
  restart |-> EmptyRestart]
\* @type: Seq($amd64Effect);
Effects == <<[kind |-> "memoryWrite", index |-> 1],
             [kind |-> "registerWrite", index |-> 2]>>
Rollback == RollbackFault(Zeros, GPException, Effects)
Prefix == PrefixFault(Zeros, GPException, Effects, 1, 3, 1)
Progress == InProgressOutcome(
  [savedIP |-> Zeros, resumeIP |-> Zeros,
   completedIterations |-> 1, remainingIterations |-> 1],
  GPException, Effects, 1)
Trapped == Trap(Zeros, ACException, Effects)

RestartContracts ==
  /\ AlignmentExceptionWellFormed(ACException)
  /\ OutcomeWellFormed(Rollback) /\ RestartContract(Rollback)
  /\ Rollback.committed = 0 /\ CommittedPrefix(Effects, Rollback.committed) = <<>>
  /\ OutcomeWellFormed(Prefix) /\ Prefix.committed = 1
  /\ Prefix.progress.completedIterations = 3
  /\ CommittedPrefix(Effects, Prefix.committed) = <<Head(Effects)>>
  /\ OutcomeWellFormed(Progress) /\ Progress.kind = "inProgress"
  /\ ~Progress.hasException /\ Progress.hasProgress
  /\ OutcomeWellFormed(Trapped) /\ Trapped.committed = Len(Effects)
  /\ Trapped.exception.errorCode = 0 /\ Trapped.exception.hasErrorCode
  /\ Trapped.exception.restart.completedIterations = 0

VARIABLE
  \* @type: Bool;
  checked

Init == checked = FALSE
Next == checked' = ~checked
Safety == checked \in BOOLEAN /\ AddressContracts /\ TranslationContracts /\
          FaultContracts /\ MemoryContracts /\ RestartContracts

====================================================================
